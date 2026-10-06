"""Hook contracts (DOMAIN-MODEL §4.6; full name table: ARCHITECTURE §4.1)."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from walk.common.ids import PhaseId, ProjectKey, RunId, WorkItemId
from walk.common.models import FrozenModel, JsonDict, WalkModel
from walk.common.roles import AgentRole


class HookName(StrEnum):
    """Full list and semantics: ARCHITECTURE.md §4.1."""

    ON_PROJECT_START = "on_project_start"
    ON_PROJECT_PAUSE = "on_project_pause"
    ON_PROJECT_RESUME = "on_project_resume"
    ON_PHASE_START = "on_phase_start"
    ON_PHASE_REVIEW_START = "on_phase_review_start"
    ON_PHASE_COMPLETE = "on_phase_complete"
    ON_PHASE_GATE_DECISION = "on_phase_gate_decision"
    ON_TASK_START = "on_task_start"
    ON_TASK_COMPLETE = "on_task_complete"
    ON_TASK_BLOCKED = "on_task_blocked"
    ON_TASK_FAILED = "on_task_failed"
    ON_TASK_CANCELLED = "on_task_cancelled"
    ON_STATE_TRANSITION = "on_state_transition"
    ON_AGENT_START = "on_agent_start"
    ON_AGENT_CHECKPOINT = "on_agent_checkpoint"
    ON_AGENT_END = "on_agent_end"
    ON_AGENT_HANDOFF = "on_agent_handoff"
    ON_MODEL_FALLBACK = "on_model_fallback"
    ON_EFFORT_CHANGE = "on_effort_change"
    ON_BUDGET_THRESHOLD = "on_budget_threshold"
    ON_BUDGET_EXHAUSTED = "on_budget_exhausted"
    ON_TOOL_BEFORE = "on_tool_before"
    ON_TOOL_AFTER = "on_tool_after"
    ON_TOOL_DENIED = "on_tool_denied"
    ON_PROTECTED_ACTION_REQUESTED = "on_protected_action_requested"
    ON_CODE_CHANGED = "on_code_changed"
    ON_COMMIT = "on_commit"
    ON_PR_OPENED = "on_pr_opened"
    ON_MERGED = "on_merged"
    ON_BUILD_START = "on_build_start"
    ON_BUILD_SUCCESS = "on_build_success"
    ON_BUILD_FAILURE = "on_build_failure"
    ON_TEST_RESULT = "on_test_result"
    ON_CONTEXT_STALE = "on_context_stale"
    ON_CONTEXT_UPDATED = "on_context_updated"
    ON_READY_FOR_QC = "on_ready_for_qc"
    ON_QC_RESULT = "on_qc_result"
    ON_BUG_CREATED = "on_bug_created"
    ON_DEBATE_OPENED = "on_debate_opened"
    ON_DEBATE_ROUND_COMPLETE = "on_debate_round_complete"
    ON_DEBATE_RESOLVED = "on_debate_resolved"
    ON_DECISION_RECORDED = "on_decision_recorded"
    ON_ESCALATION = "on_escalation"
    ON_RECOVERY_RESUME = "on_recovery_resume"
    ON_IMPROVEMENT_OBSERVATION = "on_improvement_observation"


class HookFailPolicy(StrEnum):
    """What a hook failure does to the triggering operation (ARCHITECTURE §4.1)."""

    FAIL_CLOSED = "fail_closed"
    LOG_AND_CONTINUE = "log_and_continue"


class Hook(WalkModel):
    """A registration.

    `builtin` hooks carry a dotted callable path; project hooks carry a shell command or kernel
    action.
    """

    name: HookName = Field(description="Lifecycle point the hook attaches to.")
    id: str = Field(
        description="unique within hook name, e.g. 'builtin.checkpoint', 'project.notify-slack'"
    )
    kind: Literal["builtin", "project"] = Field(
        description="builtin = kernel Python callable; project = declared in hooks.yaml."
    )
    priority: int = Field(default=100, description="lower runs first; builtin MUST hooks use < 50")
    callable_path: str | None = Field(
        default=None, description="Dotted path of a builtin callable (resolved at register)."
    )
    command: str | None = Field(default=None, description="Shell command of a project hook.")
    kernel_action: str | None = Field(
        default=None, description="Allowlisted kernel action name of a project hook."
    )
    fail_policy: HookFailPolicy = Field(
        default=HookFailPolicy.LOG_AND_CONTINUE, description="Effect of a failure or timeout."
    )
    required: bool = Field(
        default=False, description="MUST hooks: cannot be disabled by project config"
    )
    enabled: bool = Field(default=True, description="Disabled hooks are skipped without a record.")
    timeout_s: int = Field(default=120, description="Seconds before the run counts as TIMEOUT.")


class HookContext(FrozenModel):
    """What a hook receives: the lifecycle point, when it happened and what it concerns."""

    name: HookName = Field(description="Lifecycle point being fired.")
    at: datetime = Field(description="When the triggering event happened (set by the caller).")
    project_key: ProjectKey = Field(description="Project the event belongs to.")
    work_item_id: WorkItemId | None = Field(default=None, description="Work item concerned.")
    run_id: RunId | None = Field(default=None, description="Agent run concerned.")
    phase_id: PhaseId | None = Field(default=None, description="Phase concerned.")
    role: AgentRole | None = Field(default=None, description="Role concerned.")
    payload: JsonDict = Field(
        default_factory=dict, description="Hook-specific facts, e.g. checkpoint_id."
    )


class HookResult(FrozenModel):
    """Outcome of one hook execution."""

    hook_id: str = Field(description="Id of the hook that ran.")
    status: Literal["OK", "FAILED", "SKIPPED", "TIMEOUT"] = Field(description="Outcome.")
    duration_ms: int = Field(description="Execution time measured by the kernel clock.")
    message: str = Field(default="", description="Failure reason; empty on success.")


HookCallable = Callable[
    [HookContext], Awaitable[None]
]  # built-in implementations live in walk.orchestrator.builtin_hooks (ADR-0016)
