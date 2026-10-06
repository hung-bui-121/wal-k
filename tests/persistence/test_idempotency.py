import pytest

from tests.fakes.fake_clock import FakeClock
from walk.common.errors import ConfigError
from walk.persistence import Database, IdempotencyRecord, IdempotencyStore, UnitOfWork


async def test_run_replays_stored_result(db: Database, fake_clock: FakeClock) -> None:
    store = IdempotencyStore(db, fake_clock)
    calls: list[int] = []

    async def op() -> str:
        calls.append(1)
        return f"PR-{len(calls)}"

    async with UnitOfWork(db) as uow:
        first = await store.run("git:pr:FEAT-0001", "open_pr", op, uow)
    async with UnitOfWork(db) as uow:
        second = await store.run("git:pr:FEAT-0001", "open_pr", op, uow)
    assert calls == [1]
    assert first == second == "PR-1"
    assert await store.has("git:pr:FEAT-0001")


async def test_put_rejects_duplicate_key(db: Database, fake_clock: FakeClock) -> None:
    store = IdempotencyStore(db, fake_clock)
    async with UnitOfWork(db) as uow:
        await store.put("k1", "op", None, uow)
        with pytest.raises(ConfigError, match="duplicate idempotency key"):
            await store.put("k1", "op", "x", uow)


async def test_run_does_not_store_key_on_failure(db: Database, fake_clock: FakeClock) -> None:
    store = IdempotencyStore(db, fake_clock)

    async def failing() -> str:
        msg = "provider down"
        raise RuntimeError(msg)

    async with UnitOfWork(db) as uow:
        with pytest.raises(RuntimeError, match="provider down"):
            await store.run("k1", "op", failing, uow)
    assert not await store.has("k1")


async def test_get_returns_record(db: Database, fake_clock: FakeClock) -> None:
    store = IdempotencyStore(db, fake_clock)
    assert await store.get("k1") is None
    async with UnitOfWork(db) as uow:
        await store.put("k1", "create_issue", "JIRA-7", uow)
    assert await store.get("k1") == IdempotencyRecord(
        key="k1", operation="create_issue", result_ref="JIRA-7", created_at=fake_clock.now()
    )


async def test_run_rejects_replay_without_result(db: Database, fake_clock: FakeClock) -> None:
    store = IdempotencyStore(db, fake_clock)

    async def op() -> str:
        return "never"

    async with UnitOfWork(db) as uow:
        await store.put("k1", "op", None, uow)
        with pytest.raises(ConfigError):
            await store.run("k1", "op", op, uow)
