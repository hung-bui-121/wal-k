"""`codex exec --json` event lines → `AgentEvent`s (ADR-0004 D-2/D-8, ADR-0014).

Codex runs tools itself, so tool calls are reported post hoc: a completed ``command_execution``
or ``file_change`` item becomes ``TOOL_CALL_REQUESTED`` immediately followed by
``TOOL_CALL_RESULT``. ``reasoning`` items are dropped (§22); unknown item types are logged and
skipped, never fatal.
"""

import json
import logging
from datetime import datetime
from typing import Any, Final

from pydantic import Field

from walk.common.ids import RunId
from walk.common.models import FrozenModel, JsonDict, WalkModel
from walk.common.roles import AgentRole
from walk.model_router.models import AgentEvent, AgentEventKind, ProviderSessionRef, UsageReport
from walk.permissions.models import ToolCallRequest
from walk.tools.models import ToolKind

_LOG = logging.getLogger(__name__)

_PROVIDER: Final = "codex"
_TOOL_OUTPUT_MAX_BYTES: Final = 4096
_ZERO_USAGE: Final = UsageReport(
    input_tokens=0, output_tokens=0, cost_usd=0.0, turns=0, tool_calls=0, duration_s=0.0
)
_DROPPED_ITEMS: Final = frozenset({"reasoning"})
_FAILED_STATUS: Final = "failed"


class CodexEvent(FrozenModel):
    """One parsed JSONL line of ``codex exec --json``."""

    type: str = Field(description="Event type, e.g. 'thread.started', 'item.completed'.")
    item_type: str | None = Field(default=None, description="item.type for item.* events.")
    item_id: str | None = Field(default=None, description="item.id for item.* events.")
    payload: JsonDict = Field(description="The raw JSON object of the line.")


class CodexTranslationState(WalkModel):
    """Per-run translation state; one per `run`/`resume` stream."""

    role: AgentRole = Field(description="Role of the run (stamped on tool call requests).")
    worktree_path: str = Field(description="Worktree of the run.")
    thread_id: str | None = Field(default=None, description="Codex thread id, once known.")
    usage: UsageReport = Field(default=_ZERO_USAGE, description="Cumulative usage of the run.")
    turns: int = Field(default=0, description="Completed turns.")
    last_agent_message: str | None = Field(
        default=None, description="Text of the most recent agent_message item."
    )
    seen_item_ids: list[str] = Field(
        default_factory=list, description="Completed item ids already translated."
    )
    errors: list[str] = Field(
        default_factory=list, description="Messages of error and turn.failed events."
    )


def parse_codex_line(line: str) -> CodexEvent | None:
    """The event on ``line``; None (logged) for blank lines and anything but a typed object."""
    text = line.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        _LOG.warning("skipping non-JSON codex output line", extra={"line": text[:200]})
        return None
    if not isinstance(data, dict) or not isinstance(data.get("type"), str):
        _LOG.warning("skipping untyped codex output line", extra={"line": text[:200]})
        return None
    item = data.get("item")
    item_type = item.get("type") if isinstance(item, dict) else None
    item_id = item.get("id") if isinstance(item, dict) else None
    return CodexEvent(
        type=data["type"],
        item_type=item_type if isinstance(item_type, str) else None,
        item_id=item_id if isinstance(item_id, str) else None,
        payload=data,
    )


def translate_codex_event(
    ev: CodexEvent, state: CodexTranslationState, run_id: RunId, now: datetime
) -> list[AgentEvent]:
    """The events of one Codex event; updates ``state``."""
    if ev.type == "thread.started":
        return _thread_started(ev, state, run_id, now)
    if ev.type == "item.completed":
        return _item_completed(ev, state, run_id, now)
    if ev.type == "turn.completed":
        return _turn_completed(ev, state, run_id, now)
    if ev.type in {"turn.failed", "error"}:
        message = _error_message(ev)
        state.errors = [*state.errors, message]
        return [AgentEvent(kind=AgentEventKind.ERROR, run_id=run_id, at=now, error=message)]
    return []


def _thread_started(
    ev: CodexEvent, state: CodexTranslationState, run_id: RunId, now: datetime
) -> list[AgentEvent]:
    thread_id = ev.payload.get("thread_id")
    if not isinstance(thread_id, str) or not thread_id:
        return []
    state.thread_id = thread_id
    ref = ProviderSessionRef(provider=_PROVIDER, session_id=thread_id, resumable=True)
    return [AgentEvent(kind=AgentEventKind.STARTED, run_id=run_id, at=now, session=ref)]


