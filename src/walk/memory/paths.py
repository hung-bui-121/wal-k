"""Where each `.ai/` document type lives (ARCHITECTURE §8, §8.1)."""

import re
from pathlib import Path
from typing import Final

from walk.common.errors import ConfigError
from walk.memory.models import MemoryDocType

_FOLDERS: Final = {
    MemoryDocType.PROJECT: "project",
    MemoryDocType.PROJECT_CONSTITUTION: "project",
    MemoryDocType.PHASE: "phases",
    MemoryDocType.FEATURE: "features",
    MemoryDocType.BUG: "bugs",
    MemoryDocType.DECISION: "decisions",
    MemoryDocType.APPROVED: "approved",
    MemoryDocType.HANDOVER: "handovers",
    MemoryDocType.REPORT: "reports",
    MemoryDocType.EVIDENCE_PACKAGE: "phases",
    MemoryDocType.RETROSPECTIVE: "improvements",
    MemoryDocType.OBSERVATION: "improvements",
    MemoryDocType.IMPROVEMENT_CANDIDATE: "improvements",
    MemoryDocType.PATTERN: "improvements",
    MemoryDocType.ANTI_PATTERN: "improvements",
    MemoryDocType.CONSTITUTION: "agents/roles",
    MemoryDocType.SKILL: "agents/skills",
}
# Documents whose id is fixed by their type (the file stem must equal the id).
_FIXED_IDS: Final = {
    MemoryDocType.PROJECT: "project",
    MemoryDocType.PROJECT_CONSTITUTION: "constitution",
}
# Paths not derivable from an id alone: evidence-package.md and SKILL.md have fixed stems.
_NOT_ID_ADDRESSED: Final = frozenset({MemoryDocType.EVIDENCE_PACKAGE, MemoryDocType.SKILL})
_SAFE_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def folder_for_type(doc_type: MemoryDocType) -> str:
    """Folder of ``doc_type`` relative to `.ai/` (POSIX separators)."""
    return _FOLDERS[doc_type]


def doc_path_for(ai_root: Path, doc_type: MemoryDocType, id_: str) -> Path:
    """Canonical path of document ``id_`` of ``doc_type`` under ``ai_root``.

    Raises:
        ConfigError: If ``id_`` is not a single safe path segment, a project document uses
            another id than its fixed one, or the type has no id-derived path.
    """
    if not _SAFE_ID.match(id_) or ".." in id_:
        msg = f"unsafe document id {id_!r}"
        raise ConfigError(msg, detail={"doc_id": id_})
    if doc_type in _NOT_ID_ADDRESSED:
        msg = f"{doc_type.value} documents are not addressed by id"
        raise ConfigError(msg, detail={"doc_id": id_, "type": doc_type.value})
    fixed = _FIXED_IDS.get(doc_type)
    if fixed is not None and id_ != fixed:
        msg = f"a {doc_type.value} document must have id {fixed!r}, not {id_!r}"
        raise ConfigError(msg, detail={"doc_id": id_, "type": doc_type.value})
    return ai_root / folder_for_type(doc_type) / f"{id_}.md"
