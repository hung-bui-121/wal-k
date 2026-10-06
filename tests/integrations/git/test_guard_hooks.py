from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from walk.common.errors import ConfigError
from walk.integrations import AsyncioSubprocessRunner, GitCliProvider
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
