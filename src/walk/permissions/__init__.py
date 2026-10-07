"""Permission policy evaluation and approval persistence (§31, §92; ADR-0006)."""

from walk.permissions.loader import (
    DEFAULT_PROTECTED_ACTIONS,
    PermissionsFile,
    load_defaults,
    load_project_rules,
    merge_narrowing,
)
from walk.permissions.matching import (
    command_allowed,
    match_tool,
    path_inside_worktree,
    tool_pattern_specificity,
)
from walk.permissions.models import (
    ApprovalRequest,
    ApprovalState,
    Approver,
    PermissionDecision,
    PermissionEffect,
    PermissionRule,
    ProtectedAction,
    ToolCallRequest,
)
from walk.permissions.protocols import PermissionManager
from walk.permissions.repository import ApprovalRepository
from walk.permissions.service import DefaultPermissionManager

__all__ = [
    "DEFAULT_PROTECTED_ACTIONS",
    "ApprovalRepository",
    "ApprovalRequest",
    "ApprovalState",
    "Approver",
    "DefaultPermissionManager",
    "PermissionDecision",
    "PermissionEffect",
    "PermissionManager",
    "PermissionRule",
    "PermissionsFile",
    "ProtectedAction",
    "ToolCallRequest",
    "command_allowed",
    "load_defaults",
    "load_project_rules",
    "match_tool",
    "merge_narrowing",
    "path_inside_worktree",
    "tool_pattern_specificity",
]
