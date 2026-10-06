"""Workflow service protocols (INTERFACES §1.3)."""

from typing import Protocol

from walk.common.ids import (
    EvidenceId,
    FeatureId,
    PhaseId,
    ProjectKey,
    ReleaseCandidateId,
    WorkItemId,
)
from walk.common.roles import AgentRole
from walk.workflow.models import (
    BugDraft,
    DoneDimension,
    Feature,
    GuardResult,
    Phase,
    ReleaseCandidate,
    TransitionContext,
    TransitionTable,
    WorkItem,
    WorkItemDraft,
    WorkItemKind,
    WorkItemState,
    WorkItemTransition,
)


class Guard(Protocol):
    """Pure predicate used in TransitionTable rows."""

    def __call__(self, item: WorkItem, ctx: TransitionContext) -> GuardResult:
        """Evaluate the guard for ``item`` with the caller-supplied facts in ``ctx``."""
        ...


class WorkflowManager(Protocol):
    """§53-§54 explicit, persisted state machine. Hosted by walk.workflow.

    ``apply_external_transition`` (INTERFACES §1.3) is added by E03-S03: its
    ``WorkProviderEvent`` parameter lives in ``walk.integrations``, which ``walk.workflow``
    may not import (ARCHITECTURE §2.2).
    """

    def table_for(self, kind: WorkItemKind) -> TransitionTable:
        """Return the transition table that governs ``kind``."""
        ...

    async def create(
        self, draft: WorkItemDraft | BugDraft, *, actor: AgentRole, phase_id: PhaseId | None
    ) -> WorkItem:
        """Allocates id (id_sequences), persists, ledger WORK_ITEM_CREATED.

        Does NOT call WorkProvider (OutputApplier does).
        """
        ...

    async def get(self, work_item_id: WorkItemId) -> WorkItem:
        """Return the item; raises WorkItemNotFound."""
        ...

    async def query(
        self,
        *,
        states: list[WorkItemState] | None = None,
        kinds: list[WorkItemKind] | None = None,
        phase_id: PhaseId | None = None,
        parent_id: WorkItemId | None = None,
    ) -> list[WorkItem]:
        """Return items matching every given filter, by creation time."""
        ...

    async def raise_event(
        self, work_item_id: WorkItemId, event: str, ctx: TransitionContext
    ) -> WorkItemTransition:
        """Find the Transition for (item.state, event); evaluate guards; check the actor role.

        In ONE transaction: update state + state_version, insert work_item_transitions row,
        ledger WORK_ITEM_TRANSITION; then fires ON_STATE_TRANSITION and the transition's hooks.
        Raises GuardRejected / PermissionDenied.
        """
        ...

    async def ready_items(self, phase_id: PhaseId | None) -> list[WorkItem]:
        """Items whose state has a scheduled role and no unresolved dependencies, in phase scope."""
        ...

    def check_definition_of_ready(self, item: WorkItem) -> GuardResult:
        """§58 checks; failing → BLOCKED with reason."""
        ...

    async def set_done_dimension(
        self,
        feature_id: FeatureId,
        dimension: DoneDimension,
        done: bool,  # noqa: FBT001 - signature fixed by INTERFACES §1.3
        evidence_id: EvidenceId | None,
    ) -> Feature:
        """§6.5."""
        ...

    async def children_states(self, feature_id: FeatureId) -> dict[WorkItemId, WorkItemState]:
        """Child STORY/TASK items plus BUGs with related_feature_id == feature_id; no CANCELLED."""
        ...

    async def open_blocker_bug_count(self, feature_id: FeatureId) -> int:
        """BUGs of the feature with severity BLOCKER and state not COMPLETE/CANCELLED."""
        ...

    async def phase_event(self, phase_id: PhaseId, event: str, ctx: TransitionContext) -> Phase:
        """Raise ``event`` on a phase (phase_workflow)."""
        ...

    async def rc_event(
        self, rc_id: ReleaseCandidateId, event: str, ctx: TransitionContext
    ) -> ReleaseCandidate:
        """Raise ``event`` on a release candidate (rc_workflow)."""
        ...

    async def gdd_coverage(self, project_key: ProjectKey) -> dict[str, float]:
        """§74: COMPLETE stories with gdd_refs / all stories with gdd_refs, per GDD area."""
        ...
