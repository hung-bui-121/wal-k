"""SQLite repositories of budgets and cost records (``budgets``, ``cost_records``)."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import ClassVar, Final, Literal

from walk.budgets.models import Budget, BudgetDimension, BudgetScope, CostCategory, CostRecord
from walk.persistence import Repository

_SCOPE_ORDER: Final = {scope: rank for rank, scope in enumerate(BudgetScope)}
_DIMENSION_ORDER: Final = {dimension: rank for rank, dimension in enumerate(BudgetDimension)}


def _utc_text(value: datetime) -> str:
    """Fixed-width UTC text so that timestamp columns order correctly as strings."""
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def _marks(values: Sequence[object]) -> str:
    return ", ".join("?" for _ in values)


class BudgetRepository(Repository[Budget]):
    """``budgets``: the `Budget` JSON plus scope/dimension/limit/consumed columns."""

    _table: ClassVar[str] = "budgets"
    _model = Budget

    def projection(self, obj: Budget) -> dict[str, object]:
        """Indexed columns of the ``budgets`` table."""
        return {
            "scope": obj.scope,
            "scope_id": obj.scope_id,
            "dimension": obj.dimension,
            "limit": obj.limit,
            "consumed": obj.consumed,
            "soft_notified": obj.soft_notified,
            "updated_at": _utc_text(obj.updated_at),
        }

    async def for_scopes(
        self,
        scopes: Sequence[tuple[BudgetScope, str]],
        dimension: BudgetDimension | None = None,
    ) -> list[Budget]:
        """Return budgets of the given ``(scope, scope_id)`` pairs, by scope then dimension."""
        if not scopes:
            return []
        clauses = " OR ".join("(scope = ? AND scope_id = ?)" for _ in scopes)
        params: list[object] = [
            value for scope, scope_id in scopes for value in (scope.value, scope_id)
        ]
        where = f"({clauses})"
        if dimension is not None:
            where += " AND dimension = ?"
            params.append(dimension.value)
        return _ordered(await self.list_where(where, params))

    async def for_scope_ids(
        self, scope_ids: Sequence[str], dimension: BudgetDimension
    ) -> list[Budget]:
        """Return the ``dimension`` budgets whose ``scope_id`` is listed."""
        if not scope_ids:
            return []
        where = f"scope_id IN ({_marks(scope_ids)}) AND dimension = ?"
        return _ordered(await self.list_where(where, [*scope_ids, dimension.value]))


def _ordered(budgets: list[Budget]) -> list[Budget]:
    return sorted(
        budgets, key=lambda b: (_SCOPE_ORDER[b.scope], b.scope_id, _DIMENSION_ORDER[b.dimension])
    )


class CostRepository(Repository[CostRecord]):
    """``cost_records``: append-only cost lines (UPDATE/DELETE abort, ADR-0002 D-3)."""

    _table: ClassVar[str] = "cost_records"
    _model = CostRecord

    def projection(self, obj: CostRecord) -> dict[str, object]:
        """Indexed columns of the ``cost_records`` table."""
        return {
            "at": _utc_text(obj.at),
            "project_key": obj.project_key,
            "category": obj.category,
            "provider": obj.provider,
            "model_id": obj.model_id,
            "dimension": obj.dimension,
            "quantity": obj.quantity,
            "unit": obj.unit,
            "cost_usd": obj.cost_usd,
            "run_id": obj.run_id,
            "work_item_id": obj.work_item_id,
            "phase_id": obj.phase_id,
            "role": obj.role,
        }

    async def totals(
        self,
        column: Literal["work_item_id", "phase_id", "project_key"],
        values: Sequence[str],
    ) -> dict[CostCategory, float]:
        """Sum ``cost_usd`` per category over records whose ``column`` is in ``values``.

        Every category is present; categories without records are ``0.0``.
        """
        totals = dict.fromkeys(CostCategory, 0.0)
        if not values:
            return totals
        sql = (
            "SELECT category, SUM(cost_usd) FROM cost_records "  # noqa: S608 - column is a Literal
            f"WHERE {column} IN ({_marks(values)}) GROUP BY category"
        )
        for category, total in self._db.connect().execute(sql, list(values)).fetchall():
            totals[CostCategory(category)] = float(total)
        return totals
