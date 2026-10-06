import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from walk.budgets import BudgetDimension
from walk.common.enums import Effort
from walk.common.ids import RunId
from walk.common.roles import AgentRole
from walk.effort import DefaultEffortManager, EffortPolicy, EffortRequest, StaticCostEstimator
from walk.hooks import DefaultHookManager, Hook, HookContext, HookExecutionRepository, HookName
from walk.persistence import Database
from walk.telemetry import DefaultLedgerManager, LedgerEventKind, LedgerRepository

COST = BudgetDimension.COST_USD
RUN: RunId = "RUN-01J0000000000000000000000A"


class Approvals:
    """Scripted `request_approval` callback that records its calls."""

    def __init__(self, *, answer: bool) -> None:
        self.answer = answer
        self.calls: list[tuple[RunId, EffortRequest]] = []

    async def __call__(self, run_id: RunId, request: EffortRequest) -> bool:
        self.calls.append((run_id, request))
        return self.answer


@pytest.fixture
def ledger(db: Database, fake_clock: FakeClock) -> DefaultLedgerManager:
    return DefaultLedgerManager(db, LedgerRepository(db), SequentialIdFactory(), fake_clock)


@pytest.fixture
def hooks(ledger: DefaultLedgerManager, db: Database, fake_clock: FakeClock) -> DefaultHookManager:
    return DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)


@pytest.fixture
def fired(hooks: DefaultHookManager) -> list[HookContext]:
    calls: list[HookContext] = []

    async def record(ctx: HookContext) -> None:
        calls.append(ctx)

    hooks.register(Hook(name=HookName.ON_EFFORT_CHANGE, id="test.effort", kind="builtin"), record)
    return calls


@pytest.fixture
def approvals() -> Approvals:
    return Approvals(answer=True)


@pytest.fixture
def effort(
    ledger: DefaultLedgerManager,
    hooks: DefaultHookManager,
    fake_clock: FakeClock,
    approvals: Approvals,
) -> DefaultEffortManager:
    return DefaultEffortManager(
        StaticCostEstimator(), ledger, hooks, fake_clock, approvals, project_key="DEMO"
    )


def _upgrade(target: Effort) -> EffortRequest:
    return EffortRequest(direction="UPGRADE", target=target, reason="needs deeper analysis")


async def _changes(ledger: DefaultLedgerManager) -> list[dict[str, object]]:
    events = await ledger.query(kinds=[LedgerEventKind.EFFORT_CHANGED])
    return [dict(event.payload) for event in events]


async def test_target_outside_policy_is_denied(
    effort: DefaultEffortManager, ledger: DefaultLedgerManager, fired: list[HookContext]
) -> None:
    result = await effort.request_change(
        RUN, Effort.HIGH, _upgrade(Effort.VERY_HIGH), EffortPolicy(), {}
    )
    assert result is Effort.HIGH
    assert await _changes(ledger) == []
    assert fired == []


async def test_upgrade_requires_approval_when_configured(
    effort: DefaultEffortManager,
    ledger: DefaultLedgerManager,
    fired: list[HookContext],
    approvals: Approvals,
) -> None:
    approvals.answer = False
    policy = EffortPolicy(auto_approve_upgrade_within_budget=False)
    request = _upgrade(Effort.HIGH)
    result = await effort.request_change(RUN, Effort.MEDIUM, request, policy, {})
    assert result is Effort.MEDIUM
    assert approvals.calls == [(RUN, request)]
    assert await _changes(ledger) == []
    assert fired == []


async def test_approved_upgrade_is_applied_when_approval_required(
    effort: DefaultEffortManager, ledger: DefaultLedgerManager, approvals: Approvals
) -> None:
    policy = EffortPolicy(auto_approve_upgrade_within_budget=False)
    result = await effort.request_change(RUN, Effort.MEDIUM, _upgrade(Effort.HIGH), policy, {})
    assert result is Effort.HIGH
    assert len(approvals.calls) == 1
    assert len(await _changes(ledger)) == 1


async def test_auto_approved_upgrade_skips_the_callback(
    effort: DefaultEffortManager, approvals: Approvals
) -> None:
    result = await effort.request_change(
        RUN, Effort.MEDIUM, _upgrade(Effort.HIGH), EffortPolicy(), {COST: 100.0}
    )
    assert result is Effort.HIGH
    assert approvals.calls == []


async def test_upgrade_denied_by_budget(
    effort: DefaultEffortManager, ledger: DefaultLedgerManager, fired: list[HookContext]
) -> None:
    # MEDIUM -> HIGH costs 8 - 3 = 5 USD more than the 4.99 USD left.
    result = await effort.request_change(
        RUN, Effort.MEDIUM, _upgrade(Effort.HIGH), EffortPolicy(), {COST: 4.99}
    )
    assert result is Effort.MEDIUM
    assert await _changes(ledger) == []
    assert fired == []


async def test_upgrade_approved_fires_hook_and_ledger(
    effort: DefaultEffortManager, ledger: DefaultLedgerManager, fired: list[HookContext]
) -> None:
    result = await effort.request_change(
        RUN, Effort.MEDIUM, _upgrade(Effort.HIGH), EffortPolicy(), {COST: 5.0}
    )
    assert result is Effort.HIGH
    expected = {
        "from": "MEDIUM",
        "to": "HIGH",
        "direction": "UPGRADE",
        "reason": "needs deeper analysis",
    }
    events = await ledger.query(kinds=[LedgerEventKind.EFFORT_CHANGED])
    assert len(events) == 1
    event = events[0]
    assert event.payload == expected
    assert (event.project_key, event.run_id, event.effort, event.outcome) == (
        "DEMO",
        RUN,
        Effort.HIGH,
        "OK",
    )
    assert event.actor_role is AgentRole.KERNEL
    assert len(fired) == 1
    assert fired[0].name is HookName.ON_EFFORT_CHANGE
    assert (fired[0].project_key, fired[0].run_id) == ("DEMO", RUN)
    assert fired[0].payload == expected


async def test_downgrade_always_allowed(
    effort: DefaultEffortManager,
    ledger: DefaultLedgerManager,
    fired: list[HookContext],
    approvals: Approvals,
) -> None:
    approvals.answer = False
    policy = EffortPolicy(auto_approve_upgrade_within_budget=False)
    request = EffortRequest(direction="DOWNGRADE", target=Effort.LOW, reason="simple fix")
    result = await effort.request_change(RUN, Effort.HIGH, request, policy, {COST: 0.0})
    assert result is Effort.LOW
    assert approvals.calls == []
    assert [change["direction"] for change in await _changes(ledger)] == ["DOWNGRADE"]
    assert len(fired) == 1


@pytest.mark.parametrize(
    "case",
    [
        ("UPGRADE", Effort.HIGH, Effort.MEDIUM),
        ("DOWNGRADE", Effort.LOW, Effort.MEDIUM),
        ("UPGRADE", Effort.MEDIUM, Effort.MEDIUM),
    ],
)
async def test_direction_must_match_the_target(
    effort: DefaultEffortManager,
    ledger: DefaultLedgerManager,
    fired: list[HookContext],
    case: tuple[str, Effort, Effort],
) -> None:
    direction, current, target = case
    request = EffortRequest.model_validate(
        {"direction": direction, "target": target, "reason": "mislabelled"}
    )
    result = await effort.request_change(RUN, current, request, EffortPolicy(), {})
    assert result is current
    assert await _changes(ledger) == []
    assert fired == []
