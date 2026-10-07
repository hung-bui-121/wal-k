"""Builtin MUST hooks of ARCHITECTURE §4.1 (§32; ADR-0016; E02-S08).

`register_builtins` is called once by the composition root, after every service exists and
before project hooks load. Hooks run in the task that fires them (ARCHITECTURE §4.1 execution
rule): the builtins attached to lifecycle points inside a run's own task record, verify or
request, and never stop that run or repeat a checkpoint its caller took. Only
``builtin.pause_all_runs`` and ``builtin.cancel_cleanup`` stop runs; their hook names are fired
from the command-consumer task. Hooks never write ledger events (WBS §3.5).
"""

import logging
from typing import Final

from pydantic import ConfigDict, Field, SkipValidation

from walk.agents.models import Handover
from walk.budgets.models import BudgetHardAction
from walk.common.errors import ConfigError, WalkError
from walk.common.models import JsonDict, WalkModel
from walk.common.roles import AgentRole
from walk.hooks.errors import HookFailed
from walk.hooks.models import Hook, HookCallable, HookContext, HookFailPolicy, HookName
from walk.hooks.protocols import HookManager
from walk.integrations.protocols import GitProvider
from walk.memory.errors import DocumentNotFound
from walk.memory.protocols import MemoryManager
from walk.permissions.models import Approver
from walk.permissions.protocols import PermissionManager
from walk.runtime.models import AgentRun, CheckpointKind
from walk.runtime.protocols import AgentExecutor, CheckpointManager
from walk.runtime.repository import AgentRunRepository
from walk.runtime.sandbox import branch_name_for
from walk.telemetry.protocols import TelemetryManager
from walk.workflow.models import WorkItemState
from walk.workflow.protocols import WorkflowManager

_LOG = logging.getLogger(__name__)

_MUST_PRIORITY: Final = 10
_DEFAULT_PRIORITY: Final = 60
_REMAINING_WORK: Final = "Remaining Work"
_NO_REMAINING_WORK: Final = "- none"
_REMAINING_COUNTER: Final = "remaining_work_nonempty"
_ESCALATION: Final = "ESCALATION"
_NATIVE: Final = "native"
_HANDOVER: Final = "handover"


