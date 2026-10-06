"""Integration errors (WBS §3.2; E01-S23)."""

from walk.common.errors import PermanentError, TransientError


class NotSupported(PermanentError):
    """Provider does not implement the operation (e.g. LocalWorkProvider.parse_webhook)."""


class GitError(TransientError):
    """git exited non-zero; detail = argv + stderr tail."""
