"""``walk memory``: project memory maintenance (§42; INTERFACES §6)."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from walk.cli.composition import open_database, open_memory
from walk.cli.output import exit_with, render_json
from walk.common.errors import WalkError
from walk.persistence import Database
from walk.workflow import ProjectRepository

memory_app = typer.Typer(name="memory", help="Project memory under .ai/ (§34-§42).")

RepoOption = Annotated[
    Path | None,
    typer.Option(
        "--repo", help="Game repository root (overrides the global --repo).", file_okay=False
    ),
]


def _global(ctx: typer.Context, key: str) -> object:
    obj = ctx.find_root().obj
    return obj.get(key) if isinstance(obj, dict) else None


@memory_app.command("index")
def index(
    ctx: typer.Context,
    *,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit JSON (same as the global --json).")
    ] = False,
    repo: RepoOption = None,
) -> None:
    """Rebuild memory_index from the documents under .ai/ and print how many were indexed."""
    chosen = repo if repo is not None else _global(ctx, "repo")
    root = chosen if isinstance(chosen, Path) else Path()
    try:
        # The database must already exist (`walk db migrate`); probe read-only, then write.
        open_database(root, read_only=True).close()
        db = open_database(root)
    except WalkError as exc:
        exit_with(exc)
    try:
        count = asyncio.run(_rebuild(db, root))
    except WalkError as exc:
        exit_with(exc)
    finally:
        db.close()
    if json_output or bool(_global(ctx, "json")):
        typer.echo(render_json({"indexed": count}))
        return
    typer.echo(f"indexed {count} documents")


async def _rebuild(db: Database, root: Path) -> int:
    project = await ProjectRepository(db).single()
    return await open_memory(db, root, project_key=project.key).rebuild_index()
