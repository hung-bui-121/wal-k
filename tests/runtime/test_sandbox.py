import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from tests.fakes.fake_git_provider import FakeGitProvider
from tests.runtime.conftest import AT, RUN_A, RUN_B, make_run
from walk.common.errors import ConfigError
from walk.integrations import GitCliProvider, GitError
from walk.integrations.git.guard_hooks import GUARD_HOOK_MARKER
from walk.runtime import WORKTREES_DIR, AgentRun, DefaultSandboxManager, branch_name_for
from walk.workflow import Story, StoryContract, WorkItem, WorkItemState

PROTECTED = ["main", "release/*"]


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def _exists(path: Path) -> bool:
    return path.exists()


def _story(**overrides: object) -> Story:
    data: dict[str, object] = {
        "id": "STORY-0001",
        "project_key": "DEMO",
        "title": "Player jump: double jump!",
        "state": WorkItemState.IMPLEMENTING,
        "contract": StoryContract(goal="Let the player double jump"),
        "created_at": AT,
        "updated_at": AT,
    }
    data.update(overrides)
    return Story.model_validate(data)


def test_branch_name_for() -> None:
    assert branch_name_for(_story()) == "feat/story-0001-player-jump-double-jump"
    long_title = _story(title="A very long title that keeps going and going for ever")
    assert branch_name_for(long_title) == "feat/story-0001-a-very-long-title-that-keeps-g"
    assert branch_name_for(_story(title="!!!")) == "feat/story-0001"
    assert branch_name_for(_story(branch="feat/custom")) == "feat/custom"


async def test_create_worktree_with_branch_and_hooks(
    git: GitCliProvider, tmp_game_repo: Path
) -> None:
    sandbox = DefaultSandboxManager(tmp_game_repo, git, PROTECTED)

    path = await sandbox.create(make_run(RUN_A), _story())

    worktree = Path(path)
    assert worktree.is_absolute()
    assert worktree == (tmp_game_repo / WORKTREES_DIR / RUN_A).resolve()
    assert _git(worktree, "rev-parse", "--abbrev-ref", "HEAD") == (
        "feat/story-0001-player-jump-double-jump"
    )
    hook = (tmp_game_repo / ".git" / "hooks" / "pre-commit").read_text(encoding="utf-8")
    assert GUARD_HOOK_MARKER in hook
    assert "release/*" in hook


async def test_create_reuses_branch_across_runs(git: GitCliProvider, tmp_game_repo: Path) -> None:
    sandbox = DefaultSandboxManager(tmp_game_repo, git, PROTECTED)
    first_run, second_run = make_run(RUN_A), make_run(RUN_B)
    first = Path(await sandbox.create(first_run, _story()))
    (first / "A.cs").write_text("class A {}\n", encoding="utf-8")
    _git(first, "add", "A.cs")
    _git(first, "commit", "-m", "wip: first run")
    await sandbox.remove(first_run)

    second = Path(await sandbox.create(second_run, _story()))

    branches = _git(tmp_game_repo, "branch", "--list", "feat/*").splitlines()
    assert [b.strip("*+ ") for b in branches] == ["feat/story-0001-player-jump-double-jump"]
    assert second != first
    assert (second / "A.cs").is_file()  # the second run continues the first run's branch
    worktrees = _git(tmp_game_repo, "worktree", "list", "--porcelain")
    assert worktrees.count("worktree ") == 2  # main checkout + the second run


async def test_concurrent_create_on_one_branch_is_refused(
    git: GitCliProvider, tmp_game_repo: Path
) -> None:
    sandbox = DefaultSandboxManager(tmp_game_repo, git, PROTECTED)
    await sandbox.create(make_run(RUN_A), _story())

    with pytest.raises(GitError):
        await sandbox.create(make_run(RUN_B), _story())


async def test_remove_keeps_or_deletes_branch(git: GitCliProvider, tmp_game_repo: Path) -> None:
    sandbox = DefaultSandboxManager(tmp_game_repo, git, PROTECTED)
    branch = "feat/story-0001-player-jump-double-jump"
    run = make_run(RUN_A, branch=branch)
    path = Path(await sandbox.create(run, _story()))
    run.worktree_path = str(path)

    await sandbox.remove(run)

    assert not _exists(path)
    assert _git(tmp_game_repo, "branch", "--list", branch)

    path = Path(await sandbox.create(run, _story()))
    run.worktree_path = str(path)
    await sandbox.remove(run, keep_branch=False)

    assert not _exists(path)
    assert not _git(tmp_game_repo, "branch", "--list", branch)


