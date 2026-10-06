import asyncio
import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from walk.cli import cmd_ledger
from walk.cli.app import app
from walk.cli.output import exit_with, render_json, render_table
from walk.common.errors import ConfigError, GuardRejected, PermissionDenied
from walk.common.roles import AgentRole
from walk.persistence import Database, MigrationRunner
from walk.telemetry import DefaultLedgerManager, LedgerEvent, LedgerEventKind, LedgerRepository

runner = CliRunner()


@pytest.fixture
def repo(tmp_path: Path, fake_clock: FakeClock) -> Path:
    """A repository whose database holds three ledger events."""
    db = Database(tmp_path / ".ai" / "kernel.db")
    MigrationRunner(db, "project").apply_pending()
    ledger = DefaultLedgerManager(db, LedgerRepository(db), SequentialIdFactory(), fake_clock)
    kinds = [
        LedgerEventKind.WORK_ITEM_CREATED,
        LedgerEventKind.WORK_ITEM_TRANSITION,
        LedgerEventKind.WORK_ITEM_CREATED,
    ]

    async def seed() -> None:
        for n, kind in enumerate(kinds, start=1):
            await ledger.append(
                LedgerEvent(
                    kind=kind,
                    project_key="DEMO",
                    actor_role=AgentRole.KERNEL,
                    work_item_id=f"STORY-000{n}",
                    outcome="OK",
                )
            )

    asyncio.run(seed())
    db.close()
    return tmp_path


def test_ledger_query_json_output(repo: Path) -> None:
    args = ["ledger", "query", "--kind", "WORK_ITEM_CREATED", "--json", "--repo", str(repo)]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    events = json.loads(result.output)
    assert isinstance(events, list)
    assert [(e["seq"], e["kind"]) for e in events] == [
        (1, "WORK_ITEM_CREATED"),
        (3, "WORK_ITEM_CREATED"),
    ]


def test_ledger_query_table_output_with_filters(repo: Path) -> None:
    args = ["ledger", "query", "--item", "STORY-0002", "--limit", "5", "--repo", str(repo)]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    lines = result.output.strip().splitlines()
    assert lines[0].split() == ["seq", "at", "kind", "actor", "item", "run", "outcome"]
    assert len(lines) == 3  # header, rule, one row
    assert "WORK_ITEM_TRANSITION" in lines[2]


def test_ledger_query_global_json_and_time_window(repo: Path) -> None:
    args = ["--json", "--repo", str(repo), "ledger", "query", "--since", "2026-01-01T00:00:00"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert len(json.loads(result.output)) == 3
    until = runner.invoke(
        app, ["--json", "--repo", str(repo), "ledger", "query", "--until", "2025-12-31T00:00:00Z"]
    )
    assert json.loads(until.output) == []


def test_ledger_query_rejects_bad_timestamp(repo: Path) -> None:
    result = runner.invoke(app, ["ledger", "query", "--since", "not-a-date", "--repo", str(repo)])
    assert result.exit_code == 1
    assert "not-a-date" in result.output


def test_ledger_query_fails_without_database(tmp_path: Path) -> None:
    result = runner.invoke(app, ["ledger", "query", "--repo", str(tmp_path)])
    assert result.exit_code == 1
    assert not (tmp_path / ".ai").exists()


def test_ledger_tail_prints_events_after_seq(repo: Path) -> None:
    result = runner.invoke(app, ["ledger", "tail", "--since", "0", "--repo", str(repo)])
    assert result.exit_code == 0, result.output
    rows = result.output.strip().splitlines()[2:]
    assert [row.split()[0] for row in rows] == ["1", "2", "3"]
    later = runner.invoke(app, ["ledger", "tail", "--since", "2", "--json", "--repo", str(repo)])
    assert [e["seq"] for e in json.loads(later.output)] == [3]


def test_ledger_tail_follow_streams_until_interrupted(
    repo: Path, monkeypatch: pytest.MonkeyPatch, fake_clock: FakeClock
) -> None:
    async def interrupt(_seconds: float) -> None:
        raise KeyboardInterrupt

    def manager(db: Database) -> DefaultLedgerManager:
        return DefaultLedgerManager(
            db, LedgerRepository(db), SequentialIdFactory(), fake_clock, sleep=interrupt
        )

    monkeypatch.setattr(cmd_ledger, "_ledger_manager", manager)
    result = runner.invoke(
        app, ["ledger", "tail", "--since", "1", "--follow", "--json", "--repo", str(repo)]
    )
    assert result.exit_code == 0, result.output
    seqs = [json.loads(line)["seq"] for line in result.output.strip().splitlines()]
    assert seqs == [2, 3]


def test_ledger_tail_fails_without_database(tmp_path: Path) -> None:
    result = runner.invoke(app, ["ledger", "tail", "--repo", str(tmp_path)])
    assert result.exit_code == 1


def test_render_table_aligns_columns() -> None:
    table = render_table(["a", "long"], [[1, None], ["xyz", "v"]])
    assert table.splitlines() == ["a    long", "---  ----", "1", "xyz  v"]


def test_render_json_serialises_lists() -> None:
    assert json.loads(render_json([{"a": 1}])) == [{"a": 1}]


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ConfigError("bad"), 1),
        (GuardRejected("no"), 2),
        (PermissionDenied("no"), 2),
    ],
)
def test_exit_with_maps_error_to_exit_code(error: ConfigError, code: int) -> None:
    with pytest.raises(typer.Exit) as exc:
        exit_with(error)
    assert exc.value.exit_code == code


def test_ledger_tail_follow_prints_plain_lines(
    repo: Path, monkeypatch: pytest.MonkeyPatch, fake_clock: FakeClock
) -> None:
    async def interrupt(_seconds: float) -> None:
        raise KeyboardInterrupt

    def manager(db: Database) -> DefaultLedgerManager:
        return DefaultLedgerManager(
            db, LedgerRepository(db), SequentialIdFactory(), fake_clock, sleep=interrupt
        )

    monkeypatch.setattr(cmd_ledger, "_ledger_manager", manager)
    result = runner.invoke(app, ["ledger", "tail", "--since", "2", "--follow", "--repo", str(repo)])
    assert result.exit_code == 0, result.output
    assert result.output.split()[:3] == ["3", fake_clock.now().isoformat(), "WORK_ITEM_CREATED"]
