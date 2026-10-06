import asyncio
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.fakes.fake_clock import FakeClock
from walk.cli import cmd_phase
from walk.cli.app import app
from walk.cli.composition import open_workflow
from walk.common.errors import ConfigError
from walk.persistence import Database, MigrationRunner, UnitOfWork
from walk.workflow import PhaseRepository, PhaseState, Project, ProjectRepository

runner = CliRunner()


@pytest.fixture
def repo(tmp_path: Path, fake_clock: FakeClock) -> Path:
    """A repository whose database holds PHASE-01 (scoped) and PHASE-02."""
    db = Database(tmp_path / ".ai" / "kernel.db")
    MigrationRunner(db, "project").apply_pending()
    workflow = open_workflow(db, clock=fake_clock)

    async def seed() -> None:
        async with UnitOfWork(db) as uow:
            await ProjectRepository(db).insert(
                Project(key="DEMO", name="Demo", repo_path=str(tmp_path)), uow
            )
        await workflow.create_phase("Prototype", 1, scope_epic_ids=["EPIC-001"])
        await workflow.create_phase("Vertical Slice", 2)

    asyncio.run(seed())
    db.close()
    return tmp_path


def _phase_state(repo: Path, phase_id: str) -> PhaseState:
    db = Database(repo / ".ai" / "kernel.db")
    try:
        phase = asyncio.run(PhaseRepository(db).get(phase_id))
    finally:
        db.close()
    assert phase is not None
    return phase.state


def test_phase_list_and_start(repo: Path) -> None:
    listed = runner.invoke(app, ["phase", "list", "--repo", str(repo)])
    assert listed.exit_code == 0, listed.output
    lines = listed.output.strip().splitlines()
    assert lines[0].split() == ["id", "ordinal", "name", "state"]
    assert lines[2].split() == ["PHASE-01", "1", "Prototype", "PLANNED"]
    started = runner.invoke(app, ["phase", "start", "PHASE-01", "--repo", str(repo)])
    assert started.exit_code == 0, started.output
    assert started.output.strip() == "PHASE-01: PLANNED -> ACTIVE"
    assert _phase_state(repo, "PHASE-01") is PhaseState.ACTIVE
    as_json = runner.invoke(app, ["--json", "--repo", str(repo), "phase", "list"])
    assert '"state": "ACTIVE"' in as_json.output


def test_phase_start_guard_rejection_exits_2(repo: Path) -> None:
    result = runner.invoke(app, ["phase", "start", "PHASE-02", "--repo", str(repo)])
    assert result.exit_code == 2
    assert "previous_phase_complete_or_first" in result.output


def test_phase_gate_rejects_unknown_decision(repo: Path) -> None:
    result = runner.invoke(
        app, ["phase", "gate", "PHASE-01", "--decision", "MAYBE", "--repo", str(repo)]
    )
    assert result.exit_code == 1
    assert "MAYBE" in result.output


def test_phase_gate_records_decision_with_feedback_file(repo: Path, tmp_path: Path) -> None:
    db = Database(repo / ".ai" / "kernel.db")
    phases = PhaseRepository(db)

    async def to_gate() -> None:
        phase = await phases.get("PHASE-01")
        assert phase is not None
        async with UnitOfWork(db) as uow:
            await phases.upsert(phase.model_copy(update={"state": PhaseState.USER_GATE}), uow)

    asyncio.run(to_gate())
    db.close()
    rejected = runner.invoke(
        app, ["phase", "gate", "PHASE-01", "--decision", "REWORK", "--repo", str(repo)]
    )
    assert rejected.exit_code == 2
    feedback = tmp_path / "feedback.md"
    feedback.write_text("combat needs weight\n", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "phase",
            "gate",
            "PHASE-01",
            "--decision",
            "rework",
            "--feedback",
            f"@{feedback}",
            "--repo",
            str(repo),
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "PHASE-01: USER_GATE -> REWORK"


def test_phase_commands_fail_without_database(tmp_path: Path) -> None:
    for args in (["phase", "list"], ["phase", "start", "PHASE-01"]):
        assert runner.invoke(app, [*args, "--repo", str(tmp_path)]).exit_code == 1
    missing = runner.invoke(
        app,
        [
            "phase",
            "gate",
            "PHASE-01",
            "--decision",
            "GO",
            "--feedback",
            "@nowhere.md",
            "--repo",
            str(tmp_path),
        ],
    )
    assert missing.exit_code == 1
    assert not (tmp_path / ".ai").exists()


def test_phase_start_unknown_phase_exits_1(repo: Path) -> None:
    result = runner.invoke(app, ["phase", "start", "PHASE-09", "--repo", str(repo)])
    assert result.exit_code == 1


def test_phase_gate_text_feedback_and_json(repo: Path) -> None:
    started = runner.invoke(app, ["phase", "start", "PHASE-01", "--json", "--repo", str(repo)])
    assert started.exit_code == 0, started.output
    assert '"state": "ACTIVE"' in started.output
    stopped = runner.invoke(
        app,
        [
            "phase",
            "gate",
            "PHASE-01",
            "--decision",
            "STOP",
            "--feedback",
            "out of budget",
            "--repo",
            str(repo),
        ],
    )
    assert stopped.exit_code == 1  # decide:* only from USER_GATE: unknown transition
    assert "no transition" in stopped.output


def test_phase_list_reports_wiring_errors(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(db: Database, **_: object) -> object:
        del db
        msg = "invalid transition table phase_workflow.yaml"
        raise ConfigError(msg)

    monkeypatch.setattr(cmd_phase, "open_workflow", broken)
    result = runner.invoke(app, ["phase", "list", "--repo", str(repo)])
    assert result.exit_code == 1
    assert "phase_workflow.yaml" in result.output
