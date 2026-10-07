"""`DefaultOrchestrator`: startup recovery, the tick loop with wake-ups, the status snapshot.

ARCHITECTURE §3.4 steps 5-6 (E01-S29), plus the injected step-3 checks (E02-S07); steps 1-2
belong to the daemon (E01-S30) and E02;
step 4 (builtin hooks) is done by the composition root before `start` (ADR-0016). Methods whose
behaviour belongs to a later story raise ``ConfigError("implemented in <ID>")``.
"""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Final, NoReturn

from walk.agents.models import RuntimePolicy
from walk.agents.policy_file import update_model_policy
from walk.common.clock import Clock
from walk.common.errors import ConfigError, GuardRejected
from walk.common.ids import ModelId, PhaseId, ProjectKey, RunId, WorkItemId
from walk.common.models import JsonDict
from walk.common.roles import AgentRole
from walk.decisions.models import AutonomyLevel, Escalation
from walk.hooks.models import HookContext, HookName
from walk.hooks.protocols import HookManager
from walk.orchestrator.models import KernelStatus, PhaseEvidencePackage
from walk.orchestrator.scheduler import Scheduler
from walk.orchestrator.status import StatusBuilder
from walk.persistence.uow import UnitOfWork
from walk.runtime.executor import DefaultAgentExecutor
from walk.runtime.recovery import RecoveryManager
from walk.telemetry.models import LedgerEvent, LedgerEventKind
from walk.telemetry.protocols import LedgerManager
from walk.workflow.errors import UnknownTransition
from walk.workflow.models import (
    Feature,
    GddRef,
    Phase,
    PhaseDecision,
    Priority,
    Project,
    TransitionContext,
    TransitionSource,
    WorkItem,
)
from walk.workflow.protocols import WorkflowManager
from walk.workflow.repository import ProjectRepository, WorkflowRepository

_LOG = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL_S = 5.0  # ADR-0009 D-4 timer wake-up

_NOT_BUILT: Final = "status not built yet; call start() or run_once() first"
_NOT_WIRED: Final = "the override dependencies are not wired (composition root, E02-S13)"
_CANCEL: Final = "cancel"


def _deferred(method: str, story: str) -> NoReturn:
    msg = f"Orchestrator.{method} is implemented in {story}"
    raise ConfigError(msg, detail={"method": method, "story": story})


