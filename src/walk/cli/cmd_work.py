"""``walk work`` commands: inspect work items and raise workflow events (INTERFACES §6)."""

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from walk.cli.composition import open_database
from walk.cli.output import exit_with, render_json, render_table
from walk.common.clock import SystemClock
from walk.common.errors import ConfigError, WalkError
from walk.common.models import JsonDict
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.persistence import Database, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerRepository
from walk.workflow import (
    TABLES_DIR,
    DefaultWorkflowManager,
    ProjectRepository,
    StoryContract,
    TransitionContext,
    TransitionSource,
    WorkflowRepository,
    WorkItem,
    WorkItemKind,
    WorkItemState,
    WorkItemTransition,
)

work_app = typer.Typer(name="work", help="Work items (epics, features, stories, bugs).")

_HEADERS = ("id", "kind", "state", "title", "owner")
_NOT_AVAILABLE = "none"
_DB_RELATIVE_PATH = Path(".ai") / "kernel.db"

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
        TABLES_DIR,
    )


def _global(ctx: typer.Context, key: str) -> object:
    obj = ctx.find_root().obj
    return obj.get(key) if isinstance(obj, dict) else None


def _repo_root(ctx: typer.Context, repo: Path | None) -> Path:
    root = repo if repo is not None else _global(ctx, "repo")
    return root if isinstance(root, Path) else Path()


def _open(ctx: typer.Context, repo: Path | None, *, writable: bool = False) -> Database:
    """Open the project database; it must exist (writing never creates it here)."""
    root = _repo_root(ctx, repo)
    try:
        if writable and not (root / _DB_RELATIVE_PATH).is_file():
            msg = f"database does not exist: {root / _DB_RELATIVE_PATH}"
            raise ConfigError(msg, detail={"repo": str(root)})
        return open_database(root, read_only=not writable)
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
    """Print one item with its contract and transitions; runs and cost arrive in later stories."""
    db = _open(ctx, repo)
    try:
        item = asyncio.run(_workflow_manager(db).get(item_id))
        transitions = asyncio.run(WorkflowRepository(db).transitions(item.id))
    except WalkError as exc:
        exit_with(exc)
    finally:
        db.close()
    if _wants_json(ctx, json_output):
        data = item.model_dump(mode="json")
        data.setdefault("contract", None)
        data["transitions"] = [t.model_dump(mode="json") for t in transitions]
        typer.echo(render_json(data))
        return
    typer.echo("\n".join(_describe(item, transitions)))


@work_app.command("transition")
def transition(
    ctx: typer.Context,
    item_id: Annotated[str, typer.Argument(metavar="ID", help="Work item id.")],
    event: Annotated[str, typer.Argument(metavar="EVENT", help="Workflow event name.")],
    *,
    reason: Annotated[str | None, typer.Option("--reason", help="Why (stored on the row).")] = None,
    payload: Annotated[
        str | None, typer.Option("--payload", help="Guard facts as a JSON object.")
    ] = None,
    json_output: JsonOption = False,
    repo: RepoOption = None,
) -> None:
    """Raise EVENT on the item as USER; guards still apply (exit 2 when they reject)."""
    facts = _parse_payload(payload)
    if reason is not None:
        facts["reason"] = reason
    context = TransitionContext(
        actor_role=AgentRole.USER, source=TransitionSource.USER, payload=facts
    )
    db = _open(ctx, repo, writable=True)
    try:
        row = asyncio.run(_workflow_manager(db).raise_event(item_id, event, context))
    except WalkError as exc:
        exit_with(exc)
    finally:
        db.close()
    if _wants_json(ctx, json_output):
        typer.echo(render_json(row.model_dump(mode="json")))
    else:
        typer.echo(f"{row.work_item_id}: {row.from_state.value} -> {row.to_state.value}")


def _parse_payload(text: str | None) -> JsonDict:
    if text is None:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = None
    if not isinstance(value, dict):
        exit_with(ConfigError("--payload must be a JSON object", detail={"payload": text}))
    return value


def _describe(item: WorkItem, transitions: list[WorkItemTransition]) -> list[str]:
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
    if transitions:
        lines.append("transitions:")
        lines.extend(
            f"  {t.seq}  {t.at.isoformat()}  {t.from_state.value} -> {t.to_state.value}  "
            f"{t.event}  {t.actor_role.value}" + (f"  ({t.reason})" if t.reason else "")
            for t in transitions
        )
    else:
        lines.append(f"transitions: {_NOT_AVAILABLE}")
    lines.extend(f"{section}: {_NOT_AVAILABLE}" for section in ("runs", "cost"))
    return lines
