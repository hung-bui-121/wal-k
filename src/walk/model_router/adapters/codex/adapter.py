"""`CodexAdapter`: ``codex exec --json`` behind the normalised adapter boundary (ADR-0004 D-8).

Codex executes tools inside its own sandbox, so tool calls cannot be pre-authorised; the adapter
asks the session's authorizer after the fact (advisory, ADR-0006 D-5) and records the decision
on the ``TOOL_CALL_RESULT``. A watchdog bounds the run by ``RunSession.timeout_s`` on the
injected clock and kills the process when it fires.
"""

import asyncio
import enum
import json
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final, NamedTuple

from walk.agents.models import AgentInput, AgentOutput
from walk.common.clock import Clock
from walk.common.enums import Effort
from walk.common.errors import (
    ConfigError,
    OutputInvalid,
    ProviderUnavailable,
    QuotaExhausted,
    RateLimited,
    Timeout,
)
from walk.common.ids import ModelId, RunId
from walk.common.roles import AgentRole
from walk.model_router.adapters.codex.command import build_exec_command, build_resume_command
from walk.model_router.adapters.codex.effort import map_codex_effort
from walk.model_router.adapters.codex.events import (
    CodexTranslationState,
    parse_codex_line,
    translate_codex_event,
)
from walk.model_router.adapters.codex.process import CodexProcess, CodexProcessLauncher
from walk.model_router.adapters.codex.projector import CodexSkillProjector
from walk.model_router.adapters.codex.sandbox import CodexSandboxConfig
from walk.model_router.errors import NotResumable
from walk.model_router.models import (
    AdapterHealth,
    AgentEvent,
    AgentEventKind,
    ModelDescriptor,
    ProviderEffortConfig,
    ProviderSessionRef,
    RunSession,
    UsageReport,
)
from walk.model_router.output import parse_agent_output, read_output_file

_HEALTH_TTL: Final = timedelta(seconds=60)
_WATCHDOG_POLL_S: Final = 1.0
_STDERR_TAIL_CHARS: Final = 2000
_PROMPT_FILE: Final = ".walk/prompt.md"
_SCHEMA_FILE: Final = ".walk/output.schema.json"
_RATE_LIMIT: Final = re.compile(r"(?i)rate.?limit|429")
_QUOTA: Final = re.compile(r"(?i)quota|usage limit|insufficient")
_ZERO_USAGE: Final = UsageReport(
    input_tokens=0, output_tokens=0, cost_usd=0.0, turns=0, tool_calls=0, duration_s=0.0
)


class _Signal(enum.Enum):
    DONE = "DONE"


class _Failure(NamedTuple):
    error: Exception


_Item = str | _Failure | _Signal


@dataclass
class _Run:
    state: CodexTranslationState
    process: CodexProcess | None = None
    cancelled: bool = False
    queue: asyncio.Queue[_Item] = field(default_factory=asyncio.Queue)


