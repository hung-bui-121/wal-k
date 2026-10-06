"""Model routing and adapter-boundary contracts (DOMAIN-MODEL §3, §4.10; INTERFACES §2.1).

`Capability` lives in `walk.common.enums` (RELOCATE, WBS §3.2).
"""

from collections.abc import Awaitable, Callable
from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator

from walk.agents.models import AgentOutput, ModelPolicy
from walk.common.enums import Capability, Effort
from walk.common.ids import ModelId, RunId, SkillName, ToolName
from walk.common.models import FrozenModel, JsonDict, WalkModel
from walk.common.roles import AgentRole
from walk.permissions.models import PermissionDecision, ToolCallRequest
from walk.tools.models import ToolSpec
from walk.workflow.models import Risk

_MIN_SCORE = 0
_MAX_SCORE = 5

MAX_FALLBACKS_PER_RUN = 2  # ARCHITECTURE.md §5.5


class FallbackTrigger(StrEnum):
    """§21 fallback triggers."""

    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    TOKEN_LIMIT = "TOKEN_LIMIT"  # noqa: S105 - an enum value, not a credential
    PROVIDER_OUTAGE = "PROVIDER_OUTAGE"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    CONTEXT_OVERFLOW = "CONTEXT_OVERFLOW"
    TOOL_INCOMPATIBILITY = "TOOL_INCOMPATIBILITY"
    BUDGET_RESTRICTION = "BUDGET_RESTRICTION"
    MODEL_DISABLED = "MODEL_DISABLED"
    REPEATED_OUTPUT_INVALID = (
        "REPEATED_OUTPUT_INVALID"  # kernel-added: output failed validation after repair turn
    )


class ModelDescriptor(WalkModel):
    """§16 capability metadata.

    Defaults in `walk/model_router/defaults/models.yaml`, overrides in `.ai/agents/models.yaml`.
    """

    id: ModelId = Field(description="Model id served by the adapter.")
    provider: str = Field(description="adapter key: 'claude' | 'codex' | plugin name")
    display_name: str = Field(description="Human name.")
    capabilities: dict[Capability, int] = Field(description="0..5 per capability")
    context_window_tokens: int = Field(description="Context window in tokens.")
    max_output_tokens: int = Field(description="Largest output in tokens.")
    supports_effort_levels: list[Effort] = Field(description="Effort levels the model supports.")
    supports_native_resume: bool = Field(description="Provider-side session resume available.")
    input_cost_per_mtok_usd: float = Field(description="USD per million input tokens.")
    output_cost_per_mtok_usd: float = Field(description="USD per million output tokens.")
    cache_read_cost_per_mtok_usd: float = Field(
        default=0.0, description="USD per million cache-read tokens."
    )
    enabled: bool = Field(default=True, description="Disabled models are never selected.")
    tags: list[str] = Field(default_factory=list, description="Free-form tags.")

    @field_validator("capabilities")
    @classmethod
    def _scores_in_range(cls, value: dict[Capability, int]) -> dict[Capability, int]:
        bad = {c.value: s for c, s in value.items() if not _MIN_SCORE <= s <= _MAX_SCORE}
        if bad:
            msg = f"capability scores must be within 0..5: {bad}"
            raise ValueError(msg)
        return value


class CapabilityRegistry(WalkModel):
    """All model descriptors known to the router."""

    models: dict[ModelId, ModelDescriptor] = Field(description="Descriptors by model id.")
    version: str = Field(description="Version of the models configuration.")


class TaskProfile(FrozenModel):
    """What the router needs to know about the task (§16, §29)."""

    required_capabilities: list[Capability] = Field(description="Capabilities the task needs.")
    required_tools: list[ToolName] = Field(description="Tools the task needs.")
    required_skills: list[SkillName] = Field(description="Skills the task needs.")
    estimated_context_tokens: int = Field(description="Expected context size in tokens.")
    risk: Risk = Field(description="Delivery risk.")
    implementer_model_id: ModelId | None = Field(
        default=None, description="For §23 cross-model review"
    )


class RoutingDecision(FrozenModel):
    """Outcome of `ModelRouter.select` (INTERFACES §5.3)."""

    model_id: ModelId = Field(description="Chosen model.")
    provider: str = Field(description="Adapter key of the chosen model.")
    effort: Effort = Field(description="Effort the run uses.")
    reason: str = Field(description="'preferred' | 'fallback' | 'override'.")
    rejected: list[tuple[ModelId, str]] = Field(
        default_factory=list, description="Candidates rejected before the choice, with reasons."
    )
    is_fallback: bool = Field(default=False, description="Chosen model is not a preferred one.")
    trigger: FallbackTrigger | None = Field(
        default=None, description="Trigger that caused a fallback decision."
    )


