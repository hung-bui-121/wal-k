import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_subprocess import FakeSubprocessRunner
from walk.common.errors import ConfigError, PermissionDenied
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

    await git.install_guard_hooks(str(tmp_game_repo), ["main"])

    # E02-S14: the foreign hook is kept as pre-commit.local and chained by the guard hook.
    assert (hooks / "pre-commit.local").read_bytes() == FOREIGN
    assert GUARD_HOOK_MARKER.encode() in (hooks / "pre-commit").read_bytes()
    assert b"pre-commit.local" in (hooks / "pre-commit").read_bytes()
    assert (hooks / "pre-push").is_file()


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
    assert script.index('walk_in_run_worktree || walk_chain "$@"') < script.index("symbolic-ref")


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


# ---- E02-S14 ---------------------------------------------------------------------------


def _hooks_dir(repo: Path) -> Path:
    return repo / ".git" / "hooks"


async def test_install_guard_hooks_idempotent(git: GitCliProvider, tmp_game_repo: Path) -> None:
    await git.install_guard_hooks(str(tmp_game_repo), ["main", "release/*"])
    hooks = _hooks_dir(tmp_game_repo)
    first = {kind: (hooks / kind).stat().st_mtime_ns for kind in ("pre-commit", "pre-push")}

    await git.install_guard_hooks(str(tmp_game_repo), ["main", "release/*"])

    for kind in ("pre-commit", "pre-push"):
        script = (hooks / kind).read_bytes()
        assert script.startswith(b"#!/bin/sh\n")
        assert b"main|release/*)" in script
        assert b"\r" not in script
        assert (hooks / kind).stat().st_mtime_ns == first[kind]  # not rewritten
        if os.name != "nt":
            assert os.access(hooks / kind, os.X_OK)


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs sh (Git for Windows ships it)")
async def test_pre_commit_blocks_protected_branch(git: GitCliProvider, tmp_game_repo: Path) -> None:
    runner = AsyncioSubprocessRunner()
    await runner.run(["git", "checkout", "-q", "-b", "dev"], cwd=str(tmp_game_repo))
    run_worktree = tmp_game_repo / ".walk" / "worktrees" / "RUN-01J00000000000000000000000"
    wt = Path(await git.add_worktree(str(run_worktree), "main"))
    await git.install_guard_hooks(str(wt), ["main", "release/*"])
    (wt / "B.txt").write_bytes(b"b\n")
    await runner.run(["git", "add", "B.txt"], cwd=str(wt))

    done = await runner.run(["git", "commit", "-m", "feat: b"], cwd=str(wt))

    assert done.exit_code == 1
    assert "protected branch 'main'" in done.stderr


async def test_push_refuses_protected_branch(tmp_game_repo: Path, db: Database) -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    runner = FakeSubprocessRunner()  # unscripted: any git call would fail the test
    ledger = DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), clock)
    git = GitCliProvider(
        tmp_game_repo, runner, ledger, IdempotencyStore(db, clock), clock, project_key="DEMO"
    )

    with pytest.raises(PermissionDenied, match="protected branch"):
        await git.push(str(tmp_game_repo), "main", protected_branches=["main"])
    with pytest.raises(PermissionDenied):
        await git.push(str(tmp_game_repo), "release/2.0", protected_branches=["release/*"])
    with pytest.raises(ConfigError, match="E03-S01"):
        await git.push(str(tmp_game_repo), "feat/x", protected_branches=["main"])

    assert runner.calls == []


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs sh (Git for Windows ships it)")
async def test_existing_hook_is_chained_not_lost(git: GitCliProvider, tmp_game_repo: Path) -> None:
    hooks = _hooks_dir(tmp_game_repo)
    hooks.mkdir(parents=True, exist_ok=True)
    marker = tmp_game_repo / "local-hook-ran"
    (hooks / "pre-commit").write_bytes(f"#!/bin/sh\ntouch '{marker.as_posix()}'\n".encode())
    (hooks / "pre-commit").chmod(0o755)

    await git.install_guard_hooks(str(tmp_game_repo), ["release/*"])
    (tmp_game_repo / "A.txt").write_bytes(b"a\n")
    committed = await git.commit_all(
        str(tmp_game_repo), "feat: a", trailer_work_item="TASK-0001", idempotency_key="k-a"
    )

    assert committed is not None
    assert GUARD_HOOK_MARKER.encode() in (hooks / "pre-commit").read_bytes()
    assert (hooks / "pre-commit.local").is_file()
    assert marker.is_file()  # the developer's own hook still ran
    (hooks / "pre-push").write_bytes(FOREIGN)
    (hooks / "pre-push.local").write_bytes(FOREIGN)
    with pytest.raises(ConfigError, match="local"):
        await git.install_guard_hooks(str(tmp_game_repo), ["release/*"])
