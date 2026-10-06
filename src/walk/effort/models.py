"""Effort contracts (§17-§19; DOMAIN-MODEL §4.2 `EffortPolicy` RELOCATE, §4.3)."""

from typing import Literal

from pydantic import Field

from walk.common.enums import Effort
from walk.common.models import FrozenModel, WalkModel
from walk.workflow.models import Risk, WorkItemState

EFFORT_ORDER: tuple[Effort, ...] = (Effort.LOW, Effort.MEDIUM, Effort.HIGH, Effort.VERY_HIGH)
"""Effort levels from lowest to highest; resolution works on indices into this tuple."""

STATIC_COST_USD: dict[Effort, float] = {
    Effort.LOW: 1.0,
    Effort.MEDIUM: 3.0,
    Effort.HIGH: 8.0,
    Effort.VERY_HIGH: 20.0,
}
"""Seed cost estimate per run at each effort (ADR-0011 D-5)."""


class EffortPolicy(WalkModel):
    """§18-§19 inputs of one role (relocated from `walk.agents`, WBS §3.2)."""

    default: Effort = Field(default=Effort.MEDIUM, description="Role default; also a floor.")
    min: Effort = Field(default=Effort.LOW, description="Lowest effort the role may run at.")
    max: Effort = Field(default=Effort.HIGH, description="Highest effort the role may run at.")
    auto_approve_upgrade_within_budget: bool = Field(
        default=True, description="§19: upgrades within budget need no approval when true."
    )
    complexity_map: dict[str, Effort] = Field(
        default_factory=lambda: {
            "TRIVIAL": Effort.LOW,
            "SMALL": Effort.LOW,
            "NORMAL": Effort.MEDIUM,
            "LARGE": Effort.HIGH,
            "CORE": Effort.VERY_HIGH,
        },
        description="Story contract complexity → base effort (§18 task complexity).",
    )
    risk_bump: dict[Risk, int] = Field(
        default_factory=lambda: {Risk.LOW: 0, Risk.MEDIUM: 0, Risk.HIGH: 1, Risk.CRITICAL: 2},
        description="Effort levels added per work-item risk (§18 risk).",
    )
    stage_bump: dict[WorkItemState, int] = Field(
        default_factory=lambda: {WorkItemState.REWORK: 1},
        description="Effort levels added per workflow state; absent states add 0.",
    )


class EffortRequest(WalkModel):
    """§19 dynamic effort change requested by an agent."""

    direction: Literal["UPGRADE", "DOWNGRADE"] = Field(description="Requested change direction.")
    target: Effort = Field(description="Effort the agent asks for.")
    reason: str = Field(description="Why the agent asks for the change.")


class EffortResolution(FrozenModel):
    """Result of INTERFACES.md §5.2 algorithm; written as EFFORT_SET ledger payload."""

    role_default: Effort = Field(description="Policy default (step 2 floor).")
    complexity_component: Effort = Field(description="Base effort from complexity (step 1).")
    risk_bump: int = Field(description="Levels added for risk (step 3).")
    stage_bump: int = Field(description="Levels added for the workflow state (step 4).")
    escalation_bump: int = Field(description="Levels added by agent escalation (step 5).")
    effective: Effort = Field(description="Effort the run uses.")
    clamped_by_policy: bool = Field(description="Step 6 changed the level.")
    clamped_by_budget: bool = Field(description="Step 7 lowered the level.")
