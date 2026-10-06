"""Default budget and cost managers (§20, §84-§85; ARCHITECTURE §4.3 write points)."""

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
from walk.budgets.protocols import BudgetManager
from walk.budgets.repository import BudgetRepository, CostRepository
from walk.common.clock import Clock
from walk.common.errors import ConfigError
from walk.common.ids import PhaseId, ProjectKey, WorkItemId
from walk.common.models import JsonDict
from walk.common.roles import AgentRole
from walk.hooks.models import HookContext, HookName
from walk.hooks.protocols import HookManager
from walk.persistence import Database, UnitOfWork
from walk.telemetry.models import LedgerEvent, LedgerEventKind
from walk.telemetry.protocols import LedgerManager
from walk.workflow.errors import WorkItemNotFound
from walk.workflow.models import WorkItemKind
from walk.workflow.repository import WorkflowRepository

_GLOBAL_SCOPE_ID = "GLOBAL"
_OK = BudgetVerdict(status="OK", budget=None, hard_action=None)


def _scopes(subject: BudgetSubject) -> list[tuple[BudgetScope, str]]:
    """The ``(scope, scope_id)`` pairs covering ``subject``, broadest first."""
    scopes = [(BudgetScope.GLOBAL, _GLOBAL_SCOPE_ID), (BudgetScope.PROJECT, subject.project_key)]
    if subject.phase_id is not None:
        scopes.append((BudgetScope.PHASE, subject.phase_id))
    if subject.role is not None:
        scopes.append((BudgetScope.ROLE, subject.role.value))
    if subject.work_item_id is not None:
        scopes.append((BudgetScope.TASK, subject.work_item_id))
    return scopes


