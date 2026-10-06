"""Memory errors."""

from walk.common.errors import BoundaryViolation, PermanentError, PermissionDenied


class DocumentNotFound(PermanentError):
    """No `.ai/` document exists for the requested id; ``detail`` carries ``doc_id``."""


class SecretDetected(BoundaryViolation):
    """Content matches a secret pattern (ARCHITECTURE §6); nothing was written."""


class ApprovedWriteRefused(PermissionDenied):
    """A write under ``approved/`` lacks a change-request decision (Invariant 10)."""
