"""Shared `AgentOutput` parsing for every adapter (ADR-0004 D-3).

The agent writes its structured output to `<worktree>/.walk/output.json` (the mandatory
fallback channel). `parse_agent_output` reports field errors as ``<loc>: <msg>`` lines, which
the executor quotes verbatim in the repair turn.
"""

import json
from pathlib import Path

from pydantic import ValidationError

from walk.agents.models import AgentOutput
from walk.common.errors import OutputInvalid

OUTPUT_RELATIVE_PATH = ".walk/output.json"
_FENCE = "```"
_ROOT_LOC = "(output)"


def parse_agent_output(raw: str) -> AgentOutput:
    """Parse ``raw`` (a JSON object, optionally in one ```json fence) into an `AgentOutput`.

    Raises:
        OutputInvalid: Not a single JSON object, or not a valid `AgentOutput`;
            ``detail["errors"]`` lists ``<loc>: <msg>`` lines.
    """
    text = _unfence(raw.strip())
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _invalid([f"{_ROOT_LOC}: not valid JSON ({exc.msg})"]) from exc
    if not isinstance(data, dict):
        raise _invalid([f"{_ROOT_LOC}: expected a JSON object"])
    try:
        return AgentOutput.model_validate(data)
    except ValidationError as exc:
        lines = [
            f"{'.'.join(str(p) for p in err['loc']) or _ROOT_LOC}: {err['msg']}"
            for err in exc.errors()
        ]
        raise _invalid(lines) from exc


def read_output_file(path: Path) -> str | None:
    """The text of ``path`` (UTF-8), or None when the agent did not write it."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _unfence(text: str) -> str:
    if not text.startswith(_FENCE):
        return text
    first_newline = text.find("\n")
    if first_newline < 0 or not text.endswith(_FENCE):
        return text
    return text[first_newline + 1 : -len(_FENCE)].strip()


def _invalid(lines: list[str]) -> OutputInvalid:
    msg = "agent output invalid:\n" + "\n".join(lines)
    return OutputInvalid(msg, detail={"errors": lines})
