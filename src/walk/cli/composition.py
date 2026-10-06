"""Composition root: the only place that wires concrete implementations together.

`build_kernel` (E01-S30) will live here; until then this module opens the project database.
"""

from pathlib import Path

from walk.persistence import Database

_AI_DIR = ".ai"
_DB_FILE = "kernel.db"


def open_database(repo: Path, *, read_only: bool = False) -> Database:
    """Open the project database ``<repo>/.ai/kernel.db``.

    Args:
        repo: Game repository root.
        read_only: Open without write access; the database must already exist.

    Returns:
        A connected `Database`. A writable database (and ``.ai/``) is created when missing.

    Raises:
        ConfigError: If a read-only database does not exist or cannot be opened.
    """
    db = Database(repo / _AI_DIR / _DB_FILE, read_only=read_only)
    db.connect()
    return db
