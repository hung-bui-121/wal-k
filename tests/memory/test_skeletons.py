from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from walk.common.models import Actor
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.memory import (
    DefaultMemoryManager,
    MemoryDocType,
    MemoryIndexRepository,
    parse_document,
    render_document,
)
from walk.memory.sections import sections_for
from walk.memory.skeletons import project_constitution_skeleton, project_skeleton
from walk.persistence import Database, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerRepository

USER = Actor(role=AgentRole.USER)
AT = datetime(2026, 10, 7, 9, 0, tzinfo=UTC)


@pytest.fixture
def memory(db: Database, fake_clock: FakeClock) -> DefaultMemoryManager:
    ledger = DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), fake_clock)
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)
    return DefaultMemoryManager(
        db.path.parent,
        MemoryIndexRepository(db),
        ledger,
        hooks,
        IdSequenceStore(db),
        fake_clock,
        project_key="DEMO",
    )


def test_project_skeleton_seeds_goals_from_gdd_headings() -> None:
    doc = project_skeleton("DEMO", "Demo", ["GDD/combat.md"], ["# Combat", "## Shotgun"], USER, AT)

    assert doc.front_matter.id == "project"
    assert doc.front_matter.type is MemoryDocType.PROJECT
    assert doc.front_matter.title == "Demo"
    assert doc.front_matter.related.gdd == ["GDD/combat.md"]
    assert doc.front_matter.extra == {"project_key": "DEMO"}
    assert doc.path == "project/project.md"
    assert doc.sections["Goals"].splitlines() == ["- Combat"]


def test_project_skeleton_uses_second_level_headings_without_a_first_level() -> None:
    doc = project_skeleton("DEMO", "Demo", ["GDD/a.md"], ["## Loot", "## Crafting"], USER, AT)

    assert doc.sections["Goals"].splitlines() == ["- Loot", "- Crafting"]


def test_project_skeleton_without_gdd_says_so() -> None:
    no_gdd = project_skeleton("DEMO", "Demo", [], [], USER, AT)
    no_headings = project_skeleton("DEMO", "Demo", ["GDD/notes.md"], [], USER, AT)

    assert no_gdd.sections["Goals"] == "- (no GDD provided)"
    assert no_headings.sections["Goals"] == "- (no headings found in the GDD)"


async def test_project_skeleton_has_all_sections_in_order(memory: DefaultMemoryManager) -> None:
    doc = project_skeleton("DEMO", "Demo", ["GDD/combat.md"], ["# Combat"], USER, AT)

    await memory.write(doc, actor=USER, head="0000000", branch="main")
    read = await memory.read("project")

    assert tuple(read.sections) == sections_for(MemoryDocType.PROJECT)
    assert len(read.sections) == 10
    assert read.sections["Goals"] == "- Combat"


def test_project_constitution_skeleton_sections_round_trip() -> None:
    doc = project_constitution_skeleton("DEMO", "Demo", USER, AT)

    parsed = parse_document(Path(doc.path), render_document(doc))

    assert doc.front_matter.id == "constitution"
    assert doc.front_matter.type is MemoryDocType.PROJECT_CONSTITUTION
    assert doc.path == "project/constitution.md"
    assert list(parsed.sections) == ["Product Authority", "Constraints", "Quality Bar", "Forbidden"]
