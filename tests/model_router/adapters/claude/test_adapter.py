import asyncio
import dataclasses
import functools
import importlib
import json
import shutil
import sys
import types
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import walk.agents
import walk.model_router
from tests.fakes.fake_claude_client import FakeClaudeClient, ResultMessage, scripted_messages
from tests.fakes.fake_clock import FakeClock
from walk.agents import (
    AgentInput,
    AgentOutput,
    AgentOutputStatus,
    ConstitutionLoader,
    ExpectedOutput,
)
from walk.common.clock import SystemClock
from walk.common.enums import Effort
from walk.common.errors import (
    ConfigError,
    OutputInvalid,
    ProviderUnavailable,
    RateLimited,
    Timeout,
    WalkError,
)
from walk.common.roles import AgentRole
from walk.context import ContextBundle, ContextRequest
from walk.integrations import AsyncioSubprocessRunner
from walk.model_router import (
    OUTPUT_RELATIVE_PATH,
    AgentEvent,
    AgentEventKind,
    ModelAdapter,
    ModelDescriptor,
    NotResumable,
    ProviderSessionRef,
    RunSession,
    load_models_config,
)
from walk.model_router.adapters.claude import ClaudeAdapter
from walk.model_router.adapters.claude.client import (
    SDK_OPTIONS,
    ClaudeClient,
    ClaudeQueryOptions,
    SdkClaudeClient,
    missing_sdk_options,
)
from walk.model_router.adapters.claude.projector import ClaudeSkillProjector
from walk.permissions import PermissionDecision, PermissionEffect, ToolCallRequest
from walk.tools import ToolKind, ToolSpec
from walk.workflow import Story, StoryContract, WorkItemState

DEFAULTS = Path(walk.agents.__file__).resolve().parent / "defaults"
MODELS = Path(walk.model_router.__file__).resolve().parent / "defaults" / "models.yaml"
AT = datetime(2026, 1, 1, tzinfo=UTC)
RUN = "RUN-01J00000000000000000000000"
OPUS = "claude/claude-opus-5-5"
K = AgentEventKind
DONE = AgentOutput(status=AgentOutputStatus.COMPLETED, result="done", no_context_change_reason="x")
SYSTEM_PROMPT = "You are the senior developer."
USER_MESSAGE = "Implement STORY-0001."

Authorizer = Callable[[ToolCallRequest], Awaitable[PermissionDecision]]


def _opus() -> ModelDescriptor:
    return load_models_config(MODELS, None).models[OPUS]


def _input() -> AgentInput:
    constitution = ConstitutionLoader(DEFAULTS, None).load(AgentRole.SENIOR_DEV)
    story = Story(
        id="STORY-0001",
        project_key="DEMO",
        title="Run",
        contract=StoryContract(goal="Run"),
        created_at=AT,
        updated_at=AT,
    )
    request = ContextRequest(
        work_item_id="STORY-0001", role=AgentRole.SENIOR_DEV, effort=Effort.LOW, token_budget=1000
    )
    return AgentInput(
        run_id=RUN,
        role=AgentRole.SENIOR_DEV,
        constitution=constitution,
        authority=constitution.authority,
        task=story,
        workflow_state=WorkItemState.READY,
        phase=None,
        context=ContextBundle(
            request=request,
            items=[],
            total_tokens_estimate=0,
            excluded_count=0,
            built_at=AT,
            head_commit="3f9c2e1",
        ),
        approved_artifacts=[],
        decisions=[],
        skills=[],
        allowed_tools=[],
        permissions=[],
        budget=[],
        effort=Effort.LOW,
        required_evidence=[],
        expected_output=ExpectedOutput(
            status_options=[AgentOutputStatus.COMPLETED], deliverables=[], required_evidence=[]
        ),
        worktree_path="unused",
        branch="feat/x",
    )


