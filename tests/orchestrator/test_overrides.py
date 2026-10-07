import asyncio
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.hooks.conftest import DEADLOCK_GUARD_S, HoldingAdapter, holding_adapters
from tests.orchestrator.conftest import Kernel, KernelFactory, RecordingTelemetry
from tests.runtime.conftest import RUN_B, make_run
from tests.runtime.executor_env import CLAUDE_MODEL, CODEX_MODEL, builtin_deps, script
from walk.common.errors import ConfigError, GuardRejected
from walk.decisions import AutonomyLevel
from walk.orchestrator import DefaultOrchestrator, register_builtins
from walk.persistence import UnitOfWork
from walk.runtime import AgentRun, AgentRunState, CheckpointKind, HandoverRepository
from walk.telemetry import LedgerEventKind
from walk.workflow import Priority, ProjectRepository, Story, StoryContract, WorkItemState

if TYPE_CHECKING:
    from walk.model_router import ModelAdapter

K = LedgerEventKind


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def _exists(path: str) -> bool:
    return Path(path).exists()


def overriding(kernel: Kernel, policies: Path | None = None) -> DefaultOrchestrator:
    """The kernel's orchestrator wired with the E02-S13 override dependencies and builtins."""
    env = kernel.env
    register_builtins(env.hooks, builtin_deps(env, RecordingTelemetry()))
    return DefaultOrchestrator(
        kernel.scheduler,
        env.executor,
        kernel.recovery,
        kernel.status,
        env.hooks,
        env.ledger,
        env.executor._clock,  # noqa: SLF001 - the environment's clock
        project_key="DEMO",
        kernel_instance="instance-a",
        projects=ProjectRepository(env.db),
        workflow=env.workflow,
        policies_path=policies or env.db.path.parent / "agents" / "policies.yaml",
        model_known=lambda model: model in env.router.registry().models,
    )


async def _held(kernel: Kernel, story: Story | None = None) -> AgentRun:
    env = kernel.env
    run = await env.executor.start(env.agent, story or env.story, "IMPLEMENT")
    adapter = env.adapters[run.provider]
    assert isinstance(adapter, HoldingAdapter)
    await asyncio.wait_for(adapter.held(run.id).wait(), DEADLOCK_GUARD_S)
    return run


async def _story(kernel: Kernel, number: int, state: WorkItemState) -> Story:
    item = Story(
        id=f"STORY-{number:04d}",
        project_key="DEMO",
        title=f"Story {number}",
        state=state,
        contract=StoryContract(goal=f"Story {number}"),
    )
    async with UnitOfWork(kernel.env.db) as uow:
        await kernel.env.items.insert(item, uow)
    return item


async def _overrides(kernel: Kernel) -> list[dict[str, object]]:
    return [e.payload for e in await kernel.env.ledger.query(kinds=[K.USER_OVERRIDE])]


async def test_pause_project_checkpoints_and_pauses_runs(
    make_kernel: KernelFactory, fake_clock: FakeClock
) -> None:
    kernel = await make_kernel(adapters=holding_adapters(fake_clock), max_parallel_runs=2)
    orchestrator = overriding(kernel)
    first = await _held(kernel)
    second = await _held(kernel, await _story(kernel, 2, WorkItemState.IMPLEMENTING))

    await orchestrator.pause()

    project = await ProjectRepository(kernel.env.db).single()
    assert project.paused is True
    for run in (first, second):
        stored = await kernel.env.runs.get(run.id)
        assert stored is not None
        assert stored.state is AgentRunState.PAUSED_BY_USER
    pauses = [
        c
        for run in (first, second)
        for c in kernel.env.checkpoints_of(run.id)
        if c.kind is CheckpointKind.PAUSE
    ]
    assert len(pauses) == 2
    assert await _overrides(kernel) == [{"command": "pause", "args": {"run_id": None}}]
    assert await orchestrator.tick() == 0  # a paused project admits nothing


