"""The Claude Agent SDK boundary (ADR-0004 D-7, ADR-0014; ARCHITECTURE §2.3).

`SdkClaudeClient` is the only kernel code that imports `claude_agent_sdk`, and it imports it
lazily so the kernel runs without the optional ``claude`` extra. Everything else in the adapter
talks to the `ClaudeClient` protocol and treats SDK messages as opaque `SdkMessage` objects.
"""

import importlib
import shutil
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any, Final, Protocol

from pydantic import Field

from walk.common.errors import ConfigError
from walk.common.ids import ModelId
from walk.common.models import FrozenModel, JsonDict
from walk.model_router.adapters.claude.transport import scrubbed_transport

SdkMessage = object  # opaque SDK message; translate_message inspects type name + attributes
CommandProbe = Callable[[list[str]], Awaitable[tuple[int, str, str]]]
"""Runs a short command; returns (exit code, stdout, stderr). Wired by the composition root."""
TransportFactory = Callable[[Any, Mapping[str, str]], object]
"""Builds the SDK transport of one query from its SDK options and the exact CLI environment."""

_SDK_MODULE: Final = "claude_agent_sdk"
_CLI_NAME: Final = "claude.exe" if sys.platform == "win32" else "claude"
_INIT_SUBTYPE: Final = "init"


class ClaudeQueryOptions(FrozenModel):
    """Provider-mechanical options; field names are the ones ADR-0014 verified.

    They map one to one onto `claude_agent_sdk.ClaudeAgentOptions`, except ``model`` (the
    kernel `ModelId`; the SDK gets the part after ``<provider>/``) and ``output_schema``
    (sent as ``output_format={"type": "json_schema", "schema": ...}``).
    """

    cwd: str = Field(description="Working directory of the agent: the run's worktree.")
    model: ModelId = Field(description="Kernel model id, e.g. 'claude/claude-opus-5-5'.")
    tools: list[str] = Field(
        description="SDK tool names the agent may use at all (ADR-0014: restricts the tool set)."
    )
    allowed_tools: list[str] = Field(
        description="Pre-approved SDK tools; always empty so every call reaches can_use_tool."
    )
    permission_mode: str = Field(
        description="'default': every call not pre-approved goes through can_use_tool."
    )
    max_turns: int = Field(description="Turn limit of the query.")
    system_prompt: str = Field(description="Kernel system prompt (constitution and contract).")
    effort: str = Field(description="low | medium | high | xhigh | max")
    env: dict[str, str] = Field(
        description="Complete environment of the Claude Code process (nothing is inherited)."
    )
    resume: str | None = Field(default=None, description="Session id to resume.")
    output_schema: JsonDict | None = Field(
        default=None, description="AgentOutput JSON schema for SDK structured output."
    )


class ClaudeClient(Protocol):
    """What `ClaudeAdapter` needs from the Claude Agent SDK."""

    def query(
        self,
        prompt: str,
        options: ClaudeQueryOptions,
        can_use_tool: Callable[[str, JsonDict], Awaitable[JsonDict]],
    ) -> AsyncIterator[SdkMessage]:
        """Run one query; ``can_use_tool`` decides every tool call (ADR-0014 result shape)."""
        ...

    async def available(self) -> tuple[bool, str]:
        """Whether the SDK and the Claude Code CLI are usable, with a detail text."""
        ...

    async def interrupt(self, session_id: str) -> None:
        """Interrupt the active query of ``session_id``; unknown sessions are ignored."""
        ...


