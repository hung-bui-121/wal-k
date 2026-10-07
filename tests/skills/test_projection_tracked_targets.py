import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

import walk.skills
from tests.fakes.fake_clock import FakeClock
from walk.cli.composition import tracked_projection_guard
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.integrations import AsyncioSubprocessRunner, GitCliProvider
from walk.model_router.adapters.codex.projector import CodexSkillProjector
from walk.persistence import Database, IdempotencyStore, IdSequenceStore
from walk.skills import DefaultSkillRegistry
from walk.telemetry import DefaultLedgerManager, LedgerRepository

AT = datetime(2026, 1, 1, tzinfo=UTC)
BUILTIN = Path(walk.skills.__file__).resolve().parent / "builtin"
REPO_TEXT = b"# Game repository instructions\n\nUse Unity 6.\n"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def git(db: Database, tmp_game_repo: Path, fake_clock: FakeClock) -> GitCliProvider:
    ledger = DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), fake_clock)
    return GitCliProvider(
        tmp_game_repo,
        AsyncioSubprocessRunner(),
        ledger,
        IdempotencyStore(db, fake_clock),
        fake_clock,
        project_key="DEMO",
    )


@pytest.fixture
def registry(db: Database, tmp_game_repo: Path, git: GitCliProvider) -> DefaultSkillRegistry:
    (tmp_game_repo / "AGENTS.md").write_bytes(REPO_TEXT)
    _git(tmp_game_repo, "add", "AGENTS.md")
    _git(tmp_game_repo, "commit", "-q", "-m", "docs: agents")

    async def exclude_path(worktree: str) -> str:
        return await git.git_path(worktree, "info/exclude")

    return DefaultSkillRegistry(
        BUILTIN,
        None,
        {AgentRole.SENIOR_DEV: ["walk-output-contract"]},
        db=db,
        ai_root=tmp_game_repo / ".ai",
        exclude_path=exclude_path,
        hide_tracked=tracked_projection_guard(tmp_game_repo, git),
    )


async def test_tracked_agents_md_is_hidden_in_run_worktree(
    registry: DefaultSkillRegistry, git: GitCliProvider, tmp_game_repo: Path
) -> None:
    await git.ensure_branch("feat/x", "main", idempotency_key="git.branch:x")
    run_worktree = tmp_game_repo / ".walk" / "worktrees" / "RUN-01J0000000000000000000000A"
    worktree = await git.add_worktree(str(run_worktree), "feat/x")

    await registry.project_all(
        [CodexSkillProjector(clock=FakeClock(AT))], worktree, registry.load()
    )

    text = (Path(worktree) / "AGENTS.md").read_bytes()
    assert REPO_TEXT.rstrip(b"\n") in text
    assert b"walk-output-contract" in text
    assert await git.status(worktree) == []
    committed = await git.commit_all(
        worktree, "wip", trailer_work_item="STORY-0001", idempotency_key="k-wip"
    )
    assert committed is None
    assert (tmp_game_repo / "AGENTS.md").read_bytes() == REPO_TEXT  # main checkout untouched


async def test_projection_refuses_tracked_target_outside_run_worktrees(
    registry: DefaultSkillRegistry, tmp_game_repo: Path
) -> None:
    with pytest.raises(ConfigError, match="run worktrees only"):
        await registry.project_all(
            [CodexSkillProjector(clock=FakeClock(AT))], str(tmp_game_repo), registry.load()
        )

    assert (tmp_game_repo / "AGENTS.md").read_bytes() == REPO_TEXT
