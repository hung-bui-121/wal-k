"""`Scheduler`: one admission pass over ready work (INTERFACES §5.1; E01-S29).

A tick admits ready STORY/TASK implementation work while the executor has room: route, role
parallelism, idempotency key, budgets, effort, model selection, instantiation, the admission
transition (guards decide), the open handover, and the executor start. One item's failure
never aborts the tick.
"""

import logging
from collections.abc import Callable
from typing import Final

from walk.agents.models import RuntimePolicy
from walk.agents.protocols import AgentManager
from walk.budgets.models import BudgetScope, BudgetSubject
from walk.budgets.protocols import BudgetManager
from walk.common.clock import Clock
from walk.common.errors import ConfigError, GuardRejected
from walk.common.ids import ProjectKey
from walk.common.roles import AgentRole
from walk.effort.protocols import EffortManager
from walk.model_router.errors import BlockedProvider
from walk.model_router.protocols import ModelRouter
from walk.orchestrator.models import RouteDecision
from walk.orchestrator.protocols import TaskRouter
from walk.persistence.database import Database
from walk.persistence.idempotency import IdempotencyStore
from walk.persistence.uow import UnitOfWork
from walk.runtime.checkpoints import DefaultCheckpointManager
from walk.runtime.executor import DefaultAgentExecutor
from walk.runtime.models import AgentRun
from walk.runtime.sandbox import branch_name_for
from walk.telemetry.protocols import TelemetryManager
from walk.workflow.models import (
    TransitionContext,
    TransitionSource,
    WorkItem,
    WorkItemKind,
    WorkItemState,
)
from walk.workflow.protocols import WorkflowManager
from walk.workflow.repository import ProjectRepository

_LOG = logging.getLogger(__name__)

DEFAULT_MAX_PARALLEL_AGENTS = 2  # ARCHITECTURE §3.2 [MVP]
ADMISSION_EVENTS: dict[tuple[WorkItemKind, WorkItemState], str] = {
    (WorkItemKind.STORY, WorkItemState.READY): "start_implementation",
    (WorkItemKind.STORY, WorkItemState.REWORK): "start_implementation",
    (WorkItemKind.TASK, WorkItemState.READY): "start_implementation",
    (WorkItemKind.TASK, WorkItemState.REWORK): "start_implementation",
}
"""Admission transition per schedulable (kind, state); E03 adds REVIEW/QC/TRIAGE/PLAN/DESIGN."""

_SCHEDULE_OPERATION: Final = "schedule"
_NOT_ADMITTED: Final = "scheduler.not_admitted"
_ROLE_BUSY: Final = "scheduler.role_busy"
_NOT_PARALLEL: Final = "scheduler.not_parallel"
_BLOCKED_PROVIDER: Final = "scheduler.blocked_provider"
_INSTANTIATE_FAILED: Final = "scheduler.instantiate_failed"
_ADMISSION_REJECTED: Final = "scheduler.admission_rejected"
_START_FAILED: Final = "scheduler.start_failed"


