"""Workflow contracts: the §52 hierarchy, states and transition values (DOMAIN-MODEL §3, §4.1)."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field

from walk.common.ids import (
    ApprovedArtifactId,
    BugId,
    EpicId,
    EvidenceId,
    FeatureId,
    PhaseId,
    ProjectKey,
    ReleaseCandidateId,
    RunId,
    Sha,
    SkillName,
    WorkItemId,
)
from walk.common.models import FrozenModel, JsonDict, WalkModel, utcnow
from walk.common.roles import AgentRole
from walk.hooks.models import HookName
from walk.telemetry.models import EvidenceKind


class WorkItemKind(StrEnum):
    """Node kinds of the §52 hierarchy below `Project`."""

    EPIC = "EPIC"
    FEATURE = "FEATURE"
    STORY = "STORY"
    TASK = "TASK"
    BUG = "BUG"


class WorkItemState(StrEnum):
    """§53 states refined by §61, §58 BLOCKED and §93 CANCELLED.

    §61 splits REVIEW into READY_FOR_REVIEW + LEAD_DEV_REVIEW.

    Bug lifecycle (§64) maps onto the same enum: Triage=DISCOVERY, Assigned=READY,
    Fix=IMPLEMENTING, Review=READY_FOR_REVIEW/LEAD_DEV_REVIEW, Re-test=QC, Close=COMPLETE,
    Reopen=REWORK (ADR-0010).
    """

    IDEA = "IDEA"
    DISCOVERY = "DISCOVERY"
    DESIGN = "DESIGN"
    READY = "READY"
    BLOCKED = "BLOCKED"
    IMPLEMENTING = "IMPLEMENTING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    LEAD_DEV_REVIEW = "LEAD_DEV_REVIEW"
    INTEGRATION = "INTEGRATION"
    QC = "QC"
    REWORK = "REWORK"
    PHASE_REVIEW = "PHASE_REVIEW"
    USER_GATE = "USER_GATE"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"


class PhaseState(StrEnum):
    """§66-§72 phase lifecycle."""

    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    EVIDENCE_REVIEW = "EVIDENCE_REVIEW"  # §69 package being assembled
    USER_GATE = "USER_GATE"  # §68/§70 waiting for user
    REWORK = "REWORK"  # §71
    CHANGE_ANALYSIS = "CHANGE_ANALYSIS"  # §72
    COMPLETE = "COMPLETE"
    STOPPED = "STOPPED"


class PhaseDecision(StrEnum):
    """§70 user decisions at the Phase Gate."""

    GO = "GO"
    REWORK = "REWORK"
    CHANGE = "CHANGE"
    STOP = "STOP"


class ReleaseCandidateState(StrEnum):
    """§76."""

    BUILDING = "BUILDING"
    QC = "QC"
    REJECTED = "REJECTED"
    PASSED = "PASSED"
    RELEASED = "RELEASED"


class DoneDimension(StrEnum):
    """§6.5 Feature Done = sum of applicable dimensions."""

    FUNCTIONAL = "FUNCTIONAL"
    INTEGRATED = "INTEGRATED"
    DESIGN_VALIDATED = "DESIGN_VALIDATED"
    UX_COMPLETE = "UX_COMPLETE"
    ART_COMPLETE = "ART_COMPLETE"
    PERFORMANCE_ACCEPTABLE = "PERFORMANCE_ACCEPTABLE"
    TESTED = "TESTED"
    QC_ACCEPTED = "QC_ACCEPTED"


class Priority(StrEnum):
    """Work priority, P0 highest."""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class Risk(StrEnum):
    """Delivery risk of a work item."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Severity(StrEnum):
    """Bug severity (§10.8: QC identifies existence and severity)."""

    BLOCKER = "BLOCKER"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    TRIVIAL = "TRIVIAL"


class TransitionSource(StrEnum):
    """Who or what requested a transition."""

    AGENT = "AGENT"
    USER = "USER"
    KERNEL = "KERNEL"
    EXTERNAL = "EXTERNAL"  # Jira webhook / poll
    EXTERNAL_REJECTED = "EXTERNAL_REJECTED"


