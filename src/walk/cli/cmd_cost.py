"""``walk cost``: cost per work item, phase or project (§85; INTERFACES §6)."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from walk.budgets import CostCategory
from walk.cli.composition import open_costs, open_database
from walk.cli.output import exit_with, render_json, render_table
from walk.common.errors import ConfigError, WalkError
from walk.persistence import Database
from walk.workflow import ProjectRepository

cost_app = typer.Typer(name="cost", help="Cost roll-ups (§85).")

_HEADERS = ("category", "usd")
_TOTAL = "total"
_USD_DIGITS = 2

RepoOption = Annotated[
    Path | None,
    typer.Option(
        "--repo", help="Game repository root (overrides the global --repo).", file_okay=False
    ),
]


def _global(ctx: typer.Context, key: str) -> object:
    obj = ctx.find_root().obj
    return obj.get(key) if isinstance(obj, dict) else None


def _open(ctx: typer.Context, repo: Path | None) -> Database:
    root = repo if repo is not None else _global(ctx, "repo")
    try:
        return open_database(root if isinstance(root, Path) else Path(), read_only=True)
    except WalkError as exc:
        exit_with(exc)


@cost_app.callback(invoke_without_command=True)
def cost(
    ctx: typer.Context,
    *,
    item: Annotated[
        str | None, typer.Option("--item", help="Work item id (with descendants).")
    ] = None,
    phase: Annotated[str | None, typer.Option("--phase", help="Phase id.")] = None,
    project: Annotated[bool, typer.Option("--project", help="The whole project.")] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit JSON (same as the global --json).")
    ] = False,
    repo: RepoOption = None,
) -> None:
    """Print USD per cost category and the total for exactly one subject."""
    if sum((item is not None, phase is not None, project)) != 1:
        exit_with(ConfigError("walk cost needs exactly one of --item, --phase, --project"))
    db = _open(ctx, repo)
    try:
        totals = asyncio.run(_totals(db, item=item, phase=phase))
    except WalkError as exc:
        exit_with(exc)
    finally:
        db.close()
    total = round(sum(totals.values()), _USD_DIGITS)
    if json_output or bool(_global(ctx, "json")):
        categories = {category.value: usd for category, usd in totals.items()}
        typer.echo(render_json({"categories": categories, "total_usd": total}))
        return
    rows = [[category.value, f"{usd:.2f}"] for category, usd in totals.items()]
    rows.append([_TOTAL, f"{total:.2f}"])
    typer.echo(render_table(_HEADERS, rows))


async def _totals(
    db: Database, *, item: str | None, phase: str | None
) -> dict[CostCategory, float]:
    costs = open_costs(db)
    if item is not None:
        return await costs.cost_of(work_item_id=item)
    if phase is not None:
        return await costs.cost_of(phase_id=phase)
    project = await ProjectRepository(db).single()
    return await costs.cost_of(project_key=project.key)
