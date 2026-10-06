"""Decision and authority contracts (§44, §50-§51; DOMAIN-MODEL §3 decision enums, §4.8).

The "Authority" half of the §7 "Debate / Decision / Authority" layer lives here; the
decisions service arrives in E04-S05.
"""

from datetime import datetime
from enum import IntEnum, StrEnum

from pydantic import Field

from walk.common.ids import (
    ApprovalRequestId,
    DebateId,
    DecisionId,
    EvidenceId,
    ModelId,
    RunId,
    WorkItemId,
)
from walk.common.models import WalkModel, utcnow
from walk.common.roles import AgentRole
from walk.workflow.models import WorkItemKind


class DecisionCategory(StrEnum):
    """§44."""

    TECH = "TECH"
    DESIGN = "DESIGN"
    ART = "ART"
    PRODUCT = "PRODUCT"
    QUALITY = "QUALITY"
    RELEASE = "RELEASE"
    PROCESS = "PROCESS"  # kernel-added: improvement decisions (§106)


class DecisionStatus(StrEnum):
    """Lifecycle of a decision record."""

    PROPOSED = "PROPOSED"  # an opinion (Invariant 5)
    ACCEPTED = "ACCEPTED"  # recorded by an authority
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"
    OVERRIDDEN = "OVERRIDDEN"  # by user (§93)


class AutonomyLevel(IntEnum):
    """§51."""

    LOCAL = 0  # agent decides
    MULTI_AGENT = 1  # debate resolves
    PO = 2  # PO resolves
    USER = 3  # user resolves (incl. Phase Gate)


class Authority(WalkModel):
    """§12 Authority + §51 autonomy bounds. Embedded in Constitution."""

    decision_scope: list[DecisionCategory] = Field(
        default_factory=list, description="Categories this role may ACCEPT decisions in"
    )
    max_autonomy_level: AutonomyLevel = Field(
        default=AutonomyLevel.LOCAL, description="Highest level the role may resolve itself."
    )
    may_approve: list[str] = Field(
        default_factory=list,
        description=(
            "ApprovedArtifactKind / review kinds this role may approve, "
            "e.g. 'review.approve', 'ART_DIRECTION'"
        ),
    )
    may_reject: list[str] = Field(default_factory=list, description="Kinds it may reject.")
    may_create_work: list[WorkItemKind] = Field(
        default_factory=list, description="Work-item kinds it may create."
    )


class EscalationRule(WalkModel):
    """§12 Escalation Rules: when a role must escalate instead of deciding."""

    condition: str = Field(
        description="Human-readable trigger, e.g. 'core gameplay change' (§51 Level 3 list)"
    )
    to_level: AutonomyLevel = Field(description="Level the question goes to.")
    category: DecisionCategory | None = Field(default=None, description="Decision category.")


class DecisionProposal(WalkModel):
    """§126 Decisions as *proposals* (Invariant 5). Input to DecisionManager.propose."""

    category: DecisionCategory = Field(description="Decision category.")
    topic: str = Field(description="What is being decided.")
    position: str = Field(description="Proposed outcome.")
    rationale: str = Field(description="Why.")
    alternatives: list[str] = Field(default_factory=list, description="Options considered.")
    evidence_ids: list[EvidenceId] = Field(default_factory=list, description="Supporting evidence.")
    autonomy_level: AutonomyLevel = Field(description="Level the proposer believes applies.")
    affected_systems: list[str] = Field(default_factory=list, description="Systems touched.")


class EscalationRequest(WalkModel):
    """§126 Escalations. Input to DecisionManager.escalate."""

    to_level: AutonomyLevel = Field(description="Level asked to decide.")
    category: DecisionCategory = Field(description="Decision category.")
    question: str = Field(description="What must be decided.")
    options: list[str] = Field(default_factory=list, description="Options on the table.")
    recommendation: str | None = Field(default=None, description="The requester's preference.")
    evidence_ids: list[EvidenceId] = Field(default_factory=list, description="Supporting evidence.")


class DecisionPosition(WalkModel):
    """A participant's position inside a Decision record (§44 'positions')."""

    role: AgentRole = Field(description="Participant role.")
    model_id: ModelId | None = Field(description="Model that argued it, if any.")
    position: str = Field(description="The position.")
    confidence: float = Field(ge=0, le=1, description="Self-reported confidence 0..1.")


class Decision(WalkModel):
    """§44 decision record. `.ai/decisions/DEC-NNNN.md` + `decisions` table."""

    id: DecisionId = Field(description="DEC-<n>.")
    category: DecisionCategory = Field(description="Decision category.")
    status: DecisionStatus = Field(description="Lifecycle status.")
    topic: str = Field(description="Topic.")
    participants: list[AgentRole] = Field(description="Participants.")
    positions: list[DecisionPosition] = Field(description="Positions.")
    evidence_ids: list[EvidenceId] = Field(description="Evidence.")
    outcome: str = Field(description="Final outcome.")
    owner: AgentRole = Field(description="Who decided (authority or USER).")
    rationale: str = Field(description="Rationale.")
    alternatives: list[str] = Field(description="Alternatives.")
    affected_systems: list[str] = Field(description="Affected systems.")
    related_work_items: list[WorkItemId] = Field(description="Related work.")
    autonomy_level: AutonomyLevel = Field(description="Level that decided.")
    debate_id: DebateId | None = Field(default=None, description="Debate that produced it.")
    version: int = Field(default=1, description="Record version.")
    supersedes: DecisionId | None = Field(default=None, description="Decision it replaces.")
    decided_at: datetime = Field(default_factory=utcnow, description="When it was decided.")
    overridden_by_user_at: datetime | None = Field(
        default=None, description="When the user overrode it (§93)."
    )


class Escalation(WalkModel):
    """§50 escalation instance routed by DecisionManager."""

    id: str = Field(description="Escalation id.")
    from_role: AgentRole = Field(description="Role that escalated.")
    to_level: AutonomyLevel = Field(description="Level asked to decide.")
    category: DecisionCategory = Field(description="Decision category.")
    question: str = Field(description="What must be decided.")
    options: list[str] = Field(description="Options on the table.")
    recommendation: str | None = Field(description="The requester's preference.")
    evidence_ids: list[EvidenceId] = Field(description="Supporting evidence.")
    work_item_id: WorkItemId | None = Field(description="Work item concerned.")
    run_id: RunId | None = Field(description="Run that escalated.")
    approval_request_id: ApprovalRequestId | None = Field(
        default=None, description="Approval request created for it, if any."
    )
    resolved_decision_id: DecisionId | None = Field(
        default=None, description="Decision that resolved it."
    )
    created_at: datetime = Field(default_factory=utcnow, description="When it was raised.")