class _Authorizer:
    def __init__(self, effect: PermissionEffect = PermissionEffect.ALLOW) -> None:
        self.effect = effect
        self.requests: list[ToolCallRequest] = []

    async def __call__(self, request: ToolCallRequest) -> PermissionDecision:
        self.requests.append(request)
        reason = "allowed" if self.effect is PermissionEffect.ALLOW else "rm -rf is forbidden"
        return PermissionDecision(effect=self.effect, matched_rule=None, reason=reason)


def _session(
    worktree: Path,
    authorizer: Authorizer,
    *,
    timeout_s: int = 600,
    effort: Effort = Effort.HIGH,
) -> RunSession:
    tools = [
        ToolSpec(name="edit", kind=ToolKind.PROVIDER_NATIVE, description="Edit"),
        ToolSpec(name="bash", kind=ToolKind.PROVIDER_NATIVE, description="Shell"),
        ToolSpec(name="git.commit", kind=ToolKind.KERNEL, description="Commit"),
        ToolSpec(name="webfetch", kind=ToolKind.PROVIDER_NATIVE, description="Not mapped"),
    ]
    return RunSession(
        run_id=RUN,
        worktree_path=str(worktree),
        allowed_tools=tools,
        permission_authorizer=authorizer,
        effort=effort,
        model_id=OPUS,
        max_turns=77,
        timeout_s=timeout_s,
        env_allowlist={"PATH": "/usr/bin"},
        output_path=str(worktree / OUTPUT_RELATIVE_PATH),
    )


