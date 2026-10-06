"""Fixed H2 section order per document type (ADR-0003 D-2)."""

from datetime import datetime
from pathlib import Path

from walk.common.models import Actor
from walk.memory.models import FrontMatter, MemoryDocType, MemoryDocument
from walk.memory.paths import doc_path_for

SECTION_ORDER: dict[MemoryDocType, tuple[str, ...]] = {
    MemoryDocType.FEATURE: (  # §37
        "Intent",
        "Design Goal",
        "Relevant GDD",
        "Current Status",
        "Architecture",
        "Affected Systems",
        "Dependencies",
        "Relevant Files",
        "Important Decisions",
        "Implementation Notes",
        "Known Risks",
        "QC Notes",
        "Evidence",
        "Remaining Work",
    ),
    MemoryDocType.BUG: (  # §38
        "Problem",
        "Reproduction",
        "Expected Behavior",
        "Observed Behavior",
        "Investigations",
        "Hypotheses",
        "Failed Attempts",
        "Root Cause",
        "Affected Systems",
        "Fix",
        "Regression Risk",
        "Verification",
    ),
    MemoryDocType.PROJECT: (  # §36
        "Goals",
        "Platforms",
        "Technical Constraints",
        "Performance Targets",
        "Coding Conventions",
        "Architecture Overview",
        "Art Direction",
        "Product Constraints",
        "Major Decisions",
        "Known Limitations",
    ),
    MemoryDocType.HANDOVER: (  # §22
        "Task",
        "Current State",
        "Completed Work",
        "Modified Files",
        "Findings",
        "Hypotheses",
        "Decisions",
        "Risks",
        "Remaining Work",
        "Next Action",
    ),
    MemoryDocType.DECISION: (  # §44
        "Topic",
        "Participants",
        "Positions",
        "Evidence",
        "Outcome",
        "Owner",
        "Rationale",
        "Alternatives",
        "Affected Systems",
        "Related Work",
        "Version",
    ),
    MemoryDocType.APPROVED: (  # §33
        "Status",
        "Scope",
        "Version",
        "Approved By",
        "Related Requirements",
        "Payload",
    ),
}
"""H2 headings per document type, in specification order."""


def sections_for(doc_type: MemoryDocType) -> tuple[str, ...]:
    """The fixed sections of ``doc_type``; ``()`` for types without a section schema."""
    return SECTION_ORDER.get(doc_type, ())


def skeleton_for(
    doc_type: MemoryDocType, id_: str, title: str, actor: Actor, now: datetime
) -> MemoryDocument:
    """A new, unwritten document with every fixed section present and empty.

    Raises:
        ConfigError: If ``id_`` cannot address a document of ``doc_type`` (see `doc_path_for`).
    """
    path = doc_path_for(Path(), doc_type, id_).as_posix()
    front_matter = FrontMatter(
        id=id_, type=doc_type, title=title, created_at=now, updated_at=now, updated_by=actor
    )
    sections = dict.fromkeys(sections_for(doc_type), "")
    return MemoryDocument(path=path, front_matter=front_matter, sections=sections, raw_sha256="")
