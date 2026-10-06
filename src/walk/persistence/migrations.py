"""Numbered schema migrations (ADR-0002 D-8, DOMAIN-MODEL §6.3).

Migration files live under ``migrations/<kind>/NNNN_<name>.sql`` next to this module, with an
optional paired ``NNNN_<name>.py`` exposing ``migrate(conn)``. Each file is applied in its own
``BEGIN IMMEDIATE`` transaction together with its ``schema_migrations`` row and
``PRAGMA user_version``.
"""

import importlib.util
import logging
import re
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn, cast

from pydantic import Field

from walk.common.errors import ConfigError
from walk.common.models import FrozenModel
from walk.persistence.database import Database, DbKind
from walk.persistence.errors import MigrationError

_MIGRATIONS_ROOT = Path(__file__).with_name("migrations")
_FILE_RE = re.compile(r"^(?P<version>\d{4})_(?P<name>[a-z0-9_]+)\.(?P<ext>sql|py)$")

logger = logging.getLogger(__name__)


class Migration(FrozenModel):
    """One discovered migration step."""

    version: int = Field(description="Sequence number from the file name, starting at 1.")
    name: str = Field(description="Name part of the file name, e.g. 'init'.")
    sql_path: str = Field(description="Path of the NNNN_<name>.sql file.")
    py_path: str | None = Field(
        description="Path of the paired NNNN_<name>.py data step, if any; runs after the SQL."
    )


class MigrationRunner:
    """Discovers and applies the migrations of one database kind."""

    def __init__(self, db: Database, kind: DbKind) -> None:
        """Bind the runner to a database and its migration set (``project`` or ``kernel``)."""
        self._db = db
        self._kind = kind

    def discover(self) -> list[Migration]:
        """List the migration files of this kind, sorted by version.

        Returns:
            Migrations numbered contiguously from 1.

        Raises:
            ConfigError: If the folder is missing, numbering has a gap or duplicate, or a
                Python step has no SQL file of the same version and name.
        """
        folder = _MIGRATIONS_ROOT / self._kind
        if not folder.is_dir():
            self._config_error(f"migration folder not found: {folder}", folder=str(folder))
        sql_files: dict[int, tuple[str, Path]] = {}
        py_files: list[Path] = []
        for path in sorted(folder.iterdir()):
            match = _FILE_RE.match(path.name)
            if match is None:
                continue
            if match.group("ext") == "py":
                py_files.append(path)
                continue
            version = int(match.group("version"))
            if version in sql_files:
                self._config_error(
                    f"duplicate migration version {version:04d}",
                    files=[sql_files[version][1].name, path.name],
                )
            sql_files[version] = (match.group("name"), path)
        if sorted(sql_files) != list(range(1, len(sql_files) + 1)):
            self._config_error(
                "migration numbering must be contiguous from 0001", versions=sorted(sql_files)
            )
        sql_paths = {path for _, path in sql_files.values()}
        for py in py_files:
            if py.with_suffix(".sql") not in sql_paths:
                self._config_error(f"python step without sql file: {py.name}", file=py.name)
        return [
            Migration(
                version=version,
                name=name,
                sql_path=str(path),
                py_path=str(py) if (py := path.with_suffix(".py")).is_file() else None,
            )
            for version, (name, path) in sorted(sql_files.items())
        ]

    def applied(self) -> list[int]:
        """Return the versions recorded in ``schema_migrations`` (empty before the first)."""
        conn = self._db.connect()
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
        ).fetchone()
        if exists is None:
            return []
        rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        return [int(row[0]) for row in rows]

    def apply_pending(self) -> list[int]:
        """Apply every migration not yet recorded, one transaction per file.

        A database backup (``<db>.pre-NNNN.bak``) is written before the first pending
        migration when any pending migration has a Python step.

        Returns:
            The versions applied by this call; ``[]`` when the schema is up to date.

        Raises:
            ConfigError: Chained from `MigrationError` when a migration fails; that migration
                is rolled back completely and later ones are not attempted.
        """
        done = set(self.applied())
        pending = [m for m in self.discover() if m.version not in done]
        if any(m.py_path is not None for m in pending):
            first = pending[0].version
            self._db.backup_to(self._db.path.with_name(f"{self._db.path.name}.pre-{first:04d}.bak"))
        applied: list[int] = []
        for migration in pending:
            label = f"{migration.version:04d}_{migration.name}"
            try:
                self._apply(migration)
            except MigrationError as exc:
                msg = f"migration {label} failed: {exc.message}"
                detail = {"kind": self._kind, "migration": label, "version": migration.version}
                raise ConfigError(msg, detail=detail) from exc
            logger.info("migration applied", extra={"kind": self._kind, "migration": label})
            applied.append(migration.version)
        return applied

    def _apply(self, migration: Migration) -> None:
        conn = self._db.connect()
        try:
            sql = Path(migration.sql_path).read_text(encoding="utf-8")
            # executescript() commits any open transaction first, so BEGIN goes into the script.
            conn.executescript(f"BEGIN IMMEDIATE;\n{sql}\n")
            if migration.py_path is not None:
                _load_step(migration.py_path)(conn)
            conn.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                (migration.version, migration.name, datetime.now(tz=UTC).isoformat()),
            )
            # PRAGMA values cannot be bound; version is an int parsed from the file name.
            conn.execute(f"PRAGMA user_version = {migration.version:d}")
            conn.execute("COMMIT")
        except Exception as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise MigrationError(str(exc), detail={"migration": migration.name}) from exc

    def _config_error(self, message: str, **detail: object) -> NoReturn:
        raise ConfigError(message, detail={"kind": self._kind, **detail})


def _load_step(py_path: str) -> Callable[[sqlite3.Connection], None]:
    spec = importlib.util.spec_from_file_location(f"walk_migration_{Path(py_path).stem}", py_path)
    if spec is None or spec.loader is None:
        msg = f"cannot load python step {py_path}"
        raise MigrationError(msg)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    step = getattr(module, "migrate", None)
    if not callable(step):
        msg = f"python step {py_path} does not define migrate(conn)"
        raise MigrationError(msg)
    return cast("Callable[[sqlite3.Connection], None]", step)
