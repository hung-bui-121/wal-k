import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from walk.common.errors import ConfigError
from walk.common.models import Actor
from walk.common.roles import AgentRole
from walk.persistence import Database, IdSequenceStore
from walk.telemetry import (
    DefaultEvidenceManager,
    DefaultLedgerManager,
    Evidence,
    EvidenceDraft,
    EvidenceKind,
    EvidenceManager,
    EvidenceRepository,
    LedgerEventKind,
    LedgerRepository,
)

QC = Actor(role=AgentRole.QC)
NOW = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    root = tmp_path / "game"
    root.mkdir()
    return root


@pytest.fixture
def project_db(db: Database) -> Database:
    db.connect().execute(
        "INSERT INTO projects (key, name, repo_path, json, created_at, updated_at) "
        "VALUES ('DEMO', 'Demo', '.', '{}', ?, ?)",
        (NOW, NOW),
    )
    return db


@pytest.fixture
def ledger(project_db: Database, fake_clock: FakeClock) -> DefaultLedgerManager:
    return DefaultLedgerManager(
        project_db, LedgerRepository(project_db), SequentialIdFactory(), fake_clock
    )


@pytest.fixture
def evidence(
    project_db: Database, repo_root: Path, ledger: DefaultLedgerManager, fake_clock: FakeClock
) -> DefaultEvidenceManager:
    return DefaultEvidenceManager(
        project_db,
        repo_root / ".ai",
        EvidenceRepository(project_db),
        ledger,
        IdSequenceStore(project_db),
        fake_clock,
    )


def _evidence(kind: EvidenceKind, produced_at: datetime, id_: str = "EVD-000001") -> Evidence:
    return Evidence(
        id=id_,
        kind=kind,
        description="d",
        uri="x",
        sha256=None,
        produced_by=QC,
        produced_at=produced_at,
        work_item_id=None,
        phase_id=None,
        commit=None,
    )


async def test_record_copies_hashes_and_logs(
    evidence: DefaultEvidenceManager,
    ledger: DefaultLedgerManager,
    repo_root: Path,
    fake_clock: FakeClock,
) -> None:
    source = repo_root / "Logs" / "editmode.xml"
    source.parent.mkdir()
    source.write_bytes(b"<tests passed='12'/>")
    draft = EvidenceDraft(
        kind=EvidenceKind.AUTOMATED_TEST,
        path_or_uri="Logs/editmode.xml",
        description="EditMode tests",
        metrics={"passed": 12},
    )
    recorded = await evidence.record(
        draft, actor=QC, work_item_id="STORY-0001", phase_id="PHASE-01", commit="abc1234"
    )
    copied = repo_root / ".ai" / "features" / "STORY-0001" / "evidence" / "editmode.xml"
    assert copied.read_bytes() == source.read_bytes()
    assert recorded.id == "EVD-000001"
    assert recorded.uri == ".ai/features/STORY-0001/evidence/editmode.xml"
    assert recorded.sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert recorded.produced_at == fake_clock.now()
    assert recorded.metrics == {"passed": 12}
    assert await evidence.for_item("STORY-0001") == [recorded]
    (event,) = await ledger.query(kinds=[LedgerEventKind.EVIDENCE_RECORDED])
    assert (event.project_key, event.work_item_id, event.phase_id) == (
        "DEMO",
        "STORY-0001",
        "PHASE-01",
    )
    assert event.payload == {"evidence_id": "EVD-000001", "kind": "AUTOMATED_TEST"}


async def test_record_files_by_bug_and_phase(
    evidence: DefaultEvidenceManager, repo_root: Path
) -> None:
    shot = repo_root / "shot.png"
    shot.write_bytes(b"png")
    draft = EvidenceDraft(kind=EvidenceKind.SCREENSHOT, path_or_uri=str(shot), description="s")
    bug = await evidence.record(
        draft, actor=QC, work_item_id="BUG-0003", phase_id=None, commit=None
    )
    phase = await evidence.record(
        draft, actor=QC, work_item_id=None, phase_id="PHASE-02", commit=None
    )
    assert bug.uri == ".ai/bugs/BUG-0003/evidence/shot.png"
    assert phase.uri == ".ai/phases/PHASE-02/evidence/shot.png"
    assert phase.id == "EVD-000002"
    assert await evidence.for_phase("PHASE-02") == [phase]


