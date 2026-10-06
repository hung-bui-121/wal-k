import json
from pathlib import Path

from typer.testing import CliRunner

from walk.cli.app import app
from walk.skills.lockfile import ProjectionLock

runner = CliRunner()
BUILTINS = {
    "code-review-checklist",
    "git-hygiene",
    "qc-exploratory-testing",
    "unity-csharp-conventions",
    "walk-output-contract",
}


def test_skills_list_shows_builtins(kernel_repo: Path) -> None:
    table = runner.invoke(app, ["skills", "list", "--repo", str(kernel_repo)])
    as_json = runner.invoke(app, ["--json", "skills", "list", "--repo", str(kernel_repo)])

    assert table.exit_code == 0, table.output
    rows = table.stdout.splitlines()[2:]
    assert len(rows) == 5
    assert {row.split()[0] for row in rows} == BUILTINS
    assert table.stdout.splitlines()[0].split() == ["name", "version", "scope", "source", "roles"]
    assert as_json.exit_code == 0, as_json.output
    assert {entry["name"] for entry in json.loads(as_json.stdout)} == BUILTINS


def test_skills_sync_writes_lock_for_all_providers(kernel_repo: Path) -> None:
    result = runner.invoke(app, ["skills", "sync", "--repo", str(kernel_repo)])

    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "projected 5 skills for 2 providers"
    lock = ProjectionLock.load(kernel_repo / ".ai")
    assert {p.provider for p in lock.projections} == {"claude", "codex"}
    assert len(lock.projections) == 10
    claude_dir = kernel_repo / ".walk" / "projections" / "claude" / ".claude" / "skills"
    assert sorted(path.name for path in claude_dir.iterdir()) == sorted(BUILTINS)
    assert (kernel_repo / ".walk" / "projections" / "codex" / "AGENTS.md").is_file()


def test_skills_sync_into_a_worktree_with_json(kernel_repo: Path, tmp_path: Path) -> None:
    worktree = kernel_repo / "sub"
    worktree.mkdir()

    result = runner.invoke(
        app, ["skills", "sync", "--json", "--worktree", str(worktree), "--repo", str(kernel_repo)]
    )

    assert result.exit_code == 0, result.output
    assert {entry["provider"] for entry in json.loads(result.stdout)["projections"]} == {
        "claude",
        "codex",
    }
    assert (worktree / "AGENTS.md").is_file()
    assert not (tmp_path / "unused").exists()


def test_skills_commands_report_kernel_errors(tmp_path: Path) -> None:
    result = runner.invoke(app, ["skills", "sync", "--repo", str(tmp_path / "missing")])

    assert result.exit_code == 1
    assert "error:" in result.stderr
