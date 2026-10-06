"""Pure matching helpers of permission evaluation (ADR-0006 D-3)."""

import re
from pathlib import Path
from typing import Final

from walk.common.ids import ToolName
from walk.permissions.models import PermissionRule

_ANY: Final = "*"
_EXACT: Final = 3
_PREFIX_GLOB: Final = 2
_WILDCARD: Final = 1
_NO_MATCH: Final = 0


def tool_pattern_specificity(pattern: str, tool: ToolName) -> int:
    """How specifically ``pattern`` names ``tool``.

    Returns:
        3 for an exact name, 2 for a prefix glob ending in ``*`` (``git.*``, ``jira.create_*``),
        1 for ``*`` and 0 when the pattern does not match.
    """
    if pattern == _ANY:
        return _WILDCARD
    if pattern.endswith(_ANY):
        return _PREFIX_GLOB if tool.startswith(pattern[:-1]) else _NO_MATCH
    return _EXACT if pattern == tool else _NO_MATCH


def match_tool(pattern: str, tool: ToolName) -> bool:
    """True iff ``pattern`` matches ``tool``."""
    return tool_pattern_specificity(pattern, tool) > _NO_MATCH


def _deny_pattern_hit(command: str, deny_rules: list[PermissionRule]) -> str | None:
    """The first DENY command pattern found in ``command``, else None."""
    for rule in deny_rules:
        for pattern in rule.command_patterns:
            if re.search(pattern, command):
                return pattern
    return None


def command_allowed(
    command: str, allow_rules: list[PermissionRule], deny_rules: list[PermissionRule]
) -> tuple[bool, str]:
    """Check a shell command against command patterns (searched anywhere in the command).

    Returns:
        ``(False, reason)`` if a DENY pattern matches or no ALLOW pattern does; else
        ``(True, reason)`` naming the matching ALLOW pattern.
    """
    hit = _deny_pattern_hit(command, deny_rules)
    if hit is not None:
        return False, f"command matches deny pattern {hit!r}"
    for rule in allow_rules:
        for pattern in rule.command_patterns:
            if re.search(pattern, command):
                return True, f"allow pattern {pattern!r}"
    return False, "command matches no allow pattern"


def path_inside_worktree(path: str, worktree: str) -> bool:
    """True iff ``path`` (relative to ``worktree`` unless absolute) resolves inside it.

    Symlinks, junctions and ``..`` are resolved first; comparison uses the platform's path
    rules (case-insensitive on Windows).
    """
    root = Path(worktree).resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve().is_relative_to(root)
