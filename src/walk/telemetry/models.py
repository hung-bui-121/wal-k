"""Telemetry contracts: ledger events, evidence and reports (DOMAIN-MODEL §3, §4.12)."""

from datetime import datetime
from enum import StrEnum
from typing import Final, Literal

from pydantic import Field

from walk.common.enums import Effort
from walk.common.ids import (
    EvidenceId,
    LedgerEventId,
    ModelId,
    PhaseId,
    ProjectKey,
    RunId,
    Sha,
    ToolName,
    WorkItemId,
    new_ulid,
)
from walk.common.models import Actor, FrozenModel, JsonDict, WalkModel, utcnow
from walk.common.roles import AgentRole


class EvidenceKind(StrEnum):
    """§6.6 evidence forms. `rank` (§47) is a property, see Evidence.rank."""

    PLAYER_TELEMETRY = "PLAYER_TELEMETRY"
    PLAYTEST = "PLAYTEST"
    GAMEPLAY_RECORDING = "GAMEPLAY_RECORDING"
    REPRODUCIBLE_BENCHMARK = "REPRODUCIBLE_BENCHMARK"
    PERFORMANCE_METRICS = "PERFORMANCE_METRICS"
    PROFILER_RESULT = "PROFILER_RESULT"
    AUTOMATED_TEST = "AUTOMATED_TEST"
    BUILD_ARTIFACT = "BUILD_ARTIFACT"
    SCREENSHOT = "SCREENSHOT"
    LOG = "LOG"
    QC_REPORT = "QC_REPORT"
    REPRODUCTION_PROOF = "REPRODUCTION_PROOF"
    PROJECT_DATA = "PROJECT_DATA"  # ledger/cost/coverage facts
    ESTABLISHED_PATTERN = "ESTABLISHED_PATTERN"
    EXPERT_REASONING = "EXPERT_REASONING"
    PREFERENCE = "PREFERENCE"


EVIDENCE_RANK: Final[dict[EvidenceKind, int]] = {
    EvidenceKind.PLAYER_TELEMETRY: 7,
    EvidenceKind.PLAYTEST: 6,
    EvidenceKind.GAMEPLAY_RECORDING: 6,
    EvidenceKind.REPRODUCIBLE_BENCHMARK: 5,
    EvidenceKind.PERFORMANCE_METRICS: 5,
    EvidenceKind.PROFILER_RESULT: 5,
    EvidenceKind.AUTOMATED_TEST: 5,
    EvidenceKind.REPRODUCTION_PROOF: 5,
    EvidenceKind.BUILD_ARTIFACT: 4,
    EvidenceKind.SCREENSHOT: 4,
    EvidenceKind.LOG: 4,
    EvidenceKind.QC_REPORT: 4,
    EvidenceKind.PROJECT_DATA: 4,
    EvidenceKind.ESTABLISHED_PATTERN: 3,
    EvidenceKind.EXPERT_REASONING: 2,
    EvidenceKind.PREFERENCE: 1,
}
"""§47 ranking: higher = stronger. Kinds sharing a tier share a value."""


class LedgerEventKind(StrEnum):
    """§81 examples + §86 required observability, exhaustive for the kernel."""

    PROJECT_STARTED = "PROJECT_STARTED"
    PHASE_TRANSITION = "PHASE_TRANSITION"
    PHASE_GATE_DECISION = "PHASE_GATE_DECISION"
    RC_TRANSITION = "RC_TRANSITION"
    WORK_ITEM_CREATED = "WORK_ITEM_CREATED"
    WORK_ITEM_TRANSITION = "WORK_ITEM_TRANSITION"
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    AGENT_ASSIGNED = "AGENT_ASSIGNED"
    AGENT_RUN_STARTED = "AGENT_RUN_STARTED"
    AGENT_RUN_ENDED = "AGENT_RUN_ENDED"
    MODEL_SELECTED = "MODEL_SELECTED"
    MODEL_FALLBACK = "MODEL_FALLBACK"
    EFFORT_SET = "EFFORT_SET"
    EFFORT_CHANGED = "EFFORT_CHANGED"
    TOOL_INVOKED = "TOOL_INVOKED"
    TOOL_DENIED = "TOOL_DENIED"
    CHECKPOINT_CREATED = "CHECKPOINT_CREATED"
    HANDOVER_CREATED = "HANDOVER_CREATED"
    RECOVERY_RESUMED = "RECOVERY_RESUMED"
    RETRY = "RETRY"
    ERROR = "ERROR"
    COMMIT = "COMMIT"
    PR_OPENED = "PR_OPENED"
    MERGED = "MERGED"
    BUILD_RESULT = "BUILD_RESULT"
    TEST_RESULT = "TEST_RESULT"
    QC_RESULT = "QC_RESULT"
    BUG_CREATED = "BUG_CREATED"
    DEBATE_OPENED = "DEBATE_OPENED"
    DEBATE_POSITION = "DEBATE_POSITION"
    DEBATE_RESOLVED = "DEBATE_RESOLVED"
    DECISION_RECORDED = "DECISION_RECORDED"
    ESCALATION_RAISED = "ESCALATION_RAISED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_DECIDED = "APPROVAL_DECIDED"
    BUDGET_EVENT = "BUDGET_EVENT"
    COST_RECORDED = "COST_RECORDED"
    CONTEXT_FRESHNESS = "CONTEXT_FRESHNESS"
    CONTEXT_UPDATED = "CONTEXT_UPDATED"
    ARTIFACT_APPROVED = "ARTIFACT_APPROVED"
    EVIDENCE_RECORDED = "EVIDENCE_RECORDED"
    HOOK_EXECUTED = "HOOK_EXECUTED"
    HOOK_FAILED = "HOOK_FAILED"
    USER_OVERRIDE = "USER_OVERRIDE"
    IMPROVEMENT_OBSERVATION = "IMPROVEMENT_OBSERVATION"
    IMPROVEMENT_CANDIDATE = "IMPROVEMENT_CANDIDATE"
    BEHAVIOR_VERSION_CHANGED = "BEHAVIOR_VERSION_CHANGED"


