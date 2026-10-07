import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.cli.conftest import OverridesFactory, migrate
from tests.fakes.fake_subprocess import FakeSubprocessRunner
from tests.integrations.test_preflight import build_manager, script_environment, write_work_provider
from walk.cli.app import app
from walk.cli.composition import KernelSettings, build_kernel, open_database, open_memory
from walk.common.models import Actor
from walk.common.roles import AgentRole
from walk.memory import (
    ApprovalNotAuthorized,
    ApprovalStatus,
    ApprovedArtifact,
    ApprovedArtifactKind,
    FreshnessStatus,
    MemoryIndexRepository,
)

runner = CliRunner()


def _payload(repo: Path) -> Path:
    concept = repo / "GDD" / "a.png"
    concept.parent.mkdir(parents=True, exist_ok=True)
    concept.write_bytes(b"\x89PNG a")
    return concept


def test_artifacts_approve_and_list(kernel_repo: Path) -> None:
    concept = _payload(kernel_repo)

    approved = runner.invoke(
        app,
        [
            "artifacts",
            "approve",
            str(concept),
            "--kind",
            "UI_CONCEPT",
            "--title",
            "X",
            "--scope",
            "FEAT-0001",
            "--repo",
            str(kernel_repo),
        ],
    )
    listed = runner.invoke(app, ["artifacts", "list", "--repo", str(kernel_repo)])
    as_json = runner.invoke(app, ["artifacts", "list", "--json", "--repo", str(kernel_repo)])

    assert approved.exit_code == 0, approved.output
    assert approved.stdout.startswith("APR-0001 approved (sha ")
    assert listed.exit_code == 0, listed.output
    assert "APR-0001" in listed.output
    assert "UI_CONCEPT" in listed.output
    rows = json.loads(as_json.output)
    assert [(r["id"], r["status"], r["scope"]) for r in rows] == [
        ("APR-0001", "APPROVED", "FEAT-0001")
    ]
    assert (kernel_repo / ".ai" / "approved" / "APR-0001" / "a.png").is_file()


def test_artifacts_verify_exit_two_on_drift(kernel_repo: Path) -> None:
    concept = _payload(kernel_repo)
    runner.invoke(
        app,
        [
            "artifacts",
            "approve",
            str(concept.relative_to(kernel_repo)),
            "--kind",
            "GAMEPLAY_CONCEPT",
            "--title",
            "Core loop",
            "--scope",
            "project",
            "--repo",
            str(kernel_repo),
        ],
    )
    clean = runner.invoke(app, ["artifacts", "verify", "--repo", str(kernel_repo)])
    (kernel_repo / ".ai" / "approved" / "APR-0001" / "a.png").write_bytes(b"changed")

    drift = runner.invoke(app, ["artifacts", "verify", "--repo", str(kernel_repo)])

    assert (clean.exit_code, clean.stdout.strip()) == (0, "ok")
    assert drift.exit_code == 2
    assert "APR-0001" in drift.output


def test_artifacts_errors(kernel_repo: Path, tmp_path: Path) -> None:
    concept = _payload(kernel_repo)
    base = ["--title", "X", "--scope", "project", "--repo", str(kernel_repo)]

    bad_kind = runner.invoke(app, ["artifacts", "approve", str(concept), "--kind", "NOPE", *base])
    missing = runner.invoke(
        app, ["artifacts", "approve", "GDD/none.png", "--kind", "UI_CONCEPT", *base]
    )
    unknown = runner.invoke(
        app,
        [
            "artifacts",
            "approve",
            str(concept),
            "--kind",
            "UI_CONCEPT",
            "--supersedes",
            "APR-0042",
            *base,
        ],
    )
    no_db = runner.invoke(app, ["artifacts", "list", "--repo", str(tmp_path / "nowhere")])

    assert bad_kind.exit_code != 0
    assert missing.exit_code == 1
    assert "missing" in missing.output
    assert unknown.exit_code == 1
    assert no_db.exit_code == 1


def _approve(repo: Path) -> None:
    concept = _payload(repo)
    result = runner.invoke(
        app,
        [
            "artifacts",
            "approve",
            str(concept),
            "--kind",
            "GAMEPLAY_CONCEPT",
            "--title",
            "Core loop",
            "--scope",
            "project",
            "--repo",
            str(repo),
        ],
    )
    assert result.exit_code == 0, result.output


