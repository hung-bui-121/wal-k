import asyncio
from datetime import timedelta

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_model_adapter import FakeModelAdapter
from tests.runtime.executor_env import EXECUTOR_RULES, EnvFactory, ExecutorEnv, script
from walk.common.errors import ConfigError, GuardRejected, PermanentError
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, Hook, HookContext, HookExecutionRepository, HookName
from walk.permissions import (
    ApprovalRepository,
    ApprovalRequest,
    ApprovalState,
    Approver,
    DefaultPermissionManager,
    PermissionEffect,
    PermissionRule,
    ToolCallRequest,
)
from walk.persistence import Database, IdSequenceStore
from walk.runtime import AgentRun, AgentRunState, CheckpointKind
from walk.telemetry import DefaultLedgerManager, LedgerEventKind, LedgerRepository
from walk.tools import ToolKind
from walk.workflow import Risk

RUN = "RUN-01J0000000000000000000000A"
REQUEST = ToolCallRequest(
    run_id=RUN,
    role=AgentRole.LEAD_DEV,
    tool="git.merge_protected",
    kind=ToolKind.KERNEL,
    arguments={"branch": "main"},
    worktree_path="wt",
)


@pytest.fixture
def ledger(db: Database, fake_clock: FakeClock) -> DefaultLedgerManager:
    return DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), fake_clock)


@pytest.fixture
def fired() -> list[HookContext]:
    return []


@pytest.fixture
def manager(
    db: Database, ledger: DefaultLedgerManager, fake_clock: FakeClock, fired: list[HookContext]
) -> DefaultPermissionManager:
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)

    async def record(ctx: HookContext) -> None:
        fired.append(ctx)

    hooks.register(
        Hook(name=HookName.ON_PROTECTED_ACTION_REQUESTED, id="test.approval", kind="builtin"),
        record,
    )
    return DefaultPermissionManager(
        [],
        [],
        ApprovalRepository(db),
        ledger,
        hooks,
        IdSequenceStore(db),
        fake_clock,
        project_key="DEMO",
    )


async def _request(manager: DefaultPermissionManager, approver: Approver = Approver.USER) -> str:
    approval = await manager.request_approval(
        REQUEST,
        kind="PROTECTED_ACTION",
        approver=approver,
        requested_by=AgentRole.LEAD_DEV,
        run_id=RUN,
        work_item_id="STORY-0001",
    )
    return approval.id


async def test_request_approval_persists_and_logs(
    manager: DefaultPermissionManager,
    ledger: DefaultLedgerManager,
    fired: list[HookContext],
    db: Database,
    fake_clock: FakeClock,
) -> None:
    approval = await manager.request_approval(
        REQUEST,
        kind="PROTECTED_ACTION",
        approver=Approver.USER,
        requested_by=AgentRole.LEAD_DEV,
        run_id=RUN,
        work_item_id="STORY-0001",
    )
    assert approval.id == "APV-0001"
    assert approval.state is ApprovalState.PENDING
    assert approval.requested_at == fake_clock.now()
    assert approval.payload["tool"] == "git.merge_protected"
    assert approval.payload["arguments"] == {"branch": "main"}
    stored = await ApprovalRepository(db).get("APV-0001")
    assert stored == approval
    row = db.connect().execute("SELECT state, approver, kind FROM approval_requests").fetchone()
    assert tuple(row) == ("PENDING", "USER", "PROTECTED_ACTION")
    events = await ledger.query(kinds=[LedgerEventKind.APPROVAL_REQUESTED])
    assert len(events) == 1
    assert events[0].payload == {
        "approval_id": "APV-0001",
        "kind": "PROTECTED_ACTION",
        "approver": "USER",
    }
    assert (events[0].run_id, events[0].work_item_id, events[0].actor_role) == (
        RUN,
        "STORY-0001",
        AgentRole.LEAD_DEV,
    )
    assert [ctx.name for ctx in fired] == [HookName.ON_PROTECTED_ACTION_REQUESTED]
    assert fired[0].payload == {**events[0].payload, "tool": "git.merge_protected"}
    assert fired[0].run_id == RUN
    assert approval.expires_at == fake_clock.now() + timedelta(seconds=86400)
    assert fired[0].role is AgentRole.LEAD_DEV


