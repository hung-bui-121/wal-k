"""Post-run repository boundary audit (§91; ADR-0006 D-5/D-6, enforcement point 5; E02-S14).

Path rules: a changed file must resolve inside the worktree, must not match a forbidden glob
(unless it matches an evidence exception) and must match an allowed glob of the run's policy.
Content rule: an added or modified file (≤ 1 MB, text) must not contain a secret
(``SECRET:<path>``); the scanner is injected (`walk.memory.secrets.contains_secret`).
"""

import fnmatch
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Final

DEFAULT_FORBIDDEN_PATHS: tuple[str, ...] = (
    ".ai/**",
    ".walk/**",
    "**/*.env",
    "ProjectSettings/*Secrets*",
    ".ai/agents/**",
    ".ai/approved/**",
    ".git/**",
    ".claude/**",
    "AGENTS.md",
    ".codex/**",
)
"""Never writable by an agent (E02-S14 list plus the E01-S25 provider folders)."""

EVIDENCE_EXCEPTIONS: tuple[str, ...] = (
    ".ai/features/*/evidence/**",
    ".ai/bugs/*/evidence/**",
    ".ai/phases/*/evidence/**",
)
"""Forbidden paths an agent may still write: evidence folders (ADR-0006 D-5)."""

DEFAULT_ALLOWED_PATHS: tuple[str, ...] = ("**",)

SECRET_PREFIX: Final = "SECRET:"  # noqa: S105 - a label, not a password
_ANY_DIRS_PREFIX: Final = "**/"
_ANY_DIRS: Final = "/**/"
_MAX_SCAN_BYTES: Final = 1024 * 1024
_BINARY_PROBE: Final = 8192
_NUL: Final = b"\x00"

SecretScan = Callable[[str], str | None]


class DefaultBoundaryAuditor:
    """`BoundaryAuditor`: path rules plus an optional secret scan of the changed files."""

    def __init__(
        self,
        *,
        forbidden: tuple[str, ...] = DEFAULT_FORBIDDEN_PATHS,
        exceptions: tuple[str, ...] = EVIDENCE_EXCEPTIONS,
        secret_scan: SecretScan | None = None,
    ) -> None:
        """Wire the auditor.

        Args:
            forbidden: Globs always forbidden, besides those passed to `audit`.
            exceptions: Globs that win over ``forbidden`` (evidence folders).
            secret_scan: Returns the name of a secret found in a text, or None; without it no
                content is read (the composition root passes ``contains_secret``).
        """
        self._forbidden = forbidden
        self._exceptions = exceptions
        self._secret_scan = secret_scan

    def audit(
        self,
        worktree_path: str,
        changed_files: list[str],
        allowed_paths: list[str],
        forbidden_paths: list[str],
    ) -> list[str]:
        """The changed files that break the boundary (E02-S14).

        Violations: path outside worktree (absolute/..), path matching forbidden (unless
        matching an exception), path not matching any allowed glob, or ``SECRET:<path>`` when
        the secret scan finds a secret in an added/modified file. Paths are POSIX, resolved
        against the worktree; violations keep the given spelling, in input order. A file
        passes the path rules before its content is scanned; deleted, binary (NUL byte) and
        larger than 1 MB files are not scanned.
        """
        root = Path(worktree_path).resolve()
        forbidden = [*self._forbidden, *forbidden_paths]
        violations: list[str] = []
        for changed in changed_files:
            resolved = (root / changed).resolve()
            if not resolved.is_relative_to(root):
                violations.append(changed)
                continue
            relative = resolved.relative_to(root).as_posix()
            excepted = any(_matches(relative, glob) for glob in self._exceptions)
            barred = not excepted and any(_matches(relative, glob) for glob in forbidden)
            if barred or not any(_matches(relative, glob) for glob in allowed_paths):
                violations.append(changed)
            elif self._secret_scan is not None and self._has_secret(resolved):
                violations.append(f"{SECRET_PREFIX}{changed}")
        return violations

    def _has_secret(self, file: Path) -> bool:
        if self._secret_scan is None or not file.is_file():
            return False
        if file.stat().st_size > _MAX_SCAN_BYTES:
            return False
        data = file.read_bytes()
        if _NUL in data[:_BINARY_PROBE]:
            return False
        return self._secret_scan(data.decode("utf-8", errors="ignore")) is not None


def _matches(relative: str, glob: str) -> bool:
    """`fnmatch` on the full path or right-anchored `PurePosixPath.match`; ``**/`` may be empty."""
    if fnmatch.fnmatchcase(relative, glob) or PurePosixPath(relative).match(glob):
        return True
    if glob.startswith(_ANY_DIRS_PREFIX):
        return fnmatch.fnmatchcase(relative, glob.removeprefix(_ANY_DIRS_PREFIX))
    return _ANY_DIRS in glob and fnmatch.fnmatchcase(relative, glob.replace(_ANY_DIRS, "/"))
