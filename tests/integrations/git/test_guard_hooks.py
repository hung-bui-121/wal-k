from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from walk.common.errors import ConfigError
from walk.integrations import AsyncioSubprocessRunner, GitCliProvider, GitError
from walk.integrations.git.guard_hooks import GUARD_HOOK_MARKER, render_guard_hook
from walk.persistence import Database, IdempotencyStore, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerRepository

FOREIGN = b"#!/bin/sh\necho foreign\n"


@pytest.fixture
def git(tmp_game_repo: Path, db: Database, fake_clock: FakeClock) -> GitCliProvider:
    ledger = DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), fake_clock)
    return GitCliProvider(
        tmp_game_repo,
        AsyncioSubprocessRunner(),
        ledger,
        IdempotencyStore(db, fake_clock),
        fake_clock,
        project_key="DEMO",
    )


async def test_foreign_hook_is_not_overwritten(git: GitCliProvider, tmp_game_repo: Path) -> None:
    hooks = tmp_game_repo / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "pre-commit").write_bytes(FOREIGN)

    with pytest.raises(ConfigError) as info:
        await git.install_guard_hooks(str(tmp_game_repo), ["main"])

    assert (hooks / "pre-commit").read_bytes() == FOREIGN
    assert not (hooks / "pre-push").exists()
    assert info.value.detail["hook"].endswith("pre-commit")


async def test_guard_hooks_only_enforce_inside_run_worktrees(
    git: GitCliProvider, tmp_game_repo: Path
) -> None:
    await git.ensure_branch("release/1.0", "main", idempotency_key="git.branch:release")
    run_worktree = tmp_game_repo / ".walk" / "worktrees" / "RUN-01J00000000000000000000000"
    wt = Path(await git.add_worktree(str(run_worktree), "release/1.0"))
    await git.install_guard_hooks(str(wt), ["main", "release/*"])

    (tmp_game_repo / "C.txt").write_bytes(b"c\n")
    on_main = await git.commit_all(
        str(tmp_game_repo), "feat: c", trailer_work_item="TASK-0001", idempotency_key="k-main"
    )
    (wt / "B.txt").write_bytes(b"b\n")
    with pytest.raises(GitError) as refused:
        await git.commit_all(
            str(wt), "feat: b", trailer_work_item="TASK-0001", idempotency_key="k-run"
        )

    assert on_main is not None  # the developer's own checkout is not guarded
    assert "protected" in refused.value.detail["stderr_tail"]


def test_render_guard_hook_scopes_to_run_worktrees() -> None:
    script = render_guard_hook("pre-commit", ["main"])

    assert "rev-parse --show-toplevel" in script
    assert "--git-common-dir" in script
    assert "/.walk/worktrees/" in script
    assert script.index("walk_in_run_worktree || exit 0") < script.index("symbolic-ref")


def test_render_guard_hook_contents() -> None:
    script = render_guard_hook("pre-push", ["release/*"])

    assert script.startswith("#!/bin/sh\n")
    assert GUARD_HOOK_MARKER in script
    assert "release/*)" in script
    assert "refs/heads/" in script
    assert "\r" not in script


def test_render_guard_hook_pre_commit_checks_current_branch() -> None:
    script = render_guard_hook("pre-commit", ["main", "release/*"])

    assert "main|release/*)" in script
    assert "symbolic-ref" in script


def test_render_guard_hook_without_protected_branches_allows_all() -> None:
    script = render_guard_hook("pre-commit", [])

    assert GUARD_HOOK_MARKER in script
    assert "case" not in script


@pytest.mark.parametrize("glob", ["", "main branch", "a|b", "$(rm)", "x'y", "-"])
def test_render_guard_hook_rejects_unsafe_globs(glob: str) -> None:
    with pytest.raises(ConfigError, match="protected branch"):
        render_guard_hook("pre-commit", [glob])


def test_render_guard_hook_rejects_unknown_kind() -> None:
    with pytest.raises(ConfigError, match="hook kind"):
        render_guard_hook("post-commit", ["main"])  # type: ignore[arg-type]  # invalid on purpose