async def test_request_approval_accepts_models_and_dicts(manager: DefaultPermissionManager) -> None:
    escalation = await manager.request_approval(
        {"question": "ship?"},
        kind="ESCALATION",
        approver=Approver.PRODUCT_OWNER,
        requested_by=AgentRole.ORCHESTRATOR,
        run_id=None,
        work_item_id=None,
    )
    assert escalation.payload == {"question": "ship?"}
    with pytest.raises(ConfigError, match="approval kind"):
        await manager.request_approval(
            {"risk": Risk.LOW},
            kind="NOPE",
            approver=Approver.USER,
            requested_by=AgentRole.ORCHESTRATOR,
            run_id=None,
            work_item_id=None,
        )


async def test_decide_approval_updates_or_rejects(
    manager: DefaultPermissionManager, ledger: DefaultLedgerManager, fake_clock: FakeClock
) -> None:
    approval_id = await _request(manager)
    fake_clock.advance(60)
    decided = await manager.decide_approval(approval_id, approve=True, by="user", note="ok")
    assert decided.state is ApprovalState.APPROVED
    assert (decided.decided_at, decided.decided_by, decided.decision_note) == (
        fake_clock.now(),
        "user",
        "ok",
    )
    events = await ledger.query(kinds=[LedgerEventKind.APPROVAL_DECIDED])
    assert len(events) == 1
    assert events[0].payload == {
        "approval_id": approval_id,
        "kind": "PROTECTED_ACTION",
        "approver": "USER",
        "state": "APPROVED",
        "decided_by": "user",
    }
    assert events[0].actor_role is AgentRole.USER
    assert events[0].outcome == "OK"
    with pytest.raises(GuardRejected, match="approval already decided"):
        await manager.decide_approval(approval_id, approve=False, by="user", note=None)
    with pytest.raises(ConfigError, match="APV-9999"):
        await manager.decide_approval("APV-9999", approve=True, by="user", note=None)
    denied = await manager.decide_approval(
        await _request(manager), approve=False, by="lead", note=None
    )
    assert denied.state is ApprovalState.DENIED


async def test_pending_filters_by_approver(manager: DefaultPermissionManager) -> None:
    first = await _request(manager, Approver.USER)
    await _request(manager, Approver.LEAD_DEV)
    third = await _request(manager, Approver.USER)
    decided = await _request(manager, Approver.USER)
    await manager.decide_approval(decided, approve=False, by="user", note=None)
    assert [a.id for a in await manager.pending(Approver.USER)] == [first, third]
    assert len(await manager.pending()) == 3


async def test_decide_approval_can_expire(
    manager: DefaultPermissionManager, ledger: DefaultLedgerManager
) -> None:
    approval_id = await _request(manager)

    expired = await manager.decide_approval(
        approval_id, approve=False, by="kernel", note="timeout", expired=True
    )

    assert expired.state is ApprovalState.EXPIRED
    assert expired.decision_note == "timeout"
    events = await ledger.query(kinds=[LedgerEventKind.APPROVAL_DECIDED])
    assert events[0].payload["state"] == "EXPIRED"
    assert events[0].payload["reason"] == "expired"
    assert events[0].outcome == "DENIED"
    with pytest.raises(ConfigError, match="cannot approve and expire"):
        await manager.decide_approval(
            await _request(manager), approve=True, by="kernel", note=None, expired=True
        )


# ---- lifecycle inside a real run (E02-S11) --------------------------------------------------

MERGE = "git.merge_protected"
GUARD_S = 5
POLL_S = 0.01
APPROVAL_RULES = [
    *EXECUTOR_RULES,
    PermissionRule(
        role=AgentRole.SENIOR_DEV,
        tool=MERGE,
        effect=PermissionEffect.REQUIRE_APPROVAL,
        approver=Approver.USER,
    ),
]


async def _short_sleep(seconds: float) -> None:
    del seconds
    await asyncio.sleep(POLL_S)


async def _paused_env(make_executor_env: EnvFactory) -> tuple[ExecutorEnv, AgentRun]:
    """A run whose first tool call (``git.merge_protected``) waits for approval."""
    env = await make_executor_env(
        script(tool_calls=1, tool_name=MERGE),
        rules=APPROVAL_RULES,
        approval_sleep=_short_sleep,
        event_waiter=True,
    )
    run = await env.executor.start(env.agent, env.story, "IMPLEMENT")
    await asyncio.wait_for(_until_paused(env, run.id), GUARD_S)
    return env, run


async def _until_paused(env: ExecutorEnv, run_id: str) -> None:
    while True:
        run = await env.runs.get(run_id)
        paused = run is not None and run.state is AgentRunState.PAUSED_FOR_APPROVAL
        if paused and any(c.kind is CheckpointKind.PAUSE for c in env.checkpoints_of(run_id)):
            return
        await asyncio.sleep(POLL_S)


