import pytest
from pydantic import ValidationError

from walk.common.roles import AgentRole
from walk.decisions import (
    Authority,
    AutonomyLevel,
    DecisionCategory,
    DecisionPosition,
    EscalationRule,
)
from walk.workflow import WorkItemKind


def test_autonomy_levels_ordered() -> None:
    assert AutonomyLevel.USER > AutonomyLevel.PO > AutonomyLevel.MULTI_AGENT > AutonomyLevel.LOCAL
    assert [int(level) for level in AutonomyLevel] == [0, 1, 2, 3]
    assert AutonomyLevel(2) is AutonomyLevel.PO


def test_authority_defaults_and_parsing() -> None:
    assert Authority().max_autonomy_level is AutonomyLevel.LOCAL
    authority = Authority.model_validate(
        {"decision_scope": ["TECH"], "max_autonomy_level": 1, "may_create_work": ["BUG"]}
    )
    assert authority.decision_scope == [DecisionCategory.TECH]
    assert authority.max_autonomy_level is AutonomyLevel.MULTI_AGENT
    assert authority.may_create_work == [WorkItemKind.BUG]
    rule = EscalationRule.model_validate({"condition": "x", "to_level": 3})
    assert rule.to_level is AutonomyLevel.USER
    assert rule.category is None


def test_decision_position_confidence_is_bounded() -> None:
    with pytest.raises(ValidationError):
        DecisionPosition(role=AgentRole.QC, model_id=None, position="no", confidence=1.5)
