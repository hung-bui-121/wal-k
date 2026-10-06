"""SQLite repositories of the workflow aggregates (``work_items``, ``projects``)."""

import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import ClassVar

from pydantic import TypeAdapter

from walk.common.errors import ConfigError
from walk.common.ids import PhaseId, WorkItemId
from walk.common.models import utcnow
from walk.persistence import Repository, UnitOfWork
from walk.workflow.models import Project, WorkItem, WorkItemState, WorkItemTransition

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

    async def transitions(self, work_item_id: WorkItemId) -> list[WorkItemTransition]:
        """Return the item's transitions in commit order."""
        sql = f"{_SELECT_TRANSITIONS_SQL} WHERE work_item_id = ? ORDER BY seq"
        rows = self._db.connect().execute(sql, (work_item_id,)).fetchall()
        return [_transition(row) for row in rows]

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
