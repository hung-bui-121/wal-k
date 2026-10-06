"""Default workflow manager (INTERFACES §1.3); E01-S08 implements create/get/query."""

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Final, Literal, NoReturn

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    TypeAdapter,
    ValidationError,
    field_validator,
)

from walk.common.clock import Clock
from walk.common.errors import ConfigError, GuardRejected
from walk.common.ids import (
    EpicId,
    EvidenceId,
    FeatureId,
    PhaseId,
    ProjectKey,
    ReleaseCandidateId,
    WorkItemId,
)
from walk.common.models import JsonDict
from walk.common.roles import AgentRole
from walk.hooks.models import HookContext, HookName
from walk.hooks.protocols import HookManager
from walk.persistence import Database, IdSequenceStore, UnitOfWork
from walk.telemetry.models import LedgerEvent, LedgerEventKind
from walk.telemetry.protocols import LedgerManager
from walk.workflow.errors import WorkItemNotFound
from walk.workflow.lifecycle import LIFECYCLE_TABLE_FILES, Lifecycles
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
from walk.workflow.readiness import definition_of_ready_checks
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
_CONTRACT_ROLES: Final = frozenset({"contract.owner_role", "contract.reviewer_role"})
_SCHEDULED_STATES_FILE: Final = "scheduled_states.yaml"


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
            ConfigError: If a table (work-item, phase or RC) or ``scheduled_states.yaml`` is
                missing or invalid, or two tables govern the same kind.
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
        self._scheduled = _load_scheduled_states(tables_dir / _SCHEDULED_STATES_FILE)
        self._lifecycles = Lifecycles(
            db,
            items=items,
            projects=projects,
            ids=ids,
            ledger=ledger,
            hooks=hooks,
            clock=clock,
            tables_dir=tables_dir,
        )

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

    def table_for(self, kind: WorkItemKind) -> TransitionTable[WorkItemState]:
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

        The kernel adds the facts it owns to the payload before the guards run, replacing any
        caller value: ``dependency_states`` (contract dependencies), ``definition_of_ready``
        (its own §58 verdict) and, for a BLOCKED item, ``resume_state`` (the state it was blocked
        from). ``payload["reason"]`` becomes the transition reason. Effect
        ``force_children_review`` moves the item's IMPLEMENTING stories/tasks to
        READY_FOR_REVIEW in the same transaction.

        Raises:
            WorkItemNotFound: No item has ``work_item_id``.
            UnknownTransition: The item's table has no row for its state and ``event``.
            PermissionDenied: ``ctx.actor_role`` may not raise ``event``.
            GuardRejected: A guard failed, PREVIOUS has no resume state, or
                ``payload["expected_state_version"]`` is stale.
            HookFailed: A fail-closed hook failed after the commit (the transition stays).
        """
        if not isinstance(ctx.payload.get("reason"), str | None):
            msg = "payload 'reason' must be a string"
            raise ConfigError(msg, detail={"work_item_id": work_item_id, "event": event})
        async with UnitOfWork(self._db) as uow:
            item = await self.get(work_item_id)
            expected = ctx.payload.get("expected_state_version")
            if expected is not None and expected != item.state_version:
                msg = f"stale state_version for {item.id}: expected {expected}"
                detail = {"work_item_id": item.id, "expected": expected}
                raise GuardRejected(msg, detail=detail | {"actual": item.state_version})
            facts = await self._kernel_facts(item, ctx.payload)
            ctx = ctx.model_copy(update={"payload": ctx.payload | facts})
            row = self._machine.transition_for(item.kind, item.state, event, item, ctx)
            target = self._machine.resolve_target(row, item, ctx)
            transition = await self._commit(item, row, target, event, ctx=ctx, uow=uow)
            if "force_children_review" in row.effects:
                await self._force_children_review(item, ctx, uow)
        return transition

    async def ready_items(self, phase_id: PhaseId | None) -> list[WorkItem]:
        """Return schedulable items, highest priority first, then oldest.

        An item is schedulable when its ``(kind, state)`` is in ``scheduled_states.yaml``, it has
        no assigned run, every contract dependency is COMPLETE and, when ``phase_id`` is given,
        it belongs to that phase or to none.
        """
        states = sorted({state for _, state in self._scheduled})
        candidates = [
            item
            for item in await self.query(states=states)
            if (item.kind, item.state) in self._scheduled
            and item.assigned_run_id is None
            and (phase_id is None or item.phase_id in {phase_id, None})
        ]
        dependency_ids = sorted({dep for item in candidates for dep in _dependencies(item)})
        dependency_states = await self._items.states_of(dependency_ids)
        ready = [
            item
            for item in candidates
            if all(
                dependency_states.get(dep) is WorkItemState.COMPLETE for dep in _dependencies(item)
            )
        ]
        return sorted(ready, key=lambda item: (item.priority.value, item.created_at, item.id))

    def check_definition_of_ready(self, item: WorkItem) -> GuardResult:
        """§58 checks with the dependencies read from the database.

        ``reason`` lists the failing check names, comma-separated.
        """
        return self._readiness(item, None)

    async def set_done_dimension(
        self,
        feature_id: FeatureId,
        dimension: DoneDimension,
        done: bool,  # noqa: FBT001 - signature fixed by INTERFACES §1.3
        evidence_id: EvidenceId | None,
    ) -> Feature:
        """Mark one done dimension of the feature (§6.5); writes no ledger event.

        ``evidence_id`` names the supporting evidence; ``Feature`` has no field for it yet, so
        it is not stored.

        Raises:
            WorkItemNotFound: No feature has ``feature_id``.
            ConfigError: ``dimension`` is not applicable to the feature.
        """
        del evidence_id
        async with UnitOfWork(self._db) as uow:
            feature = await self.get(feature_id)
            if not isinstance(feature, Feature):  # pragma: no cover - FeatureId names a feature
                msg = f"{feature_id} is not a feature"
                raise ConfigError(msg, detail={"feature_id": feature_id})
            if dimension not in feature.applicable_dimensions:
                msg = f"{dimension.value} is not an applicable dimension of {feature_id}"
                detail = {"feature_id": feature_id, "dimension": dimension.value}
                raise ConfigError(msg, detail=detail)
            updated = feature.model_copy(
                update={
                    "done_dimensions": feature.done_dimensions | {dimension: done},
                    "updated_at": self._clock.now(),
                }
            )
            await self._items.upsert(updated, uow)
        return updated

    async def children_states(self, feature_id: FeatureId) -> dict[WorkItemId, WorkItemState]:
        """Not available before E03-S17 (raises `ConfigError`)."""
        del feature_id
        _deferred("children_states", "E03-S17")

    async def open_blocker_bug_count(self, feature_id: FeatureId) -> int:
        """Not available before E03-S17 (raises `ConfigError`)."""
        del feature_id
        _deferred("open_blocker_bug_count", "E03-S17")

    async def create_phase(
        self, name: str, ordinal: int, *, goal: str = "", scope_epic_ids: Sequence[EpicId] = ()
    ) -> Phase:
        """Persist a PLANNED phase with id ``PHASE-NN`` (no ledger event).

        Raises:
            ConfigError: ``ordinal`` < 1 or already used by another phase.
        """
        return await self._lifecycles.create_phase(
            name, ordinal, goal=goal, scope_epic_ids=scope_epic_ids
        )

    async def list_phases(self) -> list[Phase]:
        """Return every phase by ordinal."""
        return await self._lifecycles.list_phases()

    async def phase_event(self, phase_id: PhaseId, event: str, ctx: TransitionContext) -> Phase:
        """Raise ``event`` on the phase (``phase_workflow``) in one transaction.

        Kernel facts for the guards: ``previous_phase_state`` and ``scope_feature_states``;
        ``ctx.phase`` is the phase. Writes ``PHASE_TRANSITION`` and, for ``decide:*``,
        ``PHASE_GATE_DECISION`` (payload ``decision``, ``feedback``). ``start`` sets
        ``started_at`` and makes the phase current; COMPLETE sets ``completed_at``;
        ``package_ready`` increments ``gate_round``; ``decide:STOP`` pauses the project. The
        row's hooks fire after commit.

        Raises:
            ConfigError: No phase has ``phase_id``.
            UnknownTransition, PermissionDenied, GuardRejected: As `raise_event`.
        """
        return await self._lifecycles.phase_event(phase_id, event, ctx)

    async def rc_event(
        self, rc_id: ReleaseCandidateId, event: str, ctx: TransitionContext
    ) -> ReleaseCandidate:
        """Raise ``event`` on the release candidate (``rc_workflow``) in one transaction.

        Kernel facts: ``build_evidence_ids``, ``qc_report_evidence_id``, ``rejection_bug_ids``
        and ``rejection_bug_states``. Writes ``RC_TRANSITION``. ``next_rc`` keeps the rejected
        candidate and returns a new one (number + 1, BUILDING) built from ``payload["commit"]``.

        Raises:
            ConfigError: No candidate has ``rc_id``, or ``next_rc`` lacks a valid commit.
            UnknownTransition, PermissionDenied, GuardRejected: As `raise_event`.
        """
        return await self._lifecycles.rc_event(rc_id, event, ctx)

    async def gdd_coverage(self, project_key: ProjectKey) -> dict[str, float]:
        """Not available before E06-S06 (raises `ConfigError`)."""
        del project_key
        _deferred("gdd_coverage", "E06-S06")

    async def _kernel_facts(self, item: WorkItem, payload: JsonDict) -> dict[str, object]:
        deps = self._items.items_by_id(_dependencies(item))
        facts: dict[str, object] = {
            "definition_of_ready": self._readiness(item, payload, deps).model_dump(),
        }
        if _dependencies(item):
            facts["dependency_states"] = {dep.id: dep.state.value for dep in deps}
        if item.state is WorkItemState.BLOCKED:
            blocked = await self._items.last_transition_into(item.id, WorkItemState.BLOCKED)
            facts["resume_state"] = None if blocked is None else blocked.from_state.value
        return facts

    def _readiness(
        self, item: WorkItem, facts: JsonDict | None, deps: list[WorkItem] | None = None
    ) -> GuardResult:
        if deps is None:
            deps = self._items.items_by_id(_dependencies(item))
        checks = definition_of_ready_checks(item, deps, facts=facts)
        failing = [name for name, ok, _ in checks if not ok]
        return GuardResult(ok=not failing, reason=", ".join(failing))

    async def _commit(
        self,
        item: WorkItem,
        row: Transition[WorkItemState],
        target: WorkItemState,
        event: str,
        *,
        ctx: TransitionContext,
        uow: UnitOfWork,
    ) -> WorkItemTransition:
        """Persist one transition on ``uow`` and schedule its hooks for after the commit."""
        reason = ctx.payload.get("reason")
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

    async def _force_children_review(
        self, feature: WorkItem, ctx: TransitionContext, uow: UnitOfWork
    ) -> None:
        """Raise ``force_review`` on every IMPLEMENTING story/task of ``feature`` (same unit)."""
        for child in await self._items.children(feature.id):
            if child.kind in _CONTRACT_KINDS and child.state is WorkItemState.IMPLEMENTING:
                row = self._machine.transition_for(
                    child.kind, child.state, "force_review", child, ctx
                )
                target = self._machine.resolve_target(row, child, ctx)
                await self._commit(child, row, target, "force_review", ctx=ctx, uow=uow)

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


class _ScheduledState(BaseModel):
    """One ``scheduled_states.yaml`` row (INTERFACES §4)."""

    model_config = ConfigDict(extra="forbid")

    kind: WorkItemKind
    state: WorkItemState
    role: str
    fallback_role: AgentRole | None = None
    purpose: Literal["PLAN", "DESIGN", "IMPLEMENT", "REVIEW", "QC", "TRIAGE"]

    @field_validator("role")
    @classmethod
    def _known_role(cls, value: str) -> str:
        if value not in _CONTRACT_ROLES and value not in AgentRole.__members__:
            msg = f"unknown role {value!r}"
            raise ValueError(msg)
        return value


def _load_scheduled_states(path: Path) -> frozenset[tuple[WorkItemKind, WorkItemState]]:
    """Return the schedulable ``(kind, state)`` pairs of ``scheduled_states.yaml``."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        rows = TypeAdapter(list[_ScheduledState]).validate_python(data)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        msg = f"invalid {path.name}: {exc}"
        raise ConfigError(msg, detail={"path": str(path)}) from exc
    return frozenset((row.kind, row.state) for row in rows)


