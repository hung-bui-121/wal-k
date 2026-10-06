"""Non-billable Claude Agent SDK probe for ADR-0014: introspection only, no query() call.

Run: uv run --no-project --with claude-agent-sdk python scripts/spikes/claude_probe.py
"""

import dataclasses
import importlib.metadata
import inspect
import typing

import claude_agent_sdk as sdk

OPTIONS = [
    "cwd",
    "allowed_tools",
    "disallowed_tools",
    "permission_mode",
    "can_use_tool",
    "model",
    "fallback_model",
    "effort",
    "thinking",
    "max_turns",
    "max_budget_usd",
    "resume",
    "fork_session",
    "output_format",
    "env",
    "setting_sources",
    "system_prompt",
    "tools",
]
RESULT_FIELDS = [
    "session_id",
    "usage",
    "total_cost_usd",
    "structured_output",
    "num_turns",
    "is_error",
    "subtype",
    "duration_ms",
]


def main() -> None:
    print("claude-agent-sdk", importlib.metadata.version("claude-agent-sdk"))
    fields = {f.name for f in dataclasses.fields(sdk.ClaudeAgentOptions)}
    for name in OPTIONS:
        print(f"ClaudeAgentOptions.{name}: {'present' if name in fields else 'MISSING'}")
    print("query signature:", inspect.signature(sdk.query))
    result = {f.name for f in dataclasses.fields(sdk.ResultMessage)}
    for name in RESULT_FIELDS:
        print(f"ResultMessage.{name}: {'present' if name in result else 'MISSING'}")
    for alias in ("PermissionMode", "EffortLevel"):
        value = getattr(sdk.types, alias, None)
        print(alias, typing.get_args(value) if value is not None else "MISSING")


if __name__ == "__main__":
    main()
