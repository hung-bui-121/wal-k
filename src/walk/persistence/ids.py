"""Sequence ID allocation (DOMAIN-MODEL §2); the production `IdFactory`."""

from typing import Final

from walk.common.errors import ConfigError
from walk.common.ids import format_seq_id, new_ulid
from walk.persistence.database import Database
from walk.persistence.uow import UnitOfWork

SEQUENCE_WIDTHS: Final[dict[str, int]] = {
    "PHASE": 2,
    "EPIC": 3,
    "FEAT": 4,
    "STORY": 4,
    "TASK": 4,
    "BUG": 4,
    "DEC": 4,
    "DEB": 4,
    "EVD": 6,
    "APR": 4,
    "HO": 4,
    "APV": 4,
    "RC": 2,
    "OBS": 4,
    "OBS-K": 4,
    "IMP": 2,
    "PATTERN": 3,
    "ANTI": 3,
    "EXP": 4,
}
"""Minimum zero-padded digit count per ID prefix (DOMAIN-MODEL §2)."""

# ``id_sequences.next`` holds the next number to hand out; the upsert returns the one taken.
_ALLOCATE_SQL = (
    "INSERT INTO id_sequences (prefix, next) VALUES (?, 2) "
    "ON CONFLICT(prefix) DO UPDATE SET next = next + 1 RETURNING next - 1"
)


class IdSequenceStore:
    """Allocates ``<PREFIX>-<n>`` IDs from ``id_sequences`` inside a unit of work.

    Allocation shares the caller's transaction, so a rolled-back unit of work gives its
    numbers back; a committed ID is never handed out twice.
    """

    def __init__(self, db: Database) -> None:
        """Create an unbound store; use `bind` to allocate."""
        self._db = db
        self._uow: UnitOfWork | None = None

    def bind(self, uow: UnitOfWork) -> "IdSequenceStore":
        """Return a view of this store that allocates on ``uow``'s transaction."""
        return _BoundIdSequenceStore(self._db, uow)

    def next_sequence(self, prefix: str) -> str:
        """Allocate the next ID for ``prefix``, e.g. ``FEAT-0012``.

        Raises:
            ConfigError: If the store is unbound, the bound unit of work is no longer active,
                or ``prefix`` is not in `SEQUENCE_WIDTHS`.
        """
        if self._uow is None:
            msg = "IdSequenceStore is not bound to a unit of work"
            raise ConfigError(msg, detail={"prefix": prefix})
        width = SEQUENCE_WIDTHS.get(prefix)
        if width is None:
            msg = f"unknown id prefix: {prefix}"
            raise ConfigError(msg, detail={"prefix": prefix})
        row = self._uow.conn.execute(_ALLOCATE_SQL, (prefix,)).fetchone()
        return format_seq_id(prefix, int(row[0]), width)

    def new_ulid(self) -> str:
        """Return a new time-ordered ULID."""
        return new_ulid()


class _BoundIdSequenceStore(IdSequenceStore):
    """`IdSequenceStore` view bound to one unit of work (returned by `bind`)."""

    def __init__(self, db: Database, uow: UnitOfWork) -> None:
        super().__init__(db)
        self._uow = uow
