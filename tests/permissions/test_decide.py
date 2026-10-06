from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.fakes.fake_clock import FakeClock
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.permissions import (
    ApprovalRepository,
    Approver,
    DefaultPermissionManager,
    PermissionEffect,
    PermissionManager,
    PermissionRule,
    ProtectedAction,
    ToolCallRequest,
)
from walk.persistence import Database, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerRepository
from walk.tools import ToolKind

ALLOW = PermissionEffect.ALLOW
DENY = PermissionEffect.DENY
APPROVAL = PermissionEffect.REQUIRE_APPROVAL
DEV = AgentRole.SENIOR_DEV
RUN = "RUN-01J0000000000000000000000A"


def _rule(tool: str, effect: PermissionEffect, **fields: object) -> PermissionRule:
    data: dict[str, object] = {"role": DEV, "tool": tool, "effect": effect, **fields}
    if effect is APPROVAL and "approver" not in data:
        data["approver"] = Approver.LEAD_DEV
    return PermissionRule.model_validate(data)


def _manager(
    db: Database,
    clock: FakeClock,
    rules: list[PermissionRule],
    protected: list[ProtectedAction] | None = None,
) -> DefaultPermissionManager:
    ids = IdSequenceStore(db)
    ledger = DefaultLedgerManager(db, LedgerRepository(db), ids, clock)
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, clock)
    return DefaultPermissionManager(
        rules,
        protected or [],
        ApprovalRepository(db),
        ledger,
        hooks,
        ids,
        clock,
        project_key="DEMO",
    )


class Factory:
    """Builds managers over the test database with inline rules."""

    def __init__(self, db: Database, clock: FakeClock) -> None:
        self._db = db
        self._clock = clock

    def __call__(
        self, rules: list[PermissionRule], protected: list[ProtectedAction] | None = None
    ) -> DefaultPermissionManager:
        return _manager(self._db, self._clock, rules, protected)


@pytest.fixture
def make(db: Database, fake_clock: FakeClock) -> Factory:
    return Factory(db, fake_clock)


def _request(
    tool: str,
    *,
    role: AgentRole = DEV,
    command: str | None = None,
    paths: list[str] | None = None,
    worktree: str = "wt",
    kind: ToolKind = ToolKind.KERNEL,
) -> ToolCallRequest:
    return ToolCallRequest(
        run_id=RUN,
        role=role,
        tool=tool,
        kind=kind,
        arguments={},
        command=command,
        paths=paths or [],
        worktree_path=worktree,
    )


def test_default_manager_satisfies_protocol(db: Database, fake_clock: FakeClock) -> None:
    manager = _manager(db, fake_clock, [])
    protocol: PermissionManager = manager
    assert protocol is manager


def test_most_specific_rule_wins(make: Factory) -> None:
    manager = make([_rule("git.*", ALLOW), _rule("git.push", DENY, reason="no pushes")])
    decision = manager.decide(_request("git.push"))
    assert decision.effect is DENY
    assert decision.matched_rule is not None
    assert decision.matched_rule.tool == "git.push"
    assert decision.reason == "no pushes"
    assert manager.decide(_request("git.commit")).effect is ALLOW


def test_precedence_deny_over_approval_over_allow(make: Factory) -> None:
    manager = make([_rule("git.*", ALLOW), _rule("git.*", APPROVAL)])
    decision = manager.decide(_request("git.commit"))
    assert decision.effect is APPROVAL
    assert decision.matched_rule is not None
    assert decision.matched_rule.approver is Approver.LEAD_DEV
    denied = make([_rule("git.*", ALLOW), _rule("git.*", APPROVAL), _rule("git.*", DENY)])
    assert denied.decide(_request("git.commit")).effect is DENY


def test_default_deny(make: Factory) -> None:
    manager = make([_rule("git.*", ALLOW), _rule("bash", ALLOW, role=AgentRole.QC)])
    decision = manager.decide(_request("jira.delete"))
    assert (decision.effect, decision.matched_rule, decision.reason) == (
        DENY,
        None,
        "no matching rule",
    )
    assert manager.decide(_request("bash", command="pytest")).reason == "no matching rule"


def test_shell_command_must_match_allow_pattern(make: Factory) -> None:
    manager = make([_rule("bash", ALLOW, command_patterns=["^pytest"])])
    denied = manager.decide(_request("bash", command="rm -rf /", kind=ToolKind.PROVIDER_NATIVE))
    assert denied.effect is DENY
    assert denied.reason == "command matches no allow pattern"
    allowed = manager.decide(_request("bash", command="pytest -q", kind=ToolKind.PROVIDER_NATIVE))
    assert allowed.effect is ALLOW


