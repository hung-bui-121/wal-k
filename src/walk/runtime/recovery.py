"""Startup recovery of runs another kernel instance left behind (ARCHITECTURE §5.3; E01-S28).

Each orphaned run is marked INTERRUPTED and continued from its latest checkpoint: natively when
the model's adapter is healthy and resumes the provider session, otherwise from a handover on a
routed model. Adapters resume only sessions they started themselves (E01-S21/S22), so after a
real restart the handover path is the normal one. `RecoveryManager` writes its ledger events on
behalf of the executor (ARCHITECTURE §4.3).
"""

import logging
from collections.abc import Callable
from typing import Final, Literal

from pydantic import Field

from walk.agents.models import Handover
from walk.agents.protocols import AgentManager
from walk.common.clock import Clock
from walk.common.errors import WalkError
from walk.common.ids import ProjectKey, RunId, WorkItemId
from walk.common.models import FrozenModel, JsonDict
from walk.hooks.errors import HookFailed
from walk.hooks.models import HookContext, HookName
from walk.hooks.protocols import HookManager
from walk.model_router.errors import NotResumable
from walk.model_router.models import FallbackTrigger, TaskProfile
from walk.model_router.protocols import ModelRouter
from walk.persistence.uow import UnitOfWork
from walk.runtime.checkpoints import DefaultCheckpointManager
from walk.runtime.executor import DefaultAgentExecutor
from walk.runtime.models import AgentRun, AgentRunState, Checkpoint, CheckpointKind
from walk.runtime.protocols import SandboxManager
from walk.runtime.repository import AgentRunRepository
from walk.telemetry.models import LedgerEvent, LedgerEventKind
from walk.telemetry.protocols import LedgerManager
from walk.workflow.errors import WorkItemNotFound
from walk.workflow.models import WorkItem
from walk.workflow.repository import WorkflowRepository

_LOG = logging.getLogger(__name__)

_Mode = Literal["native", "handover"]
_NATIVE: Final[_Mode] = "native"
_HANDOVER: Final[_Mode] = "handover"
_RECOVERY: Final = "recovery"


class RecoveryReport(FrozenModel):
    """What one `RecoveryManager.recover` call did."""

    interrupted: list[RunId] = Field(
        default_factory=list, description="Orphaned runs marked INTERRUPTED."
    )
    resumed_native: list[RunId] = Field(
        default_factory=list, description="New runs continuing a provider session."
    )
    restarted_with_handover: list[RunId] = Field(
        default_factory=list, description="New runs started from a handover."
    )
    requeued: list[WorkItemId] = Field(
        default_factory=list, description="Items unassigned because their run had no checkpoint."
    )
    failed: list[tuple[RunId, str]] = Field(
        default_factory=list, description="Runs recovery could not continue, with the reason."
    )


