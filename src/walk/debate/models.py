"""Debate contracts (DOMAIN-MODEL §3 `DebateState`, §4.8; §45-§46).

Created by E01-S18 because `AgentInput.debate` and `AgentOutput.debate_position` embed them;
the debate service arrives in Epic 05.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from walk.common.ids import DebateId, DecisionId, EvidenceId, ModelId, RunId, WorkItemId
from walk.common.models import WalkModel, utcnow
from walk.common.roles import AgentRole
from walk.decisions.models import DecisionCategory


class DebateState(StrEnum):
    """§46."""

    OPEN = "OPEN"
    IN_ROUND = "IN_ROUND"
    CONSENSUS_CHECK = "CONSENSUS_CHECK"
    ESCALATED_PO = "ESCALATED_PO"
    ESCALATED_USER = "ESCALATED_USER"
    RESOLVED = "RESOLVED"
    ABANDONED = "ABANDONED"  # budget/round limit without authority available


class DebatePosition(WalkModel):
    """§45 one position in one round."""

    debate_id: DebateId = Field(description="Debate the position belongs to.")
    round: int = Field(description="Round number, starting at 1.")
    role: AgentRole = Field(description="Role that holds the position.")
    model_id: ModelId = Field(description="Model that argued it.")
    run_id: RunId = Field(description="Run that produced it.")
    position: str = Field(description="The position.")
    reasoning: str = Field(description="Why the role holds it.")
    evidence_ids: list[EvidenceId] = Field(description="Supporting evidence.")
    cost: str = Field(description="Cost assessment in words / numbers")
    risk: str = Field(description="Risk assessment.")
    alternative: str = Field(description="Best alternative the role sees.")
    confidence: float = Field(ge=0, le=1, description="Confidence between 0 and 1.")
    changed_from_previous: bool = Field(default=False, description="§45 agents may change opinion")
    at: datetime = Field(default_factory=utcnow, description="When it was stated.")


class Debate(WalkModel):
    """§46 lifecycle. Persisted in `debates` + `debate_positions`."""

    id: DebateId = Field(description="DEB-<n>.")
    topic: str = Field(description="What is debated.")
    category: DecisionCategory = Field(description="Decision category at stake.")
    state: DebateState = Field(default=DebateState.OPEN, description="Lifecycle state.")
    participants: list[AgentRole] = Field(description="Roles taking part.")
    opened_by: AgentRole = Field(description="Role that opened the debate.")
    work_item_id: WorkItemId | None = Field(description="Work item concerned, if any.")
    round: int = Field(default=0, description="Current round.")
    max_rounds: int = Field(default=3, description="Round limit (§138).")
    budget_id: str | None = Field(default=None, description="Budget metering the debate.")
    consensus_threshold: float = Field(
        default=0.75, description="Fraction of participants whose final positions agree"
    )
    final_positions: list[DebatePosition] = Field(
        default_factory=list, description="Positions of the last round."
    )
    decision_id: DecisionId | None = Field(default=None, description="Decision it produced.")
    opened_at: datetime = Field(default_factory=utcnow, description="When it was opened.")
    resolved_at: datetime | None = Field(default=None, description="When it was resolved.")
