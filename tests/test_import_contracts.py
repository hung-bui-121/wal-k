import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "walk"
TID251_FILES = {
    "src/walk/model_router/adapters/claude/**",
    "src/walk/cli/**",
    "src/walk/integrations/credentials.py",
    "src/walk/integrations/subprocess.py",
    "src/walk/model_router/adapters/codex/process.py",
    "tests/**",
    "scripts/**",
}
BANNED = {"claude_agent_sdk", "typer", "keyring", "subprocess", "asyncio.create_subprocess_exec"}


def _table() -> dict[tuple[str, str], str]:
    """ARCHITECTURE §2.2 cells by (importer, imported), parsed from the repository document."""
    text = (ROOT / "docs" / "01-architecture" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.startswith(("| importer", "| **"))]
    header = [cell.strip() for cell in lines[0].strip().strip("|").split("|")][1:]
    cells: dict[tuple[str, str], str] = {}
    for line in lines[1:]:
        row = [cell.strip() for cell in line.strip().strip("|").split("|")]
        for column, cell in zip(header, row[1:], strict=True):
            cells[(row[0].strip("*"), column)] = cell
    return cells


def _pyproject() -> dict[str, Any]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _forbidden_pairs() -> set[tuple[str, str]]:
    contracts = _pyproject()["tool"]["importlinter"]["contracts"]
    pairs: set[tuple[str, str]] = set()
    for contract in contracts:
        assert contract["type"] == "forbidden"
        for source in contract["source_modules"]:
            for forbidden in contract["forbidden_modules"]:
                pairs.add((source.removeprefix("walk."), forbidden.removeprefix("walk.")))
    return pairs


def test_contracts_match_dependency_table() -> None:
    table = _table()
    existing = {p.name for p in SRC.iterdir() if (p / "__init__.py").is_file()}
    pairs = _forbidden_pairs()
    forbidden_cells = {
        (row, column)
        for (row, column), cell in table.items()
        if cell.startswith("·") and row in existing and column in existing
    }
    allowed_cells = {(row, column) for (row, column), cell in table.items() if cell.startswith("✔")}

    assert forbidden_cells
    assert forbidden_cells <= pairs, sorted(forbidden_cells - pairs)
    assert not (pairs & allowed_cells), sorted(pairs & allowed_cells)
    assert {(p, "cli") for p in existing - {"cli"}} <= pairs
    assert ("cli", "*.service") in pairs


def test_sdk_confinement_rules_configured() -> None:
    lint = _pyproject()["tool"]["ruff"]["lint"]
    banned = lint["flake8-tidy-imports"]["banned-api"]
    allowed = {path for path, rules in lint["per-file-ignores"].items() if "TID251" in rules}

    assert set(banned) == BANNED
    assert all(entry["msg"] for entry in banned.values())
    assert allowed == TID251_FILES
