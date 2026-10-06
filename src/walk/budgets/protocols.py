"""Budget and cost service protocols (INTERFACES §1.6)."""

from typing import Protocol

from walk.budgets.models import (
    Budget,
    BudgetDimension,
    BudgetPolicy,
    BudgetScope,
    BudgetSubject,
    BudgetVerdict,
    CostCategory,
    CostRecord,
)
from walk.common.ids import PhaseId, ProjectKey, WorkItemId


class BudgetManager(Protocol):
    """§20. Hosted by walk.budgets."""

    async def ensure(
        self,
        scope: BudgetScope,
        scope_id: str,
        policy: BudgetPolicy | None,
        limits: dict[BudgetDimension, float] | None,
    ) -> list[Budget]:
        """Create missing Budget rows for a scope (idempotent)."""
        ...

    async def applicable(self, subject: BudgetSubject) -> list[Budget]:
        """All budgets whose scope covers the subject.

        GLOBAL, PROJECT, PHASE(subject.phase_id), ROLE(subject.role), TASK(subject.work_item_id).
        """
        ...

    async def meter(
        self, subject: BudgetSubject, dimension: BudgetDimension, quantity: float
    ) -> BudgetVerdict:
        """Adds quantity to every applicable budget in one transaction.

        Returns verdict: OK | SOFT_THRESHOLD | EXHAUSTED(hard_action). Fires ON_BUDGET_THRESHOLD
        once per budget; ON_BUDGET_EXHAUSTED on hard limit. Ledger BUDGET_EVENT.
        """
        ...

    async def headroom(self, subject: BudgetSubject) -> dict[BudgetDimension, float]:
        """Min over applicable budgets of (limit - consumed) per dimension."""
        ...

    async def can_afford(
        self, scope_ids: list[str], dimension: BudgetDimension, quantity: float
    ) -> bool:
        """True iff every listed scope's ``dimension`` budget has ``quantity`` left."""
        ...


class CostManager(Protocol):
    """§84-§85. Hosted by walk.budgets."""

    async def record(self, record: CostRecord) -> None:
        """Insert cost_records + ledger COST_RECORDED; then meter COST_USD/TOKENS.

        Token→USD conversion happens in `walk.model_router.costing` (model_router may import
        budgets; not vice versa) and is called by runtime.AgentExecutor on USAGE events.
        """
        ...

    async def cost_of(
        self,
        *,
        work_item_id: WorkItemId | None = None,
        phase_id: PhaseId | None = None,
        project_key: ProjectKey | None = None,
    ) -> dict[CostCategory, float]:
        """§85 Cost per Task/Story/Feature (roll-up through parent_id)/Phase/Project."""
        ...
