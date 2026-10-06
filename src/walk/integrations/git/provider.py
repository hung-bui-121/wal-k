"""`GitCliProvider`: local git operations through the `git` CLI (§59-§60, §91; E01-S23).

Remote operations (`push`, `open_pr`, `merge`, `squash_wip`) arrive in E03-S01. The provider
never reads credentials and never contacts a remote.
"""

import logging
import re
from pathlib import Path
from typing import Literal, NoReturn

from walk.common.clock import Clock
from walk.common.errors import ConfigError
from walk.common.ids import ProjectKey, Sha, WorkItemId
from walk.common.roles import AgentRole
from walk.integrations.errors import GitError
from walk.integrations.git.guard_hooks import GUARD_HOOK_MARKER, render_guard_hook
from walk.integrations.models import CommitInfo, PullRequestRef
from walk.integrations.subprocess import SubprocessResult, SubprocessRunner
from walk.persistence import IdempotencyStore, UnitOfWork
from walk.telemetry.models import LedgerEvent, LedgerEventKind
from walk.telemetry.protocols import LedgerManager

_LOG = logging.getLogger(__name__)

WORK_ITEM_TRAILER = "Walk-Work-Item"
FORBIDDEN_COMMIT_PATHSPECS: tuple[str, ...] = (
    ":(exclude).ai/kernel.db",
    ":(exclude).ai/kernel.db-wal",
    ":(exclude).ai/kernel.db-shm",
    ":(exclude).walk/**",
    ":(exclude)**/*.env",
    ":(exclude)ProjectSettings/*Secrets*",
)

_DEFERRED = "implemented in E03-S01"
_STDERR_TAIL_CHARS = 2000
_TRAILER_MIN_VERSION = (2, 32)  # first git release with `git commit --trailer`
_VERSION_RE = re.compile(r"(\d+)\.(\d+)")
_EXIT_NOT_ANCESTOR = 1
_HOOK_MODE = 0o755
_RENAME_OR_COPY = ("R", "C")
_STATUS_PREFIX_LEN = 3  # "XY " before the path in porcelain v1