class DefaultBudgetManager:
    """`BudgetManager` over SQLite; metering is atomic across every applicable budget."""

    def __init__(
        self,
        db: Database,
        repo: BudgetRepository,
        ledger: LedgerManager,
        hooks: HookManager,
        clock: Clock,
    ) -> None:
        """Wire the manager.

        Args:
            db: Project database; every write runs in a `UnitOfWork` on it.
            repo: Budget rows.
            ledger: Write point for ``BUDGET_EVENT``.
            hooks: Fires ``ON_BUDGET_THRESHOLD`` / ``ON_BUDGET_EXHAUSTED`` after commit.
            clock: Stamps ``updated_at`` and hook contexts.
        """
        self._db = db
        self._repo = repo
        self._ledger = ledger
        self._hooks = hooks
        self._clock = clock

    async def ensure(
        self,
        scope: BudgetScope,
        scope_id: str,
        policy: BudgetPolicy | None,
        limits: dict[BudgetDimension, float] | None,
    ) -> list[Budget]:
        """Create the missing budgets of a scope; existing rows are returned untouched.

        One budget per dimension of ``limits``, or of ``policy.per_task`` when ``limits`` is
        ``None``; ratio and hard action come from ``policy`` (Budget defaults without one).

        Raises:
            ConfigError: If neither ``policy`` nor ``limits`` is given.
        """
        if limits is None:
            if policy is None:
                msg = "ensure needs a policy or limits"
                raise ConfigError(msg, detail={"scope": scope.value, "scope_id": scope_id})
            limits = policy.per_task
        defaults = BudgetPolicy() if policy is None else policy
        async with UnitOfWork(self._db) as uow:
            existing = {b.id: b for b in await self._repo.for_scopes([(scope, scope_id)])}
            budgets: list[Budget] = []
            for dimension, limit in limits.items():
                budget_id = f"{scope.value}:{scope_id}:{dimension.value}"
                budget = existing.get(budget_id)
                if budget is None:
                    budget = Budget(
                        id=budget_id,
                        scope=scope,
                        scope_id=scope_id,
                        dimension=dimension,
                        limit=limit,
                        soft_threshold_ratio=defaults.soft_threshold_ratio,
                        hard_action=defaults.hard_action,
                        updated_at=self._clock.now(),
                    )
                    await self._repo.insert(budget, uow)
                budgets.append(budget)
        return budgets

    async def applicable(self, subject: BudgetSubject) -> list[Budget]:
        """Budgets of GLOBAL, PROJECT and the subject's PHASE/ROLE/TASK, broadest first."""
        return await self._repo.for_scopes(_scopes(subject))

    async def meter(
        self, subject: BudgetSubject, dimension: BudgetDimension, quantity: float
    ) -> BudgetVerdict:
        """Add ``quantity`` to every applicable ``dimension`` budget in one transaction.

        Verdict: EXHAUSTED (first budget at or over its limit) > SOFT_THRESHOLD (first budget
        crossing its soft threshold now) > OK. ``ON_BUDGET_THRESHOLD`` fires once per budget,
        ``ON_BUDGET_EXHAUSTED`` when a budget reaches its limit; both after commit. One
        ``BUDGET_EVENT`` is written when at least one budget was metered.

        Raises:
            ValueError: If ``quantity`` is negative.
        """
        if quantity < 0:
            msg = f"cannot meter a negative quantity: {quantity}"
            raise ValueError(msg)
        async with UnitOfWork(self._db) as uow:
            budgets = await self._repo.for_scopes(_scopes(subject), dimension)
            if not budgets:
                return _OK
            now = self._clock.now()
            metered: list[Budget] = []
            crossed: list[Budget] = []
            exhausted_now: list[Budget] = []
            for budget in budgets:
                consumed = budget.consumed + quantity
                soft = (
                    not budget.soft_notified
                    and consumed >= budget.limit * budget.soft_threshold_ratio
                )
                updated = budget.model_copy(
                    update={
                        "consumed": consumed,
                        "soft_notified": budget.soft_notified or soft,
                        "updated_at": now,
                    }
                )
                await self._repo.upsert(updated, uow)
                metered.append(updated)
                if soft:
                    crossed.append(updated)
                if budget.consumed < budget.limit <= consumed:
                    exhausted_now.append(updated)
            verdict = _verdict(metered, crossed)
            event = LedgerEvent(
                kind=LedgerEventKind.BUDGET_EVENT,
                at=now,
                project_key=subject.project_key,
                actor_role=AgentRole.KERNEL,
                work_item_id=subject.work_item_id,
                run_id=subject.run_id,
                phase_id=subject.phase_id,
                outcome="OK",
                payload={
                    "dimension": dimension.value,
                    "quantity": quantity,
                    "status": verdict.status,
                    "budgets": [
                        {"id": b.id, "consumed": b.consumed, "limit": b.limit} for b in metered
                    ],
                },
            )
            await self._ledger.append(event, uow=uow)
            contexts = [
                *(self._hook_context(HookName.ON_BUDGET_THRESHOLD, subject, b) for b in crossed),
                *(
                    self._hook_context(HookName.ON_BUDGET_EXHAUSTED, subject, b)
                    for b in exhausted_now
                ),
            ]
            if contexts:
                uow.after_commit(lambda: self._fire(contexts))
        return verdict

    async def headroom(self, subject: BudgetSubject) -> dict[BudgetDimension, float]:
        """``min(limit - consumed)`` per dimension; dimensions without budgets are absent."""
        headroom: dict[BudgetDimension, float] = {}
        for budget in await self.applicable(subject):
            left = budget.limit - budget.consumed
            headroom[budget.dimension] = min(left, headroom.get(budget.dimension, left))
        return headroom

    async def can_afford(
        self, scope_ids: list[str], dimension: BudgetDimension, quantity: float
    ) -> bool:
        """True iff each listed scope's ``dimension`` budget has ``quantity`` left.

        A scope without such a budget is unlimited.
        """
        budgets = await self._repo.for_scope_ids(scope_ids, dimension)
        return all(budget.limit - budget.consumed >= quantity for budget in budgets)

    def _hook_context(self, name: HookName, subject: BudgetSubject, budget: Budget) -> HookContext:
        return HookContext(
            name=name,
            at=budget.updated_at,
            project_key=subject.project_key,
            work_item_id=subject.work_item_id,
            run_id=subject.run_id,
            phase_id=subject.phase_id,
            role=subject.role,
            payload={
                "budget_id": budget.id,
                "scope": budget.scope.value,
                "scope_id": budget.scope_id,
                "dimension": budget.dimension.value,
                "consumed": budget.consumed,
                "limit": budget.limit,
                "hard_action": budget.hard_action.value,
            },
        )

    async def _fire(self, contexts: list[HookContext]) -> None:
        for ctx in contexts:
            await self._hooks.fire(ctx.name, ctx)


