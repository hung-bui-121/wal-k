"""Post-run repository boundary audit (§91; ADR-0006 D-5/D-6, enforcement point 5)."""

import fnmatch
from pathlib import Path, PurePosixPath
from typing import Final

DEFAULT_FORBIDDEN_PATHS: tuple[str, ...] = (
    ".ai/**",
    ".walk/**",
    "**/*.env",
    "ProjectSettings/*Secrets*",
    ".git/**",
    ".claude/**",
    "AGENTS.md",
    ".codex/**",
)
DEFAULT_ALLOWED_PATHS: tuple[str, ...] = ("**",)

_ANY_DIRS_PREFIX: Final = "**/"
# ADR-0006 D-5: agents may write evidence even though `.ai/**` is forbidden.
_EVIDENCE_ROOTS: Final = frozenset({"features", "bugs", "phases"})
_EVIDENCE_DIR: Final = "evidence"
_MIN_EVIDENCE_PARTS: Final = 4  # .ai/<root>/<folder>/evidence/<file> at the shortest


class DefaultBoundaryAuditor:
    """`BoundaryAuditor`: pure path checks, no git and no file access beyond path resolution."""

    def audit(
        self,
        worktree_path: str,
        changed_files: list[str],
        allowed_paths: list[str],
        forbidden_paths: list[str],
    ) -> list[str]:
        """The changed files that break the boundary, in input order (as given).

        A file breaks it when it resolves outside ``worktree_path``, matches a forbidden glob
        (evidence folders under `.ai/features|bugs|phases/**/evidence/` excepted) or matches
        no allowed glob. Globs apply to the worktree-relative forward-slash path, through
        `PurePosixPath.match` (right-anchored) and `fnmatch` on the full path, where a leading
        ``**/`` also matches zero folders.
        """
        root = Path(worktree_path).resolve()
        violations: list[str] = []
        for changed in changed_files:
            resolved = (root / changed).resolve()
            if not resolved.is_relative_to(root):
                violations.append(changed)
                continue
            relative = resolved.relative_to(root).as_posix()
            forbidden = any(_matches(relative, glob) for glob in forbidden_paths)
            if (forbidden and not _is_evidence(relative)) or not any(
                _matches(relative, glob) for glob in allowed_paths
            ):
                violations.append(changed)
        return violations


def _matches(relative: str, glob: str) -> bool:
    if fnmatch.fnmatchcase(relative, glob) or PurePosixPath(relative).match(glob):
        return True
    return glob.startswith(_ANY_DIRS_PREFIX) and fnmatch.fnmatchcase(
        relative, glob.removeprefix(_ANY_DIRS_PREFIX)
    )


def _is_evidence(relative: str) -> bool:
    parts = relative.split("/")
    return (
        len(parts) >= _MIN_EVIDENCE_PARTS
        and parts[0] == ".ai"
        and parts[1] in _EVIDENCE_ROOTS
        and _EVIDENCE_DIR in parts[2:-1]
    )
