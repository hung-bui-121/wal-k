"""``walk skills list|sync|check-drift``: canonical skills and their projections.

E02-S06 (list, sync) and E02-S07 (check-drift).

They run in-process and need no daemon (ADR-0007).
"""

import asyncio
import json
from pathlib import Path
from typing import Annotated, Final

import typer

from walk.cli.composition import PROJECTIONS_DIR, open_skill_registry, skill_projectors
from walk.cli.output import exit_with, render_table
from walk.common.errors import WalkError
from walk.skills import DefaultSkillRegistry, DriftReport, Skill, SkillProjector
from walk.skills.lockfile import ProjectionLock

skills_app = typer.Typer(name="skills", help="Canonical skills and provider projections.")

_EXIT_DRIFT: Final = 1

RepoOption = Annotated[
    Path | None, typer.Option("--repo", help="Game repository root.", file_okay=False)
]
JsonOption = Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")]
WorktreeOption = Annotated[
    Path | None,
    typer.Option(
        "--worktree",
        help="Folder holding every provider's projection (default .walk/projections/<provider>).",
        file_okay=False,
    ),
]


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
    worktree: WorktreeOption = None,
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
        target = _target(repo, worktree, projector.provider)
        target.mkdir(parents=True, exist_ok=True)
        await registry.project_all([projector], str(target), skills)
    return len(skills), len(projectors)


@skills_app.command("check-drift")
def skills_check_drift(
    ctx: typer.Context,
    *,
    strict: Annotated[
        bool, typer.Option("--strict", help="Exit 1 on drift instead of regenerating.")
    ] = False,
    worktree: WorktreeOption = None,
    repo: RepoOption = None,
) -> None:
    """Compare projections with the lock; regenerate drift (or exit 1 with ``--strict``)."""
    path, _ = _options(ctx, repo, json_output=False)
    try:
        registry, db = open_skill_registry(path)
        try:
            drifted = asyncio.run(_drifted(registry, path, worktree))
            if not drifted:
                typer.echo("ok")
                return
            typer.echo(_render_drift(registry, path, [report for _, _, report in drifted]))
            if strict:
                raise typer.Exit(code=_EXIT_DRIFT)
            count = asyncio.run(_regenerate(registry, drifted))
        finally:
            db.close()
    except WalkError as exc:
        exit_with(exc)
    typer.echo(f"regenerated {count} projections")


async def _drifted(
    registry: DefaultSkillRegistry, repo: Path, worktree: Path | None
) -> list[tuple[SkillProjector, Path, DriftReport]]:
    found: list[tuple[SkillProjector, Path, DriftReport]] = []
    for projector in skill_projectors():
        target = _target(repo, worktree, projector.provider)
        report = await registry.check_drift([projector], str(target))
        if not report.ok:
            found.append((projector, target, report))
    return found


async def _regenerate(
    registry: DefaultSkillRegistry, drifted: list[tuple[SkillProjector, Path, DriftReport]]
) -> int:
    count = 0
    for projector, target, report in drifted:
        target.mkdir(parents=True, exist_ok=True)
        await registry.regenerate([projector], str(target), report)
        count += len(report.missing) + len(report.modified) + len(report.orphaned)
    return count


def _render_drift(registry: DefaultSkillRegistry, repo: Path, reports: list[DriftReport]) -> str:
    """``missing:``/``modified:``/``orphaned:`` lines; a modification names its cause."""
    canonical = {skill.name: skill.content_sha256 for skill in registry.load()}
    lock = ProjectionLock.load(repo / ".ai").projections
    stale = {e.skill for e in lock if canonical.get(e.skill) not in {None, e.generated_from_sha256}}
    missing = sorted({n for report in reports for n in report.missing})
    modified = sorted({n for report in reports for n in report.modified})
    orphaned = sorted({n for report in reports for n in report.orphaned})
    lines = [
        *(f"missing: {name}" for name in missing),
        *(
            f"modified: {name} ({'canonical changed' if name in stale else 'projection edited'})"
            for name in modified
        ),
        *(f"orphaned: {name}" for name in orphaned),
    ]
    return "\n".join(lines)


def _target(repo: Path, worktree: Path | None, provider: str) -> Path:
    return (worktree if worktree is not None else repo / PROJECTIONS_DIR / provider).resolve()


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
