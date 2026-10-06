"""Git guard hooks: enforcement point 4 for protected branches (ADR-0006 D-1, §91).

The scripts are POSIX ``sh`` (Git for Windows ships ``sh``) and always use LF line endings.
"""

import re
from typing import Literal

from walk.common.errors import ConfigError

GUARD_HOOK_MARKER = "# walk-guard-hook v1"

_HookKind = Literal["pre-commit", "pre-push"]
_KINDS: tuple[str, ...] = ("pre-commit", "pre-push")
# Branch globs are embedded unquoted in a `case` pattern, so only shell-inert characters pass.
_SAFE_GLOB = re.compile(r"^[A-Za-z0-9*?][A-Za-z0-9._/*?-]*$")
_INDENT = "    "

# git shares one hooks folder between all worktrees of a repository, so the hooks must leave the
# developer's own checkouts alone and only guard run worktrees under <repo>/.walk/worktrees/
# (E01-S25). If git cannot answer (rev-parse fails) the hook keeps guarding: fail closed.
_RUN_WORKTREE_SCOPE = """\
walk_in_run_worktree() {
    top=$(git rev-parse --show-toplevel 2>/dev/null) || return 0
    common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || return 0
    case "$top/" in
        "${common%/.git}/.walk/worktrees/"*) return 0 ;;
    esac
    return 1
}
walk_in_run_worktree || exit 0
"""

_PRE_COMMIT_BODY = """\
branch=$(git symbolic-ref --short -q HEAD) || exit 0
walk_guard_check "$branch" "commit"
exit 0
"""

_PRE_PUSH_BODY = """\
while read -r local_ref local_sha remote_ref remote_sha; do
    case "$remote_ref" in
        refs/heads/*) walk_guard_check "${remote_ref#refs/heads/}" "push" ;;
    esac
done
exit 0
"""


def render_guard_hook(kind: _HookKind, protected_branches: list[str]) -> str:
    """Render the guard hook script ``kind`` for ``protected_branches`` (shell globs).

    ``pre-commit`` refuses a commit when the current branch matches a glob; ``pre-push``
    refuses a push whose target branch matches. Both exit 1 with a message on stderr. In a
    glob, ``*`` also matches ``/`` (``case`` pattern semantics). Both only act inside a run
    worktree (top level under ``<repo>/.walk/worktrees/``) and exit 0 everywhere else, because
    git shares the hooks folder with the developer's own checkouts (needs git ≥ 2.31 for
    ``rev-parse --path-format``; when git cannot answer, the hook keeps guarding).

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
    lines = [
        "#!/bin/sh",
        GUARD_HOOK_MARKER,
        f"# Installed by WAL-K: refuses {kind.removeprefix('pre-')}s to protected branches.",
        "# Managed file: the kernel overwrites it; do not edit.",
        "walk_guard_check() {",
        *_check_body(protected_branches),
        "}",
    ]
    body = _PRE_COMMIT_BODY if kind == "pre-commit" else _PRE_PUSH_BODY
    scope = _RUN_WORKTREE_SCOPE if protected_branches else ""  # nothing to guard otherwise
    return "\n".join(lines) + "\n" + scope + body


def _check_body(protected_branches: list[str]) -> list[str]:
    if not protected_branches:
        return [f"{_INDENT}:"]
    pattern = "|".join(protected_branches)
    return [
        f'{_INDENT}case "$1" in',
        f"{_INDENT * 2}{pattern})",
        f"{_INDENT * 3}echo \"walk: branch '$1' is protected; $2 refused\" >&2",
        f"{_INDENT * 3}exit 1",
        f"{_INDENT * 3};;",
        f"{_INDENT}esac",
    ]
