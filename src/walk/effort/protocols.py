"""Effort service protocols (INTERFACES §1.5)."""

from typing import Protocol

from walk.budgets.models import BudgetDimension
from walk.common.enums import Effort
from walk.common.ids import RunId
from walk.common.roles import AgentRole
from walk.effort.models import EffortPolicy, EffortRequest, EffortResolution
from walk.workflow.models import WorkItem, WorkItemState


class CostEstimator(Protocol):
    """Expected USD cost of one run of a role at an effort (INTERFACES §5.2 step 7)."""

    def estimate(self, role: AgentRole, effort: Effort) -> float:
        """Return the estimated cost in USD."""
        ...


class EffortManager(Protocol):
    """§17-§19. Hosted by walk.effort."""

    def resolve(
        self,
        policy: EffortPolicy,
        item: WorkItem,
        state: WorkItemState,
        escalation_bump: int,
        budget_headroom: dict[BudgetDimension, float],
    ) -> EffortResolution:
        """INTERFACES §5.2 algorithm. Pure."""
        ...

    async def request_change(
        self,
        run_id: RunId,
        current: Effort,
        request: EffortRequest,
        policy: EffortPolicy,
        headroom: dict[BudgetDimension, float],
    ) -> Effort:
        """§19: auto-approve if within [min,max] and budget headroom allows (upgrade).

        Otherwise ApprovalRequest(ORCHESTRATOR). Fires ON_EFFORT_CHANGE; ledger EFFORT_CHANGED.
        Returns effective effort for the *next* run (effort is fixed per run).
        """
        ...
