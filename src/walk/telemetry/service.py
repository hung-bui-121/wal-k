"""Default telemetry services."""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import datetime
from typing import Literal

from walk.common.clock import Clock
from walk.common.ids import IdFactory, PhaseId, RunId, WorkItemId
from walk.persistence import Database, UnitOfWork
from walk.telemetry.models import LedgerEvent, LedgerEventKind, Report
from walk.telemetry.repository import LedgerRepository

_TAIL_POLL_INTERVAL_S = 0.25
_REPORT_EVENT_LIMIT = 10_000  # the query maximum


class DefaultLedgerManager:
    """`LedgerManager` over SQLite (ARCHITECTURE §4.3 write points call `append`)."""

    def __init__(
        self,
        db: Database,
        repo: LedgerRepository,
        ids: IdFactory,
        clock: Clock,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Wire the manager.

        Args:
            db: Project database; `append` without a unit of work opens one on it.
            repo: Ledger table access.
            ids: Mints the ULID of events appended without an ``id``.
            clock: Stamps events appended without an ``at``.
            sleep: Awaited between `tail` polls; injected so tests do not wait.
        """
        self._db = db
        self._repo = repo
        self._ids = ids
        self._clock = clock
        self._sleep = sleep

    async def append(self, event: LedgerEvent, *, uow: UnitOfWork | None = None) -> LedgerEvent:
        """Insert ``event`` and return it with ``seq``.

        ``id`` and ``at`` not set by the caller are filled from the id factory and the clock.
        With ``uow`` the row joins the caller's transaction; otherwise it commits on its own.
        """
        updates: dict[str, object] = {}
        if "id" not in event.model_fields_set:
            updates["id"] = f"LED-{self._ids.new_ulid()}"
        if "at" not in event.model_fields_set:
            updates["at"] = self._clock.now()
        complete = LedgerEvent.model_validate(event.model_dump() | updates)
        if uow is not None:
            return self._repo.insert(complete, uow.conn)
        async with UnitOfWork(self._db) as own:
            return self._repo.insert(complete, own.conn)

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
        """Return matching events by ``seq`` ascending; ``limit`` is clamped to 10000."""
        return await self._repo.query(
            kinds=kinds,
            work_item_id=work_item_id,
            run_id=run_id,
            phase_id=phase_id,
            since=since,
            until=until,
            limit=limit,
        )

    async def tail(self, after_seq: int) -> AsyncGenerator[LedgerEvent]:
        """Yield events with ``seq > after_seq`` in order; poll every 0.25 s until cancelled."""
        last = after_seq
        while True:
            events = await self._repo.after(last)
            for event in events:
                if event.seq is not None:
                    last = event.seq
                yield event
            if not events:
                await self._sleep(_TAIL_POLL_INTERVAL_S)

    async def report(
        self,
        kind: Literal["task", "feature", "phase", "project", "cost", "improvement"],
        subject_id: str,
    ) -> Report:
        """Return the subject's events as report data; ``markdown`` stays empty until E09.

        ``task``/``feature`` select by work item, ``phase`` by phase; ``project``, ``cost``
        and ``improvement`` take every event (up to the query limit).
        """
        if kind in ("task", "feature"):
            events = await self.query(work_item_id=subject_id, limit=_REPORT_EVENT_LIMIT)
        elif kind == "phase":
            events = await self.query(phase_id=subject_id, limit=_REPORT_EVENT_LIMIT)
        else:
            events = await self.query(limit=_REPORT_EVENT_LIMIT)
        return Report(
            kind=kind,
            subject_id=subject_id,
            generated_at=self._clock.now(),
            markdown="",
            data={"events": [event.model_dump(mode="json") for event in events]},
        )
