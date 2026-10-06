"""SQLite persistence: database handle, migrations, unit of work, repositories, IDs (ADR-0002)."""

from walk.persistence.database import Database, DbKind
from walk.persistence.errors import MigrationError
from walk.persistence.idempotency import IdempotencyRecord, IdempotencyStore
from walk.persistence.ids import SEQUENCE_WIDTHS, IdSequenceStore
from walk.persistence.migrations import Migration, MigrationRunner
from walk.persistence.repository import Repository
from walk.persistence.uow import UnitOfWork

__all__ = [
    "SEQUENCE_WIDTHS",
    "Database",
    "DbKind",
    "IdSequenceStore",
    "IdempotencyRecord",
    "IdempotencyStore",
    "Migration",
    "MigrationError",
    "MigrationRunner",
    "Repository",
    "UnitOfWork",
]
