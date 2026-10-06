"""Default telemetry services: ledger, diagnostics/metrics, evidence."""

import asyncio
import hashlib
import logging
import shutil
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from walk.common.clock import Clock
from walk.common.errors import ConfigError
from walk.common.ids import IdFactory, PhaseId, RunId, Sha, WorkItemId
from walk.common.models import Actor
from walk.persistence import Database, IdSequenceStore, UnitOfWork
from walk.telemetry.logging import _FIELDS_ATTR, _LOG_RELATIVE_PATH, JsonLineHandler
from walk.telemetry.metrics import compute_metrics
from walk.telemetry.models import (
    EVIDENCE_RANK,
    Evidence,
    EvidenceDraft,
    EvidenceKind,
    LedgerEvent,
    LedgerEventKind,
    Report,
    RetrospectiveMetrics,
)
from walk.telemetry.protocols import LedgerManager
from walk.telemetry.repository import EvidenceRepository, LedgerRepository

_TAIL_POLL_INTERVAL_S = 0.25
_REPORT_EVENT_LIMIT = 10_000  # the query maximum
_METRICS_FLUSH_INTERVAL = timedelta(seconds=60)
_EXTERNAL_URI_PREFIXES = ("http://", "https://", "s3://")
_HASH_CHUNK_BYTES = 1 << 20


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


class DefaultTelemetryManager:
    """`TelemetryManager`: JSON-lines diagnostics, in-process counters/timers, ledger metrics.

    Counters and timers are flushed as one ``metrics`` log line when a call finds that 60 s
    (injected clock) have passed since the last flush, and on `close`. They are diagnostics,
    not the ledger.
    """

    def __init__(self, repo_root: Path, ledger: LedgerRepository, clock: Clock) -> None:
        """Log to ``<repo_root>/.walk/logs/kernel.jsonl``; compute metrics from ``ledger``."""
        self._handler = JsonLineHandler(repo_root / _LOG_RELATIVE_PATH)
        self._ledger = ledger
        self._clock = clock
        self._counters: dict[str, float] = {}
        self._timers: dict[str, dict[str, float]] = {}
        self._last_flush = clock.now()

    def counter(self, name: str, value: float = 1.0, **labels: str) -> None:
        """Add ``value`` to the counter ``name{labels}``."""
        self._maybe_flush()
        key = _metric_key(name, labels)
        self._counters[key] = self._counters.get(key, 0.0) + value

    def timer(self, name: str, seconds: float, **labels: str) -> None:
        """Record one duration: count, total and maximum per ``name{labels}``."""
        self._maybe_flush()
        stats = self._timers.setdefault(
            _metric_key(name, labels), {"count": 0, "total_s": 0.0, "max_s": 0.0}
        )
        stats["count"] += 1
        stats["total_s"] += seconds
        stats["max_s"] = max(stats["max_s"], seconds)

    async def metrics(
        self, *, phase_id: PhaseId | None = None, since: datetime | None = None
    ) -> RetrospectiveMetrics:
        """Evaluate `METRIC_QUERIES` over the ledger (zeros when empty)."""
        return await compute_metrics(self._ledger.db, phase_id=phase_id, since=since)

    def log(self, level: str, message: str, **fields: object) -> None:
        """Write one JSON line ``{ts, level, msg, **fields}``; never raises on odd fields.

        Unknown level names are written as given (upper-cased) at INFO severity.
        """
        self._maybe_flush()
        self._write(level, message, fields)

    def close(self) -> None:
        """Flush pending counters/timers and close the log file."""
        self._flush()
        self._handler.close()

    def _maybe_flush(self) -> None:
        if self._clock.now() - self._last_flush >= _METRICS_FLUSH_INTERVAL:
            self._flush()

    def _flush(self) -> None:
        self._last_flush = self._clock.now()
        if not self._counters and not self._timers:
            return
        fields: dict[str, object] = {"counters": self._counters, "timers": self._timers}
        self._counters, self._timers = {}, {}
        self._write("INFO", "metrics", fields)

    def _write(self, level: str, message: str, fields: dict[str, object]) -> None:
        name = level.upper()
        record = logging.LogRecord(
            "",  # no logger name: telemetry lines carry exactly ts, level, msg and the fields
            logging.getLevelNamesMapping().get(name, logging.INFO),
            "",
            0,
            message,
            None,
            None,
        )
        record.levelname = name
        record.created = self._clock.now().timestamp()
        setattr(record, _FIELDS_ATTR, fields)
        self._handler.handle(record)


def _metric_key(name: str, labels: dict[str, str]) -> str:
    if not labels:
        return name
    return name + "{" + ",".join(f"{k}={v}" for k, v in sorted(labels.items())) + "}"


