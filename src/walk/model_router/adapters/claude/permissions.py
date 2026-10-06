"""Claude `can_use_tool` translation (ADR-0006 D-1 enforcement point 2, ADR-0014).

The SDK asks the kernel before every tool call; these helpers turn the SDK's (tool name, input)
pair into the kernel's `ToolCallRequest` and the kernel's `PermissionDecision` back into the
SDK's permission result.
"""

import re
from pathlib import PurePosixPath
from typing import Final

from walk.common.ids import RunId, ToolName
from walk.common.models import JsonDict
from walk.common.roles import AgentRole
from walk.permissions.models import PermissionDecision, PermissionEffect, ToolCallRequest
from walk.tools.models import ToolKind

NATIVE_TOOL_NAMES: dict[str, ToolName] = {
    "Read": "read",
    "Write": "write",
    "Edit": "edit",
    "MultiEdit": "edit",
    "Bash": "bash",
    "Glob": "glob",
    "Grep": "grep",
}

_PATH_KEYS: Final = ("file_path", "path", "notebook_path")
_GLOB_CHARS: Final = frozenset("*?[{")
_INVALID_TOOL_CHARS: Final = re.compile(r"[^a-z0-9_-]+")
_UNKNOWN_TOOL: Final = "unknown"


def to_tool_call_request(
    tool_name: str,
    tool_input: JsonDict,
    *,
    run_id: RunId,
    role: AgentRole,
    worktree_path: str,
) -> ToolCallRequest:
    """The kernel request for one SDK tool call.

    ``Bash`` puts ``input["command"]`` into ``command``; file tools put ``file_path``, ``path``
    and ``notebook_path`` into ``paths``, plus the literal directory prefix of a ``Glob``
    pattern. A name outside `NATIVE_TOOL_NAMES` becomes its lower-cased form (characters a
    `ToolName` cannot hold become ``_``). Every request has kind ``PROVIDER_NATIVE``.
    """
    tool = NATIVE_TOOL_NAMES.get(tool_name) or _normalised_name(tool_name)
    command = tool_input.get("command") if tool == "bash" else None
    return ToolCallRequest(
        run_id=run_id,
        role=role,
        tool=tool,
        kind=ToolKind.PROVIDER_NATIVE,
        arguments=dict(tool_input),
        command=command if isinstance(command, str) else None,
        paths=_paths(tool_name, tool_input),
        worktree_path=worktree_path,
    )


def to_sdk_permission_result(decision: PermissionDecision) -> JsonDict:
    """ADR-0014 result shape: allow → ``{"behavior": "allow", "updatedInput": None}``.

    ``updatedInput`` None means the agent's input runs unchanged. Every other effect, including
    a ``REQUIRE_APPROVAL`` the authorizer failed to resolve, is a deny carrying the reason.
    """
    if decision.effect is PermissionEffect.ALLOW:
        return {"behavior": "allow", "updatedInput": None}
    if decision.effect is PermissionEffect.REQUIRE_APPROVAL:
        return {"behavior": "deny", "message": f"approval not granted: {decision.reason}"}
    return {"behavior": "deny", "message": decision.reason}


def _normalised_name(tool_name: str) -> ToolName:
    name = _INVALID_TOOL_CHARS.sub("_", tool_name.lower())
    return name if name[:1].isalpha() else _UNKNOWN_TOOL


def _paths(tool_name: str, tool_input: JsonDict) -> list[str]:
    paths = [value for key in _PATH_KEYS if isinstance(value := tool_input.get(key), str) and value]
    pattern = tool_input.get("pattern")
    if tool_name == "Glob" and isinstance(pattern, str):
        prefix = _literal_prefix(pattern)
        if prefix:
            paths.append(prefix)
    return paths


def _literal_prefix(pattern: str) -> str:
    parts: list[str] = []
    for part in PurePosixPath(pattern).parts[:-1]:
        if _GLOB_CHARS.intersection(part):
            break
        parts.append(part)
    return str(PurePosixPath(*parts)) if parts else ""
