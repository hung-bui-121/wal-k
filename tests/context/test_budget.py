import pytest

from walk.common.enums import Effort
from walk.context import (
    CHARS_PER_TOKEN,
    EFFORT_BUDGET_RATIO,
    estimate_tokens,
    token_budget_for,
)


def test_token_budget_and_estimate() -> None:
    expected = {
        Effort.LOW: 24_000,
        Effort.MEDIUM: 54_000,
        Effort.HIGH: 84_000,
        Effort.VERY_HIGH: 104_000,
    }
    for effort in Effort:
        budget = token_budget_for(effort, 200_000, 16_000)
        assert budget == int(EFFORT_BUDGET_RATIO[effort] * 200_000) - 16_000
        assert budget == expected[effort]
    assert estimate_tokens("a" * 35) == 10
    assert estimate_tokens("a" * 36) == 11
    assert estimate_tokens("") == 0
    assert CHARS_PER_TOKEN == 3.5


def test_token_budget_bounds() -> None:
    with pytest.raises(ValueError, match="max_output_tokens"):
        token_budget_for(Effort.LOW, 10_000, 16_000)
    with pytest.raises(ValueError, match="max_output_tokens"):
        token_budget_for(Effort.LOW, 16_000, 16_000)
    assert token_budget_for(Effort.LOW, 20_000, 16_000) == 1000
    assert token_budget_for(Effort.VERY_HIGH, 30_000, 17_000) == 1000
