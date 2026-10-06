"""`ClaudeAdapter`: the Claude Agent SDK behind the normalised adapter boundary (ADR-0004 D-7).

The SDK stream is consumed by one producer task (so the SDK's own task groups always run in the
task that opened them); translated events, tool-call requests from ``can_use_tool`` and
failures reach the caller's generator through a queue. A watchdog bounds the run by
``RunSession.timeout_s`` on the injected clock.
"""

import asyncio
import enum
import logging
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, NamedTuple

from walk.agents.models import AgentInput, AgentOutput
from walk.common.clock import Clock
from walk.common.enums import Effort
from walk.common.errors import (
    ConfigError,
    ProviderUnavailable,
    RateLimited,
    Timeout,
    WalkError,
)
from walk.common.ids import ModelId, RunId
from walk.common.models import JsonDict
from walk.common.roles import AgentRole
from walk.model_router.adapters.claude.client import ClaudeClient, ClaudeQueryOptions
from walk.model_router.adapters.claude.effort import map_claude_effort
from walk.model_router.adapters.claude.events import ClaudeTranslationState, translate_message
from walk.model_router.adapters.claude.permissions import (
    NATIVE_TOOL_NAMES,
    to_sdk_permission_result,
    to_tool_call_request,
)
from walk.model_router.adapters.claude.projector import ClaudeSkillProjector
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
from walk.model_router.output import parse_agent_output
from walk.tools.models import ToolKind, ToolSpec

_LOG = logging.getLogger(__name__)

_HEALTH_TTL: Final = timedelta(seconds=60)
_WATCHDOG_POLL_S: Final = 1.0
_PERMISSION_MODE: Final = "default"  # ADR-0014: routes every non-pre-approved call to can_use_tool
_RATE_LIMIT: Final = re.compile(r"(?i)\b429\b|rate.?limit")
_OVERLOADED: Final = re.compile(r"(?i)overloaded|\b5\d\d\b")
_CLI_MISSING_ERRORS: Final = frozenset({"CLINotFoundError"})
_SDK_ERRORS: Final = frozenset(
    {"ClaudeSDKError", "CLIConnectionError", "ProcessError", "CLIJSONDecodeError"}
)
_ZERO_USAGE: Final = UsageReport(
    input_tokens=0, output_tokens=0, cost_usd=0.0, turns=0, tool_calls=0, duration_s=0.0
)


class _Signal(enum.Enum):
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class _Failure(NamedTuple):
    error: Exception


_Item = AgentEvent | _Failure | _Signal


@dataclass
class _Run:
    state: ClaudeTranslationState
    system_prompt: str
    queue: asyncio.Queue[_Item]


@dataclass(frozen=True)
class _SessionInfo:
    role: AgentRole
    system_prompt: str


