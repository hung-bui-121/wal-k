import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import tests.fixtures.codex
import walk.agents
import walk.model_router
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_codex_launcher import FakeCodexProcessLauncher
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
    QuotaExhausted,
    RateLimited,
    Timeout,
)
from walk.common.roles import AgentRole
from walk.context import ContextBundle, ContextRequest
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
from walk.model_router.adapters.codex import CodexAdapter
from walk.model_router.adapters.codex.process import AsyncioCodexProcessLauncher
from walk.model_router.adapters.codex.projector import CodexSkillProjector
from walk.model_router.adapters.codex.sandbox import CodexSandboxConfig
from walk.permissions import PermissionDecision, PermissionEffect, ToolCallRequest
from walk.workflow import Story, StoryContract, WorkItemState

DEFAULTS = Path(walk.agents.__file__).resolve().parent / "defaults"
MODELS = Path(walk.model_router.__file__).resolve().parent / "defaults" / "models.yaml"
FIXTURES = Path(tests.fixtures.codex.__file__).resolve().parent
AT = datetime(2026, 1, 1, tzinfo=UTC)
RUN = "RUN-01J00000000000000000000000"
CODEX = "codex/gpt-5-codex"
K = AgentEventKind
DONE = AgentOutput(status=AgentOutputStatus.COMPLETED, result="done", no_context_change_reason="x")
SYSTEM_PROMPT = "You are the senior developer."
USER_MESSAGE = "Implement STORY-0001."
ALLOWLIST = {"PATH": "/usr/bin", "HOME": "/home/agent"}


def _fixture(name: str) -> list[str]:
    return (FIXTURES / name).read_text(encoding="utf-8").splitlines()


def _codex() -> ModelDescriptor:
    return load_models_config(MODELS, None).models[CODEX]


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
        return PermissionDecision(effect=self.effect, matched_rule=None, reason="rule")


def _session(
    worktree: Path,
    authorizer: Callable[[ToolCallRequest], Awaitable[PermissionDecision]] | None = None,
    *,
    timeout_s: int = 600,
) -> RunSession:
    return RunSession(
        run_id=RUN,
        worktree_path=str(worktree),
        allowed_tools=[],
        permission_authorizer=authorizer or _Authorizer(),
        effort=Effort.HIGH,
        model_id=CODEX,
        max_turns=50,
        timeout_s=timeout_s,
        env_allowlist=dict(ALLOWLIST),
        output_path=str(worktree / OUTPUT_RELATIVE_PATH),
    )


def _adapter(
    launcher: FakeCodexProcessLauncher,
    clock: FakeClock,
    *,
    sleep: Callable[[float], Awaitable[None]] | None = None,
    sandbox_factory: Callable[[RunSession], CodexSandboxConfig] | None = None,
) -> CodexAdapter:
    extra: dict[str, Any] = {} if sleep is None else {"sleep": sleep}
    return CodexAdapter(
        launcher,
        [_codex()],
        clock,
        system_prompt_builder=lambda _: SYSTEM_PROMPT,
        user_message_builder=lambda _: USER_MESSAGE,
        sandbox_factory=sandbox_factory,
        **extra,
    )


async def _collect(stream: AsyncIterator[AgentEvent]) -> list[AgentEvent]:
    return [event async for event in stream]


async def test_run_translates_jsonl_stream(tmp_path: Path, fake_clock: FakeClock) -> None:
    launcher = FakeCodexProcessLauncher(_fixture("exec_success.jsonl"))
    adapter = _adapter(launcher, fake_clock)

    events = await _collect(adapter.run(_input(), _session(tmp_path)))

    assert [e.kind for e in events] == [
        K.STARTED,
        K.TEXT,
        K.TOOL_CALL_REQUESTED,
        K.TOOL_CALL_RESULT,
        K.TOOL_CALL_REQUESTED,
        K.TOOL_CALL_RESULT,
        K.USAGE,
        K.FINAL_OUTPUT,
        K.USAGE,
        K.ENDED,
    ]
    assert events[0].session == ProviderSessionRef(
        provider="codex", session_id="thr_1", resumable=True
    )
    final = events[7]
    assert final.output is not None
    assert final.output.result == "tests pass"
    assert events[8].usage == adapter.usage(RUN)

    launch = launcher.launches[0]
    assert launch.argv[:3] == ["codex", "exec", "--json"]
    assert launch.argv[-1] == "-"
    schema_path = tmp_path / ".walk" / "output.schema.json"
    assert ("--output-schema", str(schema_path)) in zip(launch.argv, launch.argv[1:], strict=False)
    assert json.loads(schema_path.read_text(encoding="utf-8")) == AgentOutput.model_json_schema()
    assert launch.stdin_text == f"{SYSTEM_PROMPT}\n\n{USER_MESSAGE}"
    assert (tmp_path / ".walk" / "prompt.md").is_file()