class SdkClaudeClient:
    """`ClaudeClient` backed by `claude_agent_sdk.ClaudeSDKClient`."""

    def __init__(
        self,
        *,
        probe: CommandProbe | None = None,
        transport_factory: TransportFactory = scrubbed_transport,
    ) -> None:
        """Start with no active sessions.

        Args:
            probe: Runs ``claude --version`` for `available`; without it the CLI is only
                located.
            transport_factory: Transport of every query; the default launches the CLI with
                exactly ``ClaudeQueryOptions.env`` (the SDK's own transport would merge it
                onto the kernel's environment, E02-S01).
        """
        self._active: dict[str, Any] = {}
        self._probe = probe
        self._transport_factory = transport_factory

    async def query(
        self,
        prompt: str,
        options: ClaudeQueryOptions,
        can_use_tool: Callable[[str, JsonDict], Awaitable[JsonDict]],
    ) -> AsyncIterator[SdkMessage]:
        """Stream the SDK messages of one query.

        Raises:
            ConfigError: ``claude-agent-sdk`` is not installed.
        """
        sdk = _load_sdk()

        async def callback(tool_name: str, tool_input: JsonDict, context: object) -> object:
            del context
            result = await can_use_tool(tool_name, tool_input)
            if result.get("behavior") == "allow":
                return sdk.PermissionResultAllow(updated_input=result.get("updatedInput"))
            return sdk.PermissionResultDeny(message=str(result.get("message", "")), interrupt=False)

        sdk_options = _sdk_options(sdk, options, callback)
        transport = self._transport_factory(sdk_options, options.env)
        client = sdk.ClaudeSDKClient(options=sdk_options, transport=transport)
        session_id: str | None = None
        await client.connect()
        try:
            await client.query(prompt)
            async for message in client.receive_response():
                found = _session_id_of(message)
                if session_id is None and found is not None:
                    session_id = found
                    self._active[session_id] = client
                yield message
        finally:
            if session_id is not None:
                self._active.pop(session_id, None)
            await client.disconnect()

    async def available(self) -> tuple[bool, str]:
        """SDK importable, Claude Code CLI found and ``--version`` succeeds.

        The version probe runs through the injected `CommandProbe` (ARCHITECTURE §2.3: only
        `walk.integrations.subprocess` and the codex launcher spawn processes); without one the
        CLI is only located. Authentication cannot be proven without a billable call
        (ADR-0014); a logged-out CLI surfaces as a provider error on the first run.
        """
        try:
            sdk = _load_sdk()
        except ConfigError as exc:
            return False, exc.message
        cli = _find_cli(sdk)
        if cli is None:
            return False, "Claude Code CLI not found (bundled with the SDK or on PATH)"
        if self._probe is None:
            return True, f"{cli} (version not probed)"
        exit_code, stdout, stderr = await self._probe(_version_argv(cli))
        if exit_code != 0:
            return False, f"{cli} --version failed with exit code {exit_code}: {stderr.strip()}"
        return True, stdout.strip()

    async def interrupt(self, session_id: str) -> None:
        """Interrupt the active query of ``session_id``."""
        client = self._active.get(session_id)
        if client is not None:
            await client.interrupt()


def _load_sdk() -> ModuleType:
    try:
        return importlib.import_module(_SDK_MODULE)
    except ImportError as exc:
        msg = "claude-agent-sdk is not installed (install the 'claude' extra)"
        raise ConfigError(msg, detail={"module": _SDK_MODULE}) from exc


def _sdk_options(
    sdk: ModuleType,
    options: ClaudeQueryOptions,
    can_use_tool: Callable[[str, JsonDict, object], Awaitable[object]],
) -> object:
    output_format = (
        {"type": "json_schema", "schema": options.output_schema}
        if options.output_schema is not None
        else None
    )
    return sdk.ClaudeAgentOptions(
        cwd=options.cwd,
        model=options.model.split("/", 1)[1],
        tools=list(options.tools),
        allowed_tools=list(options.allowed_tools),
        permission_mode=options.permission_mode,
        can_use_tool=can_use_tool,
        max_turns=options.max_turns,
        system_prompt=options.system_prompt,
        effort=options.effort,
        env=dict(options.env),
        resume=options.resume,
        output_format=output_format,
        # No user/project/local settings: their permission allow-rules would pre-approve
        # tools and bypass can_use_tool, which ADR-0014 requires for every call.
        setting_sources=[],
    )


def _session_id_of(message: object) -> str | None:
    session_id = getattr(message, "session_id", None)
    if isinstance(session_id, str) and session_id:
        return session_id
    data = getattr(message, "data", None)
    if getattr(message, "subtype", None) == _INIT_SUBTYPE and isinstance(data, dict):
        found = data.get("session_id")
        if isinstance(found, str) and found:
            return found
    return None


def _find_cli(sdk: ModuleType) -> str | None:
    sdk_file = getattr(sdk, "__file__", None)
    if sdk_file is not None:
        bundled = Path(sdk_file).parent / "_bundled" / _CLI_NAME
        if bundled.is_file():
            return str(bundled)
    return shutil.which("claude")


def _version_argv(cli: str) -> list[str]:
    return [cli, "--version"]