async def test_remove_never_deletes_protected_branch(
    tmp_game_repo: Path,
) -> None:
    fake = FakeGitProvider()
    sandbox = DefaultSandboxManager(tmp_game_repo, fake, PROTECTED)
    run = make_run(RUN_A, branch="release/1.0", worktree_path=None)

    await sandbox.remove(run, keep_branch=False)

    assert [name for name, _ in fake.calls] == ["remove_worktree"]
    assert fake.calls[0][1] == (str((tmp_game_repo / WORKTREES_DIR / RUN_A).resolve()), True)


async def test_create_uses_default_branch_and_item_branch(tmp_game_repo: Path) -> None:
    fake = FakeGitProvider()
    sandbox = DefaultSandboxManager(tmp_game_repo, fake, PROTECTED, default_branch="develop")
    seen: list[tuple[str, str, str]] = []

    async def projections(run: AgentRun, item: WorkItem, path: str) -> None:
        seen.append((run.id, item.id, path))

    sandbox.post_create.append(projections)

    path = await sandbox.create(make_run(RUN_A), _story(branch="feat/custom"))

    assert seen == [(RUN_A, "STORY-0001", path)]
    assert fake.calls[0] == (
        "ensure_branch",
        ("feat/custom", "develop", "git.branch:STORY-0001"),
    )
    assert fake.hooks_installed == [
        (str((tmp_game_repo / WORKTREES_DIR / RUN_A).resolve()), PROTECTED)
    ]


def _remove_tree(path: Path) -> None:
    def make_writable(function: object, target: str, info: object) -> None:
        del function, info
        Path(target).chmod(stat.S_IWRITE)
        Path(target).unlink()

    shutil.rmtree(path, onexc=make_writable)


async def test_adopt_reuses_or_re_adds_worktree(git: GitCliProvider, tmp_game_repo: Path) -> None:
    sandbox = DefaultSandboxManager(tmp_game_repo, git, PROTECTED)
    story = _story()
    first = await sandbox.create(make_run(RUN_A), story)
    parent = make_run(RUN_A, worktree_path=first, branch=branch_name_for(story))
    (Path(first) / "Residue.cs").write_bytes(b"// not committed\n")
    seen: list[str] = []

    async def projections(run: AgentRun, item: WorkItem, path: str) -> None:
        del item
        seen.append(f"{run.id}:{path}")

    sandbox.post_create.append(projections)

    reused = await sandbox.adopt(make_run(RUN_B), parent, story)

    assert reused == first
    assert _exists(Path(first) / "Residue.cs")
    assert seen == []

    _remove_tree(Path(first))
    re_added = await sandbox.adopt(make_run(RUN_B), parent, story)

    assert re_added == first
    assert _git(Path(re_added), "rev-parse", "--abbrev-ref", "HEAD") == parent.branch
    assert not _exists(Path(first) / "Residue.cs")
    hook = (tmp_game_repo / ".git" / "hooks" / "pre-commit").read_text(encoding="utf-8")
    assert GUARD_HOOK_MARKER in hook
    assert seen == [f"{RUN_B}:{first}"]
    worktrees = _git(tmp_game_repo, "worktree", "list", "--porcelain")
    assert worktrees.count("worktree ") == 2

    with pytest.raises(ConfigError, match="no worktree to adopt"):
        await sandbox.adopt(make_run(RUN_B), make_run(RUN_A), story)


async def test_create_removes_worktree_when_guard_hooks_fail(tmp_game_repo: Path) -> None:
    fake = FakeGitProvider()
    fake.fail_on["install_guard_hooks"] = GitError("hooks folder not writable", detail={})
    sandbox = DefaultSandboxManager(tmp_game_repo, fake, PROTECTED)

    with pytest.raises(ConfigError, match="guard hooks"):
        await sandbox.create(make_run(RUN_A), _story())

    assert [call[0] for call in fake.calls][-1] == "remove_worktree"
