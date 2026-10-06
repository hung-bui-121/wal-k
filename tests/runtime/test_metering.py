import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from tests.fakes.fake_model_adapter import fake_descriptor
from tests.runtime.conftest import STORY_ID
from walk.budgets import (
    BudgetRepository,
    BudgetSubject,
    CostRepository,
    DefaultBudgetManager,
    DefaultCostManager,
)
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager
from walk.model_router import UsageReport
from walk.persistence import Database
from walk.runtime import UsageMeter
from walk.telemetry import DefaultLedgerManager, LedgerEventKind
from walk.workflow import Story, WorkflowRepository

RUN_ID = "RUN-01J0000000000000000000000A"


def _usage(input_tokens: int, output_tokens: int, cache_read_tokens: int = 0) -> UsageReport:
    return UsageReport(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cost_usd=0.0,
        turns=1,
        tool_calls=1,
        duration_s=1.0,
    )


@pytest.fixture
def meter(
    db: Database,
    story: Story,
    ledger: DefaultLedgerManager,
    hooks: DefaultHookManager,
    fake_clock: FakeClock,
) -> UsageMeter:
    budgets = DefaultBudgetManager(db, BudgetRepository(db), ledger, hooks, fake_clock)
    costs = DefaultCostManager(db, CostRepository(db), ledger, budgets, WorkflowRepository(db))
    subject = BudgetSubject(
        project_key="DEMO", role=AgentRole.SENIOR_DEV, work_item_id=story.id, run_id=RUN_ID
    )
    ids = SequentialIdFactory()
    return UsageMeter(
        costs,
        fake_descriptor("fake-codex/sim", "fake-codex"),
        subject,
        fake_clock,
        new_id=ids.new_ulid,
    )


async def test_usage_meter_records_deltas_only(
    meter: UsageMeter, ledger: DefaultLedgerManager
) -> None:
    per_call = [_usage(1000, 200), _usage(2000, 400, 50), _usage(3000, 600, 50)]
    final = per_call[-1]  # the adapter's cumulative usage, as the closing USAGE reports it

    recorded = [await meter.observe(cumulative) for cumulative in per_call]
    closing = await meter.observe(final)

    assert closing is None
    assert all(record is not None for record in recorded)
    events = await ledger.query(kinds=[LedgerEventKind.COST_RECORDED], run_id=RUN_ID)
    assert len(events) == 3
    input_tokens = sum(int(str(e.payload["input_tokens"])) for e in events)
    output_tokens = sum(int(str(e.payload["output_tokens"])) for e in events)
    cache_tokens = sum(int(str(e.payload["cache_read_tokens"])) for e in events)
    assert input_tokens + output_tokens == final.input_tokens + final.output_tokens
    assert cache_tokens == final.cache_read_tokens
    assert all(e.work_item_id == STORY_ID for e in events)
    total = meter.total
    assert total.input_tokens == final.input_tokens
    assert total.output_tokens == final.output_tokens
    # 3000 input x $1/M + 600 output x $5/M
    assert total.cost_usd == pytest.approx(0.006)


async def test_usage_meter_rejects_decreasing_totals(meter: UsageMeter) -> None:
    await meter.observe(_usage(1000, 200))

    with pytest.raises(ConfigError, match="cumulative usage decreased"):
        await meter.observe(_usage(900, 300))
