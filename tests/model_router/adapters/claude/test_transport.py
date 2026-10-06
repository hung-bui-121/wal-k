import dataclasses
import importlib
import types
from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest

from walk.model_router.adapters.claude.transport import TRANSPORT_MODULE, scrubbed_transport

PIPE = -1


@dataclasses.dataclass(frozen=True)
class _Options:
    """The `ClaudeAgentOptions` fields the transport reads."""

    cwd: str
    env: dict[str, str]
    can_use_tool: Callable[..., Any] | None = None
    permission_prompt_tool_name: str | None = None


class _FakeProcess:
    def __init__(self) -> None:
        self.stdout = object()
        self.stdin = object()


class _Stream:
    def __init__(self, inner: object) -> None:
        self.inner = inner


class _BaseTransport:
    """Stand-in `SubprocessCLITransport` with the private state the subclass relies on."""

    def __init__(self, prompt: AsyncIterator[dict[str, Any]], options: _Options) -> None:
        self._prompt = prompt
        self._options = options
        self._cli_path: str | None = None
        self._cwd: str | None = options.cwd
        self._process: _FakeProcess | None = None
        self._stdout_stream: _Stream | None = None
        self._stdin_stream: _Stream | None = None
        self._ready = False
        self.rejected: list[str] = []

    def _find_cli(self) -> str:
        return "/opt/claude/claude"

    def _reject_windows_batch_cli(self, cli_path: str) -> None:
        self.rejected.append(cli_path)

    def _build_command(self) -> list[str]:
        return [str(self._cli_path), "--input-format", "stream-json"]

    def is_ready(self) -> bool:
        return self._ready


def _module(spawned: list[dict[str, Any]]) -> types.ModuleType:
    async def open_process(command: list[str], **kwargs: Any) -> _FakeProcess:
        spawned.append({"command": command, **kwargs})
        return _FakeProcess()

    async def run_sync(func: Callable[[], str]) -> str:
        return func()

    module = types.ModuleType("fake_subprocess_cli")
    module.SubprocessCLITransport = _BaseTransport  # type: ignore[attr-defined]  # stub module attribute
    module.anyio = types.SimpleNamespace(  # type: ignore[attr-defined]  # stub module attribute
        open_process=open_process, to_thread=types.SimpleNamespace(run_sync=run_sync)
    )
    module.PIPE = PIPE  # type: ignore[attr-defined]  # stub module attribute
    module.TextReceiveStream = _Stream  # type: ignore[attr-defined]  # stub module attribute
    module.TextSendStream = _Stream  # type: ignore[attr-defined]  # stub module attribute
    return module


async def _deny(*args: object) -> object:
    del args
    return None


async def test_claude_transport_env_is_scrubbed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sentinel-secret")
    monkeypatch.setenv("JIRA_API_TOKEN", "sentinel-jira")
    spawned: list[dict[str, Any]] = []
    options = _Options(cwd="/work/tree", env={"PATH": "/usr/bin"}, can_use_tool=_deny)

    transport: Any = scrubbed_transport(options, {"PATH": "/usr/bin"}, module=_module(spawned))
    await transport.connect()

    assert len(spawned) == 1
    assert spawned[0]["env"] == {"PATH": "/usr/bin"}
    assert "ANTHROPIC_API_KEY" not in spawned[0]["env"]
    assert spawned[0]["cwd"] == "/work/tree"
    assert spawned[0]["command"][0] == "/opt/claude/claude"
    assert spawned[0]["stdin"] == PIPE
    assert spawned[0]["stdout"] == PIPE
    assert transport.rejected == ["/opt/claude/claude"]
    assert transport.is_ready()


async def test_claude_transport_routes_permission_prompts_over_stdio() -> None:
    spawned: list[dict[str, Any]] = []
    with_callback = _Options(cwd="/w", env={}, can_use_tool=_deny)
    without_callback = _Options(cwd="/w", env={})

    first: Any = scrubbed_transport(with_callback, {}, module=_module(spawned))
    second: Any = scrubbed_transport(without_callback, {}, module=_module(spawned))

    assert first._options.permission_prompt_tool_name == "stdio"  # noqa: SLF001 - the SDK's own field
    assert second._options.permission_prompt_tool_name is None  # noqa: SLF001 - the SDK's own field
    assert with_callback.permission_prompt_tool_name is None


async def test_claude_transport_connects_once_and_copies_env() -> None:
    spawned: list[dict[str, Any]] = []
    env = {"PATH": "/usr/bin"}
    transport: Any = scrubbed_transport(_Options(cwd="/w", env={}), env, module=_module(spawned))
    env["LATE_ADDITION"] = "x"

    await transport.connect()
    await transport.connect()

    assert len(spawned) == 1
    assert spawned[0]["env"] == {"PATH": "/usr/bin"}
    assert [message async for message in transport._prompt] == []  # noqa: SLF001 - SDK field


@pytest.mark.integration
def test_real_sdk_transport_has_the_overridden_members() -> None:
    sdk = pytest.importorskip("claude_agent_sdk")
    module = importlib.import_module(TRANSPORT_MODULE)
    options = sdk.ClaudeAgentOptions(cwd=".", env={"PATH": "x"})

    transport = scrubbed_transport(options, {"PATH": "x"})

    assert isinstance(transport, module.SubprocessCLITransport)
    for name in ("anyio", "PIPE", "TextReceiveStream", "TextSendStream"):
        assert hasattr(module, name), name
    for name in ("_find_cli", "_reject_windows_batch_cli", "_build_command"):
        assert callable(getattr(transport, name)), name
