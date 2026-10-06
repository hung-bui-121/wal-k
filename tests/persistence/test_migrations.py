import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

import walk.persistence.migrations as migrations_module
from walk.common.errors import ConfigError
from walk.persistence import Database, Migration, MigrationError, MigrationRunner

PROJECT_TABLES = {
    "schema_migrations",
    "id_sequences",
    "kernel_instances",
    "idempotency_keys",
    "projects",
    "phases",
    "work_items",
    "work_item_transitions",
    "release_candidates",
    "agent_runs",
    "checkpoints",
    "handovers",
    "ledger_events",
    "cost_records",
    "budgets",
    "evidence",
    "decisions",
    "decision_work_items",
    "debates",
    "debate_positions",
    "escalations",
    "approval_requests",
    "approved_artifacts",
    "memory_index",
    "hook_executions",
    "commands",
    "command_results",
    "skill_projections",
    "work_provider_sync",
    "webhook_deliveries",
    "improvement_observations",
    "improvement_candidates",
    "patterns",
    "retrospectives",
    "behavior_versions",
}
KERNEL_TABLES = {
    "schema_migrations",
    "id_sequences",
    "improvement_observations",
    "improvement_candidates",
    "patterns",
    "retrospectives",
    "behavior_versions",
    "experiments",
    "kernel_changelog",
}
MINIMAL_INIT = """
CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL,
                                applied_at TEXT NOT NULL);
CREATE TABLE items (id INTEGER PRIMARY KEY, label TEXT NOT NULL);
INSERT INTO items (label) VALUES ('before');
"""
NOW = "2026-01-01T00:00:00+00:00"


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row[0] for row in rows}


@pytest.fixture
def fresh_db(tmp_path: Path) -> Iterator[Database]:
    db = Database(tmp_path / ".ai" / "kernel.db")
    yield db
    db.close()


@pytest.fixture
def custom_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "migrations"
    (root / "project").mkdir(parents=True)
    monkeypatch.setattr(migrations_module, "_MIGRATIONS_ROOT", root)
    return root


def test_apply_pending_creates_all_tables(fresh_db: Database) -> None:
    assert MigrationRunner(fresh_db, "project").apply_pending() == [1]
    assert _tables(fresh_db.connect()) == PROJECT_TABLES


def test_apply_pending_records_version(fresh_db: Database) -> None:
    MigrationRunner(fresh_db, "project").apply_pending()
    conn = fresh_db.connect()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    rows = conn.execute("SELECT version, name, applied_at FROM schema_migrations").fetchall()
    assert [(row["version"], row["name"]) for row in rows] == [(1, "init")]
    assert rows[0]["applied_at"]


def test_apply_pending_is_idempotent(fresh_db: Database) -> None:
    runner = MigrationRunner(fresh_db, "project")
    runner.apply_pending()
    assert runner.apply_pending() == []
    assert runner.applied() == [1]


def test_applied_is_empty_before_first_migration(fresh_db: Database) -> None:
    assert MigrationRunner(fresh_db, "project").applied() == []


def test_discover_lists_packaged_migrations(fresh_db: Database) -> None:
    migrations = MigrationRunner(fresh_db, "project").discover()
    assert [(m.version, m.name, m.py_path) for m in migrations] == [(1, "init", None)]
    assert isinstance(migrations[0], Migration)
    assert Path(migrations[0].sql_path).name == "0001_init.sql"


