"""Scripted `CodexProcessLauncher` for tests (E01-S22); no process is ever spawned."""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import NamedTuple


class _Launch(NamedTuple):
    argv: list[str]
    cwd: str
    env: dict[str, str]
    stdin_text: str | None


class _Script(NamedTuple):
    lines: list[str]
    exit_code: int
    stderr: str
    hang: bool
    stdout_error: Exception | None


class FakeCodexProcess:
    """One scripted process: stdout lines, then an exit code (or a hang until killed)."""

    _KILLED_EXIT_CODE = -9

    def __init__(self, script: _Script) -> None:
        """Play ``script``."""
        self.pid: int | None = 4242
        self._script = script
        self._killed = asyncio.Event()
        self.killed = False

    async def lines(self) -> AsyncIterator[str]:
        """The scripted lines; with ``hang`` the stream then blocks until `kill`."""
        for line in self._script.lines:
            if self.killed:
                return
            yield line
        if self._script.stdout_error is not None:
            raise self._script.stdout_error
        if self._script.hang:
            await self._killed.wait()

    async def wait(self) -> int:
        """The scripted exit code (-9 once killed)."""
        return self._KILLED_EXIT_CODE if self.killed else self._script.exit_code

    async def kill(self) -> None:
        """Mark killed and release a hanging stream."""
        self.killed = True
        self._killed.set()

    async def stderr_text(self) -> str:
        """The scripted stderr."""
        return self._script.stderr


class FakeCodexProcessLauncher:
    """Each launch plays the next queued script, or the default one when none is queued."""

    def __init__(
        self,
        lines: list[str] | None = None,
        *,
        exit_code: int = 0,
        stderr: str = "",
        hang: bool = False,
        stdout_error: Exception | None = None,
        version: tuple[bool, str] = (True, "codex-cli 0.160.1"),
        login: tuple[bool, str] = (True, "Logged in using ChatGPT"),
        launch_error: OSError | None = None,
    ) -> None:
        """Script the default process, health answers and a launch failure."""
        self._default = _Script(list(lines or []), exit_code, stderr, hang, stdout_error)
        self._queued: list[_Script] = []
        self.version_result = version
        self.login_result = login
        self.launch_error = launch_error
        self.launches: list[_Launch] = []
        self.processes: list[FakeCodexProcess] = []
        self.version_calls = 0
        self.login_calls = 0

    def queue_script(
        self, lines: list[str], *, exit_code: int = 0, stderr: str = "", hang: bool = False
    ) -> None:
        """Play ``lines`` on the next launch that finds no earlier queued script."""
        self._queued.append(_Script(list(lines), exit_code, stderr, hang, None))

    async def launch(
        self, argv: list[str], *, cwd: str, env: dict[str, str], stdin_path: str | None = None
    ) -> FakeCodexProcess:
        """Record the launch (with the stdin file's text) and start the next script."""
        if self.launch_error is not None:
            raise self.launch_error
        stdin_text = _read(stdin_path) if stdin_path else None
        self.launches.append(_Launch(list(argv), cwd, dict(env), stdin_text))
        script = self._queued.pop(0) if self._queued else self._default
        process = FakeCodexProcess(script)
        self.processes.append(process)
        return process

    async def version(self) -> tuple[bool, str]:
        """The scripted `codex --version` answer."""
        self.version_calls += 1
        return self.version_result

    async def login_status(self) -> tuple[bool, str]:
        """The scripted `codex login status` answer."""
        self.login_calls += 1
        return self.login_result


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


__all__ = ["FakeCodexProcessLauncher"]
