import asyncio
import json

import pytest

from tests.fakes.fake_clock import FakeClock
from walk.common.errors import ConfigError, GuardRejected, PermissionDenied
from walk.common.models import JsonDict
from walk.orchestrator import Command, CommandConsumer
from walk.persistence import Database, UnitOfWork


async def _submit(db: Database, name: str, args: JsonDict | None = None) -> int:
    async with UnitOfWork(db) as uow:
        cursor = uow.conn.execute(
            "INSERT INTO commands (name, args_json, requested_at, requested_by) "
            "VALUES (?, ?, '2026-01-01T00:00:00+00:00', 'USER')",
            (name, json.dumps(args or {})),
        )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _rows(db: Database) -> list[tuple[str, str, int, JsonDict]]:
    rows = db.connect().execute(
        "SELECT c.name, c.state, r.ok, r.result_json FROM commands c "
        "JOIN command_results r ON r.command_id = c.id ORDER BY c.id"
    )
    return [
        (row["name"], row["state"], row["ok"], json.loads(row["result_json"]))
        for row in rows.fetchall()
    ]


async def test_poll_once_dispatches_and_records(db: Database, fake_clock: FakeClock) -> None:
    consumer = CommandConsumer(db, fake_clock)
    seen: list[JsonDict] = []

    async def wake(args: JsonDict) -> JsonDict:
        seen.append(args)
        return {"woken": True}

    consumer.register("wake", wake)
    await _submit(db, "wake", {"why": "test"})
    await _submit(db, "nope")

    processed = await consumer.poll_once()

    assert processed == 2
    assert seen == [{"why": "test"}]
    assert _rows(db) == [
        ("wake", "DONE", 1, {"woken": True, "exit_code": 0}),
        ("nope", "FAILED", 0, {"error": "unknown command nope", "exit_code": 1}),
    ]
    assert await consumer.poll_once() == 0
    command = Command(
        id=1,
        name="wake",
        args={},
        requested_at=fake_clock.now(),
        requested_by="USER",
        state="DONE",
    )
    assert command.state == "DONE"


async def test_guard_rejection_maps_to_exit_code_2(db: Database, fake_clock: FakeClock) -> None:
    consumer = CommandConsumer(db, fake_clock)

    async def guarded(args: JsonDict) -> JsonDict:
        del args
        msg = "guard said no"
        raise GuardRejected(msg)

    async def denied(args: JsonDict) -> JsonDict:
        del args
        msg = "not allowed"
        raise PermissionDenied(msg)

    async def misconfigured(args: JsonDict) -> JsonDict:
        del args
        msg = "bad config"
        raise ConfigError(msg)

    async def crashing(args: JsonDict) -> JsonDict:
        del args
        raise RuntimeError

    for name, handler in (
        ("guarded", guarded),
        ("denied", denied),
        ("misconfigured", misconfigured),
        ("crashing", crashing),
    ):
        consumer.register(name, handler)
        await _submit(db, name)

    await consumer.poll_once()

    assert [(state, ok, result) for _, state, ok, result in _rows(db)] == [
        ("FAILED", 0, {"error": "guard said no", "exit_code": 2}),
        ("FAILED", 0, {"error": "not allowed", "exit_code": 2}),
        ("FAILED", 0, {"error": "bad config", "exit_code": 1}),
        ("FAILED", 0, {"error": "RuntimeError", "exit_code": 1}),
    ]


async def test_duplicate_handler_rejected(db: Database, fake_clock: FakeClock) -> None:
    consumer = CommandConsumer(db, fake_clock)

    async def wake(args: JsonDict) -> JsonDict:
        return args

    consumer.register("wake", wake)

    with pytest.raises(ConfigError, match="already registered"):
        consumer.register("wake", wake)


async def test_run_polls_until_stopped(db: Database, fake_clock: FakeClock) -> None:
    stop = asyncio.Event()
    polls: list[float] = []

    async def sleep(seconds: float) -> None:
        polls.append(seconds)
        if len(polls) == 2:
            stop.set()

    consumer = CommandConsumer(db, fake_clock, poll_interval_s=0.5, sleep=sleep)

    async def wake(args: JsonDict) -> JsonDict:
        return args

    consumer.register("wake", wake)
    await _submit(db, "wake")

    await consumer.run(stop)

    assert polls == [0.5, 0.5]
    assert _rows(db)[0][1] == "DONE"