def _dependencies(item: WorkItem) -> list[WorkItemId]:
    contract = getattr(item, "contract", None)
    return [] if contract is None else list(contract.dependencies)


def _load_tables(tables_dir: Path) -> dict[WorkItemKind, TransitionTable[WorkItemState]]:
    """Load every work-item ``*_workflow.yaml`` table and index it by the kinds it governs."""
    if not tables_dir.is_dir():
        msg = f"transition tables folder not found: {tables_dir}"
        raise ConfigError(msg, detail={"tables_dir": str(tables_dir)})
    loader = TableLoader()
    tables: dict[WorkItemKind, TransitionTable[WorkItemState]] = {}
    for path in sorted(tables_dir.glob("*_workflow.yaml")):
        if path.name in LIFECYCLE_TABLE_FILES:
            continue
        table = loader.load(path)
        for kind in table.kinds:
            if kind in tables:
                msg = f"{kind.value} is governed by both {tables[kind].name} and {table.name}"
                raise ConfigError(msg, detail={"kind": kind.value})
            tables[kind] = table
    return tables


def _apply(
    item: WorkItem,
    row: Transition[WorkItemState],
    target: WorkItemState,
    reason: object,
    now: datetime,
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
        # store_resume_state needs no field (the transition row into BLOCKED keeps the state);
        # force_children_review is applied by DefaultWorkflowManager on the children.
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
