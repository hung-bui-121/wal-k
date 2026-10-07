from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.permissions import (
    ApprovalRepository,
    DefaultPermissionManager,
    PermissionEffect,
    PermissionsFile,
    ToolCallRequest,
    load_defaults,
    merge_narrowing,
)
from walk.persistence import Database, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerRepository
from walk.tools import ToolKind

ALLOW = PermissionEffect.ALLOW
DENY = PermissionEffect.DENY
R = AgentRole
RUN = "RUN-01J0000000000000000000000A"


def kernel_manager(
    db: Database, clock: FakeClock, project: PermissionsFile | None = None
) -> DefaultPermissionManager:
    """A permission manager on the kernel defaults narrowed by ``project``."""
    merged = merge_narrowing(load_defaults(), project or PermissionsFile())
    ids = IdSequenceStore(db)
    ledger = DefaultLedgerManager(db, LedgerRepository(db), ids, clock)
    return DefaultPermissionManager(
        merged.rules,
        merged.protected_actions,
        ApprovalRepository(db),
        ledger,
        DefaultHookManager(HookExecutionRepository(db), ledger, clock),
        ids,
        clock,
        project_key="DEMO",
    )


def request(
    role: AgentRole,
    tool: str,
    *,
    command: str | None = None,
    paths: list[str] | None = None,
    worktree: str = "wt",
) -> ToolCallRequest:
    """A tool call of ``role``; shell and file tools are provider-native."""
    native = tool in {"bash", "read", "edit", "write", "glob", "grep"}
    return ToolCallRequest(
        run_id=RUN,
        role=role,
        tool=tool,
        kind=ToolKind.PROVIDER_NATIVE if native else ToolKind.KERNEL,
        arguments={},
        command=command,
        paths=paths or [],
        worktree_path=worktree,
    )


@pytest.fixture
def manager(db: Database, fake_clock: FakeClock) -> DefaultPermissionManager:
    return kernel_manager(db, fake_clock)


def test_senior_dev_may_commit(manager: DefaultPermissionManager) -> None:
    assert manager.decide(request(R.SENIOR_DEV, "git.commit")).effect is ALLOW
    assert manager.decide(request(R.LEAD_DEV, "git.commit")).effect is ALLOW


def test_senior_dev_cannot_approve_review(manager: DefaultPermissionManager) -> None:
    assert manager.decide(request(R.SENIOR_DEV, "review.approve")).effect is DENY
    assert manager.decide(request(R.SENIOR_DEV, "qc.approve")).effect is DENY
    assert manager.decide(request(R.LEAD_DEV, "review.approve")).effect is ALLOW


def test_qc_read_only_but_may_create_bug(manager: DefaultPermissionManager, tmp_path: Path) -> None:
    edit = request(R.QC, "edit", paths=["Assets/a.cs"], worktree=str(tmp_path))
    assert manager.decide(edit).effect is DENY
    assert manager.decide(request(R.QC, "jira.create_bug")).effect is ALLOW
    read = request(R.QC, "read", paths=["Assets/a.cs"], worktree=str(tmp_path))
    assert manager.decide(read).effect is ALLOW


def test_force_push_denied_for_all_roles(manager: DefaultPermissionManager) -> None:
    for role in (R.LEAD_DEV, R.SENIOR_DEV, R.QC):
        decision = manager.decide(request(role, "bash", command="git push --force origin main"))
        assert decision.effect is DENY, role


def test_bash_command_patterns(manager: DefaultPermissionManager) -> None:
    def effect(role: AgentRole, command: str) -> PermissionEffect:
        return manager.decide(request(role, "bash", command=command)).effect

    assert effect(R.SENIOR_DEV, "curl http://x") is DENY
    assert effect(R.SENIOR_DEV, "dotnet test") is ALLOW
    assert effect(R.SENIOR_DEV, "git status") is ALLOW
    assert effect(R.SENIOR_DEV, "dotnet add package X") is DENY
    assert effect(R.SENIOR_DEV, "git merge main") is DENY
    assert effect(R.SENIOR_DEV, "python evil.py") is DENY  # not allowlisted
    assert effect(R.QC, "dotnet test") is ALLOW
    assert effect(R.QC, "dotnet build") is DENY
    assert effect(R.ORCHESTRATOR, "ls") is DENY


def test_file_tools_stay_inside_the_worktree(
    manager: DefaultPermissionManager, tmp_path: Path
) -> None:
    inside = request(R.SENIOR_DEV, "write", paths=["Assets/Scripts/a.cs"], worktree=str(tmp_path))
    outside = request(R.SENIOR_DEV, "write", paths=["../escape.cs"], worktree=str(tmp_path))
    assert manager.decide(inside).effect is ALLOW
    assert manager.decide(outside).effect is DENY
