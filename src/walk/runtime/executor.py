"""`DefaultAgentExecutor`: one `AgentRun` end-to-end over the adapter event stream.

ARCHITECTURE §3.2 steps 3-7 (E01-S27): allocation, worktree, `AgentInput` and `RunSession`
assembly, start events, the event loop (tool results, usage metering, periodic and hinted
checkpoints with a boundary audit before every WIP commit), output validation with one repair
turn, the output applier, and the run's end events. E01-S28 adds transient-error retries with
backoff, the fallback side effects of INTERFACES §5.3 (steps 5, 6, 10; the router decides), the
worktree adoption of child runs and the native session resume. The executor is the
``runtime.AgentExecutor`` ledger write point (ARCHITECTURE §4.3). Every state change runs in its
own unit of work; no transaction is held across an await on the adapter stream.
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Final, Literal

from walk.agents.models import AgentInput, AgentInstance, AgentOutput, Handover
from walk.agents.protocols import AgentManager
from walk.budgets.errors import BudgetExhausted
from walk.budgets.models import BudgetDimension, BudgetHardAction, BudgetSubject
from walk.budgets.protocols import BudgetManager, CostManager
from walk.common.clock import Clock
from walk.common.errors import ConfigError, GuardRejected, TransientError, WalkError
from walk.common.ids import IdFactory, ProjectKey, RunId, Sha
from walk.common.models import JsonDict
from walk.debate.models import Debate
from walk.effort.models import EffortResolution
from walk.hooks.errors import HookFailed
from walk.hooks.models import HookContext, HookName
from walk.hooks.protocols import HookManager
from walk.integrations.protocols import GitProvider
from walk.model_router.errors import BlockedProvider, NotResumable
from walk.model_router.models import (
    AgentEvent,
    AgentEventKind,
    FallbackRequest,
    FallbackTrigger,
    ModelDescriptor,
    ProviderSessionRef,
    RoutingDecision,
    RunSession,
    TaskProfile,
)
from walk.model_router.protocols import ModelAdapter, ModelRouter
from walk.permissions.models import Approver, ToolCallRequest
from walk.permissions.protocols import PermissionManager
from walk.persistence.database import Database
from walk.persistence.uow import UnitOfWork
from walk.runtime.boundary import DEFAULT_ALLOWED_PATHS, DEFAULT_FORBIDDEN_PATHS
from walk.runtime.checkpoints import DefaultCheckpointManager
from walk.runtime.errors import RunNotFound
from walk.runtime.inputs import AgentInputBuilder, build_run_session, expected_output_for
from walk.runtime.metering import UsageMeter
from walk.runtime.models import AgentRun, AgentRunState, Checkpoint, CheckpointKind
from walk.runtime.output_applier import DefaultOutputApplier
from walk.runtime.protocols import BoundaryAuditor, SandboxManager
from walk.runtime.repository import AgentRunRepository
from walk.runtime.sandbox import branch_name_for
from walk.runtime.tool_invoker import DefaultToolInvoker
from walk.telemetry.models import LedgerEvent, LedgerEventKind
from walk.telemetry.protocols import LedgerManager
from walk.tools.models import ToolKind
from walk.workflow.errors import WorkItemNotFound
from walk.workflow.models import WorkItem
from walk.workflow.protocols import WorkflowManager
from walk.workflow.repository import WorkflowRepository

_LOG = logging.getLogger(__name__)

MAX_REPAIR_TURNS = 1  # ARCHITECTURE §5.5
RUN_TIMEOUT_S = 2700  # used when the resolved FamilyLevel has no execution_time_s
REPAIR_INSTRUCTION = (
    "Your final output was rejected by the kernel:\n{errors}\n"
    "Write a corrected AgentOutput JSON object to .walk/output.json and finish."
)
RETRY_DELAYS_S: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0, 16.0)  # ARCHITECTURE §5.1, max 5 attempts
RESUME_INSTRUCTION = (
    "Continue the task from the current worktree state. Write .walk/output.json when finished."
)

_MAX_TURNS: Final = 50
_MS_PER_S: Final = 1000
_ACTIVE_STATES: Final = frozenset(
    {
        AgentRunState.PENDING,
        AgentRunState.RUNNING,
        AgentRunState.PAUSED_FOR_APPROVAL,
        AgentRunState.PAUSED_BY_USER,
    }
)
# Kernel decisions on an advisory (post-hoc) tool result that reject the run's effects.
_ADVISORY_REJECTIONS: Final = frozenset({"DENY", "REQUIRE_APPROVAL"})
_KERNEL_DECISION: Final = "kernel_decision"
_MEMORY_PREFIX: Final = ".ai/"
_NO_TRIGGER: Final = "none"
_NATIVE_RESUME: Final = "native_resume"
_Outcome = Literal["OK", "FAILED", "SKIPPED"]


class _Stop(Enum):
    CANCEL = "CANCEL"
    PAUSE = "PAUSE"


@dataclass
class _Live:
    """In-process state of one executing run."""

    run: AgentRun
    agent: AgentInstance
    item: WorkItem
    purpose: str
    adapter: ModelAdapter
    descriptor: ModelDescriptor
    agent_input: AgentInput
    session: RunSession
    meter: UsageMeter
    subject: BudgetSubject
    degraded_from: str | None
    started: datetime | None = None
    start_head: Sha = ""
    partial: AgentOutput | None = None
    final: AgentEvent | None = None
    pending: list[tuple[ToolCallRequest, datetime]] = field(default_factory=list)
    advisory: list[str] = field(default_factory=list)
    resume: Checkpoint | None = None
    retries: int = 0
    stop: _Stop | None = None
    finalizing: bool = False
    ended: bool = False
    task: asyncio.Task[None] | None = None


@dataclass(frozen=True)
class _StreamResult:
    """Why `DefaultAgentExecutor._consume` stopped reading a stream."""

    proceed: bool = False  # ended normally; the run continues with the final output
    error: AgentEvent | None = None  # the adapter reported ERROR
    failure: Exception | None = None  # the adapter iterator raised


@dataclass(frozen=True)
class _End:
    """How a run ends: its state, ledger outcome and failure detail."""

    state: AgentRunState
    outcome: _Outcome
    reason: str | None = None
    error: JsonDict | None = None
    task_failed: bool = False


class DefaultAgentExecutor:
    """`AgentExecutor`: runs each `AgentRun` as an asyncio task."""

    def __init__(  # noqa: PLR0917 - parameters fixed by the E01-S27/S28 contracts
        self,
        db: Database,
        runs: AgentRunRepository,
        items: WorkflowRepository,
        workflow: WorkflowManager,
        router: ModelRouter,
        inputs: AgentInputBuilder,
        sandbox: SandboxManager,
        checkpoints: DefaultCheckpointManager,
        tool_invoker: DefaultToolInvoker,
        auditor: BoundaryAuditor,
        applier: DefaultOutputApplier,
        git: GitProvider,
        budgets: BudgetManager,
        costs: CostManager,
        hooks: HookManager,
        ledger: LedgerManager,
        ids: IdFactory,
        clock: Clock,
        agents: AgentManager,
        permissions: PermissionManager,
        *,
        project_key: ProjectKey,
        kernel_instance: str,
        ready_env_keys: Callable[[], set[str]] = set,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        env_allowlist: Callable[[], dict[str, str]] = dict,
        on_run_finished: Callable[[AgentRun], Awaitable[None]] | None = None,
        allowed_paths: tuple[str, ...] = DEFAULT_ALLOWED_PATHS,
        forbidden_paths: tuple[str, ...] = DEFAULT_FORBIDDEN_PATHS,
        prompt_version: Callable[[str], str] | None = None,
    ) -> None:
        """Wire the executor.

        Args:
            db: Database every state change commits to.
            runs: ``agent_runs``.
            items: Work-item reads and the ``assigned_run_id`` column.
            workflow: Workflow service (the applier raises the status event through it).
            router: Adapter and descriptor of the run's model; error classification.
            inputs: Builds the §126 input.
            sandbox: Creates and removes the run's worktree.
            checkpoints: START/PERIODIC/AGENT_REQUESTED/PAUSE/END checkpoints.
            tool_invoker: Session authorizer and post events of provider-native tool calls.
            auditor: Boundary audit before every WIP commit and at the run end.
            applier: Applies the validated output.
            git: Status and diff of the run's worktree; discards a violating worktree.
            budgets: Applicable budgets and ``EXECUTION_TIME_S`` metering.
            costs: Token cost records (through the run's `UsageMeter`).
            hooks: ``ON_AGENT_START``, ``ON_AGENT_END``, ``ON_TASK_FAILED``.
            ledger: The ``runtime.AgentExecutor`` write point (ARCHITECTURE §4.3).
            ids: ``RUN-`` and cost record ULIDs.
            clock: Stamps events and measures the run's wall-clock time.
            agents: Instantiates the agent of a native resume.
            permissions: Escalates a run blocked by its providers to the user.
            project_key: Project of the runs, events and budgets.
            kernel_instance: Kernel process that owns the runs.
            ready_env_keys: Environment keys available to tools (native resume instances).
            sleep: Awaited between retries (`RETRY_DELAYS_S`); the composition root adds
                jitter, tests inject a recorder.
            env_allowlist: Environment of the run's subprocesses (scrubbed by E02-S01).
            on_run_finished: Awaited after a run reached an end state (wakes the scheduler);
                the composition root may bind it after construction.
            allowed_paths: Boundary audit allow globs.
            forbidden_paths: Boundary audit deny globs.
            prompt_version: Version of the task template of a purpose, reported as
                ``behavior_versions["prompt:<purpose>"]`` on the run's ledger events.
        """
        self._db = db
        self._runs = runs
        self._items = items
        self._workflow = workflow
        self._router = router
        self._inputs = inputs
        self._sandbox = sandbox
        self._checkpoints = checkpoints
        self._tool_invoker = tool_invoker
        self._auditor = auditor
        self._applier = applier
        self._git = git
        self._budgets = budgets
        self._costs = costs
        self._hooks = hooks
        self._ledger = ledger
        self._ids = ids
        self._clock = clock
        self._agents = agents
        self._permissions = permissions
        self._project_key = project_key
        self._kernel_instance = kernel_instance
        self._ready_env_keys = ready_env_keys
        self._sleep = sleep
        self._env_allowlist = env_allowlist
        self.on_run_finished = on_run_finished
        self._allowed_paths = list(allowed_paths)
        self._forbidden_paths = list(forbidden_paths)
        self._prompt_version = prompt_version
        self._live: dict[RunId, _Live] = {}
        self._tasks: dict[RunId, asyncio.Task[None]] = {}

    async def start(
        self,
        agent: AgentInstance,
        item: WorkItem,
        purpose: str,
        *,
        handover: Handover | None = None,
        parent_run_id: RunId | None = None,
        debate: Debate | None = None,
        routing: RoutingDecision | None = None,
        effort_resolution: EffortResolution | None = None,
    ) -> AgentRun:
        """ARCHITECTURE §3.2 steps 3-7; returns the RUNNING run while its task drives it.

        A failure while preparing the run (worktree, input, session) ends it FAILED and returns
        it; a failing ``ON_AGENT_START`` hook ends it FAILED_HOOK before the adapter is called.

        A child run (``parent_run_id`` of a run with a worktree) adopts that worktree.

        Raises:
            ConfigError: Unknown purpose or model, or the item already has an active run.
            WorkItemNotFound: ``item`` does not exist.
        """
        return await self._start(
            agent,
            item,
            purpose,
            handover=handover,
            parent_run_id=parent_run_id,
            debate=debate,
            routing=routing,
            effort_resolution=effort_resolution,
        )

    async def resume_native(self, checkpoint: Checkpoint) -> AgentRun:
        """Continue the checkpoint's run on the same model through the provider session.

        The new run has ``parent_run_id`` = the checkpoint's run, its session and tool-call
        count, adopts its worktree and writes ``MODEL_SELECTED(reason=native_resume)``.

        Raises:
            NotResumable: The session is missing or not resumable, the adapter is unhealthy,
                or the adapter refuses the resume (the new run then ends FAILED,
                ``not_resumable``).
            RunNotFound: The checkpoint's run does not exist.
            WorkItemNotFound: Its work item does not exist.
            ConfigError: Unknown model, or the item already has an active run.
        """
        parent = await self._persisted(checkpoint.run_id)
        item = await self._item(parent.work_item_id)
        adapter = self._router.adapter_for(checkpoint.model_id)
        ref = checkpoint.provider_session
        if ref is None or not ref.resumable:
            msg = f"checkpoint {checkpoint.id} has no resumable provider session"
            raise NotResumable(msg, detail={"checkpoint_id": checkpoint.id})
        if not (await adapter.health()).ok:
            msg = f"adapter {adapter.provider} is unhealthy"
            raise NotResumable(msg, detail={"provider": adapter.provider})
        subject = BudgetSubject(
            project_key=self._project_key,
            phase_id=item.phase_id,
            role=parent.role,
            work_item_id=item.id,
        )
        budget_ids = [budget.id for budget in await self._budgets.applicable(subject)]
        agent = await self._agents.instantiate(
            parent.role,
            item,
            checkpoint.model_id,
            checkpoint.effort,
            budget_ids,
            self._ready_env_keys(),
        )
        return await self._start(
            agent,
            item,
            parent.purpose,
            parent_run_id=parent.id,
            fallbacks=parent.fallbacks,
            resume=checkpoint,
        )

    async def cancel(self, run_id: RunId, reason: str) -> AgentRun:
        """Stop the run: PAUSE checkpoint, CANCELLED, worktree removed (branch kept).

        A run that already reached its end is returned unchanged.

        Raises:
            RunNotFound: No run has ``run_id``.
            ConfigError: The run is not executing in this kernel process.
        """
        live = await self._stopping(run_id, _Stop.CANCEL)
        if live.ended:
            return live.run
        await self._pause_checkpoint(live)
        await self._end(live, _End(AgentRunState.CANCELLED, "SKIPPED", reason=reason))
        await self._sandbox.remove(live.run, keep_branch=True)
        await self._notify_finished(live)
        return live.run

    async def pause(self, run_id: RunId) -> AgentRun:
        """Stop the run: PAUSE checkpoint, PAUSED_BY_USER; worktree and assignment are kept.

        Raises:
            RunNotFound: No run has ``run_id``.
            ConfigError: The run is not executing in this kernel process.
        """
        live = await self._stopping(run_id, _Stop.PAUSE)
        if live.ended:
            return live.run
        await self._pause_checkpoint(live)
        async with UnitOfWork(self._db) as uow:
            live.run = await self._set_state(live, AgentRunState.PAUSED_BY_USER, uow)
        return live.run

    def running(self) -> list[AgentRun]:
        """Runs whose task is still executing in this process."""
        return [
            live.run
            for live in self._live.values()
            if live.task is not None and not live.task.done()
        ]

    async def wait(self, run_id: RunId) -> AgentRun:
        """Await the run's task; return the persisted run.

        Raises:
            RunNotFound: No run has ``run_id``.
        """
        task = self._tasks.get(run_id)
        if task is not None:
            await asyncio.wait([task])
        return await self._persisted(run_id)

    # ---- start ---------------------------------------------------------------------------

    async def _start(
        self,
        agent: AgentInstance,
        item: WorkItem,
        purpose: str,
        *,
        handover: Handover | None = None,
        parent_run_id: RunId | None = None,
        debate: Debate | None = None,
        routing: RoutingDecision | None = None,
        effort_resolution: EffortResolution | None = None,
        fallbacks: int = 0,
        resume: Checkpoint | None = None,
    ) -> AgentRun:
        expected_output_for(purpose, item)
        current = await self._item(item.id)
        await self._refuse_active_run(current)
        adapter = self._router.adapter_for(agent.model_id)
        run = await self._allocate(agent, current, purpose, adapter, handover, parent_run_id)
        run = run.model_copy(update={"fallbacks": fallbacks})
        if resume is not None:
            run = run.model_copy(
                update={
                    "provider_session": resume.provider_session,
                    "tool_calls": resume.tool_calls_so_far,
                }
            )
        try:
            live = await self._prepare(run, agent, current, purpose, adapter, handover, debate)
        except Exception as exc:  # noqa: BLE001 - any preparation failure fails the run
            return await self._prepare_failed(run, exc)
        live.resume = resume
        await self._start_events(live, routing, effort_resolution)
        return await self._launch(live)

    async def _item(self, work_item_id: str) -> WorkItem:
        item = await self._items.get(work_item_id)
        if item is None:
            msg = f"work item not found: {work_item_id}"
            raise WorkItemNotFound(msg, detail={"work_item_id": work_item_id})
        return item

    async def _refuse_active_run(self, item: WorkItem) -> None:
        if item.assigned_run_id is None:
            return
        assigned = await self._runs.get(item.assigned_run_id)
        if assigned is not None and assigned.state in _ACTIVE_STATES:
            msg = f"work item {item.id} already has active run {assigned.id}"
            raise ConfigError(msg, detail={"work_item_id": item.id, "run_id": assigned.id})

    async def _allocate(  # noqa: PLR0917 - private helper of start, mirrors its parameters
        self,
        agent: AgentInstance,
        item: WorkItem,
        purpose: str,
        adapter: ModelAdapter,
        handover: Handover | None,
        parent_run_id: RunId | None,
    ) -> AgentRun:
        run = AgentRun.model_validate(
            {
                "id": f"RUN-{self._ids.new_ulid()}",
                "project_key": self._project_key,
                "work_item_id": item.id,
                "role": agent.role,
                "model_id": agent.model_id,
                "provider": adapter.provider,
                "effort": agent.effort,
                "purpose": purpose,
                "parent_run_id": parent_run_id,
                "handover_in_id": handover.id if handover is not None else None,
                "kernel_instance": self._kernel_instance,
            }
        )
        async with UnitOfWork(self._db) as uow:
            await self._runs.insert(run, uow)
            await self._items.set_assigned_run(item.id, run.id, conn=uow.conn)
            payload: JsonDict = {"role": agent.role.value, "purpose": purpose}
            await self._ledger.append(
                self._event(LedgerEventKind.AGENT_ASSIGNED, run, payload=payload), uow=uow
            )
        return run

    async def _prepare(  # noqa: PLR0917 - private helper of start, mirrors its parameters
        self,
        run: AgentRun,
        agent: AgentInstance,
        item: WorkItem,
        purpose: str,
        adapter: ModelAdapter,
        handover: Handover | None,
        debate: Debate | None,
    ) -> _Live:
        parent = await self._runs.get(run.parent_run_id) if run.parent_run_id else None
        if parent is not None and parent.worktree_path is not None:
            worktree = await self._sandbox.adopt(run, parent, item)
            branch = parent.branch or branch_name_for(item)
        else:
            worktree = await self._sandbox.create(run, item)
            branch = branch_name_for(item)
        run = run.model_copy(update={"worktree_path": worktree, "branch": branch})
        async with UnitOfWork(self._db) as uow:
            await self._runs.upsert(run, uow)
        descriptor = self._router.registry().models[run.model_id]  # adapter_for checked it
        degraded = adapter.map_effort(run.effort, run.model_id).params.get("degraded_from")
        agent_input = await self._inputs.build(
            agent,
            item,
            purpose,
            run_id=run.id,
            worktree_path=worktree,
            branch=run.branch or "",
            descriptor=descriptor,
            handover=handover,
            debate=debate,
        )
        authorizer = self._tool_invoker.authorizer_for(
            run, wait_for_approval=not _reports_tool_calls_after_the_fact(adapter)
        )
        session = build_run_session(
            run,
            agent_input,
            authorizer,
            max_turns=_MAX_TURNS,
            timeout_s=RUN_TIMEOUT_S,
            env_allowlist=self._env_allowlist(),
        )
        subject = BudgetSubject(
            project_key=self._project_key,
            phase_id=item.phase_id,
            role=run.role,
            work_item_id=item.id,
            run_id=run.id,
        )
        meter = UsageMeter(self._costs, descriptor, subject, self._clock, new_id=self._ids.new_ulid)
        return _Live(
            run=run,
            agent=agent,
            item=item,
            purpose=purpose,
            adapter=adapter,
            descriptor=descriptor,
            agent_input=agent_input,
            session=session,
            meter=meter,
            subject=subject,
            degraded_from=str(degraded) if degraded is not None else None,
        )

    async def _prepare_failed(self, run: AgentRun, exc: Exception) -> AgentRun:
        _LOG.warning(
            "agent run preparation failed", extra={"run_id": run.id, "error": _message(exc)}
        )
        stored = await self._runs.get(run.id) or run
        async with UnitOfWork(self._db) as uow:
            failed = await self._runs.set_state(
                stored.id,
                AgentRunState.FAILED,
                failure_reason=f"prepare: {_message(exc)}",
                conn=uow.conn,
            )
            payload: JsonDict = {"kind": "PREPARE", "message": _message(exc)}
            await self._ledger.append(
                self._event(LedgerEventKind.ERROR, failed, outcome="FAILED", payload=payload),
                uow=uow,
            )
            await self._unassign(failed, uow)
        await self._notify(failed)
        return failed

    async def _start_events(
        self,
        live: _Live,
        routing: RoutingDecision | None,
        effort_resolution: EffortResolution | None,
    ) -> None:
        live.started = self._clock.now()
        live.run = live.run.model_copy(update={"started_at": live.started})
        run = live.run
        started: JsonDict = {
            "purpose": live.purpose,
            "branch": run.branch,
            "worktree": run.worktree_path,
            "parent_run_id": run.parent_run_id,
            "handover_in_id": run.handover_in_id,
            "context_item_ids": live.agent_input.context.ref().item_ids,
        }
        selected: JsonDict = {"reason": _NATIVE_RESUME if live.resume else "direct"}
        if routing is not None:
            selected = {
                "reason": routing.reason,
                "rejected": [[model, why] for model, why in routing.rejected],
                "is_fallback": routing.is_fallback,
                "trigger": routing.trigger.value if routing.trigger is not None else None,
            }
        effort: JsonDict = {"effort": run.effort.value, "degraded_from": live.degraded_from}
        if effort_resolution is not None:
            effort |= effort_resolution.model_dump(mode="json")
        async with UnitOfWork(self._db) as uow:
            live.run = await self._set_state(live, AgentRunState.RUNNING, uow)
            for kind, payload in (
                (LedgerEventKind.AGENT_RUN_STARTED, started),
                (LedgerEventKind.MODEL_SELECTED, selected),
                (LedgerEventKind.EFFORT_SET, effort),
            ):
                await self._ledger.append(
                    self._event(kind, live.run, outcome="OK", payload=payload), uow=uow
                )

    async def _launch(self, live: _Live) -> AgentRun:
        doc_ids = [
            item.id
            for item in live.agent_input.context.items
            if item.source_path is not None and item.source_path.startswith(_MEMORY_PREFIX)
        ]
        try:
            await self._fire(HookName.ON_AGENT_START, live, {"context_doc_ids": doc_ids})
        except HookFailed as exc:
            await self._end(
                live, _End(AgentRunState.FAILED_HOOK, "FAILED", reason=f"hook: {exc.message}")
            )
            await self._notify_finished(live)
            return live.run
        try:
            start = await self._checkpoints.checkpoint(
                live.run,
                CheckpointKind.START,
                workflow_state=live.item.state,
                context_manifest=live.agent_input.context.ref(),
            )
        except Exception as exc:  # noqa: BLE001 - every failure ends the run
            await self._fail_with(live, exc)
            return live.run
        live.start_head = start.head_sha
        ref = live.resume.provider_session if live.resume is not None else None
        stream = await self._open_resumed_stream(live, ref) if ref is not None else None
        self._live[live.run.id] = live
        live.task = asyncio.create_task(self._drive(live, stream), name=f"walk-run-{live.run.id}")
        self._tasks[live.run.id] = live.task
        return live.run

    async def _open_resumed_stream(
        self, live: _Live, ref: ProviderSessionRef
    ) -> AsyncIterator[AgentEvent]:
        """The provider session continuation of a native resume (adapters refuse eagerly)."""
        try:
            return live.adapter.resume(ref, RESUME_INSTRUCTION, live.session)
        except NotResumable as exc:
            error: JsonDict = {"kind": "NOT_RESUMABLE", "message": exc.message}
            await self._end(live, _End(AgentRunState.FAILED, "FAILED", "not_resumable", error))
            await self._notify_finished(live)
            raise

    # ---- event loop ----------------------------------------------------------------------

    async def _drive(self, live: _Live, stream: AsyncIterator[AgentEvent] | None) -> None:
        # CancelledError (kernel shutdown) is not an Exception: the run stays RUNNING for recovery.
        try:
            if live.stop is None:
                await self._execute(live, stream)
        except Exception as exc:  # noqa: BLE001 - the task must leave a terminal state
            await self._fail_safely(live, exc)
        finally:
            self._live.pop(live.run.id, None)

    async def _execute(self, live: _Live, first: AsyncIterator[AgentEvent] | None) -> None:
        stream: AsyncIterator[AgentEvent] | None = first or live.adapter.run(
            live.agent_input, live.session
        )
        while stream is not None:
            result = await self._consume(live, stream)
            if result.failure is not None:
                stream = await self._after_adapter_failure(live, result.failure)
                continue
            if result.error is not None:
                await self._on_error_event(live, result.error)
                return
            if not result.proceed:
                return
            final = live.final
            if final is None:
                await self._fail_run(live, None, "adapter stream ended without a final output")
                return
            errors = self._validation_errors(live, final)
            if errors is None and final.output is not None:
                await self._complete(live, final.output)
                return
            stream = await self._repair(live, errors or "invalid output")

    async def _consume(self, live: _Live, stream: AsyncIterator[AgentEvent]) -> _StreamResult:
        """Handle the stream's events until it ends; the stream is always closed on return."""
        try:
            while True:
                try:
                    event = await anext(stream)
                except StopAsyncIteration:
                    break
                except Exception as exc:  # noqa: BLE001 - classified by the caller
                    return _StreamResult(failure=exc)
                if live.stop is not None or live.ended:
                    return _StreamResult()
                if event.kind is AgentEventKind.ERROR:
                    return _StreamResult(error=event)
                await self._handle(live, event)
                if live.ended:
                    return _StreamResult()
                if event.kind is AgentEventKind.ENDED:
                    break
        finally:
            close = getattr(stream, "aclose", None)
            if callable(close):
                await close()
        return _StreamResult(proceed=live.stop is None and not live.ended)

    async def _after_adapter_failure(
        self, live: _Live, exc: Exception
    ) -> AsyncIterator[AgentEvent] | None:
        """Retry a transient adapter error (ARCHITECTURE §5.1); otherwise end or fall back."""
        if isinstance(exc, TransientError) and live.retries < len(RETRY_DELAYS_S):
            return await self._retry(live, exc)
        await self._on_exception(live, exc, from_adapter=True)
        return None

    async def _retry(self, live: _Live, exc: Exception) -> AsyncIterator[AgentEvent] | None:
        live.retries += 1
        delay = RETRY_DELAYS_S[live.retries - 1]
        payload: JsonDict = {
            "reason": "transient",
            "attempt": live.retries,
            "delay": delay,
            "error": type(exc).__name__,
            "message": _message(exc),
        }
        async with UnitOfWork(self._db) as uow:
            await self._ledger.append(
                self._event(LedgerEventKind.RETRY, live.run, outcome="OK", payload=payload),
                uow=uow,
            )
        await self._sleep(delay)
        if live.stop is not None:
            return None
        live.pending.clear()
        live.final = None
        ref = live.run.provider_session
        if ref is not None and ref.resumable:
            try:
                return live.adapter.resume(ref, RESUME_INSTRUCTION, live.session)
            except NotResumable:
                _LOG.info(
                    "session not resumable; restarting the run", extra={"run_id": live.run.id}
                )
        return live.adapter.run(live.agent_input, live.session)

    async def _on_error_event(self, live: _Live, event: AgentEvent) -> None:
        message = event.error or "adapter reported an error"
        if event.trigger is not None:
            await self._fall_back(live, event.trigger, message)
            return
        await self._fail_run(live, None, message)

    async def _handle(self, live: _Live, event: AgentEvent) -> None:
        kind = event.kind
        if kind is AgentEventKind.STARTED and event.session is not None:
            live.run = live.run.model_copy(update={"provider_session": event.session})
            await self._save(live)
        elif kind is AgentEventKind.TEXT:
            _LOG.debug(
                "agent text not persisted",
                extra={"run_id": live.run.id, "chars": len(event.text or "")},
            )
        elif kind is AgentEventKind.TOOL_CALL_REQUESTED and event.tool_call is not None:
            live.pending.append((event.tool_call, event.at))
        elif kind is AgentEventKind.TOOL_CALL_RESULT:
            await self._tool_result(live, event)
        elif kind is AgentEventKind.CHECKPOINT_HINT:
            await self._audited_checkpoint(live, CheckpointKind.AGENT_REQUESTED)
        elif kind is AgentEventKind.USAGE:
            await self._meter(live)
        elif kind is AgentEventKind.PARTIAL_OUTPUT:
            live.partial = event.output
        elif kind is AgentEventKind.FINAL_OUTPUT:
            live.final = event

    async def _tool_result(self, live: _Live, event: AgentEvent) -> None:
        requested, requested_at = live.pending.pop(0) if live.pending else (None, event.at)
        request = event.tool_call or requested
        if request is None:
            msg = "tool call result without a tool call request"
            raise ConfigError(msg, detail={"run_id": live.run.id})
        result = event.tool_result or {}
        exhausted: BudgetExhausted | None = None
        if request.kind is not ToolKind.KERNEL:  # KERNEL results are recorded by invoke
            duration_ms = int((event.at - requested_at).total_seconds() * _MS_PER_S)
            try:
                await self._tool_invoker.record_result(
                    request, result, duration_ms=max(duration_ms, 0)
                )
            except BudgetExhausted as exc:
                exhausted = exc  # the call happened: count it before blocking the run
        live.run = live.run.model_copy(update={"tool_calls": live.run.tool_calls + 1})
        await self._save(live)
        if str(result.get(_KERNEL_DECISION)) in _ADVISORY_REJECTIONS:
            live.advisory.extend(request.paths or [request.tool])
        if exhausted is not None:
            raise exhausted
        every = live.agent.runtime_policy.checkpoint_every_tool_calls
        if every > 0 and live.run.tool_calls % every == 0:
            await self._audited_checkpoint(live, CheckpointKind.PERIODIC)

    async def _meter(self, live: _Live) -> None:
        if await live.meter.observe(live.adapter.usage(live.run.id)) is None:
            return
        for budget in await self._budgets.applicable(live.subject):
            if budget.hard_action is BudgetHardAction.BLOCK and budget.consumed >= budget.limit:
                msg = f"{budget.dimension.value} budget exhausted ({budget.id})"
                raise BudgetExhausted(
                    msg, detail={"budget_id": budget.id, "hard_action": budget.hard_action.value}
                )

    async def _audited_checkpoint(self, live: _Live, kind: CheckpointKind) -> None:
        if await self._violates_boundary(live, await self._git.status(_worktree(live))):
            return
        await self._checkpoint(live, kind)

    async def _checkpoint(self, live: _Live, kind: CheckpointKind) -> Checkpoint:
        return await self._checkpoints.checkpoint(
            live.run,
            kind,
            workflow_state=live.item.state,
            budget_consumed=self._consumed(live),
            context_manifest=live.agent_input.context.ref(),
        )

    async def _violates_boundary(self, live: _Live, changed: list[str]) -> bool:
        """Audit ``changed`` plus remembered advisory denials; end the run on a violation."""
        found = self._auditor.audit(
            _worktree(live), changed, self._allowed_paths, self._forbidden_paths
        )
        violations = list(dict.fromkeys([*found, *live.advisory]))
        if not violations:
            return False
        await self._git.discard_changes(_worktree(live))
        error: JsonDict = {"kind": "BOUNDARY", "violations": violations}
        reason = f"boundary: {', '.join(violations)}"
        await self._end(
            live,
            _End(AgentRunState.FAILED_BOUNDARY, "FAILED", reason, error, task_failed=True),
        )
        await self._notify_finished(live)
        return True

    # ---- output --------------------------------------------------------------------------

    def _validation_errors(self, live: _Live, final: AgentEvent) -> str | None:
        output = final.output
        if output is None:
            return final.error or "the adapter could not parse the output"
        if output.status not in live.agent_input.expected_output.status_options:
            return f"status {output.status.value} not allowed for {live.purpose}"
        return None

    async def _repair(self, live: _Live, errors: str) -> AsyncIterator[AgentEvent] | None:
        """Start the repair turn; None when no turn is left (the run then ended FAILED)."""
        ref = live.run.provider_session
        if live.run.repair_turns >= MAX_REPAIR_TURNS or ref is None or not ref.resumable:
            await self._output_invalid(live, errors)
            return None
        live.run = live.run.model_copy(update={"repair_turns": live.run.repair_turns + 1})
        live.final = None
        async with UnitOfWork(self._db) as uow:
            await self._runs.upsert(live.run, uow)
            payload: JsonDict = {
                "reason": "output_invalid",
                "errors": errors,
                "repair_turn": live.run.repair_turns,
            }
            await self._ledger.append(
                self._event(LedgerEventKind.RETRY, live.run, outcome="OK", payload=payload),
                uow=uow,
            )
        try:
            return live.adapter.resume(ref, REPAIR_INSTRUCTION.format(errors=errors), live.session)
        except NotResumable:
            await self._output_invalid(live, errors)
            return None

    async def _output_invalid(self, live: _Live, errors: str) -> None:
        error: JsonDict = {"kind": "OUTPUT_INVALID", "errors": errors}
        await self._end(
            live,
            _End(
                AgentRunState.FAILED,
                "FAILED",
                f"output_invalid: {errors}",
                error,
                task_failed=True,
            ),
        )
        await self._notify_finished(live)

    async def _complete(self, live: _Live, output: AgentOutput) -> None:
        live.finalizing = True
        worktree = _worktree(live)
        changed = sorted(
            set(await self._git.status(worktree))
            | set(await self._git.diff_names(worktree, live.start_head))
        )
        if await self._violates_boundary(live, changed):
            return
        end = await self._checkpoint(live, CheckpointKind.END)
        live.run = live.run.model_copy(update={"output": output})
        await self._save(live)
        try:
            effects = await self._applier.apply(live.run, output, start_head=live.start_head)
        except GuardRejected as exc:
            error: JsonDict = {"kind": "GUARD_REJECTED", "message": exc.message}
            reason = f"guard_rejected: {exc.message}"
            await self._end(
                live, _End(AgentRunState.FAILED, "FAILED", reason, error, task_failed=True)
            )
            await self._notify_finished(live)
            return
        await live.meter.observe(live.adapter.usage(live.run.id))
        payload: JsonDict = {
            "status": output.status.value,
            "effects": effects.model_dump(mode="json"),
            "deferred_intents": {
                "new_tasks": len(output.new_tasks),
                "new_bugs": len(output.new_bugs),
            },
        }
        await self._end(live, _End(AgentRunState.COMPLETED, "OK"), payload)
        end_payload: JsonDict = {
            "status": output.status.value,
            "context_updates": len(output.context_updates),
            "no_context_change_reason": output.no_context_change_reason,
            "checkpoint_id": end.id,
        }
        await self._fire_safely(HookName.ON_AGENT_END, live, end_payload)
        await self._notify_finished(live)

    # ---- failure paths -------------------------------------------------------------------

    async def _fail_safely(self, live: _Live, exc: Exception) -> None:
        try:
            await self._on_exception(live, exc, from_adapter=False)
        except Exception:  # noqa: BLE001 - logged; recovery resumes a run left RUNNING
            _LOG.exception("agent run could not be ended", extra={"run_id": live.run.id})

    async def _fail_with(self, live: _Live, exc: Exception) -> None:
        await self._on_exception(live, exc, from_adapter=False)

    async def _on_exception(self, live: _Live, exc: Exception, *, from_adapter: bool) -> None:
        """Adapter errors and budget exhaustion may fall back (§21); others fail the run."""
        if live.ended:
            _LOG.exception("error after the run ended", extra={"run_id": live.run.id})
            return
        trigger = (
            self._router.classify_error(exc, live.adapter)
            if from_adapter or isinstance(exc, BudgetExhausted)
            else None
        )
        if trigger is not None:
            await self._fall_back(live, trigger, _message(exc))
        elif isinstance(exc, BudgetExhausted):
            await self._block_budget(live, exc)
        else:
            await self._fail_run(live, None, _message(exc))

    async def _fall_back(self, live: _Live, trigger: FallbackTrigger, message: str) -> None:
        """INTERFACES §5.3 in the order 5 → 7-9 → 6 → 10."""
        run = live.run
        await live.adapter.cancel(run.id)
        if await self._violates_boundary(live, await self._git.status(_worktree(live))):
            return
        handover = await self._checkpoints.build_handover(run, "FALLBACK", live.partial)
        checkpoint = await self._checkpoints.checkpoint(
            live.run,
            CheckpointKind.HANDOFF,
            handover=handover,
            workflow_state=live.item.state,
            budget_consumed=self._consumed(live),
            context_manifest=live.agent_input.context.ref(),
        )
        request = FallbackRequest(
            role=run.role,
            policy=live.agent.runtime_policy.model_policy,
            current_model_id=run.model_id,
            trigger=trigger,
            profile=_profile(live),
            effort=run.effort,
            fallbacks_so_far=run.fallbacks,
        )
        try:
            decision = await self._router.fallback(request)
        except BlockedProvider as exc:
            await self._block_provider(live, exc)
            return
        payload: JsonDict = {
            "trigger": trigger.value,
            "from": run.model_id,
            "to": decision.model_id,
            "handover_id": handover.id,
            "checkpoint_id": checkpoint.id,
            "rejected": [[model, why] for model, why in decision.rejected],
        }
        async with UnitOfWork(self._db) as uow:
            await self._ledger.append(
                self._event(
                    LedgerEventKind.MODEL_FALLBACK, live.run, outcome="OK", payload=payload
                ),
                uow=uow,
            )
        await self._fire(HookName.ON_MODEL_FALLBACK, live, payload)
        reason = f"fallback: {trigger.value}: {message}"
        ended: JsonDict = {"trigger": trigger.value, "to_model_id": decision.model_id}
        await self._end(live, _End(AgentRunState.HANDED_OVER, "FAILED", reason), ended)
        successor = live.agent.model_copy(
            update={"model_id": decision.model_id, "effort": decision.effort}
        )
        child = await self._start(
            successor,
            live.item,
            live.purpose,
            handover=handover,
            parent_run_id=run.id,
            routing=decision,
            fallbacks=run.fallbacks + 1,
        )
        await self._checkpoints.close_handover(handover.id, child.id)
        await self._notify_finished(live)

    async def _block_provider(self, live: _Live, exc: BlockedProvider) -> None:
        """§21 level 3: no model left; the user decides (HANDOFF checkpoint stays)."""
        rejected = exc.detail.get("rejected", [])
        await self._permissions.request_approval(
            {
                "reason": "blocked_provider",
                "work_item_id": live.run.work_item_id,
                "run_id": live.run.id,
                "rejected": rejected,
            },
            kind="ESCALATION",
            approver=Approver.USER,
            requested_by=live.run.role,
            run_id=live.run.id,
            work_item_id=live.run.work_item_id,
        )
        error: JsonDict = {"kind": "BLOCKED_PROVIDER", "rejected": rejected}
        reason = f"blocked_provider: {exc.message}"
        await self._end(
            live,
            _End(AgentRunState.BLOCKED_PROVIDER, "FAILED", reason, error, task_failed=True),
        )
        await self._notify_finished(live)

    async def _fail_run(self, live: _Live, trigger: FallbackTrigger | None, message: str) -> None:
        """E01-S27 rule 12: FAILED, ERROR with the trigger, ON_TASK_FAILED."""
        await live.adapter.cancel(live.run.id)
        label = trigger.value if trigger is not None else _NO_TRIGGER
        error: JsonDict = {
            "kind": "RUN_ERROR",
            "trigger": trigger.value if trigger is not None else None,
            "message": message,
        }
        reason = f"error: {label}: {message}"
        await self._end(live, _End(AgentRunState.FAILED, "FAILED", reason, error, task_failed=True))
        await self._notify_finished(live)

    async def _block_budget(self, live: _Live, exc: BudgetExhausted) -> None:
        await live.adapter.cancel(live.run.id)
        await self._pause_checkpoint(live)
        error: JsonDict = {"kind": "BUDGET", "message": exc.message, **exc.detail}
        reason = f"budget: {exc.message}"
        await self._end(live, _End(AgentRunState.BLOCKED_BUDGET, "FAILED", reason, error))
        await self._notify_finished(live)

    # ---- stop and end --------------------------------------------------------------------

    async def _stopping(self, run_id: RunId, stop: _Stop) -> _Live:
        live = self._live.get(run_id)
        if live is None:
            await self._persisted(run_id)
            msg = f"run {run_id} is not executing in this kernel"
            raise ConfigError(msg, detail={"run_id": run_id})
        if not live.finalizing:
            live.stop = stop
            await live.adapter.cancel(run_id)
        if live.task is not None:
            await asyncio.wait([live.task])
        return live

    async def _pause_checkpoint(self, live: _Live) -> None:
        await self._checkpoints.checkpoint(
            live.run,
            CheckpointKind.PAUSE,
            budget_consumed=self._consumed(live),
            context_manifest=live.agent_input.context.ref(),
        )

    async def _end(self, live: _Live, end: _End, payload: JsonDict | None = None) -> None:
        """Record the run's end state, ERROR (when failed) and AGENT_RUN_ENDED; unassign."""
        live.ended = True
        if live.started is not None:
            seconds = max((self._clock.now() - live.started).total_seconds(), 0.0)
            await self._budgets.meter(live.subject, BudgetDimension.EXECUTION_TIME_S, seconds)
        async with UnitOfWork(self._db) as uow:
            live.run = await self._set_state(live, end.state, uow, failure_reason=end.reason)
            if end.error is not None:
                await self._ledger.append(
                    self._event(
                        LedgerEventKind.ERROR, live.run, outcome="FAILED", payload=end.error
                    ),
                    uow=uow,
                )
            ended: JsonDict = {
                "state": end.state.value,
                "tool_calls": live.run.tool_calls,
                "repair_turns": live.run.repair_turns,
                "failure_reason": end.reason,
                **(payload or {}),
            }
            await self._ledger.append(
                self._event(
                    LedgerEventKind.AGENT_RUN_ENDED,
                    live.run,
                    outcome=end.outcome,
                    payload=ended,
                    cost_usd=live.meter.total.cost_usd,
                ),
                uow=uow,
            )
            await self._unassign(live.run, uow)
        if end.task_failed:
            failure: JsonDict = {"state": end.state.value, "failure_reason": end.reason}
            await self._fire_safely(HookName.ON_TASK_FAILED, live, failure)

    async def _set_state(
        self,
        live: _Live,
        state: AgentRunState,
        uow: UnitOfWork,
        *,
        failure_reason: str | None = None,
    ) -> AgentRun:
        await self._runs.upsert(live.run, uow)
        return await self._runs.set_state(
            live.run.id, state, failure_reason=failure_reason, conn=uow.conn
        )

    async def _unassign(self, run: AgentRun, uow: UnitOfWork) -> None:
        item = await self._items.get(run.work_item_id)
        if item is not None and item.assigned_run_id == run.id:
            await self._items.set_assigned_run(item.id, None, conn=uow.conn)

    async def _save(self, live: _Live) -> None:
        async with UnitOfWork(self._db) as uow:
            await self._runs.upsert(live.run, uow)

    async def _persisted(self, run_id: RunId) -> AgentRun:
        run = await self._runs.get(run_id)
        if run is None:
            msg = f"unknown run {run_id}"
            raise RunNotFound(msg, detail={"run_id": run_id})
        return run

    async def _notify_finished(self, live: _Live) -> None:
        await self._notify(live.run)

    async def _notify(self, run: AgentRun) -> None:
        callback = self.on_run_finished
        if callback is None:
            return
        try:
            await callback(run)
        except Exception:  # noqa: BLE001 - a wake-up callback must not undo the run's end
            _LOG.exception("on_run_finished callback failed", extra={"run_id": run.id})

    # ---- ledger and hooks ----------------------------------------------------------------

    def _event(
        self,
        kind: LedgerEventKind,
        run: AgentRun,
        *,
        outcome: _Outcome | None = None,
        payload: JsonDict | None = None,
        cost_usd: float | None = None,
    ) -> LedgerEvent:
        versions: dict[str, str] = {}
        if self._prompt_version is not None:
            versions[f"prompt:{run.purpose}"] = self._prompt_version(run.purpose)
        return LedgerEvent(
            kind=kind,
            at=self._clock.now(),
            project_key=self._project_key,
            actor_role=run.role,
            work_item_id=run.work_item_id,
            run_id=run.id,
            model_id=run.model_id,
            effort=run.effort,
            cost_usd=cost_usd,
            outcome=outcome,
            payload=payload or {},
            behavior_versions=versions,
        )

    async def _fire(self, name: HookName, live: _Live, payload: JsonDict) -> None:
        context = HookContext(
            name=name,
            at=self._clock.now(),
            project_key=self._project_key,
            work_item_id=live.run.work_item_id,
            run_id=live.run.id,
            phase_id=live.item.phase_id,
            role=live.run.role,
            payload=payload,
        )
        await self._hooks.fire(name, context)

    async def _fire_safely(self, name: HookName, live: _Live, payload: JsonDict) -> None:
        """Fire an end-of-run hook; the run's end state stands even when a hook fails."""
        try:
            await self._fire(name, live, payload)
        except HookFailed as exc:
            _LOG.warning(
                "end-of-run hook failed",
                extra={"run_id": live.run.id, "hook": name.value, "error": exc.message},
            )

    def _consumed(self, live: _Live) -> dict[BudgetDimension, float]:
        total = live.meter.total
        return {
            BudgetDimension.TOKENS: float(
                total.input_tokens + total.output_tokens + total.cache_read_tokens
            ),
            BudgetDimension.COST_USD: total.cost_usd,
            BudgetDimension.TOOL_CALLS: float(live.run.tool_calls),
        }


def _worktree(live: _Live) -> str:
    return live.session.worktree_path


def _profile(live: _Live) -> TaskProfile:
    """E01-S28 rule 9 profile; E03-S07 replaces it with the router-built one."""
    return TaskProfile(
        required_capabilities=[],
        required_tools=list(live.agent.tools),
        required_skills=list(live.agent.skills),
        estimated_context_tokens=live.agent_input.context.total_tokens_estimate,
        risk=live.item.risk,
    )


def _message(exc: BaseException) -> str:
    if isinstance(exc, WalkError):
        return exc.message
    return str(exc) or type(exc).__name__


def _reports_tool_calls_after_the_fact(adapter: ModelAdapter) -> bool:
    """Adapters enforcing through a sandbox (Codex) report tool calls after they ran.

    ARCHITECTURE §4.2 / ADR-0006 D-5: such an adapter exposes ``configure_sandbox`` and gets
    the post-hoc authorizer that never waits for approval (E01-S27 Notes).
    """
    return callable(getattr(adapter, "configure_sandbox", None))
