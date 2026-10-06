"""Shared fixtures."""

import subprocess
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from walk.persistence import Database, MigrationRunner


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
