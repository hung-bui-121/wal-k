import asyncio
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_model_adapter import FakeModelAdapter, fake_descriptor
from tests.runtime.executor_env import (
    CODEX_MODEL,
    EnvFactory,
    ExecutorEnv,
    completed_output,
    script,
)
from walk.agents import AgentInput, AgentOutputStatus
from walk.budgets import BudgetDimension, BudgetScope
from walk.common.enums import Effort
from walk.common.errors import ConfigError
from walk.decisions import AutonomyLevel, DecisionCategory, EscalationRequest
from walk.effort import EffortResolution
from walk.hooks import Hook, HookContext, HookFailPolicy, HookName
from walk.model_router import (
    AgentEvent,
    AgentEventKind,
    FallbackTrigger,
    RoutingDecision,
    RunSession,
)
from walk.persistence import UnitOfWork
from walk.runtime import AgentRun, AgentRunState, CheckpointKind, RunNotFound
from walk.telemetry import LedgerEventKind
from walk.workflow import WorkItemState

K = LedgerEventKind
EXECUTOR_KINDS = {
    K.AGENT_ASSIGNED,
    K.AGENT_RUN_STARTED,
    K.MODEL_SELECTED,
    K.EFFORT_SET,
    K.CHECKPOINT_CREATED,
    K.AGENT_RUN_ENDED,
    K.ERROR,
    K.RETRY,
}
TEXT_MARKER = "visible assistant musing 7f3a"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def _escalation() -> EscalationRequest:
    return EscalationRequest(
        to_level=AutonomyLevel.LOCAL, category=DecisionCategory.TECH, question="which?"
    )


def _is_dir(path: str) -> bool:
    return Path(path).is_dir()


async def _story_state(env: ExecutorEnv) -> WorkItemState:
    item = await env.items.get(env.story.id)
    assert item is not None
    return item.state


async def _assigned(env: ExecutorEnv) -> str | None:
    item = await env.items.get(env.story.id)
    assert item is not None
    return item.assigned_run_id


async def test_start_runs_to_completion_with_ledger_sequence(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script(tool_calls=3))

    started = await env.executor.start(env.agent, env.story, "IMPLEMENT")
    run = await env.executor.wait(started.id)

    assert started.state is AgentRunState.RUNNING
    assert run.state is AgentRunState.COMPLETED
    executor_kinds = [kind for kind in await env.kinds(run.id) if kind in EXECUTOR_KINDS]
    assert executor_kinds[:5] == [
        K.AGENT_ASSIGNED,
        K.AGENT_RUN_STARTED,
        K.MODEL_SELECTED,
        K.EFFORT_SET,
        K.CHECKPOINT_CREATED,
    ]
    assert executor_kinds[-1] is K.AGENT_RUN_ENDED
    first_checkpoint = (await env.events(run.id, K.CHECKPOINT_CREATED))[0]
    assert first_checkpoint.payload["kind"] == "START"
    assert len(env.hooks_fired(HookName.ON_AGENT_START)) == 1
    assert len(env.hooks_fired(HookName.ON_AGENT_END)) == 1
    assert env.hooks_fired(HookName.ON_TASK_FAILED) == []
    assert await _story_state(env) is WorkItemState.READY_FOR_REVIEW
    assert await _assigned(env) is None
    ended = (await env.events(run.id, K.AGENT_RUN_ENDED))[0]
    assert ended.outcome == "OK"
    assert ended.payload["effects"]["workflow_event"] == "submit_for_review"
    assert ended.payload["deferred_intents"] == {"new_tasks": 0, "new_bugs": 0}
    assert ended.cost_usd is not None
    assert ended.cost_usd > 0
    assert env.executor.running() == []


async def test_start_events_carry_identity_and_versions(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script(tool_calls=0), prompt_version=lambda p: f"{p}-1.0")

    run = await env.run_to_end()

    started = (await env.events(run.id, K.AGENT_RUN_STARTED))[0]
    selected = (await env.events(run.id, K.MODEL_SELECTED))[0]
    effort = (await env.events(run.id, K.EFFORT_SET))[0]
    for event in (started, selected, effort):
        assert event.run_id == run.id
        assert event.work_item_id == env.story.id
        assert event.actor_role is env.agent.role
        assert event.model_id == CODEX_MODEL
        assert event.effort is env.agent.effort
        assert event.behavior_versions == {"prompt:IMPLEMENT": "IMPLEMENT-1.0"}
    assert started.payload["purpose"] == "IMPLEMENT"
    assert started.payload["branch"] == run.branch
    assert started.payload["context_item_ids"][0] == "WORK_ITEM:STORY-0001"
    assert selected.payload == {"reason": "direct"}
    assert effort.payload == {"effort": "MEDIUM", "degraded_from": None}
    assert run.provider_session is not None
    assert run.provider_session.session_id == f"fake-{run.id}"


