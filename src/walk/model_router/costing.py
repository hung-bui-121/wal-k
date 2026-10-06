"""Token usage → cost (§84; ADR-0004 D-9: prices live in `models.yaml`)."""

from datetime import datetime

from walk.budgets.models import BudgetDimension, BudgetSubject, CostCategory, CostRecord
from walk.model_router.models import ModelDescriptor, UsageReport

_TOKENS_PER_PRICE_UNIT = 1_000_000  # descriptor prices are per million tokens
_COST_DECIMALS = 6


def estimate_usage_cost_usd(usage: UsageReport, descriptor: ModelDescriptor) -> float:
    """USD for ``usage`` at ``descriptor``'s prices, rounded to 6 decimals."""
    cost = (
        usage.input_tokens * descriptor.input_cost_per_mtok_usd
        + usage.output_tokens * descriptor.output_cost_per_mtok_usd
        + usage.cache_read_tokens * descriptor.cache_read_cost_per_mtok_usd
    ) / _TOKENS_PER_PRICE_UNIT
    return round(cost, _COST_DECIMALS)


def usage_to_cost_record(
    usage: UsageReport,
    descriptor: ModelDescriptor,
    subject: BudgetSubject,
    *,
    record_id: str,
    at: datetime,
) -> CostRecord:
    """An LLM `CostRecord` in the TOKENS dimension for ``usage``, charged to ``subject``."""
    return CostRecord(
        id=record_id,
        at=at,
        project_key=subject.project_key,
        category=CostCategory.LLM,
        provider=descriptor.provider,
        model_id=descriptor.id,
        dimension=BudgetDimension.TOKENS,
        quantity=usage.input_tokens + usage.output_tokens + usage.cache_read_tokens,
        unit="tokens",
        cost_usd=estimate_usage_cost_usd(usage, descriptor),
        run_id=subject.run_id,
        work_item_id=subject.work_item_id,
        phase_id=subject.phase_id,
        role=subject.role,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cache_read_tokens,
    )
