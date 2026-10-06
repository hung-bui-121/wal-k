"""Orchestrator service protocols (INTERFACES §1.1)."""

from typing import Protocol

from walk.common.ids import PhaseId, RunId, WorkItemId
from walk.decisions.models import Escalation
from walk.orchestrator.models import KernelStatus, PhaseEvidencePackage, RouteDecision
from walk.workflow.models import Feature, GddRef, Phase, PhaseDecision, WorkItem, WorkItemState


class Orchestrator(Protocol):
    """§10.1, §56, §67-§72, §93. Owns the scheduling loop and phase gates."""

    async def start(self) -> None:
        """Run the startup sequence (ARCHITECTURE.md §3.4), then the loop until `stop()`."""
        ...

    async def stop(self, *, drain: bool = True) -> None:
        """Checkpoint and pause all running agents (drain=True waits for a checkpoint boundary).

        Release lock.
        """
        ...

    async def wake(self) -> None:
        """Signal the scheduler to run a tick now (webhook ingest, run completion, commands)."""
        ...

    async def tick(self) -> int:
        """One scheduling pass: admit ready work (INTERFACES §5.1), returns runs started."""
        ...

    async def submit_feature(self, title: str, description: str, gdd_refs: list[GddRef]) -> Feature:
        """§131 'User Feature' entry: creates Feature(IDEA) and a PLAN run for ORCHESTRATOR role."""
        ...

    async def plan_phase(self, phase_id: PhaseId) -> list[WorkItem]:
        """[Stage 6] GDD compiler output → epics/features/stories within phase scope (§48, §52)."""
        ...

    async def start_phase(self, phase_id: PhaseId) -> Phase:
        """PLANNED → ACTIVE. Requires user GO on previous phase or project start.

        Fires ON_PHASE_START.
        """
        ...

    async def request_phase_review(self, phase_id: PhaseId) -> PhaseEvidencePackage:
        """ACTIVE → EVIDENCE_REVIEW → USER_GATE. Builds evidence package (§69), retrospective."""
        ...

    async def decide_phase(
        self, phase_id: PhaseId, decision: PhaseDecision, feedback: str | None, actor: str
    ) -> Phase:
        """§70. USER only. GO→COMPLETE(+ next ACTIVE); REWORK→REWORK; CHANGE→CHANGE_ANALYSIS.

        STOP→STOPPED + project paused. Ledger PHASE_GATE_DECISION.
        """
        ...

    async def handle_escalation(self, escalation: Escalation) -> None:
        """Route per AutonomyLevel: 1→DebateManager.open, 2→PO run, 3→ApprovalRequest(USER)."""
        ...

    async def pause(self, run_id: RunId | None = None) -> None:
        """§93 Pause Project / Pause Agent. Checkpoint(PAUSE) then state PAUSED_BY_USER."""
        ...

    async def resume(self, run_id: RunId | None = None) -> None:
        """§93 Resume Project / Resume Agent."""
        ...

    async def cancel_work_item(self, work_item_id: WorkItemId, reason: str) -> None:
        """§93 Cancel Task: cancel run, state CANCELLED, remove worktree."""
        ...

    async def force_review(self, work_item_id: WorkItemId) -> None:
        """§93: raise `force_review` → READY_FOR_REVIEW regardless of the implementer state."""
        ...

    def status(self) -> KernelStatus:
        """§87 snapshot (current phase, active runs, blocked items, pending approvals, budgets)."""
        ...


class TaskRouter(Protocol):
    """§10.1 'assign role', §29 required skills. Hosted by walk.orchestrator."""

    def route(self, item: WorkItem, state: WorkItemState) -> RouteDecision:
        """Pure function of (kind, state, contract.owner_role/reviewer_role) per INTERFACES §4.

        Returns role + purpose + TaskProfile. Never returns the role of
        `item.assigned_run_id`'s implementer for REVIEW/QC purposes (Invariant 4).
        """
        ...

    def can_run_parallel(self, a: WorkItem, b: WorkItem) -> bool:
        """§60: false if dependency edge, same feature with overlapping files, or same branch."""
        ...
