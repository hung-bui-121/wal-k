from datetime import UTC, datetime

from tests.fakes.fake_model_adapter import fake_descriptor
from walk.budgets import BudgetDimension, BudgetSubject, CostCategory
from walk.common.roles import AgentRole
from walk.model_router import UsageReport, estimate_usage_cost_usd, usage_to_cost_record

AT = datetime(2026, 1, 1, tzinfo=UTC)
RUN = "RUN-01J00000000000000000000000"


def test_usage_to_cost_record_prices() -> None:
    descriptor = fake_descriptor(
        "fake-claude/sim",
        "fake-claude",
        input_cost_per_mtok_usd=3.0,
        output_cost_per_mtok_usd=15.0,
    )
    usage = UsageReport(
        input_tokens=1_000_000,
        output_tokens=100_000,
        cost_usd=0.0,
        turns=3,
        tool_calls=7,
        duration_s=12.0,
    )
    subject = BudgetSubject(
        project_key="DEMO",
        phase_id="PHASE-01",
        role=AgentRole.SENIOR_DEV,
        work_item_id="STORY-0001",
        run_id=RUN,
    )

    record = usage_to_cost_record(usage, descriptor, subject, record_id="COST-1", at=AT)

    assert record.cost_usd == 4.5
    assert record.quantity == 1_100_000
    assert record.category is CostCategory.LLM
    assert record.dimension is BudgetDimension.TOKENS
    assert record.unit == "tokens"
    assert (record.id, record.at, record.provider, record.model_id) == (
        "COST-1",
        AT,
        "fake-claude",
        "fake-claude/sim",
    )
    assert (record.project_key, record.phase_id, record.role, record.work_item_id) == (
        "DEMO",
        "PHASE-01",
        AgentRole.SENIOR_DEV,
        "STORY-0001",
    )
    assert record.run_id == RUN
    assert (record.input_tokens, record.output_tokens, record.cache_read_tokens) == (
        1_000_000,
        100_000,
        0,
    )


def test_estimate_includes_cache_reads_and_rounds() -> None:
    descriptor = fake_descriptor(
        "fake-codex/sim",
        "fake-codex",
        input_cost_per_mtok_usd=1.25,
        output_cost_per_mtok_usd=10.0,
        cache_read_cost_per_mtok_usd=0.125,
    )
    usage = UsageReport(
        input_tokens=1,
        output_tokens=1,
        cache_read_tokens=1_000_000,
        cost_usd=0.0,
        turns=1,
        tool_calls=0,
        duration_s=0.0,
    )

    assert estimate_usage_cost_usd(usage, descriptor) == round(0.125 + 11.25e-6, 6)