def _new_ledger_event_id() -> str:
    return f"LED-{new_ulid()}"


class LedgerEvent(FrozenModel):
    """Append-only (§81). `seq` assigned by SQLite AUTOINCREMENT; `id` is a ULID.

    `id` and `at` have defaults so callers can build an event without them;
    `LedgerManager.append` replaces any field the caller did not set (see
    ``model_fields_set``) with an injected ULID and clock time.
    """

    seq: int | None = Field(default=None, description="None before insert")
    id: LedgerEventId = Field(
        default_factory=_new_ledger_event_id,
        description="LED-<ULID>; assigned by LedgerManager.append when not set by the caller.",
    )
    kind: LedgerEventKind = Field(description="What happened.")
    at: datetime = Field(
        default_factory=utcnow,
        description="When it happened (UTC); clock time from append when not set by the caller.",
    )
    project_key: ProjectKey = Field(description="Project the event belongs to.")
    actor_role: AgentRole = Field(description="Role that caused the event (USER/KERNEL too).")
    work_item_id: WorkItemId | None = Field(default=None, description="Work item concerned.")
    run_id: RunId | None = Field(default=None, description="Agent run concerned.")
    phase_id: PhaseId | None = Field(default=None, description="Phase concerned.")
    model_id: ModelId | None = Field(default=None, description="Model involved.")
    effort: Effort | None = Field(default=None, description="Effort in effect.")
    tool: ToolName | None = Field(default=None, description="Tool involved.")
    duration_ms: int | None = Field(default=None, description="Duration of the action.")
    cost_usd: float | None = Field(default=None, description="Cost attributed to the event.")
    outcome: Literal["OK", "FAILED", "DENIED", "SKIPPED"] | None = Field(
        default=None, description="Result of the action, if it has one."
    )
    payload: JsonDict = Field(
        default_factory=dict,
        description="Kind-specific structured detail (e.g. from/to states, trigger, sha)",
    )
    behavior_versions: dict[str, str] = Field(
        default_factory=dict,
        description="§82 'with which version' — workflow/constitution/skill versions in effect",
    )


class Evidence(FrozenModel):
    """§6.6 evidence record.

    Files live under ``.ai/<features|bugs|phases>/<id>/evidence/``; the ``evidence`` table
    indexes them.
    """

    id: EvidenceId = Field(description="EVD-NNNNNN.")
    kind: EvidenceKind = Field(description="Evidence form (§6.6).")
    description: str = Field(description="What the evidence shows.")
    uri: str = Field(description="repo-relative path or external URI")
    sha256: str | None = Field(description="Content hash of a local file; None for URIs.")
    produced_by: Actor = Field(description="Who produced the evidence.")
    produced_at: datetime = Field(description="When it was recorded (UTC).")
    work_item_id: WorkItemId | None = Field(description="Work item it supports.")
    phase_id: PhaseId | None = Field(description="Phase it supports.")
    commit: Sha | None = Field(description="Commit the evidence was produced against.")
    metrics: JsonDict = Field(default_factory=dict, description="Numeric facts it carries.")

    @property
    def rank(self) -> int:
        """§47 ranking."""
        return EVIDENCE_RANK[self.kind]


class EvidenceDraft(WalkModel):
    """Evidence declared by an agent or a CI job.

    `EvidenceManager.record` hashes the file and mints the `EvidenceId`.
    """

    kind: EvidenceKind = Field(description="Evidence form (§6.6).")
    path_or_uri: str = Field(description="Repo-relative file path or external URI.")
    description: str = Field(description="What the evidence shows.")
    metrics: JsonDict = Field(default_factory=dict, description="Numeric facts it carries.")


class RetrospectiveMetrics(WalkModel):
    """§115 figures / §116 metrics, computed by TelemetryManager from the ledger (§83).

    Embedded in ``improvement.Retrospective``.
    """

    stories: int = Field(description="Stories in the measured window.")
    first_pass_success_rate: float = Field(
        description="Completed stories with no fix loop / completed stories."
    )
    reworked_stories: int = Field(description="Stories that needed at least one fix loop.")
    qc_bugs: int = Field(description="Bugs found by QC.")
    escaped_bugs: int = Field(description="Bugs that escaped QC (§115).")
    context_stale_incidents: int = Field(description="Stale-context incidents (§115).")
    fallbacks: int = Field(description="Model fallbacks.")
    failed_handoffs: int = Field(description="Failed handoffs (§115).")
    build_failures: int = Field(description="Failed builds.")
    debate_rounds: int = Field(description="Debate rounds held.")
    user_escalations: int = Field(description="Escalations that reached the user.")
    total_cost_usd: float = Field(description="Total recorded cost in USD.")
    total_tokens: int = Field(description="Total model tokens.")
    mean_task_duration_s: float = Field(description="Mean task duration in seconds (§116).")


class Report(FrozenModel):
    """§83 report generated from ledger events only."""

    kind: str = Field(description="task, feature, phase, project, cost or improvement.")
    subject_id: str = Field(description="Work item, phase or project the report covers.")
    generated_at: datetime = Field(description="When the report was generated (UTC).")
    markdown: str = Field(description="Rendered report; empty until E09.")
    data: JsonDict = Field(description="Structured report data, e.g. the queried events.")
