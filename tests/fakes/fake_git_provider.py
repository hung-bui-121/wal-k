"""In-memory `GitProvider` for tests where a real repository is impractical (WBS §3.6)."""

from pathlib import Path
from typing import Literal

from walk.common.errors import PermissionDenied
from walk.common.ids import Sha, WorkItemId
from walk.integrations.models import CommitInfo, PullRequestRef

_BASE_SHA = "a" * 40


class FakeGitProvider:
    """Records every call in ``calls``; ``fail_on[method]`` is raised when that method runs.

    Inject a `GitError` there to simulate a git failure. ``dirty[path]`` lists the dirty files
    of a worktree; `commit_all` commits them (new sha, clean tree). ``diffs[path]`` answers
    `diff_names`.
    """

    provider = "fake-git"

    def __init__(self) -> None:
        """Start with one branch ``main`` at a fixed sha and nothing dirty."""
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.fail_on: dict[str, Exception] = {}
        self.branches: dict[str, Sha] = {"main": _BASE_SHA}
        self.worktrees: dict[str, str] = {}
        self.heads: dict[str, Sha] = {}
        self.dirty: dict[str, list[str]] = {}
        self.diffs: dict[str, list[str]] = {}
        self.commits: list[CommitInfo] = []
        self.hooks_installed: list[tuple[str, list[str]]] = []
        self._replays: dict[str, CommitInfo | None] = {}

    def _record(self, method: str, *args: object) -> None:
        self.calls.append((method, args))
        error = self.fail_on.get(method)
        if error is not None:
            raise error

    async def head(self, path: str) -> Sha:
        """The worktree's head (the fixed base sha until something is committed)."""
        self._record("head", path)
        return self.heads.get(path, _BASE_SHA)

    async def current_branch(self, path: str) -> str:
        """The branch the worktree was added on (``main`` otherwise)."""
        self._record("current_branch", path)
        return self.worktrees.get(path, "main")

    async def ensure_branch(self, name: str, base: str, *, idempotency_key: str) -> str:
        """Create ``name`` at ``base``'s sha unless it exists."""
        self._record("ensure_branch", name, base, idempotency_key)
        self.branches.setdefault(name, self.branches.get(base, _BASE_SHA))
        return name

    async def add_worktree(self, path: str, branch: str) -> str:
        """Register a worktree; returns the resolved path."""
        self._record("add_worktree", path, branch)
        resolved = _resolve(path)
        self.worktrees[resolved] = branch
        return resolved

    async def remove_worktree(self, path: str, *, force: bool = False) -> None:
        """Forget the worktree."""
        self._record("remove_worktree", path, force)
        self.worktrees.pop(_resolve(path), None)

    async def delete_branch(self, name: str, *, protected_branches: list[str]) -> None:
        """Forget ``name``; a protected name raises `PermissionDenied`."""
        self._record("delete_branch", name, list(protected_branches))
        if name in protected_branches:
            msg = f"branch {name} is protected"
            raise PermissionDenied(msg, detail={"branch": name})
        self.branches.pop(name, None)

    async def status(self, path: str) -> list[str]:
        """The scripted dirty files."""
        self._record("status", path)
        return list(self.dirty.get(path, []))

    async def diff_names(self, path: str, base: Sha | None = None) -> list[str]:
        """The scripted diff of ``path``."""
        self._record("diff_names", path, base)
        return list(self.diffs.get(path, []))

    async def commit_all(
        self, path: str, message: str, *, trailer_work_item: WorkItemId, idempotency_key: str
    ) -> CommitInfo | None:
        """Commit the dirty files of ``path`` once per key; None when clean."""
        self._record("commit_all", path, message, trailer_work_item, idempotency_key)
        if idempotency_key in self._replays:
            return self._replays[idempotency_key]
        files = self.dirty.pop(path, [])
        if not files:
            return None
        sha = f"{len(self.commits) + 1:040x}"
        info = CommitInfo(
            sha=sha, message=f"{message}\n\nWalk-Work-Item: {trailer_work_item}", files=files
        )
        self.commits.append(info)
        self.heads[path] = sha
        self._replays[idempotency_key] = info
        return info

    async def push(self, path: str, branch: str, *, protected_branches: list[str]) -> None:
        """Record the push."""
        self._record("push", path, branch, list(protected_branches))

    async def open_pr(
        self, branch: str, base: str, title: str, body: str, *, idempotency_key: str
    ) -> PullRequestRef:
        """A local PR stub."""
        self._record("open_pr", branch, base, title, body, idempotency_key)
        return PullRequestRef(
            number=None, url=None, head=self.branches.get(branch, _BASE_SHA), base=base
        )

    async def merge(
        self, pr: PullRequestRef, *, strategy: Literal["squash", "merge"], idempotency_key: str
    ) -> Sha:
        """Record the merge; returns the PR head."""
        self._record("merge", pr, strategy, idempotency_key)
        return pr.head

    async def squash_wip(self, path: str, branch: str, base: Sha, message: str) -> Sha:
        """Record the squash; returns the current head."""
        self._record("squash_wip", path, branch, base, message)
        return self.heads.get(path, _BASE_SHA)

    async def install_guard_hooks(self, path: str, protected_branches: list[str]) -> None:
        """Record the installation."""
        self._record("install_guard_hooks", path, list(protected_branches))
        self.hooks_installed.append((path, list(protected_branches)))

    async def is_ancestor(self, ancestor: Sha, descendant: Sha, path: str) -> bool:
        """True when both shas are equal or ``ancestor`` is the base sha."""
        self._record("is_ancestor", ancestor, descendant, path)
        return ancestor in {descendant, _BASE_SHA}

    async def merge_base(self, a: str, b: str, path: str) -> Sha:
        """Always the fixed base sha."""
        self._record("merge_base", a, b, path)
        return _BASE_SHA

    async def changed_between(
        self, a: Sha, b: Sha, path: str, *, paths: list[str] | None = None
    ) -> list[str]:
        """The scripted diff of ``path``."""
        self._record("changed_between", a, b, path, paths)
        return list(self.diffs.get(path, []))


def _resolve(path: str) -> str:
    return str(Path(path).resolve())


__all__ = ["FakeGitProvider"]