class GitCliProvider:
    """`GitProvider` over the `git` executable; every command goes through a `SubprocessRunner`."""

    provider = "git-cli"

    def __init__(
        self,
        repo_root: Path,
        runner: SubprocessRunner,
        ledger: LedgerManager,
        idempotency: IdempotencyStore,
        clock: Clock,
        *,
        project_key: ProjectKey,
    ) -> None:
        """Wire the provider.

        Args:
            repo_root: Main checkout of the game repository; default ``cwd``.
            runner: Executes every git command.
            ledger: Write point for ``COMMIT`` (ARCHITECTURE §4.3).
            idempotency: Keys of branch creations and commits (ADR-0002 D-7); its database
                hosts the unit of work that stores a commit key with its ledger event.
            clock: Stamps ledger events.
            project_key: Project of the ledger events.
        """
        self._repo_root = repo_root
        self._runner = runner
        self._ledger = ledger
        self._idempotency = idempotency
        self._clock = clock
        self._project_key = project_key
        self._supports_trailer: bool | None = None

    async def head(self, path: str) -> Sha:
        """Return ``git rev-parse HEAD`` in ``path``."""
        return (await self._git(path, "rev-parse", "HEAD")).stdout.strip()

    async def current_branch(self, path: str) -> str:
        """Return ``git rev-parse --abbrev-ref HEAD`` in ``path`` (``HEAD`` when detached)."""
        return (await self._git(path, "rev-parse", "--abbrev-ref", "HEAD")).stdout.strip()

    async def ensure_branch(self, name: str, base: str, *, idempotency_key: str) -> str:
        """Create branch ``name`` from ``base`` unless it exists; return ``name``.

        Runs once per ``idempotency_key``; a replay returns the stored branch name.
        """
        root = str(self._repo_root)

        async def create() -> str:
            probe = await self._git(
                root, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}", check=False
            )
            if probe.exit_code != 0:
                await self._git(root, "branch", name, base)
            return name

        async with UnitOfWork(self._idempotency.db) as uow:
            return await self._idempotency.run(idempotency_key, "git.branch", create, uow)

    async def add_worktree(self, path: str, branch: str) -> str:
        """``git worktree add <path> <branch>``; return the absolute worktree path.

        Parent directories are created; an existing worktree at ``path`` is left as is.
        """
        target = _resolve(path)
        if target in await self._worktree_paths():
            return str(target)
        _ensure_dir(target.parent)
        await self._git(str(self._repo_root), "worktree", "add", str(target), branch)
        return str(target)

    async def remove_worktree(self, path: str, *, force: bool = False) -> None:
        """``git worktree remove [--force] <path>`` followed by ``git worktree prune``."""
        root = str(self._repo_root)
        args = ["worktree", "remove", *(["--force"] if force else []), path]
        await self._git(root, *args)
        await self._git(root, "worktree", "prune")

    async def status(self, path: str) -> list[str]:
        """Dirty files of ``path`` (porcelain v1; untracked files listed individually)."""
        result = await self._git(path, "status", "--porcelain=v1", "-z", "--untracked-files=all")
        entries = result.stdout.split("\0")
        files: list[str] = []
        index = 0
        while index < len(entries):
            entry = entries[index]
            index += 1
            if len(entry) < _STATUS_PREFIX_LEN:
                continue
            files.append(entry[_STATUS_PREFIX_LEN:])
            if entry[0] in _RENAME_OR_COPY:
                index += 1  # -z puts the rename/copy source in the next entry
        return files

    async def diff_names(self, path: str, base: Sha | None = None) -> list[str]:
        """Files changed against ``base`` (``HEAD`` when None) plus untracked files, sorted."""
        changed = await self._git(path, "diff", "--name-only", "-z", base or "HEAD")
        untracked = await self._git(path, "ls-files", "--others", "--exclude-standard", "-z")
        return sorted(set(_nul_split(changed.stdout)) | set(_nul_split(untracked.stdout)))

    async def commit_all(
        self, path: str, message: str, *, trailer_work_item: WorkItemId, idempotency_key: str
    ) -> CommitInfo | None:
        """Stage everything except `FORBIDDEN_COMMIT_PATHSPECS` and commit with a trailer.

        Returns None (no key, no ledger event) when nothing is staged. The idempotency key and
        the ``COMMIT`` ledger event are stored in one unit of work; a replayed key returns the
        stored `CommitInfo` without touching the repository.

        Raises:
            ConfigError: The key is recorded without a result to replay.
            GitError: A git command failed (e.g. a guard hook refused the commit).
        """
        existing = await self._idempotency.get(idempotency_key)
        if existing is not None:
            if existing.result_ref is None:
                msg = "idempotency key has no result to replay"
                raise ConfigError(msg, detail={"key": idempotency_key})
            return CommitInfo.model_validate_json(existing.result_ref)
        await self._stage_allowed(path)
        staged = await self._git(path, "diff", "--cached", "--name-only", "-z")
        files = _nul_split(staged.stdout)
        if not files:
            return None
        branch = await self.current_branch(path)
        trailer = f"{WORK_ITEM_TRAILER}: {trailer_work_item}"
        if await self._trailer_supported():
            await self._git(path, "commit", "-m", message, "--trailer", trailer)
        else:
            await self._git(path, "commit", "-m", f"{message}\n\n{trailer}")
        sha = await self.head(path)
        full_message = (await self._git(path, "log", "-1", "--format=%B", sha)).stdout.strip()
        info = CommitInfo(sha=sha, message=full_message, files=files)
        event = LedgerEvent(
            kind=LedgerEventKind.COMMIT,
            at=self._clock.now(),
            project_key=self._project_key,
            actor_role=AgentRole.KERNEL,
            work_item_id=trailer_work_item,
            outcome="OK",
            payload={
                "sha": sha,
                "branch": branch,
                "files_count": len(files),
                "work_item_id": trailer_work_item,
            },
        )
        async with UnitOfWork(self._idempotency.db) as uow:
            await self._idempotency.put(idempotency_key, "git.commit", info.model_dump_json(), uow)
            await self._ledger.append(event, uow=uow)
        return info

    async def push(self, path: str, branch: str, *, protected_branches: list[str]) -> None:
        """Not available before E03-S01 (raises `ConfigError`)."""
        del path, protected_branches
        _deferred("push", branch)

    async def open_pr(
        self, branch: str, base: str, title: str, body: str, *, idempotency_key: str
    ) -> PullRequestRef:
        """Not available before E03-S01 (raises `ConfigError`)."""
        del base, title, body, idempotency_key
        _deferred("open_pr", branch)

    async def merge(
        self, pr: PullRequestRef, *, strategy: Literal["squash", "merge"], idempotency_key: str
    ) -> Sha:
        """Not available before E03-S01 (raises `ConfigError`)."""
        del strategy, idempotency_key
        _deferred("merge", pr.base)

    async def squash_wip(self, path: str, branch: str, base: Sha, message: str) -> Sha:
        """Not available before E03-S01 (raises `ConfigError`)."""
        del path, base, message
        _deferred("squash_wip", branch)

    async def install_guard_hooks(self, path: str, protected_branches: list[str]) -> None:
        """Write the ``pre-commit`` and ``pre-push`` guard hooks into ``path``'s hooks folder.

        The folder is ``git rev-parse --git-path hooks``; git shares it between all worktrees
        of a repository. Only hooks carrying `GUARD_HOOK_MARKER` are overwritten.

        Raises:
            ConfigError: A hook file without the marker exists (nothing is written), or a
                protected branch glob is invalid.
        """
        out = (await self._git(path, "rev-parse", "--git-path", "hooks")).stdout.strip()
        hooks_dir = Path(out) if Path(out).is_absolute() else Path(path) / out
        scripts = {
            kind: render_guard_hook(kind, protected_branches) for kind in ("pre-commit", "pre-push")
        }
        _write_hooks(hooks_dir, scripts)
        _LOG.info(
            "guard hooks installed",
            extra={"hooks_dir": str(hooks_dir), "protected": protected_branches},
        )

    async def is_ancestor(self, ancestor: Sha, descendant: Sha, path: str) -> bool:
        """``git merge-base --is-ancestor``; exit 1 → False.

        Raises:
            GitError: Any other non-zero exit (e.g. an unknown commit).
        """
        result = await self._git(
            path, "merge-base", "--is-ancestor", ancestor, descendant, check=False
        )
        if result.exit_code == 0:
            return True
        if result.exit_code == _EXIT_NOT_ANCESTOR:
            return False
        raise _git_error(result, path)

    async def merge_base(self, a: str, b: str, path: str) -> Sha:
        """``git merge-base a b``.

        Raises:
            GitError: No common ancestor or an unknown ref.
        """
        return (await self._git(path, "merge-base", a, b)).stdout.strip()

    async def changed_between(
        self, a: Sha, b: Sha, path: str, *, paths: list[str] | None = None
    ) -> list[str]:
        """``git diff --name-only a b -- paths``."""
        result = await self._git(path, "diff", "--name-only", "-z", a, b, "--", *(paths or []))
        return _nul_split(result.stdout)

    async def discard_changes(self, path: str) -> None:
        """Reset tracked and untracked changes of the worktree at ``path`` only.

        Runs ``git checkout -- .`` and ``git clean -fd`` (ignored files stay) inside ``path``.

        Raises:
            ConfigError: ``path`` is not the top level of a worktree.
        """
        top = (await self._git(path, "rev-parse", "--show-toplevel")).stdout.strip()
        if _resolve(top) != _resolve(path):
            msg = "discard_changes needs the top level of a worktree"
            raise ConfigError(msg, detail={"path": path, "toplevel": top})
        await self._git(path, "checkout", "--", ".")
        await self._git(path, "clean", "-fd")

    async def _stage_allowed(self, path: str) -> None:
        # Candidates are listed first and staged by exact path: `git add` with an exclude
        # pathspec naming an ignored folder (`.walk/`) exits 1, and a forbidden file must never
        # be hashed into the object store. --glob-pathspecs gives `**` its directory meaning,
        # so `**/*.env` also matches top-level files such as `secrets.env`.
        listed = await self._git(
            path,
            "--glob-pathspecs",
            "ls-files",
            "-z",
            "--others",
            "--modified",
            "--deleted",
            "--exclude-standard",
            "--",
            ".",
            *FORBIDDEN_COMMIT_PATHSPECS,
        )
        candidates = list(dict.fromkeys(_nul_split(listed.stdout)))
        if not candidates:
            return
        await self._git(
            path,
            "--literal-pathspecs",
            "add",
            "-A",
            "--pathspec-from-file=-",
            "--pathspec-file-nul",
            input_text="\0".join(candidates),
        )

    async def _worktree_paths(self) -> set[Path]:
        result = await self._git(str(self._repo_root), "worktree", "list", "--porcelain")
        prefix = "worktree "
        return {
            _resolve(line.removeprefix(prefix))
            for line in result.stdout.splitlines()
            if line.startswith(prefix)
        }

    async def _trailer_supported(self) -> bool:
        if self._supports_trailer is None:
            out = (await self._git(str(self._repo_root), "--version")).stdout
            match = _VERSION_RE.search(out)
            version = (int(match.group(1)), int(match.group(2))) if match else (0, 0)
            self._supports_trailer = version >= _TRAILER_MIN_VERSION
        return self._supports_trailer

    async def _git(
        self, cwd: str, *args: str, check: bool = True, input_text: str | None = None
    ) -> SubprocessResult:
        result = await self._runner.run(["git", *args], cwd=cwd, input_text=input_text)
        if check and result.exit_code != 0:
            raise _git_error(result, cwd)
        return result


