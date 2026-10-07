from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from walk.common.errors import ConfigError
from walk.common.models import Actor
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, Hook, HookContext, HookExecutionRepository, HookName
from walk.memory import (
    ApprovedWriteRefused,
    DefaultMemoryManager,
    DocumentNotFound,
    Freshness,
    MemoryDocType,
    MemoryDocument,
    MemoryIndexRepository,
    MemoryManager,
    SecretDetected,
    skeleton_for,
)
from walk.persistence import Database, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerEventKind, LedgerRepository

ACTOR = Actor(role=AgentRole.SENIOR_DEV, model_id="codex/gpt-5-codex")
HEAD = "3f9c2e1"
BRANCH = "feat/FEAT-0001"


@pytest.fixture
def ledger(db: Database, fake_clock: FakeClock) -> DefaultLedgerManager:
    return DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), fake_clock)


@pytest.fixture
def fired() -> list[HookContext]:
    return []


@pytest.fixture
def memory(
    db: Database, ledger: DefaultLedgerManager, fake_clock: FakeClock, fired: list[HookContext]
) -> DefaultMemoryManager:
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)

    async def record(ctx: HookContext) -> None:
        fired.append(ctx)

    hooks.register(Hook(name=HookName.ON_CONTEXT_UPDATED, id="test.ctx", kind="builtin"), record)
    return DefaultMemoryManager(
        db.path.parent,
        MemoryIndexRepository(db),
        ledger,
        hooks,
        IdSequenceStore(db),
        fake_clock,
        project_key="DEMO",
    )


def _feature(fake_clock: FakeClock, doc_id: str = "FEAT-0001") -> MemoryDocument:
    doc = skeleton_for(MemoryDocType.FEATURE, doc_id, "Movement", ACTOR, fake_clock.now())
    doc.sections["Intent"] = "Walk and run."
    return doc


def test_default_manager_satisfies_protocol(memory: DefaultMemoryManager, db: Database) -> None:
    protocol: MemoryManager = memory
    assert protocol is memory
    assert memory.root() == str(db.path.parent.resolve())


async def test_write_new_document_stamps_and_indexes(
    memory: DefaultMemoryManager,
    ledger: DefaultLedgerManager,
    fired: list[HookContext],
    db: Database,
    fake_clock: FakeClock,
) -> None:
    fake_clock.advance(30)
    written = await memory.write(_feature(fake_clock), actor=ACTOR, head=HEAD, branch=BRANCH)
    path = db.path.parent / "features" / "FEAT-0001.md"
    assert path.is_file()
    fm = written.front_matter
    assert fm.version == 1
    assert fm.freshness == Freshness(commit=HEAD, branch=BRANCH, timestamp=fake_clock.now())
    assert (fm.updated_at, fm.updated_by) == (fake_clock.now(), ACTOR)
    assert written.path == "features/FEAT-0001.md"
    assert written == await memory.read("FEAT-0001")
    rows = db.connect().execute("SELECT path, doc_id, type, version FROM memory_index").fetchall()
    assert [tuple(r) for r in rows] == [("features/FEAT-0001.md", "FEAT-0001", "feature", 1)]
    events = await ledger.query(kinds=[LedgerEventKind.CONTEXT_UPDATED])
    assert len(events) == 1
    assert events[0].payload["doc_id"] == "FEAT-0001"
    assert events[0].payload["version"] == 1
    assert events[0].payload["type"] == "feature"
    assert len(events[0].payload["sections_changed"]) == 14
    assert (events[0].work_item_id, events[0].actor_role) == ("FEAT-0001", AgentRole.SENIOR_DEV)
    assert [ctx.name for ctx in fired] == [HookName.ON_CONTEXT_UPDATED]
    assert fired[0].payload["doc_id"] == "FEAT-0001"


async def test_write_bumps_version_atomically(
    memory: DefaultMemoryManager, ledger: DefaultLedgerManager, db: Database, fake_clock: FakeClock
) -> None:
    first = await memory.write(_feature(fake_clock), actor=ACTOR, head=HEAD, branch=BRANCH)
    fake_clock.advance(60)
    first.sections["Architecture"] = "State machine."
    second = await memory.write(first, actor=ACTOR, head="abcdef1", branch=BRANCH)
    assert second.front_matter.version == 2
    assert second.front_matter.created_at == first.front_matter.created_at
    assert second.front_matter.freshness is not None
    assert second.front_matter.freshness.commit == "abcdef1"
    assert list((db.path.parent / "features").iterdir()) == [
        db.path.parent / "features" / "FEAT-0001.md"
    ]
    events = await ledger.query(kinds=[LedgerEventKind.CONTEXT_UPDATED])
    assert events[-1].payload["sections_changed"] == ["Architecture"]


