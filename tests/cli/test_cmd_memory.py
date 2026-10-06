import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from walk.cli.app import app
from walk.common.models import Actor
from walk.common.roles import AgentRole
from walk.memory import MemoryDocType, render_document, skeleton_for
from walk.persistence import Database, MigrationRunner, UnitOfWork
from walk.workflow import Project, ProjectRepository

runner = CliRunner()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository with project DEMO and one feature document on disk."""
    db = Database(tmp_path / ".ai" / "kernel.db")
    MigrationRunner(db, "project").apply_pending()

    async def seed() -> None:
        async with UnitOfWork(db) as uow:
            await ProjectRepository(db).insert(
                Project(key="DEMO", name="Demo", repo_path=str(tmp_path)), uow
            )

    asyncio.run(seed())
    db.close()
    doc = skeleton_for(
        MemoryDocType.FEATURE,
        "FEAT-0001",
        "Movement",
        Actor(role=AgentRole.KERNEL),
        datetime(2026, 1, 1, tzinfo=UTC),
    )
    (tmp_path / ".ai" / "features").mkdir()
    (tmp_path / ".ai" / "features" / "FEAT-0001.md").write_text(render_document(doc), "utf-8")
    return tmp_path


def test_memory_index_cli(repo: Path) -> None:
    result = runner.invoke(app, ["memory", "index", "--repo", str(repo)])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "indexed 1 documents"
    as_json = runner.invoke(app, ["--json", "--repo", str(repo), "memory", "index"])
    assert as_json.exit_code == 0, as_json.output
    assert json.loads(as_json.output) == {"indexed": 1}


def test_memory_index_cli_needs_a_database_with_a_project(tmp_path: Path) -> None:
    missing = runner.invoke(app, ["memory", "index", "--repo", str(tmp_path)])
    assert missing.exit_code == 1
    assert "database does not exist" in missing.output
    db = Database(tmp_path / ".ai" / "kernel.db")
    MigrationRunner(db, "project").apply_pending()
    db.close()
    empty = runner.invoke(app, ["memory", "index", "--repo", str(tmp_path)])
    assert empty.exit_code == 1
    assert "exactly one project" in empty.output
