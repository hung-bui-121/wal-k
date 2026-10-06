"""Claude Code CLI transport that launches the CLI with an exact environment (E02-S01).

The SDK's default `SubprocessCLITransport` merges ``ClaudeAgentOptions.env`` onto the kernel's
inherited environment, so provider and Jira secrets would reach the agent (ARCHITECTURE §6
"Secret isolation"). `scrubbed_transport` returns a subclass whose ``connect`` spawns the CLI
with exactly the given mapping and nothing inherited. Everything else (command line, message
framing, ``close``) stays the SDK's own. The SDK's optional ``claude -v`` probe is skipped: it
would run with the inherited environment and only logs a warning.
"""

import dataclasses
import importlib
from collections.abc import AsyncIterator, Mapping
from types import ModuleType
from typing import Any, Final

TRANSPORT_MODULE: Final = "claude_agent_sdk._internal.transport.subprocess_cli"
"""SDK module of `SubprocessCLITransport` (`Transport` is public; the CLI transport is not)."""

_STDIO_PERMISSION_TOOL: Final = "stdio"


def scrubbed_transport(
    options: Any, env: Mapping[str, str], *, module: ModuleType | None = None
) -> object:
    """An SDK transport that runs the Claude Code CLI with exactly ``env``.

    Args:
        options: The `ClaudeAgentOptions` of the query. As the SDK does for its own transport,
            a set ``can_use_tool`` routes permission prompts over stdio.
        env: The complete process environment of the CLI (copied now).
        module: The SDK's transport module; imported from `TRANSPORT_MODULE` when ``None``.

    Raises:
        ImportError: ``claude-agent-sdk`` is not installed.
    """
    sdk = module if module is not None else importlib.import_module(TRANSPORT_MODULE)
    exact = dict(env)
    base: Any = sdk.SubprocessCLITransport

    class _ScrubbedEnvTransport(base):  # type: ignore[misc]  # SDK base class, loaded lazily (optional extra)
        _process: Any  # the SDK's private state, written below as the SDK's connect does
        _cli_path: str | None

        async def connect(self) -> None:
            if self._process is not None:
                return
            if self._cli_path is None:
                self._cli_path = await sdk.anyio.to_thread.run_sync(self._find_cli)
            self._reject_windows_batch_cli(self._cli_path)
            process = await sdk.anyio.open_process(
                self._build_command(),
                stdin=sdk.PIPE,
                stdout=sdk.PIPE,
                stderr=None,
                cwd=self._cwd,
                env=dict(exact),
            )
            self._process = process
            self._stdout_stream = sdk.TextReceiveStream(process.stdout)
            self._stdin_stream = sdk.TextSendStream(process.stdin)
            self._ready = True

    if getattr(options, "can_use_tool", None) is not None:
        options = dataclasses.replace(options, permission_prompt_tool_name=_STDIO_PERMISSION_TOOL)
    return _ScrubbedEnvTransport(prompt=_no_prompt(), options=options)


async def _no_prompt() -> AsyncIterator[dict[str, Any]]:
    """Prompts are written by `ClaudeSDKClient.query`, never taken from the transport."""
    return
    yield {}  # pragma: no cover - makes this an (empty) async generator
