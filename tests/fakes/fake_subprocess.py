"""Scripted subprocess runner for tests (implements `walk.integrations.SubprocessRunner`)."""

from typing import NamedTuple

from walk.integrations.subprocess import SubprocessResult


class _Call(NamedTuple):
    argv: list[str]
    cwd: str | None
    env: dict[str, str] | None
    timeout_s: int
    input_text: str | None


class _Script(NamedTuple):
    prefix: list[str]
    exit_code: int
    stdout: str
    stderr: str
    error: Exception | None


class FakeSubprocessRunner:
    """Returns scripted results by argv prefix and records every call.

    The longest matching prefix wins; among equal prefixes the most recently scripted one
    wins. An unscripted command raises ``AssertionError`` so tests notice it.
    """

    def __init__(self) -> None:
        """Start with no scripts and no recorded calls."""
        self._scripts: list[_Script] = []
        self.calls: list[_Call] = []

    def script(
        self,
        prefix: list[str],
        *,
        exit_code: int = 0,
        stdout: str = "",
        stderr: str = "",
        error: Exception | None = None,
    ) -> None:
        """Answer commands starting with ``prefix``; ``error`` is raised instead when set."""
        self._scripts.append(_Script(list(prefix), exit_code, stdout, stderr, error))

    @property
    def argvs(self) -> list[list[str]]:
        """The argv of every recorded call, in call order."""
        return [call.argv for call in self.calls]

    async def run(
        self,
        argv: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_s: int = 120,
        input_text: str | None = None,
    ) -> SubprocessResult:
        """Record the call and return (or raise) the best matching script."""
        self.calls.append(_Call(list(argv), cwd, env, timeout_s, input_text))
        best: _Script | None = None
        for candidate in self._scripts:
            if argv[: len(candidate.prefix)] != candidate.prefix:
                continue
            if best is None or len(candidate.prefix) >= len(best.prefix):
                best = candidate
        if best is None:
            msg = f"unscripted command: {argv}"
            raise AssertionError(msg)
        if best.error is not None:
            raise best.error
        return SubprocessResult(
            argv=list(argv),
            exit_code=best.exit_code,
            stdout=best.stdout,
            stderr=best.stderr,
            duration_ms=0,
        )


__all__ = ["FakeSubprocessRunner"]
