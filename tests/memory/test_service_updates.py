import pytest

from tests.fakes.fake_clock import FakeClock
from walk.common.errors import ConfigError
from walk.common.models import Actor
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.memory import (
    ContextUpdate,
    DefaultMemoryManager,
    DocumentNotFound,
    MemoryDocType,
    MemoryIndexRepository,
    skeleton_for,
)
from walk.persistence import Database, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerEventKind, LedgerRepository

ACTOR = Actor(role=AgentRole.SENIOR_DEV)
HEAD = "3f9c2e1"
BRANCH = "feat/FEAT-0001"


@pytest.fixture
def ledger(db: Database, fake_clock: FakeClock) -> DefaultLedgerManager:
    return DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), fake_clock)


@pytest.fixture
def memory(
    db: Database, ledger: DefaultLedgerManager, fake_clock: FakeClock
) -> DefaultMemoryManager:
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


def _update(
    doc_id: str, section: str, operation: str, content: str, files: list[str] | None = None
) -> ContextUpdate:
    return ContextUpdate.model_validate(
        {
            "doc_id": doc_id,
            "section": section,
            "operation": operation,
            "content_markdown": content,
            "relevant_files": files or [],
        }
    )


async def test_apply_updates_creates_skeleton_and_edits_sections(
    memory: DefaultMemoryManager, ledger: DefaultLedgerManager
) -> None:
    written = await memory.apply_updates(
        [
            _update("FEAT-0001", "Architecture", "REPLACE", "Event bus.", ["Assets/A.cs"]),
            _update("FEAT-0001", "Implementation Notes", "APPEND", "First note."),
            _update(
                "FEAT-0001",
                "Implementation Notes",
                "APPEND",
                "Second note.",
                ["Assets/B.cs", "Assets/A.cs"],
            ),
        ],
        actor=ACTOR,
        head=HEAD,
        branch=BRANCH,
    )
    assert len(written) == 1
    doc = written[0]
    assert doc.front_matter.type is MemoryDocType.FEATURE
    assert doc.front_matter.version == 1
    assert doc.sections["Architecture"] == "Event bus."
    assert doc.sections["Implementation Notes"] == "First note.\n\nSecond note."
    assert doc.sections["Intent"] == ""
    assert doc.front_matter.relevant_files == ["Assets/A.cs", "Assets/B.cs"]
    assert len(await ledger.query(kinds=[LedgerEventKind.CONTEXT_UPDATED])) == 1
    again = await memory.apply_updates(
        [_update("FEAT-0001", "Architecture", "REPLACE", "\nECS.\n")],
        actor=ACTOR,
        head=HEAD,
        branch=BRANCH,
    )
    assert again[0].front_matter.version == 2
    assert again[0].sections["Architecture"] == "ECS."
    assert again[0].sections["Implementation Notes"] == "First note.\n\nSecond note."


async def test_apply_updates_touches_each_document_once(memory: DefaultMemoryManager) -> None:
    written = await memory.apply_updates(
        [
            _update("BUG-0001", "Problem", "REPLACE", "Crash."),
            _update("project", "Goals", "REPLACE", "Ship."),
            _update("BUG-0001", "Fix", "APPEND", "Null check."),
        ],
        actor=ACTOR,
        head=HEAD,
        branch=BRANCH,
    )
    assert [d.front_matter.id for d in written] == ["BUG-0001", "project"]
    assert written[1].path == "project/project.md"


async def test_apply_updates_rejects_unknown_section(
    memory: DefaultMemoryManager, ledger: DefaultLedgerManager, db: Database
) -> None:
    updates = [
        _update("FEAT-0001", "Architecture", "REPLACE", "ok"),
        _update("FEAT-0001", "Vibes", "REPLACE", "nope"),
    ]
    with pytest.raises(ConfigError, match="Vibes"):
        await memory.apply_updates(updates, actor=ACTOR, head=HEAD, branch=BRANCH)
    assert not (db.path.parent / "features").exists()
    assert await ledger.query(kinds=[LedgerEventKind.CONTEXT_UPDATED]) == []


async def test_apply_updates_cannot_create_untyped_documents(memory: DefaultMemoryManager) -> None:
    with pytest.raises(ConfigError, match="DEC-0001"):
        await memory.apply_updates(
            [_update("DEC-0001", "Topic", "REPLACE", "x")], actor=ACTOR, head=HEAD, branch=BRANCH
        )


async def test_write_and_read_handover(
    memory: DefaultMemoryManager, ledger: DefaultLedgerManager, db: Database, fake_clock: FakeClock
) -> None:
    doc = skeleton_for(MemoryDocType.HANDOVER, "HO-0001", "Fallback", ACTOR, fake_clock.now())
    doc.front_matter.extra.update({"work_item_id": "STORY-0001", "reason": "FALLBACK"})
    doc.sections["Next Action"] = "Run the tests."
    path = await memory.write_handover(doc, actor=ACTOR, head=HEAD, branch=BRANCH)
    expected = db.path.parent / "handovers" / "HO-0001.md"
    assert path == str(expected.resolve())
    assert expected.is_file()
    events = await ledger.query(kinds=[LedgerEventKind.HANDOVER_CREATED])
    assert len(events) == 1
    assert events[0].payload == {
        "handover_id": "HO-0001",
        "work_item_id": "STORY-0001",
        "reason": "FALLBACK",
    }
    assert events[0].work_item_id == "STORY-0001"
    assert len(await ledger.query(kinds=[LedgerEventKind.CONTEXT_UPDATED])) == 1
    read = await memory.read_handover("HO-0001")
    assert read.sections["Next Action"] == "Run the tests."
    with pytest.raises(DocumentNotFound):
        await memory.read_handover("HO-0002")


async def test_write_handover_requires_a_handover_document(
    memory: DefaultMemoryManager, fake_clock: FakeClock
) -> None:
    doc = skeleton_for(MemoryDocType.FEATURE, "FEAT-0001", "x", ACTOR, fake_clock.now())
    with pytest.raises(ConfigError, match="handover"):
        await memory.write_handover(doc, actor=ACTOR, head=HEAD, branch=BRANCH)


async def test_write_handover_rejects_an_invalid_work_item(
    memory: DefaultMemoryManager, db: Database, fake_clock: FakeClock
) -> None:
    doc = skeleton_for(MemoryDocType.HANDOVER, "HO-0001", "Fallback", ACTOR, fake_clock.now())
    doc.front_matter.extra["work_item_id"] = "not an id"
    with pytest.raises(ConfigError, match="HANDOVER_CREATED"):
        await memory.write_handover(doc, actor=ACTOR, head=HEAD, branch=BRANCH)
    assert not (db.path.parent / "handovers").exists()
