"""Checkpoints and handovers (§22, §41, §54, §89; ADR-0002 D-4/D-5/D-7, ADR-0004 D-5).

A checkpoint makes a WIP commit, records the run's durable state in `checkpoints` together with
the ``CHECKPOINT_CREATED`` ledger event (one transaction), optionally writes a handover document
and fires ``ON_AGENT_CHECKPOINT`` after the commit. Every external step is idempotent per
``(run, seq)``, so a checkpoint that failed half way is replayed safely.
"""

import re
from typing import Final, get_args

from walk.agents.handover import to_document
from walk.agents.models import AgentOutput, Handover
from walk.budgets.models import BudgetDimension
from walk.common.clock import Clock
from walk.common.errors import ConfigError
from walk.common.ids import HandoverId, ProjectKey, RunId, WorkItemId
from walk.common.models import Actor
from walk.context.models import ContextBundleRef
from walk.hooks.models import HookContext, HookName
from walk.hooks.protocols import HookManager
from walk.integrations.protocols import GitProvider
from walk.memory.models import MemoryDocument
from walk.memory.protocols import MemoryManager
from walk.persistence.database import Database
from walk.persistence.idempotency import IdempotencyStore
from walk.persistence.ids import IdSequenceStore
from walk.persistence.uow import UnitOfWork
from walk.runtime.models import AgentRun, AgentRunState, Checkpoint, CheckpointKind
from walk.runtime.repository import AgentRunRepository, CheckpointRepository, HandoverRepository
from walk.telemetry.models import LedgerEvent, LedgerEventKind
from walk.telemetry.protocols import LedgerManager
from walk.workflow.models import WorkItem, WorkItemState
from walk.workflow.repository import WorkflowRepository

_DEFAULT_NEXT_ACTION: Final = "Continue the task from the current worktree state"
_HANDOVER_REASONS: Final = frozenset(get_args(Handover.model_fields["reason"].annotation))
# Kinds taken outside the executor's event loop (run start, approval or user pause) read the
# work item's state; the executor passes it explicitly for every other kind.
_STATE_FROM_ITEM: Final = frozenset({CheckpointKind.START, CheckpointKind.PAUSE})
_BULLET: Final = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_EMPTY_MANIFEST: Final = ContextBundleRef(item_ids=[], total_tokens_estimate=0)


