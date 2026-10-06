from datetime import UTC, datetime
from pathlib import Path

import pytest

from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.memory import Freshness, MemoryDocType, parse_document, render_document

# ARCHITECTURE §8.2 sample front matter with §37 sections and one unknown section.
SAMPLE = """---
id: FEAT-0012                 # required; equals file stem
type: feature
title: Save System
status: IMPLEMENTING
version: 3
schema_version: 1
created_at: 2026-10-05T09:12:00Z
updated_at: 2026-10-07T14:03:11Z
updated_by:
  role: SENIOR_DEV
  model_id: codex/gpt-5-codex
  run_id: RUN-01J9ZZZZZZZZZZZZZZZZZZZZZZ
freshness:
  commit: 3f9c2e1
  branch: feat/FEAT-0012-save-system
  pr: 42
  build: 2026.10.07.3
  timestamp: 2026-10-07T14:03:11Z
related:
  work_items: [STORY-0412, STORY-0413]
  decisions: [DEC-0007]
  approved: [APR-0003]
  gdd: ["GDD/combat.md#shotgun"]
relevant_files:
  - Assets/Scripts/Save/SaveManager.cs
---

# Save System

## Architecture

Slots are JSON files.

```text
## not a heading inside a fence
```

## Team Notes

Kept verbatim.

## Intent

Players can save anywhere.
"""


def test_parse_render_round_trip_preserves_unknown_sections() -> None:
    path = Path("features/FEAT-0012.md")
    doc = parse_document(path, SAMPLE)
    fm = doc.front_matter
    assert (fm.id, fm.type, fm.title, fm.version) == (
        "FEAT-0012",
        MemoryDocType.FEATURE,
        "Save System",
        3,
    )
    assert fm.updated_by.role is AgentRole.SENIOR_DEV
    assert fm.freshness == Freshness(
        commit="3f9c2e1",
        branch="feat/FEAT-0012-save-system",
        pr="42",
        build="2026.10.07.3",
        timestamp=datetime(2026, 10, 7, 14, 3, 11, tzinfo=UTC),
    )
    assert fm.related.work_items == ["STORY-0412", "STORY-0413"]
    assert list(doc.sections) == ["Architecture", "Team Notes", "Intent"]
    assert doc.sections["Architecture"].endswith("## not a heading inside a fence\n```")
    assert doc.sections["Team Notes"] == "Kept verbatim."
    assert doc.path == "features/FEAT-0012.md"
    rendered = render_document(doc)
    again = parse_document(path, rendered)
    assert again.front_matter == fm
    assert again.sections == doc.sections
    # Known sections first in SECTION_ORDER, then unknown ones in their original order.
    assert list(again.sections) == ["Intent", "Architecture", "Team Notes"]
    assert render_document(again) == rendered


def test_parse_rejects_id_mismatch() -> None:
    with pytest.raises(ConfigError, match="FEAT-0013"):
        parse_document(Path("features/FEAT-0013.md"), SAMPLE)


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("# no front matter\n", "front matter"),
        ("---\nid: FEAT-0012\n", "front matter"),
        ("---\n- a list\n---\n", "front matter"),
        (SAMPLE.replace("type: feature", "type: novel"), "FEAT-0012"),
        (SAMPLE.replace("# Save System\n", "stray text\n"), "before the first section"),
        (SAMPLE.replace("## Intent", "## Architecture"), "duplicate section"),
    ],
)
def test_parse_rejects_malformed_documents(text: str, problem: str) -> None:
    with pytest.raises(ConfigError, match=problem):
        parse_document(Path("features/FEAT-0012.md"), text)


def test_parse_accepts_crlf_and_empty_sections() -> None:
    text = SAMPLE.replace("\n", "\r\n").replace("Kept verbatim.", "")
    doc = parse_document(Path("FEAT-0012.md"), text)
    assert doc.sections["Team Notes"] == ""
