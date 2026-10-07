"""Git guard hooks: enforcement point 4 for protected branches (ADR-0006 D-1, §91; E02-S14).

The scripts are the POSIX ``sh`` templates ``hooks/pre-commit.sh`` and ``hooks/pre-push.sh``
(Git for Windows ships ``sh``), rendered with the protected branch globs and always written with
LF line endings. A hook that existed before WAL-K is kept as ``<kind>.local`` and chained.
"""

import re
from pathlib import Path
from typing import Final, Literal

from walk.common.errors import ConfigError

GUARD_HOOK_MARKER = "# walk-guard-hook v1"

_HookKind = Literal["pre-commit", "pre-push"]
_KINDS: tuple[str, ...] = ("pre-commit", "pre-push")
_TEMPLATES: Final = Path(__file__).resolve().parent / "hooks"
# Branch globs are embedded unquoted in a `case` pattern, so only shell-inert characters pass.
_SAFE_GLOB = re.compile(r"^[A-Za-z0-9*?][A-Za-z0-9._/*?-]*$")
_INDENT = "    "

# git shares one hooks folder between all worktrees of a repository, so the hooks must leave the
# developer's own checkouts alone and only guard run worktrees under <repo>/.walk/worktrees/
# (E01-S25). If git cannot answer (rev-parse fails) the hook keeps guarding: fail closed.
# Outside a run worktree only the chained pre-WAL-K hook runs.
_RUN_WORKTREE_SCOPE = """\
walk_in_run_worktree() {
    top=$(git rev-parse --show-toplevel 2>/dev/null) || return 0
    common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || return 0
    case "$top/" in
        "${common%/.git}/.walk/worktrees/"*) return 0 ;;
    esac
    return 1
}
walk_in_run_worktree || walk_chain "$@"
"""


def render_guard_hook(kind: _HookKind, protected_branches: list[str]) -> str:
    """Render the guard hook script ``kind`` for ``protected_branches`` (shell globs).

    ``pre-commit`` refuses a commit when the current branch matches a glob; ``pre-push``
    refuses a push whose target branch matches. Both exit 1 with ``walk: protected branch
    '<name>': <action> refused`` on stderr, and otherwise run ``<kind>.local`` when present.
    In a glob, ``*`` also matches ``/`` (``case`` pattern semantics). The checks only act inside
    a run worktree (top level under ``<repo>/.walk/worktrees/``), because git shares the hooks
    folder with the developer's own checkouts (needs git ≥ 2.31 for ``rev-parse
    --path-format``; when git cannot answer, the hook keeps guarding).

    Raises:
        ConfigError: Unknown hook kind, or a protected branch glob with characters other than
            letters, digits, ``._/-`` and the wildcards ``*``/``?``.
    """
    if kind not in _KINDS:
        msg = "unknown guard hook kind"
        raise ConfigError(msg, detail={"kind": kind, "allowed": list(_KINDS)})
    for glob in protected_branches:
        if not _SAFE_GLOB.fullmatch(glob):
            msg = "invalid protected branch glob"
            raise ConfigError(msg, detail={"glob": glob})
    template = (_TEMPLATES / f"{kind}.sh").read_bytes().decode("utf-8").replace("\r\n", "\n")
    scope = _RUN_WORKTREE_SCOPE if protected_branches else ""  # nothing to guard otherwise
    return (
        template.replace("@MARKER@", GUARD_HOOK_MARKER)
        .replace("@CHECK@\n", "\n".join(_check_body(protected_branches)) + "\n")
        .replace("@SCOPE@\n", scope)
    )


def _check_body(protected_branches: list[str]) -> list[str]:
    if not protected_branches:
        return [f"{_INDENT}:"]
    pattern = "|".join(protected_branches)
    return [
        f'{_INDENT}case "$1" in',
        f"{_INDENT * 2}{pattern})",
        f"{_INDENT * 3}echo \"walk: protected branch '$1': $2 refused\" >&2",
        f"{_INDENT * 3}exit 1",
        f"{_INDENT * 3};;",
        f"{_INDENT}esac",
    ]