async def test_write_keeps_pr_and_build(
    memory: DefaultMemoryManager, fake_clock: FakeClock
) -> None:
    doc = _feature(fake_clock)
    doc.front_matter.freshness = Freshness(
        commit="0000000", branch="x", timestamp=fake_clock.now(), pr="42", build="7"
    )
    written = await memory.write(doc, actor=ACTOR, head=HEAD, branch=BRANCH)
    assert written.front_matter.freshness is not None
    assert (written.front_matter.freshness.pr, written.front_matter.freshness.build) == ("42", "7")


async def test_write_refuses_secrets(
    memory: DefaultMemoryManager, db: Database, fake_clock: FakeClock
) -> None:
    await memory.write(_feature(fake_clock), actor=ACTOR, head=HEAD, branch=BRANCH)
    path = db.path.parent / "features" / "FEAT-0001.md"
    before = path.read_text(encoding="utf-8")
    doc = _feature(fake_clock)
    doc.sections["Implementation Notes"] = "key " + "AKIA" + "ABCDEFGHIJKLMNOP"
    with pytest.raises(SecretDetected, match="aws_access_key"):
        await memory.write(doc, actor=ACTOR, head=HEAD, branch=BRANCH)
    assert path.read_text(encoding="utf-8") == before


async def test_write_refuses_unauthorised_approved_change(
    memory: DefaultMemoryManager, db: Database, fake_clock: FakeClock
) -> None:
    doc = skeleton_for(MemoryDocType.APPROVED, "APR-0001", "Art", ACTOR, fake_clock.now())
    with pytest.raises(ApprovedWriteRefused):
        await memory.write(doc, actor=ACTOR, head=HEAD, branch=BRANCH)
    assert not (db.path.parent / "approved").exists()
    doc.front_matter.extra["change_request_decision"] = "DEC-0001"
    written = await memory.write(doc, actor=ACTOR, head=HEAD, branch=BRANCH)
    assert written.path == "approved/APR-0001.md"


async def test_write_is_atomic_on_failure(
    memory: DefaultMemoryManager,
    db: Database,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await memory.write(_feature(fake_clock), actor=ACTOR, head=HEAD, branch=BRANCH)
    path = db.path.parent / "features" / "FEAT-0001.md"
    before = path.read_text(encoding="utf-8")

    def broken_replace(self: Path, target: object) -> Path:
        msg = "disk full"
        raise OSError(msg)

    monkeypatch.setattr(Path, "replace", broken_replace)
    doc = await memory.read("FEAT-0001")
    doc.sections["Intent"] = "Changed."
    with pytest.raises(OSError, match="disk full"):
        await memory.write(doc, actor=ACTOR, head=HEAD, branch=BRANCH)
    assert path.read_text(encoding="utf-8") == before
    assert list(path.parent.iterdir()) == [path]
    version = db.connect().execute("SELECT version FROM memory_index").fetchone()[0]
    assert version == 1


async def test_write_rejects_an_invalid_head(
    memory: DefaultMemoryManager, fake_clock: FakeClock
) -> None:
    with pytest.raises(ConfigError, match="head"):
        await memory.write(_feature(fake_clock), actor=ACTOR, head="not-a-sha", branch=BRANCH)


async def test_read_unknown_document_raises(memory: DefaultMemoryManager) -> None:
    with pytest.raises(DocumentNotFound):
        await memory.read("FEAT-0099")
    with pytest.raises(DocumentNotFound):
        await memory.read("DEC-0001")


@pytest.mark.parametrize(
    "call",
    [
        "read_feature_context",
        "read_bug_context",
        "read_project_context",
        "assess_freshness",
    ],
)
async def test_later_story_methods_raise_config_error(
    memory: DefaultMemoryManager, fake_clock: FakeClock, call: str
) -> None:
    args: dict[str, tuple[object, ...]] = {
        "read_feature_context": ("FEAT-0001",),
        "read_bug_context": ("BUG-0001",),
        "assess_freshness": (_feature(fake_clock), HEAD),
    }
    pending = getattr(memory, call)(*args.get(call, ()))
    with pytest.raises(ConfigError, match="implemented in E0"):
        await pending


def test_root_is_absolute(memory: DefaultMemoryManager) -> None:
    assert Path(memory.root()).is_absolute()