class Project(WalkModel):
    """Root aggregate (§52). One per game repository."""

    key: ProjectKey = Field(description="Project key, e.g. DEMO (prefix of nothing; unique).")
    name: str = Field(description="Human-readable project name.")
    repo_path: str = Field(description="Absolute path of the game repository root")
    gdd_paths: list[str] = Field(
        default_factory=list, description="GDD files relative to repo root (§48)"
    )
    default_branch: str = Field(default="main", description="Integration branch of the game.")
    protected_branches: list[str] = Field(
        default_factory=lambda: ["main", "release/*"],
        description="Branch patterns agents may never commit or push to directly.",
    )
    work_provider: Literal["local", "jira"] = Field(
        default="local", description="Work provider holding the external work items (§55)."
    )
    autonomy_level_max: int = Field(
        default=2,
        ge=0,
        le=3,
        description="Highest AutonomyLevel agents may resolve without user (§51, §140)",
    )
    current_phase_id: PhaseId | None = Field(default=None, description="Phase in progress.")
    created_at: datetime = Field(
        default_factory=utcnow, description="When the project was created."
    )
    paused: bool = Field(default=False, description="True while `walk pause` is in effect (§93).")


class GddRef(WalkModel):
    """Pointer into the GDD for traceability (§73)."""

    path: str = Field(description="GDD file relative to the repository root.")
    anchor: str | None = Field(default=None, description="Heading anchor inside the file.")
    requirement_id: str | None = Field(
        default=None, description="Normalised requirement id after GDD compile [Stage 6]"
    )


class Phase(WalkModel):
    """§66-§72."""

    id: PhaseId = Field(description="PHASE-NN.")
    project_key: ProjectKey = Field(description="Owning project.")
    ordinal: int = Field(ge=1, description="Position in the phase sequence, from 1.")
    name: str = Field(description="e.g. Prototype, Vertical Slice (§66)")
    state: PhaseState = Field(default=PhaseState.PLANNED, description="Lifecycle state.")
    goal: str = Field(default="", description="What the phase must prove.")
    scope_epic_ids: list[EpicId] = Field(
        default_factory=list, description="Approved scope (§67 boundary)"
    )
    exit_criteria: list[str] = Field(default_factory=list, description="Gate exit criteria.")
    gate_round: int = Field(
        default=0, description="Incremented each time the phase enters USER_GATE (§71 revalidation)"
    )
    baseline_artifact_id: ApprovedArtifactId | None = Field(
        default=None, description="PHASE_BASELINE approved artifact snapshot at start."
    )
    budget_id: str | None = Field(default=None, description="Phase budget, if allocated.")
    started_at: datetime | None = Field(default=None, description="When the phase became ACTIVE.")
    completed_at: datetime | None = Field(default=None, description="When it reached COMPLETE.")
    last_decision: PhaseDecision | None = Field(
        default=None, description="Most recent Phase Gate decision."
    )


class StoryContract(WalkModel):
    """§57 Executable Story Contract. Embedded in Story/Task/Bug."""

    goal: str = Field(description="Outcome the work must achieve.")
    source_requirements: list[GddRef] = Field(
        default_factory=list, description="GDD sections the work implements."
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list, description="Verifiable conditions of done."
    )
    constraints: list[str] = Field(default_factory=list, description="Known limits to respect.")
    dependencies: list[WorkItemId] = Field(
        default_factory=list, description="Items that must be COMPLETE first."
    )
    required_evidence: list[EvidenceKind] = Field(
        default_factory=list, description="Evidence kinds the work must produce."
    )
    owner_role: AgentRole = Field(default=AgentRole.SENIOR_DEV, description="Implementing role.")
    reviewer_role: AgentRole = Field(default=AgentRole.LEAD_DEV, description="Reviewing role.")
    required_skills: list[SkillName] = Field(default_factory=list, description="§29")
    risk: Risk = Field(default=Risk.MEDIUM, description="Delivery risk (§18 effort input).")
    priority: Priority = Field(default=Priority.P2, description="Scheduling priority.")
    complexity: Literal["TRIVIAL", "SMALL", "NORMAL", "LARGE", "CORE"] = Field(
        default="NORMAL", description="§18 task complexity input"
    )


