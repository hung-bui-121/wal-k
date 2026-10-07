"""Generic aggregate repository: JSON column plus indexed projection columns (ADR-0002 D-2)."""

import re
from collections.abc import Sequence
from datetime import datetime
from enum import Enum
from typing import ClassVar

from walk.common.errors import ConfigError
from walk.common.models import WalkModel
from walk.persistence.database import Database
from walk.persistence.uow import UnitOfWork

_IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


class Repository[T: WalkModel]:
    """Base for every SQLite repository of a pydantic aggregate.

    Subclasses set `_table`, `_model` and, when the key column is not ``id``, `_key`; the key
    column holds ``getattr(obj, _key)``. Override `projection` to copy queried fields into
    typed columns. Writes run on the caller's `UnitOfWork`; reads use the database connection.
    Table and column names are code-defined and validated as SQL identifiers; ``where`` and
    ``order_by`` passed to `list_where` are SQL fragments written by kernel code, never by
    users (values go through ``params``).
    """

    _table: ClassVar[str]
    _model: type[T]
    _key: ClassVar[str] = "id"

    def __init__(self, db: Database) -> None:
        """Bind the repository to ``db``.

        Raises:
            ConfigError: If `_table` or `_key` is not a plain SQL identifier.
        """
        _check_identifier(self._table, "table")
        _check_identifier(self._key, "key")
        self._db = db

    @property
    def db(self) -> Database:
        """The database the repository reads; writers open their unit of work on it."""
        return self._db

    def projection(self, obj: T) -> dict[str, object]:
        """Return the indexed columns to store next to the JSON; the default stores none."""
        del obj
        return {}

    async def insert(self, obj: T, uow: UnitOfWork) -> T:
        """Insert ``obj``; a duplicate key raises ``sqlite3.IntegrityError``."""
        columns, values = self._row(obj)
        sql = f"INSERT INTO {self._table} ({_names(columns)}) VALUES ({_marks(columns)})"  # noqa: S608 - identifiers validated
        uow.conn.execute(sql, values)
        return obj

    async def upsert(self, obj: T, uow: UnitOfWork) -> T:
        """Insert ``obj`` or replace the JSON and projection columns of the existing row."""
        columns, values = self._row(obj)
        updates = ", ".join(f'"{c}" = excluded."{c}"' for c in columns if c != self._key)
        sql = (
            f"INSERT INTO {self._table} ({_names(columns)}) VALUES ({_marks(columns)}) "  # noqa: S608 - identifiers validated
            f'ON CONFLICT("{self._key}") DO UPDATE SET {updates}'
        )
        uow.conn.execute(sql, values)
        return obj

    async def get(self, key: str) -> T | None:
        """Return the aggregate stored under ``key``, or ``None``."""
        sql = f'SELECT json FROM {self._table} WHERE "{self._key}" = ?'  # noqa: S608 - identifiers validated
        row = self._db.connect().execute(sql, (key,)).fetchone()
        return None if row is None else self._load(row[0])

    async def list_where(
        self,
        where: str = "1=1",
        params: Sequence[object] = (),
        *,
        order_by: str | None = None,
        limit: int | None = None,
    ) -> list[T]:
        """Return the aggregates matching ``where`` (bound with ``params``).

        Args:
            where: SQL condition over the table's columns, with ``?`` placeholders.
            params: Values for the placeholders.
            order_by: SQL ``ORDER BY`` expression; table order when ``None``.
            limit: Maximum number of rows; unlimited when ``None``.
        """
        sql = f"SELECT json FROM {self._table} WHERE {where}"  # noqa: S608 - kernel-written fragment
        bound = list(params)
        if order_by is not None:
            sql += f" ORDER BY {order_by}"
        if limit is not None:
            sql += " LIMIT ?"
            bound.append(limit)
        rows = self._db.connect().execute(sql, bound).fetchall()
        return [self._load(row[0]) for row in rows]

    def _load(self, raw: str) -> T:
        """Deserialise one ``json`` column value; overridden for union aggregates."""
        return self._model.model_validate_json(raw)

    def _row(self, obj: T) -> tuple[list[str], list[object]]:
        row: dict[str, object] = {self._key: getattr(obj, self._key)}
        row.update(self.projection(obj))
        row["json"] = obj.model_dump_json()
        for column in row:
            _check_identifier(column, "column")
        return list(row), [_to_sql(value) for value in row.values()]


def _check_identifier(name: str, what: str) -> None:
    if not _IDENTIFIER_RE.match(name):
        msg = f"invalid SQL {what} name: {name!r}"
        raise ConfigError(msg, detail={what: name})


def _names(columns: Sequence[str]) -> str:
    """Quoted column list; quoting lets SQL keywords such as ``limit`` be column names."""
    return ", ".join(f'"{column}"' for column in columns)


def _marks(columns: Sequence[str]) -> str:
    return ", ".join("?" for _ in columns)


def _to_sql(value: object) -> object:
    """Convert projection values to SQLite-native types (DOMAIN-MODEL §6.1)."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value