def _verdict(metered: list[Budget], crossed: list[Budget]) -> BudgetVerdict:
    for budget in metered:
        if budget.consumed >= budget.limit:
            return BudgetVerdict(status="EXHAUSTED", budget=budget, hard_action=budget.hard_action)
    if crossed:
        return BudgetVerdict(status="SOFT_THRESHOLD", budget=crossed[0], hard_action=None)
    return _OK


class DefaultCostManager:
    """`CostManager` over SQLite: cost lines, their ledger events and roll-ups."""

    def __init__(
        self,
        db: Database,
        repo: CostRepository,
        ledger: LedgerManager,
        budgets: BudgetManager,
        items: WorkflowRepository,
    ) -> None:
        """Wire the manager.

        Args:
            db: Project database.
            repo: Cost lines.
            ledger: Write point for ``COST_RECORDED``.
            budgets: Metered after each record.
            items: Work-item hierarchy for roll-ups.
        """
        self._db = db
        self._repo = repo
        self._ledger = ledger
        self._budgets = budgets
        self._items = items

    async def record(self, record: CostRecord) -> None:
        """Persist ``record`` with ``COST_RECORDED``, then meter its budgets.

        ``COST_USD`` is metered with ``cost_usd``; ``TOKENS`` too (with ``quantity``) when the
        record's dimension is TOKENS. Metering runs after the record is committed.
        """
        async with UnitOfWork(self._db) as uow:
            await self._repo.insert(record, uow)
            event = LedgerEvent(
                kind=LedgerEventKind.COST_RECORDED,
                at=record.at,
                project_key=record.project_key,
                actor_role=record.role or AgentRole.KERNEL,
                work_item_id=record.work_item_id,
                run_id=record.run_id,
                phase_id=record.phase_id,
                model_id=record.model_id,
                cost_usd=record.cost_usd,
                outcome="OK",
                payload=_cost_payload(record),
            )
            await self._ledger.append(event, uow=uow)
        subject = BudgetSubject(
            project_key=record.project_key,
            phase_id=record.phase_id,
            role=record.role,
            work_item_id=record.work_item_id,
            run_id=record.run_id,
        )
        await self._budgets.meter(subject, BudgetDimension.COST_USD, record.cost_usd)
        if record.dimension is BudgetDimension.TOKENS:
            await self._budgets.meter(subject, BudgetDimension.TOKENS, record.quantity)

    async def cost_of(
        self,
        *,
        work_item_id: WorkItemId | None = None,
        phase_id: PhaseId | None = None,
        project_key: ProjectKey | None = None,
    ) -> dict[CostCategory, float]:
        """USD per category for one work item (with descendants), phase or project.

        A work item rolls up its descendants through ``parent_id`` and the bugs whose
        ``related_feature_id`` is in the tree. Every category is present.

        Raises:
            ConfigError: Unless exactly one of the three subjects is given.
            WorkItemNotFound: ``work_item_id`` names no item.
        """
        given = [value for value in (work_item_id, phase_id, project_key) if value is not None]
        if len(given) != 1:
            msg = "cost_of needs exactly one of work_item_id, phase_id, project_key"
            raise ConfigError(msg, detail={"given": len(given)})
        if work_item_id is not None:
            return await self._repo.totals("work_item_id", await self._tree(work_item_id))
        if phase_id is not None:
            return await self._repo.totals("phase_id", [phase_id])
        return await self._repo.totals("project_key", [str(project_key)])

    async def _tree(self, root: WorkItemId) -> list[str]:
        if await self._items.get(root) is None:
            msg = f"work item not found: {root}"
            raise WorkItemNotFound(msg, detail={"work_item_id": root})
        seen = [root]
        queue = [root]
        while queue:
            current = queue.pop()
            children = await self._items.children(current)
            bugs = await self._items.list_where(
                "kind = ? AND json_extract(json, '$.related_feature_id') = ?",
                [WorkItemKind.BUG.value, current],
            )
            for item in (*children, *bugs):
                if item.id not in seen:
                    seen.append(item.id)
                    queue.append(item.id)
        return seen


def _cost_payload(record: CostRecord) -> JsonDict:
    """``COST_RECORDED`` payload; the token keys feed ``METRIC_QUERIES`` (E01-S06)."""
    return {
        "record_id": record.id,
        "category": record.category.value,
        "provider": record.provider,
        "dimension": record.dimension.value,
        "quantity": record.quantity,
        "unit": record.unit,
        "input_tokens": record.input_tokens,
        "output_tokens": record.output_tokens,
        "cache_read_tokens": record.cache_read_tokens,
    }
