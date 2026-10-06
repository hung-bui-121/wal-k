"""Claude adapter (ADR-0004 D-7): the only package that uses `claude_agent_sdk`."""

from walk.model_router.adapters.claude.adapter import ClaudeAdapter

__all__ = ["ClaudeAdapter"]
