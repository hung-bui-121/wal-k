"""``walk work`` commands: inspect work items and raise workflow events (INTERFACES §6)."""

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from walk.cli.composition import KernelHandle, open_database, open_workflow
from walk.cli.daemon import transition_in_kernel
from walk.cli.ipc import run_mutation
from walk.cli.output import exit_with, render_json, render_table
from walk.common.errors import ConfigError, Timeout, WalkError
from walk.common.models import JsonDict
from walk.persistence import Database
from walk.workflow import (
    StoryContract,
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
_EXIT_NO_DAEMON = 3  # INTERFACES §6: daemon not responding

RepoOption = Annotated[
    Path | None,
    typer.Option(
        "--repo", help="Game repository root (overrides the global --repo).", file_okay=False
    ),
]
JsonOption = Annotated[bool, typer.Option("--json", help="Emit JSON (same as the global --json).")]


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
        items = asyncio.run(open_workflow(db).query(states=state, kinds=kind, phase_id=phase))
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
        item = asyncio.run(open_workflow(db).get(item_id))
        newest_first = asyncio.run(WorkflowRepository(db).transitions(item.id, limit=None))
        transitions = list(reversed(newest_first))
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
    """Raise EVENT on the item as USER; guards still apply (exit 2 when they reject).

    Runs in the daemon when one holds the kernel lock (command ``work.transition``), else
    in-process under the lock. Exit codes: 0 ok, 2 guard/permission, 1 other, 3 when the
    daemon does not answer.
    """
    facts = _parse_payload(payload)
    root = _repo_root(ctx, repo)
    _open(ctx, repo, writable=True).close()  # the database must exist; never create it here
    args: JsonDict = {
        "work_item_id": item_id,
        "event": event,
        "reason": reason,
        "payload": facts,
    }

    async def in_process(handle: KernelHandle) -> JsonDict:
        return await transition_in_kernel(handle, args)

    try:
        result = asyncio.run(run_mutation(root, "work.transition", args, in_process))
    except Timeout:
        typer.echo("error: daemon not responding", err=True)
        raise typer.Exit(code=_EXIT_NO_DAEMON) from None
    except WalkError as exc:
        exit_with(exc)
    if not result.ok:
        typer.echo(f"error: {result.result.get('error')}", err=True)
        raise typer.Exit(code=result.exit_code)
    row = WorkItemTransition.model_validate(result.result["transition"])
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
