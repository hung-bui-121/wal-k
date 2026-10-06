"""Applying a validated `AgentOutput` (ARCHITECTURE §3.2 step 6; E01-S27 rule 15).

The core order: context updates → evidence → the workflow event implied by the output status.
Decisions, escalations, new tasks and new bugs stay on ``run.output`` (E03-S08, E04, E05).
"""

import logging
from pathlib import Path
from typing import Final

from walk.agents.models import AgentOutput, AgentOutputStatus
from walk.common.clock import Clock
from walk.common.errors import ConfigError
from walk.common.ids import EvidenceId, Sha
from walk.common.models import Actor, JsonDict
from walk.integrations.protocols import GitProvider
from walk.memory.protocols import MemoryManager
from walk.runtime.models import AgentRun, AppliedEffects
from walk.telemetry.models import EvidenceDraft
from walk.telemetry.protocols import EvidenceManager
from walk.workflow.models import (
    TransitionContext,
    TransitionSource,
    WorkItem,
    WorkItemKind,
)
from walk.workflow.protocols import WorkflowManager

_LOG = logging.getLogger(__name__)

IMPLEMENT_OUTPUT_EVENTS: dict[AgentOutputStatus, str] = {
    AgentOutputStatus.COMPLETED: "submit_for_review",
    AgentOutputStatus.PARTIAL: "partial",
    AgentOutputStatus.BLOCKED: "block",
    AgentOutputStatus.NEEDS_INPUT: "block",
}
"""IMPLEMENT runs on STORY/TASK only; FAILED raises no event (E03-S08: output_events.yaml)."""

_EVENT_KINDS: Final = frozenset({WorkItemKind.STORY, WorkItemKind.TASK})
_EVENT_PURPOSE: Final = "IMPLEMENT"
_URI_MARKER: Final = "://"


class DefaultOutputApplier:
    """`OutputApplier` core: memory updates, evidence and the IMPLEMENT workflow event."""

    def __init__(
        self,
        memory: MemoryManager,
        evidence: EvidenceManager,
        workflow: WorkflowManager,
        git: GitProvider,
        clock: Clock,
    ) -> None:
        """Wire the applier.

        Args:
            memory: Applies ``context_updates``.
            evidence: Records the output's evidence drafts.
            workflow: Loads the item and raises the status event.
            git: HEAD of the run's worktree.
            clock: Kernel clock (kept for the full applier of E03-S08).
        """
        self._memory = memory
        self._evidence = evidence
        self._workflow = workflow
        self._git = git
        self._clock = clock

    async def apply(self, run: AgentRun, output: AgentOutput, *, start_head: Sha) -> AppliedEffects:
        """Apply ``output`` of ``run``; ``start_head`` is the worktree HEAD at run start.

        Evidence drafts are resolved against the worktree; a missing file is skipped with a
        warning. ``commit_sha`` is the worktree HEAD when it moved since ``start_head``.

        Raises:
            ConfigError: The run has no worktree or branch.
            GuardRejected: The workflow event was rejected by a guard.
            WorkItemNotFound: The run's item does not exist.
        """
        worktree, branch = _location(run)
        item = await self._workflow.get(run.work_item_id)
        actor = Actor(role=run.role, model_id=run.model_id, run_id=run.id)
        head = await self._git.head(worktree)
        memory_docs: list[str] = []
        if output.context_updates:
            written = await self._memory.apply_updates(
                output.context_updates, actor=actor, head=head, branch=branch
            )
            memory_docs = [doc.front_matter.id for doc in written]
        evidence_ids = await self._record_evidence(output, item, worktree, actor, head)
        commit_sha = head if head != start_head else None
        event = _event_for(run, item, output)
        if event is not None:
            present = await self._evidence.for_item(item.id)
            payload: JsonDict = {
                "output_status": output.status.value,
                "has_commit": commit_sha is not None,
                "evidence_kinds_present": sorted({e.kind.value for e in present}),
                "handover_present": output.handover is not None,
                "escalations_non_empty": bool(output.escalations),
            }
            context = TransitionContext(
                actor_role=run.role,
                source=TransitionSource.AGENT,
                run_id=run.id,
                payload=payload,
                phase=None,
            )
            await self._workflow.raise_event(item.id, event, context)
        return AppliedEffects(
            evidence_ids=evidence_ids,
            decision_ids=[],
            created_work_items=[],
            escalation_ids=[],
            memory_docs=memory_docs,
            commit_sha=commit_sha,
            workflow_event=event,
        )

    async def _record_evidence(
        self, output: AgentOutput, item: WorkItem, worktree: str, actor: Actor, head: Sha
    ) -> list[EvidenceId]:
        recorded: list[EvidenceId] = []
        for draft in output.evidence:
            resolved = _resolve(draft, worktree)
            if resolved is None:
                _LOG.warning(
                    "evidence file missing; draft skipped",
                    extra={"run_id": actor.run_id, "path": draft.path_or_uri},
                )
                continue
            evidence = await self._evidence.record(
                resolved,
                actor=actor,
                work_item_id=item.id,
                phase_id=item.phase_id,
                commit=head,
            )
            recorded.append(evidence.id)
        return recorded


def _location(run: AgentRun) -> tuple[str, str]:
    if run.worktree_path is None or run.branch is None:
        msg = f"run {run.id} has no worktree or branch"
        raise ConfigError(msg, detail={"run_id": run.id})
    return run.worktree_path, run.branch


def _event_for(run: AgentRun, item: WorkItem, output: AgentOutput) -> str | None:
    if item.kind not in _EVENT_KINDS or run.purpose != _EVENT_PURPOSE:
        return None
    return IMPLEMENT_OUTPUT_EVENTS.get(output.status)


def _resolve(draft: EvidenceDraft, worktree: str) -> EvidenceDraft | None:
    """The draft with its local path made absolute inside the worktree; None when missing."""
    if _URI_MARKER in draft.path_or_uri:
        return draft
    path = Path(draft.path_or_uri)
    absolute = path if path.is_absolute() else Path(worktree) / path
    if not absolute.is_file():
        return None
    return draft.model_copy(update={"path_or_uri": str(absolute)})
