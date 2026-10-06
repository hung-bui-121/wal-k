import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from walk.budgets import (
    BudgetDimension,
    BudgetHardAction,
    BudgetManager,
    BudgetPolicy,
    BudgetRepository,
    BudgetScope,
    BudgetSubject,
    DefaultBudgetManager,
)
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, Hook, HookContext, HookExecutionRepository, HookName
from walk.persistence import Database, UnitOfWork
from walk.telemetry import DefaultLedgerManager, LedgerEvent, LedgerEventKind, LedgerRepository

COST = BudgetDimension.COST_USD
SUBJECT = BudgetSubject(project_key="DEMO", role=AgentRole.SENIOR_DEV, work_item_id="STORY-0001")


class SwitchableLedger(DefaultLedgerManager):
    """Ledger whose BUDGET_EVENT append fails while ``fail`` is set."""

    fail = False

    async def append(self, event: LedgerEvent, *, uow: UnitOfWork | None = None) -> LedgerEvent:
        if self.fail and event.kind is LedgerEventKind.BUDGET_EVENT:
            msg = "ledger down"
            raise RuntimeError(msg)
        return await super().append(event, uow=uow)


@pytest.fixture
def ledger(db: Database, fake_clock: FakeClock) -> SwitchableLedger:
    return SwitchableLedger(db, LedgerRepository(db), SequentialIdFactory(), fake_clock)


@pytest.fixture
def hooks(db: Database, ledger: SwitchableLedger, fake_clock: FakeClock) -> DefaultHookManager:
    return DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)


@pytest.fixture
def fired(hooks: DefaultHookManager) -> list[HookContext]:
    calls: list[HookContext] = []

    async def record(ctx: HookContext) -> None:
        calls.append(ctx)

    for name in (HookName.ON_BUDGET_THRESHOLD, HookName.ON_BUDGET_EXHAUSTED):
        hooks.register(Hook(name=name, id=f"test.{name.value}", kind="builtin"), record)
    return calls


@pytest.fixture
def budgets(
    db: Database, ledger: SwitchableLedger, hooks: DefaultHookManager, fake_clock: FakeClock
) -> DefaultBudgetManager:
    return DefaultBudgetManager(db, BudgetRepository(db), ledger, hooks, fake_clock)


async def _limit(
    budgets: DefaultBudgetManager,
    scope: BudgetScope,
    scope_id: str,
    limit: float,
    dimension: BudgetDimension = COST,
) -> None:
    await budgets.ensure(scope, scope_id, None, {dimension: limit})


def test_default_manager_satisfies_protocol(budgets: DefaultBudgetManager) -> None:
    protocol: BudgetManager = budgets
    assert protocol is budgets


async def test_ensure_is_idempotent_and_formats_ids(
    budgets: DefaultBudgetManager, db: Database
) -> None:
    created = await budgets.ensure(BudgetScope.TASK, "STORY-0001", BudgetPolicy(), None)
    assert sorted(b.id for b in created) == [
        "TASK:STORY-0001:COST_USD",
        "TASK:STORY-0001:EXECUTION_TIME_S",
        "TASK:STORY-0001:REVIEW_LOOPS",
        "TASK:STORY-0001:TOOL_CALLS",
    ]
    await budgets.meter(SUBJECT, COST, 2.0)
    again = await budgets.ensure(BudgetScope.TASK, "STORY-0001", BudgetPolicy(), None)
    assert len(again) == 4
    assert {b.id: b.consumed for b in again}["TASK:STORY-0001:COST_USD"] == 2.0
    rows = db.connect().execute('SELECT COUNT(*), SUM("limit") FROM budgets').fetchone()
    assert tuple(rows) == (4, 15.0 + 400 + 2700 + 3)


async def test_ensure_requires_policy_or_limits(budgets: DefaultBudgetManager) -> None:
    with pytest.raises(ConfigError, match="policy or limits"):
        await budgets.ensure(BudgetScope.TASK, "STORY-0001", None, None)
    custom = BudgetPolicy(soft_threshold_ratio=0.5, hard_action=BudgetHardAction.FALLBACK_MODEL)
    created = await budgets.ensure(BudgetScope.ROLE, "SENIOR_DEV", custom, {COST: 3.0})
    assert [(b.limit, b.soft_threshold_ratio, b.hard_action) for b in created] == [
        (3.0, 0.5, BudgetHardAction.FALLBACK_MODEL)
    ]


async def test_applicable_covers_subject_scopes(budgets: DefaultBudgetManager) -> None:
    await _limit(budgets, BudgetScope.GLOBAL, "GLOBAL", 1000)
    await _limit(budgets, BudgetScope.PROJECT, "DEMO", 500)
    await _limit(budgets, BudgetScope.PHASE, "PHASE-01", 100)
    await _limit(budgets, BudgetScope.ROLE, "SENIOR_DEV", 50)
    await _limit(budgets, BudgetScope.TASK, "STORY-0001", 10)
    await _limit(budgets, BudgetScope.TASK, "STORY-0002", 10)
    applicable = await budgets.applicable(SUBJECT)
    assert [b.scope for b in applicable] == [
        BudgetScope.GLOBAL,
        BudgetScope.PROJECT,
        BudgetScope.ROLE,
        BudgetScope.TASK,
    ]
    in_phase = SUBJECT.model_copy(update={"phase_id": "PHASE-01"})
    assert len(await budgets.applicable(in_phase)) == 5