async def test_start_rejects_second_active_run(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script(tool_calls=12), checkpoint_every=5)
    first = await env.executor.start(env.agent, env.story, "IMPLEMENT")

    with pytest.raises(ConfigError, match="already has active run"):
        await env.executor.start(env.agent, env.story, "IMPLEMENT")

    count = env.db.connect().execute("SELECT COUNT(*) FROM agent_runs").fetchone()[0]
    assert count == 1
    await env.executor.wait(first.id)


async def test_start_rejects_unknown_purpose_and_item(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env()

    with pytest.raises(ConfigError, match="unknown template purpose"):
        await env.executor.start(env.agent, env.story, "DANCE")
    with pytest.raises(Exception, match="work item not found"):
        await env.executor.start(
            env.agent, env.story.model_copy(update={"id": "STORY-0099"}), "IMPLEMENT"
        )
    assert env.db.connect().execute("SELECT COUNT(*) FROM agent_runs").fetchone()[0] == 0


async def test_periodic_checkpoints_every_n_tool_calls(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script(tool_calls=12), checkpoint_every=5)

    run = await env.run_to_end()

    checkpoints = env.checkpoints_of(run.id)
    assert [c.kind for c in checkpoints] == [
        CheckpointKind.START,
        CheckpointKind.PERIODIC,
        CheckpointKind.PERIODIC,
        CheckpointKind.END,
    ]
    assert [c.seq for c in checkpoints] == [1, 2, 3, 4]
    assert [c.tool_calls_so_far for c in checkpoints] == [0, 5, 10, 12]
    assert checkpoints[0].wip_commit_sha is None
    assert all(c.wip_commit_sha is not None for c in checkpoints[1:])
    log = _git(env.repo, "log", "--format=%s", str(run.branch)).splitlines()
    assert log[:3] == [
        "wip(STORY-0001): checkpoint 4",
        "wip(STORY-0001): checkpoint 3",
        "wip(STORY-0001): checkpoint 2",
    ]
    assert checkpoints[1].budget_consumed[BudgetDimension.TOOL_CALLS] == 5.0
    assert run.state is AgentRunState.COMPLETED


async def test_checkpoint_hint_creates_agent_requested_checkpoint(
    make_executor_env: EnvFactory,
) -> None:
    env = await make_executor_env(script(tool_calls=3, checkpoint_hint_at=[2]))

    run = await env.run_to_end()

    checkpoints = env.checkpoints_of(run.id)
    assert [c.kind for c in checkpoints] == [
        CheckpointKind.START,
        CheckpointKind.AGENT_REQUESTED,
        CheckpointKind.END,
    ]
    assert checkpoints[1].tool_calls_so_far == 2


async def test_tool_results_recorded_and_counted(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script(tool_calls=3))

    run = await env.run_to_end()

    invoked = await env.events(run.id, K.TOOL_INVOKED)
    post = [event for event in invoked if event.payload.get("phase") == "post"]
    assert len(post) == 3
    assert all(event.duration_ms == 0 for event in post)
    assert run.tool_calls == 3
    assert len(env.hooks_fired(HookName.ON_TOOL_AFTER)) == 3


class _TalkativeAdapter(FakeModelAdapter):
    """Fake that emits a TEXT event after STARTED and after every tool result."""

    texts_sent = 0

    def run(self, input: AgentInput, session: RunSession) -> AsyncIterator[AgentEvent]:  # noqa: A002 - parameter name fixed by INTERFACES §2.1
        return self._talk(super().run(input, session), session)

    async def _talk(
        self, inner: AsyncIterator[AgentEvent], session: RunSession
    ) -> AsyncIterator[AgentEvent]:
        async for event in inner:
            yield event
            if event.kind in {AgentEventKind.STARTED, AgentEventKind.TOOL_CALL_RESULT}:
                self.texts_sent += 1
                yield AgentEvent(
                    kind=AgentEventKind.TEXT,
                    run_id=session.run_id,
                    at=event.at,
                    text=TEXT_MARKER,
                )


async def test_text_events_never_persisted(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapter = _TalkativeAdapter(
        "fake-codex", [fake_descriptor(CODEX_MODEL, "fake-codex")], script(), fake_clock
    )
    env = await make_executor_env(adapters={"fake-codex": adapter}, checkpoint_every=2)

    run = await env.run_to_end()

    assert run.state is AgentRunState.COMPLETED
    assert adapter.texts_sent == 4
    conn = env.db.connect()
    for table in ("ledger_events", "checkpoints", "agent_runs"):
        rows = conn.execute(f"SELECT json FROM {table}").fetchall()  # noqa: S608 - fixed names
        assert rows
        assert all(TEXT_MARKER not in str(row[0]) for row in rows)


async def test_error_event_fails_run_until_fallback_lands(make_executor_env: EnvFactory) -> None:
    # E01-S28 landed the fallback: a triggered ERROR hands the run over instead of failing it.
    plan = script(
        tool_calls=12, fail_after_tool_calls=3, fail_trigger=FallbackTrigger.PROVIDER_OUTAGE
    )
    env = await make_executor_env(plan)

    run = await env.run_to_end()

    assert run.state is AgentRunState.HANDED_OVER
    assert run.failure_reason == "fallback: PROVIDER_OUTAGE: scripted failure"
    assert await env.events(run.id, K.ERROR) == []
    fallback = (await env.events(run.id, K.MODEL_FALLBACK))[0]
    assert fallback.payload["trigger"] == "PROVIDER_OUTAGE"
    assert [c for c in env.hooks_fired(HookName.ON_TASK_FAILED) if c.run_id == run.id] == []
    ended = (await env.events(run.id, K.AGENT_RUN_ENDED))[0]
    assert ended.outcome == "FAILED"
    assert ended.payload["state"] == "HANDED_OVER"


class _SilentAdapter(FakeModelAdapter):
    """Fake whose stream ends without FINAL_OUTPUT."""

    def run(self, input: AgentInput, session: RunSession) -> AsyncIterator[AgentEvent]:  # noqa: A002 - parameter name fixed by INTERFACES §2.1
        return self._silent(super().run(input, session))

    async def _silent(self, inner: AsyncIterator[AgentEvent]) -> AsyncIterator[AgentEvent]:
        async for event in inner:
            if event.kind is not AgentEventKind.FINAL_OUTPUT:
                yield event


async def test_stream_without_final_output_fails_run(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapter = _SilentAdapter(
        "fake-codex", [fake_descriptor(CODEX_MODEL, "fake-codex")], script(), fake_clock
    )
    env = await make_executor_env(adapters={"fake-codex": adapter})

    run = await env.run_to_end()

    assert run.state is AgentRunState.FAILED
    assert run.failure_reason == "error: none: adapter stream ended without a final output"


async def test_budget_exhausted_blocks_run(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script(tool_calls=6))
    await env.budgets.ensure(BudgetScope.TASK, env.story.id, None, {BudgetDimension.TOOL_CALLS: 2})

    run = await env.run_to_end()

    assert run.state is AgentRunState.BLOCKED_BUDGET
    assert run.tool_calls == 2
    assert [c.kind for c in env.checkpoints_of(run.id)] == [
        CheckpointKind.START,
        CheckpointKind.PAUSE,
    ]
    error = (await env.events(run.id, K.ERROR))[0]
    assert error.payload["kind"] == "BUDGET"
    assert await _story_state(env) is WorkItemState.IMPLEMENTING
    assert await env.ledger.query(kinds=[K.WORK_ITEM_TRANSITION]) == []
    assert await _assigned(env) is None


async def test_cost_budget_exhausted_after_metering_blocks_run(
    make_executor_env: EnvFactory,
) -> None:
    env = await make_executor_env(script(tool_calls=6))
    await env.budgets.ensure(
        BudgetScope.TASK, env.story.id, None, {BudgetDimension.COST_USD: 0.001}
    )

    run = await env.run_to_end()

    assert run.state is AgentRunState.BLOCKED_BUDGET
    assert run.tool_calls == 1
    assert "COST_USD" in str(run.failure_reason)


async def _wait_for_tool_calls(env: ExecutorEnv, run_id: str, count: int) -> None:
    for _ in range(500):
        run = await env.runs.get(run_id)
        assert run is not None
        if run.tool_calls >= count:
            return
        await asyncio.sleep(0.01)
    msg = f"run {run_id} never reached {count} tool calls"
    raise AssertionError(msg)


async def test_cancel_and_pause(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script(tool_calls=12), checkpoint_every=5)

    first = await env.executor.start(env.agent, env.story, "IMPLEMENT")
    await _wait_for_tool_calls(env, first.id, 2)
    cancelled = await env.executor.cancel(first.id, "user")

    assert cancelled.state is AgentRunState.CANCELLED
    assert cancelled.failure_reason == "user"
    assert cancelled.tool_calls < 12
    assert env.checkpoints_of(first.id)[-1].kind is CheckpointKind.PAUSE
    assert first.worktree_path is not None
    assert not _is_dir(first.worktree_path)
    assert _git(env.repo, "branch", "--list", str(first.branch))
    ended = (await env.events(first.id, K.AGENT_RUN_ENDED))[0]
    assert ended.outcome == "SKIPPED"
    assert await _assigned(env) is None

    second = await env.executor.start(env.agent, env.story, "IMPLEMENT")
    await _wait_for_tool_calls(env, second.id, 2)
    paused = await env.executor.pause(second.id)

    assert paused.state is AgentRunState.PAUSED_BY_USER
    assert paused.ended_at is None
    assert env.checkpoints_of(second.id)[-1].kind is CheckpointKind.PAUSE
    assert second.worktree_path is not None
    assert _is_dir(second.worktree_path)
    assert await _assigned(env) == second.id
    assert await env.events(second.id, K.AGENT_RUN_ENDED) == []
    assert env.executor.running() == []


async def test_cancel_unknown_or_inactive_run(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script(tool_calls=0))
    run = await env.run_to_end()

    with pytest.raises(RunNotFound):
        await env.executor.cancel("RUN-01J0000000000000000000ZZZZ", "user")
    with pytest.raises(ConfigError, match="not executing"):
        await env.executor.pause(run.id)
    with pytest.raises(RunNotFound):
        await env.executor.wait("RUN-01J0000000000000000000ZZZZ")


async def test_failing_start_hook_fails_run_before_adapter_call(
    make_executor_env: EnvFactory,
) -> None:
    env = await make_executor_env(script())

    async def refuse(ctx: HookContext) -> None:
        del ctx
        msg = "start refused"
        raise RuntimeError(msg)

    hook = Hook(
        name=HookName.ON_AGENT_START,
        id="test.refuse",
        kind="builtin",
        priority=10,
        fail_policy=HookFailPolicy.FAIL_CLOSED,
        required=True,
    )
    env.hooks.register(hook, refuse)

    run = await env.executor.start(env.agent, env.story, "IMPLEMENT")

    assert run.state is AgentRunState.FAILED_HOOK
    adapter = env.adapters["fake-codex"]
    assert isinstance(adapter, FakeModelAdapter)
    assert adapter.runs == {}
    assert await _assigned(env) is None
    assert env.executor.running() == []


async def test_preparation_failure_fails_run_and_keeps_worktree(
    make_executor_env: EnvFactory,
) -> None:
    env = await make_executor_env(script())
    broken = env.agent.model_copy(update={"tools": ["no-such-tool"]})

    run = await env.executor.start(broken, env.story, "IMPLEMENT")

    assert run.state is AgentRunState.FAILED
    assert str(run.failure_reason).startswith("prepare: ")
    assert run.worktree_path is not None
    assert _is_dir(run.worktree_path)
    error = (await env.events(run.id, K.ERROR))[0]
    assert error.payload["kind"] == "PREPARE"
    assert await env.events(run.id, K.AGENT_RUN_STARTED) == []
    assert await _assigned(env) is None
    assert await env.executor.wait(run.id) == run


async def test_on_run_finished_called_once_per_run(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script(tool_calls=1))
    finished: list[str] = []

    async def note(run: object) -> None:
        finished.append(getattr(run, "id", ""))

    env.executor.on_run_finished = note

    run = await env.run_to_end()

    assert finished == [run.id]


async def test_start_allowed_when_assigned_run_is_terminal(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script(tool_calls=1, output=completed_output()))
    first = await env.run_to_end()
    await env.sandbox.remove(first, keep_branch=True)
    async with UnitOfWork(env.db) as uow:
        await env.items.set_assigned_run(env.story.id, first.id, conn=uow.conn)

    restarted = await env.executor.start(env.agent, env.story, "REVIEW")

    assert restarted.id != first.id
    assert restarted.state is AgentRunState.RUNNING
    await env.executor.wait(restarted.id)


async def test_start_records_routing_and_effort_resolution(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script(tool_calls=0))
    routing = RoutingDecision(
        model_id=CODEX_MODEL,
        provider="fake-codex",
        effort=Effort.MEDIUM,
        reason="fallback",
        rejected=[("fake-claude/sim", "health")],
        is_fallback=True,
        trigger=FallbackTrigger.PROVIDER_OUTAGE,
    )
    resolution = EffortResolution(
        role_default=Effort.MEDIUM,
        complexity_component=Effort.MEDIUM,
        risk_bump=0,
        stage_bump=0,
        escalation_bump=0,
        effective=Effort.MEDIUM,
        clamped_by_policy=False,
        clamped_by_budget=False,
    )

    started = await env.executor.start(
        env.agent, env.story, "IMPLEMENT", routing=routing, effort_resolution=resolution
    )
    run = await env.executor.wait(started.id)

    selected = (await env.events(run.id, K.MODEL_SELECTED))[0]
    effort = (await env.events(run.id, K.EFFORT_SET))[0]
    assert selected.payload == {
        "reason": "fallback",
        "rejected": [["fake-claude/sim", "health"]],
        "is_fallback": True,
        "trigger": "PROVIDER_OUTAGE",
    }
    assert effort.payload["effective"] == "MEDIUM"
    assert effort.payload["clamped_by_budget"] is False
    assert effort.payload["effort"] == "MEDIUM"


async def test_partial_output_kept_and_run_completes(make_executor_env: EnvFactory) -> None:
    blocked = completed_output(status=AgentOutputStatus.BLOCKED, escalations=[_escalation()])
    env = await make_executor_env(script(tool_calls=2, partial_output=blocked))

    run = await env.run_to_end()

    assert run.state is AgentRunState.COMPLETED


async def test_start_checkpoint_failure_fails_run(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script())

    async def refuse(ctx: HookContext) -> None:
        del ctx
        msg = "checkpoint storage offline"
        raise RuntimeError(msg)

    env.hooks.register(
        Hook(
            name=HookName.ON_AGENT_CHECKPOINT,
            id="test.refuse_checkpoint",
            kind="builtin",
            fail_policy=HookFailPolicy.FAIL_CLOSED,
        ),
        refuse,
    )

    run = await env.executor.start(env.agent, env.story, "IMPLEMENT")

    assert run.state is AgentRunState.FAILED
    assert str(run.failure_reason).startswith("error: none: ")
    assert env.executor.running() == []
    assert await _assigned(env) is None


class _AnonymousResultAdapter(FakeModelAdapter):
    """Drops TOOL_CALL_REQUESTED, so a result cannot be paired with its request."""

    def run(self, input: AgentInput, session: RunSession) -> AsyncIterator[AgentEvent]:  # noqa: A002 - parameter name fixed by INTERFACES §2.1
        return self._drop(super().run(input, session))

    async def _drop(self, inner: AsyncIterator[AgentEvent]) -> AsyncIterator[AgentEvent]:
        async for event in inner:
            if event.kind is not AgentEventKind.TOOL_CALL_REQUESTED:
                yield event


async def test_tool_result_without_request_fails_run(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapter = _AnonymousResultAdapter(
        "fake-codex", [fake_descriptor(CODEX_MODEL, "fake-codex")], script(), fake_clock
    )
    env = await make_executor_env(adapters={"fake-codex": adapter})

    run = await env.run_to_end()

    assert run.state is AgentRunState.FAILED
    assert run.failure_reason == "error: none: tool call result without a tool call request"


class _NamelessCrashAdapter(FakeModelAdapter):
    """Stream raising an exception without a message."""

    def run(self, input: AgentInput, session: RunSession) -> AsyncIterator[AgentEvent]:  # noqa: A002 - parameter name fixed by INTERFACES §2.1
        return self._crash(super().run(input, session))

    async def _crash(self, inner: AsyncIterator[AgentEvent]) -> AsyncIterator[AgentEvent]:
        async for event in inner:
            yield event
            raise RuntimeError


async def test_unexpected_exception_without_message_fails_run(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapter = _NamelessCrashAdapter(
        "fake-codex", [fake_descriptor(CODEX_MODEL, "fake-codex")], script(), fake_clock
    )
    env = await make_executor_env(adapters={"fake-codex": adapter})

    run = await env.run_to_end()

    assert run.state is AgentRunState.FAILED
    assert run.failure_reason == "error: none: RuntimeError"


async def test_end_hook_and_callback_failures_keep_completed_run(
    make_executor_env: EnvFactory,
) -> None:
    env = await make_executor_env(script(tool_calls=1))

    async def refuse(ctx: HookContext) -> None:
        del ctx
        msg = "end hook down"
        raise RuntimeError(msg)

    async def broken_callback(run: AgentRun) -> None:
        del run
        msg = "scheduler gone"
        raise RuntimeError(msg)

    env.hooks.register(
        Hook(
            name=HookName.ON_AGENT_END,
            id="test.refuse_end",
            kind="builtin",
            fail_policy=HookFailPolicy.FAIL_CLOSED,
        ),
        refuse,
    )
    env.executor.on_run_finished = broken_callback

    run = await env.run_to_end()

    assert run.state is AgentRunState.COMPLETED
    assert len(await env.events(run.id, K.HOOK_FAILED)) == 1


async def test_stop_requests_during_finalization_return_the_ended_run(
    make_executor_env: EnvFactory,
) -> None:
    env = await make_executor_env(script(tool_calls=1))
    late: list[asyncio.Task[AgentRun]] = []

    async def stop_late(ctx: HookContext) -> None:
        if ctx.payload["kind"] == "END" and ctx.run_id is not None:
            late.append(asyncio.create_task(env.executor.cancel(ctx.run_id, "late")))
            late.append(asyncio.create_task(env.executor.pause(ctx.run_id)))

    env.hooks.register(
        Hook(name=HookName.ON_AGENT_CHECKPOINT, id="test.stop_late", kind="builtin"), stop_late
    )

    run = await env.run_to_end()
    stopped = [await task for task in late]

    assert run.state is AgentRunState.COMPLETED
    assert [r.state for r in stopped] == [AgentRunState.COMPLETED, AgentRunState.COMPLETED]
    assert (await env.events(run.id, K.AGENT_RUN_ENDED))[0].outcome == "OK"


async def test_failure_after_the_run_ended_is_only_logged(
    make_executor_env: EnvFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = await make_executor_env(script(tool_calls=1))

    async def explode(*args: object) -> None:
        del args
        msg = "post-end failure"
        raise RuntimeError(msg)

    monkeypatch.setattr(env.executor, "_fire_safely", explode)

    run = await env.run_to_end()

    assert run.state is AgentRunState.COMPLETED
    assert len(await env.events(run.id, K.AGENT_RUN_ENDED)) == 1


async def test_unrecoverable_end_failure_leaves_run_for_recovery(
    make_executor_env: EnvFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = script(tool_calls=2, fail_after_tool_calls=1)
    env = await make_executor_env(plan)

    async def broken_end(*args: object) -> None:
        del args
        msg = "database unavailable"
        raise RuntimeError(msg)

    monkeypatch.setattr(env.executor, "_end", broken_end)

    run = await env.run_to_end()

    assert run.state is AgentRunState.RUNNING
    assert env.executor.running() == []


class _EndlessAdapter(FakeModelAdapter):
    """Fake whose stream simply stops instead of emitting ENDED."""

    def run(self, input: AgentInput, session: RunSession) -> AsyncIterator[AgentEvent]:  # noqa: A002 - parameter name fixed by INTERFACES §2.1
        return self._no_end(super().run(input, session))

    async def _no_end(self, inner: AsyncIterator[AgentEvent]) -> AsyncIterator[AgentEvent]:
        async for event in inner:
            if event.kind is not AgentEventKind.ENDED:
                yield event


async def test_stream_without_ended_event_completes(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapter = _EndlessAdapter(
        "fake-codex", [fake_descriptor(CODEX_MODEL, "fake-codex")], script(), fake_clock
    )
    env = await make_executor_env(adapters={"fake-codex": adapter})

    run = await env.run_to_end()

    assert run.state is AgentRunState.COMPLETED
