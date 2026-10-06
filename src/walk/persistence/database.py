"""SQLite database handle (ADR-0002 D-1, DOMAIN-MODEL §6.1)."""

import logging
import sqlite3
from pathlib import Path
from typing import Literal

from walk.common.errors import ConfigError

DbKind = Literal["project", "kernel"]

_BUSY_TIMEOUT_MS = 5000
_PRAGMAS: tuple[str, ...] = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA foreign_keys=ON",
    "PRAGMA synchronous=NORMAL",
    f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}",
)

logger = logging.getLogger(__name__)


class Database:
    """One SQLite database file and its process-wide connection.

    The connection uses ``isolation_level=None``: nothing is wrapped in an implicit
    transaction, callers issue ``BEGIN IMMEDIATE`` explicitly (``UnitOfWork``).
    """

    def __init__(self, path: Path, *, read_only: bool = False) -> None:
        """Bind the handle to ``path`` without opening it.

        Args:
            path: Database file, e.g. ``<repo>/.ai/kernel.db``.
            read_only: Open with ``mode=ro``; the file must already exist.
        """
        self._path = path
        self._read_only = read_only
        self._conn: sqlite3.Connection | None = None

    @property
    def path(self) -> Path:
        """Location of the database file."""
        return self._path

    def connect(self) -> sqlite3.Connection:
        """Open the connection, or return the one already open.

        A writable database creates the file and its parent directory when missing. Every new
        connection gets ``journal_mode=WAL``, ``foreign_keys=ON``, ``synchronous=NORMAL``,
        ``busy_timeout=5000``, ``row_factory=sqlite3.Row`` and ``isolation_level=None``.

        Returns:
            The open connection.

        Raises:
            ConfigError: If a read-only database does not exist, the file or its directory
                cannot be created or opened, or the pragmas cannot be applied.
        """
        if self._conn is not None:
            return self._conn
        try:
            conn = self._open()
        except (sqlite3.Error, OSError) as exc:
            msg = f"cannot open database {self._path}"
            raise ConfigError(msg, detail=self._detail(error=str(exc))) from exc
        conn.row_factory = sqlite3.Row
        try:
            for pragma in _PRAGMAS:
                conn.execute(pragma)
        except sqlite3.Error as exc:
            conn.close()
            msg = f"cannot configure database {self._path}"
            raise ConfigError(msg, detail=self._detail(error=str(exc))) from exc
        self._conn = conn
        return conn

    def close(self) -> None:
        """Close the connection if open. Safe to call repeatedly."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def backup_to(self, target: Path) -> None:
        """Copy the whole database to ``target`` with the SQLite online backup API.

        Args:
            target: Destination file; its parent directory is created, an existing file is
                overwritten.

        Raises:
            ConfigError: If the source or the target cannot be opened or the copy fails.
        """
        source = self.connect()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            dest = sqlite3.connect(target)
        except (sqlite3.Error, OSError) as exc:
            msg = f"cannot open backup target {target}"
            detail = self._detail(target=str(target), error=str(exc))
            raise ConfigError(msg, detail=detail) from exc
        try:
            source.backup(dest)
        except sqlite3.Error as exc:
            msg = f"backup of {self._path} to {target} failed"
            detail = self._detail(target=str(target), error=str(exc))
            raise ConfigError(msg, detail=detail) from exc
        finally:
            # Windows cannot move or delete the target while a handle is open.
            dest.close()
        logger.info("database backup written", extra={"db": str(self._path), "target": str(target)})

    def _open(self) -> sqlite3.Connection:
        if self._read_only:
            if not self._path.is_file():
                msg = f"database does not exist: {self._path}"
                raise ConfigError(msg, detail=self._detail())
            uri = f"{self._path.resolve().as_uri()}?mode=ro"
            return sqlite3.connect(uri, uri=True, isolation_level=None)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self._path, isolation_level=None)

    def _detail(self, **extra: str) -> dict[str, object]:
        return {"path": str(self._path), "read_only": self._read_only, **extra}