async def test_record_keeps_file_already_in_evidence_folder(
    evidence: DefaultEvidenceManager, repo_root: Path
) -> None:
    folder = repo_root / ".ai" / "features" / "FEAT-0001" / "evidence"
    folder.mkdir(parents=True)
    (folder / "metrics.json").write_text("{}", encoding="utf-8")
    draft = EvidenceDraft(
        kind=EvidenceKind.PERFORMANCE_METRICS,
        path_or_uri=".ai/features/FEAT-0001/evidence/metrics.json",
        description="m",
    )
    recorded = await evidence.record(
        draft, actor=QC, work_item_id="FEAT-0001", phase_id=None, commit=None
    )
    assert recorded.uri == ".ai/features/FEAT-0001/evidence/metrics.json"
    again = await evidence.record(
        draft, actor=QC, work_item_id="FEAT-0001", phase_id=None, commit=None
    )
    assert again.sha256 == recorded.sha256


async def test_record_refuses_to_overwrite_different_evidence(
    evidence: DefaultEvidenceManager, repo_root: Path
) -> None:
    log = repo_root / "run.log"
    log.write_text("first", encoding="utf-8")
    draft = EvidenceDraft(kind=EvidenceKind.LOG, path_or_uri="run.log", description="l")
    await evidence.record(draft, actor=QC, work_item_id="BUG-0001", phase_id=None, commit=None)
    log.write_text("second", encoding="utf-8")
    with pytest.raises(ConfigError):
        await evidence.record(draft, actor=QC, work_item_id="BUG-0001", phase_id=None, commit=None)
    assert len(await evidence.for_item("BUG-0001")) == 1


async def test_record_external_uri(evidence: DefaultEvidenceManager, repo_root: Path) -> None:
    uri = "https://ci.example.invalid/builds/42/artifact.zip"
    recorded = await evidence.record(
        EvidenceDraft(kind=EvidenceKind.BUILD_ARTIFACT, path_or_uri=uri, description="build"),
        actor=QC,
        work_item_id=None,
        phase_id=None,
        commit=None,
    )
    assert recorded.uri == uri
    assert recorded.sha256 is None
    assert not (repo_root / ".ai").exists()


@pytest.mark.parametrize(
    ("work_item_id", "phase_id"), [("STORY-0001", None), ("EPIC-001", None), (None, None)]
)
async def test_record_missing_file_raises(
    evidence: DefaultEvidenceManager,
    project_db: Database,
    repo_root: Path,
    work_item_id: str | None,
    phase_id: str | None,
) -> None:
    present = repo_root / "present.txt"
    present.write_text("x", encoding="utf-8")
    path = "missing.txt" if work_item_id == "STORY-0001" else "present.txt"
    draft = EvidenceDraft(kind=EvidenceKind.LOG, path_or_uri=path, description="l")
    with pytest.raises(ConfigError):
        await evidence.record(
            draft, actor=QC, work_item_id=work_item_id, phase_id=phase_id, commit=None
        )
    assert project_db.connect().execute("SELECT count(*) FROM evidence").fetchone()[0] == 0
    assert not (repo_root / ".ai").exists()


async def test_record_requires_a_project(
    db: Database, repo_root: Path, fake_clock: FakeClock
) -> None:
    ledger = DefaultLedgerManager(db, LedgerRepository(db), SequentialIdFactory(), fake_clock)
    manager = DefaultEvidenceManager(
        db, repo_root / ".ai", EvidenceRepository(db), ledger, IdSequenceStore(db), fake_clock
    )
    draft = EvidenceDraft(kind=EvidenceKind.LOG, path_or_uri="https://x.invalid/l", description="l")
    with pytest.raises(ConfigError):
        await manager.record(draft, actor=QC, work_item_id=None, phase_id=None, commit=None)
    assert db.connect().execute("SELECT count(*) FROM evidence").fetchone()[0] == 0