def test_discover_rejects_gap_in_numbering(fresh_db: Database, custom_root: Path) -> None:
    (custom_root / "project" / "0001_init.sql").write_text(MINIMAL_INIT, encoding="utf-8")
    (custom_root / "project" / "0003_later.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        MigrationRunner(fresh_db, "project").discover()
    assert exc.value.detail["kind"] == "project"


def test_discover_rejects_duplicate_version(fresh_db: Database, custom_root: Path) -> None:
    (custom_root / "project" / "0001_init.sql").write_text(MINIMAL_INIT, encoding="utf-8")
    (custom_root / "project" / "0001_other.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(ConfigError):
        MigrationRunner(fresh_db, "project").discover()


def test_discover_rejects_python_step_without_sql(fresh_db: Database, custom_root: Path) -> None:
    (custom_root / "project" / "0001_init.sql").write_text(MINIMAL_INIT, encoding="utf-8")
    (custom_root / "project" / "0002_orphan.py").write_text("", encoding="utf-8")
    with pytest.raises(ConfigError):
        MigrationRunner(fresh_db, "project").discover()


def test_discover_rejects_missing_folder(fresh_db: Database, custom_root: Path) -> None:
    with pytest.raises(ConfigError):
        MigrationRunner(fresh_db, "kernel").discover()
    assert custom_root.exists()


def test_failed_migration_rolls_back(fresh_db: Database, custom_root: Path) -> None:
    folder = custom_root / "project"
    (folder / "0001_init.sql").write_text(MINIMAL_INIT, encoding="utf-8")
    (folder / "0002_broken.sql").write_text(
        "CREATE TABLE partial (x INTEGER);\n"
        "INSERT INTO items (label) VALUES ('x');\n"
        "CREATE TABLE (;\n",
        encoding="utf-8",
    )
    runner = MigrationRunner(fresh_db, "project")
    with pytest.raises(ConfigError) as exc:
        runner.apply_pending()
    assert exc.value.detail["migration"] == "0002_broken"
    assert isinstance(exc.value.__cause__, MigrationError)
    conn = fresh_db.connect()
    assert not conn.in_transaction
    assert "partial" not in _tables(conn)
    assert conn.execute("SELECT count(*) FROM items").fetchone()[0] == 1
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    assert runner.applied() == [1]


def test_python_step_runs_after_sql_with_backup(fresh_db: Database, custom_root: Path) -> None:
    folder = custom_root / "project"
    (folder / "0001_init.sql").write_text(MINIMAL_INIT, encoding="utf-8")
    runner = MigrationRunner(fresh_db, "project")
    runner.apply_pending()
    (folder / "0002_reshape.sql").write_text(
        "ALTER TABLE items ADD COLUMN upper_label TEXT;", encoding="utf-8"
    )
    (folder / "0002_reshape.py").write_text(
        "import sqlite3\n\n\n"
        "def migrate(conn: sqlite3.Connection) -> None:\n"
        "    conn.execute('UPDATE items SET upper_label = upper(label)')\n",
        encoding="utf-8",
    )
    assert runner.apply_pending() == [2]
    conn = fresh_db.connect()
    assert conn.execute("SELECT upper_label FROM items").fetchone()[0] == "BEFORE"
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
    backups = list(fresh_db.path.parent.glob("*.bak"))
    assert len(backups) == 1
    backup = sqlite3.connect(backups[0])
    try:
        assert backup.execute("SELECT version FROM schema_migrations").fetchall() == [(1,)]
    finally:
        backup.close()


def test_failing_python_step_rolls_back_sql(fresh_db: Database, custom_root: Path) -> None:
    folder = custom_root / "project"
    (folder / "0001_init.sql").write_text(MINIMAL_INIT, encoding="utf-8")
    (folder / "0002_reshape.sql").write_text("CREATE TABLE reshaped (x INTEGER);", encoding="utf-8")
    (folder / "0002_reshape.py").write_text(
        "def migrate(conn):\n    raise RuntimeError('boom')\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError) as exc:
        MigrationRunner(fresh_db, "project").apply_pending()
    assert exc.value.detail["migration"] == "0002_reshape"
    conn = fresh_db.connect()
    assert "reshaped" not in _tables(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1


def test_python_step_without_migrate_function_is_rejected(
    fresh_db: Database, custom_root: Path
) -> None:
    folder = custom_root / "project"
    (folder / "0001_init.sql").write_text(MINIMAL_INIT, encoding="utf-8")
    (folder / "0002_reshape.sql").write_text("SELECT 1;", encoding="utf-8")
    (folder / "0002_reshape.py").write_text("VALUE = 1\n", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        MigrationRunner(fresh_db, "project").apply_pending()
    assert exc.value.detail["migration"] == "0002_reshape"


def _seed_parents(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO projects (key, name, repo_path, json, created_at, updated_at) "
        "VALUES ('DEMO', 'Demo', '.', '{}', ?, ?)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT INTO work_items (id, kind, project_key, state, title, priority, risk, json, "
        "created_at, updated_at) VALUES ('STORY-0001', 'STORY', 'DEMO', 'READY', 't', 'P2', "
        "'LOW', '{}', ?, ?)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT INTO agent_runs (id, project_key, work_item_id, role, model_id, provider, effort, "
        "state, purpose, kernel_instance, json) VALUES ('RUN-1', 'DEMO', 'STORY-0001', "
        "'SENIOR_DEV', 'fake/sim', 'fake', 'LOW', 'RUNNING', 'IMPLEMENT', 'k1', '{}')"
    )


# table -> (insert row, update it, delete it, count rows)
APPEND_ONLY_ROWS: dict[str, tuple[str, str, str, str]] = {
    "ledger_events": (
        (
            "INSERT INTO ledger_events (id, kind, at, project_key, actor_role, json) "
            "VALUES ('LED-1', 'X', '2026', 'DEMO', 'KERNEL', '{}')"
        ),
        "UPDATE ledger_events SET outcome = 'changed' WHERE id = 'LED-1'",
        "DELETE FROM ledger_events WHERE id = 'LED-1'",
        "SELECT count(*) FROM ledger_events",
    ),
    "checkpoints": (
        (
            "INSERT INTO checkpoints (id, run_id, work_item_id, seq, kind, head_sha, at, json) "
            "VALUES ('CKP-1', 'RUN-1', 'STORY-0001', 1, 'START', 'abc1234', '2026', '{}')"
        ),
        "UPDATE checkpoints SET kind = 'END' WHERE id = 'CKP-1'",
        "DELETE FROM checkpoints WHERE id = 'CKP-1'",
        "SELECT count(*) FROM checkpoints",
    ),
    "cost_records": (
        (
            "INSERT INTO cost_records (id, at, project_key, category, provider, dimension, "
            "quantity, unit, json) "
            "VALUES ('C-1', '2026', 'DEMO', 'MODEL', 'fake', 'TOKENS', 1, 'tok', '{}')"
        ),
        "UPDATE cost_records SET quantity = 2 WHERE id = 'C-1'",
        "DELETE FROM cost_records WHERE id = 'C-1'",
        "SELECT count(*) FROM cost_records",
    ),
    "evidence": (
        (
            "INSERT INTO evidence (id, kind, uri, produced_at, json) "
            "VALUES ('EVD-000001', 'TEST', 'x', '2026', '{}')"
        ),
        "UPDATE evidence SET uri = 'y' WHERE id = 'EVD-000001'",
        "DELETE FROM evidence WHERE id = 'EVD-000001'",
        "SELECT count(*) FROM evidence",
    ),
    "work_item_transitions": (
        (
            "INSERT INTO work_item_transitions (work_item_id, from_state, to_state, event, source, "
            "actor_role, at) VALUES ('STORY-0001', 'READY', 'IMPLEMENTING', 'start', 'KERNEL', "
            "'KERNEL', '2026')"
        ),
        "UPDATE work_item_transitions SET reason = 'changed' WHERE seq = 1",
        "DELETE FROM work_item_transitions WHERE seq = 1",
        "SELECT count(*) FROM work_item_transitions",
    ),
}


@pytest.mark.parametrize("table", sorted(APPEND_ONLY_ROWS))
def test_append_only_tables_reject_update_and_delete(fresh_db: Database, table: str) -> None:
    MigrationRunner(fresh_db, "project").apply_pending()
    conn = fresh_db.connect()
    _seed_parents(conn)
    insert, update, delete, count_rows = APPEND_ONLY_ROWS[table]
    conn.execute(insert)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(update)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(delete)
    assert conn.execute(count_rows).fetchone()[0] == 1


def test_kernel_migrations_create_kernel_subset(fresh_db: Database) -> None:
    assert MigrationRunner(fresh_db, "kernel").apply_pending() == [1]
    tables = _tables(fresh_db.connect())
    assert tables == KERNEL_TABLES
    assert "work_items" not in tables
    assert "ledger_events" not in tables