def _item_completed(
    ev: CodexEvent, state: CodexTranslationState, run_id: RunId, now: datetime
) -> list[AgentEvent]:
    item = ev.payload.get("item")
    if not isinstance(item, dict) or ev.item_type in _DROPPED_ITEMS:
        return []
    if ev.item_id is not None:
        if ev.item_id in state.seen_item_ids:
            return []
        state.seen_item_ids = [*state.seen_item_ids, ev.item_id]
    if ev.item_type == "agent_message":
        text = str(item.get("text", ""))
        state.last_agent_message = text
        return [AgentEvent(kind=AgentEventKind.TEXT, run_id=run_id, at=now, text=text)]
    if ev.item_type == "command_execution":
        return _command(item, state, run_id, now)
    if ev.item_type == "file_change":
        return _file_change(item, state, run_id, now)
    _LOG.info("skipping unknown codex item type", extra={"item_type": ev.item_type})
    return []


def _command(
    item: dict[str, Any], state: CodexTranslationState, run_id: RunId, now: datetime
) -> list[AgentEvent]:
    command = str(item.get("command", ""))
    exit_code = item.get("exit_code")
    request = _request(state, run_id, "bash", {"command": command}, command=command, paths=[])
    result: JsonDict = {
        "ok": exit_code == 0,
        "exit_code": exit_code,
        "output": _truncate(str(item.get("aggregated_output") or "")),
    }
    return _pair(request, result, run_id, now)


def _file_change(
    item: dict[str, Any], state: CodexTranslationState, run_id: RunId, now: datetime
) -> list[AgentEvent]:
    raw_changes = item.get("changes")
    changes = (
        [c for c in raw_changes if isinstance(c, dict)] if isinstance(raw_changes, list) else []
    )
    paths = [str(c["path"]) for c in changes if isinstance(c.get("path"), str)]
    request = _request(state, run_id, "edit", {"changes": changes}, command=None, paths=paths)
    result: JsonDict = {"ok": item.get("status") != _FAILED_STATUS, "changes": changes}
    return _pair(request, result, run_id, now)


def _request(
    state: CodexTranslationState,
    run_id: RunId,
    tool: str,
    arguments: JsonDict,
    *,
    command: str | None,
    paths: list[str],
) -> ToolCallRequest:
    state.usage = state.usage.model_copy(update={"tool_calls": state.usage.tool_calls + 1})
    return ToolCallRequest(
        run_id=run_id,
        role=state.role,
        tool=tool,
        kind=ToolKind.PROVIDER_NATIVE,
        arguments=arguments,
        command=command,
        paths=paths,
        worktree_path=state.worktree_path,
    )


def _pair(
    request: ToolCallRequest, result: JsonDict, run_id: RunId, now: datetime
) -> list[AgentEvent]:
    return [
        AgentEvent(
            kind=AgentEventKind.TOOL_CALL_REQUESTED, run_id=run_id, at=now, tool_call=request
        ),
        AgentEvent(
            kind=AgentEventKind.TOOL_CALL_RESULT,
            run_id=run_id,
            at=now,
            tool_call=request,
            tool_result=result,
        ),
    ]


def _turn_completed(
    ev: CodexEvent, state: CodexTranslationState, run_id: RunId, now: datetime
) -> list[AgentEvent]:
    raw = ev.payload.get("usage")
    usage: dict[str, Any] = raw if isinstance(raw, dict) else {}
    cached = int(usage.get("cached_input_tokens", 0) or 0)
    uncached = max(int(usage.get("input_tokens", 0) or 0) - cached, 0)
    total = state.usage
    state.turns += 1
    state.usage = UsageReport(
        input_tokens=total.input_tokens + uncached,
        output_tokens=total.output_tokens + int(usage.get("output_tokens", 0) or 0),
        cache_read_tokens=total.cache_read_tokens + cached,
        cost_usd=0.0,
        turns=total.turns + 1,
        tool_calls=total.tool_calls,
        duration_s=total.duration_s,
    )
    return [AgentEvent(kind=AgentEventKind.USAGE, run_id=run_id, at=now, usage=state.usage)]


def _error_message(ev: CodexEvent) -> str:
    message = ev.payload.get("message")
    if isinstance(message, str) and message:
        return message
    error = ev.payload.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return str(error["message"])
    if isinstance(error, str) and error:
        return error
    return "turn failed" if ev.type == "turn.failed" else "codex error"


def _truncate(text: str) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= _TOOL_OUTPUT_MAX_BYTES:
        return text
    return encoded[:_TOOL_OUTPUT_MAX_BYTES].decode("utf-8", errors="ignore")
