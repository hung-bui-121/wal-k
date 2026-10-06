"""``walk phase`` commands: list, start and gate phases (INTERFACES §6; gate CLI minimal)."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from walk.cli.composition import open_database, open_workflow
from walk.cli.output import exit_with, render_json, render_table
from walk.common.errors import ConfigError, WalkError
from walk.common.models import JsonDict
from walk.common.roles import AgentRole
from walk.persistence import Database
from walk.workflow import Phase, PhaseDecision, TransitionContext, TransitionSource

phase_app = typer.Typer(name="phase", help="Phases and the phase gate.", no_args_is_help=True)

_HEADERS = ("id", "ordinal", "name", "state")
_DB_RELATIVE_PATH = Path(".ai") / "kernel.db"
_FILE_PREFIX = "@"

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


def _open(ctx: typer.Context, repo: Path | None, *, writable: bool = False) -> Database:
    """Open the project database; it must exist (writing never creates it here)."""
    root_option = repo if repo is not None else _global(ctx, "repo")
    root = root_option if isinstance(root_option, Path) else Path()
    try:
        if writable and not (root / _DB_RELATIVE_PATH).is_file():
            msg = f"database does not exist: {root / _DB_RELATIVE_PATH}"
            raise ConfigError(msg, detail={"repo": str(root)})
        return open_database(root, read_only=not writable)
    except WalkError as exc:
        exit_with(exc)


def _wants_json(ctx: typer.Context, flag: bool) -> bool:
    return flag or bool(_global(ctx, "json"))


@phase_app.command("list")
def list_phases(
    ctx: typer.Context, *, json_output: JsonOption = False, repo: RepoOption = None
) -> None:
    """Print every phase by ordinal."""
    db = _open(ctx, repo)
    try:
        phases = asyncio.run(open_workflow(db).list_phases())
    except WalkError as exc:
        exit_with(exc)
    finally:
        db.close()
    if _wants_json(ctx, json_output):
        typer.echo(render_json([phase.model_dump(mode="json") for phase in phases]))
        return
    rows = ([p.id, p.ordinal, p.name, p.state.value] for p in phases)
    typer.echo(render_table(_HEADERS, rows))


@phase_app.command("start")
def start(
    ctx: typer.Context,
    phase_id: Annotated[str, typer.Argument(metavar="ID", help="Phase id.")],
    *,
    json_output: JsonOption = False,
    repo: RepoOption = None,
) -> None:
    """Start a PLANNED phase as USER (guards still apply; exit 2 when they reject)."""
    _transition(ctx, phase_id, "start", {}, as_json=_wants_json(ctx, json_output), repo=repo)


@phase_app.command("gate")
def gate(
    ctx: typer.Context,
    phase_id: Annotated[str, typer.Argument(metavar="ID", help="Phase id.")],
    *,
    decision: Annotated[str, typer.Option("--decision", help="GO, REWORK, CHANGE or STOP (§70).")],
    feedback: Annotated[
        str | None, typer.Option("--feedback", help="Feedback text, or @FILE to read it.")
    ] = None,
    json_output: JsonOption = False,
    repo: RepoOption = None,
) -> None:
    """Record the user's Phase Gate decision (REWORK/CHANGE need feedback)."""
    try:
        choice = PhaseDecision(decision.upper())
    except ValueError:
        allowed = ", ".join(d.value for d in PhaseDecision)
        exit_with(ConfigError(f"unknown decision {decision!r}; expected {allowed}"))
    payload: JsonDict = {}
    if feedback is not None:
        payload["feedback"] = _read_feedback(feedback)
    as_json = _wants_json(ctx, json_output)
    _transition(ctx, phase_id, f"decide:{choice.value}", payload, as_json=as_json, repo=repo)


def _read_feedback(value: str) -> str:
    if not value.startswith(_FILE_PREFIX):
        return value
    path = Path(value.removeprefix(_FILE_PREFIX))
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        exit_with(ConfigError(f"cannot read feedback file {path}: {exc}"))


def _transition(
    ctx: typer.Context,
    phase_id: str,
    event: str,
    payload: JsonDict,
    *,
    as_json: bool,
    repo: Path | None,
) -> None:
    context = TransitionContext(
        actor_role=AgentRole.USER, source=TransitionSource.USER, payload=payload
    )
    db = _open(ctx, repo, writable=True)
    try:
        workflow = open_workflow(db)
        before = _find(asyncio.run(workflow.list_phases()), phase_id)
        after = asyncio.run(workflow.phase_event(phase_id, event, context))
    except WalkError as exc:
        exit_with(exc)
    finally:
        db.close()
    if as_json:
        typer.echo(render_json(after.model_dump(mode="json")))
    else:
        typer.echo(f"{after.id}: {before.state.value} -> {after.state.value}")


def _find(phases: list[Phase], phase_id: str) -> Phase:
    for phase in phases:
        if phase.id == phase_id:
            return phase
    msg = f"phase not found: {phase_id}"
    raise ConfigError(msg, detail={"phase_id": phase_id})
