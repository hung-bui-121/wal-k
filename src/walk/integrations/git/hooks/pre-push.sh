#!/bin/sh
@MARKER@
# Installed by WAL-K: refuses pushes to protected branches inside run worktrees.
# Managed file: the kernel overwrites it; do not edit. A pre-push hook that existed
# before WAL-K was moved to pre-push.local and still runs (same stdin) after this check.
walk_input=$(cat)
walk_guard_check() {
@CHECK@
}
walk_chain() {
    walk_local="$(dirname "$0")/pre-push.local"
    if [ -x "$walk_local" ]; then
        printf '%s\n' "$walk_input" | "$walk_local" "$@"
        exit $?
    fi
    exit 0
}
@SCOPE@
printf '%s\n' "$walk_input" | while read -r local_ref local_sha remote_ref remote_sha; do
    case "$remote_ref" in
        refs/heads/*) walk_guard_check "${remote_ref#refs/heads/}" "push" ;;
    esac
done || exit 1
walk_chain "$@"
