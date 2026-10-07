"""``walk approve``, ``walk deny``, ``walk approvals``: the approval queue (§92, §93; E02-S11).

Decisions run in the daemon when one holds the kernel lock (commands ``approve``/``deny``),
else in-process under the lock; the daemon's permission manager then wakes the waiting run.
Listing reads the database directly. Exit codes: 0 ok, 1 unknown id or other error, 2 already
decided, 3 when the daemon does not answer.
"""

import asyncio
from pathlib import Path
from typing import Annotated, Final

import typer

from walk.cli.composition import KernelHandle, open_database
from walk.cli.daemon import decide_in_kernel
from walk.cli.ipc import run_mutation
from walk.cli.output import exit_with, render_json, render_table
from walk.common.errors import ConfigError, Timeout, WalkError
from walk.common.models import JsonDict
from walk.permissions import ApprovalRepository, ApprovalRequest

_DB_RELATIVE_PATH: Final = Path(".ai") / "kernel.db"
_EXIT_NO_DAEMON: Final = 3  # INTERFACES §6: daemon not responding
_HEADERS: Final = ("id", "kind", "tool", "state", "approver", "run", "requested_at")

RepoOption = Annotated[
    Path | None,
    typer.Option(
        "--repo", help="Game repository root (overrides the global --repo).", file_okay=False
    ),
]
JsonOption = Annotated[bool, typer.Option("--json", help="Emit JSON (same as the global --json).")]
NoteOption = Annotated[str | None, typer.Option("--note", help="Note stored with the decision.")]
IdArgument = Annotated[str, typer.Argument(metavar="APV_ID", help="Approval request id.")]


def approve(
    ctx: typer.Context,
    approval_id: IdArgument,
    *,
    note: NoteOption = None,
    json_output: JsonOption = False,
    repo: RepoOption = None,
) -> None:
    """Approve a PENDING approval request; the waiting run continues with the action."""
    _decide(ctx, approval_id, approve=True, note=note, json_output=json_output, repo=repo)


def deny(
    ctx: typer.Context,
    approval_id: IdArgument,
    *,
    note: NoteOption = None,
    json_output: JsonOption = False,
    repo: RepoOption = None,
) -> None:
    """Deny a PENDING approval request; the waiting run gets the action denied."""
    _decide(ctx, approval_id, approve=False, note=note, json_output=json_output, repo=repo)


def approvals(
    ctx: typer.Context,
    *,
    pending: Annotated[bool, typer.Option("--pending", help="Only PENDING requests.")] = False,
    json_output: JsonOption = False,
    repo: RepoOption = None,
) -> None:
    """List approval requests, oldest first."""
    root = _repo_root(ctx, repo)
    try:
        _require_database(root)
        db = open_database(root, read_only=True)
    except WalkError as exc:
        exit_with(exc)
    try:
        repository = ApprovalRepository(db)
        rows = asyncio.run(repository.list_pending() if pending else repository.all())
    finally:
        db.close()
    if _wants_json(ctx, json_output):
        typer.echo(render_json([row.model_dump(mode="json") for row in rows]))
        return
    typer.echo(render_table(_HEADERS, (_row(approval) for approval in rows)))


def _decide(
    ctx: typer.Context,
    approval_id: str,
    *,
    approve: bool,
    note: str | None,
    json_output: bool,
    repo: Path | None,
) -> None:
    root = _repo_root(ctx, repo)
    args: JsonDict = {"approval_id": approval_id, "approve": approve, "note": note}

    async def in_process(handle: KernelHandle) -> JsonDict:
        return await decide_in_kernel(handle, args)

    try:
        _require_database(root)
        result = asyncio.run(run_mutation(root, "approve" if approve else "deny", args, in_process))
    except Timeout:
        typer.echo("error: daemon not responding", err=True)
        raise typer.Exit(code=_EXIT_NO_DAEMON) from None
    except WalkError as exc:
        exit_with(exc)
    if not result.ok:
        typer.echo(f"error: {result.result.get('error')}", err=True)
        raise typer.Exit(code=result.exit_code)
    decided = ApprovalRequest.model_validate(result.result["approval"])
    if _wants_json(ctx, json_output):
        typer.echo(render_json(decided.model_dump(mode="json")))
    else:
        typer.echo(f"{decided.id} {decided.state.value}")


def _row(approval: ApprovalRequest) -> list[object]:
    tool = approval.payload.get("tool")
    return [
        approval.id,
        approval.kind,
        tool if isinstance(tool, str) else None,
        approval.state.value,
        approval.approver.value,
        approval.run_id,
        approval.requested_at.isoformat(),
    ]


def _require_database(root: Path) -> None:
    """The project database must exist; the CLI never creates it here."""
    if not (root / _DB_RELATIVE_PATH).is_file():
        msg = f"database does not exist: {root / _DB_RELATIVE_PATH}"
        raise ConfigError(msg, detail={"repo": str(root)})


def _global(ctx: typer.Context, key: str) -> object:
    obj = ctx.find_root().obj
    return obj.get(key) if isinstance(obj, dict) else None


def _repo_root(ctx: typer.Context, repo: Path | None) -> Path:
    root = repo if repo is not None else _global(ctx, "repo")
    return root if isinstance(root, Path) else Path()


def _wants_json(ctx: typer.Context, flag: bool) -> bool:
    return flag or bool(_global(ctx, "json"))
