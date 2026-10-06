from pathlib import Path

from typer.testing import CliRunner

from walk.cli.app import app

runner = CliRunner()


def _edit_projection(repo: Path) -> Path:
    target = repo / ".walk" / "projections" / "claude" / ".claude" / "skills" / "git-hygiene"
    (target / "SKILL.md").write_text("edited by hand\n", encoding="utf-8")
    return target / "SKILL.md"


def test_check_drift_strict_exits_one(kernel_repo: Path) -> None:
    runner.invoke(app, ["skills", "sync", "--repo", str(kernel_repo)])
    clean = runner.invoke(app, ["skills", "check-drift", "--strict", "--repo", str(kernel_repo)])
    edited = _edit_projection(kernel_repo)

    result = runner.invoke(app, ["skills", "check-drift", "--strict", "--repo", str(kernel_repo)])

    assert clean.exit_code == 0, clean.output
    assert clean.stdout.strip() == "ok"
    assert result.exit_code == 1
    assert "modified: git-hygiene (projection edited)" in result.stdout
    assert edited.read_text("utf-8") == "edited by hand\n"


def test_check_drift_regenerates_by_default(kernel_repo: Path) -> None:
    runner.invoke(app, ["skills", "sync", "--repo", str(kernel_repo)])
    edited = _edit_projection(kernel_repo)

    result = runner.invoke(app, ["skills", "check-drift", "--repo", str(kernel_repo)])
    again = runner.invoke(app, ["skills", "check-drift", "--strict", "--repo", str(kernel_repo)])

    assert result.exit_code == 0, result.output
    assert "modified: git-hygiene (projection edited)" in result.stdout
    assert "regenerated 1 projections" in result.stdout
    assert edited.read_text("utf-8") != "edited by hand\n"
    assert again.exit_code == 0, again.output


def test_check_drift_reports_canonical_change_and_missing(kernel_repo: Path) -> None:
    worktree = kernel_repo / "wt"
    worktree.mkdir()
    runner.invoke(app, ["skills", "sync", "--worktree", str(worktree), "--repo", str(kernel_repo)])
    project_skill = kernel_repo / ".ai" / "agents" / "skills" / "git-hygiene" / "SKILL.md"
    project_skill.parent.mkdir(parents=True)
    project_skill.write_text(
        "---\nname: git-hygiene\nversion: '1.1'\ndescription: project rules\nscope: PROJECT\n"
        "---\nOur own git rules.\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "skills",
            "check-drift",
            "--strict",
            "--worktree",
            str(worktree),
            "--repo",
            str(kernel_repo),
        ],
    )

    assert result.exit_code == 1
    assert "modified: git-hygiene (canonical changed)" in result.stdout


def test_check_drift_reports_kernel_errors(tmp_path: Path) -> None:
    result = runner.invoke(app, ["skills", "check-drift", "--repo", str(tmp_path / "missing")])

    assert result.exit_code == 1
    assert "error:" in result.stderr