class BuiltinHookDeps(WalkModel):
    """Protocol-typed service handles the builtin hooks call (ADR-0016 D-2).

    Only the composition root (and tests) construct it; stories add fields additively.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    hooks: SkipValidation[HookManager] = Field(
        description="Fires the nested ON_MODEL_FALLBACK → ON_AGENT_HANDOFF chain."
    )
    checkpoints: SkipValidation[CheckpointManager] = Field(
        description="END and HANDOFF checkpoints when the caller took none."
    )
    memory: SkipValidation[MemoryManager] = Field(
        description="Remaining-work check, handover lookup, index rebuild."
    )
    git: SkipValidation[GitProvider] = Field(description="Creates the work branch.")
    executor: SkipValidation[AgentExecutor] = Field(
        description="Pauses and cancels runs (command-consumer task only)."
    )
    permissions: SkipValidation[PermissionManager] = Field(
        description="Budget escalation approval requests."
    )
    telemetry: SkipValidation[TelemetryManager] = Field(
        description="Counter remaining_work_nonempty."
    )
    workflow: SkipValidation[WorkflowManager] = Field(
        description="Reads the work item of ON_TASK_START (its branch) and its workflow state."
    )
    runs: SkipValidation[AgentRunRepository] = Field(
        description="Loads the run an END/HANDOFF checkpoint is taken for."
    )
    default_branch: str = Field(description="Project.default_branch, base of ensure_branch.")


def _payload(ctx: HookContext, key: str) -> object:
    """``ctx.payload[key]``; a missing key fails the (fail-closed) hook naming the key."""
    if key not in ctx.payload:
        msg = f"payload key {key!r} missing for {ctx.name.value}"
        raise HookFailed(msg, detail={"hook_name": ctx.name.value, "key": key})
    return ctx.payload[key]


def _required(value: str | None, key: str, ctx: HookContext) -> str:
    """A context field the hook needs; None fails the hook naming the field."""
    if value is None:
        msg = f"{key} missing for {ctx.name.value}"
        raise HookFailed(msg, detail={"hook_name": ctx.name.value, "key": key})
    return value


class _Builtins:
    """The builtin callables, bound to their dependencies."""

    def __init__(self, deps: BuiltinHookDeps) -> None:
        self._d = deps

    async def pause_all_runs(self, ctx: HookContext) -> None:
        del ctx
        failed: list[str] = []
        for run in self._d.executor.running():
            try:
                await self._d.executor.pause(run.id)
            except Exception as exc:  # noqa: BLE001 - every run is tried; failures are reported
                _LOG.warning("run could not be paused", extra={"run_id": run.id, "error": str(exc)})
                failed.append(run.id)
        if failed:
            msg = f"runs not paused: {', '.join(failed)}"
            raise HookFailed(msg, detail={"run_ids": failed})

    async def ensure_branch(self, ctx: HookContext) -> None:
        item = await self._d.workflow.get(_required(ctx.work_item_id, "work_item_id", ctx))
        await self._d.git.ensure_branch(
            branch_name_for(item),
            base=self._d.default_branch,
            idempotency_key=f"git.branch:{item.id}",  # the key SandboxManager.create uses
        )

    async def remaining_work_check(self, ctx: HookContext) -> None:
        if ctx.work_item_id is None:
            return
        try:
            doc = await self._d.memory.read(ctx.work_item_id)
        except DocumentNotFound:
            return
        except WalkError as exc:  # never fails: the §6.5 guard decides, not this check
            _LOG.warning(
                "remaining work not checked",
                extra={"work_item_id": ctx.work_item_id, "error": exc.message},
            )
            return
        remaining = doc.sections.get(_REMAINING_WORK, "").strip()
        if remaining and remaining.lower() != _NO_REMAINING_WORK:
            self._d.telemetry.counter(_REMAINING_COUNTER, work_item=ctx.work_item_id)
            _LOG.warning("work completed with remaining work", extra={"doc_id": ctx.work_item_id})

    async def wip_commit(self, ctx: HookContext) -> None:
        if _payload(ctx, "wip_commit_done") is not True:
            msg = f"checkpoint {ctx.payload.get('checkpoint_id')} made no WIP commit"
            raise HookFailed(msg, detail={"checkpoint_id": ctx.payload.get("checkpoint_id")})

    async def final_checkpoint(self, ctx: HookContext) -> None:
        if "checkpoint_id" in ctx.payload:
            return  # the executor already took the END checkpoint
        run = await self._run(ctx)
        await self._d.checkpoints.checkpoint(
            run, CheckpointKind.END, workflow_state=await self._state(run)
        )

    async def handoff_checkpoint_and_handover(self, ctx: HookContext) -> None:
        if "checkpoint_id" in ctx.payload and "handover_id" in ctx.payload:
            return  # the caller checkpointed and wrote the handover
        handover = Handover.model_validate(_payload(ctx, "handover"))
        run = await self._run(ctx)
        await self._d.checkpoints.checkpoint(
            run, CheckpointKind.HANDOFF, handover=handover, workflow_state=await self._state(run)
        )

    async def fallback_chain(self, ctx: HookContext) -> None:
        handoff = ctx.model_copy(update={"name": HookName.ON_AGENT_HANDOFF})
        await self._d.hooks.fire(HookName.ON_AGENT_HANDOFF, handoff)

    async def budget_escalate(self, ctx: HookContext) -> None:
        if _payload(ctx, "hard_action") != BudgetHardAction.BLOCK.value:
            return  # DOWNGRADE_EFFORT / FALLBACK_MODEL: the executor and router act
        budget_id = _payload(ctx, "budget_id")
        for pending in await self._d.permissions.pending(Approver.USER):
            if pending.kind == _ESCALATION and pending.payload.get("budget_id") == budget_id:
                return
        request: JsonDict = dict(ctx.payload)
        await self._d.permissions.request_approval(
            request,
            kind=_ESCALATION,
            approver=Approver.USER,
            requested_by=AgentRole.KERNEL,
            run_id=ctx.run_id,
            work_item_id=ctx.work_item_id,
        )

    async def approval_recorded(self, ctx: HookContext) -> None:
        _payload(ctx, "approval_id")
        _payload(ctx, "kind")

    async def cancel_cleanup(self, ctx: HookContext) -> None:
        run_id = ctx.run_id
        if run_id is None or run_id not in {run.id for run in self._d.executor.running()}:
            return
        await self._d.executor.cancel(run_id, str(_payload(ctx, "reason")))

    async def load_handover(self, ctx: HookContext) -> None:
        mode = _payload(ctx, "mode")
        if mode == _NATIVE:
            return
        if mode != _HANDOVER:
            msg = f"unknown recovery mode {mode!r}"
            raise HookFailed(msg, detail={"mode": str(mode)})
        handover_id = ctx.payload.get("handover_id")
        if not isinstance(handover_id, str):
            msg = "payload key 'handover_id' missing for a handover resume"
            raise HookFailed(msg, detail={"key": "handover_id"})
        await self._d.memory.read_handover(handover_id)

    async def memory_index(self, ctx: HookContext) -> None:
        del ctx
        await self._d.memory.rebuild_index()

    async def _run(self, ctx: HookContext) -> AgentRun:
        run_id = _required(ctx.run_id, "run_id", ctx)
        run = await self._d.runs.get(run_id)
        if run is None:
            msg = f"unknown run {run_id}"
            raise HookFailed(msg, detail={"run_id": run_id})
        return run

    async def _state(self, run: AgentRun) -> WorkItemState:
        return (await self._d.workflow.get(run.work_item_id)).state


_MUST: Final[tuple[tuple[HookName, str, str], ...]] = (
    (HookName.ON_PROJECT_PAUSE, "builtin.pause_all_runs", "pause_all_runs"),
    (HookName.ON_TASK_START, "builtin.ensure_branch", "ensure_branch"),
    (HookName.ON_TASK_COMPLETE, "builtin.remaining_work_check", "remaining_work_check"),
    (HookName.ON_AGENT_CHECKPOINT, "builtin.wip_commit", "wip_commit"),
    (HookName.ON_AGENT_END, "builtin.final_checkpoint", "final_checkpoint"),
    (
        HookName.ON_AGENT_HANDOFF,
        "builtin.handoff_checkpoint_and_handover",
        "handoff_checkpoint_and_handover",
    ),
    (HookName.ON_MODEL_FALLBACK, "builtin.fallback_chain", "fallback_chain"),
    (HookName.ON_BUDGET_EXHAUSTED, "builtin.budget_escalate", "budget_escalate"),
    (HookName.ON_PROTECTED_ACTION_REQUESTED, "builtin.approval_recorded", "approval_recorded"),
    (HookName.ON_TASK_CANCELLED, "builtin.cancel_cleanup", "cancel_cleanup"),
    (HookName.ON_RECOVERY_RESUME, "builtin.load_handover", "load_handover"),
)
"""ARCHITECTURE §4.1 MUST attachments registered by E02-S08: (hook, id, callable)."""

_DEFAULTS: Final[tuple[tuple[HookName, str, str], ...]] = (
    (HookName.ON_PROJECT_START, "builtin.memory_index", "memory_index"),
)
"""Default attachments (project may disable): (hook, id, callable)."""

MUST_HOOK_IDS: tuple[str, ...] = tuple(hook_id for _, hook_id, _ in _MUST)
"""Ids of the registered MUST hooks, in ARCHITECTURE §4.1 table order."""


def builtin_hooks(deps: BuiltinHookDeps) -> list[tuple[Hook, HookCallable]]:
    """Every builtin hook with its callable: the MUST hooks, then the default attachments."""
    bound = _Builtins(deps)
    pairs: list[tuple[Hook, HookCallable]] = []
    for name, hook_id, method in _MUST:
        hook = Hook(
            name=name,
            id=hook_id,
            kind="builtin",
            priority=_MUST_PRIORITY,
            fail_policy=HookFailPolicy.FAIL_CLOSED,
            required=True,
        )
        pairs.append((hook, getattr(bound, method)))
    for name, hook_id, method in _DEFAULTS:
        hook = Hook(
            name=name,
            id=hook_id,
            kind="builtin",
            priority=_DEFAULT_PRIORITY,
            fail_policy=HookFailPolicy.LOG_AND_CONTINUE,
            required=False,
        )
        pairs.append((hook, getattr(bound, method)))
    return pairs


def register_builtins(manager: HookManager, deps: BuiltinHookDeps) -> None:
    """Register `builtin_hooks` on ``manager`` (once per manager; ADR-0016 D-3).

    Raises:
        ConfigError: The builtins are already registered on ``manager``.
    """
    pairs = builtin_hooks(deps)
    for hook, _ in pairs:
        if any(existing.id == hook.id for existing in manager.hooks_for(hook.name)):
            msg = "builtin hooks already registered"
            raise ConfigError(msg, detail={"hook_id": hook.id})
    for hook, fn in pairs:
        manager.register(hook, fn)
