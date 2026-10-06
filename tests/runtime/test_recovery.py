import shutil
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_model_adapter import FakeModelAdapter, fake_descriptor
from tests.runtime.conftest import make_run
from tests.runtime.executor_env import (
    CLAUDE_MODEL,
    CODEX_MODEL,
    DyingAdapter,
    EnvFactory,
    ExecutorEnv,
    script,
)
from walk.hooks import Hook, HookContext, HookFailPolicy, HookName
from walk.model_router import ModelAdapter
from walk.persistence import UnitOfWork
from walk.runtime import (
    AgentRun,
    AgentRunState,
    Checkpoint,
    CheckpointKind,
    HandoverRepository,
    RecoveryManager,
    RecoveryReport,
)
from walk.telemetry import LedgerEventKind
from walk.workflow import Story, StoryContract, WorkItem, WorkItemState

K = LedgerEventKind


def _adapters(clock: FakeClock, *, die_after: int = 5) -> dict[str, ModelAdapter]:
    return {
        "fake-codex": DyingAdapter(
            "fake-codex", CODEX_MODEL, script(tool_calls=8), clock, die_after=die_after
        ),
        "fake-claude": FakeModelAdapter(
            "fake-claude",
            [fake_descriptor(CLAUDE_MODEL, "fake-claude")],
            script(tool_calls=8),
            clock,
        ),
    }


def _recovery(env: ExecutorEnv, instance: str) -> RecoveryManager:
    return RecoveryManager(
        env.runs,
        env.checkpoints,
        env.executor,
        env.router,
        env.agents,
        env.items,
        env.hooks,
        env.ledger,
        env.executor._clock,  # noqa: SLF001 - the env's clock
        kernel_instance=instance,
        project_key="DEMO",
        ready_env_keys=lambda: {"git"},
        sandbox=env.sandbox,
    )


async def _crash(env: ExecutorEnv, story: Story | None = None) -> AgentRun:
    started = await env.executor.start(env.agent, story or env.story, "IMPLEMENT")
    orphan = await env.executor.wait(started.id)
    assert orphan.state is AgentRunState.RUNNING
    return orphan


async def _settled(env: ExecutorEnv, report: RecoveryReport) -> list[AgentRun]:
    await env.settle()
    continued = [*report.resumed_native, *report.restarted_with_handover]
    return [await env.executor.wait(run_id) for run_id in continued]


