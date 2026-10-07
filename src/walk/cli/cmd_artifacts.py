"""``walk artifacts list|approve|verify``: the approved artifact registry (§33; E02-S12).

The commands run in-process on the project database (they never create it). Approving as the
user copies the payload files into `.ai/approved/APR-NNNN/` through the memory manager, the
only writer of `.ai/`. Exit codes: 0 ok, 1 error, 2 drift found by ``verify``.
"""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Final

import typer

from walk.cli.composition import open_database, open_memory
from walk.cli.output import exit_with, render_json, render_table
from walk.common.errors import ConfigError, WalkError
from walk.common.models import Actor
from walk.common.roles import AgentRole
from walk.memory import (
    ApprovalStatus,
    ApprovedArtifact,
    ApprovedArtifactDrift,
    ApprovedArtifactKind,
    ApprovedArtifactRepository,
)
from walk.persistence import Database
from walk.workflow import ProjectRepository

artifacts_app = typer.Typer(name="artifacts", help="Approved artifacts (§33).")

_DB_RELATIVE_PATH: Final = Path(".ai") / "kernel.db"
_EXIT_DRIFT: Final = 2
_SHA_SHOWN: Final = 12
_PLACEHOLDER_ID: Final = "APR-0000"
_HEADERS: Final = ("id", "kind", "status", "version", "scope", "title", "sha")

RepoOption = Annotated[
    Path | None,
    typer.Option(
        "--repo", help="Game repository root (overrides the global --repo).", file_okay=False
    ),
]
JsonOption = Annotated[bool, typer.Option("--json", help="Emit JSON (same as the global --json).")]


@artifacts_app.command("list")
def artifacts_list(
    ctx: typer.Context, *, json_output: JsonOption = False, repo: RepoOption = None
) -> None:
    """List approved artifacts by id (every status)."""
    db = _open(_repo_root(ctx, repo), writable=False)
    try:
        rows = asyncio.run(ApprovedArtifactRepository(db).list())
    finally:
        db.close()
    if json_output or bool(_global(ctx, "json")):
        typer.echo(render_json([row.model_dump(mode="json") for row in rows]))
        return
    typer.echo(render_table(_HEADERS, (_row(artifact) for artifact in rows)))


@artifacts_app.command("approve")
def artifacts_approve(
    ctx: typer.Context,
    paths: Annotated[
        list[Path],
        typer.Argument(metavar="PATH...", help="Payload files (absolute or repo-relative)."),
    ],
    *,
    kind: Annotated[ApprovedArtifactKind, typer.Option("--kind", help="Artifact kind.")],
    title: Annotated[str, typer.Option("--title", help="Human title.")],
    scope: Annotated[str, typer.Option("--scope", help="project, PHASE-id or FEAT-id.")],
    supersedes: Annotated[
        str | None, typer.Option("--supersedes", help="APR id this version replaces.")
    ] = None,
    repo: RepoOption = None,
) -> None:
    """Approve PATH... as the user: copy, hash and register them as one artifact."""
    root = _repo_root(ctx, repo)
    db = _open(root, writable=True)
    actor = Actor(role=AgentRole.USER)
    try:
        draft = ApprovedArtifact(
            id=_PLACEHOLDER_ID,
            kind=kind,
            title=title,
            status=ApprovalStatus.DRAFT,
            scope=scope,
            version=1,
            approved_by=actor,
            approved_at=datetime.now(tz=UTC),
            related_requirements=[],
            payload_paths=[str(path) for path in paths],
            content_sha256="",
            supersedes=supersedes,
        )
        memory = open_memory(db, root, project_key=_project_key(db))
        approved = asyncio.run(memory.approve_artifact(draft, actor=actor))
    except WalkError as exc:
        exit_with(exc)
    except ValueError as exc:  # pydantic: e.g. a malformed --supersedes id
        exit_with(ConfigError(str(exc), detail={"supersedes": supersedes}))
    finally:
        db.close()
    typer.echo(f"{approved.id} approved (sha {approved.content_sha256[:_SHA_SHOWN]})")


@artifacts_app.command("verify")
def artifacts_verify(ctx: typer.Context, *, repo: RepoOption = None) -> None:
    """Re-hash every APPROVED artifact; exit 2 listing the drifted ones (marked INVALID)."""
    root = _repo_root(ctx, repo)
    db = _open(root, writable=True)
    try:
        memory = open_memory(db, root, project_key=_project_key(db))
        drifted = asyncio.run(memory.verify_approved_artifacts())
    except WalkError as exc:
        exit_with(exc)
    finally:
        db.close()
    if not drifted:
        typer.echo("ok")
        return
    error = ApprovedArtifactDrift(
        f"approved artifact drift: {', '.join(drifted)}", detail={"ids": drifted}
    )
    typer.echo(error.message, err=True)
    raise typer.Exit(code=_EXIT_DRIFT)


def _row(artifact: ApprovedArtifact) -> list[object]:
    return [
        artifact.id,
        artifact.kind.value,
        artifact.status.value,
        artifact.version,
        artifact.scope,
        artifact.title,
        artifact.content_sha256[:_SHA_SHOWN],
    ]


def _open(root: Path, *, writable: bool) -> Database:
    try:
        if not (root / _DB_RELATIVE_PATH).is_file():
            msg = f"database does not exist: {root / _DB_RELATIVE_PATH}"
            raise ConfigError(msg, detail={"repo": str(root)})
        return open_database(root, read_only=not writable)
    except WalkError as exc:
        exit_with(exc)


def _project_key(db: Database) -> str:
    projects = asyncio.run(ProjectRepository(db).list_where())
    if len(projects) != 1:
        msg = "the database must hold exactly one project; run 'walk bootstrap'"
        raise ConfigError(msg, detail={"projects": len(projects)})
    return projects[0].key


def _global(ctx: typer.Context, key: str) -> object:
    obj = ctx.find_root().obj
    return obj.get(key) if isinstance(obj, dict) else None


def _repo_root(ctx: typer.Context, repo: Path | None) -> Path:
    root = repo if repo is not None else _global(ctx, "repo")
    return root if isinstance(root, Path) else Path()
