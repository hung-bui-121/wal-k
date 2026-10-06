import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

import walk.persistence.migrations as migrations_module
from walk.cli.app import app

runner = CliRunner()


def test_db_migrate_applies_and_prints(tmp_path: Path) -> None:
    result = runner.invoke(app, ["db", "migrate", "--repo", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "applied: 0001_init" in result.output
    assert (tmp_path / ".ai" / "kernel.db").exists()

    again = runner.invoke(app, ["db", "migrate", "--repo", str(tmp_path)])
    assert again.exit_code == 0, again.output
    assert "up to date" in again.output


def test_db_migrate_uses_global_repo_option(tmp_path: Path) -> None:
    result = runner.invoke(app, ["--repo", str(tmp_path), "db", "migrate"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".ai" / "kernel.db").exists()


def test_db_backup_writes_copy(tmp_path: Path) -> None:
    runner.invoke(app, ["db", "migrate", "--repo", str(tmp_path)])
    target = tmp_path / "out" / "backup.db"
    result = runner.invoke(app, ["db", "backup", str(target), "--repo", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert f"backup written: {target}" in result.output
    copy = sqlite3.connect(target)
    try:
        assert copy.execute("SELECT name FROM schema_migrations").fetchall() == [("init",)]
    finally:
        copy.close()


def test_db_backup_fails_without_database(tmp_path: Path) -> None:
    target = tmp_path / "backup.db"
    result = runner.invoke(app, ["db", "backup", str(target), "--repo", str(tmp_path)])
    assert result.exit_code == 1
    assert not target.exists()
    assert not (tmp_path / ".ai").exists()


def test_db_migrate_fails_when_database_cannot_be_created(tmp_path: Path) -> None:
    (tmp_path / ".ai").write_text("not a directory", encoding="utf-8")
    result = runner.invoke(app, ["db", "migrate", "--repo", str(tmp_path)])
    assert result.exit_code == 1
    assert "error:" in result.output


def test_db_migrate_fails_on_broken_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "migrations"
    (root / "project").mkdir(parents=True)
    (root / "project" / "0001_init.sql").write_text("CREATE TABLE (;", encoding="utf-8")
    monkeypatch.setattr(migrations_module, "_MIGRATIONS_ROOT", root)
    result = runner.invoke(app, ["db", "migrate", "--repo", str(tmp_path / "repo")])
    assert result.exit_code == 1
    assert "0001_init" in result.output


def test_db_backup_fails_when_target_cannot_be_written(tmp_path: Path) -> None:
    runner.invoke(app, ["db", "migrate", "--repo", str(tmp_path)])
    (tmp_path / "blocker").write_text("file, not a directory", encoding="utf-8")
    target = tmp_path / "blocker" / "backup.db"
    result = runner.invoke(app, ["db", "backup", str(target), "--repo", str(tmp_path)])
    assert result.exit_code == 1
