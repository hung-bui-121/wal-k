"""Shared fixtures."""

import subprocess
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from tests.fakes.fake_model_adapter import FakeModelAdapter, FakeScript, fake_descriptor
from walk.agents import AgentOutput, AgentOutputStatus
from walk.common.enums import Effort
from walk.model_router import OUTPUT_RELATIVE_PATH, RunSession
from walk.permissions import PermissionDecision, PermissionEffect, ToolCallRequest
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


def _default_script() -> FakeScript:
    output = AgentOutput(
        status=AgentOutputStatus.COMPLETED, result="done", no_context_change_reason="fake run"
    )
    return FakeScript(tool_calls=3, output=output)


@pytest.fixture
def fake_codex_adapter(fake_clock: FakeClock) -> FakeModelAdapter:
    """Fake adapter ``fake-codex`` serving ``fake-codex/sim``; 3 tool calls, then COMPLETED."""
    descriptor = fake_descriptor("fake-codex/sim", "fake-codex")
    return FakeModelAdapter("fake-codex", [descriptor], _default_script(), fake_clock)


@pytest.fixture
def fake_claude_adapter(fake_clock: FakeClock) -> FakeModelAdapter:
    """Fake adapter ``fake-claude`` serving ``fake-claude/sim``; 3 tool calls, then COMPLETED."""
    descriptor = fake_descriptor("fake-claude/sim", "fake-claude")
    return FakeModelAdapter("fake-claude", [descriptor], _default_script(), fake_clock)


@pytest.fixture
def run_session(tmp_repo: Path) -> RunSession:
    """A `RunSession` on ``tmp_repo`` whose authorizer allows every tool call."""

    async def allow(request: ToolCallRequest) -> PermissionDecision:
        del request
        return PermissionDecision(effect=PermissionEffect.ALLOW, matched_rule=None, reason="test")

    return RunSession(
        run_id="RUN-01J00000000000000000000000",
        worktree_path=str(tmp_repo),
        allowed_tools=[],
        permission_authorizer=allow,
        effort=Effort.MEDIUM,
        model_id="fake-codex/sim",
        max_turns=50,
        timeout_s=600,
        env_allowlist={},
        output_path=str(tmp_repo / OUTPUT_RELATIVE_PATH),
    )
