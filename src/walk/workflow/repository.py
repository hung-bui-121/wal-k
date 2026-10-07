"""SQLite repositories of the workflow aggregates (work items, projects, phases, RCs)."""

import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import ClassVar

from pydantic import TypeAdapter

from walk.common.errors import ConfigError
from walk.common.ids import PhaseId, ProjectKey, RunId, WorkItemId
from walk.common.models import utcnow
from walk.persistence import Repository, UnitOfWork
from walk.workflow.errors import WorkItemNotFound
from walk.workflow.models import (
    Phase,
    Priority,
    Project,
    ReleaseCandidate,
    WorkItem,
    WorkItemState,
    WorkItemTransition,
)

_WORK_ITEM: TypeAdapter[WorkItem] = TypeAdapter(WorkItem)
_CREATION_ORDER = "created_at, id"
_TRANSITION_COLUMNS = (
    "seq, work_item_id, from_state, to_state, event, source, actor_role, run_id, reason, at"
)
_INSERT_TRANSITION_SQL = (
    "INSERT INTO work_item_transitions (work_item_id, from_state, to_state, event, source, "
    "actor_role, run_id, reason, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
_SELECT_TRANSITIONS_SQL = f"SELECT {_TRANSITION_COLUMNS} FROM work_item_transitions"  # noqa: S608 - constant


def _transition(row: sqlite3.Row) -> WorkItemTransition:
    return WorkItemTransition.model_validate(dict(row))


def _utc_text(value: datetime) -> str:
    """Fixed-width UTC text so that timestamp columns order correctly as strings."""
    return value.astimezone(UTC).isoformat(timespec="microseconds")


class WorkflowRepository(Repository[WorkItem]):
    """``work_items``: the `WorkItem` JSON (discriminated on ``kind``) plus indexed columns."""

    _table: ClassVar[str] = "work_items"

    def projection(self, obj: WorkItem) -> dict[str, object]:
        """Indexed columns of the ``work_items`` table."""
        return {
            "kind": obj.kind,
            "project_key": obj.project_key,
            "parent_id": obj.parent_id,
            "phase_id": obj.phase_id,
            "state": obj.state,
            "state_version": obj.state_version,
            "title": obj.title,
            "owner_role": obj.owner_role,
            "assigned_run_id": obj.assigned_run_id,
            "external_ref": obj.external_ref,
            "priority": obj.priority,
            "risk": obj.risk,
            "fix_loops": obj.fix_loops,
            "created_at": _utc_text(obj.created_at),
            "updated_at": _utc_text(obj.updated_at),
        }

    async def set_priority(
        self, work_item_id: WorkItemId, priority: Priority, uow: UnitOfWork
    ) -> WorkItem:
        """Set the item's ``priority`` (column and JSON) on ``uow``; nothing else changes.

        Raises:
            WorkItemNotFound: No item has ``work_item_id``.
        """
        item = await self.get(work_item_id)
        if item is None:
            msg = f"work item not found: {work_item_id}"
            raise WorkItemNotFound(msg, detail={"work_item_id": work_item_id})
        updated = item.model_copy(update={"priority": priority})
        await self.upsert(updated, uow)
        return updated

    async def set_assigned_run(
        self,
        work_item_id: WorkItemId,
        run_id: RunId | None,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> WorkItem:
        """Set (or clear, with ``None``) the item's ``assigned_run_id``; nothing else changes.

        The item is read on the same connection, so the caller's open transaction sees its own
        writes; the row is written on ``conn`` or in a unit of work of its own.

        Raises:
            WorkItemNotFound: No item has ``work_item_id``.
        """
        item = await self.get(work_item_id)
        if item is None:
            msg = f"work item not found: {work_item_id}"
            raise WorkItemNotFound(msg, detail={"work_item_id": work_item_id})
        updated = item.model_copy(update={"assigned_run_id": run_id})
        if conn is not None:
            _update_assigned_run(conn, updated)
        else:
            async with UnitOfWork(self._db) as uow:
                _update_assigned_run(uow.conn, updated)
        return updated

    async def by_external_ref(self, external_ref: str) -> WorkItem | None:
        """Return the item linked to the work-provider reference, or ``None``."""
        found = await self.list_where(
            "external_ref = ?", [external_ref], order_by=_CREATION_ORDER, limit=1
        )
        return found[0] if found else None

    async def children(self, parent_id: WorkItemId) -> list[WorkItem]:
        """Return the direct children of ``parent_id`` in creation order."""
        return await self.list_where("parent_id = ?", [parent_id], order_by=_CREATION_ORDER)

    async def phase_exists(self, phase_id: PhaseId) -> bool:
        """Return whether ``phases`` holds ``phase_id`` (work items reference it)."""
        row = self._db.connect().execute("SELECT 1 FROM phases WHERE id = ?", (phase_id,))
        return row.fetchone() is not None

    async def states_of(self, ids: Sequence[WorkItemId]) -> dict[WorkItemId, WorkItemState]:
        """Return the current state of each existing item in ``ids``; unknown ids are absent."""
        if not ids:
            return {}
        marks = ", ".join("?" for _ in ids)
        sql = f"SELECT id, state FROM work_items WHERE id IN ({marks})"  # noqa: S608 - placeholders only
        rows = self._db.connect().execute(sql, list(ids)).fetchall()
        return {str(row["id"]): WorkItemState(row["state"]) for row in rows}

    async def add_transition(
        self, transition: WorkItemTransition, uow: UnitOfWork
    ) -> WorkItemTransition:
        """Append a ``work_item_transitions`` row and return it with the assigned ``seq``.

        The ``seq`` of ``transition`` is ignored; SQLite assigns it.
        """
        cursor = uow.conn.execute(
            _INSERT_TRANSITION_SQL,
            (
                transition.work_item_id,
                transition.from_state.value,
                transition.to_state.value,
                transition.event,
                transition.source.value,
                transition.actor_role.value,
                transition.run_id,
                transition.reason,
                _utc_text(transition.at),
            ),
        )
        return transition.model_copy(update={"seq": cursor.lastrowid})

    async def transitions(
        self, work_item_id: WorkItemId, *, limit: int | None = 5
    ) -> list[WorkItemTransition]:
        """Return the item's newest transitions first; ``limit=None`` returns all of them."""
        sql = f"{_SELECT_TRANSITIONS_SQL} WHERE work_item_id = ? ORDER BY seq DESC LIMIT ?"
        rows = self._db.connect().execute(sql, (work_item_id, -1 if limit is None else limit))
        return [_transition(row) for row in rows.fetchall()]

    async def last_transition_into(
        self, work_item_id: WorkItemId, state: WorkItemState
    ) -> WorkItemTransition | None:
        """Return the item's most recent transition whose target is ``state``, or ``None``."""
        sql = (
            f"{_SELECT_TRANSITIONS_SQL} WHERE work_item_id = ? AND to_state = ? "
            "ORDER BY seq DESC LIMIT 1"
        )
        row = self._db.connect().execute(sql, (work_item_id, state.value)).fetchone()
        return None if row is None else _transition(row)

    def items_by_id(self, ids: Sequence[WorkItemId]) -> list[WorkItem]:
        """Return the existing items among ``ids`` (synchronous: Definition of Ready reads it)."""
        if not ids:
            return []
        marks = ", ".join("?" for _ in ids)
        sql = f"SELECT json FROM work_items WHERE id IN ({marks}) ORDER BY id"  # noqa: S608 - placeholders only
        rows = self._db.connect().execute(sql, list(ids)).fetchall()
        return [self._load(row[0]) for row in rows]

    def _load(self, raw: str) -> WorkItem:
        return _WORK_ITEM.validate_json(raw)


def _update_assigned_run(conn: sqlite3.Connection, item: WorkItem) -> None:
    conn.execute(
        "UPDATE work_items SET assigned_run_id = ?, json = ? WHERE id = ?",
        (item.assigned_run_id, item.model_dump_json(), item.id),
    )


class ProjectRepository(Repository[Project]):
    """``projects``: one row per database (ADR-0002 D-1), keyed by ``key``."""

    _table: ClassVar[str] = "projects"
    _model = Project
    _key: ClassVar[str] = "key"

    def projection(self, obj: Project) -> dict[str, object]:
        """Indexed columns of the ``projects`` table.

        ``Project`` has no ``updated_at`` field; the column records the time of the write.
        """
        return {
            "name": obj.name,
            "repo_path": obj.repo_path,
            "current_phase_id": obj.current_phase_id,
            "paused": obj.paused,
            "created_at": _utc_text(obj.created_at),
            "updated_at": _utc_text(utcnow()),
        }

    async def set_paused(self, key: ProjectKey, paused: bool, uow: UnitOfWork) -> Project:  # noqa: FBT001 - the flag is the value being written
        """Set ``Project.paused`` (column and JSON) on ``uow`` (§93 ``walk pause``).

        Raises:
            ConfigError: No project has ``key``.
        """
        return await self._update(key, uow, paused=paused)

    async def set_autonomy_level_max(self, key: ProjectKey, level: int, uow: UnitOfWork) -> Project:
        """Set ``Project.autonomy_level_max`` on ``uow`` (§93 ``walk policy set-autonomy``).

        Raises:
            ConfigError: No project has ``key``.
            ValidationError: ``level`` is outside 0-3.
        """
        return await self._update(key, uow, autonomy_level_max=level)

    async def _update(self, key: ProjectKey, uow: UnitOfWork, **fields: object) -> Project:
        project = await self.get(key)
        if project is None:
            msg = f"unknown project {key}"
            raise ConfigError(msg, detail={"project_key": key})
        updated = Project.model_validate({**project.model_dump(), **fields})
        await self.upsert(updated, uow)
        return updated

    async def single(self) -> Project:
        """Return the project this database belongs to.

        Raises:
            ConfigError: If the database does not hold exactly one project.
        """
        projects = await self.list_where(order_by="key")
        if len(projects) != 1:
            msg = f"expected exactly one project in the database, found {len(projects)}"
            raise ConfigError(msg, detail={"projects": [p.key for p in projects]})
        return projects[0]


class PhaseRepository(Repository[Phase]):
    """``phases``: the `Phase` JSON plus ordinal/state columns (ordinal unique per project)."""

    _table: ClassVar[str] = "phases"
    _model = Phase

    def projection(self, obj: Phase) -> dict[str, object]:
        """Indexed columns of the ``phases`` table.

        ``Phase`` has no ``updated_at`` field; the column records the time of the write.
        """
        return {
            "project_key": obj.project_key,
            "ordinal": obj.ordinal,
            "state": obj.state,
            "gate_round": obj.gate_round,
            "updated_at": _utc_text(utcnow()),
        }

    async def ordered(self) -> list[Phase]:
        """Return every phase by ordinal."""
        return await self.list_where(order_by="ordinal")

    async def by_ordinal(self, project_key: ProjectKey, ordinal: int) -> Phase | None:
        """Return the project's phase with ``ordinal``, or ``None``."""
        found = await self.list_where(
            "project_key = ? AND ordinal = ?", [project_key, ordinal], limit=1
        )
        return found[0] if found else None


class ReleaseCandidateRepository(Repository[ReleaseCandidate]):
    """``release_candidates``: the `ReleaseCandidate` JSON plus number/state/commit columns."""

    _table: ClassVar[str] = "release_candidates"
    _model = ReleaseCandidate

    def projection(self, obj: ReleaseCandidate) -> dict[str, object]:
        """Indexed columns of the ``release_candidates`` table."""
        return {
            "project_key": obj.project_key,
            "number": obj.number,
            "state": obj.state,
            "commit_sha": obj.commit,
            "created_at": _utc_text(obj.created_at),
        }
