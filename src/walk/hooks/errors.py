"""Hook errors."""

from walk.common.errors import PermanentError


class HookFailed(PermanentError):
    """A FAIL_CLOSED hook failed; carries hook_id and results so far in detail."""
