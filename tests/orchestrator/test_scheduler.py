from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_model_adapter import FakeModelAdapter, fake_descriptor
from tests.orchestrator.conftest import Kernel, KernelFactory
from tests.runtime.conftest import make_run
from tests.runtime.executor_env import CLAUDE_MODEL, CODEX_MODEL, script
from walk.agents import AgentInput, Handover
from walk.budgets import BudgetDimension, BudgetScope, BudgetSubject
from walk.common.enums import Effort
from walk.common.roles import AgentRole
from walk.model_router import AgentEvent, ModelAdapter, RunSession
from walk.orchestrator import ADMISSION_EVENTS, DEFAULT_MAX_PARALLEL_AGENTS
from walk.persistence import UnitOfWork
from walk.runtime import AgentRunState, HandoverRepository
from walk.telemetry import LedgerEventKind
from walk.workflow import (
    Feature,
    ProjectRepository,
    Risk,
    StoryContract,
    TransitionContext,
    TransitionSource,
    WorkItemKind,
    WorkItemState,
)

AT = datetime(2026, 1, 1, tzinfo=UTC)
K = LedgerEventKind


class InputRecorder(FakeModelAdapter):
    """Keeps the `AgentInput` of every run it starts."""

    inputs: list[AgentInput]

    def run(self, input: AgentInput, session: RunSession) -> AsyncIterator[AgentEvent]:  # noqa: A002 - parameter name fixed by INTERFACES §2.1
        self.inputs.append(input)
        return super().run(input, session)


def _recording_adapters(clock: FakeClock) -> tuple[dict[str, ModelAdapter], InputRecorder]:
    codex = InputRecorder(
        "fake-codex", [fake_descriptor(CODEX_MODEL, "fake-codex")], script(), clock
    )
    codex.inputs = []
    claude = FakeModelAdapter(
        "fake-claude", [fake_descriptor(CLAUDE_MODEL, "fake-claude")], script(), clock
    )
    return {"fake-codex": codex, "fake-claude": claude}, codex


async def _state(kernel: Kernel, item_id: str) -> WorkItemState:
    item = await kernel.env.items.get(item_id)
    assert item is not None
    return item.state


async def _runs(kernel: Kernel) -> int:
    return int(kernel.env.db.connect().execute("SELECT COUNT(*) FROM agent_runs").fetchone()[0])


async def test_tick_admits_ready_story(make_kernel: KernelFactory) -> None:
    kernel = await make_kernel()
    story = await kernel.make_ready()

    started = await kernel.scheduler.tick()
    await kernel.env.settle()

    assert started == 1
    transition = (await kernel.env.items.transitions(story.id, limit=None))[-1]
    assert transition.event == "start_implementation"
    assert transition.from_state is WorkItemState.READY
    assert transition.to_state is WorkItemState.IMPLEMENTING
    assert transition.actor_role is AgentRole.KERNEL
    assert transition.source is TransitionSource.KERNEL
    (run,) = await kernel.env.runs.for_item(story.id)
    selected = (await kernel.env.events(run.id, K.MODEL_SELECTED))[0]
    assert selected.payload["reason"] == "preferred"
    assert selected.payload["is_fallback"] is False
    record = await kernel.idempotency.get(f"schedule:{story.id}:READY:0")
    assert record is not None
    assert record.result_ref == run.id
    assert record.operation == "schedule"
    assert run.state is AgentRunState.COMPLETED
    assert ADMISSION_EVENTS[(WorkItemKind.STORY, WorkItemState.READY)] == "start_implementation"
    assert DEFAULT_MAX_PARALLEL_AGENTS == 2


async def test_tick_is_idempotent_per_state_version(make_kernel: KernelFactory) -> None:
    kernel = await make_kernel(max_parallel_runs=3)
    story = await kernel.make_ready()

    first = await kernel.scheduler.tick()
    # A stale READY view of the same state_version (e.g. replayed after a crash) is skipped:
    # while the first run is RUNNING (one run per item) and after it ended (the key).
    async with UnitOfWork(kernel.env.db) as uow:
        await kernel.env.items.upsert(story, uow)
    while_running = await kernel.scheduler.tick()
    await kernel.env.settle()
    async with UnitOfWork(kernel.env.db) as uow:
        await kernel.env.items.upsert(story, uow)
    after_end = await kernel.scheduler.tick()

    assert (first, while_running, after_end) == (1, 0, 0)
    assert await _runs(kernel) == 1


async def test_tick_skips_items_whose_agent_cannot_be_built(make_kernel: KernelFactory) -> None:
    kernel = await make_kernel()
    contract = StoryContract(goal="needs unity", constraints=["tool:unity.compile"])
    story = await kernel.make_ready(contract=contract)

    assert await kernel.scheduler.tick() == 0
    assert await _state(kernel, story.id) is WorkItemState.READY
    assert kernel.telemetry.counters["scheduler.instantiate_failed"] == 1


