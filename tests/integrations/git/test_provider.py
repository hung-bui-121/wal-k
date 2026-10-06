import re
import subprocess
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_subprocess import FakeSubprocessRunner
from walk.common.errors import ConfigError
from walk.integrations import (
    FORBIDDEN_COMMIT_PATHSPECS,
    WORK_ITEM_TRAILER,
    AsyncioSubprocessRunner,
    CommitInfo,
    GitCliProvider,
    GitError,
    GitProvider,
    PullRequestRef,
)
from walk.persistence import Database, IdempotencyStore, IdSequenceStore, UnitOfWork
from walk.telemetry import DefaultLedgerManager, LedgerEventKind, LedgerRepository

KEY = "git.commit:RUN-01J00000000000000000000000:1"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return done.stdout.strip()


@pytest.fixture
def ledger(db: Database, fake_clock: FakeClock) -> DefaultLedgerManager:
    return DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), fake_clock)


@pytest.fixture
def idempotency(db: Database, fake_clock: FakeClock) -> IdempotencyStore:
    return IdempotencyStore(db, fake_clock)


@pytest.fixture
def git(
    tmp_game_repo: Path,
    ledger: DefaultLedgerManager,
    idempotency: IdempotencyStore,
    fake_clock: FakeClock,
) -> GitCliProvider:
    return GitCliProvider(
        tmp_game_repo,
        AsyncioSubprocessRunner(),
        ledger,
        idempotency,
        fake_clock,
        project_key="DEMO",
    )


async def _worktree(git: GitCliProvider, repo: Path, branch: str, run: str = "RUN1") -> Path:
    await git.ensure_branch(branch, "main", idempotency_key=f"git.branch:{branch}")
    return Path(await git.add_worktree(str(repo / ".walk" / "worktrees" / run), branch))


async def test_head_and_current_branch(git: GitCliProvider, tmp_game_repo: Path) -> None:
    protocol: GitProvider = git

    head = await protocol.head(str(tmp_game_repo))

    assert re.fullmatch(r"[0-9a-f]{40}", head)
    assert await protocol.current_branch(str(tmp_game_repo)) == "main"
    assert git.provider == "git-cli"


async def test_ensure_branch_is_idempotent(
    git: GitCliProvider, tmp_game_repo: Path, idempotency: IdempotencyStore
) -> None:
    key = "git.branch:STORY-0001"

    first = await git.ensure_branch("feat/STORY-0001-x", "main", idempotency_key=key)
    second = await git.ensure_branch("feat/STORY-0001-x", "main", idempotency_key=key)

    assert first == second == "feat/STORY-0001-x"
    branches = _git(tmp_game_repo, "branch", "--list", "feat/STORY-0001-x").splitlines()
    assert len(branches) == 1
    record = await idempotency.get(key)
    assert record is not None
    assert record.operation == "git.branch"
    assert record.result_ref == "feat/STORY-0001-x"


async def test_ensure_branch_existing_branch_is_noop(
    git: GitCliProvider, tmp_game_repo: Path
) -> None:
    _git(tmp_game_repo, "branch", "feat/old")
    old_sha = _git(tmp_game_repo, "rev-parse", "feat/old")
    (tmp_game_repo / "B.txt").write_bytes(b"b\n")
    _git(tmp_game_repo, "add", "B.txt")
    _git(tmp_game_repo, "commit", "-m", "chore: second")

    name = await git.ensure_branch("feat/old", "main", idempotency_key="git.branch:STORY-0002")

    assert name == "feat/old"
    assert _git(tmp_game_repo, "rev-parse", "feat/old") == old_sha


async def test_worktree_add_and_remove(git: GitCliProvider, tmp_game_repo: Path) -> None:
    await git.ensure_branch("feat/STORY-0001-x", "main", idempotency_key="git.branch:STORY-0001")
    target = tmp_game_repo / ".walk" / "worktrees" / "RUN1"

    added = await git.add_worktree(str(target), "feat/STORY-0001-x")
    again = await git.add_worktree(str(target), "feat/STORY-0001-x")

    assert Path(added) == target.resolve()
    assert again == added
    assert Path(added).is_absolute()
    assert await git.current_branch(added) == "feat/STORY-0001-x"

    await git.remove_worktree(added)

    assert not target.exists()
    listed = _git(tmp_game_repo, "worktree", "list", "--porcelain")
    assert "RUN1" not in listed


