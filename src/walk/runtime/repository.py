"""Runtime persistence: `agent_runs`, `checkpoints` and `handovers` (DOMAIN-MODEL §6.2)."""

import sqlite3
from typing import ClassVar, Final

from walk.agents.models import Handover
from walk.common.clock import Clock, SystemClock
from walk.common.errors import ConfigError
from walk.common.ids import HandoverId, RunId, WorkItemId
from walk.persistence.database import Database
from walk.persistence.repository import Repository
from walk.persistence.uow import UnitOfWork
from walk.runtime.errors import RunNotFound
from walk.runtime.models import AgentRun, AgentRunState, Checkpoint

_TERMINAL_STATES: Final = frozenset(
    {
        AgentRunState.HANDED_OVER,
        AgentRunState.COMPLETED,
        AgentRunState.FAILED,
        AgentRunState.FAILED_HOOK,
        AgentRunState.FAILED_BOUNDARY,
        AgentRunState.BLOCKED_BUDGET,
        AgentRunState.BLOCKED_PROVIDER,
        AgentRunState.CANCELLED,
    }
)


class AgentRunRepository(Repository[AgentRun]):
    """``agent_runs``: the `AgentRun` JSON plus the recovery and per-item query columns."""

    _table: ClassVar[str] = "agent_runs"
    _model = AgentRun

    def __init__(self, db: Database, *, clock: Clock | None = None) -> None:
        """Bind to ``db``; ``clock`` stamps ``ended_at`` (the system clock by default)."""
        super().__init__(db)
        self._clock: Clock = clock if clock is not None else SystemClock()

    def projection(self, obj: AgentRun) -> dict[str, object]:
        """Indexed columns of the ``agent_runs`` table."""
        return {
            "project_key": obj.project_key,
            "work_item_id": obj.work_item_id,
            "role": obj.role,
            "model_id": obj.model_id,
            "provider": obj.provider,
            "effort": obj.effort,
            "state": obj.state,
            "purpose": obj.purpose,
            "kernel_instance": obj.kernel_instance,
            "parent_run_id": obj.parent_run_id,
            "provider_session_id": obj.provider_session.session_id
            if obj.provider_session is not None
            else None,
            "started_at": obj.started_at,
            "ended_at": obj.ended_at,
        }

    async def by_state(
        self, states: list[AgentRunState], *, kernel_instance_not: str | None = None
    ) -> list[AgentRun]:
        """Runs in any of ``states``, optionally excluding one kernel instance's runs.

        ``by_state([RUNNING, PAUSED_FOR_APPROVAL], kernel_instance_not=<me>)`` is the recovery
        query (ARCHITECTURE §5.3 step 1).
        """
        if not states:
            return []
        marks = ", ".join("?" for _ in states)
        where = f"state IN ({marks})"
        params: list[object] = [state.value for state in states]
        if kernel_instance_not is not None:
            where += " AND kernel_instance != ?"
            params.append(kernel_instance_not)
        return await self.list_where(where, params, order_by="started_at, id")

    async def for_item(self, work_item_id: WorkItemId) -> list[AgentRun]:
        """Every run of the work item, oldest first."""
        return await self.list_where("work_item_id = ?", (work_item_id,), order_by="started_at, id")

    async def set_state(
        self,
        run_id: RunId,
        state: AgentRunState,
        *,
        failure_reason: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> AgentRun:
        """Set ``state`` (and ``failure_reason`` when given); stamp or clear ``ended_at``.

        ``ended_at`` is the clock time for an end state and ``None`` otherwise. The row is
        written on ``conn`` (the caller's open transaction) or in a unit of work of its own.

        Raises:
            RunNotFound: No run has ``run_id``.
        """
        run = await self.get(run_id)
        if run is None:
            msg = f"unknown run {run_id}"
            raise RunNotFound(msg, detail={"run_id": run_id})
        updates: dict[str, object] = {
            "state": state,
            "ended_at": self._clock.now() if state in _TERMINAL_STATES else None,
        }
        if failure_reason is not None:
            updates["failure_reason"] = failure_reason
        updated = run.model_copy(update=updates)
        if conn is not None:
            _update_state(conn, updated)
        else:
            async with UnitOfWork(self._db) as uow:
                _update_state(uow.conn, updated)
        return updated


def _update_state(conn: sqlite3.Connection, run: AgentRun) -> None:
    conn.execute(
        "UPDATE agent_runs SET state = ?, ended_at = ?, json = ? WHERE id = ?",
        (
            run.state.value,
            run.ended_at.isoformat() if run.ended_at is not None else None,
            run.model_dump_json(),
            run.id,
        ),
    )


class CheckpointRepository:
    """``checkpoints``: append-only (no update or delete; triggers enforce it, ADR-0002)."""

    def __init__(self, db: Database) -> None:
        """Bind to ``db``."""
        self._db = db

    async def insert(self, checkpoint: Checkpoint, conn: sqlite3.Connection) -> Checkpoint:
        """Insert ``checkpoint`` on ``conn``.

        A duplicate ``(run_id, seq)`` raises ``sqlite3.IntegrityError``.
        """
        conn.execute(
            "INSERT INTO checkpoints (id, run_id, work_item_id, seq, kind, head_sha, handover_id, "
            "at, json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                checkpoint.id,
                checkpoint.run_id,
                checkpoint.work_item_id,
                checkpoint.seq,
                checkpoint.kind.value,
                checkpoint.head_sha,
                checkpoint.handover_id,
                checkpoint.at.isoformat(),
                checkpoint.model_dump_json(),
            ),
        )
        return checkpoint

    async def latest(self, run_id: RunId) -> Checkpoint | None:
        """The run's checkpoint with the highest ``seq``."""
        return self._one("run_id = ? ORDER BY seq DESC", (run_id,))

    async def latest_for_item(self, work_item_id: WorkItemId) -> Checkpoint | None:
        """The item's newest checkpoint over all its runs (latest insert wins a time tie)."""
        return self._one("work_item_id = ? ORDER BY at DESC, rowid DESC", (work_item_id,))

    async def next_seq(self, run_id: RunId) -> int:
        """``max(seq) + 1`` of the run; 1 for its first checkpoint."""
        row = (
            self._db.connect()
            .execute("SELECT COALESCE(MAX(seq), 0) FROM checkpoints WHERE run_id = ?", (run_id,))
            .fetchone()
        )
        return int(row[0]) + 1

    def _one(self, clause: str, params: tuple[object, ...]) -> Checkpoint | None:
        row = (
            self._db.connect()
            .execute(f"SELECT json FROM checkpoints WHERE {clause} LIMIT 1", params)  # noqa: S608 - kernel-written clause
            .fetchone()
        )
        return None if row is None else Checkpoint.model_validate_json(row[0])


