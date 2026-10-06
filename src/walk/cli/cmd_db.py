"""``walk db`` commands: schema migration and backup (INTERFACES §6)."""

from pathlib import Path
from typing import Annotated

import typer

from walk.cli.composition import open_database
from walk.common.errors import ConfigError
from walk.persistence import MigrationRunner

db_app = typer.Typer(name="db", help="Project database maintenance.", no_args_is_help=True)

_EXIT_CONFIG_ERROR = 1  # INTERFACES §6: validation/config error

RepoOption = Annotated[
    Path | None,
    typer.Option(
        "--repo", help="Game repository root (overrides the global --repo).", file_okay=False
    ),
]


def _repo(ctx: typer.Context, repo: Path | None) -> Path:
    if repo is not None:
        return repo
    obj = ctx.find_root().obj
    return obj["repo"] if isinstance(obj, dict) and "repo" in obj else Path()


def _fail(error: ConfigError) -> typer.Exit:
    typer.echo(f"error: {error.message}", err=True)
    return typer.Exit(code=_EXIT_CONFIG_ERROR)


@db_app.command("migrate")
def migrate(ctx: typer.Context, repo: RepoOption = None) -> None:
    """Create the project database if needed and apply pending migrations."""
    try:
        db = open_database(_repo(ctx, repo))
    except ConfigError as exc:
        raise _fail(exc) from exc
    try:
        runner = MigrationRunner(db, "project")
        applied = runner.apply_pending()
        labels = {m.version: f"{m.version:04d}_{m.name}" for m in runner.discover()}
    except ConfigError as exc:
        raise _fail(exc) from exc
    finally:
        db.close()
    if applied:
        typer.echo("applied: " + ", ".join(labels[v] for v in applied))
    else:
        typer.echo("up to date")


@db_app.command("backup")
def backup(
    ctx: typer.Context,
    path: Annotated[Path, typer.Argument(help="Target file for the copy.", dir_okay=False)],
    repo: RepoOption = None,
) -> None:
    """Copy the project database to PATH (SQLite online backup)."""
    try:
        db = open_database(_repo(ctx, repo), read_only=True)
    except ConfigError as exc:
        raise _fail(exc) from exc
    try:
        db.backup_to(path)
    except ConfigError as exc:
        raise _fail(exc) from exc
    finally:
        db.close()
    typer.echo(f"backup written: {path}")
