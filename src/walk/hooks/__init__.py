"""Lifecycle hooks: registry and dispatcher (§32, ADR-0016)."""

from walk.hooks.errors import HookFailed
from walk.hooks.models import (
    Hook,
    HookCallable,
    HookContext,
    HookFailPolicy,
    HookName,
    HookResult,
)
from walk.hooks.project import ProjectHooksFile
from walk.hooks.protocols import HookManager
from walk.hooks.repository import HookExecutionRepository
from walk.hooks.service import DefaultHookManager

__all__ = [
    "DefaultHookManager",
    "Hook",
    "HookCallable",
    "HookContext",
    "HookExecutionRepository",
    "HookFailPolicy",
    "HookFailed",
    "HookManager",
    "HookName",
    "HookResult",
    "ProjectHooksFile",
]
