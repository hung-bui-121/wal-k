import logging
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from walk.common.errors import ConfigError
from walk.common.models import Actor
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.memory import (
    DefaultMemoryManager,
    MemoryDocType,
    MemoryIndexRepository,
    MemoryIndexRow,
    SecretDetected,
    render_document,
    skeleton_for,
)
from walk.persistence import Database, IdSequenceStore, UnitOfWork
from walk.telemetry import DefaultLedgerManager, LedgerRepository

ACTOR = Actor(role=AgentRole.KERNEL)


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


def _put(ai: Path, doc_type: MemoryDocType, doc_id: str, folder: str, clock: FakeClock) -> None:
    doc = skeleton_for(doc_type, doc_id, doc_id, ACTOR, clock.now())
    target = ai / folder / f"{doc_id}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_document(doc), encoding="utf-8")


async def test_rebuild_index_syncs_rows(
    memory: DefaultMemoryManager,
    db: Database,
    fake_clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    ai = db.path.parent
    _put(ai, MemoryDocType.FEATURE, "FEAT-0001", "features", fake_clock)
    _put(ai, MemoryDocType.BUG, "BUG-0001", "bugs", fake_clock)
    _put(ai, MemoryDocType.DECISION, "DEC-0001", "decisions", fake_clock)
    # Not indexed: reports, canonical skills, evidence files, unparsable documents.
    (ai / "reports" / "tasks").mkdir(parents=True)
    (ai / "reports" / "tasks" / "STORY-0001.md").write_text("# report\n", encoding="utf-8")
    (ai / "agents" / "skills" / "git").mkdir(parents=True)
    (ai / "agents" / "skills" / "git" / "SKILL.md").write_text("---\nname: git\n---\n", "utf-8")
    (ai / "features" / "FEAT-0001" / "evidence").mkdir(parents=True)
    (ai / "features" / "FEAT-0001" / "evidence" / "notes.md").write_text("x", encoding="utf-8")
    (ai / "decisions" / "broken.md").write_text("no front matter\n", encoding="utf-8")
    index = MemoryIndexRepository(db)
    stale = MemoryIndexRow(
        path="features/FEAT-0099.md",
        doc_id="FEAT-0099",
        type=MemoryDocType.FEATURE,
        title="gone",
        status=None,
        version=1,
        updated_at=fake_clock.now(),
        freshness_commit=None,
        freshness_status=None,
        freshness_checked_at=None,
        raw_sha256="0" * 64,
        relevant_files=[],
        related={},
    )
    async with UnitOfWork(db) as uow:
        await index.upsert(stale, uow)
    with caplog.at_level(logging.WARNING, logger="walk.memory.service"):
        count = await memory.rebuild_index()
    assert count == 3
    rows = await index.all()
    assert [row.path for row in rows] == [
        "bugs/BUG-0001.md",
        "decisions/DEC-0001.md",
        "features/FEAT-0001.md",
    ]
    assert await index.by_doc_id("FEAT-0099") is None
    assert [getattr(r, "doc_path", None) for r in caplog.records] == ["decisions/broken.md"]
    assert (await memory.read("DEC-0001")).front_matter.type is MemoryDocType.DECISION


async def test_write_report_bypasses_index(memory: DefaultMemoryManager, db: Database) -> None:
    path = await memory.write_report("task", "STORY-0001", "# Task report\n")
    expected = db.path.parent / "reports" / "task" / "STORY-0001.md"
    assert path == str(expected.resolve())
    assert expected.read_text(encoding="utf-8") == "# Task report\n"
    assert await MemoryIndexRepository(db).all() == []
    await memory.write_report("task", "STORY-0001", "# Again\n")
    assert expected.read_text(encoding="utf-8") == "# Again\n"


async def test_write_report_rejects_unsafe_names_and_secrets(memory: DefaultMemoryManager) -> None:
    with pytest.raises(ConfigError):
        await memory.write_report("../x", "STORY-0001", "md")
    with pytest.raises(SecretDetected):
        await memory.write_report("task", "STORY-0001", "ghp_" + "e" * 36)
