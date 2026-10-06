from walk.common.roles import AgentRole
from walk.model_router.adapters.claude.permissions import (
    NATIVE_TOOL_NAMES,
    to_sdk_permission_result,
    to_tool_call_request,
)
from walk.permissions import PermissionDecision, PermissionEffect, ToolCallRequest
from walk.tools import ToolKind

RUN = "RUN-01J00000000000000000000000"


def _request(name: str, tool_input: dict[str, object]) -> ToolCallRequest:
    return to_tool_call_request(
        name, tool_input, run_id=RUN, role=AgentRole.SENIOR_DEV, worktree_path="/wt"
    )


def test_to_tool_call_request_maps_tools() -> None:
    edit = _request("Edit", {"file_path": "/wt/src/A.cs", "old_string": "a", "new_string": "b"})
    assert edit.tool == "edit"
    assert edit.paths == ["/wt/src/A.cs"]
    assert edit.kind is ToolKind.PROVIDER_NATIVE
    assert edit.command is None
    assert edit.run_id == RUN
    assert edit.role is AgentRole.SENIOR_DEV
    assert edit.worktree_path == "/wt"
    assert edit.arguments == {"file_path": "/wt/src/A.cs", "old_string": "a", "new_string": "b"}

    bash = _request("Bash", {"command": "dotnet test", "description": "run tests"})
    assert bash.tool == "bash"
    assert bash.command == "dotnet test"
    assert bash.paths == []

    assert _request("MultiEdit", {"file_path": "src/B.cs", "edits": []}).tool == "edit"
    assert _request("Read", {"file_path": "src/C.cs"}).paths == ["src/C.cs"]
    assert _request("Grep", {"pattern": "class \\w+", "path": "src"}).paths == ["src"]
    assert _request("Glob", {"pattern": "Assets/Scripts/**/*.cs"}).paths == ["Assets/Scripts"]
    assert _request("Glob", {"pattern": "**/*.cs"}).paths == []
    notebook = _request("NotebookEdit", {"notebook_path": "nb/a.ipynb", "new_source": ""})
    assert notebook.tool == "notebookedit"
    assert notebook.paths == ["nb/a.ipynb"]
    assert notebook.kind is ToolKind.PROVIDER_NATIVE

    unknown = _request("mcp__unity__Run Tests", {})
    assert unknown.tool == "mcp__unity__run_tests"
    assert unknown.kind is ToolKind.PROVIDER_NATIVE
    assert NATIVE_TOOL_NAMES["MultiEdit"] == "edit"


def test_to_tool_call_request_ignores_non_string_paths() -> None:
    request = _request("Write", {"file_path": 42, "content": "x"})
    assert request.paths == []
    assert _request("Bash", {"command": ["not", "a", "string"]}).command is None


def test_sdk_permission_result_shapes() -> None:
    allow = PermissionDecision(effect=PermissionEffect.ALLOW, matched_rule=None, reason="ok")
    assert to_sdk_permission_result(allow) == {"behavior": "allow", "updatedInput": None}

    deny = PermissionDecision(
        effect=PermissionEffect.DENY, matched_rule=None, reason="rm -rf is forbidden"
    )
    assert to_sdk_permission_result(deny) == {
        "behavior": "deny",
        "message": "rm -rf is forbidden",
    }


def test_sdk_permission_result_fails_closed_on_unresolved_approval() -> None:
    pending = PermissionDecision(
        effect=PermissionEffect.REQUIRE_APPROVAL, matched_rule=None, reason="needs lead"
    )
    result = to_sdk_permission_result(pending)
    assert result["behavior"] == "deny"
    assert "needs lead" in result["message"]
