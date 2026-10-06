"""Scripted `ModelAdapter` for tests and epic gates (WBS §3.6; E01-S19).

It honours every boundary rule of ADR-0004: tool calls go through the session's permission
authorizer, the structured output is written to `.walk/output.json`, an invalid output is
reported as ``FINAL_OUTPUT(output=None, error=...)``, and no thinking text is ever emitted.
"""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from walk.agents import AgentInput, AgentOutput
from walk.common.clock import Clock
from walk.common.enums import Capability, Effort
from walk.common.errors import ConfigError
from walk.common.ids import ModelId, RunId, ToolName
from walk.common.models import WalkModel
from walk.model_router import (
    AdapterHealth,
    AgentEvent,
    AgentEventKind,
    FallbackTrigger,
    ModelDescriptor,
    NotResumable,
    ProviderEffortConfig,
    ProviderSessionRef,
    RunSession,
    UsageReport,
    parse_agent_output,
)
from walk.permissions import PermissionDecision, PermissionEffect, ToolCallRequest
from walk.skills import SkillProjector
from walk.tools import ToolKind

_INVALID_OUTPUT = '{"status": "BOGUS"}'
_INVALID_ERROR = "scripted invalid output"
_EFFORT_ORDER = list(Effort)
_ZERO_USAGE = UsageReport(
    input_tokens=0, output_tokens=0, cost_usd=0.0, turns=0, tool_calls=0, duration_s=0.0
)


class FakeScript(WalkModel):
    """What one fake run does."""

    tool_calls: int = Field(default=3, description="Tool calls the run makes.")
    tool_name: ToolName = Field(default="edit", description="Tool requested by every call.")
    output: AgentOutput = Field(description="Final structured output.")
    partial_output: AgentOutput | None = Field(
        default=None, description="Emitted as PARTIAL_OUTPUT before the last tool call when set."
    )
    checkpoint_hint_at: list[int] = Field(
        default_factory=list, description="Tool-call indexes after which CHECKPOINT_HINT follows."
    )
    fail_after_tool_calls: int | None = Field(
        default=None, description="Emit ERROR(trigger) after this many tool calls and stop."
    )
    fail_trigger: FallbackTrigger | None = Field(default=None, description="Trigger of the ERROR.")
    fail_error: str = Field(default="scripted failure", description="Error text of the ERROR.")
    invalid_output_times: int = Field(
        default=0,
        description="First N FINAL_OUTPUTs carry output=None + error (forces repair turns).",
    )
    usage_per_tool_call: UsageReport = Field(
        default=UsageReport(
            input_tokens=1000,
            output_tokens=200,
            cost_usd=0.0,
            turns=1,
            tool_calls=1,
            duration_s=1.0,
        ),
        description="Usage added by each tool call.",
    )
    resumable: bool = Field(default=True, description="Session ref allows native resume.")


def fake_descriptor(model_id: ModelId, provider: str, **overrides: object) -> ModelDescriptor:
    """Descriptor with every capability 4, 200k window, 16k output, all efforts, prices 1/5."""
    data: dict[str, object] = {
        "id": model_id,
        "provider": provider,
        "display_name": model_id,
        "capabilities": dict.fromkeys(Capability, 4),
        "context_window_tokens": 200_000,
        "max_output_tokens": 16_000,
        "supports_effort_levels": list(Effort),
        "supports_native_resume": True,
        "input_cost_per_mtok_usd": 1.0,
        "output_cost_per_mtok_usd": 5.0,
    }
    data.update(overrides)
    return ModelDescriptor.model_validate(data)


@dataclass
class _RunState:
    script: FakeScript
    role_input: AgentInput
    ref: ProviderSessionRef
    next_index: int = 1
    finals: int = 0
    cancelled: bool = False
    usage: UsageReport = _ZERO_USAGE


