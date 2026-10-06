import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = [
    "uv run ruff format --check .",
    "uv run ruff check .",
    "uv run mypy src tests",
    "uv run pytest",
]


def test_check_scripts_invoke_all_gate_commands() -> None:
    for name in ("check.sh", "check.ps1"):
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        positions = [text.index(cmd) for cmd in GATE]
        assert positions == sorted(positions), name


def test_pyproject_enforces_quality_gate() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    tool = config["tool"]
    assert tool["ruff"]["lint"]["select"] == ["ALL"]
    assert tool["mypy"]["strict"] is True
    assert tool["pytest"]["ini_options"]["asyncio_mode"] == "auto"
    assert "--cov-fail-under=85" in tool["pytest"]["ini_options"]["addopts"]


def test_tmp_repo_fixture_is_initialised_git_repo(tmp_repo: Path) -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_repo, check=True, capture_output=True, text=True
    )
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=tmp_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert len(head.stdout.strip()) == 40
    assert branch.stdout.strip() == "main"
