"""Role contracts: constitutions, runtime policies, agent instances (§9, §12-§15).

DOMAIN-MODEL §4.2.

`EffortPolicy` and `BudgetPolicy` live in `walk.effort.models` / `walk.budgets.models`
(RELOCATE, WBS §3.2). The execution-contract models arrive in E01-S18.
"""

from typing import Literal

from pydantic import Field

from walk.budgets.models import BudgetPolicy
from walk.common.enums import Capability, Effort
from walk.common.ids import ModelId, SkillName, ToolName
from walk.common.models import WalkModel
from walk.common.roles import AgentRole
from walk.decisions.models import Authority, EscalationRule
from walk.effort.models import EffortPolicy
from walk.permissions.models import PermissionRule
from walk.telemetry.models import EvidenceKind


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