class FakeModelAdapter:
    """Scripted `ModelAdapter`; ``runs`` and ``authorizations`` record what happened."""

    def __init__(
        self,
        provider: str,
        descriptors: list[ModelDescriptor],
        script: FakeScript | Callable[[AgentInput], FakeScript],
        clock: Clock,
        *,
        healthy: bool = True,
    ) -> None:
        """Serve ``descriptors`` as ``provider``; ``script`` may depend on the input."""
        self.provider = provider
        self._descriptors = {d.id: d for d in descriptors}
        self._script = script
        self._clock = clock
        self._healthy = healthy
        self._states: dict[str, _RunState] = {}
        self._by_session: dict[str, _RunState] = {}
        self.runs: dict[RunId, list[AgentEvent]] = {}
        self.authorizations: list[tuple[RunId, ToolCallRequest, PermissionDecision]] = []

    def set_healthy(self, ok: bool) -> None:  # noqa: FBT001 - signature fixed by the E01-S19 contract
        """Toggle what `health` reports."""
        self._healthy = ok

    def descriptors(self) -> list[ModelDescriptor]:
        """The descriptors given at construction."""
        return list(self._descriptors.values())

    async def health(self) -> AdapterHealth:
        """Report the scripted health."""
        detail = "fake adapter healthy" if self._healthy else "fake adapter marked unhealthy"
        return AdapterHealth(
            ok=self._healthy, provider=self.provider, detail=detail, checked_at=self._clock.now()
        )

    def map_effort(self, effort: Effort, model_id: ModelId) -> ProviderEffortConfig:
        """``{"fake_effort": <level>}``; unsupported levels degrade (``degraded_from``)."""
        descriptor = self._descriptors.get(model_id)
        if descriptor is None:
            msg = f"model {model_id} is not served by {self.provider}"
            raise ConfigError(msg, detail={"model_id": model_id})
        supported = descriptor.supports_effort_levels
        if effort in supported:
            return ProviderEffortConfig(model_id=model_id, params={"fake_effort": effort.value})
        rank = _EFFORT_ORDER.index(effort)
        lower = [e for e in supported if _EFFORT_ORDER.index(e) < rank]
        chosen = (
            max(lower, key=_EFFORT_ORDER.index)
            if lower
            else min(supported, key=_EFFORT_ORDER.index)
        )
        params = {"fake_effort": chosen.value, "degraded_from": effort.value}
        return ProviderEffortConfig(model_id=model_id, params=params)

    def run(self, input: AgentInput, session: RunSession) -> AsyncIterator[AgentEvent]:  # noqa: A002 - parameter name fixed by INTERFACES §2.1
        """Start the scripted run."""
        script = self._script if isinstance(self._script, FakeScript) else self._script(input)
        ref = ProviderSessionRef(
            provider=self.provider,
            session_id=f"fake-{session.run_id}",
            resumable=script.resumable,
        )
        state = _RunState(script=script, role_input=input, ref=ref)
        self._states[session.run_id] = state
        self._by_session[ref.session_id] = state
        return self._stream(state, session, started_text=None)

    def resume(
        self, session_ref: ProviderSessionRef, instruction: str, session: RunSession
    ) -> AsyncIterator[AgentEvent]:
        """Continue the scripted run from its recorded tool-call index.

        Raises:
            NotResumable: The ref is unknown or not resumable.
        """
        state = self._by_session.get(session_ref.session_id)
        if state is None or not session_ref.resumable or not state.ref.resumable:
            msg = "fake session cannot be resumed"
            raise NotResumable(msg, detail={"session_id": session_ref.session_id})
        state.cancelled = False
        self._states[session.run_id] = state
        return self._stream(state, session, started_text=instruction)

    async def cancel(self, run_id: RunId) -> None:
        """Ask the run's stream to end with ENDED at the next event boundary."""
        state = self._states.get(run_id)
        if state is not None:
            state.cancelled = True

    def usage(self, run_id: RunId) -> UsageReport:
        """Cumulative usage of the run; zero for an unknown run."""
        state = self._states.get(run_id)
        return state.usage if state is not None else _ZERO_USAGE

    def skill_projector(self) -> SkillProjector:
        """Not available before E02-S06.

        Raises:
            ConfigError: Always.
        """
        msg = "skill projection available from E02-S06"
        raise ConfigError(msg)

    def parse_output(self, raw: str) -> AgentOutput:
        """Delegate to `parse_agent_output`."""
        return parse_agent_output(raw)

    async def _stream(
        self, state: _RunState, session: RunSession, *, started_text: str | None
    ) -> AsyncIterator[AgentEvent]:
        script = state.script
        yield self._event(session, AgentEventKind.STARTED, session=state.ref, text=started_text)
        while state.next_index <= script.tool_calls:
            if state.cancelled:
                yield self._event(session, AgentEventKind.ENDED)
                return
            index = state.next_index
            if index == script.tool_calls and script.partial_output is not None:
                yield self._event(
                    session, AgentEventKind.PARTIAL_OUTPUT, output=script.partial_output
                )
            async for event in self._tool_call(state, session, index):
                yield event
            state.next_index = index + 1
            if index in script.checkpoint_hint_at:
                yield self._event(session, AgentEventKind.CHECKPOINT_HINT)
            if script.fail_after_tool_calls == index:
                yield self._event(
                    session,
                    AgentEventKind.ERROR,
                    error=script.fail_error,
                    trigger=script.fail_trigger,
                )
                return
        if state.cancelled:
            yield self._event(session, AgentEventKind.ENDED)
            return
        yield self._final(state, session)
        yield self._event(session, AgentEventKind.USAGE, usage=state.usage)
        yield self._event(session, AgentEventKind.ENDED)

    async def _tool_call(
        self, state: _RunState, session: RunSession, index: int
    ) -> AsyncIterator[AgentEvent]:
        relative = f"src/Fake{index}.cs"
        request = ToolCallRequest(
            run_id=session.run_id,
            role=state.role_input.role,
            tool=state.script.tool_name,
            kind=ToolKind.PROVIDER_NATIVE,
            arguments={"path": relative},
            paths=[relative],
            worktree_path=session.worktree_path,
        )
        yield self._event(session, AgentEventKind.TOOL_CALL_REQUESTED, tool_call=request)
        decision = await session.permission_authorizer(request)
        self.authorizations.append((session.run_id, request, decision))
        if decision.effect is PermissionEffect.ALLOW:
            _write(Path(session.worktree_path) / relative, f"// fake edit {index}\n")
            result: dict[str, object] = {"ok": True}
        else:
            result = {"ok": False, "reason": decision.reason}
        yield self._event(session, AgentEventKind.TOOL_CALL_RESULT, tool_result=result)
        step = state.script.usage_per_tool_call
        state.usage = _add(state.usage, step)
        yield self._event(session, AgentEventKind.USAGE, usage=step)

    def _final(self, state: _RunState, session: RunSession) -> AgentEvent:
        output_path = Path(session.output_path)
        state.finals += 1
        if state.finals <= state.script.invalid_output_times:
            _write(output_path, _INVALID_OUTPUT)
            return self._event(
                session, AgentEventKind.FINAL_OUTPUT, output=None, error=_INVALID_ERROR
            )
        _write(output_path, state.script.output.model_dump_json())
        parsed = parse_agent_output(output_path.read_text(encoding="utf-8"))
        return self._event(session, AgentEventKind.FINAL_OUTPUT, output=parsed)

    def _event(self, run: RunSession, kind: AgentEventKind, /, **fields: object) -> AgentEvent:
        event = AgentEvent.model_validate(
            {"kind": kind, "run_id": run.run_id, "at": self._clock.now(), **fields}
        )
        self.runs.setdefault(run.run_id, []).append(event)
        return event


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _add(total: UsageReport, step: UsageReport) -> UsageReport:
    return UsageReport(
        input_tokens=total.input_tokens + step.input_tokens,
        output_tokens=total.output_tokens + step.output_tokens,
        cache_read_tokens=total.cache_read_tokens + step.cache_read_tokens,
        cost_usd=total.cost_usd + step.cost_usd,
        turns=total.turns + step.turns,
        tool_calls=total.tool_calls + step.tool_calls,
        duration_s=total.duration_s + step.duration_s,
    )


__all__ = ["FakeModelAdapter", "FakeScript", "fake_descriptor"]