def test_strongest_uses_rank(evidence: DefaultEvidenceManager) -> None:
    t = datetime(2026, 1, 1, tzinfo=UTC)
    log = _evidence(EvidenceKind.LOG, t + timedelta(hours=1))
    test = _evidence(EvidenceKind.AUTOMATED_TEST, t, "EVD-000002")
    assert evidence.strongest([log, test]) == test
    assert evidence.strongest([]) is None


def test_strongest_breaks_ties_by_recency(evidence: DefaultEvidenceManager) -> None:
    t = datetime(2026, 1, 1, tzinfo=UTC)
    older = _evidence(EvidenceKind.AUTOMATED_TEST, t)
    newer = _evidence(EvidenceKind.AUTOMATED_TEST, t + timedelta(minutes=5), "EVD-000002")
    assert evidence.strongest([newer, older]) == newer
    assert evidence.strongest([older, newer]) == newer


def test_satisfies_returns_missing_kinds(evidence: DefaultEvidenceManager) -> None:
    t = datetime(2026, 1, 1, tzinfo=UTC)
    present = [_evidence(EvidenceKind.BUILD_ARTIFACT, t)]
    required = [
        EvidenceKind.QC_REPORT,
        EvidenceKind.BUILD_ARTIFACT,
        EvidenceKind.AUTOMATED_TEST,
        EvidenceKind.QC_REPORT,
    ]
    assert evidence.satisfies(required, present) == [
        EvidenceKind.QC_REPORT,
        EvidenceKind.AUTOMATED_TEST,
    ]
    assert evidence.satisfies([], present) == []


async def test_for_item_filters_by_kind(evidence: DefaultEvidenceManager, repo_root: Path) -> None:
    (repo_root / "a.png").write_bytes(b"a")
    (repo_root / "b.log").write_bytes(b"b")
    shot = await evidence.record(
        EvidenceDraft(kind=EvidenceKind.SCREENSHOT, path_or_uri="a.png", description="a"),
        actor=QC,
        work_item_id="FEAT-0001",
        phase_id=None,
        commit=None,
    )
    await evidence.record(
        EvidenceDraft(kind=EvidenceKind.LOG, path_or_uri="b.log", description="b"),
        actor=QC,
        work_item_id="FEAT-0001",
        phase_id=None,
        commit=None,
    )
    assert await evidence.for_item("FEAT-0001", kinds=[EvidenceKind.SCREENSHOT]) == [shot]
    assert len(await evidence.for_item("FEAT-0001")) == 2
    assert len(await evidence.for_item("FEAT-0001", kinds=[])) == 2  # empty filter = all kinds


def test_default_evidence_manager_satisfies_protocol(evidence: DefaultEvidenceManager) -> None:
    manager: EvidenceManager = evidence
    assert manager is evidence


async def test_record_removes_copy_when_transaction_fails(
    db: Database, repo_root: Path, fake_clock: FakeClock
) -> None:
    ledger = DefaultLedgerManager(db, LedgerRepository(db), SequentialIdFactory(), fake_clock)
    manager = DefaultEvidenceManager(
        db, repo_root / ".ai", EvidenceRepository(db), ledger, IdSequenceStore(db), fake_clock
    )
    (repo_root / "run.log").write_text("log", encoding="utf-8")
    draft = EvidenceDraft(kind=EvidenceKind.LOG, path_or_uri="run.log", description="l")
    with pytest.raises(ConfigError):  # no project row: the transaction rolls back
        await manager.record(draft, actor=QC, work_item_id="BUG-0001", phase_id=None, commit=None)
    folder = repo_root / ".ai" / "bugs" / "BUG-0001" / "evidence"
    assert list(folder.iterdir()) == []
