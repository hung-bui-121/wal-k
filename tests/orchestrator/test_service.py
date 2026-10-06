import asyncio
from collections.abc import Awaitable, Callable

import pytest

from tests.orchestrator.conftest import Kernel, KernelFactory
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.decisions import AutonomyLevel, DecisionCategory, Escalation
from walk.hooks import Hook, HookContext, HookName
from walk.orchestrator import DEFAULT_POLL_INTERVAL_S, Orchestrator
from walk.runtime import AgentRunState, CheckpointKind
from walk.telemetry import LedgerEventKind
from walk.workflow import PhaseDecision, WorkItemState

K = LedgerEventKind
WAIT_S = 10.0
ATTEMPTS = 1000


async def _eventually(check: Callable[[], Awaitable[bool]]) -> None:
    for _ in range(ATTEMPTS):
        if await check():
            return
        await asyncio.sleep(0.01)
    msg = "condition not reached"
    raise AssertionError(msg)


def _record(kernel: Kernel, name: HookName) -> list[HookContext]:
    fired: list[HookContext] = []

    async def record(ctx: HookContext) -> None:
        fired.append(ctx)

    kernel.env.hooks.register(Hook(name=name, id=f"test.{name.value}", kind="builtin"), record)
    return fired


async def test_run_once_starts_and_waits(make_kernel: KernelFactory) -> None:
    kernel = await make_kernel()
    story = await kernel.make_ready()
    started_hooks = _record(kernel, HookName.ON_PROJECT_START)

    started = await kernel.orchestrator.run_once()

    assert started == 1
    project_started = await kernel.env.ledger.query(kinds=[K.PROJECT_STARTED])
    assert len(project_started) == 1
    assert project_started[0].payload == {
        "kernel_instance": "instance-a",
        "interrupted": 0,
        "resumed_native": 0,
        "restarted_with_handover": 0,
        "requeued": 0,
        "failed": 0,
    }
    assert len(started_hooks) == 1
    (run,) = await kernel.env.runs.for_item(story.id)
    assert run.state is AgentRunState.COMPLETED
    status = kernel.orchestrator.status()
    assert status.active_runs == []
    assert status.phase_progress == {WorkItemState.READY_FOR_REVIEW: 1}
    assert DEFAULT_POLL_INTERVAL_S == 5.0


async def test_wake_triggers_tick_and_stop_ends_loop(make_kernel: KernelFactory) -> None:
    kernel = await make_kernel(poll_interval_s=60.0)
    orchestrator = kernel.orchestrator
    with pytest.raises(ConfigError, match="status not built"):
        orchestrator.status()
    loop = asyncio.create_task(orchestrator.start())
    try:

        async def started() -> bool:
            return bool(await kernel.env.ledger.query(kinds=[K.PROJECT_STARTED]))

        await _eventually(started)
        story = await kernel.make_ready()
        await orchestrator.wake()

        async def completed() -> bool:
            runs = await kernel.env.runs.for_item(story.id)
            return [run.state for run in runs] == [AgentRunState.COMPLETED]

        await _eventually(completed)
    finally:
        await orchestrator.stop()
        async with asyncio.timeout(WAIT_S):
            await loop

    (run,) = await kernel.env.runs.for_item(story.id)
    assert run.state is AgentRunState.COMPLETED


async def test_stop_drain_modes(make_kernel: KernelFactory) -> None:
    kernel = await make_kernel()
    first = await kernel.make_ready()
    assert await kernel.orchestrator.tick() == 1

    await kernel.orchestrator.stop(drain=True)

    (paused,) = await kernel.env.runs.for_item(first.id)
    assert paused.state is AgentRunState.PAUSED_BY_USER
    assert kernel.env.checkpoints_of(paused.id)[-1].kind is CheckpointKind.PAUSE

    second = await kernel.add_story(2, "Wall slide")
    assert await kernel.orchestrator.tick() == 1
    await kernel.orchestrator.stop(drain=False)

    (abandoned,) = await kernel.env.runs.for_item(second.id)
    assert abandoned.state is AgentRunState.RUNNING
    assert kernel.env.executor.running() == []

    successor = await make_kernel(kernel_instance="instance-b")
    report = await successor.recovery.recover()
    await successor.env.settle()

    assert report.interrupted == [abandoned.id]
    assert len(report.resumed_native) + len(report.restarted_with_handover) == 1
    continued = [r for r in await successor.env.runs.for_item(second.id) if r.parent_run_id]
    assert [r.state for r in continued] == [AgentRunState.COMPLETED]


async def test_deferred_methods_name_their_story(make_kernel: KernelFactory) -> None:
    orchestrator: Orchestrator = (await make_kernel()).orchestrator
    escalation = Escalation(
        id="ESC-1",
        from_role=AgentRole.SENIOR_DEV,
        to_level=AutonomyLevel.LOCAL,
        category=DecisionCategory.TECH,
        question="which?",
        options=[],
        recommendation=None,
        evidence_ids=[],
        work_item_id=None,
        run_id=None,
    )
    calls = {
        "E03-S09": orchestrator.submit_feature("t", "d", []),
        "E06-S04": orchestrator.plan_phase("PHASE-01"),
        "E07-S02": orchestrator.start_phase("PHASE-01"),
        "E07-S04": orchestrator.request_phase_review("PHASE-01"),
        "E07-S05": orchestrator.decide_phase("PHASE-01", PhaseDecision.GO, None, "user"),
        "E05-S02": orchestrator.handle_escalation(escalation),
        "E02-S13": orchestrator.pause(None),
        "E03-S16": orchestrator.force_review("STORY-0001"),
    }
    for story, call in calls.items():
        with pytest.raises(ConfigError, match=f"implemented in {story}"):
            await call
    for call in (orchestrator.resume(None), orchestrator.cancel_work_item("STORY-0001", "x")):
        with pytest.raises(ConfigError, match="implemented in E02-S13"):
            await call
