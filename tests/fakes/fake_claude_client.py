"""Scripted `ClaudeClient` for tests (E01-S21).

The message classes mimic the `claude_agent_sdk` dataclasses by type name and attributes, which
is all `translate_message` inspects. The fake calls ``can_use_tool`` after yielding an assistant
message that contains a ``ToolUseBlock``, the way the SDK asks for permission before it runs the
tool and reports its result.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from walk.common.models import JsonDict
from walk.model_router.adapters.claude.client import ClaudeQueryOptions, SdkMessage


@dataclass
class SystemMessage:
    """Mimics `claude_agent_sdk.SystemMessage`."""

    subtype: str
    data: dict[str, Any]


@dataclass
class TextBlock:
    """Mimics `claude_agent_sdk.TextBlock`."""

    text: str


@dataclass
class ThinkingBlock:
    """Mimics `claude_agent_sdk.ThinkingBlock`."""

    thinking: str
    signature: str = "sig"


@dataclass
class RedactedThinkingBlock:
    """A redacted thinking block (API content type; dropped like thinking)."""

    data: str


@dataclass
class ToolUseBlock:
    """Mimics `claude_agent_sdk.ToolUseBlock`."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ToolResultBlock:
    """Mimics `claude_agent_sdk.ToolResultBlock`."""

    tool_use_id: str
    content: str | list[dict[str, Any]] | None = None
    is_error: bool | None = None


@dataclass
class AssistantMessage:
    """Mimics `claude_agent_sdk.AssistantMessage`."""

    content: list[object]
    model: str = "claude-opus-5-5"


@dataclass
class UserMessage:
    """Mimics `claude_agent_sdk.UserMessage`."""

    content: str | list[object]


@dataclass
class ResultMessage:
    """Mimics `claude_agent_sdk.ResultMessage`."""

    session_id: str
    subtype: str = "success"
    duration_ms: int = 2500
    is_error: bool = False
    num_turns: int = 3
    total_cost_usd: float | None = 0.25
    usage: dict[str, Any] | None = field(
        default_factory=lambda: {
            "input_tokens": 1000,
            "output_tokens": 200,
            "cache_creation_input_tokens": 100,
            "cache_read_input_tokens": 500,
        }
    )
    result: str | None = "done"
    structured_output: Any = None


def scripted_messages(
    *,
    session_id: str = "sess-1",
    text: str = "Editing the file.",
    thinking: str | None = None,
    tool_name: str = "Edit",
    tool_input: dict[str, Any] | None = None,
    tool_output: str = "edited",
    tool_error: bool = False,
    structured_output: Any = None,
    is_error: bool = False,
) -> list[object]:
    """init, assistant text (after an optional thinking block), tool_use, tool_result, result."""
    blocks: list[object] = []
    if thinking is not None:
        blocks.append(ThinkingBlock(thinking=thinking))
    blocks.append(TextBlock(text=text))
    arguments = tool_input if tool_input is not None else {"file_path": "src/A.cs"}
    return [
        SystemMessage(subtype="init", data={"session_id": session_id, "model": "claude-opus-5-5"}),
        AssistantMessage(content=blocks),
        AssistantMessage(content=[ToolUseBlock(id="toolu_1", name=tool_name, input=arguments)]),
        UserMessage(
            content=[
                ToolResultBlock(tool_use_id="toolu_1", content=tool_output, is_error=tool_error)
            ]
        ),
        ResultMessage(
            session_id=session_id,
            is_error=is_error,
            subtype="error_during_execution" if is_error else "success",
            result="model overloaded" if is_error else "done",
            structured_output=structured_output,
        ),
    ]


class FakeClaudeClient:
    """Plays ``messages`` back; records queries, permission results and interrupts.

    ``error`` is raised before the message at index ``error_at``; the stream blocks forever
    before the message at index ``hang_at`` (use an index past the end to hang after the last).
    """

    def __init__(
        self,
        messages: list[object] | None = None,
        *,
        error: Exception | None = None,
        error_at: int = 0,
        hang_at: int | None = None,
        available: tuple[bool, str] = (True, "2.1.0 (Claude Code)"),
    ) -> None:
        """Script the stream and what `available` reports."""
        self.messages = messages if messages is not None else scripted_messages()
        self.error = error
        self.error_at = error_at
        self.hang_at = hang_at
        self.available_result = available
        self.queries: list[tuple[str, ClaudeQueryOptions]] = []
        self.permission_results: list[JsonDict] = []
        self.interrupts: list[str] = []
        self.available_calls = 0

    def query(
        self,
        prompt: str,
        options: ClaudeQueryOptions,
        can_use_tool: Callable[[str, JsonDict], Awaitable[JsonDict]],
    ) -> AsyncIterator[SdkMessage]:
        """Record the query and return the scripted stream."""
        self.queries.append((prompt, options))
        return self._stream(can_use_tool)

    async def available(self) -> tuple[bool, str]:
        """The scripted availability; counts calls."""
        self.available_calls += 1
        return self.available_result

    async def interrupt(self, session_id: str) -> None:
        """Record the interrupted session."""
        self.interrupts.append(session_id)

    async def _stream(
        self, can_use_tool: Callable[[str, JsonDict], Awaitable[JsonDict]]
    ) -> AsyncIterator[SdkMessage]:
        for index in range(len(self.messages) + 1):
            if self.error is not None and index == self.error_at:
                raise self.error
            if index == self.hang_at:
                await asyncio.Event().wait()
            if index == len(self.messages):
                return
            message = self.messages[index]
            yield message
            for block in getattr(message, "content", None) or []:
                if isinstance(block, ToolUseBlock):
                    result = await can_use_tool(block.name, dict(block.input))
                    self.permission_results.append(result)


__all__ = [
    "AssistantMessage",
    "FakeClaudeClient",
    "RedactedThinkingBlock",
    "ResultMessage",
    "SystemMessage",
    "TextBlock",
    "ThinkingBlock",
    "ToolResultBlock",
    "ToolUseBlock",
    "UserMessage",
    "scripted_messages",
]
