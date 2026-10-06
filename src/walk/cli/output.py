"""CLI rendering and exit-code mapping (INTERFACES §6, §87 JSON mode)."""

import json
from collections.abc import Iterable, Sequence
from typing import NoReturn

import typer

from walk.common.errors import GuardRejected, PermissionDenied, WalkError

_COLUMN_GAP = "  "
_EXIT_VALIDATION = 1  # validation/config error
_EXIT_REJECTED = 2  # guard rejected / permission denied


def render_table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    """Render left-aligned columns with a dashed rule under the header.

    ``None`` cells render empty; trailing spaces are stripped from every line.
    """
    cells = [["" if value is None else str(value) for value in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in cells:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def line(values: Sequence[str]) -> str:
        padded = (value.ljust(width) for value, width in zip(values, widths, strict=True))
        return _COLUMN_GAP.join(padded).rstrip()

    rule = ["-" * width for width in widths]
    return "\n".join([line(headers), line(rule), *(line(row) for row in cells)])


def render_json(data: object) -> str:
    """Serialise JSON-compatible ``data`` (e.g. ``model_dump(mode="json")`` output)."""
    return json.dumps(data, indent=2, ensure_ascii=False)


def exit_with(error: WalkError) -> NoReturn:
    """Print ``error`` to stderr and exit with its INTERFACES §6 code.

    `GuardRejected` and `PermissionDenied` exit 2; every other kernel error exits 1.
    """
    typer.echo(f"error: {error.message}", err=True)
    code = (
        _EXIT_REJECTED if isinstance(error, GuardRejected | PermissionDenied) else _EXIT_VALIDATION
    )
    raise typer.Exit(code=code)
