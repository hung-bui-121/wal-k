"""``walk skills list|sync``: canonical skills and their provider projections (E02-S06).

Both run in-process and need no daemon (ADR-0007).
"""

import asyncio
import json
from pathlib import Path
from typing import Annotated, Final

import typer

from walk.cli.composition import open_skill_registry, skill_projectors
from walk.cli.output import exit_with, render_table
from walk.common.errors import WalkError
from walk.skills import DefaultSkillRegistry, Skill
from walk.skills.lockfile import ProjectionLock

skills_app = typer.Typer(name="skills", help="Canonical skills and provider projections.")

_PROJECTIONS_DIR: Final = Path(".walk") / "projections"

RepoOption = Annotated[
    Path | None, typer.Option("--repo", help="Game repository root.", file_okay=False)
]
JsonOption = Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")]


@skills_app.command("list")
def skills_list(
    ctx: typer.Context, json_output: JsonOption = False, repo: RepoOption = None
) -> None:
    """List every skill: name, version, scope, source file and default roles."""
    path, as_json = _options(ctx, repo, json_output=json_output)
    try:
        registry, db = open_skill_registry(path)
        try:
            skills = sorted(registry.load(), key=lambda skill: skill.name)
        finally:
            db.close()
    except WalkError as exc:
        exit_with(exc)
    if as_json:
        typer.echo(json.dumps([_summary(skill) for skill in skills], indent=2))
        return
    rows = [
        (
            s.name,
            s.version,
            s.scope.value,
            s.source_path,
            ",".join(r.value for r in s.applies_to_roles),
        )
        for s in skills
    ]
    typer.echo(render_table(("name", "version", "scope", "source", "roles"), rows))


@skills_app.command("sync")
def skills_sync(
    ctx: typer.Context,
    worktree: Annotated[
        Path | None,
        typer.Option(
            "--worktree",
            help="Folder to project every provider into (default .walk/projections/<provider>).",
            file_okay=False,
        ),
    ] = None,
    json_output: JsonOption = False,
    repo: RepoOption = None,
) -> None:
    """Project all skills for every kernel provider and rewrite the projection lock."""
    path, as_json = _options(ctx, repo, json_output=json_output)
    try:
        registry, db = open_skill_registry(path)
        try:
            count, providers = asyncio.run(_sync(registry, path, worktree))
        finally:
            db.close()
    except WalkError as exc:
        exit_with(exc)
    if as_json:
        typer.echo(ProjectionLock.load(path / ".ai").model_dump_json(indent=2))
        return
    typer.echo(f"projected {count} skills for {providers} providers")


async def _sync(
    registry: DefaultSkillRegistry, repo: Path, worktree: Path | None
) -> tuple[int, int]:
    skills = registry.load()
    projectors = skill_projectors()
    for projector in projectors:
        target = worktree if worktree is not None else repo / _PROJECTIONS_DIR / projector.provider
        target.mkdir(parents=True, exist_ok=True)
        await registry.project_all([projector], str(target.resolve()), skills)
    return len(skills), len(projectors)


def _options(ctx: typer.Context, repo: Path | None, *, json_output: bool) -> tuple[Path, bool]:
    options = ctx.find_root().obj if isinstance(ctx.find_root().obj, dict) else {}
    root = repo if repo is not None else options.get("repo", Path())
    return (root if isinstance(root, Path) else Path()), json_output or bool(options.get("json"))


def _summary(skill: Skill) -> dict[str, object]:
    return {
        "name": skill.name,
        "version": skill.version,
        "scope": skill.scope.value,
        "source": skill.source_path,
        "roles": [role.value for role in skill.applies_to_roles],
    }