class FallbackRequest(FrozenModel):
    """Input of `ModelRouter.fallback` (INTERFACES.md §5.3 steps 7-9).

    Plain data instead of an `AgentRun`, because model_router may not import runtime
    (ARCHITECTURE.md §2.2). Built by runtime.AgentExecutor (E01-S28).
    """

    role: AgentRole = Field(description="Role of the failing run.")
    policy: ModelPolicy = Field(description="Model policy of the role.")
    current_model_id: ModelId = Field(description="Model of the failing run.")
    trigger: FallbackTrigger = Field(description="§21 trigger of the fallback.")
    profile: TaskProfile = Field(description="Task profile for the new selection.")
    effort: Effort = Field(description="Effort of the failing run.")
    fallbacks_so_far: int = Field(description="AgentRun.fallbacks of the failing run (chain count)")
    max_fallbacks: int = Field(
        default=MAX_FALLBACKS_PER_RUN, description="Fallbacks allowed per chain of runs."
    )
    measured_context_tokens: int | None = Field(
        default=None, description="Measured context size (CONTEXT_OVERFLOW only)."
    )


class ProviderSessionRef(FrozenModel):
    """Opaque provider-side session handle enabling native resume.

    Claude session_id / Codex thread id.
    """

    provider: str = Field(description="Adapter key.")
    session_id: str = Field(description="Provider session or thread id.")
    resumable: bool = Field(description="Whether `ModelAdapter.resume` may continue it.")


class UsageReport(FrozenModel):
    """Token, cost and turn usage of a run (or one step of it)."""

    input_tokens: int = Field(description="Input tokens.")
    output_tokens: int = Field(description="Output tokens.")
    cache_read_tokens: int = Field(default=0, description="Cache-read input tokens.")
    cost_usd: float = Field(description="Cost in USD as reported or computed.")
    turns: int = Field(description="Model turns.")
    tool_calls: int = Field(description="Tool calls.")
    duration_s: float = Field(description="Wall time in seconds.")


class AdapterHealth(FrozenModel):
    """Result of `ModelAdapter.health`."""

    ok: bool = Field(description="Adapter usable.")
    provider: str = Field(description="Adapter key.")
    detail: str = Field(description="Reason or version information.")
    checked_at: datetime = Field(description="When the check ran.")


class AgentEventKind(StrEnum):
    """ADR-0004 D-2 normalised event kinds."""

    STARTED = "STARTED"
    TEXT = "TEXT"  # visible assistant text (not persisted beyond logs)
    TOOL_CALL_REQUESTED = "TOOL_CALL_REQUESTED"
    TOOL_CALL_RESULT = "TOOL_CALL_RESULT"
    CHECKPOINT_HINT = "CHECKPOINT_HINT"
    USAGE = "USAGE"
    PARTIAL_OUTPUT = "PARTIAL_OUTPUT"
    FINAL_OUTPUT = "FINAL_OUTPUT"
    ERROR = "ERROR"
    ENDED = "ENDED"


class AgentEvent(FrozenModel):
    """Normalised adapter stream element (ADR-0004). Thinking/chain-of-thought is never emitted."""

    kind: AgentEventKind = Field(description="Event kind.")
    run_id: RunId = Field(description="Run that produced the event.")
    at: datetime = Field(description="When it was produced.")
    text: str | None = Field(default=None, description="Visible text (TEXT; resume instruction).")
    tool_call: ToolCallRequest | None = Field(
        default=None, description="Requested call (TOOL_CALL_REQUESTED)."
    )
    tool_result: JsonDict | None = Field(
        default=None, description="Call result (TOOL_CALL_RESULT)."
    )
    usage: UsageReport | None = Field(default=None, description="Usage (USAGE).")
    output: AgentOutput | None = Field(
        default=None, description="Parsed output (PARTIAL_OUTPUT, FINAL_OUTPUT)."
    )
    error: str | None = Field(default=None, description="Error detail (ERROR; invalid output).")
    trigger: FallbackTrigger | None = Field(default=None, description="Fallback trigger (ERROR).")
    session: ProviderSessionRef | None = Field(
        default=None, description="Provider session (STARTED)."
    )


class RunSession(FrozenModel):
    """Per-run adapter configuration supplied by the kernel."""

    run_id: RunId = Field(description="Run being executed.")
    worktree_path: str = Field(description="Sandbox worktree of the run.")
    allowed_tools: list[ToolSpec] = Field(description="Tools the adapter may expose.")
    permission_authorizer: Callable[[ToolCallRequest], Awaitable[PermissionDecision]] = Field(
        description="Enforcement point every tool call goes through before execution."
    )
    effort: Effort = Field(description="Effective effort.")
    model_id: ModelId = Field(description="Model chosen by the router.")
    max_turns: int = Field(description="Turn limit.")
    timeout_s: int = Field(description="Wall-clock limit in seconds.")
    env_allowlist: dict[str, str] = Field(description="Environment passed to subprocesses.")
    output_path: str = Field(
        description="<worktree>/.walk/output.json — fallback channel for the structured AgentOutput"
    )


class ProviderEffortConfig(FrozenModel):
    """ADR-0011: what the adapter actually sets."""

    model_id: ModelId = Field(description="Model the parameters apply to.")
    params: JsonDict = Field(description="Provider parameters, e.g. effort or reasoning level.")