def _deferred(operation: str, branch: str) -> NoReturn:
    raise ConfigError(_DEFERRED, detail={"operation": operation, "branch": branch})


def _git_error(result: SubprocessResult, cwd: str) -> GitError:
    msg = "git command failed"
    return GitError(
        msg,
        detail={
            "argv": result.argv,
            "cwd": cwd,
            "exit_code": result.exit_code,
            "stderr_tail": result.stderr[-_STDERR_TAIL_CHARS:],
        },
    )


def _resolve(path: str) -> Path:
    # Normalises separators, 8.3 short names and case for comparing worktree paths.
    return Path(path).resolve()


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_hooks(hooks_dir: Path, scripts: dict[str, str]) -> None:
    """Write ``scripts`` (hook name → text) after checking every target is ours."""
    for kind in scripts:
        target = hooks_dir / kind
        if target.exists() and GUARD_HOOK_MARKER.encode() not in target.read_bytes():
            msg = "refusing to overwrite a foreign git hook"
            raise ConfigError(msg, detail={"hook": str(target)})
    hooks_dir.mkdir(parents=True, exist_ok=True)
    for kind, script in scripts.items():
        target = hooks_dir / kind
        target.write_bytes(script.encode("utf-8"))  # bytes keep LF endings on Windows
        target.chmod(_HOOK_MODE)


def _nul_split(text: str) -> list[str]:
    return [part for part in text.split("\0") if part]
