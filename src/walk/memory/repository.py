"""SQLite repository of the `.ai/` document index (``memory_index``)."""

import json
import sqlite3
from datetime import UTC, datetime
from typing import Final

from pydantic import Field

from walk.common.errors import ConfigError
from walk.common.ids import ApprovedArtifactId
from walk.common.models import FrozenModel, JsonDict
from walk.memory.models import (
    ApprovalStatus,
    ApprovedArtifact,
    FreshnessStatus,
    MemoryDocType,
    MemoryDocument,
)
from walk.persistence import Database, UnitOfWork

_COLUMNS: Final = (
    "path",
    "doc_id",
    "type",
    "title",
    "status",
    "version",
    "updated_at",
    "freshness_commit",
    "freshness_status",
    "freshness_checked_at",
    "raw_sha256",
    "relevant_files_json",
    "related_json",
)
_ARTIFACT_UPSERT: Final = (
    "INSERT INTO approved_artifacts (id, kind, status, scope, version, content_sha256, ai_path, "
    "approved_at, json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
    "kind = excluded.kind, status = excluded.status, scope = excluded.scope, "
    "version = excluded.version, content_sha256 = excluded.content_sha256, "
    "ai_path = excluded.ai_path, approved_at = excluded.approved_at, json = excluded.json"
)
_SELECT: Final = f"SELECT {', '.join(_COLUMNS)} FROM memory_index"  # noqa: S608 - constant columns
_UPSERT: Final = (
    f"INSERT INTO memory_index ({', '.join(_COLUMNS)}) "  # noqa: S608 - constant columns
    f"VALUES ({', '.join('?' for _ in _COLUMNS)}) "
    "ON CONFLICT(path) DO UPDATE SET "
    + ", ".join(f"{column} = excluded.{column}" for column in _COLUMNS[1:])
)


def _utc_text(value: datetime) -> str:
    """Fixed-width UTC text so that timestamp columns order correctly as strings."""
    return value.astimezone(UTC).isoformat(timespec="microseconds")


class MemoryIndexRow(FrozenModel):
    """One ``memory_index`` row: where a document lives and its header facts."""

    path: str = Field(description="Path relative to `.ai/`, POSIX separators.")
    doc_id: str = Field(description="Front-matter id.")
    type: MemoryDocType = Field(description="Front-matter type.")
    title: str = Field(description="Front-matter title.")
    status: str | None = Field(description="Front-matter status.")
    version: int = Field(description="Front-matter version.")
    updated_at: datetime = Field(description="Front-matter updated_at.")
    freshness_commit: str | None = Field(description="Stamp commit, if stamped.")
    freshness_status: FreshnessStatus | None = Field(
        description="Cached §42 classification; None until assessed (E04-S03)."
    )
    freshness_checked_at: datetime | None = Field(description="When it was last assessed.")
    raw_sha256: str = Field(description="sha256 of the file text.")
    relevant_files: list[str] = Field(description="Front-matter relevant_files.")
    related: JsonDict = Field(description="Front-matter related links as JSON.")

    @classmethod
    def of(cls, doc: MemoryDocument) -> "MemoryIndexRow":
        """The index row of a parsed or written document (freshness not yet assessed)."""
        fm = doc.front_matter
        return cls(
            path=doc.path,
            doc_id=fm.id,
            type=fm.type,
            title=fm.title,
            status=fm.status,
            version=fm.version,
            updated_at=fm.updated_at,
            freshness_commit=fm.freshness.commit if fm.freshness else None,
            freshness_status=None,
            freshness_checked_at=None,
            raw_sha256=doc.raw_sha256,
            relevant_files=list(fm.relevant_files),
            related=fm.related.model_dump(mode="json"),
        )


def _from_sql(row: sqlite3.Row | tuple[object, ...]) -> MemoryIndexRow:
    values = dict(zip(_COLUMNS, tuple(row), strict=True))
    values["relevant_files"] = json.loads(str(values.pop("relevant_files_json")))
    values["related"] = json.loads(str(values.pop("related_json")))
    return MemoryIndexRow.model_validate(values)