class RecoveryManager:
    """ARCHITECTURE §5.3 steps 1-6 for the runs of dead kernel instances."""

    def __init__(  # noqa: PLR0917 - positional parameters fixed by the E01-S28 contract
        self,
        runs: AgentRunRepository,
        checkpoints: DefaultCheckpointManager,
        executor: DefaultAgentExecutor,
        router: ModelRouter,
        agents: AgentManager,
        items: WorkflowRepository,
        hooks: HookManager,
        ledger: LedgerManager,
        clock: Clock,
        *,
        kernel_instance: str,
        project_key: ProjectKey,
        ready_env_keys: Callable[[], set[str]] = set,
        sandbox: SandboxManager,
    ) -> None:
        """Wire the manager.

        Args:
            runs: ``agent_runs`` (state changes of the interrupted runs).
            checkpoints: Orphan query, latest checkpoint, handovers.
            executor: Starts or natively resumes the continuing runs.
            router: Adapter health and the model of a handover restart.
            agents: Runtime policy and agent instance of the continuing run.
            items: The runs' work items and their assignment.
            hooks: ``ON_MODEL_FALLBACK``, ``ON_RECOVERY_RESUME`` and, for a run whose recovery
                failed, ``ON_TASK_FAILED``.
            ledger: ``ERROR(kind=INTERRUPTED)``, ``MODEL_FALLBACK``, ``RECOVERY_RESUMED`` and
                the interrupted run's ``AGENT_RUN_ENDED``.
            clock: Stamps events.
            kernel_instance: This kernel process; its own runs are never orphans.
            project_key: Project of the events.
            ready_env_keys: Environment keys available to tools.
            sandbox: Re-adds a deleted worktree before a RECOVERY handover is built (§5.3 step 4).
        """
        self._runs = runs
        self._checkpoints = checkpoints
        self._executor = executor
        self._router = router
        self._agents = agents
        self._items = items
        self._hooks = hooks
        self._ledger = ledger
        self._clock = clock
        self._kernel_instance = kernel_instance
        self._project_key = project_key
        self._ready_env_keys = ready_env_keys
        self._sandbox = sandbox

    async def recover(self) -> RecoveryReport:
        """Interrupt and continue every orphaned run; one run's failure never stops the rest.

        A run whose recovery fails ends like every failed run: FAILED, ``AGENT_RUN_ENDED``, item
        unassigned, ``ON_TASK_FAILED``. Idempotent: the continuing runs belong to this kernel
        instance, so a second call finds no orphan.
        """
        report = RecoveryReport()
        for run in await self._checkpoints.interrupted_runs(self._kernel_instance):
            try:
                await self._recover(run, report)
            except Exception as exc:  # noqa: BLE001 - recovery isolates failures per run
                detail = exc.message if isinstance(exc, WalkError) else str(exc)
                _LOG.exception("run recovery failed", extra={"run_id": run.id})
                await self._fail(run.id, f"{_RECOVERY}: {detail}")
                report.failed.append((run.id, detail))
        return report

    async def _fail(self, run_id: RunId, reason: str) -> None:
        """End a run whose recovery raised (Invariant 9: one start, one end).

        A run already HANDED_OVER (its continuation started, then a later step raised) keeps
        that end state and its single ``AGENT_RUN_ENDED``.
        """
        current = await self._runs.get(run_id)
        if current is None or current.state is AgentRunState.HANDED_OVER:
            return
        async with UnitOfWork(self._runs.db) as uow:
            failed = await self._runs.set_state(
                run_id, AgentRunState.FAILED, failure_reason=reason, conn=uow.conn
            )
            item = await self._items.get(failed.work_item_id)
            if item is not None and item.assigned_run_id == failed.id:
                await self._items.set_assigned_run(item.id, None, conn=uow.conn)
            ended: JsonDict = {
                "state": AgentRunState.FAILED.value,
                "failure_reason": reason,
                "mode": _RECOVERY,
            }
            await self._ledger.append(
                self._event(LedgerEventKind.AGENT_RUN_ENDED, failed, "FAILED", ended), uow=uow
            )
        failure: JsonDict = {"state": AgentRunState.FAILED.value, "failure_reason": reason}
        try:
            await self._fire(HookName.ON_TASK_FAILED, failed, failure)
        except HookFailed as exc:
            _LOG.warning(
                "end-of-run hook failed",
                extra={
                    "run_id": failed.id,
                    "hook": HookName.ON_TASK_FAILED.value,
                    "error": exc.message,
                },
            )

    async def _recover(self, run: AgentRun, report: RecoveryReport) -> None:
        interrupted = await self._interrupt(run)
        report.interrupted.append(run.id)
        item = await self._item(run.work_item_id)
        checkpoint = await self._checkpoints.latest(run.id)
        if checkpoint is None:
            async with UnitOfWork(self._runs.db) as uow:
                if item.assigned_run_id == run.id:
                    await self._items.set_assigned_run(item.id, None, conn=uow.conn)
            report.requeued.append(item.id)
            return
        healthy = (await self._router.adapter_for(checkpoint.model_id).health()).ok
        session = checkpoint.provider_session
        if healthy and session is not None and session.resumable:
            try:
                resumed = await self._executor.resume_native(checkpoint)
            except NotResumable as exc:
                _LOG.info(
                    "native resume refused; continuing from a handover",
                    extra={"run_id": run.id, "reason": exc.message},
                )
            else:
                await self._continued(interrupted, resumed, checkpoint, _NATIVE, None)
                report.resumed_native.append(resumed.id)
                return
        restarted, handover = await self._restart(interrupted, item, checkpoint, healthy=healthy)
        await self._continued(interrupted, restarted, checkpoint, _HANDOVER, handover)
        report.restarted_with_handover.append(restarted.id)

    async def _interrupt(self, run: AgentRun) -> AgentRun:
        payload: JsonDict = {
            "kind": "INTERRUPTED",
            "previous_state": run.state.value,
            "previous_kernel_instance": run.kernel_instance,
        }
        async with UnitOfWork(self._runs.db) as uow:
            interrupted = await self._runs.set_state(
                run.id, AgentRunState.INTERRUPTED, conn=uow.conn
            )
            await self._ledger.append(
                self._event(LedgerEventKind.ERROR, interrupted, "FAILED", payload), uow=uow
            )
        return interrupted

    async def _restart(
        self, run: AgentRun, item: WorkItem, checkpoint: Checkpoint, *, healthy: bool
    ) -> tuple[AgentRun, Handover]:
        """ARCHITECTURE §5.3 step 5 else-branch: handover, routing, new run."""
        handover = await self._checkpoints.latest_open_handover(item.id)
        if handover is None:
            # §5.3 step 4: the worktree may be gone (`.walk/` is git-ignored scratch).
            await self._sandbox.adopt(run, run, item)
            handover = await self._checkpoints.build_handover(run, "RECOVERY", None)
            await self._checkpoints.checkpoint(
                run, CheckpointKind.HANDOFF, handover=handover, workflow_state=item.state
            )
        policy = self._agents.load_runtime_policy(run.role)
        agent = await self._agents.instantiate(
            run.role, item, checkpoint.model_id, checkpoint.effort, [], self._ready_env_keys()
        )
        profile = TaskProfile(
            required_capabilities=[],
            required_tools=list(agent.tools),
            required_skills=list(agent.skills),
            estimated_context_tokens=checkpoint.context_manifest.total_tokens_estimate,
            risk=item.risk,
        )
        decision = await self._router.select(
            run.role,
            policy.model_policy,
            profile,
            checkpoint.effort,
            exclude=[] if healthy else [checkpoint.model_id],
        )
        if decision.model_id != checkpoint.model_id:
            payload: JsonDict = {
                "trigger": FallbackTrigger.PROVIDER_OUTAGE.value,
                "from": checkpoint.model_id,
                "to": decision.model_id,
            }
            await self._ledger.append(
                self._event(LedgerEventKind.MODEL_FALLBACK, run, "OK", payload)
            )
            await self._fire(HookName.ON_MODEL_FALLBACK, run, payload)
        successor = agent.model_copy(
            update={"model_id": decision.model_id, "effort": decision.effort}
        )
        restarted = await self._executor.start(
            successor,
            item,
            run.purpose,
            handover=handover,
            parent_run_id=run.id,
            routing=decision,
        )
        return restarted, handover

    async def _continued(
        self,
        run: AgentRun,
        new_run: AgentRun,
        checkpoint: Checkpoint,
        mode: _Mode,
        handover: Handover | None,
    ) -> None:
        """The interrupted run ends HANDED_OVER; RECOVERY_RESUMED and ON_RECOVERY_RESUME."""
        ended: JsonDict = {"state": AgentRunState.HANDED_OVER.value, "mode": mode}
        resumed: JsonDict = {
            "from_run_id": run.id,
            "mode": mode,
            "checkpoint_seq": checkpoint.seq,
            "handover_id": handover.id if handover is not None else None,
        }
        async with UnitOfWork(self._runs.db) as uow:
            handed = await self._runs.set_state(run.id, AgentRunState.HANDED_OVER, conn=uow.conn)
            await self._ledger.append(
                self._event(LedgerEventKind.AGENT_RUN_ENDED, handed, "FAILED", ended), uow=uow
            )
            await self._ledger.append(
                self._event(LedgerEventKind.RECOVERY_RESUMED, new_run, "OK", resumed), uow=uow
            )
        if handover is not None:
            await self._checkpoints.close_handover(handover.id, new_run.id)
        await self._fire(
            HookName.ON_RECOVERY_RESUME,
            new_run,
            {"handover_id": resumed["handover_id"], "mode": mode, "from_run_id": run.id},
        )

    async def _item(self, work_item_id: WorkItemId) -> WorkItem:
        item = await self._items.get(work_item_id)
        if item is None:
            msg = f"work item not found: {work_item_id}"
            raise WorkItemNotFound(msg, detail={"work_item_id": work_item_id})
        return item

    def _event(
        self,
        kind: LedgerEventKind,
        run: AgentRun,
        outcome: Literal["OK", "FAILED"],
        payload: JsonDict,
    ) -> LedgerEvent:
        return LedgerEvent(
            kind=kind,
            at=self._clock.now(),
            project_key=self._project_key,
            actor_role=run.role,
            work_item_id=run.work_item_id,
            run_id=run.id,
            model_id=run.model_id,
            effort=run.effort,
            outcome=outcome,
            payload=payload,
        )

    async def _fire(self, name: HookName, run: AgentRun, payload: JsonDict) -> None:
        context = HookContext(
            name=name,
            at=self._clock.now(),
            project_key=self._project_key,
            work_item_id=run.work_item_id,
            run_id=run.id,
            role=run.role,
            payload=payload,
        )
        await self._hooks.fire(name, context)
