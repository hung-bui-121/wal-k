"""Codex adapter (ADR-0004 D-8): the only package that spawns the `codex` CLI."""

from walk.model_router.adapters.codex.adapter import CodexAdapter

__all__ = ["CodexAdapter"]
