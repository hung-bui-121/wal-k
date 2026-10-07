"""Isolated git worktrees and scrubbed environments for agent runs.

§60, §139; ADR-0009 D-5/D-8, ADR-0006 D-1 enforcement point 4.
"""

import fnmatch
import logging
import re
import sys
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Final

from walk.common.errors import ConfigError
from walk.integrations.errors import GitError
from walk.integrations.protocols import GitProvider
from walk.runtime.models import AgentRun
from walk.workflow.models import WorkItem

_LOG = logging.getLogger(__name__)

WORKTREES_DIR: Final = ".walk/worktrees"

AGENT_ENV_ALLOWLIST: tuple[str, ...] = (
    "PATH",
    "HOME",
    "TMP",
    "TEMP",
    "USERPROFILE",
    "SYSTEMROOT",
    "UNITY_EDITOR_PATH",
    "UNITY_PATH",
    "UNITY_VERSION",
    "UNITY_PROJECT_PATH",
)
"""Environment keys an agent subprocess may see; a trailing ``*`` matches a key prefix.

Only named, non-secret Unity variables pass (E02-S14): the Unity licence credentials
(``UNITY_PASSWORD``, ``UNITY_SERIAL``, ``UNITY_LICENSE``, ``UNITY_EMAIL``) are kernel credentials.
"""

WINDOWS_AGENT_ENV_ALLOWLIST: tuple[str, ...] = ("APPDATA", "LOCALAPPDATA", "PATHEXT", "COMSPEC")
"""Extra keys on Windows: npm-installed CLIs read their config under ``APPDATA``/``LOCALAPPDATA``;
Node and Rust process spawning (shells, ``.cmd`` children) needs ``PATHEXT`` and ``COMSPEC``."""

_SLUG_MAX: Final = 30
_NON_SLUG: Final = re.compile(r"[^a-z0-9]+")

_PostCreate = Callable[[AgentRun, WorkItem, str], Awaitable[None]]


def scrubbed_env(
    os_env: Mapping[str, str],
    *,
    platform: str = sys.platform,
    allowlist: tuple[str, ...] = AGENT_ENV_ALLOWLIST,
) -> dict[str, str]:
    """Keys equal to an allowlist entry or matching a trailing-`*` glob; values copied verbatim.

    ``allowlist`` (default `AGENT_ENV_ALLOWLIST`) applies everywhere;
    `WINDOWS_AGENT_ENV_ALLOWLIST` is added when ``platform == "win32"``. Keys compare
    case-sensitively on POSIX and case-insensitively on Windows (``ComSpec`` and
    ``SystemRoot`` match), where environment variable names are case-insensitive; the key
    spelling of ``os_env`` is kept.
    """
    fold = platform == "win32"
    entries = allowlist + (WINDOWS_AGENT_ENV_ALLOWLIST if fold else ())
    exact = {_fold(e, fold=fold) for e in entries if not e.endswith("*")}
    prefixes = tuple(_fold(e[:-1], fold=fold) for e in entries if e.endswith("*"))
    return {
        key: value
        for key, value in os_env.items()
        if (folded := _fold(key, fold=fold)) in exact or folded.startswith(prefixes)
    }


def _fold(key: str, *, fold: bool) -> str:
    return key.upper() if fold else key


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
        project_skills: _PostCreate | None = None,
    ) -> None:
        """Wire the manager.

        Args:
            repo_root: Main checkout of the game repository.
            git: Branch, worktree and hook operations.
            protected_branches: Globs the guard hooks protect and `remove` never deletes.
            default_branch: Base of new work branches (``Project.default_branch``).
            project_skills: Projects the run's skills for the run's provider into a worktree
                (``SkillRegistry.project_all``, wired by the composition root; E02-S06).
        """
        self._repo_root = repo_root
        self._git = git
        self._protected = list(protected_branches)
        self._default_branch = default_branch
        self._project_skills = project_skills
        # Extension point for E02-S06 (skill projections into the new worktree); empty here.
        self.post_create: list[_PostCreate] = []

    async def create(self, run: AgentRun, item: WorkItem) -> str:
        """Ensure the branch, add the worktree, project the run's skills, install guard hooks.

        The worktree is `<repo>/.walk/worktrees/<run_id>`. The branch is created once per
        item (idempotency key ``git.branch:<item id>``) from ``default_branch``; later runs of
        the item reuse it. Returns the absolute worktree
        path; the caller stores it with the branch on the run.

        Raises:
            ConfigError: Skill projection or the guard hook installation failed; the new
                worktree has been removed (the branch is kept).
        """
        branch = branch_name_for(item)
        await self._git.ensure_branch(
            branch, self._default_branch, idempotency_key=f"git.branch:{item.id}"
        )
        path = await self._git.add_worktree(str(self._worktree_path(run)), branch)
        try:
            await self._project(run, item, path)
            await self._git.install_guard_hooks(path, self._protected)
        except (ConfigError, GitError) as exc:
            await self._git.remove_worktree(path, force=True)
            if isinstance(exc, ConfigError):
                raise
            msg = f"guard hooks could not be installed in {path}"
            raise ConfigError(msg, detail={"run_id": run.id, "error": str(exc)}) from exc
        for hook in self.post_create:
            await hook(run, item, path)
        return path

    async def adopt(self, run: AgentRun, previous: AgentRun, item: WorkItem) -> str:
        """Reuse ``previous``'s worktree for the child ``run`` (fallback, recovery, resume).

        An existing directory is kept (uncommitted residue included). A missing one is
        re-added on ``previous``'s branch with guard hooks (and the post-create extensions).
        Either way the skills are projected for ``run``, whose provider may differ from
        ``previous``'s (fallback). Never `create`: git checks a branch out in one worktree only.

        Raises:
            ConfigError: ``previous`` has no worktree, or skill projection failed (the
                worktree is kept: it may hold uncommitted work).
            GitError: From re-adding the worktree.
        """
        if previous.worktree_path is None:
            msg = f"run {previous.id} has no worktree to adopt"
            raise ConfigError(msg, detail={"run_id": run.id, "previous_run_id": previous.id})
        path = previous.worktree_path
        if _is_dir(path):
            await self._project(run, item, path)
            return path
        branch = previous.branch or branch_name_for(item)
        path = await self._git.add_worktree(path, branch)
        await self._project(run, item, path)
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

    async def _project(self, run: AgentRun, item: WorkItem, path: str) -> None:
        """Run the skill projection; any failure becomes `ConfigError` naming the run."""
        if self._project_skills is None:
            return
        try:
            await self._project_skills(run, item, path)
        except Exception as exc:
            msg = f"skill projection failed: {exc}"
            raise ConfigError(msg, detail={"run_id": run.id, "worktree": path}) from exc

    def _worktree_path(self, run: AgentRun) -> Path:
        return (self._repo_root / WORKTREES_DIR / run.id).resolve()


def _is_dir(path: str) -> bool:
    return Path(path).is_dir()
