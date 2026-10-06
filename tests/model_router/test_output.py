from pathlib import Path

import pytest

from walk.agents import AgentOutput, AgentOutputStatus
from walk.common.errors import OutputInvalid
from walk.model_router import OUTPUT_RELATIVE_PATH, parse_agent_output, read_output_file

VALID = AgentOutput(
    status=AgentOutputStatus.COMPLETED, result="done", no_context_change_reason="none"
)


def test_parse_agent_output_accepts_fence_and_lists_errors() -> None:
    fenced = f"```json\n{VALID.model_dump_json()}\n```\n"

    assert parse_agent_output(fenced) == VALID
    assert parse_agent_output(VALID.model_dump_json()) == VALID
    assert parse_agent_output(f"```\n{VALID.model_dump_json()}\n```") == VALID
    with pytest.raises(OutputInvalid) as info:
        parse_agent_output('{"status": "BOGUS"}')
    errors = info.value.detail["errors"]
    assert any(line.startswith("status: ") for line in errors)
    assert any(line.startswith("result: ") for line in errors)
    assert "status: " in info.value.message


def test_parse_agent_output_rejects_non_objects_and_rule_violations() -> None:
    unclosed = ("```{}", "```json\n{}")
    for raw in ("not json", "[1, 2]", "", "```json\n{}\n```\n```json\n{}\n```", *unclosed):
        with pytest.raises(OutputInvalid):
            parse_agent_output(raw)
    with pytest.raises(OutputInvalid) as info:
        parse_agent_output(
            '{"status": "PARTIAL", "result": "half", "no_context_change_reason": "x"}'
        )
    assert info.value.detail["errors"][0].startswith("(output): ")
    assert "handover" in info.value.detail["errors"][0]


def test_read_output_file_missing_returns_none(tmp_path: Path) -> None:
    path = tmp_path / OUTPUT_RELATIVE_PATH

    assert read_output_file(path) is None
    path.parent.mkdir(parents=True)
    path.write_text('{"status": "FAILED", "result": "x"}', encoding="utf-8")
    assert read_output_file(path) == '{"status": "FAILED", "result": "x"}'
    assert OUTPUT_RELATIVE_PATH == ".walk/output.json"
