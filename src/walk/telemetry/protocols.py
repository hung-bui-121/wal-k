"""Telemetry service protocols (INTERFACES §1.14)."""

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Literal, Protocol

from walk.common.ids import PhaseId, RunId, WorkItemId
from walk.persistence import UnitOfWork
from walk.telemetry.models import LedgerEvent, LedgerEventKind, Report


class LedgerManager(Protocol):
    """§81-§83, §86. Hosted by walk.telemetry."""

    async def append(self, event: LedgerEvent, *, uow: UnitOfWork | None = None) -> LedgerEvent:
        """Insert; returns event with seq. Participates in the caller's UnitOfWork when provided."""
        ...

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
        """Return matching events by ``seq`` ascending; filters are ANDed."""
        ...

    def tail(self, after_seq: int) -> AsyncIterator[LedgerEvent]:
        """Yield events with ``seq > after_seq`` in order, polling for new ones until cancelled."""
        ...

    async def report(
        self,
        kind: Literal["task", "feature", "phase", "project", "cost", "improvement"],
        subject_id: str,
    ) -> Report:
        """§83 generated from events only."""
        ...
