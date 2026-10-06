import logging

import pytest

from tests.fakes.fake_clock import FakeClock
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.permissions import (
    ApprovalRepository,
    Approver,
    DefaultPermissionManager,
    PermissionEffect,
    PermissionRule,
)
from walk.persistence import Database, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerRepository

ALLOW = PermissionEffect.ALLOW
DENY = PermissionEffect.DENY
APPROVAL = PermissionEffect.REQUIRE_APPROVAL
DEV = AgentRole.SENIOR_DEV


def _rule(
    tool: str, effect: PermissionEffect, role: AgentRole = DEV, **fields: object
) -> PermissionRule:
    data: dict[str, object] = {"role": role, "tool": tool, "effect": effect, **fields}
    if effect is APPROVAL:
        data.setdefault("approver", Approver.USER)
    return PermissionRule.model_validate(data)


KERNEL = [
    _rule("bash", ALLOW, command_patterns=["^pytest"]),
    _rule("jira.close_feature", DENY),
    _rule("git.*", APPROVAL),
    _rule("jira.close_feature", ALLOW, role=AgentRole.QC),
]


@pytest.fixture
def manager(db: Database, fake_clock: FakeClock) -> DefaultPermissionManager:
    ids = IdSequenceStore(db)
    ledger = DefaultLedgerManager(db, LedgerRepository(db), ids, fake_clock)
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)
    return DefaultPermissionManager(
        KERNEL, [], ApprovalRepository(db), ledger, hooks, ids, fake_clock, project_key="DEMO"
    )


def test_rules_for_returns_the_role_kernel_rules(manager: DefaultPermissionManager) -> None:
    assert manager.rules_for(DEV) == KERNEL[:3]
    assert manager.rules_for(AgentRole.QC) == KERNEL[3:]
    assert manager.rules_for(AgentRole.ORCHESTRATOR) == []


def test_extra_rules_may_only_narrow(
    manager: DefaultPermissionManager, caplog: pytest.LogCaptureFixture
) -> None:
    widen = _rule("jira.close_feature", ALLOW)
    widen_glob = _rule("git.push", ALLOW)
    relax = _rule("jira.*", APPROVAL)
    narrow = _rule("read", ALLOW)
    deny = _rule("bash", DENY, command_patterns=["rm -rf"])
    with caplog.at_level(logging.WARNING, logger="walk.permissions.service"):
        rules = manager.rules_for(DEV, [widen, widen_glob, relax, narrow, deny])
    assert rules == [*KERNEL[:3], narrow, deny]
    assert sum("dropped" in record.getMessage() for record in caplog.records) == 3


def test_extra_rule_for_another_role_is_ignored(manager: DefaultPermissionManager) -> None:
    other = _rule("read", ALLOW, role=AgentRole.QC)
    assert manager.rules_for(DEV, [other]) == KERNEL[:3]


def test_rules_for_deduplicates(manager: DefaultPermissionManager) -> None:
    again = _rule("bash", ALLOW, command_patterns=["^dotnet"])
    read = _rule("read", ALLOW)
    rules = manager.rules_for(DEV, [read, read, again, KERNEL[1]])
    assert rules == [*KERNEL[:3], read]
