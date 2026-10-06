"""Budget and cost contracts (DOMAIN-MODEL §3, §4.4; BudgetPolicy relocated from §4.2)."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from walk.common.ids import ModelId, PhaseId, ProjectKey, RunId, WorkItemId
from walk.common.models import FrozenModel, WalkModel, utcnow
from walk.common.roles import AgentRole


class BudgetScope(StrEnum):
    """§20."""

    GLOBAL = "GLOBAL"
    PROJECT = "PROJECT"
    PHASE = "PHASE"
    ROLE = "ROLE"
    TASK = "TASK"


class BudgetDimension(StrEnum):
    """§20 + §84 cost dimensions."""

    TOKENS = "TOKENS"
    COST_USD = "COST_USD"
    AGENT_TURNS = "AGENT_TURNS"
    TOOL_CALLS = "TOOL_CALLS"
    EXECUTION_TIME_S = "EXECUTION_TIME_S"
    REVIEW_LOOPS = "REVIEW_LOOPS"
    EXTERNAL_CREDITS = "EXTERNAL_CREDITS"


class CostCategory(StrEnum):
    """§84 accounting tree root."""

    LLM = "LLM"
    ASSETS = "ASSETS"
    COMPUTE = "COMPUTE"
    TIME = "TIME"


class BudgetHardAction(StrEnum):
    """What the kernel does when a hard limit is reached."""

    BLOCK = "BLOCK"  # stop run, escalate
    DOWNGRADE_EFFORT = "DOWNGRADE_EFFORT"
    FALLBACK_MODEL = "FALLBACK_MODEL"


class Budget(WalkModel):
    """One limit for one dimension at one scope. Persisted in `budgets`."""

    id: str = Field(description="'<scope>:<scope_id>:<dimension>' e.g. 'TASK:STORY-0412:COST_USD'")
    scope: BudgetScope = Field(description="Scope the limit applies to.")
    scope_id: str = Field(
        description="project key / PHASE-id / role name / work item id / 'GLOBAL'"
    )
    dimension: BudgetDimension = Field(description="What is limited.")
    limit: float = Field(description="Hard limit in the dimension's unit.")
    consumed: float = Field(default=0.0, description="Metered so far.")
    soft_threshold_ratio: float = Field(
        default=0.8, description="Share of the limit that triggers ON_BUDGET_THRESHOLD."
    )
    hard_action: BudgetHardAction = Field(
        default=BudgetHardAction.BLOCK, description="Action when the limit is reached."
    )
    soft_notified: bool = Field(
        default=False, description="True once ON_BUDGET_THRESHOLD has fired for this budget."
    )
    updated_at: datetime = Field(default_factory=utcnow, description="Last change.")


class BudgetSubject(FrozenModel):
    """Identifies which budget scopes a metered quantity applies to.

    Passed by runtime instead of AgentRun to keep budgets below runtime.
    """

    project_key: ProjectKey = Field(description="PROJECT scope.")
    phase_id: PhaseId | None = Field(default=None, description="PHASE scope, if any.")
    role: AgentRole | None = Field(default=None, description="ROLE scope, if any.")
    work_item_id: WorkItemId | None = Field(default=None, description="TASK scope, if any.")
    run_id: RunId | None = Field(default=None, description="Run that consumed, if any.")


class CostRecord(FrozenModel):
    """§84 one metered cost line. Persisted in `cost_records`; also emitted as COST_RECORDED.

    Built from adapter usage by `walk.model_router.costing.usage_to_cost_record(usage,
    descriptor, subject)`.
    """

    id: str = Field(description="Unique record id (callers mint it, e.g. a ULID).")
    at: datetime = Field(description="When the cost was incurred (UTC).")
    project_key: ProjectKey = Field(description="Project charged.")
    category: CostCategory = Field(description="§84 accounting category.")
    provider: str = Field(description="claude / codex / meshy / ci / wallclock")
    model_id: ModelId | None = Field(default=None, description="Model that incurred it.")
    dimension: BudgetDimension = Field(description="Dimension of ``quantity``.")
    quantity: float = Field(description="Amount in ``unit``.")
    unit: str = Field(description="tokens / usd / seconds / calls / credits")
    cost_usd: float = Field(default=0.0, description="Cost in US dollars.")
    run_id: RunId | None = Field(default=None, description="Run charged, if any.")
    work_item_id: WorkItemId | None = Field(default=None, description="Work item charged.")
    phase_id: PhaseId | None = Field(default=None, description="Phase charged.")
    role: AgentRole | None = Field(default=None, description="Role charged.")
    input_tokens: int | None = Field(default=None, description="Prompt tokens, for LLM costs.")
    output_tokens: int | None = Field(default=None, description="Completion tokens.")
    cache_read_tokens: int | None = Field(default=None, description="Cached prompt tokens.")


class BudgetPolicy(WalkModel):
    """§20 per-role defaults; instantiated as Budget rows at ROLE and TASK scope."""

    per_task: dict[BudgetDimension, float] = Field(
        default_factory=lambda: {
            BudgetDimension.COST_USD: 15.0,
            BudgetDimension.TOOL_CALLS: 400,
            BudgetDimension.EXECUTION_TIME_S: 2700,
            BudgetDimension.REVIEW_LOOPS: 3,
        },
        description="Limit per dimension for one task.",
    )
    soft_threshold_ratio: float = Field(
        default=0.8, ge=0, le=1, description="Share of a limit that triggers the soft threshold."
    )
    hard_action: BudgetHardAction = Field(
        default=BudgetHardAction.BLOCK, description="Action when a limit is reached."
    )


class BudgetVerdict(FrozenModel):
    """Result of `BudgetManager.meter`."""

    status: Literal["OK", "SOFT_THRESHOLD", "EXHAUSTED"] = Field(description="Outcome.")
    budget: Budget | None = Field(description="Budget that caused the status; None when OK.")
    hard_action: BudgetHardAction | None = Field(description="Set when EXHAUSTED.")
