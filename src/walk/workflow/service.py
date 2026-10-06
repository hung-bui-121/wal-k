"""Default workflow manager (INTERFACES §1.3); E01-S08 implements create/get/query."""

from pathlib import Path
from typing import Final, NoReturn

from walk.common.clock import Clock
from walk.common.errors import ConfigError
from walk.common.ids import (
    EvidenceId,
    FeatureId,
    PhaseId,
    ProjectKey,
    ReleaseCandidateId,
    WorkItemId,
)
from walk.common.roles import AgentRole
from walk.hooks.protocols import HookManager
from walk.persistence import Database, IdSequenceStore, UnitOfWork
from walk.telemetry.models import LedgerEvent, LedgerEventKind
from walk.telemetry.protocols import LedgerManager
from walk.workflow.errors import WorkItemNotFound
from walk.workflow.models import (
    Bug,
    BugDraft,
    DoneDimension,
    Epic,
    Feature,
    GuardResult,
    Phase,
    ReleaseCandidate,
    Story,
    Task,
    TransitionContext,
    TransitionTable,
    WorkItem,
    WorkItemDraft,
    WorkItemKind,
    WorkItemState,
    WorkItemTransition,
)
from walk.workflow.repository import ProjectRepository, WorkflowRepository

_ID_PREFIXES: Final[dict[WorkItemKind, str]] = {
    WorkItemKind.EPIC: "EPIC",
    WorkItemKind.FEATURE: "FEAT",
    WorkItemKind.STORY: "STORY",
    WorkItemKind.TASK: "TASK",
    WorkItemKind.BUG: "BUG",
}
# Allowed parent kinds per child kind; None = no parent (DOMAIN-MODEL §2, §52).
_ALLOWED_PARENTS: Final[dict[WorkItemKind, frozenset[WorkItemKind | None]]] = {
    WorkItemKind.EPIC: frozenset({None}),
    WorkItemKind.FEATURE: frozenset({None, WorkItemKind.EPIC}),
    WorkItemKind.STORY: frozenset({WorkItemKind.FEATURE}),
    WorkItemKind.TASK: frozenset({WorkItemKind.FEATURE}),
}
_CONTRACT_KINDS: Final = frozenset({WorkItemKind.STORY, WorkItemKind.TASK})


def _deferred(method: str, story: str) -> NoReturn:
    msg = f"WorkflowManager.{method} is implemented in {story}"
    raise ConfigError(msg, detail={"method": method, "story": story})


