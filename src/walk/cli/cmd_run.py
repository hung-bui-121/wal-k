"""``walk run``: start the kernel for the repository (INTERFACES §6; E01-S30)."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from walk.cli.composition import KernelSettings
from walk.cli.daemon import run_daemon
from walk.orchestrator import DEFAULT_MAX_PARALLEL_AGENTS, DEFAULT_POLL_INTERVAL_S


def run(
    ctx: typer.Context,
    *,
    once: Annotated[bool, typer.Option("--once", help="Run one scheduling tick and exit.")] = False,
    max_parallel: Annotated[
        int, typer.Option("--max-parallel", help="Runs executing at once.")
    ] = DEFAULT_MAX_PARALLEL_AGENTS,
    poll_interval: Annotated[
        float, typer.Option("--poll-interval", help="Seconds between ticks without a wake-up.")
    ] = DEFAULT_POLL_INTERVAL_S,
    skip_preflight: Annotated[
        bool, typer.Option("--skip-preflight", help="Skip the environment preflight.")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit JSON output.")] = False,
    repo: Annotated[
        Path | None, typer.Option("--repo", help="Game repository root.", file_okay=False)
    ] = None,
) -> None:
    """Acquire the kernel lock, recover, then run one tick (--once) or the daemon loop."""
    root_options = ctx.find_root().obj if isinstance(ctx.find_root().obj, dict) else {}
    root = repo if repo is not None else root_options.get("repo", Path())
    settings = KernelSettings(
        repo_path=root if isinstance(root, Path) else Path(),
        max_parallel=max_parallel,
        poll_interval_s=poll_interval,
        skip_preflight=skip_preflight,
        json_output=json_output or bool(root_options.get("json")),
    )
    code = asyncio.run(run_daemon(settings, once=once))
    raise typer.Exit(code=code)
