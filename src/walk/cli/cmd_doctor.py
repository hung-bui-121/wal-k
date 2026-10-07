"""``walk doctor``: the §26 environment preflight with a readable report (E02-S02).

It runs in-process, needs no daemon and opens no database: the preflight reads only the
environment and `.ai/project/*.yaml`, and replaces `environment.yaml` atomically, so it does
not contend with a running kernel's exclusive lock.
"""

import asyncio
from pathlib import Path
from typing import Annotated, Final

import typer

from walk.cli.composition import open_database, open_integrations, skill_drift_reports
from walk.cli.output import exit_with, render_table
from walk.common.clock import SystemClock
from walk.common.errors import ConfigError, WalkError
from walk.integrations import (
    ComponentStatus,
    EnvironmentManifest,
    ManifestStore,
    ReadinessState,
)
from walk.integrations.preflight import MISSING_COMPONENTS, REQUIRED_DEFAULT
from walk.memory import (
    APPROVED_DIR,
    ApprovalStatus,
    ApprovedArtifact,
    ApprovedArtifactRepository,
    hash_payload,
)

_EXIT_PREFLIGHT: Final = 4  # INTERFACES §6: preflight failed
_DB_RELATIVE_PATH: Final = Path(".ai") / "kernel.db"


def doctor(
    ctx: typer.Context,
    *,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit the EnvironmentManifest as JSON.")
    ] = False,
    repo: Annotated[
        Path | None, typer.Option("--repo", help="Game repository root.", file_okay=False)
    ] = None,
) -> None:
    """Check git, Unity, providers, credentials and skills; write `.ai/project/environment.yaml`.

    Exit 0 when every required component is present, 4 when one is missing, 1 on any other
    kernel error.
    """
    options = ctx.find_root().obj if isinstance(ctx.find_root().obj, dict) else {}
    root = repo if repo is not None else options.get("repo", Path())
    as_json = json_output or bool(options.get("json"))
    path = root if isinstance(root, Path) else Path()
    try:
        manager = open_integrations(path)
        manifest = asyncio.run(manager.preflight(list(REQUIRED_DEFAULT)))
    except ConfigError as exc:
        if MISSING_COMPONENTS not in exc.detail:
            exit_with(exc)
        stored = ManifestStore(path / ".ai", SystemClock()).read()  # written before raising
        if stored is not None:
            typer.echo(_render(stored, as_json=as_json))
        typer.echo(f"error: {exc.message}", err=True)
        raise typer.Exit(code=_EXIT_PREFLIGHT) from exc
    except WalkError as exc:
        exit_with(exc)
    typer.echo(_render(manifest, as_json=as_json))
    if not as_json:
        typer.echo(_skills_section(path))
        typer.echo(_approved_section(path))


def _render(manifest: EnvironmentManifest, *, as_json: bool) -> str:
    if as_json:
        return manifest.model_dump_json(indent=2)
    rows: list[tuple[str, str, str, str]] = [_row("unity", manifest.unity)]
    for section, statuses in (
        ("unity_packages", manifest.unity_packages),
        ("tools", manifest.tools),
        ("providers", manifest.providers),
    ):
        rows += [_row(f"{section}.{key}", status) for key, status in statuses.items()]
    rows.append(_row("work_provider", manifest.work_provider))
    for section, states in (
        ("credentials", manifest.credentials),
        ("required_skills", manifest.required_skills),
        ("build_targets", manifest.build_targets),
    ):
        rows += [(f"{section}.{key}", state.value, "", "") for key, state in states.items()]
    lines = [render_table(("component", "state", "version", "detail"), rows)]
    if manifest.drift_from is not None and manifest.drift_items:
        lines += ["", f"drift from {manifest.drift_from}:"]
        lines += [f"  {item}" for item in manifest.drift_items]
    return "\n".join(lines)


def _skills_section(repo: Path) -> str:
    """``skills`` lines: ``ok`` or counts per drift category; never changes the exit code."""
    try:
        reports = skill_drift_reports(repo)
    except WalkError as exc:
        return f"\nskills: error: {exc.message}"
    lines = ["", "skills:"]
    for provider, report in reports.items():
        counts = [
            f"{label} {len(names)}"
            for label, names in (
                ("missing", report.missing),
                ("modified", report.modified),
                ("orphaned", report.orphaned),
            )
            if names
        ]
        lines.append(f"  {provider}: {', '.join(counts) or 'ok'}")
    return "\n".join(lines)


def _approved_section(repo: Path) -> str:
    """``approved`` line: ``ok`` or the drifted artifact ids (E02-S12); never changes the exit.

    Read-only: the hashes are recomputed against a read-only database connection; marking the
    drift INVALID is left to the kernel start and `walk artifacts verify`.
    """
    if not (repo / _DB_RELATIVE_PATH).is_file():
        return "\napproved: no database"
    try:
        db = open_database(repo, read_only=True)
    except WalkError as exc:
        return f"\napproved: error: {exc.message}"
    try:
        artifacts = asyncio.run(ApprovedArtifactRepository(db).list(status=ApprovalStatus.APPROVED))
    finally:
        db.close()
    drifted = [a.id for a in artifacts if not _intact(repo, a)]
    return f"\napproved: {'drift ' + ', '.join(drifted) if drifted else 'ok'}"


def _intact(repo: Path, artifact: ApprovedArtifact) -> bool:
    folder = repo / ".ai" / APPROVED_DIR / artifact.id
    try:
        return hash_payload(folder, artifact.payload_paths) == artifact.content_sha256
    except ConfigError:
        return False


def _row(name: str, status: ComponentStatus) -> tuple[str, str, str, str]:
    state: ReadinessState = status.state
    return (name, state.value, status.version or "", status.detail)
