"""Role contracts and the §126 execution contract (§9, §12-§15, §22, §126).

DOMAIN-MODEL §4.2.

`EffortPolicy` and `BudgetPolicy` live in `walk.effort.models` / `walk.budgets.models`
(RELOCATE, WBS §3.2). `AgentOutputStatus` lives here rather than in `walk.runtime.models`
because `agents` may not import `runtime` (RELOCATE, E01-S18).
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from walk.budgets.models import Budget, BudgetPolicy
from walk.common.enums import Capability, Effort, ImprovementScope
from walk.common.ids import (
    DecisionId,
    EvidenceId,
    HandoverId,
    ModelId,
    RunId,
    Sha,
    SkillName,
    ToolName,
    WorkItemId,
)
from walk.common.models import FrozenModel, WalkModel, utcnow
from walk.common.roles import AgentRole
from walk.context.models import ContextBundle
from walk.debate.models import Debate, DebatePosition
from walk.decisions.models import (
    Authority,
    Decision,
    DecisionProposal,
    EscalationRequest,
    EscalationRule,
)
from walk.effort.models import EffortPolicy, EffortRequest
from walk.memory.models import ApprovedArtifact, ContextUpdate
from walk.permissions.models import PermissionRule
from walk.skills.models import Skill
from walk.telemetry.models import EvidenceDraft, EvidenceKind
from walk.tools.models import ToolSpec
from walk.workflow.models import BugDraft, Phase, WorkItem, WorkItemDraft, WorkItemState


class Constitution(WalkModel):
    """§12 Agent Constitution — model-independent.

    Loaded from kernel defaults `walk/agents/defaults/<role>.md` merged with project overrides
    `.ai/agents/roles/<role>.md` (ADR-0013).
    """

    role: AgentRole = Field(description="Role the constitution defines.")
    version: str = Field(description="BehaviorVersion string, e.g. '1.3' (§105)")
    identity: str = Field(description="Display identity, e.g. 'Lead Developer'")
    mission: str = Field(description="Primary objective.")
    responsibilities: list[str] = Field(description="What the role is accountable for.")
    authority: Authority = Field(description="Decision scope and autonomy bounds.")
    professional_bias: str = Field(description="What this role optimises (§6.7)")
    core_beliefs: list[str] = Field(description="Beliefs that shape its judgement.")
    decision_principles: list[str] = Field(description="How it decides.")
    risk_tolerance: Literal["VERY_LOW", "LOW", "MEDIUM", "HIGH"] = Field(
        default="MEDIUM", description="Appetite for risk."
    )
    preferred_evidence: list[EvidenceKind] = Field(description="Evidence it trusts most.")
    conflict_behavior: str = Field(description="How it behaves in disagreements.")
    escalation_rules: list[EscalationRule] = Field(description="When it must escalate.")
    tool_permissions: list[PermissionRule] = Field(
        description="Permission rules of the role (ADR-0006)."
    )
    forbidden_actions: list[str] = Field(description="Actions the role must never take.")
    body_markdown: str = Field(
        default="", description="Free-form guidance sections rendered into the system prompt"
    )


class ModelPolicy(WalkModel):
    """§14."""

    preferred: list[ModelId] = Field(description="Preferred model families or ids, in order.")
    fallback: list[ModelId] = Field(default_factory=list, description="Fallbacks, in order.")
    restricted: list[ModelId] = Field(default_factory=list, description="Never use for this role")
    required_capabilities: list[Capability] = Field(
        default_factory=list, description="Capabilities a candidate model must have."
    )
    cross_model_review: bool = Field(
        default=True, description="§23 prefer reviewer model != implementer model"
    )
    allow_task_override: bool = Field(
        default=True, description="Whether a task may override the model choice."
    )


class RuntimePolicy(WalkModel):
    """§13 how a role executes. From `.ai/agents/policies.yaml` merged over kernel defaults."""

    role: AgentRole = Field(description="Role the policy applies to.")
    version: str = Field(description="BehaviorVersion string.")
    model_policy: ModelPolicy = Field(description="Model selection policy.")
    effort_policy: EffortPolicy = Field(description="Effort resolution inputs.")
    budget_policy: BudgetPolicy = Field(description="Per-role budget defaults.")
    default_skills: list[SkillName] = Field(
        default_factory=list, description="Skills every run of the role receives."
    )
    allowed_tools: list[ToolName] = Field(
        default_factory=list, description="Tools the role may be given."
    )
    execution_strategy: Literal["single_run", "plan_then_execute", "review_only"] = Field(
        default="single_run", description="How a task is executed."
    )
    max_parallel_runs: int = Field(default=1, description="Concurrent runs of the role.")
    checkpoint_every_tool_calls: int = Field(
        default=10, description="Periodic checkpoint interval in tool calls."
    )
    allowed_paths: list[str] = Field(
        default_factory=lambda: ["**"],
        description="Worktree globs the role may change (boundary audit); [] = none (E02-S14).",
    )


class AgentInstance(WalkModel):
    """§9 Agent Instance.

    = constitution + authority + policy + model + effort + budget + skills + tools +
    permissions + context.
    """

    role: AgentRole = Field(description="Role of the instance.")
    constitution: Constitution = Field(description="Merged constitution.")
    runtime_policy: RuntimePolicy = Field(description="Merged runtime policy.")
    skills: list[SkillName] = Field(description="Skills given to the run.")
    tools: list[ToolName] = Field(description="Tools given to the run.")
    permissions: list[PermissionRule] = Field(description="Effective permission rules.")
    model_id: ModelId = Field(description="Model chosen by the router.")
    effort: Effort = Field(description="Effective effort.")
    budget_ids: list[str] = Field(description="Budgets metered by the run.")


class AgentOutputStatus(StrEnum):
    """§126 Output.Status (DOMAIN-MODEL §3; RELOCATE from walk.runtime.models, E01-S18)."""

    COMPLETED = "COMPLETED"  # task done per contract; triggers forward transition
    PARTIAL = "PARTIAL"  # progress made; needs another run (budget/time) — handover required
    BLOCKED = "BLOCKED"  # cannot proceed; escalations[] must be non-empty
    FAILED = "FAILED"
    NEEDS_INPUT = "NEEDS_INPUT"  # question for authority/user; escalations[] non-empty
    REJECTED = "REJECTED"  # reviewer/QC verdict: send back (REWORK)
    APPROVED = "APPROVED"  # reviewer/QC verdict: pass


class ToolCallSummary(FrozenModel):
    """Tool usage of a run, per tool."""

    tool: ToolName = Field(description="Tool name.")
    count: int = Field(description="Calls made.")
    denied: int = Field(default=0, description="Calls the permission system denied.")


class Finding(WalkModel):
    """§126 Findings — facts discovered, with evidence pointers."""

    summary: str = Field(description="One-line fact.")
    detail: str = Field(default="", description="Elaboration.")
    evidence_ids: list[EvidenceId] = Field(default_factory=list, description="Supporting evidence.")
    affected_files: list[str] = Field(default_factory=list, description="Files concerned.")
    severity: Literal["INFO", "WARNING", "RISK"] = Field(default="INFO", description="Weight.")


class FileChange(WalkModel):
    """§126 Changes — kernel verifies against git diff (ADR-0006 §D-2)."""

    path: str = Field(description="Repository-relative path.")
    change: Literal["ADDED", "MODIFIED", "DELETED", "RENAMED"] = Field(description="Change kind.")
    summary: str = Field(default="", description="What changed.")


class NextAction(WalkModel):
    """§126 Next Actions."""

    description: str = Field(description="What should happen next.")
    role: AgentRole | None = Field(default=None, description="Role that should do it.")
    blocked_on: str | None = Field(default=None, description="What it waits for, if anything.")


class Handover(WalkModel):
    """§22 structured handover — part of the agent execution contract.

    Used as AgentInput.handover / AgentOutput.handover. Persisted in `handovers`
    (runtime.CheckpointManager) and rendered to `.ai/handovers/HO-NNNN.md` through
    `walk.agents.handover.to_document()` → MemoryManager.write_handover(MemoryDocument).
    No chain-of-thought (ADR-0004).
    """

    id: HandoverId = Field(description="HO-<n>.")
    work_item_id: WorkItemId = Field(description="Work item handed over.")
    role: AgentRole = Field(description="Role of the run that hands over.")
    from_run_id: RunId = Field(description="Run that hands over.")
    from_model_id: ModelId = Field(description="Model of that run.")
    to_run_id: RunId | None = Field(default=None, description="Run that continues, once known.")
    reason: Literal["FALLBACK", "PAUSE", "BUDGET", "PARTIAL", "REASSIGN", "RECOVERY"] = Field(
        description="Why the work is handed over (§22)."
    )
    task_summary: str = Field(description="Task")
    current_state: str = Field(description="Current State")
    completed_work: list[str] = Field(description="Completed Work")
    modified_files: list[str] = Field(description="Modified Files")
    findings: list[Finding] = Field(description="Findings")
    hypotheses: list[str] = Field(description="Hypotheses")
    decisions: list[DecisionId] = Field(description="Decisions (ids of recorded decisions)")
    proposed_decisions: list[DecisionProposal] = Field(
        default_factory=list, description="Decision proposals not yet recorded."
    )
    risks: list[str] = Field(description="Risks")
    remaining_work: list[str] = Field(description="Remaining Work")
    next_action: str = Field(description="Next Action")
    worktree_head: Sha = Field(description="HEAD of the worktree at handover.")
    branch: str = Field(description="Work branch.")
    created_at: datetime = Field(default_factory=utcnow, description="When it was built.")


class ObservationDraft(WalkModel):
    """§96 improvement observation from within a run."""

    observed: str = Field(description="What was observed.")
    potential_cause: str = Field(description="Likely cause.")
    possible_improvement: str = Field(description="What could improve.")
    scope: ImprovementScope = Field(description="What kind of behavior could change.")


class ExpectedOutput(WalkModel):
    """§126 Expected Output: what the run must produce."""

    status_options: list[AgentOutputStatus] = Field(description="Statuses the run may report.")
    deliverables: list[str] = Field(
        description="e.g. 'technical design section in FEAT-0012', 'passing EditMode tests'"
    )
    required_evidence: list[EvidenceKind] = Field(description="Evidence the run must produce.")
    output_schema_ref: str = Field(
        default="walk.agents.models.AgentOutput", description="Model the output must match."
    )


class AgentInput(WalkModel):
    """§126 structured input — every listed field present."""

    run_id: RunId = Field(description="Run the input is for.")
    role: AgentRole = Field(description="Agent Role")
    constitution: Constitution = Field(description="Constitution")
    authority: Authority = Field(description="Authority")
    task: WorkItem = Field(description="Task")
    workflow_state: WorkItemState = Field(description="Workflow State")
    phase: Phase | None = Field(description="Phase scope (§67).")
    context: ContextBundle = Field(description="Relevant Context")
    approved_artifacts: list[ApprovedArtifact] = Field(description="Approved Artifacts")
    decisions: list[Decision] = Field(description="Relevant Decisions")
    skills: list[Skill] = Field(description="Available Skills")
    allowed_tools: list[ToolSpec] = Field(description="Allowed Tools")
    permissions: list[PermissionRule] = Field(description="Permissions")
    budget: list[Budget] = Field(description="Budget (TASK + ROLE scope rows)")
    effort: Effort = Field(description="Effort")
    required_evidence: list[EvidenceKind] = Field(description="Required Evidence")
    expected_output: ExpectedOutput = Field(description="Expected Output")
    handover: Handover | None = Field(
        default=None, description="Present on fallback/resume (§22, §132)."
    )
    worktree_path: str = Field(description="Worktree the run executes in.")
    branch: str = Field(description="Work branch of the worktree.")
    debate: Debate | None = Field(
        default=None, description="Present when the run is a debate turn."
    )
    instructions_markdown: str = Field(
        default="", description="Rendered task prompt (kernel-owned template, versioned)"
    )


class AgentOutput(WalkModel):
    """§126 structured output — every listed field present. Persisted (never chain-of-thought).

    Validation (E01-S18): PARTIAL needs ``handover``; BLOCKED and NEEDS_INPUT need
    ``escalations``; an empty ``context_updates`` needs ``no_context_change_reason`` unless the
    status is FAILED.
    """

    status: AgentOutputStatus = Field(description="Status")
    result: str = Field(description="Result (summary, markdown)")
    findings: list[Finding] = Field(default_factory=list, description="Findings")
    changes: list[FileChange] = Field(default_factory=list, description="Changes")
    decisions: list[DecisionProposal] = Field(
        default_factory=list, description="Decisions (proposals)"
    )
    evidence: list[EvidenceDraft] = Field(default_factory=list, description="Evidence")
    context_updates: list[ContextUpdate] = Field(
        default_factory=list, description="Context Updates"
    )
    new_tasks: list[WorkItemDraft] = Field(default_factory=list, description="New Tasks")
    new_bugs: list[BugDraft] = Field(default_factory=list, description="New Bugs")
    escalations: list[EscalationRequest] = Field(default_factory=list, description="Escalations")
    next_actions: list[NextAction] = Field(default_factory=list, description="Next Actions")
    handover: Handover | None = Field(default=None, description="Required when status is PARTIAL")
    effort_request: EffortRequest | None = Field(
        default=None, description="§19 dynamic effort change."
    )
    debate_position: DebatePosition | None = Field(
        default=None, description="§45 position when the run is a debate turn."
    )
    observations: list[ObservationDraft] = Field(
        default_factory=list, description="§96 improvement observations."
    )
    no_context_change_reason: str | None = Field(
        default=None, description="Required if context_updates is empty and status != FAILED"
    )

    @model_validator(mode="after")
    def _status_rules(self) -> Self:
        if self.status is AgentOutputStatus.PARTIAL and self.handover is None:
            msg = "handover is required when status is PARTIAL"
            raise ValueError(msg)
        needs_escalation = {AgentOutputStatus.BLOCKED, AgentOutputStatus.NEEDS_INPUT}
        if self.status in needs_escalation and not self.escalations:
            msg = f"escalations must not be empty when status is {self.status.value}"
            raise ValueError(msg)
        if (
            not self.context_updates
            and self.status is not AgentOutputStatus.FAILED
            and not self.no_context_change_reason
        ):
            msg = "no_context_change_reason is required when context_updates is empty"
            raise ValueError(msg)
        return self
