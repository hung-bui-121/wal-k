"""Unit of work: one SQLite transaction (ADR-0002 D-9)."""

import sqlite3
from collections.abc import Awaitable, Callable
from typing import Self

from walk.common.errors import ConfigError, TransientError
from walk.persistence.database import Database


class UnitOfWork:
    """Async context manager around one ``BEGIN IMMEDIATE`` transaction.

    State changes, their ledger events, idempotency keys and transition rows are written on
    `conn` inside one unit of work and commit atomically. Callbacks registered with
    `after_commit` run only after a successful ``COMMIT`` (hooks fire after commit).
    """

    def __init__(self, db: Database) -> None:
        """Create an inactive unit of work on ``db``; entering it starts the transaction."""
        self._db = db
        self._conn: sqlite3.Connection | None = None
        self._after_commit: list[Callable[[], Awaitable[None]]] = []

    @property
    def conn(self) -> sqlite3.Connection:
        """The connection holding the open transaction.

        Raises:
            ConfigError: If the unit of work is not active.
        """
        if self._conn is None:
            msg = "unit of work is not active"
            raise ConfigError(msg, detail={"db": str(self._db.path)})
        return self._conn

    async def __aenter__(self) -> Self:
        """Begin the transaction.

        Raises:
            ConfigError: ``nested transaction`` if a transaction is already open on the
                connection.
            TransientError: If the write lock is not obtained within the busy timeout.
        """
        conn = self._db.connect()
        if conn.in_transaction:
            msg = "nested transaction"
            raise ConfigError(msg, detail={"db": str(self._db.path)})
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            msg = "cannot begin transaction"
            raise TransientError(msg, detail={"db": str(self._db.path), "error": str(exc)}) from exc
        self._conn = conn
        self._after_commit = []
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Commit on success, roll back on exception; the exception always propagates.

        After a successful commit the `after_commit` callbacks are awaited in registration
        order. The unit of work is already inactive then, so a callback may open a new one; an
        exception from a callback propagates and skips the remaining callbacks.
        """
        conn = self.conn
        callbacks = self._after_commit
        self._conn = None
        self._after_commit = []
        if exc[0] is not None:
            conn.execute("ROLLBACK")
            return
        try:
            conn.execute("COMMIT")
        except sqlite3.Error:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        for callback in callbacks:
            await callback()

    def after_commit(self, fn: Callable[[], Awaitable[None]]) -> None:
        """Register ``fn`` to run after this unit of work commits; dropped on rollback.

        Raises:
            ConfigError: If the unit of work is not active.
        """
        _ = self.conn
        self._after_commit.append(fn)
