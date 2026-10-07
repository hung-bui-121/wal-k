import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from walk.common.errors import ConfigError, PermissionDenied
from walk.common.models import Actor
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, Hook, HookContext, HookExecutionRepository, HookName
from walk.integrations import AsyncioSubprocessRunner, GitCliProvider
from walk.memory import (
    APPROVED_DIR,
    ApprovalNotAuthorized,
    ApprovalStatus,
    ApprovedArtifact,
    ApprovedArtifactKind,
    ApprovedArtifactRepository,
    DefaultMemoryManager,
    FreshnessStatus,
    MemoryIndexRepository,
    hash_payload,
)
from walk.persistence import Database, IdempotencyStore, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerEventKind, LedgerRepository

AT = datetime(2026, 1, 1, tzinfo=UTC)
USER = Actor(role=AgentRole.USER)
MAY_APPROVE = {AgentRole.LEAD_DEV: frozenset({"ARCHITECTURE_DIRECTION"})}

ManagerFactory = Callable[..., DefaultMemoryManager]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def ledger(db: Database, fake_clock: FakeClock) -> DefaultLedgerManager:
    return DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), fake_clock)


@pytest.fixture
def stale() -> list[HookContext]:
    return []


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A git repository whose `.ai/` is the test database's folder (``<tmp>/.ai``)."""
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.name", "walk-tests")
    _git(tmp_path, "config", "user.email", "walk-tests@example.invalid")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "chore: initial commit")
    (tmp_path / "GDD").mkdir()
    (tmp_path / "GDD" / "concept.png").write_bytes(b"\x89PNG concept")
    (tmp_path / "GDD" / "loop.md").write_bytes(b"# Core loop\n")
    return tmp_path


@pytest.fixture
def manager(
    db: Database,
    ledger: DefaultLedgerManager,
    fake_clock: FakeClock,
    stale: list[HookContext],
    repo: Path,
) -> DefaultMemoryManager:
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)

    async def record(ctx: HookContext) -> None:
        stale.append(ctx)

    hooks.register(Hook(name=HookName.ON_CONTEXT_STALE, id="test.stale", kind="builtin"), record)
    git = GitCliProvider(
        repo,
        AsyncioSubprocessRunner(),
        ledger,
        IdempotencyStore(db, fake_clock),
        fake_clock,
        project_key="DEMO",
    )
    return DefaultMemoryManager(
        repo / ".ai",
        MemoryIndexRepository(db),
        ledger,
        hooks,
        IdSequenceStore(db),
        fake_clock,
        project_key="DEMO",
        git=git,
        may_approve=lambda role: MAY_APPROVE.get(role, frozenset()),
    )


def artifact(
    kind: ApprovedArtifactKind = ApprovedArtifactKind.GAMEPLAY_CONCEPT, **fields: object
) -> ApprovedArtifact:
    """A placeholder (``APR-0000``) artifact over the two GDD files."""
    data: dict[str, object] = {
        "id": "APR-0000",
        "kind": kind,
        "title": "Core loop",
        "status": ApprovalStatus.DRAFT,
        "scope": "project",
        "version": 1,
        "approved_by": USER,
        "approved_at": AT,
        "related_requirements": [],
        "payload_paths": ["GDD/concept.png", "GDD/loop.md"],
        "content_sha256": "",
        **fields,
    }
    return ApprovedArtifact.model_validate(data)


async def test_approve_writes_doc_payload_row_and_ledger(
    manager: DefaultMemoryManager, db: Database, ledger: DefaultLedgerManager, repo: Path
) -> None:
    approved = await manager.approve_artifact(artifact(), actor=USER)

    folder = repo / ".ai" / APPROVED_DIR / "APR-0001"
    assert approved.id == "APR-0001"
    assert approved.status is ApprovalStatus.APPROVED
    assert approved.version == 1
    assert approved.payload_paths == ["concept.png", "loop.md"]
    assert (folder / "concept.png").read_bytes() == b"\x89PNG concept"
    assert approved.content_sha256 == hash_payload(folder, approved.payload_paths)
    doc = await manager.read("APR-0001")
    assert doc.path == "approved/APR-0001.md"
    assert doc.front_matter.extra["content_sha256"] == approved.content_sha256
    assert doc.front_matter.extra["kind"] == "GAMEPLAY_CONCEPT"
    assert list(doc.sections) == [
        "Status",
        "Scope",
        "Version",
        "Approved By",
        "Related Requirements",
        "Payload",
        "Summary",
        "Change History",
    ]
    stored = await ApprovedArtifactRepository(db).get("APR-0001")
    assert stored == approved
    events = await ledger.query(kinds=[LedgerEventKind.ARTIFACT_APPROVED])
    assert [e.payload for e in events] == [
        {"id": "APR-0001", "kind": "GAMEPLAY_CONCEPT", "sha": approved.content_sha256}
    ]


async def test_approve_requires_authority(manager: DefaultMemoryManager, repo: Path) -> None:
    senior = Actor(role=AgentRole.SENIOR_DEV)

    with pytest.raises(ApprovalNotAuthorized):
        await manager.approve_artifact(artifact(ApprovedArtifactKind.ART_DIRECTION), actor=senior)

    assert isinstance(ApprovalNotAuthorized("x"), PermissionDenied)
    assert not (repo / ".ai" / APPROVED_DIR).exists()


async def test_role_with_may_approve_can_approve_kind(manager: DefaultMemoryManager) -> None:
    lead = Actor(role=AgentRole.LEAD_DEV)

    approved = await manager.approve_artifact(
        artifact(ApprovedArtifactKind.ARCHITECTURE_DIRECTION), actor=lead
    )

    assert approved.status is ApprovalStatus.APPROVED
    assert approved.approved_by == lead
    with pytest.raises(ApprovalNotAuthorized):
        await manager.approve_artifact(artifact(ApprovedArtifactKind.UI_CONCEPT), actor=lead)


