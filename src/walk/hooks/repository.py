"""SQLite access to ``hook_executions`` (one row per hook execution)."""

from datetime import UTC, datetime

from walk.hooks.models import HookContext, HookResult
from walk.persistence import Database, UnitOfWork

_INSERT_SQL = (
    "INSERT INTO hook_executions "
    "(hook_name, hook_id, at, run_id, work_item_id, status, duration_ms, message) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
)


class HookExecutionRepository:
    """Appends execution records; the ledger event of the same execution shares the unit."""

    def __init__(self, db: Database) -> None:
        """Bind the repository to ``db``."""
        self._db = db

    @property
    def db(self) -> Database:
        """The database holding ``hook_executions``; the manager opens units of work on it."""
        return self._db

    async def insert(
        self, ctx: HookContext, result: HookResult, *, at: datetime, uow: UnitOfWork
    ) -> None:
        """Record ``result`` of a hook fired with ``ctx`` that started at ``at``."""
        uow.conn.execute(
            _INSERT_SQL,
            (
                ctx.name.value,
                result.hook_id,
                at.astimezone(UTC).isoformat(timespec="microseconds"),
                ctx.run_id,
                ctx.work_item_id,
                result.status,
                result.duration_ms,
                result.message or None,
            ),
        )