class DefaultWorkflowManager:
    """`WorkflowManager` over SQLite; work items are created atomically with their ledger event."""

    def __init__(  # noqa: PLR0917 - positional parameters fixed by the E01-S08 contract
        self,
        db: Database,
        items: WorkflowRepository,
        projects: ProjectRepository,
        ids: IdSequenceStore,
        ledger: LedgerManager,
        hooks: HookManager,
        clock: Clock,
        tables_dir: Path,
    ) -> None:
        """Wire the manager.

        Args:
            db: Project database; every write runs in a `UnitOfWork` on it.
            items: Work-item repository.
            projects: Project repository (one project per database).
            ids: Allocates work-item ids inside the create transaction.
            ledger: Write point for ``WORK_ITEM_CREATED``.
            hooks: Fires transition hooks after commit (E01-S09).
            clock: Stamps ``created_at``/``updated_at``.
            tables_dir: Folder of the YAML transition tables (E01-S09).
        """
        self._db = db
        self._items = items
        self._projects = projects
        self._ids = ids
        self._ledger = ledger
        self._hooks = hooks
        self._clock = clock
        self._tables_dir = tables_dir

    async def create(
        self, draft: WorkItemDraft | BugDraft, *, actor: AgentRole, phase_id: PhaseId | None
    ) -> WorkItem:
        """Persist a new item in state IDEA and its ``WORK_ITEM_CREATED`` event in one transaction.

        Raises:
            ConfigError: The draft breaks a hierarchy or contract rule, the phase does not exist,
                or the database does not hold exactly one project.
            WorkItemNotFound: ``parent_id``/``related_feature_id`` names no item.
        """
        if isinstance(draft, WorkItemDraft):
            self._check_contract(draft)
        async with UnitOfWork(self._db) as uow:
            project = await self._projects.single()
            if phase_id is not None and not await self._items.phase_exists(phase_id):
                msg = f"phase {phase_id} does not exist"
                raise ConfigError(msg, detail={"phase_id": phase_id})
            if isinstance(draft, BugDraft):
                await self._check_related_feature(draft)
                kind = WorkItemKind.BUG
            else:
                await self._check_parent(draft)
                kind = draft.kind
            item_id = self._ids.bind(uow).next_sequence(_ID_PREFIXES[kind])
            item = self._build(draft, item_id, project.key, phase_id)
            await self._items.insert(item, uow)
            event = LedgerEvent(
                kind=LedgerEventKind.WORK_ITEM_CREATED,
                at=item.created_at,
                project_key=project.key,
                actor_role=actor,
                work_item_id=item.id,
                phase_id=phase_id,
                outcome="OK",
                payload={"kind": kind.value, "title": item.title, "parent_id": item.parent_id},
            )
            await self._ledger.append(event, uow=uow)
        return item

    async def get(self, work_item_id: WorkItemId) -> WorkItem:
        """Return the item.

        Raises:
            WorkItemNotFound: No item has ``work_item_id``.
        """
        item = await self._items.get(work_item_id)
        if item is None:
            msg = f"work item not found: {work_item_id}"
            raise WorkItemNotFound(msg, detail={"work_item_id": work_item_id})
        return item

    async def query(
        self,
        *,
        states: list[WorkItemState] | None = None,
        kinds: list[WorkItemKind] | None = None,
        phase_id: PhaseId | None = None,
        parent_id: WorkItemId | None = None,
    ) -> list[WorkItem]:
        """Return items matching every given filter (empty lists = no filter), by creation time."""
        clauses: list[str] = []
        params: list[object] = []
        for column, values in (("state", states), ("kind", kinds)):
            if values:
                clauses.append(f"{column} IN ({', '.join('?' for _ in values)})")
                params.extend(value.value for value in values)
        for column, value in (("phase_id", phase_id), ("parent_id", parent_id)):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        where = " AND ".join(clauses) or "1=1"
        return await self._items.list_where(where, params, order_by="created_at, id")

    def table_for(self, kind: WorkItemKind) -> TransitionTable:
        """Not available before E01-S09 (raises `ConfigError`)."""
        del kind
        _deferred("table_for", "E01-S09")

    async def raise_event(
        self, work_item_id: WorkItemId, event: str, ctx: TransitionContext
    ) -> WorkItemTransition:
        """Not available before E01-S09 (raises `ConfigError`)."""
        del work_item_id, event, ctx
        _deferred("raise_event", "E01-S09")

    async def ready_items(self, phase_id: PhaseId | None) -> list[WorkItem]:
        """Not available before E01-S10 (raises `ConfigError`)."""
        del phase_id
        _deferred("ready_items", "E01-S10")

    def check_definition_of_ready(self, item: WorkItem) -> GuardResult:
        """Not available before E01-S10 (raises `ConfigError`)."""
        del item
        _deferred("check_definition_of_ready", "E01-S10")

    async def set_done_dimension(
        self,
        feature_id: FeatureId,
        dimension: DoneDimension,
        done: bool,  # noqa: FBT001 - signature fixed by INTERFACES §1.3
        evidence_id: EvidenceId | None,
    ) -> Feature:
        """Not available before E01-S10 (raises `ConfigError`)."""
        del feature_id, dimension, done, evidence_id
        _deferred("set_done_dimension", "E01-S10")

    async def children_states(self, feature_id: FeatureId) -> dict[WorkItemId, WorkItemState]:
        """Not available before E03-S17 (raises `ConfigError`)."""
        del feature_id
        _deferred("children_states", "E03-S17")

    async def open_blocker_bug_count(self, feature_id: FeatureId) -> int:
        """Not available before E03-S17 (raises `ConfigError`)."""
        del feature_id
        _deferred("open_blocker_bug_count", "E03-S17")

    async def phase_event(self, phase_id: PhaseId, event: str, ctx: TransitionContext) -> Phase:
        """Not available before E01-S11 (raises `ConfigError`)."""
        del phase_id, event, ctx
        _deferred("phase_event", "E01-S11")

    async def rc_event(
        self, rc_id: ReleaseCandidateId, event: str, ctx: TransitionContext
    ) -> ReleaseCandidate:
        """Not available before E01-S11 (raises `ConfigError`)."""
        del rc_id, event, ctx
        _deferred("rc_event", "E01-S11")

    async def gdd_coverage(self, project_key: ProjectKey) -> dict[str, float]:
        """Not available before E06-S06 (raises `ConfigError`)."""
        del project_key
        _deferred("gdd_coverage", "E06-S06")

    @staticmethod
    def _check_contract(draft: WorkItemDraft) -> None:
        detail = {"kind": draft.kind.value, "title": draft.title}
        if draft.kind is WorkItemKind.BUG:
            msg = "bugs are created from a BugDraft"
            raise ConfigError(msg, detail=detail)
        if draft.kind in _CONTRACT_KINDS and draft.contract is None:
            msg = f"a {draft.kind.value} draft needs a contract"
            raise ConfigError(msg, detail=detail)
        if draft.kind not in _CONTRACT_KINDS and draft.contract is not None:
            msg = f"a {draft.kind.value} draft takes no contract"
            raise ConfigError(msg, detail=detail)

    async def _check_parent(self, draft: WorkItemDraft) -> None:
        allowed = _ALLOWED_PARENTS[draft.kind]
        parent_kind = None if draft.parent_id is None else (await self.get(draft.parent_id)).kind
        if parent_kind not in allowed:
            names = sorted("none" if kind is None else kind.value for kind in allowed)
            msg = (
                f"a {draft.kind.value} cannot have parent "
                f"{draft.parent_id or 'none'}; allowed parent: {' or '.join(names)}"
            )
            raise ConfigError(msg, detail={"kind": draft.kind.value, "parent_id": draft.parent_id})

    async def _check_related_feature(self, draft: BugDraft) -> None:
        # A FeatureId can only name a FEATURE (ids are allocated per kind prefix).
        if draft.related_feature_id is not None:
            await self.get(draft.related_feature_id)

    def _build(
        self,
        draft: WorkItemDraft | BugDraft,
        item_id: str,
        project_key: ProjectKey,
        phase_id: PhaseId | None,
    ) -> WorkItem:
        now = self._clock.now()
        common: dict[str, object] = {
            "id": item_id,
            "project_key": project_key,
            "title": draft.title,
            "phase_id": phase_id,
            "created_at": now,
            "updated_at": now,
        }
        if isinstance(draft, BugDraft):
            return Bug.model_validate(
                common
                | {
                    "contract": {"goal": draft.title},
                    "severity": draft.severity,
                    "reproduction": draft.reproduction,
                    "expected": draft.expected,
                    "observed": draft.observed,
                    "related_feature_id": draft.related_feature_id,
                    "found_against_commit": draft.against_commit,
                }
            )
        common |= {"description": draft.description, "parent_id": draft.parent_id}
        if draft.contract is not None:
            contract = draft.contract
            model = Story if draft.kind is WorkItemKind.STORY else Task
            return model.model_validate(
                common
                | {
                    "contract": contract,
                    "owner_role": contract.owner_role,
                    "priority": contract.priority,
                    "risk": contract.risk,
                }
            )
        return (Epic if draft.kind is WorkItemKind.EPIC else Feature).model_validate(common)