def test_shell_deny_pattern_overrides_allow(make: Factory) -> None:
    manager = make(
        [
            _rule("bash", ALLOW, command_patterns=["^git"]),
            _rule("bash", DENY, command_patterns=["git push --force"]),
        ]
    )
    decision = manager.decide(_request("bash", command="git push --force"))
    assert decision.effect is DENY
    assert "git push --force" in decision.reason
    assert decision.matched_rule is not None
    assert decision.matched_rule.effect is DENY
    assert manager.decide(_request("bash", command="git status")).effect is ALLOW


def test_less_specific_deny_patterns_still_apply(make: Factory) -> None:
    manager = make(
        [
            _rule("bash", ALLOW, command_patterns=["^rm"]),
            _rule("*", DENY, command_patterns=["rm -rf"]),
        ]
    )
    assert manager.decide(_request("bash", command="rm -rf /")).effect is DENY
    assert manager.decide(_request("bash", command="rm a.txt")).effect is ALLOW


def test_tool_level_deny_without_command(make: Factory) -> None:
    manager = make(
        [
            _rule("bash", ALLOW, command_patterns=["^git"]),
            _rule("bash", DENY, command_patterns=["x"]),
        ]
    )
    decision = manager.decide(_request("bash"))
    assert decision.effect is DENY


def test_pattern_deny_alone_is_not_an_allow(make: Factory) -> None:
    manager = make([_rule("bash", DENY, command_patterns=["rm -rf"])])
    decision = manager.decide(_request("bash", command="ls"))
    assert (decision.effect, decision.reason) == (DENY, "command matches no allow pattern")


def test_file_path_outside_worktree_denied(make: Factory, tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    manager = make([_rule("write", ALLOW)])
    decision = manager.decide(
        _request("write", paths=["Assets/a.cs", "../escape.cs"], worktree=str(worktree))
    )
    assert decision.effect is DENY
    assert "../escape.cs" in decision.reason
    inside = manager.decide(_request("write", paths=["Assets/a.cs"], worktree=str(worktree)))
    assert inside.effect is ALLOW


def test_file_path_must_match_rule_patterns(make: Factory, tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    manager = make([_rule("write", ALLOW, path_patterns=["Assets/*"])])
    ok = manager.decide(_request("write", paths=["Assets/Scripts/a.cs"], worktree=str(worktree)))
    assert ok.effect is ALLOW
    denied = manager.decide(_request("write", paths=["ProjectSettings/x"], worktree=str(worktree)))
    assert denied.effect is DENY
    assert "ProjectSettings/x" in denied.reason


def test_protected_action_forces_approval(make: Factory) -> None:
    lead = AgentRole.LEAD_DEV
    protected = [ProtectedAction(name="git.merge_protected")]
    manager = make([_rule("git.merge_protected", ALLOW, role=lead)], protected)
    decision = manager.decide(_request("git.merge_protected", role=lead))
    assert decision.effect is APPROVAL
    assert decision.reason == "protected action git.merge_protected requires USER approval"
    assert decision.matched_rule is not None
    assert decision.matched_rule.tool == "git.merge_protected"
    approval = make(
        [_rule("git.merge_protected", APPROVAL, role=lead, approver=Approver.LEAD_DEV)],
        [ProtectedAction(name="git.merge_protected", approver=Approver.PRODUCT_OWNER)],
    ).decide(_request("git.merge_protected", role=lead))
    assert approval.effect is APPROVAL
    assert "PRODUCT_OWNER" in approval.reason


def test_protected_action_never_relaxes_a_deny(make: Factory) -> None:
    protected = [ProtectedAction(name="store.publish")]
    manager = make([_rule("store.publish", DENY)], protected)
    assert manager.decide(_request("store.publish")).effect is DENY
    assert make([], protected).decide(_request("store.publish")).effect is DENY


def test_approval_rule_still_checks_deny_patterns_and_paths(make: Factory, tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    manager = make(
        [_rule("bash", APPROVAL), _rule("bash", DENY, command_patterns=["--force"])],
    )
    assert manager.decide(_request("bash", command="git push")).effect is APPROVAL
    assert manager.decide(_request("bash", command="git push --force")).effect is DENY
    writer = make([_rule("write", APPROVAL)])
    escape = _request("write", paths=["../x"], worktree=str(worktree))
    assert writer.decide(escape).effect is DENY


def test_rule_validation() -> None:
    with pytest.raises(ValidationError, match="approver"):
        PermissionRule(role=DEV, tool="git.*", effect=APPROVAL)
    with pytest.raises(ValidationError, match="invalid command pattern"):
        PermissionRule(role=DEV, tool="bash", effect=ALLOW, command_patterns=["("])