async def test_remove_worktree_force_discards_dirty_tree(
    git: GitCliProvider, tmp_game_repo: Path
) -> None:
    wt = await _worktree(git, tmp_game_repo, "feat/dirty")
    (wt / "README.md").write_bytes(b"changed\n")

    with pytest.raises(GitError) as info:
        await git.remove_worktree(str(wt))
    await git.remove_worktree(str(wt), force=True)

    assert info.value.detail["exit_code"] != 0
    assert "worktree" in info.value.detail["argv"]
    assert not wt.exists()


async def test_commit_all_excludes_forbidden_and_adds_trailer(
    git: GitCliProvider, tmp_game_repo: Path, ledger: DefaultLedgerManager
) -> None:
    wt = await _worktree(git, tmp_game_repo, "feat/STORY-0001-x")
    (wt / "src").mkdir()
    (wt / "src" / "A.cs").write_bytes(b"class A {}\n")
    (wt / ".walk").mkdir()
    (wt / ".walk" / "x.json").write_bytes(b"{}\n")
    (wt / "secrets.env").write_bytes(b"TOKEN=1\n")

    info = await git.commit_all(
        str(wt),
        "wip(STORY-0001): checkpoint 1",
        trailer_work_item="STORY-0001",
        idempotency_key=KEY,
    )

    assert info is not None
    assert info.files == ["src/A.cs"]
    assert info.sha == _git(wt, "rev-parse", "HEAD")
    assert f"{WORK_ITEM_TRAILER}: STORY-0001" in info.message
    assert _git(wt, "show", "--name-only", "--format=", "HEAD").splitlines() == ["src/A.cs"]
    trailers = _git(wt, "log", "-1", "--format=%(trailers:key=Walk-Work-Item,valueonly)")
    assert trailers == "STORY-0001"
    assert (wt / "secrets.env").exists()
    events = await ledger.query(kinds=[LedgerEventKind.COMMIT])
    assert len(events) == 1
    assert events[0].work_item_id == "STORY-0001"
    assert events[0].payload == {
        "sha": info.sha,
        "branch": "feat/STORY-0001-x",
        "files_count": 1,
        "work_item_id": "STORY-0001",
    }
    assert ":(exclude)**/*.env" in FORBIDDEN_COMMIT_PATHSPECS


async def test_commit_all_clean_returns_none(
    git: GitCliProvider,
    tmp_game_repo: Path,
    ledger: DefaultLedgerManager,
    idempotency: IdempotencyStore,
) -> None:
    head = _git(tmp_game_repo, "rev-parse", "HEAD")

    info = await git.commit_all(
        str(tmp_game_repo), "wip", trailer_work_item="STORY-0001", idempotency_key=KEY
    )

    assert info is None
    assert await ledger.query(kinds=[LedgerEventKind.COMMIT]) == []
    assert not await idempotency.has(KEY)
    assert _git(tmp_game_repo, "rev-parse", "HEAD") == head


async def test_commit_all_replays_idempotency_key(
    git: GitCliProvider, tmp_game_repo: Path, ledger: DefaultLedgerManager
) -> None:
    wt = await _worktree(git, tmp_game_repo, "feat/replay")
    (wt / "A.txt").write_bytes(b"a\n")
    first = await git.commit_all(
        str(wt), "wip 1", trailer_work_item="TASK-0001", idempotency_key=KEY
    )
    head = _git(wt, "rev-parse", "HEAD")
    (wt / "B.txt").write_bytes(b"b\n")

    second = await git.commit_all(
        str(wt), "wip 2", trailer_work_item="TASK-0001", idempotency_key=KEY
    )

    assert second == first
    assert isinstance(second, CommitInfo)
    assert _git(wt, "rev-parse", "HEAD") == head
    assert len(await ledger.query(kinds=[LedgerEventKind.COMMIT])) == 1


