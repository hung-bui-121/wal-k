"""Memory errors."""

from walk.common.errors import BoundaryViolation, PermanentError, PermissionDenied


class DocumentNotFound(PermanentError):
    """No `.ai/` document exists for the requested id; ``detail`` carries ``doc_id``."""


class SecretDetected(BoundaryViolation, PermissionDenied):
    """Content matches a secret pattern (ARCHITECTURE §6); nothing was written.

    Also a `PermissionDenied` (E02-S14: the write is refused).
    """


class ApprovedWriteRefused(PermissionDenied):
    """A write under ``approved/`` lacks a change-request decision (Invariant 10)."""


class ApprovalNotAuthorized(PermissionDenied):
    """The actor may not approve this artifact kind (§33; constitution ``may_approve``)."""


class ApprovedArtifactDrift(PermanentError):
    """Approved artifact payloads no longer match their hash; ``detail["ids"]`` lists them."""
