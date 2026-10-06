from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from walk.budgets import (
    Budget,
    BudgetDimension,
    BudgetExhausted,
    BudgetHardAction,
    BudgetPolicy,
    BudgetScope,
    BudgetVerdict,
    CostCategory,
    CostRecord,
)
from walk.common.errors import PermanentError


def test_budget_policy_defaults() -> None:
    policy = BudgetPolicy()
    assert policy.per_task == {
        BudgetDimension.COST_USD: 15.0,
        BudgetDimension.TOOL_CALLS: 400,
        BudgetDimension.EXECUTION_TIME_S: 2700,
        BudgetDimension.REVIEW_LOOPS: 3,
    }
    assert policy.soft_threshold_ratio == 0.8
    assert policy.hard_action is BudgetHardAction.BLOCK
    with pytest.raises(ValidationError):
        BudgetPolicy(soft_threshold_ratio=1.5)


def test_budget_and_cost_record_models() -> None:
    budget = Budget(
        id="TASK:STORY-0001:COST_USD",
        scope=BudgetScope.TASK,
        scope_id="STORY-0001",
        dimension=BudgetDimension.COST_USD,
        limit=10.0,
    )
    assert (budget.consumed, budget.soft_notified) == (0.0, False)
    verdict = BudgetVerdict(status="OK", budget=None, hard_action=None)
    assert verdict.status == "OK"
    record = CostRecord(
        id="COST-1",
        at=datetime(2026, 1, 1, tzinfo=UTC),
        project_key="DEMO",
        category=CostCategory.LLM,
        provider="claude",
        dimension=BudgetDimension.TOKENS,
        quantity=1200,
        unit="tokens",
    )
    assert record.cost_usd == 0.0


def test_budget_exhausted_is_permanent() -> None:
    error = BudgetExhausted("limit reached", detail={"budget_id": "TASK:STORY-0001:COST_USD"})
    assert isinstance(error, PermanentError)
    assert error.detail["budget_id"] == "TASK:STORY-0001:COST_USD"