class WorkItemBase(WalkModel):
    """Common fields of §52 hierarchy nodes. Persisted in `work_items`."""

    id: WorkItemId = Field(description="<PREFIX>-<n> allocated from id_sequences.")
    kind: WorkItemKind = Field(description="Discriminator of the WorkItem union.")
    project_key: ProjectKey = Field(description="Owning project.")
    title: str = Field(description="Short title.")
    description: str = Field(default="", description="Free-text description.")
    state: WorkItemState = Field(default=WorkItemState.IDEA, description="Workflow state.")
    state_version: int = Field(
        default=0, description="Optimistic concurrency + idempotency component"
    )
    parent_id: WorkItemId | None = Field(default=None, description="Parent in the hierarchy.")
    phase_id: PhaseId | None = Field(default=None, description="Phase the item is scoped to.")
    external_ref: str | None = Field(
        default=None, description="Jira key or local provider ref (§55)"
    )
    owner_role: AgentRole | None = Field(default=None, description="Role that owns the work.")
    assigned_run_id: RunId | None = Field(default=None, description="Agent run working on it.")
    priority: Priority = Field(default=Priority.P2, description="Scheduling priority.")
    risk: Risk = Field(default=Risk.MEDIUM, description="Delivery risk.")
    labels: list[str] = Field(default_factory=list, description="Free-form labels.")
    blocked_reason: str | None = Field(default=None, description="Why the item is BLOCKED.")
    fix_loops: int = Field(default=0, description="QC rejections so far (§138 circuit breaker)")
    branch: str | None = Field(default=None, description="Work branch in the game repository.")
    created_at: datetime = Field(default_factory=utcnow, description="When it was created.")
    updated_at: datetime = Field(default_factory=utcnow, description="Last state or field change.")
    completed_at: datetime | None = Field(default=None, description="When it reached COMPLETE.")


class Epic(WorkItemBase):
    """Top-level grouping of features (§52)."""

    kind: Literal[WorkItemKind.EPIC] = Field(default=WorkItemKind.EPIC, description="Always EPIC.")
    gdd_refs: list[GddRef] = Field(default_factory=list, description="GDD sections covered.")


class Feature(WorkItemBase):
    """§6.5: done only when applicable dimensions are complete."""

    kind: Literal[WorkItemKind.FEATURE] = Field(
        default=WorkItemKind.FEATURE, description="Always FEATURE."
    )
    gdd_refs: list[GddRef] = Field(default_factory=list, description="GDD sections covered.")
    applicable_dimensions: list[DoneDimension] = Field(
        default_factory=lambda: [
            DoneDimension.FUNCTIONAL,
            DoneDimension.INTEGRATED,
            DoneDimension.TESTED,
            DoneDimension.QC_ACCEPTED,
        ],
        description="Done dimensions that apply to this feature (§6.5).",
    )
    done_dimensions: dict[DoneDimension, bool] = Field(
        default_factory=dict, description="Dimension → completed."
    )
    context_path: str | None = Field(default=None, description=".ai/features/<id>.md")


class Story(WorkItemBase):
    """Implementable unit under a feature (§52, §57)."""

    kind: Literal[WorkItemKind.STORY] = Field(
        default=WorkItemKind.STORY, description="Always STORY."
    )
    contract: StoryContract = Field(description="Executable story contract (§57).")


class Task(WorkItemBase):
    """Technical unit under a feature (§52, §57)."""

    kind: Literal[WorkItemKind.TASK] = Field(default=WorkItemKind.TASK, description="Always TASK.")
    contract: StoryContract = Field(description="Executable story contract (§57).")


class Bug(WorkItemBase):
    """§64 bug workflow uses WorkItemState (ADR-0010)."""

    kind: Literal[WorkItemKind.BUG] = Field(default=WorkItemKind.BUG, description="Always BUG.")
    contract: StoryContract = Field(description="Fix contract; goal is the bug title.")
    severity: Severity = Field(default=Severity.MAJOR, description="QC-assessed severity.")
    found_in_run_id: RunId | None = Field(default=None, description="Run that found the bug.")
    found_against_commit: Sha | None = Field(default=None, description="Commit it was found on.")
    reproduction: str = Field(default="", description="Steps to reproduce.")
    expected: str = Field(default="", description="Expected behaviour.")
    observed: str = Field(default="", description="Observed behaviour.")
    related_feature_id: FeatureId | None = Field(
        default=None, description="Feature the bug belongs to."
    )
    reopen_count: int = Field(default=0, description="Times the bug was reopened.")
    context_path: str | None = Field(default=None, description=".ai/bugs/<id>.md")


WorkItem = Annotated[Epic | Feature | Story | Task | Bug, Field(discriminator="kind")]


class WorkItemTransition(FrozenModel):
    """Row in `work_item_transitions`; `seq` is the idempotency component for provider sync."""

    seq: int = Field(description="AUTOINCREMENT position of the transition.")
    work_item_id: WorkItemId = Field(description="Item that transitioned.")
    from_state: WorkItemState = Field(description="State before.")
    to_state: WorkItemState = Field(description="State after.")
    event: str = Field(description="Event that caused it.")
    source: TransitionSource = Field(description="Who requested it.")
    actor_role: AgentRole = Field(description="Role that raised the event.")
    run_id: RunId | None = Field(default=None, description="Run that raised it, if any.")
    reason: str | None = Field(default=None, description="Free-text reason.")
    at: datetime = Field(description="When it was committed.")


