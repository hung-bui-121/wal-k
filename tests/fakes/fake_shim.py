"""Fake command-line tools written to a directory for executable-resolution tests (E02-B01).

On Windows a tool is a `.cmd` batch shim (how npm installs `codex`, `graphify`, ...); elsewhere it
is an executable ``#!/bin/sh`` script. Neither starts a real provider CLI.
"""

import stat
import sys
from pathlib import Path


def write_shim(directory: Path, name: str, *, output: str, marker: Path | None = None) -> Path:
    """Write tool ``name`` into ``directory``; it prints ``output`` and exits 0.

    Args:
        directory: Existing directory to write the tool into.
        name: Command name without extension (``codex`` becomes ``codex.cmd`` on Windows).
        output: One line printed to stdout; plain words only (no shell metacharacters).
        marker: When given, the tool creates this file, proving that it ran.

    Returns:
        The path of the written tool.
    """
    if sys.platform == "win32":
        path = directory / f"{name}.cmd"
        lines = ["@echo off", f"echo {output}"]
        if marker is not None:
            lines.append(f'type nul > "{marker}"')
        path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
        return path
    path = directory / name
    lines = ["#!/bin/sh", f"echo '{output}'"]
    if marker is not None:
        lines.append(f": > '{marker}'")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path
