"""``walk policy set-model|set-autonomy`` and the shared §93 override runner (E02-S13).

Every override goes through the daemon when one holds the kernel lock (`CommandClient`), else
it runs in-process under the lock; the orchestrator writes its ``USER_OVERRIDE``. Exit codes:
0 ok, 1 error, 2 guard rejected, 3 daemon not responding (or required and not running).
"""

import asyncio
from pathlib import Path
from typing import Annotated, Final

import typer

from walk.cli.composition import KernelHandle
from walk.cli.ipc import daemon_running, run_mutation
from walk.cli.output import exit_with, render_json
from walk.common.errors import Timeout, WalkError
from walk.common.models import JsonDict
from walk.common.roles import AgentRole
from walk.orchestrator.commands import override_handlers

policy_app = typer.Typer(name="policy", help="Runtime policy overrides (§93).")

_EXIT_NO_DAEMON: Final = 3  # INTERFACES §6: daemon not responding / required

RepoOption = Annotated[
    Path | None,
    typer.Option(
        "--repo", help="Game repository root (overrides the global --repo).", file_okay=False
    ),
]
JsonOption = Annotated[bool, typer.Option("--json", help="Emit JSON (same as the global --json).")]


@policy_app.command("set-model")
def policy_set_model(
    ctx: typer.Context,
    role: Annotated[AgentRole, typer.Argument(metavar="ROLE", help="Role to change.")],
    *,
    preferred: Annotated[
        list[str], typer.Option("--preferred", help="Preferred model or family (repeatable).")
    ],
    fallback: Annotated[
        list[str] | None, typer.Option("--fallback", help="Fallback model or family (repeatable).")
    ] = None,
    json_output: JsonOption = False,
    repo: RepoOption = None,
) -> None:
    """Set ROLE's model policy in `.ai/agents/policies.yaml` (next scheduled run uses it)."""
    args: JsonDict = {"role": role.value, "preferred": preferred, "fallback": fallback or []}
    result = run_override(ctx, repo, "policy.set_model", args)
    if wants_json(ctx, json_output):
        typer.echo(render_json(result))
        return
    typer.echo(
        f"{role.value} model policy: preferred {', '.join(preferred)}; "
        f"fallback {', '.join(fallback or []) or '-'}"
    )


@policy_app.command("set-autonomy")
def policy_set_autonomy(
    ctx: typer.Context,
    level: Annotated[int, typer.Argument(metavar="LEVEL", min=0, max=3, help="0-3 (§51).")],
    *,
    json_output: JsonOption = False,
    repo: RepoOption = None,
) -> None:
    """Set the project's highest autonomy level agents resolve without the user."""
    result = run_override(ctx, repo, "policy.set_autonomy", {"level": level})
    if wants_json(ctx, json_output):
        typer.echo(render_json(result))
        return
    typer.echo(f"autonomy level {level}")


def run_override(
    ctx: typer.Context,
    repo: Path | None,
    name: str,
    args: JsonDict,
    *,
    daemon_required: bool = False,
) -> JsonDict:
    """Run override ``name`` through the daemon or in-process; exit on failure."""
    root = repo_root(ctx, repo)
    if daemon_required and not daemon_running(root):
        typer.echo(f"error: {name} needs a running kernel daemon ('walk run')", err=True)
        raise typer.Exit(code=_EXIT_NO_DAEMON)

    async def in_process(handle: KernelHandle) -> JsonDict:
        return await override_handlers(handle.orchestrator)[name](args)

    try:
        result = asyncio.run(run_mutation(root, name, args, in_process))
    except Timeout:
        typer.echo("error: daemon not responding", err=True)
        raise typer.Exit(code=_EXIT_NO_DAEMON) from None
    except WalkError as exc:
        exit_with(exc)
    if not result.ok:
        typer.echo(f"error: {result.result.get('error')}", err=True)
        raise typer.Exit(code=result.exit_code)
    return result.result


def repo_root(ctx: typer.Context, repo: Path | None) -> Path:
    """``--repo``, else the global ``--repo``, else the current directory."""
    root = repo if repo is not None else _global(ctx, "repo")
    return root if isinstance(root, Path) else Path()


def wants_json(ctx: typer.Context, flag: bool) -> bool:
    """``--json`` on the command or globally."""
    return flag or bool(_global(ctx, "json"))


def _global(ctx: typer.Context, key: str) -> object:
    obj = ctx.find_root().obj
    return obj.get(key) if isinstance(obj, dict) else None
