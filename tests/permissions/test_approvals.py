import pytest

from tests.fakes.fake_clock import FakeClock
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, Hook, HookContext, HookExecutionRepository, HookName
from walk.permissions import (
    ApprovalRepository,
    ApprovalState,
    Approver,
    DefaultPermissionManager,
    ToolCallRequest,
)
from walk.persistence import Database, IdSequenceStore
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
    assert fired[0].payload == events[0].payload
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
    with pytest.raises(ConfigError, match="not pending"):
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
