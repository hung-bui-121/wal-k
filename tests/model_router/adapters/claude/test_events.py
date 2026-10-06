import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from tests.fakes.fake_claude_client import (
    AssistantMessage,
    RedactedThinkingBlock,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    scripted_messages,
)
from walk.common.roles import AgentRole
from walk.model_router import AgentEvent, AgentEventKind
from walk.model_router.adapters.claude.events import ClaudeTranslationState, translate_message

RUN = "RUN-01J00000000000000000000000"
AT = datetime(2026, 1, 1, tzinfo=UTC)
K = AgentEventKind
HIDDEN_REASONING = "hidden chain of thought about the release plan"
DONE = {"status": "COMPLETED", "result": "done", "no_context_change_reason": "x"}


def _state(tmp_path: Path) -> ClaudeTranslationState:
    return ClaudeTranslationState(
        role=AgentRole.SENIOR_DEV,
        worktree_path=str(tmp_path),
        output_path=str(tmp_path / ".walk" / "output.json"),
    )


def _translate_all(messages: list[object], state: ClaudeTranslationState) -> list[AgentEvent]:
    events: list[AgentEvent] = []
    for message in messages:
        events.extend(translate_message(message, state, RUN, AT))
    return events


def test_thinking_blocks_are_dropped(tmp_path: Path) -> None:
    messages = scripted_messages(thinking=HIDDEN_REASONING, structured_output=DONE)
    messages.insert(2, AssistantMessage(content=[RedactedThinkingBlock(data=HIDDEN_REASONING)]))
    events = _translate_all(messages, _state(tmp_path))

    assert [e.kind for e in events] == [
        K.STARTED,
        K.TEXT,
        K.TOOL_CALL_RESULT,
        K.USAGE,
        K.FINAL_OUTPUT,
        K.ENDED,
    ]
    for event in events:
        assert HIDDEN_REASONING not in event.model_dump_json()


def test_init_sets_session_and_tool_result_carries_request(tmp_path: Path) -> None:
    state = _state(tmp_path)
    events = _translate_all(scripted_messages(structured_output=DONE), state)

    started = events[0]
    assert started.session is not None
    assert started.session.provider == "claude"
    assert started.session.session_id == "sess-1"
    assert started.session.resumable is True
    assert state.session_id == "sess-1"

    result = next(e for e in events if e.kind is K.TOOL_CALL_RESULT)
    assert result.tool_result == {"ok": True, "content": "edited"}
    assert result.tool_call is not None
    assert result.tool_call.tool == "edit"
    assert result.tool_call.paths == ["src/A.cs"]
    assert state.pending_tool_calls == {}


def test_result_usage_and_structured_output(tmp_path: Path) -> None:
    state = _state(tmp_path)
    events = _translate_all(scripted_messages(structured_output=DONE), state)

    usage = next(e for e in events if e.kind is K.USAGE).usage
    assert usage is not None
    assert usage.input_tokens == 1100  # input + cache creation
    assert usage.output_tokens == 200
    assert usage.cache_read_tokens == 500
    assert usage.cost_usd == 0.25
    assert usage.turns == 3
    assert usage.tool_calls == 1
    assert usage.duration_s == 2.5
    assert state.usage == usage
    final = next(e for e in events if e.kind is K.FINAL_OUTPUT)
    assert final.output is not None
    assert final.output.result == "done"
    assert final.error is None


def test_result_without_cost_or_usage_counts_zero(tmp_path: Path) -> None:
    state = _state(tmp_path)
    result = ResultMessage(session_id="s", total_cost_usd=None, usage=None, structured_output=DONE)
    events = translate_message(result, state, RUN, AT)
    assert [e.kind for e in events] == [K.STARTED, K.USAGE, K.FINAL_OUTPUT, K.ENDED]
    usage = events[1].usage
    assert usage is not None
    assert (usage.input_tokens, usage.output_tokens, usage.cost_usd) == (0, 0, 0.0)
    assert state.session_id == "s"


def test_output_file_is_the_fallback_channel(tmp_path: Path) -> None:
    state = _state(tmp_path)
    output = tmp_path / ".walk" / "output.json"
    output.parent.mkdir()
    output.write_text(json.dumps(DONE), encoding="utf-8")
    events = translate_message(ResultMessage(session_id="s"), state, RUN, AT)
    final = next(e for e in events if e.kind is K.FINAL_OUTPUT)
    assert final.output is not None
    assert final.output.status.value == "COMPLETED"


def test_invalid_structured_output_is_repairable(tmp_path: Path) -> None:
    state = _state(tmp_path)
    result = ResultMessage(session_id="s", structured_output={"status": "BOGUS"})
    final = next(e for e in translate_message(result, state, RUN, AT) if e.kind is K.FINAL_OUTPUT)
    assert final.output is None
    assert final.error is not None
    assert "status" in final.error


def test_error_result_emits_usage_then_error(tmp_path: Path) -> None:
    state = _state(tmp_path)
    events = translate_message(
        ResultMessage(session_id="s", is_error=True, result="boom"), state, RUN, AT
    )
    assert [e.kind for e in events] == [K.STARTED, K.USAGE, K.ERROR]
    assert events[-1].error == "boom"
    assert events[-1].trigger is None

    no_text = ResultMessage(session_id="s", is_error=True, result=None, subtype="error_max_turns")
    assert translate_message(no_text, state, RUN, AT)[-1].error == "error_max_turns"


def test_tool_result_content_is_flattened_and_truncated(tmp_path: Path) -> None:
    state = _state(tmp_path)
    translate_message(
        AssistantMessage(content=[ToolUseBlock(id="t1", name="Bash", input={"command": "ls"})]),
        state,
        RUN,
        AT,
    )
    long_text = "x" * 5000
    blocks: list[object] = [
        ToolResultBlock(
            tool_use_id="t1",
            content=[{"type": "text", "text": long_text}, {"type": "image", "data": "..."}],
            is_error=True,
        ),
        ToolResultBlock(tool_use_id="unknown", content=None),
        TextBlock(text="not a tool result"),
        ToolResultBlock(tool_use_id="other", content=cast("Any", 42)),
    ]
    events = translate_message(UserMessage(content=blocks), state, RUN, AT)
    first, second, third = events
    assert third.tool_result == {"ok": True, "content": "42"}
    assert first.tool_result is not None
    assert first.tool_result["ok"] is False
    assert len(first.tool_result["content"].encode("utf-8")) == 4096
    assert first.tool_call is not None
    assert first.tool_call.command == "ls"
    assert second.tool_result == {"ok": True, "content": ""}
    assert second.tool_call is None


def test_other_messages_produce_no_events(tmp_path: Path) -> None:
    state = _state(tmp_path)
    assert translate_message(SystemMessage(subtype="status", data={}), state, RUN, AT) == []
    assert translate_message(UserMessage(content="plain prompt echo"), state, RUN, AT) == []
    assert translate_message(AssistantMessage(content=[TextBlock(text="  ")]), state, RUN, AT) == []
    assert translate_message(object(), state, RUN, AT) == []
    first = translate_message(
        SystemMessage(subtype="init", data={"session_id": "a"}), state, RUN, AT
    )
    again = translate_message(
        SystemMessage(subtype="init", data={"session_id": "a"}), state, RUN, AT
    )
    assert [e.kind for e in first] == [K.STARTED]
    assert again == []
    assert state.turns == 1
