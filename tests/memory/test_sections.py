from datetime import UTC, datetime
from pathlib import Path

import pytest

from walk.common.errors import ConfigError
from walk.common.models import Actor
from walk.common.roles import AgentRole
from walk.memory import (
    SECTION_ORDER,
    MemoryDocType,
    doc_path_for,
    folder_for_type,
    sections_for,
    skeleton_for,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)
FEATURE_SECTIONS = (
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
)


def test_feature_section_order_and_skeleton() -> None:
    assert SECTION_ORDER[MemoryDocType.FEATURE] == FEATURE_SECTIONS
    doc = skeleton_for(
        MemoryDocType.FEATURE, "FEAT-0001", "Movement", Actor(role=AgentRole.KERNEL), NOW
    )
    assert tuple(doc.sections) == FEATURE_SECTIONS
    assert set(doc.sections.values()) == {""}
    fm = doc.front_matter
    assert (fm.id, fm.type, fm.title, fm.version) == (
        "FEAT-0001",
        MemoryDocType.FEATURE,
        "Movement",
        1,
    )
    assert (fm.created_at, fm.updated_at) == (NOW, NOW)
    assert doc.path == "features/FEAT-0001.md"


def test_section_order_sizes() -> None:
    sizes = {doc_type: len(SECTION_ORDER[doc_type]) for doc_type in SECTION_ORDER}
    assert sizes == {
        MemoryDocType.FEATURE: 14,
        MemoryDocType.BUG: 12,
        MemoryDocType.PROJECT: 10,
        MemoryDocType.HANDOVER: 10,
        MemoryDocType.DECISION: 11,
        MemoryDocType.APPROVED: 6,
    }
    assert SECTION_ORDER[MemoryDocType.DECISION][0] == "Topic"
    assert SECTION_ORDER[MemoryDocType.APPROVED][-1] == "Payload"
    assert sections_for(MemoryDocType.OBSERVATION) == ()


@pytest.mark.parametrize(
    ("doc_type", "doc_id", "expected"),
    [
        (MemoryDocType.PROJECT, "project", "project/project.md"),
        (MemoryDocType.PROJECT_CONSTITUTION, "constitution", "project/constitution.md"),
        (MemoryDocType.FEATURE, "FEAT-0012", "features/FEAT-0012.md"),
        (MemoryDocType.BUG, "BUG-0031", "bugs/BUG-0031.md"),
        (MemoryDocType.DECISION, "DEC-0007", "decisions/DEC-0007.md"),
        (MemoryDocType.APPROVED, "APR-0003", "approved/APR-0003.md"),
        (MemoryDocType.HANDOVER, "HO-0005", "handovers/HO-0005.md"),
        (MemoryDocType.PHASE, "PHASE-01", "phases/PHASE-01.md"),
        (MemoryDocType.OBSERVATION, "OBS-0001", "improvements/OBS-0001.md"),
        (MemoryDocType.CONSTITUTION, "lead_dev", "agents/roles/lead_dev.md"),
        (MemoryDocType.REPORT, "gdd-coverage", "reports/gdd-coverage.md"),
    ],
)
def test_doc_path_for_follows_the_ai_layout(
    tmp_path: Path, doc_type: MemoryDocType, doc_id: str, expected: str
) -> None:
    assert doc_path_for(tmp_path, doc_type, doc_id) == tmp_path / expected
    assert expected.startswith(folder_for_type(doc_type))


@pytest.mark.parametrize(
    ("doc_type", "doc_id"),
    [
        (MemoryDocType.FEATURE, "../escape"),
        (MemoryDocType.FEATURE, "a/b"),
        (MemoryDocType.FEATURE, ""),
        (MemoryDocType.PROJECT, "other"),
        (MemoryDocType.SKILL, "git-hygiene"),
        (MemoryDocType.EVIDENCE_PACKAGE, "PHASE-01"),
    ],
)
def test_doc_path_for_rejects_unsafe_or_underivable_ids(
    tmp_path: Path, doc_type: MemoryDocType, doc_id: str
) -> None:
    with pytest.raises(ConfigError):
        doc_path_for(tmp_path, doc_type, doc_id)
