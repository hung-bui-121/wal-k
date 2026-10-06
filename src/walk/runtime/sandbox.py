"""Isolated git worktrees for agent runs (§60; ADR-0009 D-5, ADR-0006 D-1 enforcement point 4)."""

import fnmatch
import logging
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Final

from walk.common.errors import ConfigError
from walk.integrations.protocols import GitProvider
from walk.runtime.models import AgentRun
from walk.workflow.models import WorkItem

_LOG = logging.getLogger(__name__)

WORKTREES_DIR: Final = ".walk/worktrees"

_SLUG_MAX: Final = 30
_NON_SLUG: Final = re.compile(r"[^a-z0-9]+")

_PostCreate = Callable[[AgentRun, WorkItem, str], Awaitable[None]]


def branch_name_for(item: WorkItem) -> str:
    """``item.branch``, else ``feat/<id lower>-<slug of title, ≤ 30 chars>``."""
    if item.branch:
        return item.branch
    slug = _NON_SLUG.sub("-", item.title.lower()).strip("-")[:_SLUG_MAX].rstrip("-")
    prefix = f"feat/{item.id.lower()}"
    return f"{prefix}-{slug}" if slug else prefix


class DefaultSandboxManager:
    """`SandboxManager` on a `GitProvider`: one worktree per run under `.walk/worktrees/`."""

    def __init__(
        self,
        repo_root: Path,
        git: GitProvider,
        protected_branches: list[str],
        *,
        default_branch: str = "main",
    ) -> None:
        """Wire the manager.

        Args:
            repo_root: Main checkout of the game repository.
            git: Branch, worktree and hook operations.
            protected_branches: Globs the guard hooks protect and `remove` never deletes.
            default_branch: Base of new work branches (``Project.default_branch``).
        """
        self._repo_root = repo_root
        self._git = git
        self._protected = list(protected_branches)
        self._default_branch = default_branch
        # Extension point for E02-S06 (skill projections into the new worktree); empty here.
        self.post_create: list[_PostCreate] = []

    async def create(self, run: AgentRun, item: WorkItem) -> str:
        """Ensure the item's branch, add `<repo>/.walk/worktrees/<run_id>`, install guard hooks.

        The branch is created once per item (idempotency key ``git.branch:<item id>``) from
        ``default_branch``; later runs of the item reuse it. Returns the absolute worktree
        path; the caller stores it with the branch on the run.
        """
        branch = branch_name_for(item)
        await self._git.ensure_branch(
            branch, self._default_branch, idempotency_key=f"git.branch:{item.id}"
        )
        path = await self._git.add_worktree(str(self._worktree_path(run)), branch)
        await self._git.install_guard_hooks(path, self._protected)
        for hook in self.post_create:
            await hook(run, item, path)
        return path

    async def adopt(self, run: AgentRun, previous: AgentRun, item: WorkItem) -> str:
        """Reuse ``previous``'s worktree for the child ``run`` (fallback, recovery, resume).

        An existing directory is returned unchanged (uncommitted residue kept). A missing one is
        re-added on ``previous``'s branch with guard hooks (and the post-create extensions).
        Never `create`: git checks a branch out in one worktree only.

        Raises:
            ConfigError: ``previous`` has no worktree.
            GitError: From re-adding the worktree.
        """
        if previous.worktree_path is None:
            msg = f"run {previous.id} has no worktree to adopt"
            raise ConfigError(msg, detail={"run_id": run.id, "previous_run_id": previous.id})
        path = previous.worktree_path
        if _is_dir(path):
            return path
        branch = previous.branch or branch_name_for(item)
        path = await self._git.add_worktree(path, branch)
        await self._git.install_guard_hooks(path, self._protected)
        for hook in self.post_create:
            await hook(run, item, path)
        return path

    async def remove(self, run: AgentRun, *, keep_branch: bool = True) -> None:
        """Force-remove the run's worktree; delete its branch only on request and if unprotected."""
        path = run.worktree_path or str(self._worktree_path(run))
        await self._git.remove_worktree(path, force=True)
        if keep_branch or run.branch is None:
            return
        if any(fnmatch.fnmatchcase(run.branch, glob) for glob in self._protected):
            _LOG.info("protected branch kept", extra={"branch": run.branch, "run_id": run.id})
            return
        await self._git.delete_branch(run.branch, protected_branches=self._protected)

    def _worktree_path(self, run: AgentRun) -> Path:
        return (self._repo_root / WORKTREES_DIR / run.id).resolve()


def _is_dir(path: str) -> bool:
    return Path(path).is_dir()
