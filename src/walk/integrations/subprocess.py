"""Injectable subprocess execution (WBS §3.6; E01-S23).

Git, Unity, Codex and Graphify code runs external commands only through a `SubprocessRunner`
so that it can be unit-tested with a scripted fake instead of spawning processes.
"""

import asyncio
import logging
import time
from typing import Protocol

from pydantic import Field

from walk.common.errors import Timeout
from walk.common.models import FrozenModel

_LOG = logging.getLogger(__name__)
_EXIT_NOT_FOUND = 127  # POSIX shell convention for "command not found"
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

        ``input_text`` is written to stdin (UTF-8). A missing executable is reported as exit
        code 127 with the reason on stderr, like a POSIX shell.

        Raises:
            Timeout: The command ran longer than ``timeout_s``; it has been killed.
        """
        started = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=cwd,
                env=env,
                stdin=asyncio.subprocess.PIPE if input_text is not None else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            return SubprocessResult(
                argv=list(argv),
                exit_code=_EXIT_NOT_FOUND,
                stdout="",
                stderr=f"executable not found: {argv[0]} ({exc})",
                duration_ms=_elapsed_ms(started),
            )
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


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * _MS_PER_S)
