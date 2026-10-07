import pytest

from tests.fakes.fake_clock import FakeClock
from tests.permissions.test_defaults_rules import kernel_manager, request
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.permissions import (
    DEFAULT_PROTECTED_ACTIONS,
    Approver,
    PermissionEffect,
    PermissionRule,
    PermissionsFile,
    ProtectedAction,
    load_defaults,
    merge_narrowing,
)
from walk.persistence import Database

APPROVAL = PermissionEffect.REQUIRE_APPROVAL
R = AgentRole


def test_protected_action_requires_user_approval(db: Database, fake_clock: FakeClock) -> None:
    widen = PermissionsFile(
        rules=[
            PermissionRule(
                role=R.LEAD_DEV, tool="git.merge_protected", effect=PermissionEffect.ALLOW
            )
        ]
    )
    with pytest.raises(ConfigError, match="protected action cannot be downgraded"):
        merge_narrowing(load_defaults(), widen)
    manager = kernel_manager(db, fake_clock)

    decision = manager.decide(request(R.LEAD_DEV, "git.merge_protected"))

    assert decision.effect is APPROVAL
    assert "protected action" in decision.reason
    assert decision.matched_rule is not None
    assert decision.matched_rule.approver is Approver.USER
    for action in DEFAULT_PROTECTED_ACTIONS:
        effect = manager.decide(request(R.ORCHESTRATOR, action)).effect
        assert effect is APPROVAL, action
    # A role-specific DENY stays a DENY (ADR-0006 D-3).
    assert manager.decide(request(R.SENIOR_DEV, "git.merge_protected")).effect is (
        PermissionEffect.DENY
    )


def test_project_added_protected_action(db: Database, fake_clock: FakeClock) -> None:
    project = PermissionsFile(
        protected_actions=[ProtectedAction(name="analytics.purge", approver=Approver.PRODUCT_OWNER)]
    )
    manager = kernel_manager(db, fake_clock, project)

    decision = manager.decide(request(R.ORCHESTRATOR, "analytics.purge"))

    assert decision.effect is APPROVAL
    assert decision.matched_rule is not None
    assert decision.matched_rule.approver is Approver.PRODUCT_OWNER
    assert "PRODUCT_OWNER" in decision.reason
    with pytest.raises(ConfigError, match="protected action cannot be downgraded"):
        merge_narrowing(
            load_defaults(),
            PermissionsFile(
                rules=[
                    PermissionRule(
                        role=R.ORCHESTRATOR,
                        tool="analytics.*",
                        effect=PermissionEffect.ALLOW,
                    )
                ],
                protected_actions=project.protected_actions,
            ),
        )