class MemoryIndexRepository:
    """Reads and writes ``memory_index``; writes run on the caller's `UnitOfWork`."""

    def __init__(self, db: Database) -> None:
        """Bind the repository to ``db``."""
        self._db = db

    @property
    def db(self) -> Database:
        """The database holding ``memory_index``; writers open units of work on it."""
        return self._db

    async def upsert(self, row: MemoryIndexRow, uow: UnitOfWork) -> None:
        """Insert or replace the row of ``row.path``."""
        uow.conn.execute(
            _UPSERT,
            (
                row.path,
                row.doc_id,
                row.type.value,
                row.title,
                row.status,
                row.version,
                _utc_text(row.updated_at),
                row.freshness_commit,
                None if row.freshness_status is None else row.freshness_status.value,
                None if row.freshness_checked_at is None else _utc_text(row.freshness_checked_at),
                row.raw_sha256,
                json.dumps(row.relevant_files),
                json.dumps(row.related, sort_keys=True),
            ),
        )

    async def delete(self, path: str, uow: UnitOfWork) -> None:
        """Remove the row of ``path`` (no error when absent)."""
        uow.conn.execute("DELETE FROM memory_index WHERE path = ?", (path,))

    async def by_doc_id(self, doc_id: str) -> MemoryIndexRow | None:
        """The row of document ``doc_id``, or None."""
        row = self._db.connect().execute(f"{_SELECT} WHERE doc_id = ?", (doc_id,)).fetchone()
        return None if row is None else _from_sql(row)

    async def all(self) -> list[MemoryIndexRow]:
        """Every row, ordered by path."""
        rows = self._db.connect().execute(f"{_SELECT} ORDER BY path").fetchall()
        return [_from_sql(row) for row in rows]


class ApprovedArtifactRepository:
    """``approved_artifacts``: the `ApprovedArtifact` JSON plus its indexed columns (E02-S12)."""

    def __init__(self, db: Database) -> None:
        """Bind the repository to ``db``."""
        self._db = db

    async def upsert(self, uow: UnitOfWork, artifact: ApprovedArtifact) -> None:
        """Insert or replace the row of ``artifact.id`` on ``uow``."""
        uow.conn.execute(
            _ARTIFACT_UPSERT,
            (
                artifact.id,
                artifact.kind.value,
                artifact.status.value,
                artifact.scope,
                artifact.version,
                artifact.content_sha256,
                f"approved/{artifact.id}.md",
                _utc_text(artifact.approved_at),
                artifact.model_dump_json(),
            ),
        )

    async def get(self, artifact_id: ApprovedArtifactId) -> ApprovedArtifact:
        """The artifact stored under ``artifact_id``.

        Raises:
            ConfigError: No artifact has ``artifact_id``.
        """
        row = (
            self._db.connect()
            .execute("SELECT json FROM approved_artifacts WHERE id = ?", (artifact_id,))
            .fetchone()
        )
        if row is None:
            msg = f"unknown approved artifact {artifact_id}"
            raise ConfigError(msg, detail={"artifact_id": artifact_id})
        return ApprovedArtifact.model_validate_json(row[0])

    async def list(
        self, *, status: ApprovalStatus | None = None, scope: str | None = None
    ) -> list[ApprovedArtifact]:
        """Artifacts matching every given filter, by id."""
        where, params = ["1 = 1"], []
        if status is not None:
            where.append("status = ?")
            params.append(status.value)
        if scope is not None:
            where.append("scope = ?")
            params.append(scope)
        sql = f"SELECT json FROM approved_artifacts WHERE {' AND '.join(where)} ORDER BY id"  # noqa: S608 - fixed fragments, values bound
        rows = self._db.connect().execute(sql, params).fetchall()
        return [ApprovedArtifact.model_validate_json(row[0]) for row in rows]
