"""`DefaultOrchestrator`: startup recovery, the tick loop with wake-ups, the status snapshot.

ARCHITECTURE §3.4 steps 5-6 (E01-S29), plus the injected step-3 checks (E02-S07); steps 1-2
belong to the daemon (E01-S30) and E02;
step 4 (builtin hooks) is done by the composition root before `start` (ADR-0016). Methods whose
behaviour belongs to a later story raise ``ConfigError("implemented in <ID>")``.
"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Final, NoReturn

from walk.common.clock import Clock
from walk.common.errors import ConfigError
from walk.common.ids import PhaseId, ProjectKey, RunId, WorkItemId
from walk.common.roles import AgentRole
from walk.decisions.models import Escalation
from walk.hooks.models import HookContext, HookName
from walk.hooks.protocols import HookManager
from walk.orchestrator.models import KernelStatus, PhaseEvidencePackage
from walk.orchestrator.scheduler import Scheduler
from walk.orchestrator.status import StatusBuilder
from walk.runtime.executor import DefaultAgentExecutor
from walk.runtime.recovery import RecoveryManager
from walk.telemetry.models import LedgerEvent, LedgerEventKind
from walk.telemetry.protocols import LedgerManager
from walk.workflow.models import Feature, GddRef, Phase, PhaseDecision, WorkItem

DEFAULT_POLL_INTERVAL_S = 5.0  # ADR-0009 D-4 timer wake-up

_NOT_BUILT: Final = "status not built yet; call start() or run_once() first"


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
        """Deferred to E02-S13.

        Raises:
            ConfigError: Always.
        """
        del run_id
        _deferred("pause", "E02-S13")

    async def resume(self, run_id: RunId | None = None) -> None:
        """Deferred to E02-S13.

        Raises:
            ConfigError: Always.
        """
        del run_id
        _deferred("resume", "E02-S13")

    async def cancel_work_item(self, work_item_id: WorkItemId, reason: str) -> None:
        """Deferred to E02-S13.

        Raises:
            ConfigError: Always.
        """
        del work_item_id, reason
        _deferred("cancel_work_item", "E02-S13")

    async def force_review(self, work_item_id: WorkItemId) -> None:
        """Deferred to E03-S16.

        Raises:
            ConfigError: Always.
        """
        del work_item_id
        _deferred("force_review", "E03-S16")

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
