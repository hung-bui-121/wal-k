"""``walk status``: the §87 `KernelStatus` snapshot, read-only (INTERFACES §6; E01-S30).

It reads the database through a read-only connection, needs no daemon and takes no lock.
"""

import asyncio
import time
from pathlib import Path
from typing import Annotated, Final

import typer

from walk.cli.composition import build_status_reader
from walk.cli.output import exit_with, render_table
from walk.common.errors import WalkError
from walk.orchestrator import KernelStatus, StatusBuilder

_WATCH_INTERVAL_S: Final = 2.0
_NONE: Final = "none"


def status(
    ctx: typer.Context,
    *,
    json_output: Annotated[bool, typer.Option("--json", help="Emit KernelStatus JSON.")] = False,
    watch: Annotated[
        bool, typer.Option("--watch", help="Re-render every 2 s until interrupted.")
    ] = False,
    repo: Annotated[
        Path | None, typer.Option("--repo", help="Game repository root.", file_okay=False)
    ] = None,
) -> None:
    """Print phase, progress, active runs, blocked items, approvals and budgets."""
    options = ctx.find_root().obj if isinstance(ctx.find_root().obj, dict) else {}
    root = repo if repo is not None else options.get("repo", Path())
    as_json = json_output or bool(options.get("json"))
    path = root if isinstance(root, Path) else Path()
    try:
        reader = build_status_reader(path)
        _print(reader, as_json=as_json)
        while watch:
            time.sleep(_WATCH_INTERVAL_S)
            _print(reader, as_json=as_json)
    except KeyboardInterrupt:
        return
    except WalkError as exc:
        exit_with(exc)


def _print(reader: StatusBuilder, *, as_json: bool) -> None:
    snapshot = asyncio.run(reader.build())
    if as_json:
        typer.echo(snapshot.model_dump_json(indent=2))
        return
    typer.echo(_render(snapshot))


def _render(snapshot: KernelStatus) -> str:
    phase = snapshot.current_phase
    lines = [
        f"project: {snapshot.project_key}" + ("  (paused)" if snapshot.paused else ""),
        f"phase: {f'{phase.id} {phase.name} ({phase.state.value})' if phase else _NONE}",
        "",
        render_table(
            ("state", "items"),
            sorted((state.value, count) for state, count in snapshot.phase_progress.items()),
        ),
        "",
        "active runs:",
        render_table(
            ("run", "item", "role", "model", "state"),
            (
                (run.id, run.work_item_id, run.role.value, run.model_id, run.state.value)
                for run in snapshot.active_runs
            ),
        ),
        "",
        f"blocked items: {', '.join(snapshot.blocked_items) or _NONE}",
        f"pending approvals: {', '.join(a.id for a in snapshot.pending_approvals) or _NONE}",
        "",
        "budgets:",
        render_table(
            ("budget", "consumed", "limit"),
            ((b.id, b.consumed, b.limit) for b in snapshot.budgets),
        ),
    ]
    return "\n".join(lines)
