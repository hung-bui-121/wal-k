"""``walk doctor [--fix] [--strict]``: the §26 preflight plus repairs and lints (E02-S02, E02-S15).

Without flags it runs in-process, needs no daemon and only reads the database: the preflight
reads the environment and `.ai/project/*.yaml` and replaces `environment.yaml` atomically.
``--fix`` repairs guard hooks, skill projections and the memory index, then refreshes the
manifest; ``--strict`` turns drift, pin problems and the lints into findings. Exit codes:
0 clean, 4 a required component is missing, 1 a strict finding or a failed fix (or any other
kernel error).
"""

import asyncio
from pathlib import Path
from typing import Annotated, Final

import typer
from pydantic import Field

import walk
from walk.cli.composition import (
    PROJECTIONS_DIR,
    load_constitutions,
    load_model_registry,
    open_database,
    open_git,
    open_integrations,
    open_memory,
    open_skill_registry,
    skill_drift_reports,
    skill_projectors,
    version_pin_problems,
)
from walk.cli.lints import lint_constitutions_provider_names, lint_models_yaml, run_import_linter
from walk.cli.output import exit_with, render_table
from walk.common.clock import SystemClock
from walk.common.errors import ConfigError, WalkError
from walk.common.ids import ApprovedArtifactId
from walk.common.models import WalkModel
from walk.integrations import (
    AsyncioSubprocessRunner,
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
from walk.persistence import Database
from walk.runtime.sandbox import WORKTREES_DIR
from walk.skills import DriftReport
from walk.workflow import ProjectRepository

_EXIT_PREFLIGHT: Final = 4  # INTERFACES §6: preflight failed
_EXIT_FINDINGS: Final = 1
_DB_RELATIVE_PATH: Final = Path(".ai") / "kernel.db"
_KERNEL_ROOT: Final = Path(walk.__file__).resolve().parents[2]  # source checkout (dev env)
_PYPROJECT: Final = "pyproject.toml"


class DoctorReport(WalkModel):
    """What `walk doctor` found (``--json`` prints it)."""

    manifest: EnvironmentManifest = Field(description="§26 environment manifest.")
    skills: DriftReport = Field(description="Projection drift of every kernel provider, merged.")
    approved_drift: list[ApprovedArtifactId] = Field(description="Drifted approved artifacts.")
    version_pins_ok: bool = Field(description="kernel-versions.yaml matches the kernel (§105).")
    lints: list[str] = Field(description="Strict findings; empty when clean or not strict.")
    fixes_applied: list[str] = Field(description="Repairs made (and failed) by --fix.")
    exit_code: int = Field(description="0 clean, 1 findings or failed fix, 4 preflight failed.")


def doctor(
    ctx: typer.Context,
    *,
    fix: Annotated[
        bool, typer.Option("--fix", help="Repair hooks, projections, index and manifest.")
    ] = False,
    strict: Annotated[
        bool, typer.Option("--strict", help="Lint and fail on any finding (drift, pins).")
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit the DoctorReport as JSON.")
    ] = False,
    repo: Annotated[
        Path | None, typer.Option("--repo", help="Game repository root.", file_okay=False)
    ] = None,
) -> None:
    """Check git, Unity, providers, credentials and skills; write `.ai/project/environment.yaml`.

    Exit 0 when every required component is present and nothing else is wrong, 4 when one is
    missing, 1 on a strict finding, a failed fix or any other kernel error.
    """
    options = ctx.find_root().obj if isinstance(ctx.find_root().obj, dict) else {}
    root = repo if repo is not None else options.get("repo", Path())
    as_json = json_output or bool(options.get("json"))
    path = root if isinstance(root, Path) else Path()
    fixes, fix_failed = asyncio.run(_apply_fixes(path)) if fix else ([], False)
    missing: ConfigError | None = None
    try:
        manifest = asyncio.run(open_integrations(path).preflight(list(REQUIRED_DEFAULT)))
    except ConfigError as exc:
        stored = ManifestStore(path / ".ai", SystemClock()).read()  # written before raising
        if MISSING_COMPONENTS not in exc.detail or stored is None:
            exit_with(exc)
        manifest, missing = stored, exc
    except WalkError as exc:
        exit_with(exc)
    if fix:
        fixes.append("manifest: refreshed")
    reports, skills_note = _skill_reports(path)
    approved, approved_note = _approved(path)
    pin_problems = _pin_problems(path)
    lints = _lints(path, reports, skills_note, approved, pin_problems) if strict else []
    findings = fix_failed or bool(lints)
    exit_code = _EXIT_PREFLIGHT if missing else _EXIT_FINDINGS if findings else 0
    report = DoctorReport(
        manifest=manifest,
        skills=_merged(reports),
        approved_drift=approved,
        version_pins_ok=not pin_problems,
        lints=lints,
        fixes_applied=fixes,
        exit_code=exit_code,
    )
    if as_json:
        typer.echo(report.model_dump_json(indent=2))
    else:
        typer.echo(_render(manifest))
        typer.echo(_skills_section(reports, skills_note))
        typer.echo(f"\napproved: {approved_note}")
        typer.echo(f"\nversions: {'; '.join(pin_problems) or 'ok'}")
        if strict:
            typer.echo("\nlints: " + ("none" if not lints else "\n  " + "\n  ".join(lints)))
        if fix:
            typer.echo("\nfixes:\n  " + "\n  ".join(fixes))
    if missing is not None:
        typer.echo(f"error: {missing.message}", err=True)
    if exit_code:
        raise typer.Exit(code=exit_code)


async def _apply_fixes(repo: Path) -> tuple[list[str], bool]:
    """Guard hooks, skill projections, memory index; each failure recorded, none stops."""
    applied: list[str] = []
    failed = False
    for name, step in (
        ("guard hooks", _fix_guard_hooks),
        ("skills", _fix_skills),
        ("memory index", _fix_memory_index),
    ):
        try:
            applied += await step(repo)
        except Exception as exc:  # noqa: BLE001 - a failing fix is reported; the others still run
            message = exc.message if isinstance(exc, WalkError) else str(exc)
            applied.append(f"{name} failed: {message}")
            failed = True
    return applied, failed


async def _fix_guard_hooks(repo: Path) -> list[str]:
    db = _writable_database(repo)
    try:
        project = await ProjectRepository(db).single()
        git = open_git(db, repo, project_key=project.key)
        worktrees = repo / WORKTREES_DIR
        targets = (
            [repo, *sorted(p for p in worktrees.iterdir() if p.is_dir())]
            if (worktrees.is_dir())
            else [repo]
        )
        for target in targets:
            await git.install_guard_hooks(str(target), list(project.protected_branches))
        return [f"guard hooks: {target}" for target in targets]
    finally:
        db.close()


async def _fix_skills(repo: Path) -> list[str]:
    registry, db = open_skill_registry(repo)
    try:
        applied: list[str] = []
        for projector in skill_projectors():
            worktree = repo / PROJECTIONS_DIR / projector.provider
            worktree.mkdir(parents=True, exist_ok=True)
            report = await registry.check_drift([projector], str(worktree))
            if not report.ok:
                await registry.regenerate([projector], str(worktree), report)
                applied.append(f"skills: regenerated {projector.provider}")
        return applied
    finally:
        db.close()


async def _fix_memory_index(repo: Path) -> list[str]:
    db = _writable_database(repo)
    try:
        project = await ProjectRepository(db).single()
        count = await open_memory(db, repo, project_key=project.key).rebuild_index()
        return [f"memory index: {count} documents"]
    finally:
        db.close()


def _writable_database(repo: Path) -> Database:
    if not (repo / _DB_RELATIVE_PATH).is_file():
        msg = f"no database at {repo / _DB_RELATIVE_PATH}; run 'walk bootstrap'"
        raise ConfigError(msg, detail={"repo": str(repo)})
    return open_database(repo)


def _skill_reports(repo: Path) -> tuple[dict[str, DriftReport], str]:
    try:
        return skill_drift_reports(repo), ""
    except WalkError as exc:
        return {}, f"error: {exc.message}"


def _merged(reports: dict[str, DriftReport]) -> DriftReport:
    missing = list(dict.fromkeys(name for r in reports.values() for name in r.missing))
    modified = list(dict.fromkeys(name for r in reports.values() for name in r.modified))
    orphaned = list(dict.fromkeys(name for r in reports.values() for name in r.orphaned))
    ok = bool(reports) and all(r.ok for r in reports.values())
    return DriftReport(missing=missing, modified=modified, orphaned=orphaned, ok=ok)


def _pin_problems(repo: Path) -> list[str]:
    try:
        return version_pin_problems(repo)
    except WalkError as exc:
        return [exc.message]


def _lints(
    repo: Path,
    reports: dict[str, DriftReport],
    skills_note: str,
    approved: list[ApprovedArtifactId],
    pin_problems: list[str],
) -> list[str]:
    """Strict findings: drift, pins, constitutions, models.yaml, import contracts."""
    findings = [f"skills: {skills_note}"] if skills_note else []
    findings += [
        f"skills {provider}: {_counts(report)}"
        for provider, report in reports.items()
        if not report.ok
    ]
    findings += [f"approved artifact drift: {artifact_id}" for artifact_id in approved]
    findings += [f"versions: {problem}" for problem in pin_problems]
    try:
        findings += lint_constitutions_provider_names(load_constitutions(repo))
        findings += lint_models_yaml(load_model_registry(repo))
    except WalkError as exc:
        findings.append(f"configuration: {exc.message}")
    if (_KERNEL_ROOT / _PYPROJECT).is_file():  # an installed wheel has no contracts to check
        try:
            findings += asyncio.run(run_import_linter(AsyncioSubprocessRunner(), _KERNEL_ROOT))
        except ConfigError as exc:
            findings.append(exc.message)
    return findings


def _render(manifest: EnvironmentManifest) -> str:
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


def _skills_section(reports: dict[str, DriftReport], note: str) -> str:
    """``skills`` lines: ``ok`` or counts per drift category per provider."""
    if note:
        return f"\nskills: {note}"
    lines = ["", "skills:"]
    lines += [f"  {provider}: {_counts(report) or 'ok'}" for provider, report in reports.items()]
    return "\n".join(lines)


def _counts(report: DriftReport) -> str:
    return ", ".join(
        f"{label} {len(names)}"
        for label, names in (
            ("missing", report.missing),
            ("modified", report.modified),
            ("orphaned", report.orphaned),
        )
        if names
    )


def _approved(repo: Path) -> tuple[list[ApprovedArtifactId], str]:
    """Drifted approved artifacts (E02-S12) and the ``approved`` line, read-only.

    The hashes are recomputed against a read-only database connection; marking the drift
    INVALID is left to the kernel start and `walk artifacts verify`.
    """
    if not (repo / _DB_RELATIVE_PATH).is_file():
        return [], "no database"
    try:
        db = open_database(repo, read_only=True)
    except WalkError as exc:
        return [], f"error: {exc.message}"
    try:
        artifacts = asyncio.run(ApprovedArtifactRepository(db).list(status=ApprovalStatus.APPROVED))
    finally:
        db.close()
    drifted = [a.id for a in artifacts if not _intact(repo, a)]
    return drifted, ("drift " + ", ".join(drifted)) if drifted else "ok"


def _intact(repo: Path, artifact: ApprovedArtifact) -> bool:
    folder = repo / ".ai" / APPROVED_DIR / artifact.id
    try:
        return hash_payload(folder, artifact.payload_paths) == artifact.content_sha256
    except ConfigError:
        return False


def _row(name: str, status: ComponentStatus) -> tuple[str, str, str, str]:
    state: ReadinessState = status.state
    return (name, state.value, status.version or "", status.detail)
