import pytest
from pydantic import ValidationError

from walk.agents import (
    AgentInput,
    AgentOutput,
    AgentOutputStatus,
    FileChange,
    Handover,
    NextAction,
    ObservationDraft,
    ToolCallSummary,
    render_input_sections,
)
from walk.common.enums import ImprovementScope
from walk.common.roles import AgentRole
from walk.debate import Debate, DebatePosition, DebateState
from walk.decisions import AutonomyLevel, DecisionCategory, EscalationRequest
from walk.memory import ContextUpdate

UPDATE = ContextUpdate(
    doc_id="FEAT-0001", section="Implementation Notes", operation="APPEND", content_markdown="x"
)
ESCALATION = EscalationRequest(
    to_level=AutonomyLevel.PO, category=DecisionCategory.PRODUCT, question="Which speed?"
)


def test_partial_requires_handover(handover: Handover) -> None:
    with pytest.raises(ValidationError, match="handover"):
        AgentOutput(status=AgentOutputStatus.PARTIAL, result="half", context_updates=[UPDATE])

    output = AgentOutput(
        status=AgentOutputStatus.PARTIAL, result="half", context_updates=[UPDATE], handover=handover
    )
    assert output.handover == handover


def test_blocked_requires_escalation() -> None:
    for status in (AgentOutputStatus.BLOCKED, AgentOutputStatus.NEEDS_INPUT):
        with pytest.raises(ValidationError, match="escalations"):
            AgentOutput(status=status, result="stuck", no_context_change_reason="nothing learned")

    output = AgentOutput(
        status=AgentOutputStatus.BLOCKED,
        result="stuck",
        escalations=[ESCALATION],
        no_context_change_reason="nothing learned",
    )
    assert output.escalations == [ESCALATION]


def test_empty_context_updates_requires_reason() -> None:
    with pytest.raises(ValidationError, match="no_context_change_reason"):
        AgentOutput(status=AgentOutputStatus.COMPLETED, result="done")

    reasoned = AgentOutput(
        status=AgentOutputStatus.COMPLETED, result="done", no_context_change_reason="pure refactor"
    )
    failed = AgentOutput(status=AgentOutputStatus.FAILED, result="crashed")
    assert reasoned.no_context_change_reason == "pure refactor"
    assert failed.context_updates == []


def test_agent_output_round_trip_with_extras() -> None:
    output = AgentOutput(
        status=AgentOutputStatus.APPROVED,
        result="Looks good",
        changes=[FileChange(path="Assets/A.cs", change="MODIFIED")],
        next_actions=[NextAction(description="Merge", role=None)],
        observations=[
            ObservationDraft(
                observed="slow tests",
                potential_cause="no cache",
                possible_improvement="cache",
                scope=ImprovementScope.WORKFLOW,
            )
        ],
        context_updates=[UPDATE],
    )

    assert AgentOutput.model_validate_json(output.model_dump_json()) == output
    with pytest.raises(ValidationError):
        AgentOutput.model_validate({**output.model_dump(mode="json"), "thinking": "secret"})
    assert ToolCallSummary(tool="bash", count=3).denied == 0


def test_agent_input_round_trip(agent_input: AgentInput) -> None:
    section_fields = [
        "role",
        "constitution",
        "authority",
        "task",
        "workflow_state",
        "context",
        "approved_artifacts",
        "decisions",
        "skills",
        "allowed_tools",
        "permissions",
        "budget",
        "effort",
        "required_evidence",
        "expected_output",
        "handover",
    ]
    dumped = agent_input.model_dump(mode="json")

    assert all(name in dumped for name in section_fields)
    assert AgentInput.model_validate_json(agent_input.model_dump_json()) == agent_input
    assert agent_input.expected_output.output_schema_ref == "walk.agents.models.AgentOutput"
    with pytest.raises(ValidationError):
        AgentInput.model_validate({**dumped, "legacy_field": 1})


def test_debate_turn_round_trips(agent_input: AgentInput) -> None:
    position = DebatePosition(
        debate_id="DEB-0001",
        round=1,
        role=AgentRole.LEAD_DEV,
        model_id="codex/default",
        run_id="RUN-01J00000000000000000000002",
        position="Use a state machine",
        reasoning="Predictable",
        evidence_ids=[],
        cost="low",
        risk="low",
        alternative="flags",
        confidence=0.8,
    )
    debate = Debate(
        id="DEB-0001",
        topic="Movement architecture",
        category=DecisionCategory.TECH,
        participants=[AgentRole.LEAD_DEV, AgentRole.SENIOR_DEV],
        opened_by=AgentRole.ORCHESTRATOR,
        work_item_id="FEAT-0001",
        final_positions=[position],
    )
    turn = agent_input.model_copy(update={"debate": debate})
    output = AgentOutput(
        status=AgentOutputStatus.COMPLETED,
        result="position stated",
        debate_position=position,
        no_context_change_reason="debate only",
    )

    assert AgentInput.model_validate_json(turn.model_dump_json()) == turn
    assert AgentOutput.model_validate_json(output.model_dump_json()) == output
    assert debate.state is DebateState.OPEN
    assert "### Debate" in render_input_sections(turn)
    with pytest.raises(ValidationError):
        DebatePosition.model_validate({**position.model_dump(), "confidence": 2.0})
