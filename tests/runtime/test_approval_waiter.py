import asyncio

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.runtime.executor_env import EXECUTOR_RULES, EnvFactory, ExecutorEnv, script
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.permissions import (
    ApprovalRepository,
    ApprovalRequest,
    ApprovalState,
    Approver,
    DefaultPermissionManager,
    PermissionEffect,
    PermissionRule,
)
from walk.persistence import Database, IdSequenceStore
from walk.runtime import AgentRunState, ApprovalWaiter, EventApprovalWaiter, RecoveryManager
from walk.telemetry import DefaultLedgerManager, LedgerEventKind

MERGE = "git.merge_protected"
GUARD_S = 5
POLL_S = 0.01


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
        {"tool": MERGE},
        kind="PROTECTED_ACTION",
        approver=Approver.USER,
        requested_by=AgentRole.LEAD_DEV,
        run_id=None,
        work_item_id=None,
    )
    return approval.id


async def test_wait_timeout_returns_expired(
    db: Database,
    permissions: DefaultPermissionManager,
    ledger: DefaultLedgerManager,
    fake_clock: FakeClock,
) -> None:
    approval_id = await _pending(permissions)
    sleeps: list[float] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        fake_clock.advance(seconds)

    waiter: ApprovalWaiter = EventApprovalWaiter(
        ApprovalRepository(db), fake_clock, permissions=permissions, sleep=sleep, poll_interval_s=30
    )

    state = await asyncio.wait_for(waiter.wait(approval_id, timeout_s=60), GUARD_S)

    assert state is ApprovalState.EXPIRED
    assert sleeps == [30, 30]
    stored = await ApprovalRepository(db).get(approval_id)
    assert stored is not None
    assert stored.state is ApprovalState.EXPIRED
    events = await ledger.query(kinds=[LedgerEventKind.APPROVAL_DECIDED])
    assert [e.outcome for e in events] == ["DENIED"]


async def test_resolve_wakes_the_waiter_without_polling(
    db: Database, permissions: DefaultPermissionManager, fake_clock: FakeClock
) -> None:
    approval_id = await _pending(permissions)
    waiter = EventApprovalWaiter(ApprovalRepository(db), fake_clock, permissions=permissions)
    permissions.on_decided = lambda approval: waiter.resolve(approval.id, approval.state)
    waiter.register(approval_id)

    waiting = asyncio.create_task(waiter.wait(approval_id, timeout_s=3600))
    await asyncio.sleep(0)
    await permissions.decide_approval(approval_id, approve=True, by="user", note=None)

    assert await asyncio.wait_for(waiting, GUARD_S) is ApprovalState.APPROVED


async def test_wait_sees_a_decision_made_by_another_process(
    db: Database, permissions: DefaultPermissionManager, fake_clock: FakeClock
) -> None:
    approval_id = await _pending(permissions)
    polls: list[float] = []

    async def sleep(seconds: float) -> None:
        polls.append(seconds)
        if len(polls) == 1:  # e.g. `walk deny` in-process while no callback reaches the waiter
            await permissions.decide_approval(approval_id, approve=False, by="user", note=None)

    waiter = EventApprovalWaiter(
        ApprovalRepository(db), fake_clock, permissions=permissions, sleep=sleep
    )

    state = await asyncio.wait_for(waiter.wait(approval_id, timeout_s=3600), GUARD_S)

    assert state is ApprovalState.DENIED
    assert polls == [1.0]


async def test_wait_for_unknown_request_raises(
    db: Database, permissions: DefaultPermissionManager, fake_clock: FakeClock
) -> None:
    waiter = EventApprovalWaiter(ApprovalRepository(db), fake_clock, permissions=permissions)

    with pytest.raises(ConfigError, match="APV-0404"):
        await waiter.wait("APV-0404", timeout_s=1)


async def _short_sleep(seconds: float) -> None:
    del seconds
    await asyncio.sleep(POLL_S)


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


