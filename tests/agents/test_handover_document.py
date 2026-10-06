from datetime import UTC, datetime
from pathlib import Path

import pytest

from walk.agents import HANDOVER_SECTION_FIELDS, Handover, from_document, to_document
from walk.common.errors import ConfigError
from walk.common.models import Actor
from walk.common.roles import AgentRole
from walk.memory import (
    SECTION_ORDER,
    MemoryDocType,
    parse_document,
    render_document,
    skeleton_for,
)

ACTOR = Actor(role=AgentRole.KERNEL)
NOW = datetime(2026, 2, 1, tzinfo=UTC)


def test_handover_document_round_trip(handover: Handover) -> None:
    doc = to_document(handover, actor=ACTOR, now=NOW)

    assert from_document(doc) == handover
    assert list(doc.sections) == list(SECTION_ORDER[MemoryDocType.HANDOVER])
    assert [heading for heading, _ in HANDOVER_SECTION_FIELDS] == list(doc.sections)
    assert doc.front_matter.type is MemoryDocType.HANDOVER
    assert doc.front_matter.id == "HO-0001"
    assert doc.front_matter.related.work_items == ["STORY-0001"]
    assert doc.front_matter.freshness is None
    assert doc.front_matter.extra["work_item_id"] == "STORY-0001"
    assert doc.front_matter.extra["reason"] == "FALLBACK"
    assert doc.front_matter.updated_by == ACTOR
    assert doc.path == "handovers/HO-0001.md"
    assert "- **Animator lacks a run state** — Needs a blend tree." in doc.sections["Findings"]
    assert "- Shift input mapped" in doc.sections["Completed Work"]
    assert doc.sections["Risks"] == "(none)"
    reparsed = parse_document(Path(doc.path), render_document(doc))
    assert from_document(reparsed) == handover


def test_handover_without_optional_values_round_trips(handover: Handover) -> None:
    bare = handover.model_copy(
        update={"to_run_id": None, "findings": [], "proposed_decisions": [], "decisions": []}
    )

    doc = to_document(bare, actor=ACTOR, now=NOW)

    assert from_document(doc) == bare
    assert from_document(parse_document(Path(doc.path), render_document(doc))) == bare


def test_from_document_rejects_wrong_type_or_reason(handover: Handover) -> None:
    feature = skeleton_for(MemoryDocType.FEATURE, "FEAT-0001", "Movement", ACTOR, NOW)
    with pytest.raises(ConfigError, match="handover"):
        from_document(feature)

    doc = to_document(handover, actor=ACTOR, now=NOW)
    doc.front_matter.extra["reason"] = "WHATEVER"
    with pytest.raises(ConfigError, match="reason") as info:
        from_document(doc)
    assert info.value.detail["key"] == "reason"


def test_from_document_rejects_missing_parts(handover: Handover) -> None:
    doc = to_document(handover, actor=ACTOR, now=NOW)
    del doc.front_matter.extra["worktree_head"]
    with pytest.raises(ConfigError, match="worktree_head"):
        from_document(doc)

    doc = to_document(handover, actor=ACTOR, now=NOW)
    del doc.sections["Next Action"]
    with pytest.raises(ConfigError, match="Next Action"):
        from_document(doc)

    doc = to_document(handover, actor=ACTOR, now=NOW)
    doc.sections["Findings"] = "- **x** — y"
    with pytest.raises(ConfigError, match="Findings"):
        from_document(doc)

    doc = to_document(handover, actor=ACTOR, now=NOW)
    doc.front_matter.extra["from_run_id"] = "not-a-run"
    with pytest.raises(ConfigError, match="HO-0001"):
        from_document(doc)


def test_from_document_rejects_invalid_json(handover: Handover) -> None:
    doc = to_document(handover, actor=ACTOR, now=NOW)
    doc.sections["Findings"] = "(none)\n\n```json\n[not json\n```"

    with pytest.raises(ConfigError, match="invalid JSON"):
        from_document(doc)
