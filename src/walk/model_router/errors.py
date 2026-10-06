"""Model router errors (WBS §3.2)."""

from walk.common.errors import PermanentError, TransientError


class NotResumable(PermanentError):
    """Adapter cannot continue the provider-side session (unsupported or expired)."""


class BlockedProvider(TransientError):
    """No routing candidate survived; detail = list[(model_id, reason)]."""
