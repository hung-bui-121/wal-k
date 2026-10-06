import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from walk.cli.app import app
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.persistence import Database, IdSequenceStore, MigrationRunner, UnitOfWork
from walk.telemetry import DefaultLedgerManager, LedgerRepository
from walk.workflow import (
    TABLES_DIR,
    DefaultWorkflowManager,
    Project,
    ProjectRepository,
    StoryContract,
    WorkflowRepository,
    WorkItemDraft,
    WorkItemKind,
)

runner = CliRunner()


@pytest.fixture
def repo(tmp_path: Path, fake_clock: FakeClock) -> Path:
    """A repository whose database holds FEAT-0001 and STORY-0001."""
    db = Database(tmp_path / ".ai" / "kernel.db")
    MigrationRunner(db, "project").apply_pending()
    ledger = DefaultLedgerManager(db, LedgerRepository(db), SequentialIdFactory(), fake_clock)
    workflow = DefaultWorkflowManager(
        db,
        WorkflowRepository(db),
        ProjectRepository(db),
        IdSequenceStore(db),
        ledger,
        DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock),
        fake_clock,
        TABLES_DIR,
    )

    async def seed() -> None:
        demo = Project(
            key="DEMO",
            name="Demo",
            repo_path=str(tmp_path),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        async with UnitOfWork(db) as uow:
            await ProjectRepository(db).insert(demo, uow)
        await workflow.create(
            WorkItemDraft(kind=WorkItemKind.FEATURE, title="Inventory", description="Bag"),
            actor=AgentRole.PRODUCT_OWNER,
            phase_id=None,
        )
        await workflow.create(
            WorkItemDraft(
                kind=WorkItemKind.STORY,
                title="Pick up item",
                description="",
                parent_id="FEAT-0001",
                contract=StoryContract(goal="Pick up", acceptance_criteria=["item in bag"]),
            ),
            actor=AgentRole.PRODUCT_OWNER,
            phase_id=None,
        )

    asyncio.run(seed())
    db.close()
    return tmp_path


def test_work_list_filters_by_kind(repo: Path) -> None:
    result = runner.invoke(app, ["work", "list", "--kind", "FEATURE", "--repo", str(repo)])
    assert result.exit_code == 0, result.output
    lines = result.output.strip().splitlines()
    assert lines[0].split() == ["id", "kind", "state", "title", "owner"]
    assert len(lines) == 3
    assert lines[2].split() == ["FEAT-0001", "FEATURE", "IDEA", "Inventory"]


def test_work_list_all_and_json(repo: Path) -> None:
    result = runner.invoke(app, ["--json", "--repo", str(repo), "work", "list", "--state", "IDEA"])
    assert result.exit_code == 0, result.output
    items = json.loads(result.output)
    assert [(item["id"], item["owner_role"]) for item in items] == [
        ("FEAT-0001", None),
        ("STORY-0001", "SENIOR_DEV"),
    ]
    empty = runner.invoke(app, ["work", "list", "--state", "READY", "--repo", str(repo)])
    assert empty.exit_code == 0
    assert len(empty.output.strip().splitlines()) == 2


def test_work_show_json(repo: Path) -> None:
    result = runner.invoke(app, ["work", "show", "FEAT-0001", "--json", "--repo", str(repo)])
    assert result.exit_code == 0, result.output
    shown = json.loads(result.output)
    assert shown["id"] == "FEAT-0001"
    assert shown["state"] == "IDEA"
    assert shown["contract"] is None
    story = json.loads(
        runner.invoke(app, ["work", "show", "STORY-0001", "--json", "--repo", str(repo)]).output
    )
    assert story["contract"]["goal"] == "Pick up"


def test_work_show_text(repo: Path) -> None:
    result = runner.invoke(app, ["work", "show", "STORY-0001", "--repo", str(repo)])
    assert result.exit_code == 0, result.output
    text = result.output
    assert "STORY-0001  STORY  IDEA" in text
    assert "goal: Pick up" in text
    assert "- item in bag" in text
    for section in ("transitions: none", "runs: none", "cost: none"):
        assert section in text
    feature = runner.invoke(app, ["work", "show", "FEAT-0001", "--repo", str(repo)])
    assert "contract: none" in feature.output
    assert "owner: -" in feature.output


def test_work_show_unknown_exits_1(repo: Path) -> None:
    result = runner.invoke(app, ["work", "show", "NOPE-1", "--repo", str(repo)])
    assert result.exit_code == 1
    assert "NOPE-1" in result.output


def test_work_commands_fail_without_database(tmp_path: Path) -> None:
    assert runner.invoke(app, ["work", "list", "--repo", str(tmp_path)]).exit_code == 1
    assert runner.invoke(app, ["work", "show", "FEAT-0001", "--repo", str(tmp_path)]).exit_code == 1
    assert not (tmp_path / ".ai").exists()


def test_work_transition_exit_codes(repo: Path) -> None:
    result = runner.invoke(app, ["work", "transition", "STORY-0001", "ready", "--repo", str(repo)])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "STORY-0001: IDEA -> READY"
    rejected = runner.invoke(
        app, ["work", "transition", "STORY-0001", "start_implementation", "--repo", str(repo)]
    )
    assert rejected.exit_code == 2
    assert "branch_available: payload missing" in rejected.output
    payload = '{"branch_available": true, "budget_ok": true}'
    started = runner.invoke(
        app,
        [
            "work",
            "transition",
            "STORY-0001",
            "start_implementation",
            "--payload",
            payload,
            "--reason",
            "manual start",
            "--json",
            "--repo",
            str(repo),
        ],
    )
    assert started.exit_code == 0, started.output
    row = json.loads(started.output)
    assert (row["from_state"], row["to_state"], row["reason"]) == (
        "READY",
        "IMPLEMENTING",
        "manual start",
    )
    assert row["actor_role"] == "USER"


def test_work_transition_errors_exit_1(repo: Path, tmp_path: Path) -> None:
    unknown_event = runner.invoke(
        app, ["work", "transition", "STORY-0001", "explode", "--repo", str(repo)]
    )
    assert unknown_event.exit_code == 1
    unknown_item = runner.invoke(
        app, ["work", "transition", "STORY-0042", "ready", "--repo", str(repo)]
    )
    assert unknown_item.exit_code == 1
    for bad in ("not json", "[1, 2]"):
        result = runner.invoke(
            app,
            ["work", "transition", "STORY-0001", "ready", "--payload", bad, "--repo", str(repo)],
        )
        assert result.exit_code == 1
        assert "--payload" in result.output
    missing = tmp_path / "elsewhere"
    missing.mkdir()
    no_db = runner.invoke(
        app, ["work", "transition", "STORY-0001", "ready", "--repo", str(missing)]
    )
    assert no_db.exit_code == 1
    assert not (missing / ".ai").exists()


def test_work_show_lists_transitions(repo: Path) -> None:
    runner.invoke(app, ["work", "transition", "STORY-0001", "ready", "--repo", str(repo)])
    text = runner.invoke(app, ["work", "show", "STORY-0001", "--repo", str(repo)]).output
    assert "transitions:" in text
    assert "IDEA -> READY  ready  USER" in text
    shown = json.loads(
        runner.invoke(app, ["work", "show", "STORY-0001", "--json", "--repo", str(repo)]).output
    )
    assert [(t["from_state"], t["to_state"]) for t in shown["transitions"]] == [("IDEA", "READY")]