async def test_launch_env_is_exactly_allowlist(
    tmp_path: Path, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = FakeCodexProcessLauncher(_fixture("exec_success.jsonl"))
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")

    await _collect(_adapter(launcher, fake_clock).run(_input(), _session(tmp_path)))

    launch = launcher.launches[0]
    assert launch.env == ALLOWLIST
    assert launch.cwd == str(tmp_path)


async def test_rate_limit_exit_maps_to_rate_limited(tmp_path: Path, fake_clock: FakeClock) -> None:
    launcher = FakeCodexProcessLauncher(
        _fixture("exec_error_rate_limit.jsonl"), exit_code=1, stderr="error: 429 rate limit"
    )
    stream = _adapter(launcher, fake_clock).run(_input(), _session(tmp_path))

    with pytest.raises(RateLimited):
        await _collect(stream)


async def test_quota_exit_maps_to_quota_exhausted(tmp_path: Path, fake_clock: FakeClock) -> None:
    launcher = FakeCodexProcessLauncher(
        _fixture("exec_success.jsonl")[:2], exit_code=1, stderr="You've hit your usage limit."
    )
    with pytest.raises(QuotaExhausted):
        await _collect(_adapter(launcher, fake_clock).run(_input(), _session(tmp_path)))


async def test_unknown_failure_maps_to_provider_unavailable(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    stderr = "x" * 3000 + "\nthread 'main' panicked at sandbox.rs"
    launcher = FakeCodexProcessLauncher(
        _fixture("exec_success.jsonl")[:2], exit_code=101, stderr=stderr
    )

    with pytest.raises(ProviderUnavailable) as caught:
        await _collect(_adapter(launcher, fake_clock).run(_input(), _session(tmp_path)))

    assert caught.value.detail["exit_code"] == 101
    assert caught.value.detail["stderr_tail"].endswith("panicked at sandbox.rs")
    assert len(caught.value.detail["stderr_tail"]) == 2000


async def test_error_event_with_failed_exit_ends_with_error(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    lines = [*_fixture("exec_success.jsonl")[:2], '{"type":"error","message":"model refused"}']
    launcher = FakeCodexProcessLauncher(lines, exit_code=1, stderr="fatal")

    events = await _collect(_adapter(launcher, fake_clock).run(_input(), _session(tmp_path)))

    assert [e.kind for e in events] == [K.STARTED, K.ERROR]
    assert events[-1].error == "model refused"


async def test_missing_binary_is_config_error(tmp_path: Path, fake_clock: FakeClock) -> None:
    launcher = FakeCodexProcessLauncher(launch_error=FileNotFoundError("codex"))
    with pytest.raises(ConfigError, match="codex CLI not found"):
        await _collect(_adapter(launcher, fake_clock).run(_input(), _session(tmp_path)))

    launcher = FakeCodexProcessLauncher(launch_error=PermissionError("access denied"))
    with pytest.raises(ProviderUnavailable, match="could not be started"):
        await _collect(_adapter(launcher, fake_clock).run(_input(), _session(tmp_path)))


async def test_stdout_failure_propagates(tmp_path: Path, fake_clock: FakeClock) -> None:
    launcher = FakeCodexProcessLauncher(
        ["", "not json", *_fixture("exec_success.jsonl")[:1]],
        stdout_error=ConnectionResetError("stdout pipe closed"),
    )
    adapter = _adapter(launcher, fake_clock)
    stream = adapter.run(_input(), _session(tmp_path))

    assert (await anext(stream)).kind is K.STARTED
    with pytest.raises(ConnectionResetError):
        await anext(stream)
    assert launcher.processes[0].killed is True


async def test_consumer_cancellation_kills_process(tmp_path: Path, fake_clock: FakeClock) -> None:
    launcher = FakeCodexProcessLauncher(_fixture("exec_success.jsonl")[:1], hang=True)
    stream = _adapter(launcher, fake_clock).run(_input(), _session(tmp_path))
    await anext(stream)
    waiting = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0)

    waiting.cancel()

    with pytest.raises(asyncio.CancelledError):
        await waiting
    await stream.aclose()  # type: ignore[attr-defined]  # run() returns an async generator
    assert launcher.processes[0].killed is True


async def test_timeout_kills_process(tmp_path: Path, fake_clock: FakeClock) -> None:
    async def advance(seconds: float) -> None:
        fake_clock.advance(seconds)

    launcher = FakeCodexProcessLauncher([], hang=True)
    stream = _adapter(launcher, fake_clock, sleep=advance).run(
        _input(), _session(tmp_path, timeout_s=1)
    )

    with pytest.raises(Timeout) as caught:
        await _collect(stream)

    assert launcher.processes[0].killed is True
    assert caught.value.detail["timeout_s"] == 1


async def test_advisory_deny_is_recorded_not_blocking(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    launcher = FakeCodexProcessLauncher(_fixture("exec_success.jsonl"))
    authorizer = _Authorizer(PermissionEffect.DENY)

    events = await _collect(
        _adapter(launcher, fake_clock).run(_input(), _session(tmp_path, authorizer))
    )

    results = [e for e in events if e.kind is K.TOOL_CALL_RESULT]
    assert len(results) == 2
    for result in results:
        assert result.tool_result is not None
        assert result.tool_result["kernel_decision"] == "DENY"
    assert [r.tool for r in authorizer.requests] == ["bash", "edit"]
    assert events[-1].kind is K.ENDED


async def test_advisory_allow_is_recorded(tmp_path: Path, fake_clock: FakeClock) -> None:
    launcher = FakeCodexProcessLauncher(_fixture("exec_success.jsonl"))
    events = await _collect(_adapter(launcher, fake_clock).run(_input(), _session(tmp_path)))
    result = next(e for e in events if e.kind is K.TOOL_CALL_RESULT)
    assert result.tool_result is not None
    assert result.tool_result["kernel_decision"] == "ALLOW"


async def test_missing_output_yields_repairable_final_output(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    lines = [line for line in _fixture("exec_success.jsonl") if '"agent_message"' not in line]
    launcher = FakeCodexProcessLauncher(lines)

    events = await _collect(_adapter(launcher, fake_clock).run(_input(), _session(tmp_path)))

    final = next(e for e in events if e.kind is K.FINAL_OUTPUT)
    assert final.output is None
    assert final.error is not None
    assert "output.json" in final.error
    assert events[-1].kind is K.ENDED


async def test_output_file_is_the_fallback_channel(tmp_path: Path, fake_clock: FakeClock) -> None:
    lines = [
        '{"type":"thread.started","thread_id":"thr_9"}',
        '{"type":"item.completed","item":{"id":"m","type":"agent_message","text":"Done."}}',
        '{"type":"turn.completed","usage":{"input_tokens":1,"cached_input_tokens":0,"output_tokens":1}}',
    ]
    output = tmp_path / OUTPUT_RELATIVE_PATH
    output.parent.mkdir(parents=True)
    output.write_text(DONE.model_dump_json(), encoding="utf-8")

    events = await _collect(
        _adapter(FakeCodexProcessLauncher(lines), fake_clock).run(_input(), _session(tmp_path))
    )

    final = next(e for e in events if e.kind is K.FINAL_OUTPUT)
    assert final.output == DONE

    output.write_text('{"status": "BOGUS"}', encoding="utf-8")
    events = await _collect(
        _adapter(FakeCodexProcessLauncher(lines), fake_clock).run(_input(), _session(tmp_path))
    )
    final = next(e for e in events if e.kind is K.FINAL_OUTPUT)
    assert final.output is None
    assert final.error is not None
    assert "status" in final.error


async def test_resume_uses_thread_id_or_raises(tmp_path: Path, fake_clock: FakeClock) -> None:
    launcher = FakeCodexProcessLauncher(_fixture("exec_success.jsonl"))
    launcher.queue_script(_fixture("exec_success.jsonl"))
    launcher.queue_script(_fixture("exec_resume.jsonl"))
    adapter = _adapter(launcher, fake_clock)
    session = _session(tmp_path)
    events = await _collect(adapter.run(_input(), session))
    ref = events[0].session
    assert ref is not None

    resumed = await _collect(adapter.resume(ref, "Fix the failing test.", session))

    argv = launcher.launches[1].argv
    assert argv[:5] == ["codex", "exec", "resume", "thr_1", "--json"]
    assert launcher.launches[1].cwd == str(tmp_path)
    assert launcher.launches[1].stdin_text == "Fix the failing test."
    assert [e.kind for e in resumed][-3:] == [K.FINAL_OUTPUT, K.USAGE, K.ENDED]
    final = next(e for e in resumed if e.kind is K.FINAL_OUTPUT)
    assert final.output is not None
    assert final.output.result == "fixed after resume"
    assert adapter.usage(RUN).turns == 2

    with pytest.raises(NotResumable):
        adapter.resume(
            ProviderSessionRef(provider="claude", session_id="s", resumable=True), "x", session
        )
    with pytest.raises(NotResumable):
        adapter.resume(ref.model_copy(update={"resumable": False}), "x", session)
    with pytest.raises(NotResumable, match="unknown"):
        adapter.resume(ref.model_copy(update={"session_id": "thr_other"}), "x", session)


async def test_health_requires_login_and_caches(fake_clock: FakeClock) -> None:
    launcher = FakeCodexProcessLauncher(login=(False, "Not logged in"))
    adapter = _adapter(launcher, fake_clock)

    first = await adapter.health()
    second = await adapter.health()

    assert first.ok is False
    assert "Not logged in" in first.detail
    assert first == second
    assert (launcher.version_calls, launcher.login_calls) == (1, 1)

    fake_clock.advance(60)
    launcher.login_result = (True, "Logged in using ChatGPT")
    healthy = await adapter.health()
    assert healthy.ok is True
    assert "codex-cli 0.160.1" in healthy.detail

    launcher.version_result = (False, "codex: command not found")
    fake_clock.advance(60)
    broken = await adapter.health()
    assert broken.ok is False
    assert broken.detail == "codex: command not found"


async def test_cancel_kills_and_ends(tmp_path: Path, fake_clock: FakeClock) -> None:
    launcher = FakeCodexProcessLauncher(_fixture("exec_success.jsonl")[:1], hang=True)
    adapter = _adapter(launcher, fake_clock)
    stream = adapter.run(_input(), _session(tmp_path))

    first = await anext(stream)
    await adapter.cancel(RUN)
    rest = await _collect(stream)

    assert first.kind is K.STARTED
    assert [e.kind for e in rest] == [K.ENDED]
    assert launcher.processes[0].killed is True
    await adapter.cancel("RUN-01J99999999999999999999999")  # unknown run: no-op


async def test_sandbox_factory_is_used(tmp_path: Path, fake_clock: FakeClock) -> None:
    seen: list[RunSession] = []

    def factory(session: RunSession) -> CodexSandboxConfig:
        seen.append(session)
        return CodexSandboxConfig(mode="read-only", cwd=session.worktree_path)

    launcher = FakeCodexProcessLauncher(_fixture("exec_success.jsonl"))
    await _collect(
        _adapter(launcher, fake_clock, sandbox_factory=factory).run(_input(), _session(tmp_path))
    )

    assert len(seen) == 1
    assert ("--sandbox", "read-only") in zip(
        launcher.launches[0].argv, launcher.launches[0].argv[1:], strict=False
    )


async def test_adapter_surface(tmp_path: Path, fake_clock: FakeClock) -> None:
    adapter: ModelAdapter = _adapter(FakeCodexProcessLauncher(), fake_clock)
    assert adapter.provider == "codex"
    assert [d.id for d in adapter.descriptors()] == [CODEX]
    assert adapter.map_effort(Effort.VERY_HIGH, CODEX).params == {"model_reasoning_effort": "xhigh"}
    assert isinstance(adapter.skill_projector(), CodexSkillProjector)
    assert adapter.parse_output(DONE.model_dump_json()) == DONE
    with pytest.raises(OutputInvalid):
        adapter.parse_output("[]")
    assert adapter.usage("RUN-01J99999999999999999999999").input_tokens == 0
    with pytest.raises(ConfigError, match="not served"):
        adapter.map_effort(Effort.LOW, "codex/unknown")
    bad = _session(tmp_path).model_copy(update={"model_id": "claude/x"})
    with pytest.raises(ConfigError, match="not served"):
        adapter.run(_input(), bad)


def _python_launcher() -> AsyncioCodexProcessLauncher:
    return AsyncioCodexProcessLauncher(binary=sys.executable)


async def test_asyncio_launcher_streams_lines_and_exit_code(tmp_path: Path) -> None:
    script = tmp_path / "emit.py"
    script.write_text(
        "import sys\n"
        "data = sys.stdin.read()\n"
        'print(\'{"type": "turn.started"}\')\n'
        "print(data.upper())\n"
        "print('warning', file=sys.stderr)\n"
        "sys.exit(3)\n",
        encoding="utf-8",
    )
    prompt = tmp_path / "prompt.md"
    prompt.write_text("hello", encoding="utf-8")
    launcher = _python_launcher()

    process = await launcher.launch(
        [sys.executable, str(script)],
        cwd=str(tmp_path),
        env=dict(os.environ),
        stdin_path=str(prompt),
    )
    lines = [line async for line in process.lines()]

    assert lines == ['{"type": "turn.started"}', "HELLO"]
    assert await process.wait() == 3
    assert (await process.stderr_text()).strip() == "warning"
    assert process.pid is not None
    await process.kill()  # already exited: no error


async def test_asyncio_launcher_kills_and_reports_missing_binary(tmp_path: Path) -> None:
    launcher = _python_launcher()
    process = await launcher.launch(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        cwd=str(tmp_path),
        env=dict(os.environ),
    )
    await process.kill()
    assert await process.wait() != 0

    with pytest.raises(FileNotFoundError):
        await launcher.launch(["walk-no-such-codex-binary"], cwd=str(tmp_path), env={})


async def test_asyncio_launcher_version_and_login(tmp_path: Path) -> None:
    ok, text = await _python_launcher().version()
    assert ok is True
    assert "Python" in text

    ok, text = await _python_launcher().login_status()  # python cannot open 'login'
    assert ok is False
    assert text

    ok, text = await AsyncioCodexProcessLauncher(binary=str(tmp_path / "missing")).version()
    assert ok is False
    assert "not found" in text


@pytest.mark.integration
async def test_real_codex_round_trip(tmp_repo: Path) -> None:
    launcher = AsyncioCodexProcessLauncher()
    ok, detail = await launcher.version()
    if not ok:
        pytest.skip(detail)
    adapter = CodexAdapter(
        launcher,
        [_codex()],
        SystemClock(),
        system_prompt_builder=lambda _: "Answer with the structured output only.",
        user_message_builder=lambda _: (
            'Return {"status": "COMPLETED", "result": "ok", "no_context_change_reason": "probe"}.'
        ),
    )
    session = _session(tmp_repo).model_copy(update={"env_allowlist": dict(os.environ)})

    events = await _collect(adapter.run(_input(), session))

    print(json.dumps([e.kind.value for e in events]))  # noqa: T201 - transcript for ADR-0014 evidence
    assert events[0].kind is K.STARTED
    assert events[-1].kind in {K.ENDED, K.ERROR}
