"""Default hook manager: registry and sequential dispatcher (ARCHITECTURE §4.1, ADR-0009 D-7)."""

import asyncio
from typing import Literal

from walk.common.clock import Clock
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.hooks.errors import HookFailed
from walk.hooks.models import (
    Hook,
    HookCallable,
    HookContext,
    HookFailPolicy,
    HookName,
    HookResult,
)
from walk.hooks.repository import HookExecutionRepository
from walk.persistence import UnitOfWork
from walk.telemetry.models import LedgerEvent, LedgerEventKind
from walk.telemetry.protocols import LedgerManager

_PROJECT_HOOKS_UNAVAILABLE = "project hooks are available from E02-S09"
_LEDGER_OUTCOME: dict[str, Literal["OK", "FAILED", "SKIPPED"]] = {
    "OK": "OK",
    "FAILED": "FAILED",
    "TIMEOUT": "FAILED",
    "SKIPPED": "SKIPPED",
}


class DefaultHookManager:
    """`HookManager` that runs hooks in-process and records every execution.

    Hooks run strictly one after another, so they must be fired outside any open unit of work
    on the same database (normally from `UnitOfWork.after_commit`): each execution is recorded
    in its own unit of work after the hook has returned.
    """

    def __init__(
        self,
        repo: HookExecutionRepository,
        ledger: LedgerManager,
        clock: Clock,
        *,
        callables: dict[str, HookCallable] | None = None,
    ) -> None:
        """Wire the manager.

        Args:
            repo: Execution records; its database also receives the ledger events.
            ledger: Write point for ``HOOK_EXECUTED``/``HOOK_FAILED`` (ARCHITECTURE §4.3).
            clock: Measures ``duration_ms`` and stamps the records.
            callables: Builtin callables by ``Hook.callable_path``, used when `register` gets
                no ``fn``.
        """
        self._repo = repo
        self._ledger = ledger
        self._clock = clock
        self._callables = dict(callables or {})
        self._hooks: dict[HookName, dict[str, tuple[Hook, HookCallable | None]]] = {}

    def register(self, hook: Hook, fn: HookCallable | None = None) -> None:
        """Add ``hook``; builtins need ``fn`` or a ``callable_path`` known to the manager.

        Raises:
            ConfigError: On a duplicate ``(name, id)``; a project hook whose id is a required
                builtin's; a disabled required hook; a builtin without a resolvable callable;
                a project hook given a callable.
        """
        detail = {"hook_name": hook.name.value, "hook_id": hook.id}
        if hook.kind == "project" and self._is_required_builtin(hook.id):
            msg = f"project hook cannot replace required builtin {hook.id!r}"
            raise ConfigError(msg, detail=detail)
        if hook.id in self._hooks.get(hook.name, {}):
            msg = f"duplicate hook {hook.name.value}/{hook.id}"
            raise ConfigError(msg, detail=detail)
        if hook.required and not hook.enabled:
            msg = f"required hook {hook.id!r} cannot be disabled"
            raise ConfigError(msg, detail=detail)
        if hook.kind == "builtin":
            if fn is None and hook.callable_path is not None:
                fn = self._callables.get(hook.callable_path)
            if fn is None:
                msg = f"builtin hook {hook.id!r} needs a callable"
                raise ConfigError(msg, detail=detail | {"callable_path": hook.callable_path})
        elif fn is not None:
            msg = f"project hook {hook.id!r} takes no callable; it runs its command or action"
            raise ConfigError(msg, detail=detail)
        self._hooks.setdefault(hook.name, {})[hook.id] = (hook, fn)

    def load_project_hooks(self, path: str) -> list[Hook]:
        """Read ``.ai/agents/hooks.yaml``; not available before E02-S09.

        Raises:
            ConfigError: Always, until E02-S09 implements project hooks.
        """
        raise ConfigError(_PROJECT_HOOKS_UNAVAILABLE, detail={"path": path})

    def hooks_for(self, name: HookName) -> list[Hook]:
        """Return the enabled hooks of ``name`` by priority, then id."""
        return [hook for hook, _ in self._ordered(name)]

    async def fire(self, name: HookName, ctx: HookContext) -> list[HookResult]:
        """Run the enabled hooks of ``name`` in order and record each execution.

        Returns:
            One result per executed hook; ``[]`` (and no records) when none is registered.

        Raises:
            ConfigError: If ``ctx`` was built for another hook name.
            HookFailed: After recording, when a ``FAIL_CLOSED`` hook fails or times out; the
                remaining hooks are not run.
        """
        if ctx.name is not name:
            msg = f"hook context is for {ctx.name.value}, fired as {name.value}"
            raise ConfigError(msg, detail={"hook_name": name.value})
        results: list[HookResult] = []
        for hook, fn in self._ordered(name):
            result = await self._execute(hook, fn, ctx)
            results.append(result)
            if result.status != "OK" and hook.fail_policy is HookFailPolicy.FAIL_CLOSED:
                msg = f"hook {name.value}/{hook.id} failed: {result.status}"
                raise HookFailed(
                    msg,
                    detail={
                        "hook_name": name.value,
                        "hook_id": hook.id,
                        "results": [r.model_dump(mode="json") for r in results],
                    },
                )
        return results

    def _is_required_builtin(self, hook_id: str) -> bool:
        return any(
            hook.kind == "builtin" and hook.required and hook.id == hook_id
            for by_id in self._hooks.values()
            for hook, _ in by_id.values()
        )

    def _ordered(self, name: HookName) -> list[tuple[Hook, HookCallable | None]]:
        entries = [entry for entry in self._hooks.get(name, {}).values() if entry[0].enabled]
        return sorted(entries, key=lambda entry: (entry[0].priority, entry[0].id))

    async def _execute(self, hook: Hook, fn: HookCallable | None, ctx: HookContext) -> HookResult:
        started = self._clock.now()
        status, message = await _run(hook, fn, ctx)
        duration_ms = int((self._clock.now() - started).total_seconds() * 1000)
        result = HookResult(
            hook_id=hook.id, status=status, duration_ms=duration_ms, message=message
        )
        event = LedgerEvent(
            kind=LedgerEventKind.HOOK_EXECUTED if status == "OK" else LedgerEventKind.HOOK_FAILED,
            at=started,
            project_key=ctx.project_key,
            actor_role=AgentRole.KERNEL,
            work_item_id=ctx.work_item_id,
            run_id=ctx.run_id,
            phase_id=ctx.phase_id,
            duration_ms=duration_ms,
            outcome=_LEDGER_OUTCOME[status],
            payload={
                "hook_name": hook.name.value,
                "hook_id": hook.id,
                "kind": hook.kind,
                "status": status,
                "fail_policy": hook.fail_policy.value,
                "message": message,
            },
        )
        async with UnitOfWork(self._repo.db) as uow:
            await self._repo.insert(ctx, result, at=started, uow=uow)
            await self._ledger.append(event, uow=uow)
        return result


async def _run(
    hook: Hook, fn: HookCallable | None, ctx: HookContext
) -> tuple[Literal["OK", "FAILED", "TIMEOUT"], str]:
    """Run one hook under its timeout; never raises except on cancellation."""
    if fn is None:
        return "FAILED", _PROJECT_HOOKS_UNAVAILABLE
    timeout = asyncio.timeout(hook.timeout_s)
    try:
        async with timeout:
            await fn(ctx)
    except TimeoutError as exc:
        # Distinguish our deadline from a TimeoutError raised by the hook itself.
        if timeout.expired():
            return "TIMEOUT", f"exceeded {hook.timeout_s} s"
        return "FAILED", _describe(exc)
    except Exception as exc:  # noqa: BLE001 - any hook failure is recorded and judged by fail_policy
        return "FAILED", _describe(exc)
    return "OK", ""


def _describe(exc: Exception) -> str:
    text = str(exc)
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__
