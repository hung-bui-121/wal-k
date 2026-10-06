"""Default workflow manager (INTERFACES §1.3); E01-S08 implements create/get/query."""

from datetime import datetime
from pathlib import Path
from typing import Final, NoReturn

from walk.common.clock import Clock
from walk.common.errors import ConfigError, GuardRejected
from walk.common.ids import (
    EvidenceId,
    FeatureId,
    PhaseId,
    ProjectKey,
    ReleaseCandidateId,
    WorkItemId,
)
from walk.common.roles import AgentRole
from walk.hooks.models import HookContext, HookName
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
    Transition,
    TransitionContext,
    TransitionTable,
    WorkItem,
    WorkItemDraft,
    WorkItemKind,
    WorkItemState,
    WorkItemTransition,
)
from walk.workflow.repository import ProjectRepository, WorkflowRepository
from walk.workflow.state_machine import StateMachine, TableLoader

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
            hooks: Fires ``ON_STATE_TRANSITION`` and the row's hooks after commit.
            clock: Stamps ``created_at``/``updated_at``.
            tables_dir: Folder of the ``*_workflow.yaml`` transition tables (`TABLES_DIR`).

        Raises:
            ConfigError: If a table is invalid, or two tables govern the same kind.
        """
        self._db = db
        self._items = items
        self._projects = projects
        self._ids = ids
        self._ledger = ledger
        self._hooks = hooks
        self._clock = clock
        self._tables = _load_tables(tables_dir)
        self._machine = StateMachine(self._tables)

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
        """Return the transition table that governs ``kind``.

        Raises:
            ConfigError: If no loaded table lists ``kind``.
        """
        table = self._tables.get(kind)
        if table is None:
            msg = f"no transition table governs {kind.value}"
            raise ConfigError(msg, detail={"kind": kind.value})
        return table

    async def raise_event(
        self, work_item_id: WorkItemId, event: str, ctx: TransitionContext
    ) -> WorkItemTransition:
        """Apply ``event`` to the item in one transaction, then fire hooks after commit.

        The kernel adds the facts it owns to the payload before the guards run:
        ``dependency_states`` (contract dependencies) and, for a BLOCKED item, ``resume_state``
        (the state it was blocked from). ``payload["reason"]`` becomes the transition reason.

        Raises:
            WorkItemNotFound: No item has ``work_item_id``.
            UnknownTransition: The item's table has no row for its state and ``event``.
            PermissionDenied: ``ctx.actor_role`` may not raise ``event``.
            GuardRejected: A guard failed, PREVIOUS has no resume state, or
                ``payload["expected_state_version"]`` is stale.
            HookFailed: A fail-closed hook failed after the commit (the transition stays).
        """
        reason = ctx.payload.get("reason")
        if reason is not None and not isinstance(reason, str):
            msg = "payload 'reason' must be a string"
            raise ConfigError(msg, detail={"work_item_id": work_item_id, "event": event})
        async with UnitOfWork(self._db) as uow:
            item = await self.get(work_item_id)
            expected = ctx.payload.get("expected_state_version")
            if expected is not None and expected != item.state_version:
                msg = f"stale state_version for {item.id}: expected {expected}"
                detail = {"work_item_id": item.id, "expected": expected}
                raise GuardRejected(msg, detail=detail | {"actual": item.state_version})
            facts = await self._kernel_facts(item)
            ctx = ctx.model_copy(update={"payload": ctx.payload | facts})
            row = self._machine.transition_for(item.kind, item.state, event, item, ctx)
            target = self._machine.resolve_target(row, item, ctx)
            now = self._clock.now()
            updated = _apply(item, row, target, reason, now)
            await self._items.upsert(updated, uow)
            transition = await self._items.add_transition(
                WorkItemTransition(
                    seq=0,
                    work_item_id=item.id,
                    from_state=item.state,
                    to_state=target,
                    event=event,
                    source=ctx.source,
                    actor_role=ctx.actor_role,
                    run_id=ctx.run_id,
                    reason=reason,
                    at=now,
                ),
                uow,
            )
            await self._ledger.append(_transition_event(item, updated, transition), uow=uow)
            hook_ctx = HookContext(
                name=HookName.ON_STATE_TRANSITION,
                at=now,
                project_key=item.project_key,
                work_item_id=item.id,
                run_id=ctx.run_id,
                phase_id=item.phase_id,
                role=ctx.actor_role,
                payload={"from": item.state.value, "to": target.value, "event": event},
            )
            uow.after_commit(lambda: self._fire(row.hooks, hook_ctx))
        return transition

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

    async def _kernel_facts(self, item: WorkItem) -> dict[str, object]:
        facts: dict[str, object] = {}
        contract = getattr(item, "contract", None)
        if contract is not None and contract.dependencies:
            states = await self._items.states_of(contract.dependencies)
            facts["dependency_states"] = {key: state.value for key, state in states.items()}
        if item.state is WorkItemState.BLOCKED:
            blocked = await self._items.last_transition_into(item.id, WorkItemState.BLOCKED)
            facts["resume_state"] = None if blocked is None else blocked.from_state.value
        return facts

    async def _fire(self, hooks: tuple[HookName, ...], ctx: HookContext) -> None:
        for name in (HookName.ON_STATE_TRANSITION, *hooks):
            await self._hooks.fire(name, ctx.model_copy(update={"name": name}))

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


def _load_tables(tables_dir: Path) -> dict[WorkItemKind, TransitionTable]:
    """Load every ``*_workflow.yaml`` table and index it by the kinds it governs."""
    if not tables_dir.is_dir():
        msg = f"transition tables folder not found: {tables_dir}"
        raise ConfigError(msg, detail={"tables_dir": str(tables_dir)})
    loader = TableLoader()
    tables: dict[WorkItemKind, TransitionTable] = {}
    for path in sorted(tables_dir.glob("*_workflow.yaml")):
        table = loader.load(path)
        for kind in table.kinds:
            if kind in tables:
                msg = f"{kind.value} is governed by both {tables[kind].name} and {table.name}"
                raise ConfigError(msg, detail={"kind": kind.value})
            tables[kind] = table
    return tables


def _apply(
    item: WorkItem, row: Transition, target: WorkItemState, reason: object, now: datetime
) -> WorkItem:
    """Return the item after the transition: state, version, timestamps and effects."""
    update: dict[str, object] = {
        "state": target,
        "state_version": item.state_version + 1,
        "updated_at": now,
    }
    if target is WorkItemState.BLOCKED:
        update["blocked_reason"] = reason
    elif item.state is WorkItemState.BLOCKED:
        update["blocked_reason"] = None
    if target is WorkItemState.COMPLETE:
        update["completed_at"] = now
    for effect in row.effects:
        if effect == "increment_fix_loops":
            update["fix_loops"] = item.fix_loops + 1
        elif effect == "increment_reopen_count":
            if not isinstance(item, Bug):
                msg = f"effect increment_reopen_count needs a bug, got {item.kind.value}"
                raise ConfigError(msg, detail={"work_item_id": item.id})
            update["reopen_count"] = item.reopen_count + 1
        # store_resume_state needs no field: the transition row into BLOCKED keeps the state.
    return item.model_validate(item.model_dump() | update)


def _transition_event(
    item: WorkItem, updated: WorkItem, transition: WorkItemTransition
) -> LedgerEvent:
    """``WORK_ITEM_TRANSITION`` with the payload read by ``METRIC_QUERIES`` (E01-S06)."""
    payload: dict[str, object] = {
        "from": transition.from_state.value,
        "to": transition.to_state.value,
        "event": transition.event,
        "reason": transition.reason,
        "state_version": updated.state_version,
        "kind": item.kind.value,
        "fix_loops": updated.fix_loops,
    }
    if transition.to_state is WorkItemState.BLOCKED:
        payload["resume_state"] = transition.from_state.value
    elif transition.from_state is WorkItemState.BLOCKED:
        payload["resume_state"] = transition.to_state.value
    return LedgerEvent(
        kind=LedgerEventKind.WORK_ITEM_TRANSITION,
        at=transition.at,
        project_key=item.project_key,
        actor_role=transition.actor_role,
        work_item_id=item.id,
        run_id=transition.run_id,
        phase_id=item.phase_id,
        outcome="OK",
        payload=payload,
    )
