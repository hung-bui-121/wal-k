import asyncio
import json
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.cli.conftest import add_story
from tests.runtime.conftest import make_run
from walk.budgets import Budget, BudgetDimension, BudgetRepository, BudgetScope
from walk.cli.app import app
from walk.orchestrator import KernelStatus
from walk.persistence import Database, KernelLock, UnitOfWork
from walk.runtime import AgentRunRepository, AgentRunState
from walk.workflow import WorkItemState

runner = CliRunner()


async def _seed(repo: Path) -> None:
    await add_story(repo, 1, "Double jump", WorkItemState.IMPLEMENTING)
    await add_story(repo, 2, "Wall slide", WorkItemState.BLOCKED)
    db = Database(repo / ".ai" / "kernel.db")
    try:
        async with UnitOfWork(db) as uow:
            await AgentRunRepository(db).insert(
                make_run(
                    "RUN-01J0000000000000000000000S",
                    state=AgentRunState.RUNNING,
                    model_id="fake-codex/sim",
                ),
                uow,
            )
            await BudgetRepository(db).upsert(
                Budget(
                    id="PROJECT:DEMO:COST_USD",
                    scope=BudgetScope.PROJECT,
                    scope_id="DEMO",
                    dimension=BudgetDimension.COST_USD,
                    limit=50.0,
                    consumed=1.5,
                ),
                uow,
            )
    finally:
        db.close()


def test_status_json_and_table(kernel_repo: Path) -> None:
    asyncio.run(_seed(kernel_repo))

    as_json = runner.invoke(app, ["status", "--json", "--repo", str(kernel_repo)])
    table = runner.invoke(app, ["--repo", str(kernel_repo), "status"])

    assert as_json.exit_code == 0, as_json.output
    status = KernelStatus.model_validate(json.loads(as_json.stdout))
    assert status.project_key == "DEMO"
    assert status.phase_progress == {WorkItemState.IMPLEMENTING: 1, WorkItemState.BLOCKED: 1}
    assert status.blocked_items == ["STORY-0002"]
    assert [run.id for run in status.active_runs] == ["RUN-01J0000000000000000000000S"]
    assert [budget.id for budget in status.budgets] == ["PROJECT:DEMO:COST_USD"]
    assert table.exit_code == 0, table.output
    assert "SENIOR_DEV" in table.stdout
    assert "fake-codex/sim" in table.stdout
    assert "blocked items: STORY-0002" in table.stdout
    assert "PROJECT:DEMO:COST_USD  1.5" in table.stdout


def test_status_does_not_need_lock(kernel_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    def interrupted(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) > 1:
            raise KeyboardInterrupt

    monkeypatch.setattr(time, "sleep", interrupted)
    with KernelLock(kernel_repo / ".ai", kernel_instance="daemon"):
        held = runner.invoke(app, ["status", "--repo", str(kernel_repo)])
        watched = runner.invoke(app, ["status", "--watch", "--json", "--repo", str(kernel_repo)])

    assert held.exit_code == 0, held.output
    assert "project: DEMO" in held.stdout
    assert "phase: none" in held.stdout
    assert watched.exit_code == 0, watched.output
    assert watched.stdout.count('"project_key": "DEMO"') == 2
    assert sleeps == [2.0, 2.0]


def test_status_without_database_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(app, ["status", "--repo", str(tmp_path)])

    assert result.exit_code == 1
    assert not (tmp_path / ".ai").exists()
