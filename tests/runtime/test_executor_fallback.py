import subprocess
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_model_adapter import FakeModelAdapter, FakeScript, fake_descriptor
from tests.runtime.executor_env import (
    CLAUDE_MODEL,
    CODEX_MODEL,
    EnvFactory,
    ExecutorEnv,
    script,
)
from walk.agents import AgentInput, AgentInstance
from walk.budgets import BudgetDimension, BudgetHardAction, BudgetPolicy, BudgetScope
from walk.hooks import Hook, HookContext, HookName
from walk.model_router import FallbackTrigger, ModelAdapter, RunSession
from walk.model_router.models import AgentEvent
from walk.permissions import ApprovalRepository, Approver
from walk.runtime import AgentRun, AgentRunState, CheckpointKind, HandoverRepository
from walk.telemetry import DefaultTelemetryManager, LedgerEventKind, LedgerRepository
from walk.workflow import WorkItemState

K = LedgerEventKind
OUTAGE = FallbackTrigger.PROVIDER_OUTAGE


def _outage(**fields: object) -> FakeScript:
    return script(tool_calls=12, fail_after_tool_calls=3, fail_trigger=OUTAGE, **fields)


class InputRecorder(FakeModelAdapter):
    """Keeps the `AgentInput` of every run it starts."""

    inputs: list[AgentInput]

    def run(self, input: AgentInput, session: RunSession) -> AsyncIterator[AgentEvent]:  # noqa: A002 - parameter name fixed by INTERFACES §2.1
        self.inputs.append(input)
        return super().run(input, session)


def _adapters(
    clock: FakeClock, codex_plan: FakeScript, claude_plan: FakeScript
) -> tuple[dict[str, ModelAdapter], InputRecorder]:
    claude = InputRecorder(
        "fake-claude", [fake_descriptor(CLAUDE_MODEL, "fake-claude")], claude_plan, clock
    )
    claude.inputs = []
    codex = FakeModelAdapter(
        "fake-codex", [fake_descriptor(CODEX_MODEL, "fake-codex")], codex_plan, clock
    )
    return {"fake-codex": codex, "fake-claude": claude}, claude


async def _chain(env: ExecutorEnv) -> list[AgentRun]:
    return await env.runs.for_item(env.story.id)