async def test_tick_respects_max_parallel_agents(make_kernel: KernelFactory) -> None:
    kernel = await make_kernel(max_parallel_agents=2, max_parallel_runs=3)
    await kernel.make_ready()
    await kernel.add_story(2, "Wall slide")
    third = await kernel.add_story(3, "Dash")

    started = await kernel.scheduler.tick()

    assert started == 2
    assert await _state(kernel, third.id) is WorkItemState.READY
    await kernel.env.settle()
    assert await kernel.scheduler.tick() == 1
    await kernel.env.settle()
    assert await _runs(kernel) == 3


async def test_tick_respects_role_parallelism(make_kernel: KernelFactory) -> None:
    kernel = await make_kernel(max_parallel_runs=1)
    await kernel.make_ready()
    second = await kernel.add_story(2, "Wall slide")

    started = await kernel.scheduler.tick()

    assert started == 1
    assert await _state(kernel, second.id) is WorkItemState.READY
    assert kernel.telemetry.counters["scheduler.role_busy"] == 1
    await kernel.env.settle()


async def test_tick_skips_items_that_cannot_run_in_parallel(make_kernel: KernelFactory) -> None:
    kernel = await make_kernel(max_parallel_runs=3)
    await kernel.make_ready(branch="feat/shared")
    second = await kernel.add_story(2, "Wall slide", branch="feat/shared")

    started = await kernel.scheduler.tick()

    assert started == 1
    assert await _state(kernel, second.id) is WorkItemState.READY
    assert kernel.telemetry.counters["scheduler.not_parallel"] == 1
    await kernel.env.settle()


async def test_tick_returns_zero_when_paused(make_kernel: KernelFactory) -> None:
    kernel = await make_kernel()
    story = await kernel.make_ready()
    projects = ProjectRepository(kernel.env.db)
    project = await projects.get("DEMO")
    assert project is not None
    async with UnitOfWork(kernel.env.db) as uow:
        await projects.upsert(project.model_copy(update={"paused": True}), uow)

    assert await kernel.scheduler.tick() == 0
    assert await _state(kernel, story.id) is WorkItemState.READY
    assert await kernel.env.items.transitions(story.id) == []


async def test_tick_skips_states_without_admission_event(make_kernel: KernelFactory) -> None:
    kernel = await make_kernel()
    await kernel.make_ready(state=WorkItemState.READY_FOR_REVIEW)
    async with UnitOfWork(kernel.env.db) as uow:
        await kernel.env.items.insert(
            Feature(id="FEAT-0001", project_key="DEMO", title="Movement"), uow
        )

    assert await kernel.scheduler.tick() == 0
    assert await _runs(kernel) == 0
    assert kernel.telemetry.counters["scheduler.not_admitted"] == 2


async def test_blocked_provider_skips_item(make_kernel: KernelFactory) -> None:
    kernel = await make_kernel(max_parallel_runs=3)
    first = await kernel.make_ready()
    second = await kernel.add_story(2, "Wall slide")
    for adapter in kernel.env.adapters.values():
        assert isinstance(adapter, FakeModelAdapter)
        adapter.set_healthy(False)

    assert await kernel.scheduler.tick() == 0
    assert await _state(kernel, first.id) is WorkItemState.READY
    assert await _state(kernel, second.id) is WorkItemState.READY
    assert kernel.telemetry.counters["scheduler.blocked_provider"] == 2


async def test_budget_guard_blocks_admission(make_kernel: KernelFactory) -> None:
    kernel = await make_kernel()
    story = await kernel.make_ready()
    budgets = kernel.env.budgets
    await budgets.ensure(BudgetScope.TASK, story.id, None, {BudgetDimension.TOOL_CALLS: 1})
    subject = BudgetSubject(project_key="DEMO", work_item_id=story.id)
    await budgets.meter(subject, BudgetDimension.TOOL_CALLS, 1)

    assert await kernel.scheduler.tick() == 0
    assert await _state(kernel, story.id) is WorkItemState.READY
    assert await _runs(kernel) == 0
    assert kernel.telemetry.counters["scheduler.admission_rejected"] == 1