async def test_require_approval_pauses_run_and_persists_request(
    make_executor_env: EnvFactory,
) -> None:
    env, run = await _paused_env(make_executor_env)
    try:
        pending = await env.permissions.pending()
        assert [(a.id, a.kind, a.state) for a in pending] == [
            ("APV-0001", "PROTECTED_ACTION", ApprovalState.PENDING)
        ]
        assert pending[0].payload["tool"] == MERGE
        assert pending[0].run_id == run.id
        assert [c.kind for c in env.checkpoints_of(run.id)] == [
            CheckpointKind.START,
            CheckpointKind.PAUSE,
        ]
        requested = await env.events(run.id, LedgerEventKind.APPROVAL_REQUESTED)
        assert [e.payload["approval_id"] for e in requested] == ["APV-0001"]
    finally:
        await env.permissions.decide_approval("APV-0001", approve=True, by="user", note=None)
        await asyncio.wait_for(env.executor.wait(run.id), GUARD_S)


async def test_approve_resumes_run_with_allow(make_executor_env: EnvFactory) -> None:
    env, run = await _paused_env(make_executor_env)

    await env.permissions.decide_approval("APV-0001", approve=True, by="user", note="ok")
    ended = await asyncio.wait_for(env.executor.wait(run.id), GUARD_S)

    adapter = env.adapters["fake-codex"]
    assert isinstance(adapter, FakeModelAdapter)
    decisions = [decision for _, _, decision in adapter.authorizations]
    assert [(d.effect, d.approval_request_id) for d in decisions] == [
        (PermissionEffect.ALLOW, "APV-0001")
    ]
    invoked = await env.events(run.id, LedgerEventKind.TOOL_INVOKED)
    assert invoked[0].payload["approval_request_id"] == "APV-0001"
    kinds = [c.kind for c in env.checkpoints_of(run.id)]
    assert kinds == [CheckpointKind.START, CheckpointKind.PAUSE, CheckpointKind.END]
    assert ended.state is AgentRunState.COMPLETED


async def test_deny_results_in_tool_denied(make_executor_env: EnvFactory) -> None:
    env, run = await _paused_env(make_executor_env)

    await env.permissions.decide_approval("APV-0001", approve=False, by="user", note="no")
    await asyncio.wait_for(env.executor.wait(run.id), GUARD_S)

    denied = await env.events(run.id, LedgerEventKind.TOOL_DENIED)
    assert [(e.payload["approval_request_id"], e.payload["reason"]) for e in denied] == [
        ("APV-0001", "approval denied")
    ]
    assert len(env.hooks_fired(HookName.ON_TOOL_AFTER)) == 1


async def test_decide_twice_raises(manager: DefaultPermissionManager) -> None:
    approval_id = await _request(manager)
    await manager.decide_approval(approval_id, approve=False, by="user", note=None)

    with pytest.raises(PermanentError, match="approval already decided"):
        await manager.decide_approval(approval_id, approve=True, by="user", note=None)


async def test_expire_due_marks_expired(
    manager: DefaultPermissionManager, ledger: DefaultLedgerManager, fake_clock: FakeClock
) -> None:
    due = await _request(manager)
    fake_clock.advance(3600)
    later = await _request(manager)
    decided: list[tuple[str, ApprovalState]] = []
    manager.on_decided = lambda approval: decided.append((approval.id, approval.state))
    fake_clock.advance(86400 - 3600)

    expired = await manager.expire_due(fake_clock.now())
    again = await manager.expire_due(fake_clock.now())

    assert [(a.id, a.state) for a in expired] == [(due, ApprovalState.EXPIRED)]
    assert again == []
    assert [a.id for a in await manager.pending()] == [later]
    events = await ledger.query(kinds=[LedgerEventKind.APPROVAL_DECIDED])
    assert [(e.outcome, e.payload["reason"], e.actor_role) for e in events] == [
        ("DENIED", "expired", AgentRole.KERNEL)
    ]
    assert decided == [(due, ApprovalState.EXPIRED)]


async def test_failing_on_decided_callback_keeps_the_decision(
    manager: DefaultPermissionManager,
) -> None:
    approval_id = await _request(manager)

    def broken(approval: ApprovalRequest) -> None:
        msg = f"cannot wake {approval.id}"
        raise RuntimeError(msg)

    manager.on_decided = broken
    decided = await manager.decide_approval(approval_id, approve=True, by="user", note=None)

    assert decided.state is ApprovalState.APPROVED
    assert await manager.pending() == []