async def test_supersede_bumps_version_and_marks_previous(
    manager: DefaultMemoryManager, db: Database, repo: Path
) -> None:
    first = await manager.approve_artifact(artifact(), actor=USER)
    (repo / "GDD" / "loop.md").write_bytes(b"# Core loop v2\n")

    second = await manager.approve_artifact(artifact(supersedes=first.id), actor=USER)

    repository = ApprovedArtifactRepository(db)
    assert (second.id, second.version, second.supersedes) == ("APR-0002", 2, "APR-0001")
    previous = await repository.get("APR-0001")
    assert previous.status is ApprovalStatus.SUPERSEDED
    assert [a.id for a in await repository.list(status=ApprovalStatus.APPROVED)] == ["APR-0002"]
    assert [a.id for a in await repository.list(scope="project")] == ["APR-0001", "APR-0002"]
    with pytest.raises(ConfigError, match="APR-0009"):
        await manager.approve_artifact(artifact(supersedes="APR-0009"), actor=USER)


async def test_hash_payload_missing_file_raises(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"a")

    with pytest.raises(ConfigError, match=r"b\.txt"):
        hash_payload(tmp_path, ["a.txt", "b.txt"])
    assert hash_payload(tmp_path, ["a.txt"]) == hash_payload(tmp_path, ["a.txt"])


async def test_verify_detects_payload_drift(
    manager: DefaultMemoryManager,
    db: Database,
    ledger: DefaultLedgerManager,
    stale: list[HookContext],
    repo: Path,
) -> None:
    approved = await manager.approve_artifact(artifact(), actor=USER)
    other = await manager.approve_artifact(artifact(title="Other"), actor=USER)
    (repo / ".ai" / APPROVED_DIR / approved.id / "loop.md").write_bytes(b"# tampered\n")
    (repo / ".ai" / APPROVED_DIR / other.id / "concept.png").unlink()

    drifted = await manager.verify_approved_artifacts()

    assert drifted == [approved.id, other.id]
    row = await MemoryIndexRepository(db).by_doc_id(approved.id)
    assert row is not None
    assert row.freshness_status is FreshnessStatus.INVALID
    assert [(c.payload["doc_id"], c.payload["status"], c.payload["reason"]) for c in stale] == [
        (approved.id, "INVALID", "approved artifact drift"),
        (other.id, "INVALID", "approved artifact drift"),
    ]
    events = await ledger.query(kinds=[LedgerEventKind.CONTEXT_FRESHNESS])
    assert [e.payload["doc_id"] for e in events] == [approved.id, other.id]
    stored = await ApprovedArtifactRepository(db).get(approved.id)
    assert stored.status is ApprovalStatus.APPROVED  # re-approval restores, not verify


async def test_verify_clean_returns_empty(
    manager: DefaultMemoryManager, stale: list[HookContext]
) -> None:
    await manager.approve_artifact(artifact(), actor=USER)

    assert await manager.verify_approved_artifacts() == []
    assert stale == []


async def test_approve_rejects_bad_payloads(manager: DefaultMemoryManager, repo: Path) -> None:
    (repo / "other").mkdir()
    (repo / "other" / "loop.md").write_bytes(b"clash")

    with pytest.raises(ConfigError, match="missing"):
        await manager.approve_artifact(artifact(payload_paths=["GDD/nope.png"]), actor=USER)
    with pytest.raises(ConfigError, match="same name"):
        await manager.approve_artifact(
            artifact(payload_paths=["GDD/loop.md", "other/loop.md"]), actor=USER
        )
    with pytest.raises(ConfigError, match="payload"):
        await manager.approve_artifact(artifact(payload_paths=[]), actor=USER)


async def test_approve_needs_git_and_unknown_artifact_raises(
    db: Database, ledger: DefaultLedgerManager, fake_clock: FakeClock, repo: Path
) -> None:
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)
    bare = DefaultMemoryManager(
        repo / ".ai",
        MemoryIndexRepository(db),
        ledger,
        hooks,
        IdSequenceStore(db),
        fake_clock,
        project_key="DEMO",
    )

    with pytest.raises(ConfigError, match="git"):
        await bare.approve_artifact(artifact(), actor=USER)
    with pytest.raises(ConfigError, match="APR-0404"):
        await ApprovedArtifactRepository(db).get("APR-0404")
    senior = Actor(role=AgentRole.SENIOR_DEV)
    with pytest.raises(ApprovalNotAuthorized):  # no may_approve lookup: only USER approves
        await bare.approve_artifact(artifact(), actor=senior)


async def test_supersede_without_document_and_failed_copy(
    manager: DefaultMemoryManager, db: Database, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = await manager.approve_artifact(artifact(), actor=USER)
    (repo / ".ai" / APPROVED_DIR / f"{first.id}.md").unlink()

    second = await manager.approve_artifact(artifact(supersedes=first.id), actor=USER)

    assert (await ApprovedArtifactRepository(db).get(first.id)).status is (
        ApprovalStatus.SUPERSEDED
    )

    def refuse(self: Path, target: Path) -> Path:
        del self, target
        msg = "disk full"
        raise OSError(msg)

    monkeypatch.setattr(Path, "replace", refuse)
    with pytest.raises(OSError, match="disk full"):
        await manager.approve_artifact(artifact(supersedes=second.id), actor=USER)
    leftovers = list((repo / ".ai" / APPROVED_DIR).rglob("*.tmp"))
    assert leftovers == []
