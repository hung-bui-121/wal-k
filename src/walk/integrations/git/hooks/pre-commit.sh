#!/bin/sh
@MARKER@
# Installed by WAL-K: refuses commits to protected branches inside run worktrees.
# Managed file: the kernel overwrites it; do not edit. A pre-commit hook that existed
# before WAL-K was moved to pre-commit.local and still runs after this check.
walk_guard_check() {
@CHECK@
}
walk_chain() {
    walk_local="$(dirname "$0")/pre-commit.local"
    if [ -x "$walk_local" ]; then
        exec "$walk_local" "$@"
    fi
    exit 0
}
@SCOPE@
branch=$(git symbolic-ref --short -q HEAD) || walk_chain "$@"
walk_guard_check "$branch" "commit"
walk_chain "$@"