class DefaultCheckpointManager:
    """`CheckpointManager` over SQLite, a `GitProvider` and the memory manager."""

    def __init__(  # noqa: PLR0917 - positional parameters fixed by the E01-S25 contract
        self,
        db: Database,
        runs: AgentRunRepository,
        checkpoints: CheckpointRepository,
        handovers: HandoverRepository,
        git: GitProvider,
        memory: MemoryManager,
        hooks: HookManager,
        ledger: LedgerManager,
        ids: IdSequenceStore,
        idempotency: IdempotencyStore,
        clock: Clock,
        *,
        project_key: ProjectKey,
        default_branch: str = "main",
    ) -> None:
        """Wire the manager.

        Args:
            db: Database of the runtime tables; checkpoint transactions open on it.
            runs: ``agent_runs`` (``handover_out_id`` updates; interrupted-run query).
            checkpoints: ``checkpoints`` (append-only).
            handovers: ``handovers`` rows.
            git: WIP commits, HEAD, status and diff of the run's worktree.
            memory: Writes and reads handover documents.
            hooks: Fires ``ON_AGENT_CHECKPOINT``.
            ledger: Write point for ``CHECKPOINT_CREATED`` (ARCHITECTURE §4.3 note, E01-S25).
            ids: Allocates ``HO-`` and ``CKP-`` ids.
            idempotency: Replays a handover document already written for ``(run, seq)``.
            clock: Stamps checkpoints, handovers and events.
            project_key: Project of the ledger events and hook contexts.
            default_branch: Branch a work branch forks from (`build_handover` diff base).
        """
        self._db = db
        self._runs = runs
        self._checkpoints = checkpoints
        self._handovers = handovers
        self._git = git
        self._memory = memory
        self._hooks = hooks
        self._ledger = ledger
        self._ids = ids
        self._idempotency = idempotency
        self._clock = clock
        self._project_key = project_key
        self._default_branch = default_branch
        self._items = WorkflowRepository(db)

    async def checkpoint(
        self,
        run: AgentRun,
        kind: CheckpointKind,
        *,
        handover: Handover | None = None,
        workflow_state: WorkItemState | None = None,
        budget_consumed: dict[BudgetDimension, float] | None = None,
        context_manifest: ContextBundleRef | None = None,
    ) -> Checkpoint:
        """WIP commit, optional handover document, checkpoint row + ledger, then the hook.

        A ``handover`` is written to `.ai/handovers/<id>.md`, recorded in ``handovers`` and
        set as ``run.handover_out_id`` (the run row is updated from ``run``).

        Raises:
            ConfigError: ``workflow_state`` missing for a kind other than START/PAUSE, or the
                run has no worktree.
            GitError: From the WIP commit, HEAD or status.
        """
        worktree = _worktree(run)
        state = workflow_state if workflow_state is not None else await self._item_state(run, kind)
        seq = await self._checkpoints.next_seq(run.id)
        commit = await self._git.commit_all(
            worktree,
            f"wip({run.work_item_id}): checkpoint {seq}",
            trailer_work_item=run.work_item_id,
            idempotency_key=f"git.commit:{run.id}:{seq}",
        )
        head = await self._git.head(worktree)
        dirty = await self._git.status(worktree)
        if handover is not None:
            await self._write_handover_document(run, seq, handover, head)
        now = self._clock.now()
        checkpoint = Checkpoint(
            id=f"CKP-{self._ids.new_ulid()}",
            run_id=run.id,
            work_item_id=run.work_item_id,
            seq=seq,
            kind=kind,
            at=now,
            role=run.role,
            model_id=run.model_id,
            effort=run.effort,
            workflow_state=state,
            head_sha=head,
            wip_commit_sha=commit.sha if commit is not None else None,
            dirty_files=dirty,
            tool_calls_so_far=run.tool_calls,
            budget_consumed=dict(budget_consumed or {}),
            provider_session=run.provider_session,
            handover_id=handover.id if handover is not None else None,
            context_manifest=context_manifest or _EMPTY_MANIFEST,
        )
        async with UnitOfWork(self._db) as uow:
            if handover is not None:
                await self._handovers.insert(handover, uow)
                run.handover_out_id = handover.id
                await self._runs.upsert(run, uow)
            await self._checkpoints.insert(checkpoint, uow.conn)
            await self._ledger.append(self._created_event(run, checkpoint), uow=uow)
            uow.after_commit(lambda: self._fire(run, checkpoint))
        return checkpoint

    async def latest(self, run_id: RunId) -> Checkpoint | None:
        """The run's newest checkpoint, or None."""
        return await self._checkpoints.latest(run_id)

    async def latest_for_item(self, work_item_id: WorkItemId) -> Checkpoint | None:
        """The item's newest checkpoint over all its runs, or None."""
        return await self._checkpoints.latest_for_item(work_item_id)

    async def build_handover(
        self, run: AgentRun, reason: str, partial_output: AgentOutput | None
    ) -> Handover:
        """§22 handover from the work item, the run, its partial output and the git diff.

        Never reads model transcripts. The id is allocated here (``HO-<n>``).

        Raises:
            ConfigError: ``reason`` is not a handover reason, the run has no worktree, or the
                work item is unknown.
            GitError: From HEAD, merge-base or diff.
        """
        if reason not in _HANDOVER_REASONS:
            msg = f"invalid handover reason {reason!r}"
            raise ConfigError(msg, detail={"reason": reason, "allowed": sorted(_HANDOVER_REASONS)})
        worktree = _worktree(run)
        item = await self._work_item(run.work_item_id)
        head = await self._git.head(worktree)
        base = await self._git.merge_base(self._default_branch, head, worktree)
        modified = await self._git.diff_names(worktree, base)
        output = partial_output
        embedded = output.handover if output is not None else None
        if embedded is not None:
            hypotheses, risks = list(embedded.hypotheses), list(embedded.risks)
            remaining, next_action = list(embedded.remaining_work), embedded.next_action
        else:
            hypotheses, risks = [], []
            remaining = [n.description for n in output.next_actions] if output else []
            next_action = remaining[0] if remaining else _DEFAULT_NEXT_ACTION
        async with UnitOfWork(self._db) as uow:
            handover_id = self._ids.bind(uow).next_sequence("HO")
        return Handover.model_validate(
            {
                "id": handover_id,
                "work_item_id": run.work_item_id,
                "role": run.role,
                "from_run_id": run.id,
                "from_model_id": run.model_id,
                "reason": reason,
                "task_summary": _task_summary(item),
                "current_state": (
                    f"{item.state.value}; {run.tool_calls} tool calls; branch {run.branch} @ {head}"
                ),
                "completed_work": _completed_work(output),
                "modified_files": modified,
                "findings": list(output.findings) if output else [],
                "hypotheses": hypotheses,
                "decisions": [],
                "proposed_decisions": list(output.decisions) if output else [],
                "risks": risks,
                "remaining_work": remaining,
                "next_action": next_action,
                "worktree_head": head,
                "branch": run.branch or "",
                "created_at": self._clock.now(),
            }
        )

    async def interrupted_runs(self, current_instance: str) -> list[AgentRun]:
        """RUNNING or PAUSED_FOR_APPROVAL runs owned by another kernel instance."""
        return await self._runs.by_state(
            [AgentRunState.RUNNING, AgentRunState.PAUSED_FOR_APPROVAL],
            kernel_instance_not=current_instance,
        )

    async def latest_open_handover(self, work_item_id: WorkItemId) -> Handover | None:
        """The item's newest handover that no run continues yet."""
        return await self._handovers.latest_open(work_item_id)

    async def latest_open_handover_doc(self, work_item_id: WorkItemId) -> MemoryDocument | None:
        """The document of `latest_open_handover` (the context manager's ``HandoverLookup``)."""
        handover = await self._handovers.latest_open(work_item_id)
        if handover is None:
            return None
        return await self._memory.read_handover(handover.id)

    async def close_handover(self, handover_id: HandoverId, to_run_id: RunId) -> Handover:
        """Record the run that continues the handover."""
        return await self._handovers.close(handover_id, to_run_id)

    async def _write_handover_document(
        self, run: AgentRun, seq: int, handover: Handover, head: str
    ) -> None:
        key = f"handover:{run.id}:{seq}"
        if await self._idempotency.has(key):
            return  # written by an earlier attempt of this checkpoint
        actor = Actor(role=run.role, model_id=run.model_id, run_id=run.id)
        doc = to_document(handover, actor=actor, now=self._clock.now())
        path = await self._memory.write_handover(
            doc, actor=actor, head=head, branch=run.branch or handover.branch
        )
        async with UnitOfWork(self._idempotency.db) as uow:
            await self._idempotency.put(key, "memory.write_handover", path, uow)

    async def _item_state(self, run: AgentRun, kind: CheckpointKind) -> WorkItemState:
        if kind not in _STATE_FROM_ITEM:
            msg = f"{kind.value} checkpoint needs the workflow_state"
            raise ConfigError(msg, detail={"run_id": run.id, "kind": kind.value})
        return (await self._work_item(run.work_item_id)).state

    async def _work_item(self, work_item_id: WorkItemId) -> WorkItem:
        item = await self._items.get(work_item_id)
        if item is None:
            msg = f"unknown work item {work_item_id}"
            raise ConfigError(msg, detail={"work_item_id": work_item_id})
        return item

    def _created_event(self, run: AgentRun, checkpoint: Checkpoint) -> LedgerEvent:
        return LedgerEvent(
            kind=LedgerEventKind.CHECKPOINT_CREATED,
            at=checkpoint.at,
            project_key=self._project_key,
            actor_role=run.role,
            work_item_id=run.work_item_id,
            run_id=run.id,
            model_id=run.model_id,
            effort=run.effort,
            outcome="OK",
            payload={
                "seq": checkpoint.seq,
                "kind": checkpoint.kind.value,
                "head_sha": checkpoint.head_sha,
                "wip_commit_sha": checkpoint.wip_commit_sha,
                "handover_id": checkpoint.handover_id,
            },
        )

    async def _fire(self, run: AgentRun, checkpoint: Checkpoint) -> None:
        context = HookContext(
            name=HookName.ON_AGENT_CHECKPOINT,
            at=checkpoint.at,
            project_key=self._project_key,
            work_item_id=run.work_item_id,
            run_id=run.id,
            role=run.role,
            payload={
                "checkpoint_id": checkpoint.id,
                "seq": checkpoint.seq,
                "kind": checkpoint.kind.value,
                "handover_id": checkpoint.handover_id,
            },
        )
        await self._hooks.fire(HookName.ON_AGENT_CHECKPOINT, context)


def _worktree(run: AgentRun) -> str:
    if run.worktree_path is None:
        msg = f"run {run.id} has no worktree"
        raise ConfigError(msg, detail={"run_id": run.id})
    return run.worktree_path


def _task_summary(item: WorkItem) -> str:
    contract = getattr(item, "contract", None)
    goal = getattr(contract, "goal", "") if contract is not None else ""
    return goal or item.title


def _completed_work(output: AgentOutput | None) -> list[str]:
    if output is None:
        return []
    lines = [_BULLET.sub("", line).strip() for line in output.result.splitlines()]
    return [line for line in lines if line] + [finding.summary for finding in output.findings]