class CodexAdapter:
    """`ModelAdapter` for Codex through a `CodexProcessLauncher`."""

    provider = "codex"

    def __init__(
        self,
        launcher: CodexProcessLauncher,
        descriptors: list[ModelDescriptor],
        clock: Clock,
        *,
        system_prompt_builder: Callable[[AgentInput], str],
        user_message_builder: Callable[[AgentInput], str],
        sandbox_factory: Callable[[RunSession], CodexSandboxConfig] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Serve ``descriptors`` by launching the Codex CLI.

        Args:
            launcher: Process boundary.
            descriptors: Models this adapter serves (the registry stays authoritative).
            clock: Time source of events, health caching and the run watchdog.
            system_prompt_builder: Renders the system part of the prompt.
            user_message_builder: Renders the task part of the prompt.
            sandbox_factory: Sandbox per run; default ``workspace-write`` on the worktree with
                the network off (E01-S26 injects the policy-aware factory).
            sleep: Awaited between watchdog checks; injected so tests do not wait.
        """
        self._launcher = launcher
        self._descriptors = {d.id: d for d in descriptors}
        self._clock = clock
        self._system_prompt_builder = system_prompt_builder
        self._user_message_builder = user_message_builder
        self._sandbox_factory = sandbox_factory or _default_sandbox
        self._sleep = sleep
        self._health: AdapterHealth | None = None
        self._runs: dict[RunId, _Run] = {}
        self._thread_roles: dict[str, AgentRole] = {}

    def descriptors(self) -> list[ModelDescriptor]:
        """The descriptors given at construction."""
        return list(self._descriptors.values())

    async def health(self) -> AdapterHealth:
        """``codex --version`` and ``codex login status`` both succeed; cached for 60 s."""
        now = self._clock.now()
        if self._health is not None and now - self._health.checked_at < _HEALTH_TTL:
            return self._health
        version_ok, version = await self._launcher.version()
        if version_ok:
            login_ok, login = await self._launcher.login_status()
            ok, detail = login_ok, f"{version}; {login}"
        else:
            ok, detail = False, version
        self._health = AdapterHealth(ok=ok, provider=self.provider, detail=detail, checked_at=now)
        return self._health

    def map_effort(self, effort: Effort, model_id: ModelId) -> ProviderEffortConfig:
        """`map_codex_effort` for a served model.

        Raises:
            ConfigError: ``model_id`` is not served by this adapter.
        """
        return map_codex_effort(effort, self._descriptor(model_id), None)

    def run(self, input: AgentInput, session: RunSession) -> AsyncIterator[AgentEvent]:  # noqa: A002 - parameter name fixed by INTERFACES §2.1
        """Start a fresh ``codex exec`` thread for ``input``.

        Raises:
            ConfigError: ``session.model_id`` is not served by this adapter.
        """
        cfg = self.map_effort(session.effort, session.model_id)
        prompt = f"{self._system_prompt_builder(input)}\n\n{self._user_message_builder(input)}"
        worktree = Path(session.worktree_path)
        schema_path = str(worktree / _SCHEMA_FILE)
        argv = build_exec_command(
            cfg,
            self._sandbox_factory(session),
            prompt_file=str(worktree / _PROMPT_FILE),
            output_schema_path=schema_path,
        )
        return self._start(argv, prompt, input.role, session, write_schema=True)

    def resume(
        self, session_ref: ProviderSessionRef, instruction: str, session: RunSession
    ) -> AsyncIterator[AgentEvent]:
        """Continue thread ``session_ref`` with ``instruction`` as the prompt.

        Raises:
            NotResumable: Not a resumable Codex thread, or one this adapter instance has not
                started (its role is unknown).
            ConfigError: ``session.model_id`` is not served by this adapter.
        """
        if session_ref.provider != self.provider or not session_ref.resumable:
            msg = f"session {session_ref.session_id} of {session_ref.provider} is not resumable"
            raise NotResumable(msg, detail={"provider": session_ref.provider})
        role = self._thread_roles.get(session_ref.session_id)
        if role is None:
            msg = f"unknown codex thread {session_ref.session_id}"
            raise NotResumable(msg, detail={"session_id": session_ref.session_id})
        cfg = self.map_effort(session.effort, session.model_id)
        argv = build_resume_command(session_ref.session_id, cfg, self._sandbox_factory(session))
        return self._start(argv, instruction, role, session, write_schema=False)

    async def cancel(self, run_id: RunId) -> None:
        """Kill the run's process; its stream then ends with ``ENDED``."""
        run = self._runs.get(run_id)
        if run is None:
            return
        run.cancelled = True
        if run.process is not None:
            await run.process.kill()

    def usage(self, run_id: RunId) -> UsageReport:
        """Cumulative usage of the run (all zeros for an unknown run)."""
        run = self._runs.get(run_id)
        return run.state.usage if run is not None else _ZERO_USAGE

    def skill_projector(self) -> CodexSkillProjector:
        """Codex's skill projection format."""
        return CodexSkillProjector(clock=self._clock)

    def parse_output(self, raw: str) -> AgentOutput:
        """`parse_agent_output`."""
        return parse_agent_output(raw)

    def _descriptor(self, model_id: ModelId) -> ModelDescriptor:
        descriptor = self._descriptors.get(model_id)
        if descriptor is None:
            msg = f"model {model_id} is not served by the codex adapter"
            raise ConfigError(msg, detail={"model_id": model_id})
        return descriptor

    def _start(
        self,
        argv: list[str],
        prompt: str,
        role: AgentRole,
        session: RunSession,
        *,
        write_schema: bool,
    ) -> AsyncIterator[AgentEvent]:
        previous = self._runs.get(session.run_id)
        state = CodexTranslationState(
            role=role,
            worktree_path=session.worktree_path,
            usage=previous.state.usage if previous is not None else _ZERO_USAGE,
        )
        run = _Run(state=state)
        self._runs[session.run_id] = run
        return self._stream(argv, prompt, run, session, write_schema=write_schema)

    async def _stream(
        self,
        argv: list[str],
        prompt: str,
        run: _Run,
        session: RunSession,
        *,
        write_schema: bool,
    ) -> AsyncIterator[AgentEvent]:
        prompt_path = _write_inputs(Path(session.worktree_path), prompt, write_schema=write_schema)
        try:
            process = await self._launcher.launch(
                argv,
                cwd=session.worktree_path,
                env=dict(session.env_allowlist),
                stdin_path=prompt_path,
            )
        except FileNotFoundError as exc:
            msg = f"codex CLI not found: {exc}"
            raise ConfigError(msg, detail={"argv0": argv[0]}) from exc
        except OSError as exc:
            msg = f"codex CLI could not be started: {exc}"
            raise ProviderUnavailable(msg, detail={"argv0": argv[0]}) from exc
        run.process = process
        deadline = self._clock.now() + timedelta(seconds=session.timeout_s)
        reader = asyncio.create_task(_read_lines(process, run.queue))
        watchdog = asyncio.create_task(self._watch(deadline))
        try:
            while True:
                item = await _next(run.queue, watchdog)
                if run.cancelled:
                    yield self._event(AgentEventKind.ENDED, session.run_id)
                    return
                if item is None:
                    await process.kill()
                    msg = f"codex run exceeded {session.timeout_s} s"
                    raise Timeout(msg, detail={"timeout_s": session.timeout_s})
                if isinstance(item, _Failure):
                    raise item.error
                if item is _Signal.DONE:
                    break
                for event in await self._translate(item, run, session):
                    yield event
            async for event in self._finish(process, run, session):
                yield event
        finally:
            reader.cancel()
            watchdog.cancel()
            await asyncio.gather(reader, watchdog, return_exceptions=True)
            await process.kill()  # no-op once exited; stops an abandoned or failed stream

    async def _translate(self, line: str, run: _Run, session: RunSession) -> list[AgentEvent]:
        parsed = parse_codex_line(line)
        if parsed is None:
            return []
        events = translate_codex_event(parsed, run.state, session.run_id, self._clock.now())
        if run.state.thread_id is not None:
            self._thread_roles.setdefault(run.state.thread_id, run.state.role)
        advised: list[AgentEvent] = []
        for event in events:
            if event.kind is AgentEventKind.TOOL_CALL_RESULT and event.tool_call is not None:
                decision = await session.permission_authorizer(event.tool_call)
                result = {**(event.tool_result or {}), "kernel_decision": decision.effect.value}
                event = event.model_copy(update={"tool_result": result})  # noqa: PLW2901 - replaced by the advised copy
            advised.append(event)
        return advised

    async def _finish(
        self, process: CodexProcess, run: _Run, session: RunSession
    ) -> AsyncIterator[AgentEvent]:
        exit_code = await process.wait()
        if exit_code != 0:
            stderr = await process.stderr_text()
            failure = _exit_failure(exit_code, stderr, run.state.errors)
            if failure is not None:
                raise failure
            return  # the ERROR event the CLI reported was the stream's last event
        yield self._final_output(run, session)
        yield AgentEvent(
            kind=AgentEventKind.USAGE,
            run_id=session.run_id,
            at=self._clock.now(),
            usage=run.state.usage,
        )
        yield self._event(AgentEventKind.ENDED, session.run_id)

    def _final_output(self, run: _Run, session: RunSession) -> AgentEvent:
        message = run.state.last_agent_message
        if message is not None:
            try:
                output = parse_agent_output(message)
            except OutputInvalid:
                pass  # plain prose: the output file is the fallback channel (ADR-0004 D-3)
            else:
                return self._event(AgentEventKind.FINAL_OUTPUT, session.run_id, output=output)
        raw = read_output_file(Path(session.output_path))
        if raw is None:
            error = f"no parsable agent message and no output file at {session.output_path}"
            return self._event(AgentEventKind.FINAL_OUTPUT, session.run_id, error=error)
        try:
            output = parse_agent_output(raw)
        except OutputInvalid as exc:
            return self._event(AgentEventKind.FINAL_OUTPUT, session.run_id, error=exc.message)
        return self._event(AgentEventKind.FINAL_OUTPUT, session.run_id, output=output)

    def _event(
        self,
        kind: AgentEventKind,
        run_id: RunId,
        *,
        output: AgentOutput | None = None,
        error: str | None = None,
    ) -> AgentEvent:
        return AgentEvent(
            kind=kind, run_id=run_id, at=self._clock.now(), output=output, error=error
        )

    async def _watch(self, deadline: datetime) -> None:
        while self._clock.now() < deadline:
            await self._sleep(_WATCHDOG_POLL_S)


def _default_sandbox(session: RunSession) -> CodexSandboxConfig:
    return CodexSandboxConfig(cwd=session.worktree_path)


def _write_inputs(worktree: Path, prompt: str, *, write_schema: bool) -> str:
    prompt_path = worktree / _PROMPT_FILE
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8")
    if write_schema:
        schema = json.dumps(AgentOutput.model_json_schema(), indent=2)
        (worktree / _SCHEMA_FILE).write_text(schema, encoding="utf-8")
    return str(prompt_path)


async def _read_lines(process: CodexProcess, queue: asyncio.Queue[_Item]) -> None:
    try:
        async for line in process.lines():
            queue.put_nowait(line)
    except Exception as exc:  # noqa: BLE001 - handed to the consumer and re-raised there
        queue.put_nowait(_Failure(exc))
    else:
        queue.put_nowait(_Signal.DONE)


async def _next(queue: asyncio.Queue[_Item], watchdog: asyncio.Task[None]) -> _Item | None:
    """The next queued item, or None when the watchdog finished first (deadline passed)."""
    getter = asyncio.ensure_future(queue.get())
    try:
        await asyncio.wait({getter, watchdog}, return_when=asyncio.FIRST_COMPLETED)
    except BaseException:
        getter.cancel()
        raise
    if getter.done():
        return getter.result()
    getter.cancel()
    return None


def _exit_failure(exit_code: int, stderr: str, errors: list[str]) -> Exception | None:
    """ARCHITECTURE §5.1 error for a failed exit; None when the CLI already reported an error."""
    text = "\n".join([stderr, *errors])
    detail = {"exit_code": exit_code, "stderr_tail": stderr[-_STDERR_TAIL_CHARS:]}
    if _RATE_LIMIT.search(text):
        return RateLimited(f"codex rate limited (exit {exit_code})", detail=detail)
    if _QUOTA.search(text):
        return QuotaExhausted(f"codex quota exhausted (exit {exit_code})", detail=detail)
    if errors:
        return None
    return ProviderUnavailable(f"codex exited with {exit_code}", detail=detail)