async def test_meter_soft_threshold_fires_once(
    budgets: DefaultBudgetManager, ledger: SwitchableLedger, fired: list[HookContext]
) -> None:
    await _limit(budgets, BudgetScope.TASK, "STORY-0001", 10)
    verdict = await budgets.meter(SUBJECT, COST, 8.5)
    assert verdict.status == "SOFT_THRESHOLD"
    assert verdict.budget is not None
    assert verdict.budget.id == "TASK:STORY-0001:COST_USD"
    assert [(c.name, c.payload["budget_id"]) for c in fired] == [
        (HookName.ON_BUDGET_THRESHOLD, "TASK:STORY-0001:COST_USD")
    ]
    assert fired[0].work_item_id == "STORY-0001"
    events = await ledger.query(kinds=[LedgerEventKind.BUDGET_EVENT])
    assert len(events) == 1
    assert events[0].payload["dimension"] == "COST_USD"
    assert events[0].payload["quantity"] == 8.5
    assert events[0].payload["budgets"] == [
        {"id": "TASK:STORY-0001:COST_USD", "consumed": 8.5, "limit": 10.0}
    ]


async def test_soft_threshold_not_refired(
    budgets: DefaultBudgetManager, fired: list[HookContext]
) -> None:
    await _limit(budgets, BudgetScope.TASK, "STORY-0001", 10)
    await budgets.meter(SUBJECT, COST, 8.5)
    verdict = await budgets.meter(SUBJECT, COST, 0.5)
    assert verdict.status == "OK"
    assert len(fired) == 1


async def test_meter_exhausted_fires_hook(
    budgets: DefaultBudgetManager, fired: list[HookContext]
) -> None:
    await budgets.ensure(
        BudgetScope.TASK,
        "STORY-0001",
        BudgetPolicy(hard_action=BudgetHardAction.DOWNGRADE_EFFORT),
        {COST: 10.0},
    )
    verdict = await budgets.meter(SUBJECT, COST, 10.0)
    assert verdict.status == "EXHAUSTED"
    assert verdict.hard_action is BudgetHardAction.DOWNGRADE_EFFORT
    assert [c.name for c in fired] == [HookName.ON_BUDGET_THRESHOLD, HookName.ON_BUDGET_EXHAUSTED]
    again = await budgets.meter(SUBJECT, COST, 1.0)
    assert again.status == "EXHAUSTED"
    assert len(fired) == 2  # the exhausted hook fires when the limit is crossed, not again


async def test_meter_is_atomic_across_budgets(
    budgets: DefaultBudgetManager, ledger: SwitchableLedger
) -> None:
    await _limit(budgets, BudgetScope.TASK, "STORY-0001", 10)
    await _limit(budgets, BudgetScope.ROLE, "SENIOR_DEV", 20)
    await budgets.meter(SUBJECT, COST, 1.0)
    assert {b.scope: b.consumed for b in await budgets.applicable(SUBJECT)} == {
        BudgetScope.TASK: 1.0,
        BudgetScope.ROLE: 1.0,
    }
    ledger.fail = True
    with pytest.raises(RuntimeError, match="ledger down"):
        await budgets.meter(SUBJECT, COST, 2.0)
    assert [b.consumed for b in await budgets.applicable(SUBJECT)] == [1.0, 1.0]


async def test_meter_ignores_other_dimensions_and_missing_budgets(
    budgets: DefaultBudgetManager, ledger: SwitchableLedger
) -> None:
    await _limit(budgets, BudgetScope.TASK, "STORY-0001", 400, BudgetDimension.TOOL_CALLS)
    verdict = await budgets.meter(SUBJECT, COST, 3.0)
    assert (verdict.status, verdict.budget, verdict.hard_action) == ("OK", None, None)
    assert await ledger.query(kinds=[LedgerEventKind.BUDGET_EVENT]) == []
    assert [b.consumed for b in await budgets.applicable(SUBJECT)] == [0.0]


async def test_headroom_is_minimum_across_scopes(budgets: DefaultBudgetManager) -> None:
    await _limit(budgets, BudgetScope.PROJECT, "DEMO", 100)
    await _limit(budgets, BudgetScope.TASK, "STORY-0001", 10)
    await _limit(budgets, BudgetScope.ROLE, "SENIOR_DEV", 50, BudgetDimension.TOOL_CALLS)
    await budgets.meter(SUBJECT, COST, 4.0)
    assert await budgets.headroom(SUBJECT) == {
        BudgetDimension.COST_USD: 6.0,
        BudgetDimension.TOOL_CALLS: 50.0,
    }


async def test_meter_rejects_negative(budgets: DefaultBudgetManager) -> None:
    with pytest.raises(ValueError, match="negative"):
        await budgets.meter(SUBJECT, COST, -1)


async def test_can_afford(budgets: DefaultBudgetManager) -> None:
    await _limit(budgets, BudgetScope.TASK, "STORY-0001", 10)
    await _limit(budgets, BudgetScope.ROLE, "SENIOR_DEV", 5)
    await budgets.meter(SUBJECT, COST, 2.0)
    assert await budgets.can_afford(["STORY-0001"], COST, 8.0)
    assert not await budgets.can_afford(["STORY-0001", "SENIOR_DEV"], COST, 4.0)
    assert await budgets.can_afford(["STORY-0099"], COST, 1_000.0)
    assert await budgets.can_afford([], COST, 1.0)
