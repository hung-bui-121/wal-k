import sqlite3
from pathlib import Path

import pytest

from walk.common.errors import ConfigError
from walk.persistence import Database, MigrationRunner


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row[0] for row in rows}


def test_connect_creates_db_with_wal_and_pragmas(tmp_path: Path) -> None:
    path = tmp_path / "repo" / ".ai" / "kernel.db"
    db = Database(path)
    conn = db.connect()
    try:
        assert path.exists()
        assert db.path == path
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1  # NORMAL
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert conn.isolation_level is None
        assert conn.row_factory is sqlite3.Row
    finally:
        db.close()


def test_connect_returns_the_same_connection_until_closed(tmp_path: Path) -> None:
    db = Database(tmp_path / "kernel.db")
    first = db.connect()
    assert db.connect() is first
    db.close()
    db.close()  # idempotent
    second = db.connect()
    try:
        assert second is not first
    finally:
        db.close()


def test_read_only_never_creates_file(tmp_path: Path) -> None:
    path = tmp_path / ".ai" / "kernel.db"
    with pytest.raises(ConfigError) as exc:
        Database(path, read_only=True).connect()
    assert not path.exists()
    assert not path.parent.exists()
    assert exc.value.detail["path"] == str(path)


def test_read_only_connection_rejects_writes(tmp_path: Path) -> None:
    path = tmp_path / "kernel.db"
    writer = Database(path)
    writer.connect().execute("CREATE TABLE t (x INTEGER)")
    writer.close()
    reader = Database(path, read_only=True)
    conn = reader.connect()
    try:
        assert conn.execute("SELECT count(*) FROM t").fetchone()[0] == 0
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO t VALUES (1)")
    finally:
        reader.close()


def test_backup_copies_database(tmp_path: Path) -> None:
    db = Database(tmp_path / "src" / "kernel.db")
    MigrationRunner(db, "project").apply_pending()
    target = tmp_path / "backups" / "copy.db"
    db.backup_to(target)
    expected = _tables(db.connect())
    db.close()
    copy = sqlite3.connect(target)
    try:
        assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert _tables(copy) == expected
    finally:
        copy.close()


def test_connect_rejects_unopenable_path(tmp_path: Path) -> None:
    (tmp_path / "kernel.db").mkdir()
    with pytest.raises(ConfigError):
        Database(tmp_path / "kernel.db").connect()


def test_connect_rejects_parent_that_is_a_file(tmp_path: Path) -> None:
    (tmp_path / ".ai").write_text("not a directory", encoding="utf-8")
    with pytest.raises(ConfigError):
        Database(tmp_path / ".ai" / "kernel.db").connect()


def test_read_only_connect_fails_when_wal_cannot_be_enabled(tmp_path: Path) -> None:
    path = tmp_path / "rollback-journal.db"
    plain = sqlite3.connect(path)
    plain.execute("CREATE TABLE t (x INTEGER)")
    plain.commit()
    plain.close()
    with pytest.raises(ConfigError) as exc:
        Database(path, read_only=True).connect()
    assert "error" in exc.value.detail


def test_backup_rejects_unopenable_target(tmp_path: Path) -> None:
    db = Database(tmp_path / "kernel.db")
    target = tmp_path / "is-a-dir"
    target.mkdir()
    try:
        with pytest.raises(ConfigError):
            db.backup_to(target)
    finally:
        db.close()


def test_backup_fails_when_target_is_not_a_database(tmp_path: Path) -> None:
    db = Database(tmp_path / "kernel.db")
    db.connect().execute("CREATE TABLE t (x INTEGER)")
    target = tmp_path / "garbage.db"
    target.write_bytes(b"not a database" * 100)
    try:
        with pytest.raises(ConfigError) as exc:
            db.backup_to(target)
        assert exc.value.detail["target"] == str(target)
    finally:
        db.close()
