"""``walk bootstrap``: create the Production Kit of a game repository (§25; E02-S03).

The command checks everything that needs no filesystem change first (confirmation, project
key, Jira credentials); only then does `open_bootstrapper` open the database, which creates
`.ai/`.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Annotated, Final, Literal

import typer
from pydantic import ValidationError

from walk.cli.composition import open_bootstrapper
from walk.cli.output import exit_with
from walk.common.errors import ConfigError, WalkError
from walk.integrations import CREDENTIAL_NAMES, CredentialStore
from walk.integrations.credentials import SystemKeyringBackend
from walk.integrations.preflight import MISSING_COMPONENTS
from walk.orchestrator import BootstrapOptions, BootstrapResult

_EXIT_ERROR: Final = 1  # INTERFACES §6: validation error
_EXIT_PREFLIGHT: Final = 4  # INTERFACES §6: preflight failed
_JIRA_PREFIX: Final = "JIRA_"


def bootstrap(
    ctx: typer.Context,
    *,
    key: Annotated[str, typer.Option("--key", help="Project key, e.g. DEMO.")],
    name: Annotated[str, typer.Option("--name", help="Project name.")],
    gdd: Annotated[
        list[str] | None,
        typer.Option("--gdd", help="GDD file relative to the repository (repeatable)."),
    ] = None,
    provider: Annotated[
        Literal["local", "jira"], typer.Option("--provider", help="Work provider.")
    ] = "local",
    unity_path: Annotated[
        str | None, typer.Option("--unity-path", help="Unity editor executable.")
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", help="Do not ask for confirmation.")] = False,
    repo: Annotated[
        Path | None, typer.Option("--repo", help="Game repository root.", file_okay=False)
    ] = None,
) -> None:
    """Preflight, copy the kernel defaults into `.ai/agents/`, initialise `.ai/` and the database.

    Idempotent: existing files are never overwritten. Exit 0 on success, 4 when the preflight
    or the Jira credentials fail, 1 on any other error (nothing is created on 1 or 4 before the
    database is opened).
    """
    options_obj = ctx.find_root().obj if isinstance(ctx.find_root().obj, dict) else {}
    root = repo if repo is not None else options_obj.get("repo", Path())
    path = root if isinstance(root, Path) else Path()
    as_json = bool(options_obj.get("json"))
    try:
        options = BootstrapOptions(
            repo_path=str(path),
            project_key=key,
            name=name,
            gdd_paths=list(gdd or []),
            provider=provider,
            unity_path=unity_path,
            yes=yes,
        )
    except ValidationError as exc:
        _fail(f"invalid project key {key!r}: expected 2-10 uppercase letters or digits", exc)
    _confirm(path, yes=yes)
    _require_jira_credentials(provider)
    try:
        result = asyncio.run(open_bootstrapper(path, options).run(options))
    except ConfigError as exc:
        if MISSING_COMPONENTS not in exc.detail:
            exit_with(exc)
        typer.echo(f"error: {exc.message}", err=True)
        raise typer.Exit(code=_EXIT_PREFLIGHT) from exc
    except WalkError as exc:
        exit_with(exc)
    typer.echo(_render(result, as_json=as_json))


def _interactive() -> bool:
    return sys.stdin.isatty()


def _confirm(repo: Path, *, yes: bool) -> None:
    """Behavior 3: ``--yes``, or a confirmed prompt on a terminal."""
    if yes:
        return
    if not _interactive():
        _fail("bootstrap requires --yes in non-interactive mode")
    if not typer.confirm(f"Create Production Kit in {repo}?", default=False):
        _fail("bootstrap aborted")


def _require_jira_credentials(provider: str) -> None:
    """Behavior 7: the Jira credentials must be present before anything is created."""
    if provider != "jira":
        return
    store = CredentialStore(os.environ, SystemKeyringBackend())
    absent = [n for n in CREDENTIAL_NAMES if n.startswith(_JIRA_PREFIX) and not store.present(n)]
    if absent:
        typer.echo(f"error: jira credentials missing: {', '.join(absent)}", err=True)
        raise typer.Exit(code=_EXIT_PREFLIGHT)


def _fail(message: str, cause: Exception | None = None) -> None:
    typer.echo(f"error: {message}", err=True)
    raise typer.Exit(code=_EXIT_ERROR) from cause


def _render(result: BootstrapResult, *, as_json: bool) -> str:
    if as_json:
        return result.model_dump_json(indent=2)
    if not result.created_paths:
        return "nothing to do"
    return "\n".join(["created:", *(f"  {path}" for path in result.created_paths)])