async def test_commit_all_replay_without_result_raises(
    git: GitCliProvider, db: Database, idempotency: IdempotencyStore, tmp_game_repo: Path
) -> None:
    async with UnitOfWork(db) as uow:
        await idempotency.put(KEY, "git.commit", None, uow)

    with pytest.raises(ConfigError, match="no result"):
        await git.commit_all(
            str(tmp_game_repo), "wip", trailer_work_item="TASK-0001", idempotency_key=KEY
        )


async def test_status_and_diff_names_include_untracked(
    git: GitCliProvider, tmp_game_repo: Path
) -> None:
    (tmp_game_repo / "README.md").write_bytes(b"changed\n")
    (tmp_game_repo / "docs").mkdir()
    (tmp_game_repo / "docs" / "new file.md").write_bytes(b"new\n")
    path = str(tmp_game_repo)

    status = await git.status(path)
    names = await git.diff_names(path)
    names_from_base = await git.diff_names(path, _git(tmp_game_repo, "rev-parse", "HEAD"))

    assert sorted(status) == ["README.md", "docs/new file.md"]
    assert names == ["README.md", "docs/new file.md"]
    assert names_from_base == names


async def test_status_reports_renamed_target(git: GitCliProvider, tmp_game_repo: Path) -> None:
    _git(tmp_game_repo, "mv", "README.md", "READ.md")

    assert await git.status(str(tmp_game_repo)) == ["READ.md"]


async def test_ancestry_and_changed_between(git: GitCliProvider, tmp_game_repo: Path) -> None:
    path = str(tmp_game_repo)
    a = await git.head(path)
    (tmp_game_repo / "src").mkdir()
    (tmp_game_repo / "src" / "A.cs").write_bytes(b"a\n")
    (tmp_game_repo / "README.md").write_bytes(b"changed\n")
    _git(tmp_game_repo, "add", "-A")
    _git(tmp_game_repo, "commit", "-m", "feat: b")
    b = await git.head(path)

    assert await git.is_ancestor(a, b, path) is True
    assert await git.is_ancestor(b, a, path) is False
    assert await git.changed_between(a, b, path, paths=["src/"]) == ["src/A.cs"]
    assert await git.changed_between(a, b, path) == ["README.md", "src/A.cs"]
    assert await git.merge_base(a, b, path) == a
    with pytest.raises(GitError):
        await git.is_ancestor(a, "0" * 40, path)


async def test_guard_hooks_block_protected_branches(
    git: GitCliProvider, tmp_game_repo: Path
) -> None:
    wt = await _worktree(git, tmp_game_repo, "feat/x")

    await git.install_guard_hooks(str(wt), ["main", "release/*"])

    (wt / "A.txt").write_bytes(b"a\n")
    ok = await git.commit_all(
        str(wt), "feat: a", trailer_work_item="TASK-0001", idempotency_key="k1"
    )
    assert ok is not None
    _git(wt, "switch", "-c", "release/1.0")
    (wt / "B.txt").write_bytes(b"b\n")
    with pytest.raises(GitError) as release_info:
        await git.commit_all(
            str(wt), "feat: b", trailer_work_item="TASK-0001", idempotency_key="k2"
        )
    (tmp_game_repo / "C.txt").write_bytes(b"c\n")
    with pytest.raises(GitError) as main_info:
        await git.commit_all(
            str(tmp_game_repo), "feat: c", trailer_work_item="TASK-0001", idempotency_key="k3"
        )

    assert "protected" in release_info.value.detail["stderr_tail"]
    assert "protected" in main_info.value.detail["stderr_tail"]


async def test_install_guard_hooks_overwrites_own_hooks(
    git: GitCliProvider, tmp_game_repo: Path
) -> None:
    await git.install_guard_hooks(str(tmp_game_repo), ["release/*"])
    await git.install_guard_hooks(str(tmp_game_repo), ["main"])

    hook = (tmp_game_repo / ".git" / "hooks" / "pre-push").read_bytes()
    assert b"main)" in hook
    assert b"release/*" not in hook
    assert b"\r\n" not in hook