class HandoverRepository(Repository[Handover]):
    """``handovers``: one row per §22 handover; the document lives in `.ai/handovers/`."""

    _table: ClassVar[str] = "handovers"
    _model = Handover

    def projection(self, obj: Handover) -> dict[str, object]:
        """Indexed columns; ``ai_path`` is the document path relative to `.ai/`."""
        return {
            "work_item_id": obj.work_item_id,
            "from_run_id": obj.from_run_id,
            "to_run_id": obj.to_run_id,
            "reason": obj.reason,
            "ai_path": f"handovers/{obj.id}.md",
            "created_at": obj.created_at,
        }

    async def latest_open(self, work_item_id: WorkItemId) -> Handover | None:
        """The item's newest handover nobody has continued yet (``to_run_id`` IS NULL)."""
        found = await self.list_where(
            "work_item_id = ? AND to_run_id IS NULL",
            (work_item_id,),
            order_by="created_at DESC, id DESC",
            limit=1,
        )
        return found[0] if found else None

    async def close(self, handover_id: HandoverId, to_run_id: RunId) -> Handover:
        """Record ``to_run_id`` as the run continuing the handover.

        Raises:
            ConfigError: No handover has ``handover_id``.
        """
        handover = await self.get(handover_id)
        if handover is None:
            msg = f"unknown handover {handover_id}"
            raise ConfigError(msg, detail={"handover_id": handover_id})
        closed = handover.model_copy(update={"to_run_id": to_run_id})
        async with UnitOfWork(self._db) as uow:
            await self.upsert(closed, uow)
        return closed
