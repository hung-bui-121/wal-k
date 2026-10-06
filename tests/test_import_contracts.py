import ast
import re
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


# ---- module-level cells and per-file confinement (E01-B06) ---------------------------------

PUBLIC_MODULES = frozenset({"models", "protocols", "errors"})
INFRASTRUCTURE = frozenset({"common", "persistence"})
UNRESTRICTED_IMPORTERS = frozenset({"orchestrator", "cli"})  # §2.2 legend: any module
NAMED_MODULE = re.compile(r"`(\w+)`")
PACKAGE_PARTS = 2  # "walk.<pkg>"; a third part is the module
CONFINED: dict[str, tuple[str, ...]] = {
    # banned name → files (or folders, ending in "/") allowed to use it, relative to src/walk
    "subprocess": ("integrations/subprocess.py", "model_router/adapters/codex/process.py"),
    "asyncio.create_subprocess_exec": (
        "integrations/subprocess.py",
        "model_router/adapters/codex/process.py",
    ),
    "claude_agent_sdk": ("model_router/adapters/claude/",),
    "typer": ("cli/",),
    "keyring": ("integrations/credentials.py",),
}


def _allowed_modules(cell: str) -> frozenset[str] | None:
    """Modules a `✔` cell allows (None: the cell forbids the package)."""
    if not cell.startswith("✔"):
        return None
    named = NAMED_MODULE.findall(cell) if "+" in cell else []
    return PUBLIC_MODULES | set(named)


def _reexports(src: Path, package: str) -> dict[str, str]:
    """Name → defining submodule of ``walk.<package>`` (from its ``__init__`` imports)."""
    init = src / package / "__init__.py"
    names: dict[str, str] = {}
    for node in ast.walk(ast.parse(init.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        parts = node.module.split(".")
        if (
            node.level == 0
            and parts[:PACKAGE_PARTS] == ["walk", package]
            and len(parts) > PACKAGE_PARTS
        ):
            submodule = parts[2]
        elif node.level == 1:
            submodule = parts[0]
        else:
            continue
        for alias in node.names:
            names[alias.asname or alias.name] = submodule
    return names


def _imported_modules(node: ast.Import | ast.ImportFrom, src: Path) -> list[tuple[str, str, str]]:
    """``(package, module, text)`` for each ``walk.<package>`` module the import statement uses."""
    found: list[tuple[str, str, str]] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            parts = alias.name.split(".")
            if parts[0] == "walk" and len(parts) > PACKAGE_PARTS:
                found.append((parts[1], parts[2], f"import {alias.name}"))
        return found
    if node.level != 0 or node.module is None:
        return found
    parts = node.module.split(".")
    if parts[0] != "walk" or len(parts) < PACKAGE_PARTS:
        return found
    package = parts[1]
    if len(parts) > PACKAGE_PARTS:
        found.append((package, parts[2], f"from {node.module} import ..."))
        return found
    reexports = _reexports(src, package)
    for alias in node.names:  # rule 2: resolve the package __init__ re-export
        module = reexports.get(alias.name, alias.name)
        found.append((package, module, f"from {node.module} import {alias.name}"))
    return found


def _cell_violations(src: Path, cells: dict[tuple[str, str], str]) -> list[str]:
    """Imports of another package's module that its §2.2 cell does not allow."""
    violations: list[str] = []
    for path in sorted(src.rglob("*.py")):
        importer = path.relative_to(src).parts[0]
        if importer in UNRESTRICTED_IMPORTERS or not (src / importer).is_dir():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            for package, module, text in _imported_modules(node, src):
                if package in {importer, *INFRASTRUCTURE}:
                    continue
                cell = cells.get((importer, package), "")
                allowed = _allowed_modules(cell)
                if allowed is None or module not in allowed:
                    where = f"{path.relative_to(src).as_posix()}:{node.lineno}"
                    violations.append(
                        f"{where}: {text} uses walk.{package}.{module}; "
                        f"{importer} -> {package} cell {cell!r} allows {sorted(allowed or [])}"
                    )
    return violations


def _uses(tree: ast.AST, name: str) -> list[int]:
    """Lines where ``name`` (a module, or ``module.attribute``) is imported or used."""
    module, _, attribute = name.partition(".")
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and not attribute:
            lines += [node.lineno for a in node.names if a.name.split(".")[0] == module]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
            if node.module.split(".")[0] != module:
                continue
            if not attribute or any(a.name == attribute for a in node.names):
                lines.append(node.lineno)
        elif (
            isinstance(node, ast.Attribute)
            and attribute
            and node.attr == attribute
            and isinstance(node.value, ast.Name)
            and node.value.id == module
        ):
            lines.append(node.lineno)
    return lines


def _confinement_violations(src: Path) -> list[str]:
    violations: list[str] = []
    for path in sorted(src.rglob("*.py")):
        relative = path.relative_to(src).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name, allowed in CONFINED.items():
            if any(relative == a or (a.endswith("/") and relative.startswith(a)) for a in allowed):
                continue
            violations += [
                f"{relative}:{line}: uses {name}; allowed only in {', '.join(allowed)}"
                for line in _uses(tree, name)
            ]
    return violations


def test_cross_package_imports_respect_module_cells() -> None:
    assert _cell_violations(SRC, _table()) == []


def test_reexported_services_count_as_service_imports(tmp_path: Path) -> None:
    src = tmp_path / "walk"
    files = {
        "alpha/__init__.py": (
            "from walk.alpha.models import Thing\nfrom walk.alpha.service import DefaultThing\n"
        ),
        "alpha/models.py": "class Thing: ...\n",
        "alpha/service.py": "class DefaultThing: ...\n",
        "beta/__init__.py": "",
        "beta/uses.py": (
            "from walk.alpha import Thing\n"
            "from walk.alpha import DefaultThing\n"
            "from walk.alpha.models import Thing as Again\n"
        ),
    }
    for relative, text in files.items():
        (src / relative).parent.mkdir(parents=True, exist_ok=True)
        (src / relative).write_text(text, encoding="utf-8")

    violations = _cell_violations(src, {("beta", "alpha"): "✔"})

    assert len(violations) == 1
    assert violations[0].startswith("beta/uses.py:2: from walk.alpha import DefaultThing")
    assert "walk.alpha.service" in violations[0]
    assert _cell_violations(src, {("beta", "alpha"): "✔ (+ `service`)"}) == []


def test_process_and_sdk_imports_confined_per_file() -> None:
    assert _confinement_violations(SRC) == []
