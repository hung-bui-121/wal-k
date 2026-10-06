"""Identifier types and helpers (DOMAIN-MODEL §1.2, §2).

Human-facing IDs are ``<PREFIX>-<zero-padded sequence>``; the width is a minimum, never a
maximum. Run, checkpoint and ledger IDs are ULIDs (time-ordered, generated in-process).
Sequence numbers are allocated by an `IdFactory` implementation (``walk.persistence``),
never hand-rolled elsewhere.
"""

import re
from typing import Annotated, Protocol

from pydantic import StringConstraints
from ulid import ULID

ULID_PATTERN: str = r"[0-9A-HJKMNP-TV-Z]{26}"

ProjectKey = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9]{1,9}$")]
PhaseId = Annotated[str, StringConstraints(pattern=r"^PHASE-\d{2,}$")]
EpicId = Annotated[str, StringConstraints(pattern=r"^EPIC-\d{3,}$")]
FeatureId = Annotated[str, StringConstraints(pattern=r"^FEAT-\d{4,}$")]
StoryId = Annotated[str, StringConstraints(pattern=r"^STORY-\d{4,}$")]
TaskId = Annotated[str, StringConstraints(pattern=r"^TASK-\d{4,}$")]
BugId = Annotated[str, StringConstraints(pattern=r"^BUG-\d{4,}$")]
WorkItemId = Annotated[str, StringConstraints(pattern=r"^(EPIC|FEAT|STORY|TASK|BUG)-\d{3,}$")]
DecisionId = Annotated[str, StringConstraints(pattern=r"^DEC-\d{4,}$")]
DebateId = Annotated[str, StringConstraints(pattern=r"^DEB-\d{4,}$")]
EvidenceId = Annotated[str, StringConstraints(pattern=r"^EVD-\d{6,}$")]
ApprovedArtifactId = Annotated[str, StringConstraints(pattern=r"^APR-\d{4,}$")]
HandoverId = Annotated[str, StringConstraints(pattern=r"^HO-\d{4,}$")]
ApprovalRequestId = Annotated[str, StringConstraints(pattern=r"^APV-\d{4,}$")]
ReleaseCandidateId = Annotated[str, StringConstraints(pattern=r"^RC-\d{2,}$")]
ObservationId = Annotated[str, StringConstraints(pattern=r"^OBS(-K)?-\d{4,}$")]
ImprovementId = Annotated[str, StringConstraints(pattern=r"^IMP-\d{2,}$")]
PatternId = Annotated[str, StringConstraints(pattern=r"^PATTERN-\d{3,}$")]
AntiPatternId = Annotated[str, StringConstraints(pattern=r"^ANTI-\d{3,}$")]
ExperimentId = Annotated[str, StringConstraints(pattern=r"^EXP-\d{4,}$")]
RetrospectiveId = Annotated[str, StringConstraints(pattern=r"^RETRO-[A-Z]+-[A-Z0-9-]+$")]
RunId = Annotated[str, StringConstraints(pattern=rf"^RUN-{ULID_PATTERN}$")]
CheckpointId = Annotated[str, StringConstraints(pattern=rf"^CKP-{ULID_PATTERN}$")]
LedgerEventId = Annotated[str, StringConstraints(pattern=rf"^LED-{ULID_PATTERN}$")]
ModelId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_-]+/[A-Za-z0-9._-]+$")]
SkillName = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
ToolName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")]
HookNameStr = Annotated[str, StringConstraints(pattern=r"^on_[a-z_]+$")]
Sha = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{7,64}$")]

_PREFIX_RE = re.compile(r"^(?P<prefix>.+)-\d+$")


class IdFactory(Protocol):
    """Allocates identifiers. The production implementation is ``IdSequenceStore``."""

    def next_sequence(self, prefix: str) -> str:
        """Return the next human-facing ID for ``prefix``, e.g. ``FEAT-0012``."""
        ...

    def new_ulid(self) -> str:
        """Return a new 26-character, time-ordered ULID."""
        ...


def new_ulid() -> str:
    """Return a new ULID: 26 Crockford base32 characters, lexicographically time-ordered."""
    return str(ULID())


def format_seq_id(prefix: str, n: int, width: int) -> str:
    """Format a sequence ID, zero-padding ``n`` to at least ``width`` digits.

    Args:
        prefix: ID prefix without the trailing dash, e.g. ``"FEAT"``.
        n: Sequence number, starting at 1.
        width: Minimum number of digits; longer numbers are never truncated.

    Returns:
        The formatted ID, e.g. ``"FEAT-0012"``.

    Raises:
        ValueError: If ``n`` is smaller than 1.
    """
    if n < 1:
        msg = f"sequence number must be >= 1, got {n}"
        raise ValueError(msg)
    return f"{prefix}-{n:0{width}d}"


def parse_prefix(id_: str) -> str:
    """Return everything before the last ``-<digits>`` group of an ID.

    Args:
        id_: A sequence ID such as ``"FEAT-0012"`` or ``"OBS-K-0001"``.

    Returns:
        The prefix, e.g. ``"FEAT"`` or ``"OBS-K"``.

    Raises:
        ValueError: If ``id_`` does not end with ``-<digits>``.
    """
    match = _PREFIX_RE.match(id_)
    if match is None:
        msg = f"not a sequence id: {id_!r}"
        raise ValueError(msg)
    return match.group("prefix")
