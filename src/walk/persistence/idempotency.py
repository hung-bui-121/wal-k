"""Idempotency keys for critical and external operations (ADR-0002 D-7, §90)."""

import sqlite3
from collections.abc import Awaitable, Callable
from datetime import datetime

from pydantic import Field

from walk.common.clock import Clock
from walk.common.errors import ConfigError
from walk.common.models import FrozenModel
from walk.persistence.database import Database
from walk.persistence.uow import UnitOfWork


class IdempotencyRecord(FrozenModel):
    """A completed operation recorded under its idempotency key."""

    key: str = Field(description="Idempotency key (formats in ARCHITECTURE §5.4).")
    operation: str = Field(description="Name of the operation that used the key.")
    result_ref: str | None = Field(description="Reference to the operation's result, if any.")
    created_at: datetime = Field(description="When the key was recorded (UTC).")


class IdempotencyStore:
    """Records operation keys in the caller's transaction and replays stored results."""

    def __init__(self, db: Database, clock: Clock) -> None:
        """Bind the store to ``db``; ``clock`` stamps ``created_at``."""
        self._db = db
        self._clock = clock

    @property
    def db(self) -> Database:
        """The database holding ``idempotency_keys``; callers open units of work on it."""
        return self._db

    async def has(self, key: str) -> bool:
        """Return whether ``key`` is recorded."""
        row = (
            self._db.connect()
            .execute("SELECT 1 FROM idempotency_keys WHERE key = ?", (key,))
            .fetchone()
        )
        return row is not None

    async def get(self, key: str) -> IdempotencyRecord | None:
        """Return the record stored under ``key``, or ``None``."""
        row = (
            self._db.connect()
            .execute(
                "SELECT key, operation, result_ref, created_at FROM idempotency_keys WHERE key = ?",
                (key,),
            )
            .fetchone()
        )
        if row is None:
            return None
        return IdempotencyRecord(
            key=row["key"],
            operation=row["operation"],
            result_ref=row["result_ref"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    async def put(self, key: str, operation: str, result_ref: str | None, uow: UnitOfWork) -> None:
        """Record ``key`` in ``uow``'s transaction.

        Raises:
            ConfigError: ``duplicate idempotency key`` if ``key`` is already recorded.
        """
        try:
            uow.conn.execute(
                "INSERT INTO idempotency_keys (key, operation, result_ref, created_at) "
                "VALUES (?, ?, ?, ?)",
                (key, operation, result_ref, self._clock.now().isoformat()),
            )
        except sqlite3.IntegrityError as exc:
            msg = "duplicate idempotency key"
            raise ConfigError(msg, detail={"key": key, "operation": operation}) from exc

    async def run(
        self, key: str, operation: str, fn: Callable[[], Awaitable[str]], uow: UnitOfWork
    ) -> str:
        """Run ``fn`` once per ``key``; later calls replay the stored ``result_ref``.

        The key is stored in ``uow``'s transaction only after ``fn`` succeeds, so a failing
        ``fn`` leaves no key and the operation is retried next time.

        Raises:
            ConfigError: If ``key`` is recorded without a ``result_ref`` to replay.
        """
        existing = await self.get(key)
        if existing is not None:
            if existing.result_ref is None:
                msg = "idempotency key has no result to replay"
                raise ConfigError(msg, detail={"key": key, "operation": existing.operation})
            return existing.result_ref
        result = await fn()
        await self.put(key, operation, result, uow)
        return result
