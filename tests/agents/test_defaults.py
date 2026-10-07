from pathlib import Path

import pytest

import walk.agents
from walk.agents import ConstitutionLoader, PolicyLoader
from walk.common.roles import AgentRole
from walk.decisions import AutonomyLevel, DecisionCategory
from walk.permissions import PermissionEffect
from walk.workflow import WorkItemKind

DEFAULTS = Path(walk.agents.__file__).resolve().parent / "defaults"
MVP_ROLES = [AgentRole.ORCHESTRATOR, AgentRole.LEAD_DEV, AgentRole.SENIOR_DEV, AgentRole.QC]
D3_SECTIONS = [
    "Identity",
    "Mission",
    "Responsibilities",
    "Authority",
    "Professional Bias",
    "Core Beliefs",
    "Decision Principles",
    "Risk Tolerance",
    "Preferred Evidence",
    "Conflict Behavior",
    "Escalation Rules",
    "Forbidden Actions",
]
# ADR-0011 D-3 (families); GAME_DIRECTOR and PROCESS_ARCHITECT follow the opus/codex default.
FAMILIES = {
    AgentRole.ORCHESTRATOR: ("claude/opus", "codex/default"),
    AgentRole.PRODUCT_OWNER: ("claude/opus", "codex/default"),
    AgentRole.DESIGN_LEADER: ("claude/opus", "codex/default"),
    AgentRole.ART_DIRECTOR: ("claude/opus", "codex/default"),
    AgentRole.UA_RELEASE: ("claude/opus", "codex/default"),
    AgentRole.SCRUM_MASTER: ("claude/sonnet", "claude/opus"),
    AgentRole.LEAD_DEV: ("claude/opus", "codex/default"),
    AgentRole.SENIOR_DEV: ("codex/default", "claude/opus"),
    AgentRole.QC: ("claude/sonnet", "codex/default"),
    AgentRole.GAME_DIRECTOR: ("claude/opus", "codex/default"),
    AgentRole.PROCESS_ARCHITECT: ("claude/opus", "codex/default"),
}


@pytest.fixture
def constitutions() -> ConstitutionLoader:
    return ConstitutionLoader(DEFAULTS, None)


def test_default_constitutions_load(constitutions: ConstitutionLoader) -> None:
    for role in MVP_ROLES:
        constitution = constitutions.load(role)
        assert constitution.role is role
        assert constitution.version == "1.0"
        headings = [
            line[3:] for line in constitution.body_markdown.splitlines() if line.startswith("## ")
        ]
        assert headings == D3_SECTIONS, role
        assert all(rule.role is role for rule in constitution.tool_permissions)


def test_default_authorities_match_adr(constitutions: ConstitutionLoader) -> None:
    lead = constitutions.load(AgentRole.LEAD_DEV).authority
    assert lead.decision_scope == [DecisionCategory.TECH]
    assert lead.max_autonomy_level is AutonomyLevel.MULTI_AGENT
    assert lead.may_approve == ["review.approve", "ARCHITECTURE_DIRECTION"]
    assert constitutions.load(AgentRole.QC).authority.may_create_work == [WorkItemKind.BUG]
    senior = constitutions.load(AgentRole.SENIOR_DEV)
    assert senior.authority.max_autonomy_level == 0
    denied = {r.tool for r in senior.tool_permissions if r.effect is PermissionEffect.DENY}
    assert {"git.merge_protected", "jira.close_feature", "review.approve"} <= denied
    merge = [
        r
        for r in constitutions.load(AgentRole.LEAD_DEV).tool_permissions
        if r.tool == "git.merge_protected"
    ]
    assert [(r.effect, r.approver) for r in merge] == [(PermissionEffect.REQUIRE_APPROVAL, "USER")]


def test_default_policies_match_adr_0011() -> None:
    policies = PolicyLoader(DEFAULTS / "policies.yaml", None)
    for role, (preferred, fallback) in FAMILIES.items():
        policy = policies.load(role)
        assert policy.role is role
        assert (policy.model_policy.preferred, policy.model_policy.fallback) == (
            [preferred],
            [fallback],
        ), role
        assert policy.version == ("1.1" if role is AgentRole.QC else "1.0")  # QC: E02-S14
    assert policies.load(AgentRole.QC).model_policy.cross_model_review is True
    assert policies.load(AgentRole.QC).allowed_paths == []
    assert policies.load(AgentRole.SENIOR_DEV).checkpoint_every_tool_calls == 10
