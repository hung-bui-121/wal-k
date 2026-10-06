"""SQLite access to ``ledger_events``: insert and read only (Invariant 9).

There is deliberately no update or delete method; the table's triggers abort both.
"""

import sqlite3
from datetime import UTC, datetime

from walk.common.ids import PhaseId, RunId, WorkItemId
from walk.persistence import Database
from walk.telemetry.models import LedgerEvent, LedgerEventKind

_MAX_QUERY_LIMIT = 10_000
_INSERT_SQL = (
    "INSERT INTO ledger_events (id, kind, at, project_key, actor_role, work_item_id, run_id, "
    "phase_id, model_id, tool, cost_usd, outcome, json) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def _at_column(value: datetime) -> str:
    """Fixed-width UTC text so that ``at`` compares correctly as a string."""
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def _from_row(row: sqlite3.Row) -> LedgerEvent:
    event = LedgerEvent.model_validate_json(row["json"])
    return event.model_copy(update={"seq": int(row["seq"])})


class LedgerRepository:
    """Reads and appends ledger rows; the JSON column holds the full `LedgerEvent`."""

    def __init__(self, db: Database) -> None:
        """Bind the repository to ``db``."""
        self._db = db

    def insert(self, event: LedgerEvent, conn: sqlite3.Connection) -> LedgerEvent:
        """Insert ``event`` on ``conn`` (the caller's transaction) and return it with ``seq``."""
        cursor = conn.execute(
            _INSERT_SQL,
            (
                event.id,
                event.kind.value,
                _at_column(event.at),
                event.project_key,
                event.actor_role.value,
                event.work_item_id,
                event.run_id,
                event.phase_id,
                event.model_id,
                event.tool,
                event.cost_usd,
                event.outcome,
                event.model_dump_json(exclude={"seq"}),
            ),
        )
        return event.model_copy(update={"seq": cursor.lastrowid})

    async def query(
        self,
        *,
        kinds: list[LedgerEventKind] | None = None,
        work_item_id: WorkItemId | None = None,
        run_id: RunId | None = None,
        phase_id: PhaseId | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 1000,
    ) -> list[LedgerEvent]:
        """Return events matching every given filter, by ``seq`` ascending.

        ``since``/``until`` are inclusive bounds on ``at``; ``limit`` is clamped to
        ``0..10000``.
        """
        clauses: list[str] = []
        params: list[object] = []
        if kinds:
            clauses.append(f"kind IN ({', '.join('?' for _ in kinds)})")
            params.extend(kind.value for kind in kinds)
        for column, value in (
            ("work_item_id", work_item_id),
            ("run_id", run_id),
            ("phase_id", phase_id),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        if since is not None:
            clauses.append("at >= ?")
            params.append(_at_column(since))
        if until is not None:
            clauses.append("at <= ?")
            params.append(_at_column(until))
        where = " AND ".join(clauses) or "1=1"
        params.append(max(0, min(limit, _MAX_QUERY_LIMIT)))
        sql = f"SELECT seq, json FROM ledger_events WHERE {where} ORDER BY seq LIMIT ?"  # noqa: S608 - clauses are fixed strings
        rows = self._db.connect().execute(sql, params).fetchall()
        return [_from_row(row) for row in rows]

    async def after(self, seq: int, limit: int = 1000) -> list[LedgerEvent]:
        """Return up to ``limit`` events with ``seq`` greater than ``seq``, in order."""
        rows = (
            self._db.connect()
            .execute(
                "SELECT seq, json FROM ledger_events WHERE seq > ? ORDER BY seq LIMIT ?",
                (seq, max(0, min(limit, _MAX_QUERY_LIMIT))),
            )
            .fetchall()
        )
        return [_from_row(row) for row in rows]
