import sys
from pathlib import Path

import pytest

from walk.common.roles import AgentRole
from walk.permissions import (
    PermissionEffect,
    PermissionRule,
    command_allowed,
    match_tool,
    path_inside_worktree,
    tool_pattern_specificity,
)


def _link_dir(target: Path, link: Path) -> None:
    """Directory symlink, or a junction on Windows hosts without the symlink privilege."""
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            raise
        import _winapi  # noqa: PLC0415 - Windows-only fallback

        _winapi.CreateJunction(str(target), str(link))


def _rule(effect: PermissionEffect, *patterns: str) -> PermissionRule:
    return PermissionRule(
        role=AgentRole.SENIOR_DEV, tool="bash", effect=effect, command_patterns=list(patterns)
    )


def test_tool_pattern_specificity() -> None:
    patterns = ["git.commit", "git.*", "*", "jira.*"]
    assert [tool_pattern_specificity(p, "git.commit") for p in patterns] == [3, 2, 1, 0]
    assert tool_pattern_specificity("jira.create_*", "jira.create_bug") == 2
    assert tool_pattern_specificity("git.*", "git") == 0
    assert tool_pattern_specificity("git.com", "git.commit") == 0


def test_match_tool() -> None:
    assert match_tool("git.*", "git.push")
    assert match_tool("*", "bash")
    assert not match_tool("git.*", "gitk")
    assert not match_tool("bash", "bash2")


def test_command_allowed_reports_the_deciding_pattern() -> None:
    allow = [_rule(PermissionEffect.ALLOW, "^pytest", "^dotnet test")]
    deny = [_rule(PermissionEffect.DENY, "--force")]
    assert command_allowed("pytest -q", allow, deny) == (True, "allow pattern '^pytest'")
    assert command_allowed("dotnet test --force", allow, deny) == (
        False,
        "command matches deny pattern '--force'",
    )
    assert command_allowed("rm -rf /", allow, deny) == (False, "command matches no allow pattern")
    assert command_allowed("pytest", [], []) == (False, "command matches no allow pattern")


def test_path_inside_worktree_rejects_escapes(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    outside = tmp_path / "outside"
    worktree.mkdir()
    outside.mkdir()
    _link_dir(outside, worktree / "link")
    wt = str(worktree)
    assert not path_inside_worktree("../x", wt)
    assert not path_inside_worktree("link/secret.txt", wt)
    assert not path_inside_worktree(str(outside / "f.txt"), wt)
    assert path_inside_worktree("Assets/Player.cs", wt)
    assert path_inside_worktree("Assets/../README.md", wt)
    assert path_inside_worktree(str(worktree / "a.txt"), wt)
    assert path_inside_worktree(".", wt)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path semantics")
def test_path_inside_worktree_is_case_insensitive_on_windows(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    assert path_inside_worktree(str(worktree).upper() + "\\a.txt", str(worktree))
