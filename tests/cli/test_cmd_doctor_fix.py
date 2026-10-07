import asyncio
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.fakes.fake_subprocess import FakeSubprocessRunner
from tests.integrations.test_preflight import build_manager, script_environment, write_work_provider
from walk.cli import cmd_doctor
from walk.cli.app import app
from walk.cli.cmd_doctor import DoctorReport
from walk.common.errors import ConfigError
from walk.integrations import SubprocessRunner
from walk.memory import MemoryDocType, MemoryIndexRepository, MemoryIndexRow
from walk.persistence import Database, UnitOfWork

runner = CliRunner()
RUN_WORKTREE = Path(".walk") / "worktrees" / "RUN-01J0000000000000000000000A"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def doctor_repo(kernel_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`kernel_repo` with a scripted preflight and a clean import-linter."""
    write_work_provider(kernel_repo, "local")
    manager = build_manager(kernel_repo, script_environment(FakeSubprocessRunner()))
    monkeypatch.setattr(cmd_doctor, "open_integrations", lambda _repo: manager)

    async def clean(runner: SubprocessRunner, repo_root: Path) -> list[str]:
        del runner, repo_root
        return []

    monkeypatch.setattr(cmd_doctor, "run_import_linter", clean)
    return kernel_repo


def _doctor(repo: Path, *flags: str) -> tuple[int, DoctorReport]:
    result = runner.invoke(app, ["doctor", *flags, "--json", "--repo", str(repo)])
    return result.exit_code, DoctorReport.model_validate_json(result.stdout)


def test_fix_installs_guard_hooks(doctor_repo: Path) -> None:
    _git(doctor_repo, "worktree", "add", "-q", "-b", "feat/x", str(doctor_repo / RUN_WORKTREE))
    hooks = doctor_repo / ".git" / "hooks"
    for kind in ("pre-commit", "pre-push"):
        (hooks / kind).unlink(missing_ok=True)

    code, report = _doctor(doctor_repo, "--fix")

    assert code == 0
    assert (hooks / "pre-commit").is_file()
    assert (hooks / "pre-push").is_file()
    assert any(f.startswith("guard hooks: ") and "RUN-01J" in f for f in report.fixes_applied)
    assert any(f == f"guard hooks: {doctor_repo}" for f in report.fixes_applied)


def test_fix_regenerates_skill_projections(doctor_repo: Path) -> None:
    before = runner.invoke(app, ["doctor", "--repo", str(doctor_repo)])
    assert "missing" in before.stdout

    code, report = _doctor(doctor_repo, "--fix")

    assert code == 0
    assert report.skills.ok
    assert {f for f in report.fixes_applied if f.startswith("skills: ")} == {
        "skills: regenerated claude",
        "skills: regenerated codex",
    }
    assert (doctor_repo / ".walk" / "projections" / "codex" / "AGENTS.md").is_file()


def test_fix_rebuilds_memory_index(doctor_repo: Path) -> None:
    db = Database(doctor_repo / ".ai" / "kernel.db")
    stale = MemoryIndexRow(
        path="features/FEAT-0404.md",
        doc_id="FEAT-0404",
        type=MemoryDocType.FEATURE,
        title="Gone",
        status=None,
        version=1,
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        freshness_commit=None,
        freshness_status=None,
        freshness_checked_at=None,
        raw_sha256="0" * 64,
        relevant_files=[],
        related={},
    )

    async def insert() -> None:
        async with UnitOfWork(db) as uow:
            await MemoryIndexRepository(db).upsert(stale, uow)

    try:
        asyncio.run(insert())
        code, report = _doctor(doctor_repo, "--fix")
        remaining = asyncio.run(MemoryIndexRepository(db).by_doc_id("FEAT-0404"))
    finally:
        db.close()

    assert code == 0
    assert remaining is None
    assert any(f.startswith("memory index: ") for f in report.fixes_applied)
    assert "manifest: refreshed" in report.fixes_applied


def test_strict_clean_exit_zero(doctor_repo: Path) -> None:
    _doctor(doctor_repo, "--fix")

    code, report = _doctor(doctor_repo, "--strict")
    text = runner.invoke(app, ["doctor", "--strict", "--repo", str(doctor_repo)])

    assert code == 0
    assert report.lints == []
    assert report.version_pins_ok
    assert report.approved_drift == []
    assert report.exit_code == 0
    assert "lints: none" in text.stdout
    assert "versions: ok" in text.stdout


def test_strict_fails_on_pin_mismatch(doctor_repo: Path) -> None:
    _doctor(doctor_repo, "--fix")
    pins = doctor_repo / ".ai" / "project" / "kernel-versions.yaml"
    pins.parent.mkdir(parents=True, exist_ok=True)
    pins.write_bytes(b"pins:\n  WORKFLOW/story_workflow: '9.9'\n")

    code, report = _doctor(doctor_repo, "--strict")
    lenient, informational = _doctor(doctor_repo)

    assert code == 1
    assert report.exit_code == 1
    assert report.version_pins_ok is False
    assert any("story_workflow" in lint for lint in report.lints)
    assert lenient == 0
    assert informational.version_pins_ok is False
    assert informational.lints == []


def test_doctor_json_report(doctor_repo: Path) -> None:
    result = runner.invoke(app, ["doctor", "--json", "--repo", str(doctor_repo)])

    report = DoctorReport.model_validate_json(result.stdout)
    assert result.exit_code == 0
    assert report.manifest.tools["git"].version == "2.45.0"
    assert report.fixes_applied == []
    assert report.skills.ok is False  # informational drift without --strict
    assert report.exit_code == 0


def test_fix_failures_and_strict_configuration_findings(
    doctor_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def missing_tool(runner: SubprocessRunner, repo_root: Path) -> list[str]:
        del runner, repo_root
        msg = "import-linter not installed"
        raise ConfigError(msg)

    monkeypatch.setattr(cmd_doctor, "run_import_linter", missing_tool)
    (doctor_repo / ".ai" / "agents" / "models.yaml").write_bytes(b"models: [unclosed\n")
    lock = doctor_repo / ".ai" / "agents" / "projections.lock.yaml"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_bytes(b"projections: [broken\n")

    code, report = _doctor(doctor_repo, "--fix", "--strict")
    bare = tmp_path / "bare"
    bare.mkdir()
    write_work_provider(bare, "local")
    fixed_bare = runner.invoke(app, ["doctor", "--fix", "--repo", str(bare)])

    assert code == 1
    assert any(f.startswith("skills failed: ") for f in report.fixes_applied)
    assert "import-linter not installed" in report.lints
    assert any(lint.startswith("configuration: ") for lint in report.lints)
    assert any(lint.startswith("skills: error: ") for lint in report.lints)
    assert fixed_bare.exit_code == 1
    assert "guard hooks failed: no database" in fixed_bare.stdout


def test_invalid_pin_file_is_a_version_problem(doctor_repo: Path) -> None:
    pins = doctor_repo / ".ai" / "project" / "kernel-versions.yaml"
    pins.parent.mkdir(parents=True, exist_ok=True)
    pins.write_bytes(b"pins: [unclosed\n")

    result = runner.invoke(app, ["doctor", "--repo", str(doctor_repo)])

    assert result.exit_code == 0, result.output
    assert "versions: invalid kernel version pins" in result.stdout
