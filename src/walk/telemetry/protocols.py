"""Telemetry service protocols (INTERFACES §1.14)."""

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Literal, Protocol

from walk.common.ids import PhaseId, RunId, Sha, WorkItemId
from walk.common.models import Actor
from walk.persistence import UnitOfWork
from walk.telemetry.models import (
    Evidence,
    EvidenceDraft,
    EvidenceKind,
    LedgerEvent,
    LedgerEventKind,
    Report,
    RetrospectiveMetrics,
)


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


class EvidenceManager(Protocol):
    """§6.6, §47. Hosted by walk.telemetry."""

    async def record(
        self,
        draft: EvidenceDraft,
        *,
        actor: Actor,
        work_item_id: WorkItemId | None,
        phase_id: PhaseId | None,
        commit: Sha | None,
    ) -> Evidence:
        """Copy/link the file under `.ai/<features|bugs|phases>/<id>/evidence/`, hash it.

        Mints the EVD id and writes the ledger event `EVIDENCE_RECORDED`.
        """
        ...

    async def for_item(
        self, work_item_id: WorkItemId, kinds: list[EvidenceKind] | None = None
    ) -> list[Evidence]:
        """Return the item's evidence, oldest first, optionally only of ``kinds``."""
        ...

    async def for_phase(self, phase_id: PhaseId) -> list[Evidence]:
        """Return the phase's evidence, oldest first."""
        ...

    def strongest(self, evidence: list[Evidence]) -> Evidence | None:
        """Return the maximum by rank (§47), ties by produced_at desc."""
        ...

    def satisfies(
        self, required: list[EvidenceKind], present: list[Evidence]
    ) -> list[EvidenceKind]:
        """Returns missing kinds (guard `required_evidence_present`)."""
        ...


class TelemetryManager(Protocol):
    """§86 metrics + §116 improvement metrics. Hosted by walk.telemetry."""

    def counter(self, name: str, value: float = 1.0, **labels: str) -> None:
        """Add ``value`` to an in-process counter (diagnostics, not the ledger)."""
        ...

    def timer(self, name: str, seconds: float, **labels: str) -> None:
        """Record one duration sample (diagnostics, not the ledger)."""
        ...

    async def metrics(
        self, *, phase_id: PhaseId | None = None, since: datetime | None = None
    ) -> RetrospectiveMetrics:
        """Computed from ledger.

        First-pass rate = items reaching COMPLETE with fix_loops == 0 / completed; etc.
        """
        ...

    def log(self, level: str, message: str, **fields: object) -> None:
        """JSON line to `.walk/logs/kernel.jsonl`; diagnostics only (ADR-0001)."""
        ...