def test_doctor_prints_approved_drift_without_changing_exit_code(
    kernel_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_work_provider(kernel_repo, "local")
    manager = build_manager(kernel_repo, script_environment(FakeSubprocessRunner()))
    monkeypatch.setattr("walk.cli.cmd_doctor.open_integrations", lambda _repo: manager)
    _approve(kernel_repo)

    clean = runner.invoke(app, ["doctor", "--repo", str(kernel_repo)])
    (kernel_repo / ".ai" / "approved" / "APR-0001" / "a.png").unlink()
    drift = runner.invoke(app, ["doctor", "--repo", str(kernel_repo)])
    write_work_provider(tmp_path, "local")
    no_db = runner.invoke(app, ["doctor", "--repo", str(tmp_path)])

    assert clean.exit_code == 0, clean.output
    assert "approved: ok" in clean.stdout
    assert drift.exit_code == 0, drift.output
    assert "approved: drift APR-0001" in drift.stdout
    assert "approved: no database" in no_db.stdout


def test_kernel_start_marks_approved_drift_invalid(
    kernel_repo: Path, fake_overrides: OverridesFactory
) -> None:
    _approve(kernel_repo)
    (kernel_repo / ".ai" / "approved" / "APR-0001" / "a.png").write_bytes(b"tampered")

    async def start() -> None:
        handle = build_kernel(KernelSettings(repo_path=kernel_repo), overrides=fake_overrides())
        try:
            assert await handle.orchestrator.run_once() == 0
            row = await MemoryIndexRepository(handle.db).by_doc_id("APR-0001")
            assert row is not None
            assert row.freshness_status is FreshnessStatus.INVALID
        finally:
            await handle.aclose()

    asyncio.run(start())


def test_artifacts_reject_bad_ids_and_projectless_databases(
    kernel_repo: Path, tmp_path: Path
) -> None:
    concept = _payload(kernel_repo)
    malformed = runner.invoke(
        app,
        [
            "artifacts",
            "approve",
            str(concept),
            "--kind",
            "UI_CONCEPT",
            "--title",
            "X",
            "--scope",
            "project",
            "--supersedes",
            "nope",
            "--repo",
            str(kernel_repo),
        ],
    )
    empty = tmp_path / "empty"
    empty.mkdir()
    migrate(empty, project=False)
    no_project = runner.invoke(app, ["artifacts", "verify", "--repo", str(empty)])

    assert malformed.exit_code == 1
    assert no_project.exit_code == 1
    assert "exactly one project" in no_project.output


def test_constitution_authority_and_broken_database_in_doctor(
    kernel_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _payload(kernel_repo)
    db = open_database(kernel_repo)
    memory = open_memory(db, kernel_repo, project_key="DEMO")

    def draft(kind: ApprovedArtifactKind) -> ApprovedArtifact:
        return ApprovedArtifact(
            id="APR-0000",
            kind=kind,
            title="Arch",
            status=ApprovalStatus.DRAFT,
            scope="project",
            version=1,
            approved_by=Actor(role=AgentRole.LEAD_DEV),
            approved_at=datetime(2026, 1, 1, tzinfo=UTC),
            related_requirements=[],
            payload_paths=["GDD/a.png"],
            content_sha256="",
        )

    async def approve() -> list[str]:
        lead = await memory.approve_artifact(
            draft(ApprovedArtifactKind.ARCHITECTURE_DIRECTION), actor=Actor(role=AgentRole.LEAD_DEV)
        )
        with pytest.raises(ApprovalNotAuthorized):
            await memory.approve_artifact(
                draft(ApprovedArtifactKind.UI_CONCEPT), actor=Actor(role=AgentRole.SCRUM_MASTER)
            )
        return [lead.id]

    try:
        assert asyncio.run(approve()) == ["APR-0001"]
    finally:
        db.close()
    broken = tmp_path / "broken"
    (broken / ".ai").mkdir(parents=True)
    (broken / ".ai" / "kernel.db").write_bytes(b"not a database at all, just bytes")
    write_work_provider(broken, "local")
    manager = build_manager(broken, script_environment(FakeSubprocessRunner()))
    monkeypatch.setattr("walk.cli.cmd_doctor.open_integrations", lambda _repo: manager)

    report = runner.invoke(app, ["doctor", "--repo", str(broken)])

    assert report.exit_code == 0, report.output
    assert "approved: error:" in report.stdout
