import json
from datetime import UTC, datetime
from pathlib import Path

import tests.fixtures.codex
from walk.common.roles import AgentRole
from walk.model_router import AgentEvent, AgentEventKind
from walk.model_router.adapters.codex.events import (
    CodexEvent,
    CodexTranslationState,
    parse_codex_line,
    translate_codex_event,
)

FIXTURES = Path(tests.fixtures.codex.__file__).resolve().parent
RUN = "RUN-01J00000000000000000000000"
AT = datetime(2026, 1, 1, tzinfo=UTC)
K = AgentEventKind


def _state() -> CodexTranslationState:
    return CodexTranslationState(role=AgentRole.SENIOR_DEV, worktree_path="/wt")


def _translate(lines: list[str], state: CodexTranslationState) -> list[AgentEvent]:
    events: list[AgentEvent] = []
    for line in lines:
        parsed = parse_codex_line(line)
        if parsed is not None:
            events.extend(translate_codex_event(parsed, state, RUN, AT))
    return events


def _fixture(name: str) -> list[str]:
    return (FIXTURES / name).read_text(encoding="utf-8").splitlines()


def test_reasoning_items_dropped() -> None:
    events = _translate(_fixture("exec_success.jsonl"), _state())

    assert [e.kind for e in events] == [
        K.STARTED,
        K.TEXT,
        K.TOOL_CALL_REQUESTED,
        K.TOOL_CALL_RESULT,
        K.TOOL_CALL_REQUESTED,
        K.TOOL_CALL_RESULT,
        K.USAGE,
    ]
    for event in events:
        assert "hidden chain of thought" not in event.model_dump_json()


def test_parse_codex_line() -> None:
    assert parse_codex_line("not json") is None
    assert parse_codex_line("") is None
    assert parse_codex_line("   ") is None
    assert parse_codex_line("[1, 2]") is None
    assert parse_codex_line('{"no_type": true}') is None
    line = (
        '{"type":"item.completed","item":{"id":"item_2","type":"command_execution",'
        '"command":"ls","aggregated_output":"","exit_code":0}}'
    )
    event = parse_codex_line(line)
    assert event == CodexEvent(
        type="item.completed",
        item_type="command_execution",
        item_id="item_2",
        payload=json.loads(line),
    )
    started = parse_codex_line('{"type":"thread.started","thread_id":"t"}')
    assert started is not None
    assert started.item_type is None
    assert started.item_id is None


def test_tool_items_become_post_hoc_pairs() -> None:
    state = _state()
    events = _translate(_fixture("exec_success.jsonl"), state)

    bash_request, bash_result = events[2], events[3]
    assert bash_request.tool_call is not None
    assert bash_request.tool_call.tool == "bash"
    assert bash_request.tool_call.command == "dotnet test"
    assert bash_request.tool_call.worktree_path == "/wt"
    assert bash_request.tool_call.role is AgentRole.SENIOR_DEV
    assert bash_result.tool_call == bash_request.tool_call
    assert bash_result.tool_result == {"ok": True, "exit_code": 0, "output": "Passed! 12 tests"}

    edit_request, edit_result = events[4], events[5]
    assert edit_request.tool_call is not None
    assert edit_request.tool_call.tool == "edit"
    assert edit_request.tool_call.paths == ["src/A.cs"]
    assert edit_result.tool_result == {
        "ok": True,
        "changes": [{"path": "src/A.cs", "kind": "update"}],
    }
    assert state.thread_id == "thr_1"
    assert state.last_agent_message is not None
    assert "tests pass" in state.last_agent_message


def test_turn_completed_accumulates_usage() -> None:
    state = _state()
    events = _translate(_fixture("exec_success.jsonl"), state)
    usage = events[-1].usage
    assert usage is not None
    assert usage.input_tokens == 1000  # uncached part of input_tokens
    assert usage.cache_read_tokens == 200
    assert usage.output_tokens == 300
    assert usage.cost_usd == 0.0
    assert usage.turns == 1
    assert usage.tool_calls == 2

    _translate(_fixture("exec_resume.jsonl"), state)
    assert state.usage.input_tokens == 1100
    assert state.usage.cache_read_tokens == 600
    assert state.usage.turns == 2
    assert state.usage.tool_calls == 3


def test_errors_and_failed_items() -> None:
    state = _state()
    events = _translate(_fixture("exec_error_rate_limit.jsonl"), state)
    assert [e.kind for e in events] == [K.STARTED, K.ERROR, K.ERROR]
    assert events[1].error == "stream disconnected before completion: 429 Too Many Requests"
    assert events[1].trigger is None
    assert events[2].error == "rate limit exceeded, retry later"
    assert state.errors == [events[1].error, events[2].error]

    failed = [
        (
            '{"type":"item.completed","item":{"id":"a","type":"command_execution","command":"x",'
            '"aggregated_output":"' + "y" * 5000 + '","exit_code":2}}'
        ),
        (
            '{"type":"item.completed","item":{"id":"b","type":"file_change","changes":'
            '[{"path":"a.cs","kind":"add"},{"kind":"delete"}],"status":"failed"}}'
        ),
        '{"type":"turn.failed","error":"plain text"}',
        '{"type":"turn.failed"}',
        '{"type":"error"}',
    ]
    events = _translate(failed, _state())
    command = events[1].tool_result
    assert command is not None
    assert command["ok"] is False
    assert command["exit_code"] == 2
    assert len(command["output"].encode("utf-8")) == 4096
    edit = events[3]
    assert edit.tool_result is not None
    assert edit.tool_result["ok"] is False
    assert edit.tool_call is not None
    assert edit.tool_call.paths == ["a.cs"]
    assert [e.error for e in events[4:]] == ["plain text", "turn failed", "codex error"]


def test_duplicate_and_unknown_items_are_skipped() -> None:
    state = _state()
    line = '{"type":"item.completed","item":{"id":"m1","type":"agent_message","text":"hello"}}'
    assert [e.kind for e in _translate([line], state)] == [K.TEXT]
    assert _translate([line], state) == []
    assert (
        _translate(['{"type":"item.completed","item":{"id":"w","type":"web_search"}}'], state) == []
    )
    assert _translate(['{"type":"item.completed","item":"broken"}'], state) == []
    assert _translate(['{"type":"something.new"}', '{"type":"turn.started"}'], state) == []
    assert _translate(['{"type":"thread.started"}'], state) == []