async def test_recover_resumes_natively_when_possible(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapters = _adapters(fake_clock)
    old = await make_executor_env(adapters=adapters, kernel_instance="old", checkpoint_every=5)
    orphan = await _crash(old)
    new = await make_executor_env(adapters=adapters, kernel_instance="new")

    report = await _recovery(new, "new").recover()

    assert report.interrupted == [orphan.id]
    assert len(report.resumed_native) == 1
    assert report.restarted_with_handover == []
    assert report.requeued == []
    assert report.failed == []
    resumed = (await _settled(new, report))[0]
    assert resumed.state is AgentRunState.COMPLETED
    assert resumed.parent_run_id == orphan.id
    assert resumed.kernel_instance == "new"
    interrupted = (await new.events(orphan.id, K.ERROR))[0]
    assert interrupted.payload == {
        "kind": "INTERRUPTED",
        "previous_state": "RUNNING",
        "previous_kernel_instance": "old",
    }
    resumed_event = (await new.events(resumed.id, K.RECOVERY_RESUMED))[0]
    assert resumed_event.payload == {
        "from_run_id": orphan.id,
        "mode": "native",
        "checkpoint_seq": 2,
        "handover_id": None,
    }
    fired = new.hooks_fired(HookName.ON_RECOVERY_RESUME)
    assert [(ctx.run_id, ctx.payload["mode"]) for ctx in fired] == [(resumed.id, "native")]
    stored = await new.runs.get(orphan.id)
    assert stored is not None
    assert stored.state is AgentRunState.HANDED_OVER


async def test_recover_uses_handover_when_provider_unhealthy(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapters = _adapters(fake_clock)
    old = await make_executor_env(adapters=adapters, kernel_instance="old", checkpoint_every=5)
    orphan = await _crash(old)
    codex = adapters["fake-codex"]
    assert isinstance(codex, FakeModelAdapter)
    codex.set_healthy(False)
    new = await make_executor_env(adapters=adapters, kernel_instance="new")

    report = await _recovery(new, "new").recover()

    assert report.resumed_native == []
    restarted = (await _settled(new, report))[0]
    assert restarted.model_id == CLAUDE_MODEL
    assert restarted.handover_in_id == "HO-0001"
    assert restarted.parent_run_id == orphan.id
    assert restarted.worktree_path == orphan.worktree_path
    assert restarted.state is AgentRunState.COMPLETED
    handover = await HandoverRepository(new.db).get("HO-0001")
    assert handover is not None
    assert handover.reason == "RECOVERY"
    assert handover.to_run_id == restarted.id
    fallback = (await new.events(orphan.id, K.MODEL_FALLBACK))[0]
    assert fallback.payload == {
        "trigger": "PROVIDER_OUTAGE",
        "from": CODEX_MODEL,
        "to": CLAUDE_MODEL,
    }
    resumed_event = (await new.events(restarted.id, K.RECOVERY_RESUMED))[0]
    assert resumed_event.payload["mode"] == "handover"
    assert resumed_event.payload["handover_id"] == "HO-0001"
    assert [ctx.payload["to"] for ctx in new.hooks_fired(HookName.ON_MODEL_FALLBACK)] == [
        CLAUDE_MODEL
    ]


async def test_recover_after_restart_uses_handover_on_the_same_model(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    old = await make_executor_env(
        adapters=_adapters(fake_clock), kernel_instance="old", checkpoint_every=5
    )
    orphan = await _crash(old)
    # A new process: fresh adapters that never saw the orphan's provider session.
    new = await make_executor_env(
        adapters=_adapters(fake_clock, die_after=99), kernel_instance="new"
    )

    report = await _recovery(new, "new").recover()

    restarted = (await _settled(new, report))[0]
    assert restarted.model_id == CODEX_MODEL
    assert restarted.state is AgentRunState.COMPLETED
    assert restarted.handover_in_id == "HO-0001"
    assert await new.events(orphan.id, K.MODEL_FALLBACK) == []
    refused = [
        r for r in await new.runs.for_item(new.story.id) if r.failure_reason == "not_resumable"
    ]
    assert len(refused) == 1


async def test_recover_requeues_runs_without_checkpoint(
    make_executor_env: EnvFactory,
) -> None:
    env = await make_executor_env()
    orphan = make_run(
        "RUN-01J0000000000000000000000X",
        state=AgentRunState.RUNNING,
        kernel_instance="old",
        model_id=CODEX_MODEL,
        provider="fake-codex",
    )
    async with UnitOfWork(env.db) as uow:
        await env.runs.insert(orphan, uow)
        await env.items.set_assigned_run(env.story.id, orphan.id, conn=uow.conn)

    report = await _recovery(env, "new").recover()

    assert report.interrupted == [orphan.id]
    assert report.requeued == [env.story.id]
    item = await env.items.get(env.story.id)
    assert item is not None
    assert item.assigned_run_id is None
    stored = await env.runs.get(orphan.id)
    assert stored is not None
    assert stored.state is AgentRunState.INTERRUPTED


async def test_recover_isolates_failures(
    make_executor_env: EnvFactory, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapters = _adapters(fake_clock)
    old = await make_executor_env(adapters=adapters, kernel_instance="old", checkpoint_every=5)
    second_story = Story(
        id="STORY-0002",
        project_key="DEMO",
        title="Wall slide",
        state=WorkItemState.IMPLEMENTING,
        contract=StoryContract(goal="Slide down walls"),
    )
    async with UnitOfWork(old.db) as uow:
        await old.items.insert(second_story, uow)
    first = await _crash(old)
    second = await _crash(old, second_story)
    new = await make_executor_env(adapters=adapters, kernel_instance="new")
    resume = new.executor.resume_native

    async def broken_for_first(checkpoint: Checkpoint, *args: Any) -> AgentRun:
        if checkpoint.run_id == first.id:
            msg = "disk full"
            raise RuntimeError(msg)
        return await resume(checkpoint, *args)

    monkeypatch.setattr(new.executor, "resume_native", broken_for_first)

    report = await _recovery(new, "new").recover()

    assert report.interrupted == [first.id, second.id]
    assert report.failed == [(first.id, "disk full")]
    assert len(report.resumed_native) == 1
    stored = await new.runs.get(first.id)
    assert stored is not None
    assert stored.state is AgentRunState.FAILED
    assert stored.failure_reason == "recovery: disk full"
    resumed = (await _settled(new, report))[0]
    assert resumed.parent_run_id == second.id
    assert resumed.state is AgentRunState.COMPLETED


async def test_recover_is_idempotent(make_executor_env: EnvFactory, fake_clock: FakeClock) -> None:
    adapters = _adapters(fake_clock)
    old = await make_executor_env(adapters=adapters, kernel_instance="old", checkpoint_every=5)
    await _crash(old)
    new = await make_executor_env(adapters=adapters, kernel_instance="new")
    recovery = _recovery(new, "new")

    first = await recovery.recover()
    await _settled(new, first)
    second = await recovery.recover()

    assert len(first.interrupted) == 1
    assert second == RecoveryReport()


async def test_recover_reports_a_run_whose_item_vanished(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env()
    orphan = make_run(
        "RUN-01J0000000000000000000000Y",
        state=AgentRunState.RUNNING,
        kernel_instance="old",
        model_id=CODEX_MODEL,
        provider="fake-codex",
    )
    async with UnitOfWork(env.db) as uow:
        await env.runs.insert(orphan, uow)
    conn = env.db.connect()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DELETE FROM work_items WHERE id = ?", (env.story.id,))
    conn.execute("PRAGMA foreign_keys = ON")

    report = await _recovery(env, "new").recover()

    assert report.failed == [(orphan.id, f"work item not found: {env.story.id}")]


def _delete_tree(path: str) -> None:
    """Delete a worktree directory like `git clean -fdx` on `.walk/` would (read-only files too)."""

    def make_writable(func: Callable[[str], object], target: str, exc: BaseException) -> None:
        del exc
        Path(target).chmod(stat.S_IWRITE)
        func(target)

    shutil.rmtree(path, onexc=make_writable)


def _is_dir(path: str) -> bool:
    return Path(path).is_dir()


async def test_recover_recreates_deleted_worktree_before_handover(
    make_executor_env: EnvFactory, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapters = _adapters(fake_clock)
    old = await make_executor_env(adapters=adapters, kernel_instance="old", checkpoint_every=5)
    orphan = await _crash(old)
    assert orphan.worktree_path is not None
    _delete_tree(orphan.worktree_path)
    codex = adapters["fake-codex"]
    assert isinstance(codex, FakeModelAdapter)
    codex.set_healthy(False)
    new = await make_executor_env(adapters=adapters, kernel_instance="new")
    adopted: list[tuple[str, str, bool]] = []
    adopt = new.sandbox.adopt

    async def recording_adopt(run: AgentRun, previous: AgentRun, item: WorkItem) -> str:
        path = await adopt(run, previous, item)
        adopted.append((run.id, previous.id, _is_dir(path)))
        return path

    monkeypatch.setattr(new.sandbox, "adopt", recording_adopt)

    report = await _recovery(new, "new").recover()

    assert report.failed == []
    assert adopted[0] == (orphan.id, orphan.id, True)
    handoff = new.checkpoints_of(orphan.id)[-1]
    assert handoff.kind is CheckpointKind.HANDOFF
    handover = await HandoverRepository(new.db).get("HO-0001")
    assert handover is not None
    assert handover.reason == "RECOVERY"
    restarted = (await _settled(new, report))[0]
    assert restarted.parent_run_id == orphan.id
    assert restarted.worktree_path == orphan.worktree_path
    assert restarted.handover_in_id == "HO-0001"
    assert restarted.state is AgentRunState.COMPLETED, restarted.failure_reason


async def test_recover_failure_ends_run_and_unassigns_item(
    make_executor_env: EnvFactory, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapters = _adapters(fake_clock)
    old = await make_executor_env(adapters=adapters, kernel_instance="old", checkpoint_every=5)
    orphan = await _crash(old)
    new = await make_executor_env(adapters=adapters, kernel_instance="new")

    async def broken(checkpoint: Checkpoint) -> AgentRun:
        del checkpoint
        msg = "disk full"
        raise RuntimeError(msg)

    monkeypatch.setattr(new.executor, "resume_native", broken)

    report = await _recovery(new, "new").recover()

    assert report.failed == [(orphan.id, "disk full")]
    stored = await new.runs.get(orphan.id)
    assert stored is not None
    assert stored.state is AgentRunState.FAILED
    assert stored.failure_reason == "recovery: disk full"
    item = await new.items.get(new.story.id)
    assert item is not None
    assert item.assigned_run_id is None
    kinds = await new.kinds(orphan.id)
    assert kinds.count(K.AGENT_RUN_STARTED) == 1
    (ended,) = await new.events(orphan.id, K.AGENT_RUN_ENDED)
    assert ended.outcome == "FAILED"
    assert ended.payload == {
        "state": "FAILED",
        "failure_reason": "recovery: disk full",
        "mode": "recovery",
        "handover_in_id": None,
    }
    assert kinds.index(K.ERROR) < kinds.index(K.AGENT_RUN_ENDED)
    failed = new.hooks_fired(HookName.ON_TASK_FAILED)
    assert [(ctx.run_id, ctx.payload["state"]) for ctx in failed] == [(orphan.id, "FAILED")]


async def test_recover_failure_after_continuation_keeps_single_end(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapters = _adapters(fake_clock)
    old = await make_executor_env(adapters=adapters, kernel_instance="old", checkpoint_every=5)
    orphan = await _crash(old)
    new = await make_executor_env(adapters=adapters, kernel_instance="new")

    async def refuse(ctx: HookContext) -> None:
        del ctx
        msg = "resume hook refused"
        raise RuntimeError(msg)

    hook = Hook(
        name=HookName.ON_RECOVERY_RESUME,
        id="test.refuse",
        kind="builtin",
        priority=10,
        fail_policy=HookFailPolicy.FAIL_CLOSED,
        required=True,
    )
    new.hooks.register(hook, refuse)

    report = await _recovery(new, "new").recover()

    assert [run_id for run_id, _ in report.failed] == [orphan.id]
    await new.settle()
    stored = await new.runs.get(orphan.id)
    assert stored is not None
    assert stored.state is AgentRunState.HANDED_OVER
    (ended,) = await new.events(orphan.id, K.AGENT_RUN_ENDED)
    assert ended.payload["state"] == "HANDED_OVER"
    assert [ctx.run_id for ctx in new.hooks_fired(HookName.ON_TASK_FAILED)] == []
