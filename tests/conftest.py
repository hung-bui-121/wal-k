"""Shared fixtures."""

import subprocess
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from walk.persistence import Database, MigrationRunner, UnitOfWork
from walk.workflow import Project, ProjectRepository


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """A temporary git repository on branch ``main`` with one initial commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "walk-tests")
    _git(repo, "config", "user.email", "walk-tests@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "config", "core.hooksPath", str(repo / ".git" / "hooks"))
    (repo / "README.md").write_text("test repo\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "chore: initial commit")
    return repo


@pytest.fixture
def tmp_game_repo(tmp_path: Path) -> Path:
    """A temporary game repository on ``main``: one commit with README.md and .gitignore.

    ``.gitignore`` holds the kernel's local state (``.walk/``, ``.ai/kernel.db``); hooks are
    pinned to the repository's own hooks folder so global git configuration cannot leak in.
    """
    repo = tmp_path / "game"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "walk-tests")
    _git(repo, "config", "user.email", "walk-tests@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "config", "core.autocrlf", "false")
    _git(repo, "config", "core.hooksPath", str(repo / ".git" / "hooks"))
    (repo / "README.md").write_bytes(b"game repo\n")
    (repo / ".gitignore").write_bytes(b".walk/\n.ai/kernel.db\n")
    _git(repo, "add", "README.md", ".gitignore")
    _git(repo, "commit", "-m", "chore: initial commit")
    return repo


@pytest.fixture
def fake_clock() -> FakeClock:
    """A clock fixed at 2026-01-01T00:00:00Z."""
    return FakeClock(datetime(2026, 1, 1, tzinfo=UTC))


@pytest.fixture
def sequential_ids() -> SequentialIdFactory:
    """Deterministic ID factory."""
    return SequentialIdFactory()


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    """A project database at ``<tmp>/.ai/kernel.db`` migrated to the latest schema."""
    database = Database(tmp_path / ".ai" / "kernel.db")
    MigrationRunner(database, "project").apply_pending()
    yield database
    database.close()


@pytest.fixture
async def project(db: Database) -> Project:
    """The persisted project ``DEMO`` (one project per database)."""
    demo = Project(
        key="DEMO",
        name="Demo",
        repo_path=str(db.path.parent.parent),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    async with UnitOfWork(db) as uow:
        await ProjectRepository(db).insert(demo, uow)
    return demo
