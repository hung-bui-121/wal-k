"""Root ``walk`` command (INTERFACES §6)."""

from pathlib import Path
from typing import Annotated

import typer

from walk import __version__
from walk.cli.cmd_cost import cost_app
from walk.cli.cmd_db import db_app
from walk.cli.cmd_ledger import ledger_app
from walk.cli.cmd_memory import memory_app
from walk.cli.cmd_phase import phase_app
from walk.cli.cmd_run import run
from walk.cli.cmd_status import status
from walk.cli.cmd_work import work_app

app = typer.Typer(
    name="walk",
    help="WAL-K: Workflow Agent Layers Kernel.",
    add_completion=False,
    invoke_without_command=True,
)
app.add_typer(db_app)
app.add_typer(cost_app)
app.add_typer(ledger_app)
app.add_typer(memory_app)
app.add_typer(phase_app)
app.add_typer(work_app)
app.command("run")(run)
app.command("status")(status)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"walk {__version__}")
        raise typer.Exit


@app.callback()
def root(
    ctx: typer.Context,
    repo: Annotated[
        Path,
        typer.Option("--repo", help="Game repository root.", file_okay=False),
    ] = Path(),
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON output."),
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", help="Verbose logging.")] = False,
    version: Annotated[  # noqa: ARG001 - handled by the eager callback
        bool,
        typer.Option(
            "--version",
            help="Print the kernel version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Store global options in the context; print help when no command is given."""
    ctx.obj = {"repo": repo, "json": json_output, "verbose": verbose}
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit


def main() -> None:
    """Console-script entry point."""
    app()
