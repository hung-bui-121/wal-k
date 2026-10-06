"""Runtime contracts: runs, checkpoints and applied output effects (DOMAIN-MODEL §3, §4.11).

`AgentOutputStatus` lives in `walk.agents.models` (RELOCATE, E01-S18) and is re-exported here.
`AppliedEffects` comes from INTERFACES §1.13 (WBS §3.2).
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from walk.agents.models import AgentOutput, AgentOutputStatus
from walk.budgets.models import BudgetDimension
from walk.common.enums import Effort
from walk.common.ids import (
    CheckpointId,
    DecisionId,
    EvidenceId,
    HandoverId,
    ModelId,
    ProjectKey,
    RunId,
    Sha,
    WorkItemId,
)
from walk.common.models import FrozenModel, WalkModel
from walk.common.roles import AgentRole
from walk.context.models import ContextBundleRef
from walk.model_router.models import ProviderSessionRef
from walk.workflow.models import WorkItemState

__all__ = [
    "AgentOutputStatus",
    "AgentRun",
    "AgentRunState",
    "AppliedEffects",
    "Checkpoint",
    "CheckpointKind",
]


class AgentRunState(StrEnum):
    """Lifecycle of one `AgentRun`."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED_FOR_APPROVAL = "PAUSED_FOR_APPROVAL"
    PAUSED_BY_USER = "PAUSED_BY_USER"
    INTERRUPTED = "INTERRUPTED"  # process died; resume pending
    HANDED_OVER = "HANDED_OVER"  # continued by another run
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    FAILED_HOOK = "FAILED_HOOK"
    FAILED_BOUNDARY = "FAILED_BOUNDARY"
    BLOCKED_BUDGET = "BLOCKED_BUDGET"
    BLOCKED_PROVIDER = "BLOCKED_PROVIDER"
    CANCELLED = "CANCELLED"


class CheckpointKind(StrEnum):
    """Why a checkpoint was taken (ADR-0002)."""

    START = "START"
    PERIODIC = "PERIODIC"
    AGENT_REQUESTED = "AGENT_REQUESTED"
    HANDOFF = "HANDOFF"
    PAUSE = "PAUSE"
    END = "END"


class AgentRun(WalkModel):
    """One adapter session for one (work item, role, state). Persisted in `agent_runs`."""

    id: RunId = Field(description="RUN-<ULID>.")
    project_key: ProjectKey = Field(description="Owning project.")
    work_item_id: WorkItemId = Field(description="Work item the run works on.")
    role: AgentRole = Field(description="Role executing the run.")
    model_id: ModelId = Field(description="Model chosen by the router.")
    provider: str = Field(description="Adapter key of the model.")
    effort: Effort = Field(description="Effective effort.")
    state: AgentRunState = Field(default=AgentRunState.PENDING, description="Run lifecycle state.")
    purpose: Literal[
        "IMPLEMENT", "DESIGN", "REVIEW", "QC", "TRIAGE", "DEBATE", "PLAN", "ANALYSIS", "RETRO"
    ] = Field(description="Template the run was instantiated from.")
    worktree_path: str | None = Field(default=None, description="Sandbox worktree of the run.")
    branch: str | None = Field(default=None, description="Work branch checked out in it.")
    kernel_instance: str = Field(description="UUID of the kernel process that owns the run")
    parent_run_id: RunId | None = Field(
        default=None, description="Run this one continues (fallback, recovery, resume)."
    )
    handover_in_id: HandoverId | None = Field(default=None, description="Handover it started from.")
    handover_out_id: HandoverId | None = Field(default=None, description="Handover it produced.")
    provider_session: ProviderSessionRef | None = Field(
        default=None, description="Provider session for native resume."
    )
    tool_calls: int = Field(default=0, description="Tool calls made so far.")
    fallbacks: int = Field(default=0, description="Model fallbacks so far.")
    repair_turns: int = Field(default=0, description="Output repair turns so far.")
    started_at: datetime | None = Field(default=None, description="When the run started.")
    ended_at: datetime | None = Field(default=None, description="When it reached an end state.")
    output: AgentOutput | None = Field(default=None, description="Accepted structured output.")
    failure_reason: str | None = Field(default=None, description="Why the run failed.")


class Checkpoint(FrozenModel):
    """ADR-0002. Persisted in `checkpoints`; immutable."""

    id: CheckpointId = Field(description="CKP-<ULID>.")
    run_id: RunId = Field(description="Run checkpointed.")
    work_item_id: WorkItemId = Field(description="Work item of the run.")
    seq: int = Field(description="1-based sequence within the run.")
    kind: CheckpointKind = Field(description="Why it was taken.")
    at: datetime = Field(description="When it was taken.")
    role: AgentRole = Field(description="Role of the run.")
    model_id: ModelId = Field(description="Model of the run.")
    effort: Effort = Field(description="Effort of the run.")
    workflow_state: WorkItemState = Field(description="Work item state at the checkpoint.")
    head_sha: Sha = Field(description="Work-branch HEAD after the WIP commit")
    wip_commit_sha: Sha | None = Field(description="WIP commit made, None when clean.")
    dirty_files: list[str] = Field(description="Files still dirty after the WIP commit.")
    tool_calls_so_far: int = Field(description="Tool calls of the run so far.")
    budget_consumed: dict[BudgetDimension, float] = Field(
        description="Budget consumed by the run so far, per dimension."
    )
    provider_session: ProviderSessionRef | None = Field(
        description="Provider session for native resume."
    )
    handover_id: HandoverId | None = Field(description="Handover written with the checkpoint.")
    context_manifest: ContextBundleRef = Field(description="Context the run was given.")


class AppliedEffects(FrozenModel):
    """What `OutputApplier.apply` did with an `AgentOutput` (INTERFACES §1.13)."""

    evidence_ids: list[EvidenceId] = Field(description="Evidence recorded.")
    decision_ids: list[DecisionId] = Field(description="Decisions recorded.")
    created_work_items: list[WorkItemId] = Field(description="Work items created.")
    escalation_ids: list[str] = Field(description="Escalations raised.")
    memory_docs: list[str] = Field(description="Memory documents written.")
    commit_sha: Sha | None = Field(description="Commit of the output's changes, if any.")
    workflow_event: str | None = Field(description="Workflow event raised, if any.")
