"""`kernel_instances`: which kernel processes ran against the database (E01-S30)."""

from walk.common.clock import Clock
from walk.persistence.database import Database
from walk.persistence.uow import UnitOfWork


class KernelInstanceRegistry:
    """Registers a kernel process and records its heartbeats."""

    def __init__(self, db: Database, clock: Clock) -> None:
        """Bind to ``db``; ``clock`` stamps start and heartbeat times."""
        self._db = db
        self._clock = clock

    async def register(self, kernel_instance: str, *, hostname: str, pid: int) -> None:
        """Insert (or refresh) the row of ``kernel_instance``."""
        now = self._clock.now().isoformat()
        async with UnitOfWork(self._db) as uow:
            uow.conn.execute(
                "INSERT INTO kernel_instances (id, hostname, started_at, heartbeat_at, pid) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                "hostname = excluded.hostname, started_at = excluded.started_at, "
                "heartbeat_at = excluded.heartbeat_at, pid = excluded.pid",
                (kernel_instance, hostname, now, now, pid),
            )

    async def heartbeat(self, kernel_instance: str) -> None:
        """Stamp ``heartbeat_at`` of ``kernel_instance``."""
        async with UnitOfWork(self._db) as uow:
            uow.conn.execute(
                "UPDATE kernel_instances SET heartbeat_at = ? WHERE id = ?",
                (self._clock.now().isoformat(), kernel_instance),
            )