class DefaultOrchestrator:
    """`Orchestrator` for E01: recovery, scheduling loop, snapshot; later stories add the rest."""

    def __init__(  # noqa: PLR0917 - positional parameters fixed by the E01-S29 contract
        self,
        scheduler: Scheduler,
        executor: DefaultAgentExecutor,
        recovery: RecoveryManager,
        status_builder: StatusBuilder,
        hooks: HookManager,
        ledger: LedgerManager,
        clock: Clock,
        *,
        project_key: ProjectKey,
        kernel_instance: str,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        startup_checks: Callable[[], Awaitable[None]] | None = None,
        expire_approvals: Callable[[], Awaitable[object]] | None = None,
        projects: ProjectRepository | None = None,
        workflow: WorkflowManager | None = None,
        policies_path: Path | None = None,
        model_known: Callable[[ModelId], bool] | None = None,
        on_policy_changed: Callable[[], None] | None = None,
    ) -> None:
        """Wire the orchestrator.

        Args:
            scheduler: One admission pass per tick.
            executor: Running runs (stop, drain, wait).
            recovery: Startup recovery of orphaned runs.
            status_builder: Builds the `KernelStatus` snapshot.
            hooks: Fires ``ON_PROJECT_START``.
            ledger: Write point for ``PROJECT_STARTED``.
            clock: Stamps the event and the hook context.
            project_key: Project of the kernel.
            kernel_instance: This kernel process.
            poll_interval_s: Seconds between ticks without a wake-up.
            startup_checks: ARCHITECTURE §3.4 step 3 checks (kernel version pins, E02-S04;
                skill drift, E02-S07; approved artifact hashes, E02-S12, which only report
                drift), awaited before recovery; an exception (e.g.
                `VersionPinError`) aborts startup before ``PROJECT_STARTED`` and
                ``ON_PROJECT_START``.
            expire_approvals: Awaited at the start of every tick: expires approval requests
                past their ``expires_at`` (``DefaultPermissionManager.expire_due``, E02-S11).
            projects: The project row (paused flag, autonomy level) of the §93 overrides.
            workflow: Raises ``cancel`` and changes priorities (§93 overrides).
            policies_path: The project's `.ai/agents/policies.yaml` (`set_model_policy`).
            model_known: Whether a model id or family is configured and enabled.
            on_policy_changed: Called after `set_model_policy` (drops cached policies, so
                the role's next scheduled run uses the new one).
        """
        self._scheduler = scheduler
        self._executor = executor
        self._recovery = recovery
        self._status_builder = status_builder
        self._hooks = hooks
        self._ledger = ledger
        self._clock = clock
        self._project_key = project_key
        self._kernel_instance = kernel_instance
        self._poll_interval_s = poll_interval_s
        self._startup_checks = startup_checks
        self._expire_approvals = expire_approvals
        self._projects = projects
        self._workflow = workflow
        self._policies_path = policies_path
        self._model_known = model_known
        self._on_policy_changed = on_policy_changed
        self._wake = asyncio.Event()
        self._stopping = False
        self._loop_exited: asyncio.Event | None = None
        self._status: KernelStatus | None = None

    async def start(self) -> None:
        """Recover, write ``PROJECT_STARTED``, fire ``ON_PROJECT_START``, then tick until `stop`.

        A tick runs every ``poll_interval_s`` seconds or as soon as `wake` is called. An
        orchestrator runs once: after `stop` (also one requested before `start` began) no tick
        runs any more.
        """
        self._loop_exited = asyncio.Event()
        try:
            await self._startup()
            while not self._stopping:
                await self.tick()
                self._status = await self._status_builder.build()
                with contextlib.suppress(TimeoutError):  # a timeout is the timer wake-up
                    await asyncio.wait_for(self._wake.wait(), self._poll_interval_s)
                self._wake.clear()
        finally:
            self._loop_exited.set()

    async def stop(self, *, drain: bool = True) -> None:
        """End the loop. ``drain=True`` pauses every running run (PAUSE checkpoint).

        ``drain=False`` abandons them without a checkpoint; they stay RUNNING and the next
        kernel instance's recovery resumes them. A running loop first finishes its current
        tick, so no run it starts escapes the drain. Never call it from the loop's own task.
        """
        self._stopping = True
        self._wake.set()
        if self._loop_exited is not None:
            await self._loop_exited.wait()
        if drain:
            for run in self._executor.running():
                await self._executor.pause(run.id)
        else:
            await self._executor.shutdown()

    async def wake(self) -> None:
        """Make the loop tick now."""
        self._wake.set()

    async def tick(self) -> int:
        """Expire due approvals, then one scheduling pass; the number of runs started."""
        if self._expire_approvals is not None:
            await self._expire_approvals()
        return await self._scheduler.tick()

    async def run_once(self, *, wait_runs: bool = True) -> int:
        """Startup steps, one tick, optionally wait for every run (continuations too), stop.

        Returns the number of runs the tick started.
        """
        await self._startup()
        started = await self.tick()
        if wait_runs:
            while running := self._executor.running():
                for run in running:
                    await self._executor.wait(run.id)
        await self.stop(drain=False)
        self._status = await self._status_builder.build()
        return started

    def status(self) -> KernelStatus:
        """The latest snapshot (refreshed after every tick).

        Raises:
            ConfigError: Neither `start` nor `run_once` has run yet.
        """
        if self._status is None:
            raise ConfigError(_NOT_BUILT, detail={"project_key": self._project_key})
        return self._status

    async def submit_feature(self, title: str, description: str, gdd_refs: list[GddRef]) -> Feature:
        """Deferred to E03-S09.

        Raises:
            ConfigError: Always.
        """
        del title, description, gdd_refs
        _deferred("submit_feature", "E03-S09")

    async def plan_phase(self, phase_id: PhaseId) -> list[WorkItem]:
        """Deferred to E06-S04.

        Raises:
            ConfigError: Always.
        """
        del phase_id
        _deferred("plan_phase", "E06-S04")

    async def start_phase(self, phase_id: PhaseId) -> Phase:
        """Deferred to E07-S02.

        Raises:
            ConfigError: Always.
        """
        del phase_id
        _deferred("start_phase", "E07-S02")

    async def request_phase_review(self, phase_id: PhaseId) -> PhaseEvidencePackage:
        """Deferred to E07-S04.

        Raises:
            ConfigError: Always.
        """
        del phase_id
        _deferred("request_phase_review", "E07-S04")

    async def decide_phase(
        self, phase_id: PhaseId, decision: PhaseDecision, feedback: str | None, actor: str
    ) -> Phase:
        """Deferred to E07-S05.

        Raises:
            ConfigError: Always.
        """
        del phase_id, decision, feedback, actor
        _deferred("decide_phase", "E07-S05")

    async def handle_escalation(self, escalation: Escalation) -> None:
        """Deferred to E05-S02.

        Raises:
            ConfigError: Always.
        """
        del escalation
        _deferred("handle_escalation", "E05-S02")

    async def pause(self, run_id: RunId | None = None) -> None:
        """§93 Pause Project (``run_id`` None) or Pause Agent; ``USER_OVERRIDE`` either way.

        The project: ``paused`` is set (the scheduler admits nothing), then ``ON_PROJECT_PAUSE``
        fires from this (command-consumer) task, whose builtin pauses every running run through
        the executor (one PAUSE checkpoint each, PAUSED_BY_USER). One run: the executor pauses
        it.

        Raises:
            RunNotFound: Unknown ``run_id``.
            ConfigError: The run is not executing here, or the overrides are not wired.
            HookFailed: A run could not be paused (the project stays paused).
        """
        if run_id is not None:
            await self._executor.pause(run_id)
            await self._override("pause", {"run_id": run_id}, run_id=run_id)
            return
        await self._set_paused(paused=True)
        await self._override("pause", {"run_id": None})
        await self._fire_project(HookName.ON_PROJECT_PAUSE)

    async def resume(self, run_id: RunId | None = None) -> None:
        """§93 Resume Project (``run_id`` None) or Resume Agent; ``USER_OVERRIDE`` either way.

        The project: ``paused`` is cleared, ``ON_PROJECT_RESUME`` fires and every PAUSED_BY_USER
        run of this kernel instance continues (`DefaultAgentExecutor.resume`: natively, else
        from a handover); one run that cannot continue is logged and the others still resume.
        One run: the executor resumes it.

        Raises:
            RunNotFound: Unknown ``run_id``.
            ConfigError: The run is not paused, or the overrides are not wired.
        """
        if run_id is not None:
            await self._executor.resume(run_id)
            await self._override("resume", {"run_id": run_id}, run_id=run_id)
            return
        await self._set_paused(paused=False)
        await self._override("resume", {"run_id": None})
        await self._fire_project(HookName.ON_PROJECT_RESUME)
        for run in await self._executor.paused_runs():
            try:
                await self._executor.resume(run.id)
            except Exception:  # noqa: BLE001 - one run must not stop the others from resuming
                _LOG.exception("paused run could not resume", extra={"run_id": run.id})
        await self.wake()

    async def cancel_work_item(self, work_item_id: WorkItemId, reason: str) -> None:
        """§93 Cancel Task: raise ``cancel`` as USER; ``USER_OVERRIDE``.

        The transition's ``ON_TASK_CANCELLED`` fires from this task with ``run_id`` = the
        item's running run (or None) and ``reason`` in its payload; the builtin cancels that
        run (CANCELLED, worktree removed, branch kept).

        Raises:
            GuardRejected: The item cannot be cancelled (COMPLETE, CANCELLED, guards).
            WorkItemNotFound: Unknown item.
            ConfigError: The overrides are not wired.
        """
        workflow = self._wired(self._workflow)
        item = await workflow.get(work_item_id)
        running = {run.id for run in self._executor.running()}
        run_id = item.assigned_run_id if item.assigned_run_id in running else None
        context = TransitionContext(
            actor_role=AgentRole.USER,
            source=TransitionSource.USER,
            run_id=run_id,
            payload={"reason": reason},
            phase=None,
        )
        try:
            await workflow.raise_event(work_item_id, _CANCEL, context)
        except UnknownTransition as exc:
            msg = f"work item {work_item_id} cannot be cancelled in state {item.state.value}"
            raise GuardRejected(msg, detail={"work_item_id": work_item_id}) from exc
        args: JsonDict = {"work_item_id": work_item_id, "reason": reason}
        await self._override("work.cancel", args, work_item_id=work_item_id)

    async def set_priority(
        self, work_item_id: WorkItemId, priority: Priority, *, actor: str
    ) -> WorkItem:
        """§93 Change Priority; the next tick orders ready items by it; ``USER_OVERRIDE``.

        Raises:
            WorkItemNotFound: Unknown item.
            ConfigError: The overrides are not wired.
        """
        workflow = self._wired(self._workflow)
        await workflow.get(work_item_id)  # WorkItemNotFound before anything is written
        items = WorkflowRepository(self._wired(self._projects).db)
        async with UnitOfWork(items.db) as uow:
            updated = await items.set_priority(work_item_id, priority, uow)
        args: JsonDict = {"work_item_id": work_item_id, "priority": priority.value, "actor": actor}
        await self._override("work.priority", args, work_item_id=work_item_id)
        await self.wake()
        return updated

    async def set_autonomy(self, level: AutonomyLevel, *, actor: str) -> Project:
        """§93 Change Autonomy Level: ``Project.autonomy_level_max``; ``USER_OVERRIDE``.

        Raises:
            ConfigError: The overrides are not wired.
        """
        projects = self._wired(self._projects)
        async with UnitOfWork(projects.db) as uow:
            project = await projects.set_autonomy_level_max(self._project_key, int(level), uow)
        await self._override("policy.set_autonomy", {"level": int(level), "actor": actor})
        return project

    async def set_model_policy(
        self, role: AgentRole, preferred: list[ModelId], fallback: list[ModelId]
    ) -> RuntimePolicy:
        """§93 Change Model Policy of one role in `.ai/agents/policies.yaml`; ``USER_OVERRIDE``.

        Applies from the role's next scheduled run (ADR-0011 D-6).

        Raises:
            ConfigError: An unknown or disabled model, no preferred model, or the overrides
                are not wired.
            ConstitutionError: The resulting policy is invalid (the file is left unchanged).
        """
        known = self._wired(self._model_known)
        path = self._wired(self._policies_path)
        unknown = [model for model in [*preferred, *fallback] if not known(model)]
        if unknown or not preferred:
            msg = f"unknown or disabled model(s): {unknown}" if unknown else "no preferred model"
            raise ConfigError(msg, detail={"models": unknown, "role": role.value})
        policy = update_model_policy(path, role, preferred, fallback)
        if self._on_policy_changed is not None:
            self._on_policy_changed()
        args: JsonDict = {"role": role.value, "preferred": preferred, "fallback": fallback}
        await self._override("policy.set_model", args)
        return policy

    async def force_review(self, work_item_id: WorkItemId) -> None:
        """Deferred to E03-S16.

        Raises:
            ConfigError: Always.
        """
        del work_item_id
        _deferred("force_review", "E03-S16")

    async def _set_paused(self, *, paused: bool) -> None:
        projects = self._wired(self._projects)
        async with UnitOfWork(projects.db) as uow:
            await projects.set_paused(self._project_key, paused, uow)

    async def _override(
        self,
        command: str,
        args: JsonDict,
        *,
        run_id: RunId | None = None,
        work_item_id: WorkItemId | None = None,
    ) -> None:
        """``USER_OVERRIDE`` ``{command, args}`` (ARCHITECTURE §4.3 orchestrator write point)."""
        await self._ledger.append(
            LedgerEvent(
                kind=LedgerEventKind.USER_OVERRIDE,
                at=self._clock.now(),
                project_key=self._project_key,
                actor_role=AgentRole.USER,
                run_id=run_id,
                work_item_id=work_item_id,
                outcome="OK",
                payload={"command": command, "args": args},
            )
        )

    async def _fire_project(self, name: HookName) -> None:
        context = HookContext(name=name, at=self._clock.now(), project_key=self._project_key)
        await self._hooks.fire(name, context)

    @staticmethod
    def _wired[T](dependency: T | None) -> T:
        if dependency is None:
            raise ConfigError(_NOT_WIRED, detail={})
        return dependency

    async def _startup(self) -> None:
        """ARCHITECTURE §3.4 steps 3, 5-6: checks, recovery, ``PROJECT_STARTED``, hook."""
        if self._startup_checks is not None:
            await self._startup_checks()
        report = await self._recovery.recover()
        payload: dict[str, object] = {
            "kernel_instance": self._kernel_instance,
            "interrupted": len(report.interrupted),
            "resumed_native": len(report.resumed_native),
            "restarted_with_handover": len(report.restarted_with_handover),
            "requeued": len(report.requeued),
            "failed": len(report.failed),
        }
        now = self._clock.now()
        await self._ledger.append(
            LedgerEvent(
                kind=LedgerEventKind.PROJECT_STARTED,
                at=now,
                project_key=self._project_key,
                actor_role=AgentRole.KERNEL,
                outcome="OK",
                payload=payload,
            )
        )
        context = HookContext(
            name=HookName.ON_PROJECT_START,
            at=now,
            project_key=self._project_key,
            payload=payload,
        )
        await self._hooks.fire(HookName.ON_PROJECT_START, context)
        self._status = await self._status_builder.build()
