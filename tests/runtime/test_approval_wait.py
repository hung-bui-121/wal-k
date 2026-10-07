import pytest

from tests.fakes.fake_clock import FakeClock
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.permissions import (
    ApprovalRepository,
    ApprovalRequest,
    ApprovalState,
    Approver,
    DefaultPermissionManager,
)
from walk.persistence import Database, IdSequenceStore
from walk.runtime import ApprovalWaiter, PollingApprovalWaiter
from walk.telemetry import DefaultLedgerManager, LedgerEventKind, LedgerRepository


@pytest.fixture
def ledger(db: Database, fake_clock: FakeClock) -> DefaultLedgerManager:
    return DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), fake_clock)


@pytest.fixture
def permissions(
    db: Database, ledger: DefaultLedgerManager, fake_clock: FakeClock
) -> DefaultPermissionManager:
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)
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


async def _pending(permissions: DefaultPermissionManager) -> str:
    approval = await permissions.request_approval(
        {"tool": "git.merge_protected"},
        kind="PROTECTED_ACTION",
        approver=Approver.USER,
        requested_by=AgentRole.LEAD_DEV,
        run_id=None,
        work_item_id=None,
    )
    return approval.id


async def test_polling_waiter_returns_on_decision(
    db: Database, permissions: DefaultPermissionManager, fake_clock: FakeClock
) -> None:
    approval_id = await _pending(permissions)
    sleeps: list[float] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        fake_clock.advance(seconds)
        if len(sleeps) == 2:
            await permissions.decide_approval(approval_id, approve=True, by="user", note="ok")

    waiter: ApprovalWaiter = PollingApprovalWaiter(
        ApprovalRepository(db), fake_clock, permissions=permissions, sleep=sleep, interval_s=0.5
    )

    approved = await waiter.wait(approval_id, timeout_s=60)

    assert approved is ApprovalState.APPROVED
    assert sleeps == [0.5, 0.5]


async def test_polling_waiter_times_out_and_expires(
    db: Database,
    permissions: DefaultPermissionManager,
    ledger: DefaultLedgerManager,
    fake_clock: FakeClock,
) -> None:
    approval_id = await _pending(permissions)

    async def sleep(seconds: float) -> None:
        fake_clock.advance(seconds)

    waiter = PollingApprovalWaiter(
        ApprovalRepository(db), fake_clock, permissions=permissions, sleep=sleep
    )

    approved = await waiter.wait(approval_id, timeout_s=3)

    assert approved is ApprovalState.EXPIRED
    stored = await ApprovalRepository(db).get(approval_id)
    assert stored is not None
    assert stored.state is ApprovalState.EXPIRED
    assert stored.decision_note == "timeout"
    assert stored.decided_by == "kernel"
    events = await ledger.query(kinds=[LedgerEventKind.APPROVAL_DECIDED])
    assert len(events) == 1
    assert events[0].payload["state"] == "EXPIRED"


async def test_polling_waiter_denied_and_decided_during_expiry(
    db: Database, permissions: DefaultPermissionManager, fake_clock: FakeClock
) -> None:
    denied_id = await _pending(permissions)
    await permissions.decide_approval(denied_id, approve=False, by="user", note=None)
    late_id = await _pending(permissions)

    async def sleep(seconds: float) -> None:
        fake_clock.advance(seconds)

    class _Racing(ApprovalRepository):
        """Reports PENDING once more after the user approved (decision raced the expiry)."""

        async def get(self, key: str) -> ApprovalRequest | None:
            current = await super().get(key)
            if key == late_id and current is not None and current.state is ApprovalState.PENDING:
                await permissions.decide_approval(late_id, approve=True, by="user", note=None)
            return current

    waiter = PollingApprovalWaiter(
        ApprovalRepository(db), fake_clock, permissions=permissions, sleep=sleep
    )
    racing = PollingApprovalWaiter(_Racing(db), fake_clock, permissions=permissions, sleep=sleep)

    assert await waiter.wait(denied_id, timeout_s=10) is ApprovalState.DENIED
    assert await racing.wait(late_id, timeout_s=0) is ApprovalState.APPROVED
    with pytest.raises(ConfigError, match="unknown approval"):
        await waiter.wait("APV-9999", timeout_s=1)
