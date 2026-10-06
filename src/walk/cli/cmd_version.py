"""``walk version``: the kernel version and the project's behavior-version pins (§105; E02-S04).

Works without a bootstrapped repository: the pins section then reads ``(no project)``.
"""

import json
from pathlib import Path
from typing import Annotated

import typer

import walk
from walk.cli.output import exit_with
from walk.common.errors import WalkError
from walk.improvement import PINS_PATH, KernelVersionPins

_AI_DIR = ".ai"


def version(
    ctx: typer.Context,
    *,
    json_output: Annotated[
        bool, typer.Option("--json", help='Emit {"kernel": ..., "pins": ...} as JSON.')
    ] = False,
    repo: Annotated[
        Path | None, typer.Option("--repo", help="Game repository root.", file_okay=False)
    ] = None,
) -> None:
    """Print ``walk <version>``, then one ``<KIND>/<name> <version>`` line per project pin.

    Exit 0; 1 when `.ai/project/kernel-versions.yaml` exists but is invalid.
    """
    root_obj = ctx.find_root().obj
    options = root_obj if isinstance(root_obj, dict) else {}
    root = repo if repo is not None else options.get("repo", Path())
    path = root if isinstance(root, Path) else Path()
    as_json = json_output or bool(options.get("json"))
    ai_root = path / _AI_DIR
    try:
        pins = KernelVersionPins.load(ai_root).pins if (ai_root / PINS_PATH).is_file() else None
    except WalkError as exc:
        exit_with(exc)
    if as_json:
        typer.echo(json.dumps({"kernel": walk.__version__, "pins": pins}, indent=2))
        return
    lines = [f"walk {walk.__version__}"]
    if pins is None:
        lines.append("(no project)")
    elif not pins:
        lines.append("(no pins)")
    else:
        lines += [f"{key} {value}" for key, value in sorted(pins.items())]
    typer.echo("\n".join(lines))
