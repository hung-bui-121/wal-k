"""Kernel exception hierarchy (ARCHITECTURE §5.1).

```text
WalkError
├── TransientError          retry with backoff; may become a FallbackTrigger
│   ├── ProviderUnavailable, RateLimited, Timeout, QuotaExhausted, ToolCrashed
├── PermanentError          no retry; fail the run or operation
│   ├── PermissionDenied, GuardRejected, OutputInvalid, BoundaryViolation, ConfigError
└── RecoverableInterruption process died or was cancelled; resume from checkpoint
```
"""

from walk.common.models import JsonDict


class WalkError(Exception):
    """Base class of every kernel error.

    Attributes:
        message: Human-readable description.
        detail: Structured context for the ledger and logs; never contains secrets.
    """

    def __init__(self, message: str, *, detail: JsonDict | None = None) -> None:
        """Create the error with a message and optional structured detail."""
        super().__init__(message)
        self.message = message
        self.detail: JsonDict = dict(detail) if detail is not None else {}


class TransientError(WalkError):
    """A failure that may succeed on retry (exponential backoff, ARCHITECTURE §5.1)."""


class ProviderUnavailable(TransientError):
    """The model or service provider is unreachable or reports an outage."""


class RateLimited(TransientError):
    """The provider rejected the call because of rate limiting."""


class Timeout(TransientError):
    """An operation exceeded its time limit."""


class QuotaExhausted(TransientError):
    """The provider quota or budget is exhausted."""


class ToolCrashed(TransientError):
    """An external tool process crashed or exited abnormally."""


class PermanentError(WalkError):
    """A failure that retrying cannot fix; the run or operation fails."""


class PermissionDenied(PermanentError):
    """The kernel permission system denied an action (§31)."""


class GuardRejected(PermanentError):
    """A workflow transition guard rejected an event (§53)."""


class OutputInvalid(PermanentError):
    """An agent output failed schema validation after the allowed repair turns."""


class BoundaryViolation(PermanentError):
    """An agent touched paths outside its allowed repository boundary (§91)."""


class ConfigError(PermanentError):
    """Configuration is missing, malformed or inconsistent."""


class RecoverableInterruption(WalkError):
    """The process died or work was cancelled; resume from the last checkpoint (§89)."""