async def test_recovery_reregisters_and_resumes_approved(make_executor_env: EnvFactory) -> None:
    rules = [
        *EXECUTOR_RULES,
        PermissionRule(
            role=AgentRole.SENIOR_DEV,
            tool=MERGE,
            effect=PermissionEffect.REQUIRE_APPROVAL,
            approver=Approver.USER,
        ),
    ]
    plan = script(tool_calls=1, tool_name=MERGE)
    old = await make_executor_env(
        plan, rules=rules, approval_sleep=_short_sleep, event_waiter=True, kernel_instance="old"
    )
    run = await old.executor.start(old.agent, old.story, "IMPLEMENT")
    await asyncio.wait_for(_until_requested(old), GUARD_S)
    await old.executor.shutdown()  # the kernel dies while the run waits for the approval
    orphan = await old.runs.get(run.id)
    assert orphan is not None
    assert orphan.state is AgentRunState.PAUSED_FOR_APPROVAL
    await old.permissions.decide_approval("APV-0001", approve=True, by="user", note="ok")
    new = await make_executor_env(
        adapters=old.adapters,
        rules=rules,
        approval_sleep=_short_sleep,
        event_waiter=True,
        kernel_instance="new",
    )

    report = await _recovery(new, "new").recover()

    assert report.failed == []
    continued = [*report.resumed_native, *report.restarted_with_handover]
    assert len(continued) == 1
    ended = await asyncio.wait_for(new.executor.wait(continued[0]), GUARD_S)
    assert ended.state is AgentRunState.COMPLETED
    requested = await new.ledger.query(kinds=[LedgerEventKind.APPROVAL_REQUESTED])
    assert [e.payload["approval_id"] for e in requested] == ["APV-0001"]
    invoked = await new.ledger.query(run_id=continued[0], kinds=[LedgerEventKind.TOOL_INVOKED])
    assert invoked[0].payload["approval_request_id"] == "APV-0001"


async def _until_requested(env: ExecutorEnv) -> None:
    while True:
        if await env.permissions.pending():
            return
        await asyncio.sleep(POLL_S)


async def test_resolve_ignores_pending_and_expiry_loses_a_race(
    db: Database, permissions: DefaultPermissionManager, fake_clock: FakeClock
) -> None:
    approval_id = await _pending(permissions)

    class _Racing(ApprovalRepository):
        """Reports PENDING once more after the user approved (the decision raced the expiry)."""

        async def get(self, key: str) -> ApprovalRequest | None:
            current = await super().get(key)
            if current is not None and current.state is ApprovalState.PENDING:
                await permissions.decide_approval(key, approve=True, by="user", note=None)
            return current

    waiter = EventApprovalWaiter(_Racing(db), fake_clock, permissions=permissions)
    waiter.register(approval_id)
    waiter.resolve(approval_id, ApprovalState.PENDING)  # not decided: nothing to wake

    assert await waiter.wait(approval_id, timeout_s=0) is ApprovalState.APPROVED


async def test_recovery_waits_on_the_pending_request_and_asks_anew_for_the_next_call(
    make_executor_env: EnvFactory,
) -> None:
    rules = [
        *EXECUTOR_RULES,
        PermissionRule(
            role=AgentRole.SENIOR_DEV,
            tool=MERGE,
            effect=PermissionEffect.REQUIRE_APPROVAL,
            approver=Approver.USER,
        ),
    ]
    plan = script(tool_calls=2, tool_name=MERGE)
    old = await make_executor_env(
        plan, rules=rules, approval_sleep=_short_sleep, event_waiter=True, kernel_instance="old"
    )
    await old.executor.start(old.agent, old.story, "IMPLEMENT")
    await asyncio.wait_for(_until_requested(old), GUARD_S)
    await old.executor.shutdown()
    new = await make_executor_env(
        adapters=old.adapters,
        rules=rules,
        approval_sleep=_short_sleep,
        event_waiter=True,
        kernel_instance="new",
    )

    report = await _recovery(new, "new").recover()
    continued = [*report.resumed_native, *report.restarted_with_handover][0]
    # The continuing run waits on the still-pending APV-0001, then asks anew for its 2nd call.
    await asyncio.wait_for(_until_paused(new, continued), GUARD_S)
    await new.permissions.decide_approval("APV-0001", approve=True, by="user", note=None)
    await asyncio.wait_for(_until_pending(new, "APV-0002"), GUARD_S)
    await new.permissions.decide_approval("APV-0002", approve=True, by="user", note=None)
    ended = await asyncio.wait_for(new.executor.wait(continued), GUARD_S)

    assert ended.state is AgentRunState.COMPLETED
    requested = await new.ledger.query(kinds=[LedgerEventKind.APPROVAL_REQUESTED])
    assert [e.payload["approval_id"] for e in requested] == ["APV-0001", "APV-0002"]
    assert [e.run_id for e in requested] == [requested[0].run_id, continued]


async def _until_pending(env: ExecutorEnv, approval_id: str) -> None:
    while True:
        if approval_id in [a.id for a in await env.permissions.pending()]:
            return
        await asyncio.sleep(POLL_S)


async def _until_paused(env: ExecutorEnv, run_id: str) -> None:
    while True:
        run = await env.runs.get(run_id)
        if run is not None and run.state is AgentRunState.PAUSED_FOR_APPROVAL:
            return
        await asyncio.sleep(POLL_S)
