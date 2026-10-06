"""Token budget by effort and token estimation (ADR-0012 D-3)."""

import math

from walk.common.enums import Effort

EFFORT_BUDGET_RATIO: dict[Effort, float] = {
    Effort.LOW: 0.20,
    Effort.MEDIUM: 0.35,
    Effort.HIGH: 0.50,
    Effort.VERY_HIGH: 0.60,
}  # ADR-0012 D-3
CHARS_PER_TOKEN = 3.5
_MIN_BUDGET_TOKENS = 1000


def estimate_tokens(text: str) -> int:
    """Estimate the tokens of ``text`` as ``ceil(len(text) / 3.5)``."""
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def token_budget_for(effort: Effort, context_window_tokens: int, max_output_tokens: int) -> int:
    """Context budget = ``int(ratio[effort] * window) - max_output``, at least 1000 tokens.

    Raises:
        ValueError: ``max_output_tokens`` is not smaller than ``context_window_tokens``.
    """
    if max_output_tokens >= context_window_tokens:
        msg = (
            f"max_output_tokens ({max_output_tokens}) must be below "
            f"context_window_tokens ({context_window_tokens})"
        )
        raise ValueError(msg)
    budget = int(EFFORT_BUDGET_RATIO[effort] * context_window_tokens) - max_output_tokens
    return max(budget, _MIN_BUDGET_TOKENS)
