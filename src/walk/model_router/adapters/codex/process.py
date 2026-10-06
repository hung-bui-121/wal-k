"""Codex CLI processes (ARCHITECTURE §2.3: the only module that spawns the ``codex`` CLI).

`CodexProcessLauncher` mirrors `walk.integrations.SubprocessRunner` structurally but streams
stdout; `model_router` may not import `integrations` (ARCHITECTURE §2.2, E01-S22 Notes).
"""

import asyncio
import contextlib
import shutil
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Final, Protocol

from walk.model_router.adapters.codex.command import CODEX_BINARY

_LINE_LIMIT_BYTES: Final = 16 * 1024 * 1024  # one JSONL event can carry a large tool output
_QUICK_TIMEOUT_S: Final = 30.0


class CodexProcess(Protocol):
    """A running ``codex exec`` process."""

    pid: int | None

    def lines(self) -> AsyncIterator[str]:
        """Stdout lines (JSONL) without line terminators."""
        ...

    async def wait(self) -> int:
        """Wait for the exit code."""
        ...

    async def kill(self) -> None:
        """Kill the process; no error when it already exited."""
        ...

    async def stderr_text(self) -> str:
        """Everything the process wrote to stderr (complete once it exited)."""
        ...


class CodexProcessLauncher(Protocol):
    """Starts ``codex`` processes and answers the cheap health probes."""

    async def launch(
        self, argv: list[str], *, cwd: str, env: dict[str, str], stdin_path: str | None = None
    ) -> CodexProcess:
        """Start ``argv`` in ``cwd`` with exactly ``env``; ``stdin_path`` is fed to stdin.

        Raises:
            FileNotFoundError: The executable does not exist.
        """
        ...

    async def version(self) -> tuple[bool, str]:
        """``codex --version`` succeeded, and its output."""
        ...

    async def login_status(self) -> tuple[bool, str]:
        """``codex login status`` succeeded, and its output."""
        ...


class _AsyncioCodexProcess:
    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self._process = process
        self.pid: int | None = process.pid
        stderr = process.stderr
        assert stderr is not None  # noqa: S101 - created with stderr=PIPE
        # Drain stderr concurrently so a chatty process cannot block on a full pipe.
        self._stderr = asyncio.create_task(stderr.read())

    async def lines(self) -> AsyncIterator[str]:
        stdout = self._process.stdout
        assert stdout is not None  # noqa: S101 - created with stdout=PIPE
        while True:
            raw = await stdout.readline()
            if not raw:
                return
            yield raw.decode("utf-8", errors="replace").rstrip("\r\n")

    async def wait(self) -> int:
        return await self._process.wait()

    async def kill(self) -> None:
        if self._process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                self._process.kill()
        await self._process.wait()

    async def stderr_text(self) -> str:
        return (await self._stderr).decode("utf-8", errors="replace")


class AsyncioCodexProcessLauncher:
    """`CodexProcessLauncher` on `asyncio.create_subprocess_exec`."""

    def __init__(self, binary: str = CODEX_BINARY) -> None:
        """Probe health with ``binary`` (resolved on PATH)."""
        self._binary = binary

    async def launch(
        self, argv: list[str], *, cwd: str, env: dict[str, str], stdin_path: str | None = None
    ) -> CodexProcess:
        """Start ``argv``; ``argv[0]`` is resolved on the kernel's PATH (``codex.cmd`` on Windows).

        Raises:
            FileNotFoundError: ``argv[0]`` cannot be found.
        """
        executable = _resolve(argv[0])
        stdin = Path(stdin_path).open("rb") if stdin_path is not None else None  # noqa: ASYNC230, SIM115 - handed to the child, closed below
        try:
            process = await asyncio.create_subprocess_exec(
                executable,
                *argv[1:],
                cwd=cwd,
                env=env,
                stdin=stdin if stdin is not None else subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=_LINE_LIMIT_BYTES,
            )
        finally:
            if stdin is not None:
                stdin.close()
        return _AsyncioCodexProcess(process)

    async def version(self) -> tuple[bool, str]:
        """``<binary> --version``."""
        return await self._quick("--version")

    async def login_status(self) -> tuple[bool, str]:
        """``<binary> login status``."""
        return await self._quick("login", "status")

    async def _quick(self, *args: str) -> tuple[bool, str]:
        try:
            executable = _resolve(self._binary)
        except FileNotFoundError as exc:
            return False, str(exc)
        process = await asyncio.create_subprocess_exec(
            executable, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), _QUICK_TIMEOUT_S)
        text = (stdout or stderr).decode("utf-8", errors="replace").strip()
        return process.returncode == 0, text or f"exit code {process.returncode}"


def _resolve(executable: str) -> str:
    resolved = shutil.which(executable)
    if resolved is None:
        msg = f"executable not found: {executable}"
        raise FileNotFoundError(msg)
    return resolved