class ReleaseCandidate(WalkModel):
    """§76."""

    id: ReleaseCandidateId = Field(description="RC-NN.")
    project_key: ProjectKey = Field(description="Owning project.")
    number: int = Field(description="Sequential RC number.")
    state: ReleaseCandidateState = Field(
        default=ReleaseCandidateState.BUILDING, description="Lifecycle state."
    )
    commit: Sha = Field(description="Commit the candidate was built from.")
    build_evidence_ids: list[EvidenceId] = Field(
        default_factory=list, description="Build evidence."
    )
    qc_report_evidence_id: EvidenceId | None = Field(default=None, description="QC report.")
    rejection_bug_ids: list[BugId] = Field(
        default_factory=list, description="Bugs that rejected the candidate."
    )
    created_at: datetime = Field(default_factory=utcnow, description="When it was created.")


class WorkItemDraft(WalkModel):
    """§126 New Tasks — input to WorkflowManager.create.

    Also produced by agents in AgentOutput.new_tasks.
    """

    kind: WorkItemKind = Field(description="EPIC, FEATURE, STORY or TASK (bugs use BugDraft).")
    title: str = Field(description="Short title.")
    description: str = Field(description="Free-text description.")
    parent_id: WorkItemId | None = Field(default=None, description="Parent in the hierarchy.")
    contract: StoryContract | None = Field(
        default=None, description="Required for STORY/TASK; not allowed otherwise."
    )


class BugDraft(WalkModel):
    """§126 New Bugs (§63 QC authority) — input to WorkflowManager.create."""

    title: str = Field(description="Short title; becomes the contract goal.")
    severity: Severity = Field(description="QC-assessed severity.")
    reproduction: str = Field(description="Steps to reproduce.")
    expected: str = Field(description="Expected behaviour.")
    observed: str = Field(description="Observed behaviour.")
    related_feature_id: FeatureId | None = Field(
        default=None, description="Feature the bug belongs to."
    )
    evidence_ids: list[EvidenceId] = Field(
        default_factory=list, description="Evidence already recorded for the bug."
    )
    against_commit: Sha | None = Field(default=None, description="Commit the bug was found on.")


class TransitionContext(FrozenModel):
    """Facts supplied by the caller of a transition; guards read `payload` (WBS §3.4)."""

    actor_role: AgentRole = Field(description="Role raising the event.")
    source: TransitionSource = Field(description="Who requested the transition.")
    run_id: RunId | None = Field(default=None, description="Run raising the event, if any.")
    payload: JsonDict = Field(default_factory=dict, description="Guard facts by fixed key.")
    phase: Phase | None = Field(default=None, description="Phase in effect, if any.")


class GuardResult(FrozenModel):
    """Outcome of one guard."""

    ok: bool = Field(description="True when the guard passes.")
    reason: str = Field(default="", description="Why it failed; empty when ok.")


class Transition(FrozenModel):
    """One row of a transition table."""

    from_state: WorkItemState | Literal["*"] = Field(
        description="State the row applies to; '*' = any state not in excluded_states."
    )
    excluded_states: tuple[WorkItemState, ...] = Field(
        default=(), description="States a '*' row does not apply to ('* except A,B')."
    )
    event: str = Field(description="Event name.")
    to_state: WorkItemState | Literal["PREVIOUS"] = Field(
        description="Target state; 'PREVIOUS' = the payload resume_state (unblock)."
    )
    guards: tuple[str, ...] = Field(description="guard names (registered callables)")
    allowed_roles: tuple[AgentRole, ...] = Field(description="Roles that may raise the event.")
    hooks: tuple[HookName, ...] = Field(description="fired after commit, in order")
    effects: tuple[str, ...] = Field(
        default=(),
        description="Kernel mutations applied in the transition's transaction, e.g. "
        "increment_fix_loops.",
    )

    def applies_to(self, state: WorkItemState) -> bool:
        """Return whether the row's ``from`` side matches ``state``."""
        if self.from_state == "*":
            return state not in self.excluded_states
        return self.from_state == state


class TransitionTable(FrozenModel):
    """BehaviorVersion kind=WORKFLOW.

    Name in {'feature_workflow','story_workflow','bug_workflow','phase_workflow','rc_workflow'}.
    """

    name: str = Field(description="Table name, e.g. story_workflow.")
    version: str = Field(description="Behavior version, e.g. 1.0.")
    kinds: tuple[WorkItemKind, ...] = Field(
        default=(), description="Work-item kinds governed by the table (none for phase/RC)."
    )
    transitions: tuple[Transition, ...] = Field(description="Rows in evaluation order.")
