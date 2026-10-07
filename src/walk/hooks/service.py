"""Default hook manager: registry and sequential dispatcher (ARCHITECTURE §4.1, ADR-0009 D-7).

Project hooks (E02-S09) run a shell command through an injected command runner (the kernel's
`SubprocessRunner`, which `walk.hooks` may not import) or an allowlisted kernel action
registered by the composition root.
"""

import asyncio
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final, Literal, Protocol

from walk.common.clock import Clock
from walk.common.errors import ConfigError, Timeout
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
from walk.hooks.project import KERNEL_ACTIONS, ProjectHooksFile, hook_env
from walk.hooks.repository import HookExecutionRepository
from walk.persistence import UnitOfWork
from walk.telemetry.models import LedgerEvent, LedgerEventKind
from walk.telemetry.protocols import LedgerManager

_NO_RUNNER: Final = "no command runner"
_NO_TARGET: Final = "project hook has neither command nor kernel action"


class _CommandResult(Protocol):
    """What the command runner reports (`walk.integrations.SubprocessResult`)."""

    @property
    def exit_code(self) -> int: ...
    @property
    def stderr(self) -> str: ...


class _CommandRunner(Protocol):
    """The kernel's `walk.integrations.SubprocessRunner`, structurally."""

    async def run(
        self,
        argv: list[str],
        *,
        cwd: str | None = ...,
        env: dict[str, str] | None = ...,
        timeout_s: int = ...,
        input_text: str | None = ...,
    ) -> _CommandResult: ...


class _CommandFailed(Exception):
    """A project command exited non-zero; ``str()`` is the recorded message."""


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
        command_runner: _CommandRunner | None = None,
        cwd: str | None = None,
        base_env: Mapping[str, str] | None = None,
    ) -> None:
        """Wire the manager.

        Args:
            repo: Execution records; its database also receives the ledger events.
            ledger: Write point for ``HOOK_EXECUTED``/``HOOK_FAILED`` (ARCHITECTURE §4.3).
            clock: Measures ``duration_ms`` and stamps the records.
            callables: Builtin callables by ``Hook.callable_path``, used when `register` gets
                no ``fn``.
            command_runner: Runs project shell commands (a ``SubprocessRunner``); without it
                a command hook fails by its policy.
            cwd: Working directory of project commands (the repository root).
            base_env: Environment of project commands before the ``WALK_HOOK_*`` variables
                (the scrubbed agent environment: no secrets).
        """
        self._repo = repo
        self._ledger = ledger
        self._clock = clock
        self._callables = dict(callables or {})
        self._hooks: dict[HookName, dict[str, tuple[Hook, HookCallable | None]]] = {}
        self._runner = command_runner
        self._cwd = cwd
        self._base_env = dict(base_env or {})
        self._actions: dict[str, HookCallable] = {}

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
        """Read ``.ai/agents/hooks.yaml`` and register its hooks; return them.

        An absent file declares no hooks. Every hook is validated before any is registered.

        Raises:
            ConfigError: Invalid YAML or schema (naming the hook id), an unknown kernel
                action, or a duplicate id.
        """
        hooks = ProjectHooksFile.load(Path(path)).to_hooks()
        for hook in hooks:
            self.register(hook)
        return hooks

    def set_kernel_actions(self, actions: Mapping[str, HookCallable]) -> None:
        """Make the allowlisted kernel actions available to project hooks.

        The action receives the hook's context with ``payload["hook_id"]`` set to the id of
        the project hook that runs it.

        Raises:
            ConfigError: A name is not in ``KERNEL_ACTIONS``.
        """
        unknown = sorted(set(actions) - set(KERNEL_ACTIONS))
        if unknown:
            msg = f"unknown kernel action(s): {unknown}"
            raise ConfigError(msg, detail={"actions": unknown})
        self._actions.update(actions)

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
            result = await self._execute(hook, fn or self._project_callable(hook), ctx)
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

    def _project_callable(self, hook: Hook) -> HookCallable:
        """What a project hook runs: its kernel action or its command (builtins have ``fn``)."""
        if hook.kernel_action is not None:
            return self._action_callable(hook, hook.kernel_action)
        if hook.command is not None:
            return self._command_callable(hook, hook.command)
        return _failing(_NO_TARGET)

    def _action_callable(self, hook: Hook, action_name: str) -> HookCallable:
        action = self._actions.get(action_name)
        if action is None:
            return _failing(f"kernel action {action_name!r} is not available")

        async def run_action(ctx: HookContext) -> None:
            await action(ctx.model_copy(update={"payload": {**ctx.payload, "hook_id": hook.id}}))

        return run_action

    def _command_callable(self, hook: Hook, command: str) -> HookCallable:
        runner = self._runner
        if runner is None:
            return _failing(_NO_RUNNER)

        async def run_command(ctx: HookContext) -> None:
            result = await runner.run(
                _shell_argv(command, self._base_env),
                cwd=self._cwd,
                env=hook_env(ctx, self._base_env),
                timeout_s=hook.timeout_s,
            )
            if result.exit_code != 0:
                raise _CommandFailed(_failure_message(result))

        return run_command

    def _is_required_builtin(self, hook_id: str) -> bool:
        return any(
            hook.kind == "builtin" and hook.required and hook.id == hook_id
            for by_id in self._hooks.values()
            for hook, _ in by_id.values()
        )

    def _ordered(self, name: HookName) -> list[tuple[Hook, HookCallable | None]]:
        entries = [entry for entry in self._hooks.get(name, {}).values() if entry[0].enabled]
        return sorted(entries, key=lambda entry: (entry[0].priority, entry[0].id))

    async def _execute(self, hook: Hook, fn: HookCallable, ctx: HookContext) -> HookResult:
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
    hook: Hook, fn: HookCallable, ctx: HookContext
) -> tuple[Literal["OK", "FAILED", "TIMEOUT"], str]:
    """Run one hook under its timeout; never raises except on cancellation."""
    timeout = asyncio.timeout(hook.timeout_s)
    try:
        async with timeout:
            await fn(ctx)
    except (TimeoutError, Timeout) as exc:
        # Our deadline, or the command runner killing a project command at its timeout;
        # a TimeoutError raised by the hook itself is a failure.
        if timeout.expired() or isinstance(exc, Timeout):
            return "TIMEOUT", f"exceeded {hook.timeout_s} s"
        return "FAILED", _describe(exc)
    except _CommandFailed as exc:
        return "FAILED", str(exc)
    except Exception as exc:  # noqa: BLE001 - any hook failure is recorded and judged by fail_policy
        return "FAILED", _describe(exc)
    return "OK", ""


def _describe(exc: Exception) -> str:
    text = str(exc)
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


def _failing(message: str) -> HookCallable:
    async def fail(ctx: HookContext) -> None:
        del ctx
        raise _CommandFailed(message)

    return fail


def _shell_argv(command: str, env: Mapping[str, str]) -> list[str]:
    """``command`` run by the platform shell: ``%COMSPEC% /d /s /c`` or ``/bin/sh -c``."""
    if sys.platform == "win32":
        comspec = next((v for k, v in env.items() if k.upper() == "COMSPEC"), "cmd.exe")
        return [comspec, "/d", "/s", "/c", command]
    return ["/bin/sh", "-c", command]


def _failure_message(result: _CommandResult) -> str:
    lines = [line.strip() for line in result.stderr.splitlines() if line.strip()]
    return lines[-1] if lines else f"exit code {result.exit_code}"
