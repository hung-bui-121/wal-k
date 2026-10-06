import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.fakes.fake_clock import FakeClock
from walk.budgets import BudgetDimension, CostCategory, CostRecord
from walk.cli.app import app
from walk.cli.composition import open_costs, open_workflow
from walk.common.roles import AgentRole
from walk.persistence import Database, MigrationRunner, UnitOfWork
from walk.workflow import Project, ProjectRepository, WorkItemDraft, WorkItemKind

runner = CliRunner()


def _record(record_id: str, usd: float, item: str, category: CostCategory) -> CostRecord:
    return CostRecord(
        id=record_id,
        at=datetime(2026, 1, 1, tzinfo=UTC),
        project_key="DEMO",
        category=category,
        provider="claude",
        dimension=BudgetDimension.COST_USD,
        quantity=usd,
        unit="usd",
        cost_usd=usd,
        work_item_id=item,
        phase_id="PHASE-01",
    )


@pytest.fixture
def repo(tmp_path: Path, fake_clock: FakeClock) -> Path:
    """A repository with FEAT-0001 and two cost records on it."""
    db = Database(tmp_path / ".ai" / "kernel.db")
    MigrationRunner(db, "project").apply_pending()

    async def seed() -> None:
        async with UnitOfWork(db) as uow:
            await ProjectRepository(db).insert(
                Project(key="DEMO", name="Demo", repo_path=str(tmp_path)), uow
            )
        await open_workflow(db, clock=fake_clock).create(
            WorkItemDraft(kind=WorkItemKind.FEATURE, title="F", description=""),
            actor=AgentRole.PRODUCT_OWNER,
            phase_id=None,
        )
        costs = open_costs(db, clock=fake_clock)
        await costs.record(_record("COST-1", 1.25, "FEAT-0001", CostCategory.LLM))
        await costs.record(_record("COST-2", 0.5, "FEAT-0001", CostCategory.COMPUTE))

    asyncio.run(seed())
    db.close()
    return tmp_path


def test_cost_item_json(repo: Path) -> None:
    result = runner.invoke(app, ["cost", "--item", "FEAT-0001", "--json", "--repo", str(repo)])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["categories"] == {"LLM": 1.25, "ASSETS": 0.0, "COMPUTE": 0.5, "TIME": 0.0}
    assert data["total_usd"] == 1.75


def test_cost_project_and_phase_tables(repo: Path) -> None:
    result = runner.invoke(app, ["cost", "--project", "--repo", str(repo)])
    assert result.exit_code == 0, result.output
    lines = result.output.strip().splitlines()
    assert lines[0].split() == ["category", "usd"]
    assert lines[2].split() == ["LLM", "1.25"]
    assert lines[-1].split() == ["total", "1.75"]
    phase = runner.invoke(app, ["--json", "--repo", str(repo), "cost", "--phase", "PHASE-01"])
    assert json.loads(phase.output)["total_usd"] == 1.75


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--item", "FEAT-0001", "--project"],
    ],
)
def test_cost_requires_exactly_one_subject(repo: Path, args: list[str]) -> None:
    result = runner.invoke(app, ["cost", *args, "--repo", str(repo)])
    assert result.exit_code == 1
    assert "exactly one" in result.output


def test_cost_fails_without_database(tmp_path: Path) -> None:
    assert runner.invoke(app, ["cost", "--project", "--repo", str(tmp_path)]).exit_code == 1
    assert not (tmp_path / ".ai").exists()


def test_cost_unknown_item_exits_1(repo: Path) -> None:
    result = runner.invoke(app, ["cost", "--item", "STORY-0042", "--repo", str(repo)])
    assert result.exit_code == 1
    assert "STORY-0042" in result.output