async def test_remote_operations_deferred(git: GitCliProvider, tmp_game_repo: Path) -> None:
    path = str(tmp_game_repo)
    pr = PullRequestRef(number=1, url=None, head="3f9c2e1", base="main")

    with pytest.raises(ConfigError, match="E03-S01"):
        await git.push(path, "feat/x", protected_branches=["main"])
    with pytest.raises(ConfigError, match="E03-S01"):
        await git.open_pr("feat/x", "main", "t", "b", idempotency_key="git.pr:STORY-0001:x")
    with pytest.raises(ConfigError, match="E03-S01"):
        await git.merge(pr, strategy="squash", idempotency_key="git.merge:STORY-0001:1")
    with pytest.raises(ConfigError, match="E03-S01"):
        await git.squash_wip(path, "feat/x", "3f9c2e1", "feat: x")


async def test_discard_changes_scoped_to_worktree(git: GitCliProvider, tmp_game_repo: Path) -> None:
    wt = await _worktree(git, tmp_game_repo, "feat/discard")
    (wt / "README.md").write_bytes(b"changed\n")
    (wt / "new").mkdir()
    (wt / "new" / "N.cs").write_bytes(b"n\n")
    (tmp_game_repo / "ROOT.txt").write_bytes(b"root\n")
    (tmp_game_repo / "README.md").write_bytes(b"root change\n")

    await git.discard_changes(str(wt))

    assert await git.status(str(wt)) == []
    assert (wt / "README.md").read_bytes() == b"game repo\n"
    assert sorted(await git.status(str(tmp_game_repo))) == ["README.md", "ROOT.txt"]


async def test_discard_changes_rejects_non_worktree_path(
    git: GitCliProvider, tmp_game_repo: Path
) -> None:
    (tmp_game_repo / "src").mkdir()

    with pytest.raises(ConfigError, match="worktree"):
        await git.discard_changes(str(tmp_game_repo / "src"))


async def test_git_failure_raises_git_error(git: GitCliProvider, tmp_path: Path) -> None:
    outside = tmp_path / "not-a-repo"
    outside.mkdir()

    with pytest.raises(GitError) as info:
        await git.head(str(outside))

    assert info.value.detail["argv"] == ["git", "rev-parse", "HEAD"]
    assert info.value.detail["stderr_tail"]


async def test_commit_all_falls_back_to_message_trailer_on_old_git(
    ledger: DefaultLedgerManager, idempotency: IdempotencyStore, fake_clock: FakeClock
) -> None:
    fake = FakeSubprocessRunner()
    fake.script(["git", "--version"], stdout="git version 2.25.1\n")
    fake.script(["git", "--glob-pathspecs", "ls-files"], stdout="src/A.cs\0")
    fake.script(["git", "--literal-pathspecs", "add"])
    fake.script(["git", "diff", "--cached"], stdout="src/A.cs\0")
    fake.script(["git", "rev-parse", "--abbrev-ref"], stdout="feat/x\n")
    fake.script(["git", "commit"])
    fake.script(["git", "rev-parse", "HEAD"], stdout="3f9c2e1aa\n")
    fake.script(["git", "log"], stdout="wip\n\nWalk-Work-Item: TASK-0001\n")
    provider = GitCliProvider(
        Path("/repo"), fake, ledger, idempotency, fake_clock, project_key="DEMO"
    )

    info = await provider.commit_all(
        "/repo", "wip", trailer_work_item="TASK-0001", idempotency_key=KEY
    )
    await provider.commit_all("/repo", "wip", trailer_work_item="TASK-0001", idempotency_key="k9")

    commits = [argv for argv in fake.argvs if argv[1] == "commit"]
    assert commits[0] == ["git", "commit", "-m", "wip\n\nWalk-Work-Item: TASK-0001"]
    assert info == CommitInfo(
        sha="3f9c2e1aa", message="wip\n\nWalk-Work-Item: TASK-0001", files=["src/A.cs"]
    )
    assert fake.argvs.count(["git", "--version"]) == 1