class DefaultEvidenceManager:
    """`EvidenceManager`: files evidence under ``.ai/`` and indexes it (§6.6, §47).

    Folder rule: ``features/<id>`` for FEAT/STORY/TASK ids, ``bugs/<id>`` for BUG ids,
    ``phases/<phase>`` when only a phase is given; files keep their basename.
    """

    def __init__(  # noqa: PLR0917 - constructor fixed by the E01-S06 contract
        self,
        db: Database,
        ai_root: Path,
        repo: EvidenceRepository,
        ledger: LedgerManager,
        ids: IdSequenceStore,
        clock: Clock,
    ) -> None:
        """Wire the manager; ``ai_root`` is ``<repo>/.ai`` and its parent the repository root."""
        self._db = db
        self._ai_root = ai_root
        self._repo_root = ai_root.parent
        self._repo = repo
        self._ledger = ledger
        self._ids = ids
        self._clock = clock

    async def record(
        self,
        draft: EvidenceDraft,
        *,
        actor: Actor,
        work_item_id: WorkItemId | None,
        phase_id: PhaseId | None,
        commit: Sha | None,
    ) -> Evidence:
        """File, hash and index ``draft``; ledger ``EVIDENCE_RECORDED`` in the same transaction.

        Local paths are repository-relative (or absolute). External URIs (http, https, s3)
        are stored as given with ``sha256=None``.

        Raises:
            ConfigError: If the local file is missing, there is no evidence folder for the
                given ids, a different file already has the target name, or the database
                does not hold exactly one project.
        """
        created: Path | None = None
        if draft.path_or_uri.startswith(_EXTERNAL_URI_PREFIXES):
            uri, sha256 = draft.path_or_uri, None
        else:
            source = self._source(draft.path_or_uri)
            folder = self._folder(work_item_id, phase_id)
            stored, created = _store(source, folder)
            uri, sha256 = stored.relative_to(self._repo_root).as_posix(), _sha256(stored)
        try:
            async with UnitOfWork(self._db) as uow:
                project_key = await self._repo.project_key(uow)
                evidence = Evidence(
                    id=self._ids.bind(uow).next_sequence("EVD"),
                    kind=draft.kind,
                    description=draft.description,
                    uri=uri,
                    sha256=sha256,
                    produced_by=actor,
                    produced_at=self._clock.now(),
                    work_item_id=work_item_id,
                    phase_id=phase_id,
                    commit=commit,
                    metrics=draft.metrics,
                )
                await self._repo.insert(evidence, uow)
                await self._ledger.append(
                    LedgerEvent(
                        kind=LedgerEventKind.EVIDENCE_RECORDED,
                        at=evidence.produced_at,
                        project_key=project_key,
                        actor_role=actor.role,
                        work_item_id=work_item_id,
                        run_id=actor.run_id,
                        phase_id=phase_id,
                        model_id=actor.model_id,
                        payload={"evidence_id": evidence.id, "kind": evidence.kind.value},
                    ),
                    uow=uow,
                )
        except BaseException:
            # The row was rolled back; do not leave an unindexed copy behind.
            if created is not None:
                created.unlink(missing_ok=True)
            raise
        return evidence

    async def for_item(
        self, work_item_id: WorkItemId, kinds: list[EvidenceKind] | None = None
    ) -> list[Evidence]:
        """Return the item's evidence, oldest first; ``kinds`` (if non-empty) filters."""
        return await self._repo.for_item(work_item_id, kinds)

    async def for_phase(self, phase_id: PhaseId) -> list[Evidence]:
        """Return the phase's evidence, oldest first."""
        return await self._repo.for_phase(phase_id)

    def strongest(self, evidence: list[Evidence]) -> Evidence | None:
        """Return the highest-ranked evidence (§47); ties go to the newest."""
        if not evidence:
            return None
        return max(evidence, key=lambda e: (EVIDENCE_RANK[e.kind], e.produced_at))

    def satisfies(
        self, required: list[EvidenceKind], present: list[Evidence]
    ) -> list[EvidenceKind]:
        """Return the required kinds absent from ``present``, in ``required`` order, once each."""
        have = {e.kind for e in present}
        return [kind for kind in dict.fromkeys(required) if kind not in have]

    def _source(self, path_or_uri: str) -> Path:
        path = Path(path_or_uri)
        source = path if path.is_absolute() else self._repo_root / path
        if not source.is_file():
            msg = f"evidence file not found: {path_or_uri}"
            raise ConfigError(msg, detail={"path": str(source)})
        return source

    def _folder(self, work_item_id: WorkItemId | None, phase_id: PhaseId | None) -> Path:
        if work_item_id is not None:
            prefix = work_item_id.split("-", 1)[0]
            if prefix in {"FEAT", "STORY", "TASK"}:
                return self._ai_root / "features" / work_item_id / "evidence"
            if prefix == "BUG":
                return self._ai_root / "bugs" / work_item_id / "evidence"
            msg = f"no evidence folder for {work_item_id}"
            raise ConfigError(msg, detail={"work_item_id": work_item_id})
        if phase_id is not None:
            return self._ai_root / "phases" / phase_id / "evidence"
        msg = "local evidence needs a work item or a phase"
        raise ConfigError(msg)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _store(source: Path, folder: Path) -> tuple[Path, Path | None]:
    """Copy ``source`` into ``folder`` atomically; return the target and, if new, the copy.

    Evidence is immutable, so an existing target is reused only when its content is identical.
    """
    target = folder / source.name
    if target.exists():
        if target.resolve() == source.resolve() or _sha256(target) == _sha256(source):
            return target, None
        msg = f"different evidence already stored as {target.name}"
        raise ConfigError(msg, detail={"target": str(target), "source": str(source)})
    folder.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(f"{target.name}.partial")
    shutil.copyfile(source, partial)
    partial.replace(target)
    return target, target
