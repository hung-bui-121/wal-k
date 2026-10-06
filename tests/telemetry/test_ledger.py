import asyncio
import re
import sqlite3
from datetime import UTC, datetime, timedelta, timezone

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from walk.common.roles import AgentRole
from walk.persistence import Database, UnitOfWork
from walk.telemetry import (
    DefaultLedgerManager,
    LedgerEvent,
    LedgerEventKind,
    LedgerManager,
    LedgerRepository,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _event(
    kind: LedgerEventKind = LedgerEventKind.WORK_ITEM_CREATED,
    *,
    item: str | None = None,
    phase: str | None = None,
    run: str | None = None,
    at: datetime | None = None,
) -> LedgerEvent:
    fields: dict[str, object] = {
        "kind": kind,
        "project_key": "DEMO",
        "actor_role": AgentRole.KERNEL,
        "work_item_id": item,
        "phase_id": phase,
        "run_id": run,
    }
    if at is not None:
        fields["at"] = at
    return LedgerEvent.model_validate(fields)


class NoSleep:
    """Injected sleep: yields to the loop and counts polls."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        await asyncio.sleep(0)


@pytest.fixture
def ledger(
    db: Database, fake_clock: FakeClock, sequential_ids: SequentialIdFactory
) -> DefaultLedgerManager:
    return DefaultLedgerManager(
        db, LedgerRepository(db), sequential_ids, fake_clock, sleep=NoSleep()
    )


async def test_append_assigns_id_time_and_seq(
    ledger: DefaultLedgerManager, fake_clock: FakeClock
) -> None:
    stored = await ledger.append(_event())
    assert stored.seq == 1
    assert re.fullmatch(r"LED-[0-9A-HJKMNP-TV-Z]{26}", stored.id)
    assert stored.id == "LED-00000000000000000000000001"
    assert stored.at == fake_clock.now()
    assert (await ledger.query()) == [stored]


async def test_append_keeps_caller_id_and_time(ledger: DefaultLedgerManager) -> None:
    at = T0 + timedelta(hours=1)
    event = LedgerEvent(
        id="LED-01J00000000000000000000000",
        at=at,
        kind=LedgerEventKind.ERROR,
        project_key="DEMO",
        actor_role=AgentRole.KERNEL,
    )
    stored = await ledger.append(event)
    assert stored.id == "LED-01J00000000000000000000000"
    assert stored.at == at
    assert stored.seq == 1


async def test_append_participates_in_caller_transaction(
    db: Database, ledger: DefaultLedgerManager
) -> None:
    async def rolled_back() -> None:
        async with UnitOfWork(db) as uow:
            await ledger.append(_event(), uow=uow)
            msg = "abort"
            raise RuntimeError(msg)

    with pytest.raises(RuntimeError):
        await rolled_back()
    assert await ledger.query() == []
    async with UnitOfWork(db) as uow:
        await ledger.append(_event(), uow=uow)
    assert len(await ledger.query()) == 1


async def test_query_filters_and_orders(
    ledger: DefaultLedgerManager, fake_clock: FakeClock
) -> None:
    created = LedgerEventKind.WORK_ITEM_CREATED
    moved = LedgerEventKind.WORK_ITEM_TRANSITION
    specs = [
        (created, "STORY-0001"),
        (moved, "STORY-0002"),
        (moved, "STORY-0001"),
        (LedgerEventKind.ERROR, "STORY-0001"),
        (moved, "STORY-0001"),
    ]
    for kind, item in specs:
        fake_clock.advance(60)
        await ledger.append(_event(kind, item=item, run="RUN-" + "0" * 26))
    found = await ledger.query(kinds=[created, moved], work_item_id="STORY-0001")
    assert [(e.seq, e.kind) for e in found] == [(1, created), (3, moved), (5, moved)]
    assert [e.seq for e in await ledger.query(run_id="RUN-" + "0" * 26, limit=2)] == [1, 2]
    window = await ledger.query(since=T0 + timedelta(minutes=2), until=T0 + timedelta(minutes=4))
    assert [e.seq for e in window] == [2, 3, 4]
    assert await ledger.query(phase_id="PHASE-01") == []


async def test_query_normalises_non_utc_bounds(ledger: DefaultLedgerManager) -> None:
    plus_two = timezone(timedelta(hours=2))
    await ledger.append(_event(at=datetime(2026, 1, 1, 2, tzinfo=plus_two)))  # == T0
    assert len(await ledger.query(since=datetime(2026, 1, 1, 1, tzinfo=plus_two))) == 1
    assert await ledger.query(since=datetime(2026, 1, 1, 3, tzinfo=plus_two)) == []
    stored = (await ledger.query())[0]
    assert stored.at == T0


async def test_query_clamps_limit(db: Database, ledger: DefaultLedgerManager) -> None:
    conn = db.connect()
    conn.execute("BEGIN")
    for n in range(10_005):
        conn.execute(
            "INSERT INTO ledger_events (id, kind, at, project_key, actor_role, json) "
            "VALUES (?, 'ERROR', ?, 'DEMO', 'KERNEL', ?)",
            (
                f"LED-{n:026d}",
                T0.isoformat(),
                _event(LedgerEventKind.ERROR, at=T0).model_dump_json(exclude={"seq"}),
            ),
        )
    conn.execute("COMMIT")
    assert len(await ledger.query(limit=20_000)) == 10_000
    assert await ledger.query(limit=0) == []


async def test_tail_streams_new_events_until_cancelled(db: Database, fake_clock: FakeClock) -> None:
    sleep = NoSleep()
    ledger = DefaultLedgerManager(
        db, LedgerRepository(db), SequentialIdFactory(), fake_clock, sleep=sleep
    )
    await ledger.append(_event(item="STORY-0001"))
    received: list[int] = []
    three = asyncio.Event()

    async def consume() -> None:
        async for event in ledger.tail(0):
            assert event.seq is not None
            received.append(event.seq)
            if len(received) == 3:
                three.set()

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)
    await ledger.append(_event(item="STORY-0002"))
    await ledger.append(_event(item="STORY-0003"))
    await asyncio.wait_for(three.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert received == [1, 2, 3]
    assert sleep.calls
    assert set(sleep.calls) == {0.25}


async def test_tail_skips_events_up_to_after_seq(ledger: DefaultLedgerManager) -> None:
    for _ in range(3):
        await ledger.append(_event())
    stream = ledger.tail(2)
    first = await anext(stream)
    await stream.aclose()
    assert first.seq == 3


async def test_ledger_rows_are_immutable(db: Database, ledger: DefaultLedgerManager) -> None:
    await ledger.append(_event())
    with pytest.raises(sqlite3.IntegrityError):
        db.connect().execute("UPDATE ledger_events SET outcome = 'OK'")
    with pytest.raises(sqlite3.IntegrityError):
        db.connect().execute("DELETE FROM ledger_events")
    public = {name for name in dir(LedgerRepository) if not name.startswith("_")}
    assert public == {"insert", "query", "after", "db"}  # reads only; no update/delete


async def test_report_returns_subject_events(
    ledger: DefaultLedgerManager, fake_clock: FakeClock
) -> None:
    await ledger.append(_event(item="STORY-0001", phase="PHASE-01"))
    await ledger.append(_event(item="STORY-0002", phase="PHASE-01"))
    await ledger.append(_event(item="STORY-0001"))
    report = await ledger.report("task", "STORY-0001")
    assert (report.kind, report.subject_id, report.markdown) == ("task", "STORY-0001", "")
    assert report.generated_at == fake_clock.now()
    events = report.data["events"]
    assert [e["seq"] for e in events] == [1, 3]
    assert {e["work_item_id"] for e in events} == {"STORY-0001"}
    phase = await ledger.report("phase", "PHASE-01")
    assert [e["seq"] for e in phase.data["events"]] == [1, 2]
    project = await ledger.report("project", "DEMO")
    assert len(project.data["events"]) == 3


def test_default_ledger_manager_satisfies_protocol(ledger: DefaultLedgerManager) -> None:
    manager: LedgerManager = ledger
    assert manager is ledger