def _adapter(
    client: ClaudeClient,
    clock: FakeClock,
    *,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> ClaudeAdapter:
    extra: dict[str, Any] = {} if sleep is None else {"sleep": sleep}
    return ClaudeAdapter(
        client,
        [_opus()],
        clock,
        system_prompt_builder=lambda _: SYSTEM_PROMPT,
        user_message_builder=lambda _: USER_MESSAGE,
        **extra,
    )


def _write_output(worktree: Path, data: str) -> None:
    path = worktree / OUTPUT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


async def _collect(stream: AsyncIterator[AgentEvent]) -> list[AgentEvent]:
    return [event async for event in stream]


async def test_run_translates_sdk_stream(tmp_path: Path, fake_clock: FakeClock) -> None:
    client = FakeClaudeClient()
    adapter = _adapter(client, fake_clock)
    authorizer = _Authorizer()
    _write_output(tmp_path, DONE.model_dump_json())

    events = await _collect(adapter.run(_input(), _session(tmp_path, authorizer)))

    assert [e.kind for e in events] == [
        K.STARTED,
        K.TEXT,
        K.TOOL_CALL_REQUESTED,
        K.TOOL_CALL_RESULT,
        K.USAGE,
        K.FINAL_OUTPUT,
        K.ENDED,
    ]
    assert all(e.run_id == RUN for e in events)
    assert events[1].text == "Editing the file."
    requested = events[2].tool_call
    assert requested is not None
    assert requested.tool == "edit"
    assert requested.paths == ["src/A.cs"]
    assert requested.role is AgentRole.SENIOR_DEV
    assert requested.worktree_path == str(tmp_path)
    assert authorizer.requests == [requested]
    assert client.permission_results == [{"behavior": "allow", "updatedInput": None}]
    assert events[5].output == DONE
    usage = adapter.usage(RUN)
    assert usage == events[4].usage
    assert usage.output_tokens == 200


async def test_run_builds_restricted_query_options(tmp_path: Path, fake_clock: FakeClock) -> None:
    client = FakeClaudeClient()
    adapter = _adapter(client, fake_clock)
    _write_output(tmp_path, DONE.model_dump_json())

    await _collect(adapter.run(_input(), _session(tmp_path, _Authorizer())))

    prompt, options = client.queries[0]
    assert prompt == USER_MESSAGE
    assert options.cwd == str(tmp_path)
    assert options.model == OPUS
    assert options.tools == ["Edit", "MultiEdit", "Bash"]
    assert options.allowed_tools == []
    assert options.permission_mode == "default"
    assert options.max_turns == 77
    assert options.system_prompt == SYSTEM_PROMPT
    assert options.effort == "high"
    assert options.env == {"PATH": "/usr/bin"}
    assert options.resume is None
    assert options.output_schema == AgentOutput.model_json_schema()


async def test_can_use_tool_denies_through_authorizer(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    messages = scripted_messages(
        tool_name="Bash",
        tool_input={"command": "rm -rf /"},
        tool_output="denied by the kernel",
        tool_error=True,
        structured_output=DONE.model_dump(mode="json"),
    )
    client = FakeClaudeClient(messages)
    authorizer = _Authorizer(PermissionEffect.DENY)

    events = await _collect(
        _adapter(client, fake_clock).run(_input(), _session(tmp_path, authorizer))
    )

    assert client.permission_results == [{"behavior": "deny", "message": "rm -rf is forbidden"}]
    requested = [e for e in events if e.kind is K.TOOL_CALL_REQUESTED]
    assert len(requested) == 1
    assert requested[0].tool_call is not None
    assert requested[0].tool_call.command == "rm -rf /"
    assert requested[0].tool_call.tool == "bash"
    result = next(e for e in events if e.kind is K.TOOL_CALL_RESULT)
    assert result.tool_result is not None
    assert result.tool_result["ok"] is False


async def test_authorizer_failure_denies_and_fails_run(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    async def broken(request: ToolCallRequest) -> PermissionDecision:
        del request
        msg = "permission store unavailable"
        raise ProviderUnavailable(msg)

    client = FakeClaudeClient()
    adapter = _adapter(client, fake_clock)
    stream = adapter.run(_input(), _session(tmp_path, broken))

    with pytest.raises(ProviderUnavailable, match="permission store unavailable"):
        await _collect(stream)
    assert client.permission_results[0]["behavior"] == "deny"


async def test_missing_output_yields_repairable_final_output(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    client = FakeClaudeClient()
    events = await _collect(
        _adapter(client, fake_clock).run(_input(), _session(tmp_path, _Authorizer()))
    )

    final = next(e for e in events if e.kind is K.FINAL_OUTPUT)
    assert final.output is None
    assert final.error is not None
    assert "output.json" in final.error
    assert events[-1].kind is K.ENDED


class CLINotFoundError(Exception):
    """Named like the SDK's error; the adapter classifies by class name."""


class ProcessError(Exception):
    """Named like the SDK's error."""


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (ConnectionError("connection refused"), ProviderUnavailable),
        (RuntimeError("API Error: 429 Too Many Requests"), RateLimited),
        (RuntimeError("rate limit exceeded"), RateLimited),
        (RuntimeError("API Error: overloaded_error"), ProviderUnavailable),
        (RuntimeError("API Error: 503 Service Unavailable"), ProviderUnavailable),
        (ProcessError("Command failed with exit code 1"), ProviderUnavailable),
        (CLINotFoundError("Claude Code not found"), ConfigError),
        (FileNotFoundError("claude"), ConfigError),
        (Timeout("already typed"), Timeout),
        (ValueError("programming error"), ValueError),
    ],
)
async def test_client_errors_are_mapped(
    tmp_path: Path, fake_clock: FakeClock, raised: Exception, expected: type[Exception]
) -> None:
    client = FakeClaudeClient(error=raised, error_at=1)
    stream = _adapter(client, fake_clock).run(_input(), _session(tmp_path, _Authorizer()))

    with pytest.raises(expected) as caught:
        await _collect(stream)
    if isinstance(caught.value, WalkError) and not isinstance(raised, WalkError):
        assert caught.value.__cause__ is raised
        assert caught.value.detail["error_type"] == type(raised).__name__


async def test_timeout_interrupts_and_raises(tmp_path: Path, fake_clock: FakeClock) -> None:
    sleeps: list[float] = []

    async def advance(seconds: float) -> None:
        sleeps.append(seconds)
        fake_clock.advance(seconds)

    client = FakeClaudeClient(hang_at=1)  # yields init (session known), then never again
    adapter = _adapter(client, fake_clock, sleep=advance)
    stream = adapter.run(_input(), _session(tmp_path, _Authorizer(), timeout_s=1))

    first = await anext(stream)
    with pytest.raises(Timeout) as caught:
        await anext(stream)

    assert first.kind is K.STARTED
    assert client.interrupts == ["sess-1"]
    assert caught.value.detail["timeout_s"] == 1
    assert sleeps


async def test_timeout_before_init_raises_without_interrupt(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    async def advance(seconds: float) -> None:
        fake_clock.advance(seconds)

    client = FakeClaudeClient(hang_at=0)
    adapter = _adapter(client, fake_clock, sleep=advance)

    with pytest.raises(Timeout):
        await _collect(adapter.run(_input(), _session(tmp_path, _Authorizer(), timeout_s=1)))
    assert client.interrupts == []


class _BrokenInterruptClient(FakeClaudeClient):
    async def interrupt(self, session_id: str) -> None:
        msg = f"cannot interrupt {session_id}"
        raise RuntimeError(msg)


async def test_interrupt_failure_does_not_mask_timeout(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    async def advance(seconds: float) -> None:
        fake_clock.advance(seconds)

    adapter = _adapter(_BrokenInterruptClient(hang_at=1), fake_clock, sleep=advance)
    with pytest.raises(Timeout):
        await _collect(adapter.run(_input(), _session(tmp_path, _Authorizer(), timeout_s=1)))


async def test_consumer_cancellation_stops_the_stream(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    client = FakeClaudeClient(hang_at=1)
    stream = _adapter(client, fake_clock).run(_input(), _session(tmp_path, _Authorizer()))
    await anext(stream)
    waiting = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0)

    waiting.cancel()

    with pytest.raises(asyncio.CancelledError):
        await waiting
    await stream.aclose()  # type: ignore[attr-defined]  # run() returns an async generator


async def test_resume_passes_session_id_or_raises(tmp_path: Path, fake_clock: FakeClock) -> None:
    client = FakeClaudeClient(scripted_messages(structured_output=DONE.model_dump(mode="json")))
    adapter = _adapter(client, fake_clock)
    session = _session(tmp_path, _Authorizer())
    events = await _collect(adapter.run(_input(), session))
    ref = events[0].session
    assert ref is not None

    resumed = await _collect(adapter.resume(ref, "Fix the failing test.", session))

    prompt, options = client.queries[1]
    assert prompt == "Fix the failing test."
    assert options.resume == ref.session_id
    assert options.system_prompt == SYSTEM_PROMPT
    assert resumed[-1].kind is K.ENDED
    assert adapter.usage(RUN).output_tokens == 400  # cumulative over run and resume

    with pytest.raises(NotResumable):
        adapter.resume(
            ProviderSessionRef(provider="codex", session_id="t", resumable=True), "x", session
        )
    with pytest.raises(NotResumable):
        adapter.resume(ref.model_copy(update={"resumable": False}), "x", session)
    with pytest.raises(NotResumable, match="unknown"):
        adapter.resume(ref.model_copy(update={"session_id": "other"}), "x", session)


async def test_health_is_cached(fake_clock: FakeClock) -> None:
    client = FakeClaudeClient(available=(False, "Claude Code CLI not found"))
    adapter = _adapter(client, fake_clock)

    first = await adapter.health()
    fake_clock.advance(59)
    second = await adapter.health()

    assert client.available_calls == 1
    assert first == second
    assert first.ok is False
    assert first.provider == "claude"
    assert first.detail == "Claude Code CLI not found"
    fake_clock.advance(1)
    await adapter.health()
    assert client.available_calls == 2


async def test_cancel_ends_stream_with_ended(tmp_path: Path, fake_clock: FakeClock) -> None:
    client = FakeClaudeClient(hang_at=1)
    adapter = _adapter(client, fake_clock)
    stream = adapter.run(_input(), _session(tmp_path, _Authorizer()))

    first = await anext(stream)
    await adapter.cancel(RUN)
    rest = await _collect(stream)

    assert first.kind is K.STARTED
    assert [e.kind for e in rest] == [K.ENDED]
    assert client.interrupts == ["sess-1"]
    await adapter.cancel("RUN-01J99999999999999999999999")  # unknown run: no-op


async def test_stream_without_result_is_provider_unavailable(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    client = FakeClaudeClient(scripted_messages()[:2])
    stream = _adapter(client, fake_clock).run(_input(), _session(tmp_path, _Authorizer()))
    with pytest.raises(ProviderUnavailable, match="without a result"):
        await _collect(stream)


async def test_adapter_surface(tmp_path: Path, fake_clock: FakeClock) -> None:
    adapter: ModelAdapter = _adapter(FakeClaudeClient(), fake_clock)
    assert adapter.provider == "claude"
    assert [d.id for d in adapter.descriptors()] == [OPUS]
    assert adapter.map_effort(Effort.VERY_HIGH, OPUS).params == {
        "effort": "xhigh",
        "max_turns": 300,
    }
    assert isinstance(adapter.skill_projector(), ClaudeSkillProjector)
    assert adapter.parse_output(DONE.model_dump_json()) == DONE
    with pytest.raises(OutputInvalid):
        adapter.parse_output('{"status": "BOGUS"}')
    assert adapter.usage("RUN-01J99999999999999999999999").input_tokens == 0
    with pytest.raises(ConfigError):
        adapter.map_effort(Effort.LOW, "claude/unknown")
    bad_session = _session(tmp_path, _Authorizer()).model_copy(update={"model_id": "codex/x"})
    with pytest.raises(ConfigError, match="not served"):
        adapter.run(_input(), bad_session)


def test_module_imports_without_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", None)  # import now raises ImportError
    for name in list(sys.modules):
        if name.startswith("walk.model_router.adapters.claude"):
            monkeypatch.delitem(sys.modules, name)

    module = importlib.import_module("walk.model_router.adapters.claude.adapter")

    assert module.ClaudeAdapter.provider == "claude"


async def test_sdk_client_without_sdk_reports_and_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", None)
    client = SdkClaudeClient()

    ok, detail = await client.available()
    assert ok is False
    assert "claude-agent-sdk" in detail
    options = ClaudeQueryOptions(
        cwd=".",
        model=OPUS,
        tools=[],
        allowed_tools=[],
        permission_mode="default",
        max_turns=1,
        system_prompt="",
        effort="low",
        env={},
    )

    async def allow(name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        del name, tool_input
        return {"behavior": "allow", "updatedInput": None}

    with pytest.raises(ConfigError, match="claude-agent-sdk"):
        await anext(client.query("hi", options, allow))
    await client.interrupt("unknown")  # nothing active: no-op


class _StubSdkClient:
    """Stand-in `claude_agent_sdk.ClaudeSDKClient`; records what `SdkClaudeClient` does."""

    def __init__(
        self, record: dict[str, Any], *, options: types.SimpleNamespace, transport: object
    ) -> None:
        self.record = record
        self.options = options
        self.transport = transport
        record["client"] = self
        record["calls"] = []

    async def connect(self) -> None:
        self.record["calls"].append("connect")

    async def query(self, prompt: str) -> None:
        self.record["calls"].append(("query", prompt))

    async def receive_response(self) -> AsyncIterator[object]:
        yield types.SimpleNamespace(subtype="status", data={})
        yield types.SimpleNamespace(subtype="init", data={"session_id": "sess-9"})
        sdk_client = self.record["sdk_client"]
        self.record["active_during_stream"] = dict(sdk_client._active)  # noqa: SLF001 - asserting the private session map
        callback = self.options.can_use_tool
        self.record["allow"] = await callback("Edit", {"file_path": "a"}, None)
        self.record["deny"] = await callback("Bash", {"command": "rm"}, None)
        yield ResultMessage(session_id="sess-9")

    async def interrupt(self) -> None:
        self.record["calls"].append("interrupt")

    async def disconnect(self) -> None:
        self.record["calls"].append("disconnect")


def _stub_allow(updated_input: dict[str, Any] | None = None) -> types.SimpleNamespace:
    return types.SimpleNamespace(updated_input=updated_input)


def _stub_deny(message: str, *, interrupt: bool = False) -> types.SimpleNamespace:
    return types.SimpleNamespace(message=message, interrupt=interrupt)


def _stub_transport(record: dict[str, Any]) -> Callable[[Any, Mapping[str, str]], object]:
    """A transport factory that records its arguments instead of preparing a CLI process."""

    def build(sdk_options: Any, env: Mapping[str, str]) -> object:
        transport = types.SimpleNamespace(options=sdk_options, env=dict(env))
        record["transport"] = transport
        return transport

    return build


def _stub_sdk(tmp_path: Path, record: dict[str, Any]) -> types.ModuleType:
    """A stand-in `claude_agent_sdk` with the attributes `SdkClaudeClient` uses."""
    module = types.ModuleType("claude_agent_sdk")
    module.__file__ = str(tmp_path / "claude_agent_sdk" / "__init__.py")
    module.ClaudeAgentOptions = types.SimpleNamespace  # type: ignore[attr-defined]  # stub module attribute
    module.PermissionResultAllow = _stub_allow  # type: ignore[attr-defined]  # stub module attribute
    module.PermissionResultDeny = _stub_deny  # type: ignore[attr-defined]  # stub module attribute
    module.ClaudeSDKClient = functools.partial(_StubSdkClient, record)  # type: ignore[attr-defined]  # stub module attribute
    return module


async def test_sdk_client_maps_options_and_permission_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record: dict[str, Any] = {}
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", _stub_sdk(tmp_path, record))
    client = SdkClaudeClient(transport_factory=_stub_transport(record))
    record["sdk_client"] = client
    options = ClaudeQueryOptions(
        cwd=str(tmp_path),
        model=OPUS,
        tools=["Edit"],
        allowed_tools=[],
        permission_mode="default",
        max_turns=9,
        system_prompt="sys",
        effort="high",
        env={"PATH": "x"},
        resume="sess-0",
        output_schema={"type": "object"},
    )

    async def decide(name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        del tool_input
        if name == "Edit":
            return {"behavior": "allow", "updatedInput": None}
        return {"behavior": "deny", "message": "no shell"}

    messages = [m async for m in client.query("go", options, decide)]

    assert len(messages) == 3
    sdk_options = record["client"].options
    assert sdk_options.model == "claude-opus-5-5"
    assert sdk_options.tools == ["Edit"]
    assert sdk_options.allowed_tools == []
    assert sdk_options.permission_mode == "default"
    assert sdk_options.cwd == str(tmp_path)
    assert sdk_options.max_turns == 9
    assert sdk_options.effort == "high"
    assert sdk_options.resume == "sess-0"
    assert sdk_options.env == {"PATH": "x"}
    assert sdk_options.output_format == {"type": "json_schema", "schema": {"type": "object"}}
    assert sdk_options.setting_sources == []
    assert record["client"].transport is record["transport"]
    assert record["transport"].options is sdk_options
    assert record["transport"].env == {"PATH": "x"}
    assert record["allow"].updated_input is None
    assert record["deny"].message == "no shell"
    assert record["deny"].interrupt is False
    assert record["calls"] == ["connect", ("query", "go"), "disconnect"]
    assert "sess-9" in record["active_during_stream"]
    assert client._active == {}  # noqa: SLF001 - session map is cleared after the stream


async def test_sdk_client_interrupts_active_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record: dict[str, Any] = {}
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", _stub_sdk(tmp_path, record))
    client = SdkClaudeClient(transport_factory=_stub_transport(record))
    record["sdk_client"] = client
    options = ClaudeQueryOptions(
        cwd=".",
        model=OPUS,
        tools=[],
        allowed_tools=[],
        permission_mode="default",
        max_turns=1,
        system_prompt="",
        effort="low",
        env={},
    )

    async def allow(name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        del name, tool_input
        return {"behavior": "allow", "updatedInput": None}

    stream = client.query("go", options, allow)
    await anext(stream)
    await anext(stream)
    await client.interrupt("sess-9")
    assert "interrupt" in record["calls"]
    await stream.aclose()  # type: ignore[attr-defined]  # SdkClaudeClient.query is an async generator


async def _probe(argv: list[str]) -> tuple[int, str, str]:
    result = await AsyncioSubprocessRunner().run(argv, timeout_s=30)
    return result.exit_code, result.stdout, result.stderr


async def test_sdk_client_available_checks_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_which = shutil.which
    record: dict[str, Any] = {}
    stub = _stub_sdk(tmp_path, record)
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", stub)
    client_module = importlib.import_module("walk.model_router.adapters.claude.client")

    monkeypatch.setattr(client_module.shutil, "which", lambda _: None)
    ok, detail = await SdkClaudeClient(probe=_probe).available()
    assert ok is False
    assert "not found" in detail

    def which(name: str, path: str | None = None) -> str | None:
        # Global patch: answer only the CLI lookup; the probe runner resolves through here too.
        return sys.executable if name == "claude" else real_which(name, path=path)

    monkeypatch.setattr(client_module.shutil, "which", which)
    ok, detail = await SdkClaudeClient(probe=_probe).available()
    assert ok is True
    assert "Python" in detail
    ok, detail = await SdkClaudeClient().available()
    assert ok is True
    assert detail == f"{sys.executable} (version not probed)"

    failing = tmp_path / "failing.py"
    failing.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    monkeypatch.setattr(client_module, "_version_argv", lambda _cli: [sys.executable, str(failing)])
    ok, detail = await SdkClaudeClient(probe=_probe).available()
    assert ok is False
    assert "exit code 3" in detail

    bundled = tmp_path / "claude_agent_sdk" / "_bundled" / client_module._CLI_NAME  # noqa: SLF001 - platform file name
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b"")
    seen: list[str] = []

    def version_argv(cli: str) -> list[str]:
        seen.append(cli)
        return [sys.executable, "--version"]

    monkeypatch.setattr(client_module, "_version_argv", version_argv)
    ok, _ = await SdkClaudeClient(probe=_probe).available()
    assert ok is True
    assert seen == [str(bundled)]

    missing = str(tmp_path / "no-such-cli.exe")
    monkeypatch.setattr(client_module, "_version_argv", lambda _cli: [missing, "--version"])
    ok, detail = await SdkClaudeClient(probe=_probe).available()
    assert ok is False
    assert "exit code 127" in detail


@pytest.mark.integration
async def test_real_sdk_round_trip(tmp_path: Path) -> None:
    pytest.importorskip("claude_agent_sdk")
    adapter = ClaudeAdapter(
        SdkClaudeClient(),
        [_opus()],
        SystemClock(),
        system_prompt_builder=lambda _: "Answer with the structured output only.",
        user_message_builder=lambda _: (
            'Return {"status": "COMPLETED", "result": "ok", "no_context_change_reason": "probe"}.'
        ),
    )
    health = await adapter.health()
    assert health.ok, health.detail
    session = _session(tmp_path, _Authorizer(PermissionEffect.DENY), effort=Effort.LOW)

    events = await _collect(adapter.run(_input(), session))

    print(json.dumps([e.kind.value for e in events]))  # noqa: T201 - transcript for ADR-0014 evidence
    assert events[0].kind is K.STARTED
    assert any(e.kind is K.USAGE for e in events)
    assert events[-1].kind in {K.ENDED, K.ERROR}


def test_missing_sdk_options_introspects_claude_agent_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    present = [name for name in SDK_OPTIONS if name != "output_format"]
    options_class = dataclasses.make_dataclass("ClaudeAgentOptions", [*present, "extra"])
    stub = types.ModuleType("claude_agent_sdk")
    stub.ClaudeAgentOptions = options_class  # type: ignore[attr-defined]  # stub module attribute
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", stub)

    assert missing_sdk_options() == ["output_format"]

    monkeypatch.setitem(sys.modules, "claude_agent_sdk", None)
    with pytest.raises(ConfigError, match="claude-agent-sdk"):
        missing_sdk_options()
