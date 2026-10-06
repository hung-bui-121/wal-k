#!/bin/sh
# Non-billable Codex CLI probe for ADR-0014: no login, no model call.
# Uses an installed `codex` if present, else `npx -y @openai/codex`.
# Run from an empty temp directory; it never touches repository content.
set -u
if command -v codex >/dev/null 2>&1; then CODEX="codex"; else CODEX="npx -y @openai/codex"; fi
echo "== version"; $CODEX --version
echo "== exec --help (flags)"
$CODEX exec --help | grep -E '^\s+(-[a-zA-Z], )?--[a-z-]+' | sed 's/^ *//'
echo "== exec resume --help (flags)"
$CODEX exec resume --help | grep -E '^(Usage|\s+(-[a-zA-Z], )?--[a-z-]+)' | sed 's/^ *//'