async def test_resume_project_restarts_runs(
    make_kernel: KernelFactory, fake_clock: FakeClock
) -> None:
    kernel = await make_kernel(adapters=holding_adapters(fake_clock))
    orchestrator = overriding(kernel)
    run = await _held(kernel)
    await orchestrator.pause()

    await orchestrator.resume()
    await kernel.env.settle()

    project = await ProjectRepository(kernel.env.db).single()
    assert project.paused is False
    paused = await kernel.env.runs.get(run.id)
    assert paused is not None
    assert paused.state is AgentRunState.HANDED_OVER
    continued = [r for r in await kernel.env.runs.for_item(run.work_item_id) if r.id != run.id]
    assert [(r.parent_run_id, r.state) for r in continued] == [(run.id, AgentRunState.COMPLETED)]
    assert [p["command"] for p in await _overrides(kernel)] == ["pause", "resume"]


async def test_pause_resume_single_agent(make_kernel: KernelFactory, fake_clock: FakeClock) -> None:
    kernel = await make_kernel(adapters=holding_adapters(fake_clock), max_parallel_runs=2)
    orchestrator = overriding(kernel)
    first = await _held(kernel)
    second = await _held(kernel, await _story(kernel, 2, WorkItemState.IMPLEMENTING))

    await orchestrator.pause(first.id)
    other = await kernel.env.runs.get(second.id)
    assert other is not None
    assert other.state is AgentRunState.RUNNING
    await orchestrator.resume(first.id)
    await kernel.env.executor.cancel(second.id, "test cleanup")
    await kernel.env.settle()

    project = await ProjectRepository(kernel.env.db).single()
    assert project.paused is False
    resumed = [r for r in await kernel.env.runs.for_item(first.work_item_id) if r.id != first.id]
    assert [(r.parent_run_id, r.state) for r in resumed] == [(first.id, AgentRunState.COMPLETED)]
    selected = await kernel.env.events(resumed[0].id, K.MODEL_SELECTED)
    assert selected[0].payload["reason"] == "native_resume"
    assert await _overrides(kernel) == [
        {"command": "pause", "args": {"run_id": first.id}},
        {"command": "resume", "args": {"run_id": first.id}},
    ]


async def test_cancel_work_item_cleans_up(
    make_kernel: KernelFactory, fake_clock: FakeClock
) -> None:
    kernel = await make_kernel(adapters=holding_adapters(fake_clock))
    orchestrator = overriding(kernel)
    run = await _held(kernel)

    await orchestrator.cancel_work_item(kernel.env.story.id, "scope dropped")

    item = await kernel.env.items.get(kernel.env.story.id)
    assert item is not None
    assert item.state is WorkItemState.CANCELLED
    stored = await kernel.env.runs.get(run.id)
    assert stored is not None
    assert (stored.state, stored.failure_reason) == (AgentRunState.CANCELLED, "scope dropped")
    assert not _exists(run.worktree_path or "")
    assert _git(kernel.env.repo, "branch", "--list", str(run.branch))
    assert await _overrides(kernel) == [
        {
            "command": "work.cancel",
            "args": {"work_item_id": kernel.env.story.id, "reason": "scope dropped"},
        }
    ]


async def test_cancel_complete_item_rejected(make_kernel: KernelFactory) -> None:
    kernel = await make_kernel()
    orchestrator = overriding(kernel)
    done = await _story(kernel, 3, WorkItemState.COMPLETE)

    with pytest.raises(GuardRejected, match="STORY-0003"):
        await orchestrator.cancel_work_item(done.id, "too late")

    assert await _overrides(kernel) == []


async def test_set_priority_persists_and_logs(make_kernel: KernelFactory) -> None:
    kernel = await make_kernel()
    orchestrator = overriding(kernel)
    story = await _story(kernel, 4, WorkItemState.READY)

    updated = await orchestrator.set_priority(story.id, Priority.P0, actor="user")

    assert updated.priority is Priority.P0
    stored = await kernel.env.items.get(story.id)
    assert stored is not None
    assert stored.priority is Priority.P0
    column = kernel.env.db.connect().execute(
        "SELECT priority FROM work_items WHERE id = ?", (story.id,)
    )
    assert column.fetchone()[0] == "P0"
    project = await orchestrator.set_autonomy(AutonomyLevel.MULTI_AGENT, actor="user")
    assert project.autonomy_level_max == 1
    assert await _overrides(kernel) == [
        {
            "command": "work.priority",
            "args": {"work_item_id": story.id, "priority": "P0", "actor": "user"},
        },
        {"command": "policy.set_autonomy", "args": {"level": 1, "actor": "user"}},
    ]


