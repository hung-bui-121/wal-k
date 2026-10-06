"""Claude SDK message → `AgentEvent` translation (ADR-0004 D-2, ADR-0014).

Messages are inspected by type name and attributes only, so this module never imports the SDK.
Thinking blocks are dropped without a trace (§22). ``TOOL_CALL_REQUESTED`` is not produced
here: the adapter emits it from ``can_use_tool``, before the tool runs.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from pydantic import Field

from walk.common.errors import OutputInvalid
from walk.common.ids import RunId
from walk.common.models import JsonDict, WalkModel
from walk.common.roles import AgentRole
from walk.model_router.adapters.claude.client import SdkMessage
from walk.model_router.adapters.claude.permissions import to_tool_call_request
from walk.model_router.models import AgentEvent, AgentEventKind, ProviderSessionRef, UsageReport
from walk.model_router.output import parse_agent_output, read_output_file
from walk.permissions.models import ToolCallRequest

_LOG = logging.getLogger(__name__)

_PROVIDER: Final = "claude"
_TOOL_RESULT_MAX_BYTES: Final = 4096
_MS_PER_S: Final = 1000.0
_THINKING_BLOCKS: Final = frozenset({"ThinkingBlock", "RedactedThinkingBlock"})
_ZERO_USAGE: Final = UsageReport(
    input_tokens=0, output_tokens=0, cost_usd=0.0, turns=0, tool_calls=0, duration_s=0.0
)


class ClaudeTranslationState(WalkModel):
    """Per-run translation state; one per `run`/`resume` stream."""

    role: AgentRole = Field(description="Role of the run (stamped on tool call requests).")
    worktree_path: str = Field(description="Worktree of the run.")
    output_path: str = Field(description="Fallback output file (<worktree>/.walk/output.json).")
    session_id: str | None = Field(default=None, description="SDK session id, once known.")
    started: bool = Field(default=False, description="STARTED was emitted.")
    finished: bool = Field(default=False, description="The result message was translated.")
    pending_tool_calls: dict[str, ToolCallRequest] = Field(
        default_factory=dict, description="Requests of tool_use blocks by SDK tool_use_id."
    )
    usage: UsageReport = Field(
        default=_ZERO_USAGE, description="Cumulative usage of the run's completed queries."
    )
    turns: int = Field(default=0, description="Assistant messages seen.")
    query_tool_calls: int = Field(default=0, description="tool_use blocks in the current query.")


def translate_message(
    msg: SdkMessage, state: ClaudeTranslationState, run_id: RunId, now: datetime
) -> list[AgentEvent]:
    """The events of one SDK message; updates ``state``."""
    kind = type(msg).__name__
    if kind == "SystemMessage":
        return _system(msg, state, run_id, now)
    if kind == "AssistantMessage":
        return _assistant(msg, state, run_id, now)
    if kind == "UserMessage":
        return _user(msg, state, run_id, now)
    if kind == "ResultMessage":
        return _result(msg, state, run_id, now)
    _LOG.debug("skipping SDK message", extra={"message_type": kind, "run_id": run_id})
    return []


def _system(
    msg: Any, state: ClaudeTranslationState, run_id: RunId, now: datetime
) -> list[AgentEvent]:
    data = getattr(msg, "data", None)
    if getattr(msg, "subtype", None) != "init" or not isinstance(data, dict):
        return []
    session_id = data.get("session_id")
    if isinstance(session_id, str) and session_id:
        state.session_id = session_id
    return _started(state, run_id, now)


def _started(state: ClaudeTranslationState, run_id: RunId, now: datetime) -> list[AgentEvent]:
    if state.started or state.session_id is None:
        return []
    state.started = True
    ref = ProviderSessionRef(provider=_PROVIDER, session_id=state.session_id, resumable=True)
    return [AgentEvent(kind=AgentEventKind.STARTED, run_id=run_id, at=now, session=ref)]


def _assistant(
    msg: Any, state: ClaudeTranslationState, run_id: RunId, now: datetime
) -> list[AgentEvent]:
    state.turns += 1
    events: list[AgentEvent] = []
    for block in getattr(msg, "content", None) or []:
        block_kind = type(block).__name__
        if block_kind in _THINKING_BLOCKS:
            continue
        if block_kind == "TextBlock":
            text = getattr(block, "text", "")
            if isinstance(text, str) and text.strip():
                events.append(
                    AgentEvent(kind=AgentEventKind.TEXT, run_id=run_id, at=now, text=text)
                )
        elif block_kind == "ToolUseBlock":
            tool_input = getattr(block, "input", None)
            state.pending_tool_calls[str(block.id)] = to_tool_call_request(
                str(block.name),
                tool_input if isinstance(tool_input, dict) else {},
                run_id=run_id,
                role=state.role,
                worktree_path=state.worktree_path,
            )
            state.query_tool_calls += 1
    return events


def _user(
    msg: Any, state: ClaudeTranslationState, run_id: RunId, now: datetime
) -> list[AgentEvent]:
    content = getattr(msg, "content", None)
    if not isinstance(content, list):
        return []
    events: list[AgentEvent] = []
    for block in content:
        if type(block).__name__ != "ToolResultBlock":
            continue
        request = state.pending_tool_calls.pop(str(block.tool_use_id), None)
        result: JsonDict = {
            "ok": not bool(getattr(block, "is_error", False)),
            "content": _truncate(_result_text(getattr(block, "content", None))),
        }
        events.append(
            AgentEvent(
                kind=AgentEventKind.TOOL_CALL_RESULT,
                run_id=run_id,
                at=now,
                tool_call=request,
                tool_result=result,
            )
        )
    return events


def _result(
    msg: Any, state: ClaudeTranslationState, run_id: RunId, now: datetime
) -> list[AgentEvent]:
    session_id = getattr(msg, "session_id", None)
    if isinstance(session_id, str) and session_id:
        state.session_id = session_id
    events = _started(state, run_id, now)
    state.usage = _add_usage(state.usage, msg, state.query_tool_calls)
    state.query_tool_calls = 0
    state.finished = True
    events.append(AgentEvent(kind=AgentEventKind.USAGE, run_id=run_id, at=now, usage=state.usage))
    if getattr(msg, "is_error", False):
        text = getattr(msg, "result", None) or getattr(msg, "subtype", None) or "error"
        events.append(AgentEvent(kind=AgentEventKind.ERROR, run_id=run_id, at=now, error=str(text)))
        return events
    events.append(_final_output(msg, state, run_id, now))
    events.append(AgentEvent(kind=AgentEventKind.ENDED, run_id=run_id, at=now))
    return events


def _final_output(
    msg: Any, state: ClaudeTranslationState, run_id: RunId, now: datetime
) -> AgentEvent:
    structured = getattr(msg, "structured_output", None)
    if structured is not None:
        raw: str | None = structured if isinstance(structured, str) else json.dumps(structured)
    else:
        raw = read_output_file(Path(state.output_path))
    if raw is None:
        error = f"no structured output and no output file at {state.output_path}"
        return AgentEvent(kind=AgentEventKind.FINAL_OUTPUT, run_id=run_id, at=now, error=error)
    try:
        output = parse_agent_output(raw)
    except OutputInvalid as exc:
        return AgentEvent(
            kind=AgentEventKind.FINAL_OUTPUT, run_id=run_id, at=now, error=exc.message
        )
    return AgentEvent(kind=AgentEventKind.FINAL_OUTPUT, run_id=run_id, at=now, output=output)


def _add_usage(total: UsageReport, msg: Any, tool_calls: int) -> UsageReport:
    usage = getattr(msg, "usage", None)
    counts: dict[str, Any] = usage if isinstance(usage, dict) else {}
    cost = getattr(msg, "total_cost_usd", None)
    return UsageReport(
        input_tokens=total.input_tokens
        + int(counts.get("input_tokens", 0))
        + int(counts.get("cache_creation_input_tokens", 0)),
        output_tokens=total.output_tokens + int(counts.get("output_tokens", 0)),
        cache_read_tokens=total.cache_read_tokens + int(counts.get("cache_read_input_tokens", 0)),
        cost_usd=total.cost_usd + (float(cost) if cost is not None else 0.0),
        turns=total.turns + int(getattr(msg, "num_turns", 0) or 0),
        tool_calls=total.tool_calls + tool_calls,
        duration_s=total.duration_s + (getattr(msg, "duration_ms", 0) or 0) / _MS_PER_S,
    )


def _result_text(content: object) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        return "\n".join(texts)
    return str(content)


def _truncate(text: str) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= _TOOL_RESULT_MAX_BYTES:
        return text
    return encoded[:_TOOL_RESULT_MAX_BYTES].decode("utf-8", errors="ignore")
