"""``walk ledger`` commands: read the append-only execution ledger (INTERFACES §6)."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from walk.cli.composition import open_database
from walk.cli.output import exit_with, render_json, render_table
from walk.common.clock import SystemClock
from walk.common.errors import ConfigError
from walk.persistence import Database, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerEvent, LedgerEventKind, LedgerRepository

ledger_app = typer.Typer(
    name="ledger", help="Execution ledger (audit trail).", no_args_is_help=True
)

_HEADERS = ("seq", "at", "kind", "actor", "item", "run", "outcome")
_COLUMN_GAP = "  "

RepoOption = Annotated[
    Path | None,
    typer.Option(
        "--repo", help="Game repository root (overrides the global --repo).", file_okay=False
    ),
]
JsonOption = Annotated[bool, typer.Option("--json", help="Emit JSON (same as the global --json).")]


def _ledger_manager(db: Database) -> DefaultLedgerManager:
    return DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), SystemClock())


def _global(ctx: typer.Context, key: str) -> object:
    obj = ctx.find_root().obj
    return obj.get(key) if isinstance(obj, dict) else None


def _open(ctx: typer.Context, repo: Path | None) -> Database:
    root = repo if repo is not None else _global(ctx, "repo")
    try:
        return open_database(root if isinstance(root, Path) else Path(), read_only=True)
    except ConfigError as exc:
        exit_with(exc)


def _wants_json(ctx: typer.Context, flag: bool) -> bool:
    return flag or bool(_global(ctx, "json"))


def _parse_time(value: str | None, option: str) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        exit_with(ConfigError(f"invalid {option} timestamp: {value!r}", detail={option: value}))
    # A timestamp without offset is read as UTC, the kernel's only time zone.
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _row(event: LedgerEvent) -> list[object]:
    return [
        event.seq,
        event.at.isoformat(),
        event.kind.value,
        event.actor_role.value,
        event.work_item_id,
        event.run_id,
        event.outcome,
    ]


def _print(events: list[LedgerEvent], *, as_json: bool) -> None:
    if as_json:
        typer.echo(render_json([event.model_dump(mode="json") for event in events]))
    else:
        typer.echo(render_table(_HEADERS, (_row(event) for event in events)))


@ledger_app.command("query")
def query(
    ctx: typer.Context,
    *,
    kind: Annotated[
        list[LedgerEventKind] | None, typer.Option("--kind", help="Event kind (repeatable).")
    ] = None,
    item: Annotated[str | None, typer.Option("--item", help="Work item id.")] = None,
    run: Annotated[str | None, typer.Option("--run", help="Agent run id.")] = None,
    phase: Annotated[str | None, typer.Option("--phase", help="Phase id.")] = None,
    since: Annotated[str | None, typer.Option("--since", help="ISO 8601 lower bound.")] = None,
    until: Annotated[str | None, typer.Option("--until", help="ISO 8601 upper bound.")] = None,
    limit: Annotated[int, typer.Option("--limit", help="Maximum rows (≤ 10000).")] = 1000,
    json_output: JsonOption = False,
    repo: RepoOption = None,
) -> None:
    """Print ledger events matching every given filter, oldest first."""
    since_at = _parse_time(since, "--since")
    until_at = _parse_time(until, "--until")
    db = _open(ctx, repo)
    try:
        events = asyncio.run(
            _ledger_manager(db).query(
                kinds=kind,
                work_item_id=item,
                run_id=run,
                phase_id=phase,
                since=since_at,
                until=until_at,
                limit=limit,
            )
        )
    finally:
        db.close()
    _print(events, as_json=_wants_json(ctx, json_output))


@ledger_app.command("tail")
def tail(
    ctx: typer.Context,
    *,
    since: Annotated[int, typer.Option("--since", help="Print events after this seq.")] = 0,
    follow: Annotated[bool, typer.Option("--follow", help="Keep printing new events.")] = False,
    json_output: JsonOption = False,
    repo: RepoOption = None,
) -> None:
    """Print events after ``--since``; with ``--follow`` keep streaming until interrupted."""
    as_json = _wants_json(ctx, json_output)
    db = _open(ctx, repo)
    try:
        if follow:
            _follow(db, since, as_json=as_json)
        else:
            _print(asyncio.run(_events_after(LedgerRepository(db), since)), as_json=as_json)
    finally:
        db.close()


async def _events_after(repo: LedgerRepository, seq: int) -> list[LedgerEvent]:
    events: list[LedgerEvent] = []
    while batch := await repo.after(seq):
        events.extend(batch)
        seq = batch[-1].seq or seq
    return events


def _follow(db: Database, since: int, *, as_json: bool) -> None:
    """Stream one line per event (JSON lines with ``--json``) until Ctrl+C."""

    async def stream() -> None:
        async for event in _ledger_manager(db).tail(since):
            if as_json:
                typer.echo(event.model_dump_json())
            else:
                typer.echo(_COLUMN_GAP.join("" if v is None else str(v) for v in _row(event)))

    try:
        asyncio.run(stream())
    except KeyboardInterrupt:
        return
