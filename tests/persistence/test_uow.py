import sqlite3

import pytest

from walk.common.errors import ConfigError, TransientError
from walk.persistence import Database, UnitOfWork


def _count(db: Database) -> int:
    return int(db.connect().execute("SELECT count(*) FROM id_sequences").fetchone()[0])


def _insert(uow: UnitOfWork, prefix: str) -> None:
    uow.conn.execute("INSERT INTO id_sequences (prefix, next) VALUES (?, 1)", (prefix,))


async def test_uow_rolls_back_on_exception(db: Database) -> None:
    async def body() -> None:
        async with UnitOfWork(db) as uow:
            _insert(uow, "FEAT")
            msg = "boom"
            raise RuntimeError(msg)

    with pytest.raises(RuntimeError, match="boom"):
        await body()
    assert _count(db) == 0
    assert not db.connect().in_transaction


async def test_uow_commits_and_runs_after_commit_hooks(db: Database) -> None:
    calls: list[str] = []

    async def first() -> None:
        calls.append(f"first:{_count(db)}")

    async def second() -> None:
        calls.append("second")

    async with UnitOfWork(db) as uow:
        _insert(uow, "FEAT")
        uow.after_commit(first)
        uow.after_commit(second)
        assert calls == []
    assert _count(db) == 1
    assert calls == ["first:1", "second"]


async def test_after_commit_hooks_skipped_on_rollback(db: Database) -> None:
    calls: list[str] = []

    async def hook() -> None:
        calls.append("ran")

    async def body() -> None:
        async with UnitOfWork(db) as uow:
            uow.after_commit(hook)
            msg = "fail"
            raise ValueError(msg)

    with pytest.raises(ValueError, match="fail"):
        await body()
    assert calls == []
    async with UnitOfWork(db):
        pass
    assert calls == []


async def test_nested_uow_rejected(db: Database) -> None:
    async with UnitOfWork(db) as outer:
        _insert(outer, "FEAT")
        with pytest.raises(ConfigError, match="nested transaction"):
            async with UnitOfWork(db):
                pass
        assert db.connect().in_transaction
    assert _count(db) == 1


async def test_after_commit_hook_can_open_new_uow(db: Database) -> None:
    async def follow_up() -> None:
        async with UnitOfWork(db) as inner:
            _insert(inner, "BUG")

    async with UnitOfWork(db) as uow:
        _insert(uow, "FEAT")
        uow.after_commit(follow_up)
    assert _count(db) == 2


async def test_conn_and_after_commit_require_active_uow(db: Database) -> None:
    uow = UnitOfWork(db)

    async def hook() -> None:
        return None

    with pytest.raises(ConfigError):
        _ = uow.conn
    with pytest.raises(ConfigError):
        uow.after_commit(hook)
    async with uow:
        pass
    with pytest.raises(ConfigError):
        _ = uow.conn


async def test_uow_raises_transient_error_when_database_is_locked(db: Database) -> None:
    other = Database(db.path)
    other.connect().execute("PRAGMA busy_timeout = 0")
    try:
        async with UnitOfWork(db):
            with pytest.raises(TransientError):
                async with UnitOfWork(other):
                    pass
        assert not other.connect().in_transaction
    finally:
        other.close()


async def test_failed_commit_rolls_back_and_raises(db: Database) -> None:
    calls: list[str] = []

    async def hook() -> None:
        calls.append("ran")

    async def body() -> None:
        async with UnitOfWork(db) as uow:
            uow.after_commit(hook)
            uow.conn.execute("PRAGMA defer_foreign_keys = ON")
            uow.conn.execute(
                "INSERT INTO phases (id, project_key, ordinal, state, json, updated_at) "
                "VALUES ('PHASE-01', 'MISSING', 1, 'PLANNED', '{}', '2026')"
            )

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        await body()
    conn = db.connect()
    assert not conn.in_transaction
    assert conn.execute("SELECT count(*) FROM phases").fetchone()[0] == 0
    assert calls == []
