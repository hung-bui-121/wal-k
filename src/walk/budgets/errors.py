"""Budget errors."""

from walk.common.errors import PermanentError


class BudgetExhausted(PermanentError):
    """Hard limit reached; ``detail`` carries the budget id and its hard_action."""
