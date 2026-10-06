"""Injectable subprocess execution (WBS §3.6; E01-S23).

Git, Unity, Codex and Graphify code runs external commands only through a `SubprocessRunner`
so that it can be unit-tested with a scripted fake instead of spawning processes.
"""

import asyncio
import logging
import shutil
import sys
import time
from collections.abc import Mapping
from typing import Final, Protocol

from pydantic import Field

from walk.common.errors import Timeout
from walk.common.models import FrozenModel

_LOG = logging.getLogger(__name__)
_EXIT_NOT_FOUND: Final = 127  # POSIX shell convention for "command not found"
_EXIT_REFUSED: Final = 126  # POSIX "found but cannot be executed"
_BATCH_SUFFIXES: Final = (".cmd", ".bat")

BATCH_UNSAFE_CHARS: str = '%!"&|<>^\r\n'  # characters cmd.exe re-parses in batch-file arguments
_MS_PER_S = 1000


class SubprocessResult(FrozenModel):
    """Outcome of one finished command; a non-zero exit is a result, not an error."""

    argv: list[str] = Field(description="The command and its arguments as executed.")
    exit_code: int = Field(description="Process exit code (127 when the executable is missing).")
    stdout: str = Field(description="Captured standard output, decoded as UTF-8.")
    stderr: str = Field(description="Captured standard error, decoded as UTF-8.")
    duration_ms: int = Field(description="Wall time from spawn to exit in milliseconds.")


class SubprocessRunner(Protocol):
    """Runs one external command to completion."""

    async def run(
        self,
        argv: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_s: int = 120,
        input_text: str | None = None,
    ) -> SubprocessResult:
        """Run ``argv`` and return its result without raising on a non-zero exit.

        Raises:
            Timeout: The command ran longer than ``timeout_s``; it has been killed.
        """
        ...


class AsyncioSubprocessRunner:
    """`SubprocessRunner` on `asyncio.create_subprocess_exec` (no shell)."""

    async def run(
        self,
        argv: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_s: int = 120,
        input_text: str | None = None,
    ) -> SubprocessResult:
        """Run ``argv``; ``env=None`` inherits the environment, a dict replaces it entirely.

        ``argv[0]`` is resolved with `resolve_executable` (``PATHEXT`` shims on Windows), and the
        resolved path is spawned. ``input_text`` is written to stdin (UTF-8). A missing
        executable is reported as exit code 127, and an argument that ``cmd.exe`` would re-parse
        for a ``.cmd``/``.bat`` executable as exit code 126; in both cases nothing is spawned
        and the reason is on stderr, like a POSIX shell.

        Raises:
            Timeout: The command ran longer than ``timeout_s``; it has been killed.
        """
        started = time.monotonic()
        executable = resolve_executable(argv[0], env)
        if executable is None:
            return _unspawned(argv, _EXIT_NOT_FOUND, f"executable not found: {argv[0]}", started)
        unsafe = unsafe_batch_argument(executable, argv[1:])
        if unsafe is not None:
            position = unsafe + 1  # argv position: argument 1 is the first after the executable
            _LOG.warning("refused batch-file argument", extra={"argv0": argv[0], "index": position})
            reason = f"refused: argument {position} is unsafe for batch file {argv[0]}"
            return _unspawned(argv, _EXIT_REFUSED, reason, started)
        try:
            proc = await asyncio.create_subprocess_exec(
                executable,
                *argv[1:],
                cwd=cwd,
                env=env,
                stdin=asyncio.subprocess.PIPE if input_text is not None else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:  # removed between lookup and spawn
            reason = f"executable not found: {argv[0]} ({exc})"
            return _unspawned(argv, _EXIT_NOT_FOUND, reason, started)
        stdin = input_text.encode("utf-8") if input_text is not None else None
        try:
            out, err = await asyncio.wait_for(proc.communicate(stdin), timeout=timeout_s)
        except TimeoutError as exc:
            proc.kill()
            await proc.wait()
            _LOG.warning("subprocess timed out", extra={"argv": argv, "timeout_s": timeout_s})
            msg = "subprocess timed out"
            raise Timeout(msg, detail={"argv": list(argv), "timeout_s": timeout_s}) from exc
        return SubprocessResult(
            argv=list(argv),
            exit_code=proc.returncode if proc.returncode is not None else -1,
            stdout=out.decode("utf-8", errors="replace"),
            stderr=err.decode("utf-8", errors="replace"),
            duration_ms=_elapsed_ms(started),
        )


def resolve_executable(name: str, env: Mapping[str, str] | None) -> str | None:
    """Absolute path of executable ``name``, searched the way the child's spawn would search.

    The search path is the ``PATH`` of ``env`` when ``env`` is given and has one (matched
    case-insensitively on Windows), else the kernel's ``PATH``. On Windows `shutil.which` applies
    the kernel's ``PATHEXT``, so ``codex`` finds ``codex.cmd``.

    Returns:
        The resolved path, or None when ``name`` is not found.
    """
    return shutil.which(name, path=_search_path(env))


def unsafe_batch_argument(executable: str, args: list[str]) -> int | None:
    """Index in ``args`` of the first argument ``cmd.exe`` would re-parse for a batch file.

    Applies only when ``executable`` ends with ``.cmd`` or ``.bat`` (case-insensitive): an
    argument containing a `BATCH_UNSAFE_CHARS` character could inject commands (the
    CVE-2024-24576 class). Pure; independent of the running platform.

    Returns:
        The index of the first unsafe argument, or None when there is none or the executable
        is not a batch file.
    """
    if not executable.lower().endswith(_BATCH_SUFFIXES):
        return None
    for index, arg in enumerate(args):
        if any(char in BATCH_UNSAFE_CHARS for char in arg):
            return index
    return None


def _unspawned(argv: list[str], exit_code: int, reason: str, started: float) -> SubprocessResult:
    """The result of a command that was not spawned; ``reason`` goes to stderr."""
    return SubprocessResult(
        argv=list(argv),
        exit_code=exit_code,
        stdout="",
        stderr=reason,
        duration_ms=_elapsed_ms(started),
    )


def _search_path(env: Mapping[str, str] | None) -> str | None:
    """The ``PATH`` value of ``env``; None (the kernel's ``PATH``) when absent."""
    if env is None:
        return None
    if sys.platform == "win32":
        values = [value for key, value in env.items() if key.upper() == "PATH"]
        return values[0] if values else None
    return env.get("PATH")


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * _MS_PER_S)