async def test_tick_passes_open_handover(make_kernel: KernelFactory, fake_clock: FakeClock) -> None:
    adapters, codex = _recording_adapters(fake_clock)
    kernel = await make_kernel(adapters=adapters)
    story = await kernel.make_ready()
    previous = "RUN-01J0000000000000000000000P"
    async with UnitOfWork(kernel.env.db) as uow:
        await kernel.env.runs.insert(
            make_run(
                previous,
                state=AgentRunState.HANDED_OVER,
                model_id=CODEX_MODEL,
                provider="fake-codex",
                kernel_instance="old",
            ),
            uow,
        )
        handover = Handover(
            id="HO-0001",
            work_item_id=story.id,
            role=AgentRole.SENIOR_DEV,
            from_run_id=previous,
            from_model_id=CODEX_MODEL,
            reason="FALLBACK",
            task_summary="Double jump",
            current_state="READY",
            completed_work=[],
            modified_files=[],
            findings=[],
            hypotheses=[],
            decisions=[],
            risks=[],
            remaining_work=["all"],
            next_action="Start",
            worktree_head="a" * 40,
            branch="feat/story-0001",
            created_at=AT,
        )
        await HandoverRepository(kernel.env.db).insert(handover, uow)

    assert await kernel.scheduler.tick() == 1
    await kernel.env.settle()

    received = codex.inputs[0].handover
    assert received is not None
    assert received.id == "HO-0001"
    stored = await HandoverRepository(kernel.env.db).get("HO-0001")
    assert stored is not None
    run = next(r for r in await kernel.env.runs.for_item(story.id) if r.id != previous)
    assert stored.to_run_id == run.id
    assert run.handover_in_id == "HO-0001"


async def test_tick_uses_effort_resolution(make_kernel: KernelFactory) -> None:
    kernel = await make_kernel()
    story = await kernel.make_ready(risk=Risk.HIGH)

    assert await kernel.scheduler.tick() == 1
    await kernel.env.settle()

    (run,) = await kernel.env.runs.for_item(story.id)
    effort = (await kernel.env.events(run.id, K.EFFORT_SET))[0]
    assert effort.payload["role_default"] == "MEDIUM"
    assert effort.payload["complexity_component"] == "MEDIUM"
    assert effort.payload["risk_bump"] == 1
    assert effort.payload["effective"] == "HIGH"
    assert run.effort is Effort.HIGH


async def test_tick_counts_start_failures_and_continues(
    make_kernel: KernelFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    kernel = await make_kernel(max_parallel_runs=3)
    first = await kernel.make_ready()
    second = await kernel.add_story(2, "Wall slide")
    original = kernel.env.executor.start
    calls: list[str] = []

    async def failing_once(*args: object, **kwargs: object) -> object:
        item = args[1]
        calls.append(getattr(item, "id", ""))
        if len(calls) == 1:
            msg = "worktree disk full"
            raise RuntimeError(msg)
        return await original(*args, **kwargs)  # type: ignore[arg-type]  # forwarded unchanged

    monkeypatch.setattr(kernel.env.executor, "start", failing_once)

    assert await kernel.scheduler.tick() == 1
    await kernel.env.settle()

    assert calls == [first.id, second.id]
    assert kernel.telemetry.counters["scheduler.start_failed"] == 1


async def test_second_tick_starts_rework_run_on_same_branch(make_kernel: KernelFactory) -> None:
    # The second run writes one more file than the first, so its own END checkpoint commits.
    plans = iter([script(tool_calls=3), script(tool_calls=4)])
    kernel = await make_kernel(plan=lambda _input: next(plans))
    story = await kernel.make_ready()
    assert await kernel.scheduler.tick() == 1
    await kernel.env.settle()
    (first,) = await kernel.env.runs.for_item(story.id)
    assert first.state is AgentRunState.COMPLETED
    review = {
        "implementer_role": AgentRole.SENIOR_DEV.value,
        "reviewer_role": AgentRole.LEAD_DEV.value,
        "cross_model_review": False,
    }
    await kernel.env.workflow.raise_event(
        story.id,
        "start_review",
        TransitionContext(
            actor_role=AgentRole.KERNEL, source=TransitionSource.KERNEL, payload=review
        ),
    )
    await kernel.env.workflow.raise_event(
        story.id,
        "review_rejected",
        TransitionContext(actor_role=AgentRole.LEAD_DEV, source=TransitionSource.AGENT),
    )
    assert await _state(kernel, story.id) is WorkItemState.REWORK

    assert await kernel.scheduler.tick() == 1
    await kernel.env.settle()

    second = next(r for r in await kernel.env.runs.for_item(story.id) if r.id != first.id)
    assert second.state is AgentRunState.COMPLETED, second.failure_reason
    assert second.purpose == "IMPLEMENT"
    assert second.parent_run_id is None
    assert second.branch == first.branch
    assert second.worktree_path != first.worktree_path
    assert await kernel.env.events(second.id, K.ERROR) == []
    assert await _state(kernel, story.id) is WorkItemState.READY_FOR_REVIEW
