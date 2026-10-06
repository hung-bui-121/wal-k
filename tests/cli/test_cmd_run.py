import json
from pathlib import Path

from typer.testing import CliRunner

from tests.cli.conftest import migrate
from walk.cli.app import app
from walk.persistence import KernelLock

runner = CliRunner()


def test_run_exits_1_when_lock_held(kernel_repo: Path) -> None:
    with KernelLock(kernel_repo / ".ai", kernel_instance="other-process"):
        result = runner.invoke(app, ["run", "--once", "--repo", str(kernel_repo)])

    assert result.exit_code == 1
    assert "already running" in result.stderr


def test_run_once_with_no_ready_work(tmp_game_repo: Path, kernel_repo: Path) -> None:
    bare = tmp_game_repo.parent / "bare"
    bare.mkdir()
    migrate(bare, project=False)

    no_project = runner.invoke(app, ["run", "--once", "--json", "--repo", str(bare)])
    no_work = runner.invoke(app, ["--json", "run", "--once", "--repo", str(kernel_repo)])
    text = runner.invoke(
        app,
        ["--repo", str(kernel_repo), "run", "--once", "--max-parallel", "1", "--skip-preflight"],
    )

    assert no_project.exit_code == 0, no_project.output
    assert json.loads(no_project.stdout) == {"started": 0}
    assert "no project" in no_project.stderr
    assert no_work.exit_code == 0, no_work.output
    assert json.loads(no_work.stdout) == {"started": 0}
    assert text.exit_code == 0, text.output
    assert text.stdout.strip() == "started 0 run(s)"
    assert KernelLock.is_held(kernel_repo / ".ai") is False