async def test_resume_without_a_resumable_session_continues_from_a_handover(
    make_kernel: KernelFactory, fake_clock: FakeClock
) -> None:
    plan = script(tool_calls=12, resumable=False)
    adapters: dict[str, ModelAdapter] = {
        "fake-codex": HoldingAdapter("fake-codex", CODEX_MODEL, plan, fake_clock, 2),
        "fake-claude": HoldingAdapter("fake-claude", CLAUDE_MODEL, plan, fake_clock, 2),
    }
    kernel = await make_kernel(adapters=adapters)
    orchestrator = overriding(kernel)
    run = await _held(kernel)
    await orchestrator.pause(run.id)

    continued = await kernel.env.executor.resume(run.id)
    codex = adapters["fake-codex"]
    assert isinstance(codex, HoldingAdapter)
    await asyncio.wait_for(codex.held(continued.id).wait(), DEADLOCK_GUARD_S)
    codex.release(continued.id)  # the new session holds after 2 calls too
    await asyncio.wait_for(kernel.env.settle(), DEADLOCK_GUARD_S)

    assert continued.parent_run_id == run.id
    assert continued.handover_in_id is not None
    handover = await HandoverRepository(kernel.env.db).get(continued.handover_in_id)
    assert handover is not None
    assert (handover.reason, handover.to_run_id) == ("PAUSE", continued.id)
    ended = await kernel.env.runs.get(continued.id)
    assert ended is not None
    assert ended.state is AgentRunState.COMPLETED


async def test_resume_refuses_runs_that_are_not_paused_and_unwired_overrides(
    make_kernel: KernelFactory, fake_clock: FakeClock
) -> None:
    kernel = await make_kernel(adapters=holding_adapters(fake_clock))
    run = await _held(kernel)
    stray = make_run(RUN_B, state=AgentRunState.PAUSED_BY_USER, work_item_id="STORY-0002")
    await _story(kernel, 2, WorkItemState.IMPLEMENTING)
    async with UnitOfWork(kernel.env.db) as uow:
        await kernel.env.runs.insert(stray, uow)

    with pytest.raises(ConfigError, match="not paused"):
        await kernel.env.executor.resume(run.id)
    with pytest.raises(ConfigError, match="no checkpoint"):
        await kernel.env.executor.resume(RUN_B)
    with pytest.raises(ConfigError, match="not wired"):
        await kernel.orchestrator.set_autonomy(AutonomyLevel.USER, actor="user")
    await kernel.env.executor.cancel(run.id, "test cleanup")


async def test_resume_project_logs_a_run_that_cannot_resume(
    make_kernel: KernelFactory, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    kernel = await make_kernel(adapters=holding_adapters(fake_clock))
    orchestrator = overriding(kernel)
    run = await _held(kernel)
    await orchestrator.pause()

    async def broken(run_id: str) -> AgentRun:
        msg = f"cannot resume {run_id}"
        raise ConfigError(msg)

    monkeypatch.setattr(kernel.env.executor, "resume", broken)

    await orchestrator.resume()

    project = await ProjectRepository(kernel.env.db).single()
    assert project.paused is False
    stored = await kernel.env.runs.get(run.id)
    assert stored is not None
    assert stored.state is AgentRunState.PAUSED_BY_USER
    with pytest.raises(ConfigError, match="unknown project"):
        async with UnitOfWork(kernel.env.db) as uow:
            await ProjectRepository(kernel.env.db).set_paused("NOPE", True, uow)  # noqa: FBT003 - the flag under test