class Scheduler:
    """INTERFACES §5.1 tick for the MVP admission set (`ADMISSION_EVENTS`)."""

    def __init__(  # noqa: PLR0917 - parameters fixed by the E01-S29 contract
        self,
        db: Database,
        projects: ProjectRepository,
        workflow: WorkflowManager,
        router: TaskRouter,
        agents: AgentManager,
        effort: EffortManager,
        budgets: BudgetManager,
        models: ModelRouter,
        executor: DefaultAgentExecutor,
        checkpoints: DefaultCheckpointManager,
        idempotency: IdempotencyStore,
        telemetry: TelemetryManager,
        clock: Clock,
        *,
        project_key: ProjectKey,
        max_parallel_agents: int = DEFAULT_MAX_PARALLEL_AGENTS,
        ready_env_keys: Callable[[], set[str]] = set,
    ) -> None:
        """Wire the scheduler.

        Args:
            db: Database of the ``schedule:`` idempotency keys.
            projects: The project row (pause flag, current phase).
            workflow: Ready items and the admission transition.
            router: Role and purpose of each item.
            agents: Runtime policies and agent instances.
            effort: Effort resolution (INTERFACES §5.2).
            budgets: TASK/ROLE budget rows and headroom.
            models: Model selection.
            executor: Starts runs; its running set bounds parallelism.
            checkpoints: Open handovers of an item.
            idempotency: ``schedule:<item>:<state>:<state_version>`` keys.
            telemetry: ``scheduler.*`` counters.
            clock: Kernel clock.
            project_key: Project of the kernel.
            max_parallel_agents: Runs executing at once.
            ready_env_keys: Environment keys available to tools.
        """
        self._db = db
        self._projects = projects
        self._workflow = workflow
        self._router = router
        self._agents = agents
        self._effort = effort
        self._budgets = budgets
        self._models = models
        self._executor = executor
        self._checkpoints = checkpoints
        self._idempotency = idempotency
        self._telemetry = telemetry
        self._clock = clock
        self._project_key = project_key
        self._max_parallel_agents = max_parallel_agents
        self._ready_env_keys = ready_env_keys

    async def tick(self) -> int:
        """Admit ready work while the executor has room; return the runs started.

        Raises:
            ConfigError: The project row is missing.
        """
        project = await self._projects.get(self._project_key)
        if project is None:
            msg = f"project {self._project_key} not found"
            raise ConfigError(msg, detail={"project_key": self._project_key})
        if project.paused:
            return 0
        started = 0
        for item in await self._workflow.ready_items(project.current_phase_id):
            if len(self._executor.running()) >= self._max_parallel_agents:
                break
            if (item.kind, item.state) not in ADMISSION_EVENTS:
                self._telemetry.counter(_NOT_ADMITTED, kind=item.kind.value, state=item.state.value)
                continue
            try:
                started += await self._admit(item)
            except Exception:  # noqa: BLE001 - one item's failure never aborts the tick
                _LOG.exception("scheduling failed", extra={"work_item_id": item.id})
                self._telemetry.counter(_START_FAILED)
        return started

    async def _admit(self, item: WorkItem) -> int:
        route = self._router.route(item, item.state)
        policy = self._agents.load_runtime_policy(route.role)
        running = self._executor.running()
        if not await self._has_room(item, route, policy, running):
            return 0
        key = f"schedule:{item.id}:{item.state.value}:{item.state_version}"
        if await self._idempotency.has(key):
            return 0
        await self._budgets.ensure(BudgetScope.TASK, item.id, policy.budget_policy, None)
        await self._budgets.ensure(BudgetScope.ROLE, route.role.value, policy.budget_policy, None)
        subject = BudgetSubject(
            project_key=self._project_key,
            phase_id=item.phase_id,
            role=route.role,
            work_item_id=item.id,
        )
        headroom = await self._budgets.headroom(subject)
        resolution = self._effort.resolve(policy.effort_policy, item, item.state, 0, headroom)
        try:
            routing = await self._models.select(
                route.role, policy.model_policy, route.profile, resolution.effective
            )
        except BlockedProvider as exc:
            _LOG.warning(
                "no model available; item skipped",
                extra={"work_item_id": item.id, "rejected": exc.detail.get("rejected")},
            )
            self._telemetry.counter(_BLOCKED_PROVIDER)
            return 0
        applicable = await self._budgets.applicable(subject)
        try:
            agent = await self._agents.instantiate(
                route.role,
                item,
                routing.model_id,
                routing.effort,
                [budget.id for budget in applicable],
                self._ready_env_keys(),
            )
        except ConfigError:
            _LOG.warning("agent instantiation failed", extra={"work_item_id": item.id})
            self._telemetry.counter(_INSTANTIATE_FAILED)
            return 0
        payload = {
            "budget_ok": all(value > 0 for value in headroom.values()),
            "branch_available": _branch_available(item, running),
        }
        context = TransitionContext(
            actor_role=AgentRole.KERNEL,
            source=TransitionSource.KERNEL,
            run_id=None,
            payload=payload,
            phase=None,
        )
        try:
            await self._workflow.raise_event(
                item.id, ADMISSION_EVENTS[(item.kind, item.state)], context
            )
        except GuardRejected as exc:
            _LOG.info("admission rejected", extra={"work_item_id": item.id, "reason": exc.message})
            self._telemetry.counter(_ADMISSION_REJECTED)
            return 0
        admitted = await self._workflow.get(item.id)
        handover = await self._checkpoints.latest_open_handover(item.id)
        run = await self._executor.start(
            agent,
            admitted,
            route.purpose,
            handover=handover,
            routing=routing,
            effort_resolution=resolution,
        )
        async with UnitOfWork(self._db) as uow:
            await self._idempotency.put(key, _SCHEDULE_OPERATION, run.id, uow)
        if handover is not None:
            await self._checkpoints.close_handover(handover.id, run.id)
        return 1

    async def _has_room(
        self,
        item: WorkItem,
        route: RouteDecision,
        policy: RuntimePolicy,
        running: list[AgentRun],
    ) -> bool:
        if sum(run.role is route.role for run in running) >= policy.max_parallel_runs:
            self._telemetry.counter(_ROLE_BUSY, role=route.role.value)
            return False
        for run in running:
            other = await self._workflow.get(run.work_item_id)
            if not self._router.can_run_parallel(item, other):
                self._telemetry.counter(_NOT_PARALLEL)
                return False
        return True


def _branch_available(item: WorkItem, running: list[AgentRun]) -> bool:
    """No executing run of another item works on the item's branch."""
    branch = branch_name_for(item)
    return not any(run.branch == branch and run.work_item_id != item.id for run in running)