def _git(repo: str, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def _is_file(path: Path) -> bool:
    return path.is_file()


async def test_provider_outage_falls_back_with_handover(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapters, _ = _adapters(fake_clock, _outage(), script(tool_calls=5))
    env = await make_executor_env(adapters=adapters)

    first = await env.run_to_end()

    old, new = await _chain(env)
    assert old.id == first.id
    assert old.state is AgentRunState.HANDED_OVER
    assert old.handover_out_id == "HO-0001"
    assert [c.kind for c in env.checkpoints_of(old.id)] == [
        CheckpointKind.START,
        CheckpointKind.HANDOFF,
    ]
    handoff = env.checkpoints_of(old.id)[-1]
    assert handoff.handover_id == "HO-0001"
    assert _is_file(env.db.path.parent / "handovers" / "HO-0001.md")
    fallback = (await env.events(old.id, K.MODEL_FALLBACK))[0]
    assert fallback.payload["from"] == CODEX_MODEL
    assert fallback.payload["to"] == CLAUDE_MODEL
    assert fallback.payload["handover_id"] == "HO-0001"
    assert fallback.payload["checkpoint_id"] == handoff.id
    assert new.state is AgentRunState.COMPLETED
    assert new.parent_run_id == old.id
    assert new.handover_in_id == "HO-0001"
    assert new.fallbacks == 1
    assert new.model_id == CLAUDE_MODEL
    assert new.provider == "fake-claude"
    handover = await HandoverRepository(env.db).get("HO-0001")
    assert handover is not None
    assert handover.to_run_id == new.id
    assert handover.reason == "FALLBACK"
    ended = (await env.events(old.id, K.AGENT_RUN_ENDED))[0]
    assert ended.payload["state"] == "HANDED_OVER"
    assert ended.payload["trigger"] == "PROVIDER_OUTAGE"
    selected = (await env.events(new.id, K.MODEL_SELECTED))[0]
    assert selected.payload["is_fallback"] is True
    assert selected.payload["trigger"] == "PROVIDER_OUTAGE"
    item = await env.items.get(env.story.id)
    assert item is not None
    assert item.state is WorkItemState.READY_FOR_REVIEW
    kinds = [e.kind for e in await env.ledger.query(work_item_id=env.story.id)]
    order = [K.CHECKPOINT_CREATED, K.MODEL_FALLBACK, K.AGENT_RUN_ENDED, K.AGENT_RUN_STARTED]
    positions = [kinds.index(kind, kinds.index(K.HANDOVER_CREATED)) for kind in order]
    assert positions == sorted(positions)


async def test_fallback_run_adopts_worktree(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapters, claude = _adapters(fake_clock, _outage(), script(tool_calls=5))
    env = await make_executor_env(adapters=adapters)

    await env.run_to_end()

    old, new = await _chain(env)
    assert new.worktree_path == old.worktree_path
    assert new.branch == old.branch
    assert new.branch is not None
    # The completed run released the worktree (E01-B01); its commits stay on the branch.
    tree = _git(str(env.repo), "ls-tree", "-r", "--name-only", new.branch).splitlines()
    for n in (1, 2, 3):
        assert f"src/Fake{n}.cs" in tree
    log = _git(str(env.repo), "log", "--format=%s", new.branch)
    assert "wip(STORY-0001): checkpoint 2" in log
    assert claude.inputs[0].worktree_path == old.worktree_path


async def test_fallback_preserves_role_and_passes_handover(
    make_executor_env: EnvFactory, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapters, claude = _adapters(fake_clock, _outage(), script(tool_calls=5))
    env = await make_executor_env(adapters=adapters)
    started: list[AgentInstance] = []
    original = env.executor._start  # noqa: SLF001 - observe the instance each run starts with

    async def spy(agent: AgentInstance, *args: Any, **kwargs: Any) -> AgentRun:
        started.append(agent)
        return await original(agent, *args, **kwargs)

    monkeypatch.setattr(env.executor, "_start", spy)

    await env.run_to_end()

    handover = claude.inputs[0].handover
    assert handover is not None
    assert handover.next_action
    assert handover.reason == "FALLBACK"
    assert handover.modified_files == ["src/Fake1.cs", "src/Fake2.cs", "src/Fake3.cs"]
    first, second = started
    assert first.model_dump(exclude={"model_id", "effort"}) == second.model_dump(
        exclude={"model_id", "effort"}
    )
    assert (first.model_id, second.model_id) == (CODEX_MODEL, CLAUDE_MODEL)
    assert claude.inputs[0].role is first.role


async def test_exhausted_fallbacks_block_provider_and_escalate(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapters, _ = _adapters(fake_clock, _outage(), _outage())
    env = await make_executor_env(adapters=adapters)

    await env.run_to_end()

    chain = await _chain(env)
    assert [r.state for r in chain] == [
        AgentRunState.HANDED_OVER,
        AgentRunState.HANDED_OVER,
        AgentRunState.BLOCKED_PROVIDER,
    ]
    assert [r.model_id for r in chain] == [CODEX_MODEL, CLAUDE_MODEL, CODEX_MODEL]
    assert [r.fallbacks for r in chain] == [0, 1, 2]
    blocked = chain[-1]
    assert str(blocked.failure_reason).startswith("blocked_provider: ")
    error = (await env.events(blocked.id, K.ERROR))[0]
    assert error.payload["kind"] == "BLOCKED_PROVIDER"
    assert error.payload["rejected"] == [[CODEX_MODEL, "max_fallbacks"]]
    approvals = await ApprovalRepository(env.db).list_where()
    assert [(a.kind, a.approver, a.run_id) for a in approvals] == [
        ("ESCALATION", Approver.USER, blocked.id)
    ]
    failed = env.hooks_fired(HookName.ON_TASK_FAILED)
    assert [ctx.run_id for ctx in failed] == [blocked.id]
    assert env.checkpoints_of(blocked.id)[-1].kind is CheckpointKind.HANDOFF
    item = await env.items.get(env.story.id)
    assert item is not None
    assert item.assigned_run_id is None


async def test_untriggered_error_does_not_fall_back(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapters, _ = _adapters(
        fake_clock, script(tool_calls=5, fail_after_tool_calls=2), script(tool_calls=2)
    )
    env = await make_executor_env(adapters=adapters)

    run = await env.run_to_end()

    assert run.state is AgentRunState.FAILED
    assert run.failure_reason == "error: none: scripted failure"
    assert await env.events(run.id, K.MODEL_FALLBACK) == []
    assert len(await _chain(env)) == 1


async def test_budget_fallback_action_falls_back(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapters, _ = _adapters(fake_clock, script(tool_calls=4), script(tool_calls=1))
    env = await make_executor_env(adapters=adapters)
    policy = BudgetPolicy(
        per_task={BudgetDimension.TOOL_CALLS: 2}, hard_action=BudgetHardAction.FALLBACK_MODEL
    )
    await env.budgets.ensure(BudgetScope.TASK, env.story.id, policy, None)

    run = await env.run_to_end()

    assert run.state is AgentRunState.HANDED_OVER
    fallback = (await env.events(run.id, K.MODEL_FALLBACK))[0]
    assert fallback.payload["trigger"] == "BUDGET_RESTRICTION"


async def test_boundary_violation_stops_fallback(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapters, _ = _adapters(fake_clock, _outage(), script(tool_calls=5))
    env = await make_executor_env(adapters=adapters)

    async def write_forbidden(ctx: HookContext) -> None:
        run = await env.runs.get(str(ctx.run_id))
        assert run is not None
        assert run.worktree_path is not None
        target = Path(run.worktree_path) / ".ai" / "agents" / "roles" / "qc.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"# rogue\n")

    env.hooks.register(
        Hook(name=HookName.ON_TOOL_AFTER, id="test.rogue", kind="builtin"), write_forbidden
    )

    run = await env.run_to_end()

    assert run.state is AgentRunState.FAILED_BOUNDARY
    assert await env.events(run.id, K.MODEL_FALLBACK) == []
    assert len(await _chain(env)) == 1


async def test_verify_only_continuation_submits_for_review(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapters, _ = _adapters(fake_clock, _outage(), script(tool_calls=0))
    env = await make_executor_env(adapters=adapters)

    await env.run_to_end()

    old, new = await _chain(env)
    assert new.state is AgentRunState.COMPLETED, new.failure_reason
    assert new.tool_calls == 0
    (ended,) = await env.events(new.id, K.AGENT_RUN_ENDED)
    handoff = env.checkpoints_of(old.id)[-1]
    assert handoff.kind is CheckpointKind.HANDOFF
    assert ended.payload["effects"]["commit_sha"] == handoff.head_sha
    assert ended.payload["effects"]["workflow_event"] == "submit_for_review"
    item = await env.items.get(env.story.id)
    assert item is not None
    assert item.state is WorkItemState.READY_FOR_REVIEW


async def test_continuation_final_audit_covers_parent_commits(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapters, _ = _adapters(fake_clock, _outage(), script(tool_calls=5))
    env = await make_executor_env(adapters=adapters)
    forbidden = ".ai/agents/roles/qc.md"
    calls: list[str] = []

    async def commit_forbidden(ctx: HookContext) -> None:
        calls.append(str(ctx.run_id))
        if len(calls) != 2:  # the parent's second tool call
            return
        run = await env.runs.get(str(ctx.run_id))
        assert run is not None
        assert run.worktree_path is not None
        target = Path(run.worktree_path) / forbidden
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"# rogue\n")
        # An unaudited WIP checkpoint (as recovery's HANDOFF or a START over residue) commits it.
        await env.checkpoints.checkpoint(
            run, CheckpointKind.PERIODIC, workflow_state=WorkItemState.IMPLEMENTING
        )

    env.hooks.register(
        Hook(name=HookName.ON_TOOL_AFTER, id="test.rogue", kind="builtin"), commit_forbidden
    )

    await env.run_to_end()

    old, new = await _chain(env)
    assert old.state is AgentRunState.HANDED_OVER
    assert new.parent_run_id == old.id
    assert new.state is AgentRunState.FAILED_BOUNDARY
    assert new.failure_reason == f"boundary: {forbidden}"
    error = (await env.events(new.id, K.ERROR))[0]
    assert error.payload == {"kind": "BOUNDARY", "violations": [forbidden]}


async def test_run_ended_payload_carries_handover_in_id(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapters, _ = _adapters(fake_clock, _outage(), script(tool_calls=5))
    env = await make_executor_env(adapters=adapters)

    await env.run_to_end()

    run_a, run_b = await _chain(env)
    (ended_a,) = await env.events(run_a.id, K.AGENT_RUN_ENDED)
    (ended_b,) = await env.events(run_b.id, K.AGENT_RUN_ENDED)
    assert ended_a.payload["handover_in_id"] is None
    assert ended_b.payload["handover_in_id"] == "HO-0001"
    assert ended_b.outcome == "OK"


async def test_failed_continuations_count_as_failed_handoffs(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapters, _ = _adapters(fake_clock, _outage(), _outage())
    env = await make_executor_env(adapters=adapters)

    await env.run_to_end()

    chain = await _chain(env)
    assert [r.handover_in_id for r in chain] == [None, "HO-0001", "HO-0002"]
    assert chain[-1].state is AgentRunState.BLOCKED_PROVIDER
    telemetry = DefaultTelemetryManager(env.repo, LedgerRepository(env.db), fake_clock)
    try:
        metrics = await telemetry.metrics()
    finally:
        telemetry.close()
    assert metrics.failed_handoffs == 2
    assert metrics.fallbacks == 2
