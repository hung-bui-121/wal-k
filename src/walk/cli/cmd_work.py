"""``walk work`` commands: inspect work items (INTERFACES §6)."""

import asyncio
from importlib.resources import files
from pathlib import Path
from typing import Annotated

import typer

from walk.cli.composition import open_database
from walk.cli.output import exit_with, render_json, render_table
from walk.common.clock import SystemClock
from walk.common.errors import WalkError
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.persistence import Database, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerRepository
from walk.workflow import (
    DefaultWorkflowManager,
    ProjectRepository,
    StoryContract,
    WorkflowRepository,
    WorkItem,
    WorkItemKind,
    WorkItemState,
)

work_app = typer.Typer(name="work", help="Work items (epics, features, stories, bugs).")

_HEADERS = ("id", "kind", "state", "title", "owner")
# Packaged YAML transition tables (E01-S09 adds the files and its TABLES_DIR constant).
_TABLES_DIR = Path(str(files("walk.workflow"))) / "tables"
_NOT_AVAILABLE = "none"

RepoOption = Annotated[
    Path | None,
    typer.Option(
        "--repo", help="Game repository root (overrides the global --repo).", file_okay=False
    ),
]
JsonOption = Annotated[bool, typer.Option("--json", help="Emit JSON (same as the global --json).")]


def _workflow_manager(db: Database) -> DefaultWorkflowManager:
    clock = SystemClock()
    ids = IdSequenceStore(db)
    ledger = DefaultLedgerManager(db, LedgerRepository(db), ids, clock)
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, clock)
    return DefaultWorkflowManager(
        db,
        WorkflowRepository(db),
        ProjectRepository(db),
        ids,
        ledger,
        hooks,
        clock,
        _TABLES_DIR,
    )


def _global(ctx: typer.Context, key: str) -> object:
    obj = ctx.find_root().obj
    return obj.get(key) if isinstance(obj, dict) else None


def _open(ctx: typer.Context, repo: Path | None) -> Database:
    root = repo if repo is not None else _global(ctx, "repo")
    try:
        return open_database(root if isinstance(root, Path) else Path(), read_only=True)
    except WalkError as exc:
        exit_with(exc)


def _wants_json(ctx: typer.Context, flag: bool) -> bool:
    return flag or bool(_global(ctx, "json"))


@work_app.command("list")
def list_items(
    ctx: typer.Context,
    *,
    state: Annotated[
        list[WorkItemState] | None, typer.Option("--state", help="State (repeatable).")
    ] = None,
    kind: Annotated[
        list[WorkItemKind] | None, typer.Option("--kind", help="Kind (repeatable).")
    ] = None,
    phase: Annotated[str | None, typer.Option("--phase", help="Phase id.")] = None,
    json_output: JsonOption = False,
    repo: RepoOption = None,
) -> None:
    """Print work items matching every given filter, oldest first."""
    db = _open(ctx, repo)
    try:
        items = asyncio.run(_workflow_manager(db).query(states=state, kinds=kind, phase_id=phase))
    finally:
        db.close()
    if _wants_json(ctx, json_output):
        typer.echo(render_json([item.model_dump(mode="json") for item in items]))
        return
    rows = (
        [item.id, item.kind.value, item.state.value, item.title, item.owner_role] for item in items
    )
    typer.echo(render_table(_HEADERS, rows))


@work_app.command("show")
def show(
    ctx: typer.Context,
    item_id: Annotated[str, typer.Argument(metavar="ID", help="Work item id.")],
    *,
    json_output: JsonOption = False,
    repo: RepoOption = None,
) -> None:
    """Print one item with its contract; transitions, runs and cost arrive in later stories."""
    db = _open(ctx, repo)
    try:
        item = asyncio.run(_workflow_manager(db).get(item_id))
    except WalkError as exc:
        exit_with(exc)
    finally:
        db.close()
    if _wants_json(ctx, json_output):
        data = item.model_dump(mode="json")
        data.setdefault("contract", None)
        typer.echo(render_json(data))
        return
    typer.echo("\n".join(_describe(item)))


def _describe(item: WorkItem) -> list[str]:
    lines = [
        f"{item.id}  {item.kind.value}  {item.state.value}",
        f"title: {item.title}",
        f"parent: {item.parent_id or '-'}",
        f"phase: {item.phase_id or '-'}",
        f"owner: {item.owner_role or '-'}",
        f"priority: {item.priority.value}  risk: {item.risk.value}",
    ]
    contract: StoryContract | None = getattr(item, "contract", None)
    if contract is None:
        lines.append(f"contract: {_NOT_AVAILABLE}")
    else:
        lines.append("contract:")
        lines.append(f"  goal: {contract.goal}")
        lines.append("  acceptance criteria:")
        lines.extend(f"  - {criterion}" for criterion in contract.acceptance_criteria)
    lines.extend(f"{section}: {_NOT_AVAILABLE}" for section in ("transitions", "runs", "cost"))
    return lines
