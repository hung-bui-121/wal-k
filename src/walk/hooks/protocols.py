"""Hook service protocol (INTERFACES §1.11)."""

from typing import Protocol

from walk.hooks.models import Hook, HookCallable, HookContext, HookName, HookResult


class HookManager(Protocol):
    """§32. Hosted by walk.hooks — registry and dispatcher only.

    Built-in callables live in `walk.orchestrator.builtin_hooks` and are registered once by
    the composition root via `register_builtins(manager, deps)` (ADR-0016).
    """

    def register(self, hook: Hook, fn: HookCallable | None = None) -> None:
        """Add a hook; `builtin` hooks need `fn`, project hooks pass None.

        Raises ConfigError on a duplicate (name, id) and if a project hook tries to
        disable/replace a `required` builtin.
        """
        ...

    def load_project_hooks(self, path: str) -> list[Hook]:
        """Register the hooks of `.ai/agents/hooks.yaml` and return them (absent file: []).

        Raises ConfigError on invalid YAML/schema, an unknown kernel action or a duplicate id.
        """
        ...

    async def fire(self, name: HookName, ctx: HookContext) -> list[HookResult]:
        """Run hooks for `name` ordered by priority, sequentially, each with timeout.

        FAIL_CLOSED failure raises HookFailed after recording; LOG_AND_CONTINUE records and
        continues. Every execution → hook_executions + ledger HOOK_EXECUTED/HOOK_FAILED.
        """
        ...

    def hooks_for(self, name: HookName) -> list[Hook]:
        """Return the enabled hooks of `name` in execution order (priority, then id)."""
        ...
