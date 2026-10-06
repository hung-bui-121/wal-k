"""Permission policy evaluation and approval persistence (§31, §92; ADR-0006)."""

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
    "ApprovalRepository",
    "ApprovalRequest",
    "ApprovalState",
    "Approver",
    "DefaultPermissionManager",
    "PermissionDecision",
    "PermissionEffect",
    "PermissionManager",
    "PermissionRule",
    "ProtectedAction",
    "ToolCallRequest",
    "command_allowed",
    "match_tool",
    "path_inside_worktree",
    "tool_pattern_specificity",
]