class ClaudeAdapter:
    """`ModelAdapter` for Claude through `ClaudeClient` (the SDK, or a fake in tests)."""

    provider = "claude"

    def __init__(
        self,
        client: ClaudeClient,
        descriptors: list[ModelDescriptor],
        clock: Clock,
        *,
        system_prompt_builder: Callable[[AgentInput], str],
        user_message_builder: Callable[[AgentInput], str],
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Serve ``descriptors`` through ``client``.

        Args:
            client: SDK boundary.
            descriptors: Models this adapter serves (the registry stays authoritative).
            clock: Time source of events, health caching and the run watchdog.
            system_prompt_builder: Renders the system prompt (from `walk.agents.rendering`).
            user_message_builder: Renders the first user message.
            sleep: Awaited between watchdog checks; injected so tests do not wait.
        """
        self._client = client
        self._descriptors = {d.id: d for d in descriptors}
        self._clock = clock
        self._system_prompt_builder = system_prompt_builder
        self._user_message_builder = user_message_builder
        self._sleep = sleep
        self._health: AdapterHealth | None = None
        self._runs: dict[RunId, _Run] = {}
        self._sessions: dict[str, _SessionInfo] = {}

    def descriptors(self) -> list[ModelDescriptor]:
        """The descriptors given at construction."""
        return list(self._descriptors.values())

    async def health(self) -> AdapterHealth:
        """`ClaudeClient.available`, queried at most once per 60 s."""
        now = self._clock.now()
        if self._health is not None and now - self._health.checked_at < _HEALTH_TTL:
            return self._health
        ok, detail = await self._client.available()
        self._health = AdapterHealth(ok=ok, provider=self.provider, detail=detail, checked_at=now)
        return self._health

    def map_effort(self, effort: Effort, model_id: ModelId) -> ProviderEffortConfig:
        """`map_claude_effort` for a served model.

        Raises:
            ConfigError: ``model_id`` is not served by this adapter.
        """
        return map_claude_effort(effort, self._descriptor(model_id), None)

    def run(self, input: AgentInput, session: RunSession) -> AsyncIterator[AgentEvent]:  # noqa: A002 - parameter name fixed by INTERFACES §2.1
        """Start a fresh SDK session for ``input``.

        Raises:
            ConfigError: ``session.model_id`` is not served by this adapter.
        """
        descriptor = self._descriptor(session.model_id)
        system_prompt = self._system_prompt_builder(input)
        options = self._options(session, descriptor, system_prompt, resume=None)
        prompt = self._user_message_builder(input)
        return self._start(prompt, options, input.role, system_prompt, session)

    def resume(
        self, session_ref: ProviderSessionRef, instruction: str, session: RunSession
    ) -> AsyncIterator[AgentEvent]:
        """Continue ``session_ref`` with ``instruction`` as the prompt.

        Raises:
            NotResumable: Not a resumable Claude session, or one this adapter instance has
                not started (its role and system prompt are unknown).
            ConfigError: ``session.model_id`` is not served by this adapter.
        """
        if session_ref.provider != self.provider or not session_ref.resumable:
            msg = f"session {session_ref.session_id} of {session_ref.provider} is not resumable"
            raise NotResumable(msg, detail={"provider": session_ref.provider})
        info = self._sessions.get(session_ref.session_id)
        if info is None:
            msg = f"unknown claude session {session_ref.session_id}"
            raise NotResumable(msg, detail={"session_id": session_ref.session_id})
        descriptor = self._descriptor(session.model_id)
        options = self._options(
            session, descriptor, info.system_prompt, resume=session_ref.session_id
        )
        return self._start(instruction, options, info.role, info.system_prompt, session)

    async def cancel(self, run_id: RunId) -> None:
        """Interrupt the run's session; its stream then ends with ``ENDED``."""
        run = self._runs.get(run_id)
        if run is None:
            return
        await self._interrupt(run)
        run.queue.put_nowait(_Signal.CANCELLED)

    def usage(self, run_id: RunId) -> UsageReport:
        """Cumulative usage of the run (all zeros for an unknown run)."""
        run = self._runs.get(run_id)
        return run.state.usage if run is not None else _ZERO_USAGE

    def skill_projector(self) -> ClaudeSkillProjector:
        """Claude's skill projection format."""
        return ClaudeSkillProjector(clock=self._clock)

    def parse_output(self, raw: str) -> AgentOutput:
        """`parse_agent_output`."""
        return parse_agent_output(raw)

    def _descriptor(self, model_id: ModelId) -> ModelDescriptor:
        descriptor = self._descriptors.get(model_id)
        if descriptor is None:
            msg = f"model {model_id} is not served by the claude adapter"
            raise ConfigError(msg, detail={"model_id": model_id})
        return descriptor

    def _options(
        self,
        session: RunSession,
        descriptor: ModelDescriptor,
        system_prompt: str,
        *,
        resume: str | None,
    ) -> ClaudeQueryOptions:
        effort = map_claude_effort(session.effort, descriptor, None).params["effort"]
        return ClaudeQueryOptions(
            cwd=session.worktree_path,
            model=session.model_id,
            tools=_sdk_tools(session.allowed_tools),
            allowed_tools=[],
            permission_mode=_PERMISSION_MODE,
            max_turns=session.max_turns,
            system_prompt=system_prompt,
            effort=str(effort),
            env=dict(session.env_allowlist),
            resume=resume,
            output_schema=AgentOutput.model_json_schema(),
        )

    def _start(
        self,
        prompt: str,
        options: ClaudeQueryOptions,
        role: AgentRole,
        system_prompt: str,
        session: RunSession,
    ) -> AsyncIterator[AgentEvent]:
        previous = self._runs.get(session.run_id)
        state = ClaudeTranslationState(
            role=role,
            worktree_path=session.worktree_path,
            output_path=session.output_path,
            usage=previous.state.usage if previous is not None else _ZERO_USAGE,
        )
        run = _Run(state=state, system_prompt=system_prompt, queue=asyncio.Queue())
        self._runs[session.run_id] = run
        return self._stream(prompt, options, run, session)

    async def _stream(
        self, prompt: str, options: ClaudeQueryOptions, run: _Run, session: RunSession
    ) -> AsyncIterator[AgentEvent]:
        deadline = self._clock.now() + timedelta(seconds=session.timeout_s)
        producer = asyncio.create_task(self._produce(prompt, options, run, session))
        watchdog = asyncio.create_task(self._watch(deadline))
        try:
            while True:
                item = await _next(run.queue, watchdog)
                if item is None:
                    await self._interrupt(run)
                    msg = f"claude run exceeded {session.timeout_s} s"
                    raise Timeout(msg, detail={"timeout_s": session.timeout_s})
                if item is _Signal.CANCELLED:
                    yield AgentEvent(
                        kind=AgentEventKind.ENDED, run_id=session.run_id, at=self._clock.now()
                    )
                    return
                if item is _Signal.DONE:
                    if not run.state.finished:
                        msg = "claude stream ended without a result message"
                        raise ProviderUnavailable(msg, detail={"run_id": session.run_id})
                    return
                if isinstance(item, _Failure):
                    mapped = _map_error(item.error)
                    if mapped is item.error:
                        raise mapped
                    raise mapped from item.error
                yield item
        finally:
            producer.cancel()
            watchdog.cancel()
            await asyncio.gather(producer, watchdog, return_exceptions=True)

    async def _produce(
        self, prompt: str, options: ClaudeQueryOptions, run: _Run, session: RunSession
    ) -> None:
        async def can_use_tool(tool_name: str, tool_input: JsonDict) -> JsonDict:
            request = to_tool_call_request(
                tool_name,
                tool_input,
                run_id=session.run_id,
                role=run.state.role,
                worktree_path=session.worktree_path,
            )
            run.queue.put_nowait(
                AgentEvent(
                    kind=AgentEventKind.TOOL_CALL_REQUESTED,
                    run_id=session.run_id,
                    at=self._clock.now(),
                    tool_call=request,
                )
            )
            try:
                decision = await session.permission_authorizer(request)
            except Exception as exc:  # noqa: BLE001 - fail closed; the run fails with this error
                run.queue.put_nowait(_Failure(exc))
                return {"behavior": "deny", "message": f"kernel authorization failed: {exc}"}
            return to_sdk_permission_result(decision)

        try:
            async for message in self._client.query(prompt, options, can_use_tool):
                for event in translate_message(
                    message, run.state, session.run_id, self._clock.now()
                ):
                    run.queue.put_nowait(event)
                self._remember_session(run)
        except Exception as exc:  # noqa: BLE001 - handed to the consumer, mapped and re-raised there
            run.queue.put_nowait(_Failure(exc))
        else:
            run.queue.put_nowait(_Signal.DONE)

    async def _watch(self, deadline: datetime) -> None:
        while self._clock.now() < deadline:
            await self._sleep(_WATCHDOG_POLL_S)

    def _remember_session(self, run: _Run) -> None:
        session_id = run.state.session_id
        if session_id is not None and session_id not in self._sessions:
            self._sessions[session_id] = _SessionInfo(run.state.role, run.system_prompt)

    async def _interrupt(self, run: _Run) -> None:
        session_id = run.state.session_id
        if session_id is None:
            return
        try:
            await self._client.interrupt(session_id)
        except Exception:  # noqa: BLE001 - best effort: the timeout or cancel proceeds; logged below
            _LOG.exception("claude interrupt failed", extra={"session_id": session_id})


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


def _sdk_tools(tools: list[ToolSpec]) -> list[str]:
    names: list[str] = []
    for spec in tools:
        if spec.kind is not ToolKind.PROVIDER_NATIVE:
            continue
        mapped = [sdk for sdk, kernel in NATIVE_TOOL_NAMES.items() if kernel == spec.name]
        if not mapped:
            _LOG.debug("no claude tool for kernel tool", extra={"tool": spec.name})
        names.extend(name for name in mapped if name not in names)
    return names


def _map_error(exc: Exception) -> Exception:
    """ARCHITECTURE §5.1 taxonomy for client exceptions; unknown exceptions are returned as is."""
    if isinstance(exc, WalkError):
        return exc
    names = {cls.__name__ for cls in type(exc).__mro__}
    text = str(exc)
    detail = {"error_type": type(exc).__name__}
    if names & _CLI_MISSING_ERRORS or isinstance(exc, FileNotFoundError):
        return ConfigError(f"Claude Code CLI not found: {text}", detail=detail)
    if _RATE_LIMIT.search(text):
        return RateLimited(f"claude rate limited: {text}", detail=detail)
    if _OVERLOADED.search(text) or names & _SDK_ERRORS or isinstance(exc, OSError):
        return ProviderUnavailable(f"claude unavailable: {text}", detail=detail)
    return exc
