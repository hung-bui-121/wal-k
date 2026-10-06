"""Phase and release-candidate lifecycles (INTERFACES §3.4, §3.6; ADR-0010 D-3).

`DefaultWorkflowManager` delegates its phase/RC methods here so the work-item manager stays
focused on the §52 hierarchy.
"""

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from walk.common.clock import Clock
from walk.common.errors import ConfigError
from walk.common.ids import EpicId, PhaseId, ProjectKey, ReleaseCandidateId
from walk.common.models import JsonDict
from walk.hooks.models import HookContext, HookName
from walk.hooks.protocols import HookManager
from walk.persistence import Database, IdSequenceStore, UnitOfWork
from walk.telemetry.models import LedgerEvent, LedgerEventKind
from walk.telemetry.protocols import LedgerManager
from walk.workflow.models import (
    Phase,
    PhaseDecision,
    PhaseState,
    ReleaseCandidate,
    ReleaseCandidateState,
    TransitionContext,
    WorkItemKind,
)
from walk.workflow.repository import (
    PhaseRepository,
    ProjectRepository,
    ReleaseCandidateRepository,
    WorkflowRepository,
)
from walk.workflow.state_machine import PhaseStateMachine, RcStateMachine, TableLoader

_PHASE_TABLE: Final = "phase_workflow.yaml"
_RC_TABLE: Final = "rc_workflow.yaml"
LIFECYCLE_TABLE_FILES: Final = frozenset({_PHASE_TABLE, _RC_TABLE})
"""Table files in ``tables_dir`` that are phase/RC tables, not work-item tables."""
_DECIDE_PREFIX: Final = "decide:"


class Lifecycles:
    """Creates phases and drives phase/RC transitions with ledger events and hooks."""

    def __init__(
        self,
        db: Database,
        *,
        items: WorkflowRepository,
        projects: ProjectRepository,
        ids: IdSequenceStore,
        ledger: LedgerManager,
        hooks: HookManager,
        clock: Clock,
        tables_dir: Path,
    ) -> None:
        """Wire the lifecycles and load ``phase_workflow.yaml`` and ``rc_workflow.yaml``.

        Raises:
            ConfigError: If either table is missing or invalid.
        """
        self._db = db
        self._items = items
        self._projects = projects
        self._phases = PhaseRepository(db)
        self._rcs = ReleaseCandidateRepository(db)
        self._ids = ids
        self._ledger = ledger
        self._hooks = hooks
        self._clock = clock
        loader = TableLoader()
        self._phase_machine = PhaseStateMachine(
            loader.load_lifecycle(tables_dir / _PHASE_TABLE, PhaseState)
        )
        self._rc_machine = RcStateMachine(
            loader.load_lifecycle(tables_dir / _RC_TABLE, ReleaseCandidateState)
        )

    async def create_phase(
        self, name: str, ordinal: int, *, goal: str, scope_epic_ids: Sequence[EpicId]
    ) -> Phase:
        """Persist a PLANNED phase with id ``PHASE-NN``.

        Raises:
            ConfigError: ``ordinal`` < 1 or already used, or no single project.
        """
        async with UnitOfWork(self._db) as uow:
            project = await self._projects.single()
            if ordinal < 1:
                msg = f"phase ordinal must be >= 1, got {ordinal}"
                raise ConfigError(msg, detail={"ordinal": ordinal})
            existing = await self._phases.by_ordinal(project.key, ordinal)
            if existing is not None:
                msg = f"phase ordinal {ordinal} is already used by {existing.id}"
                raise ConfigError(msg, detail={"ordinal": ordinal, "phase_id": existing.id})
            phase = Phase(
                id=self._ids.bind(uow).next_sequence("PHASE"),
                project_key=project.key,
                ordinal=ordinal,
                name=name,
                goal=goal,
                scope_epic_ids=list(scope_epic_ids),
            )
            await self._phases.insert(phase, uow)
        return phase

    async def list_phases(self) -> list[Phase]:
        """Return every phase by ordinal."""
        return await self._phases.ordered()

    async def phase_event(self, phase_id: PhaseId, event: str, ctx: TransitionContext) -> Phase:
        """Apply ``event`` to the phase; see `DefaultWorkflowManager.phase_event`."""
        async with UnitOfWork(self._db) as uow:
            phase = await self._phases.get(phase_id)
            if phase is None:
                msg = f"phase not found: {phase_id}"
                raise ConfigError(msg, detail={"phase_id": phase_id})
            facts = await self._phase_facts(phase)
            ctx = ctx.model_copy(update={"payload": ctx.payload | facts, "phase": phase})
            row = self._phase_machine.transition_for(phase.state, event, phase, ctx)
            target = self._phase_machine.resolve_target(row, phase, ctx)
            now = self._clock.now()
            update: JsonDict = {"state": target}
            if "increment_gate_round" in row.effects:
                update["gate_round"] = phase.gate_round + 1
            if event == "start":
                update["started_at"] = now
            if target is PhaseState.COMPLETE:
                update["completed_at"] = now
            decision = _decision(event)
            if decision is not None:
                update["last_decision"] = decision
            updated = Phase.model_validate(phase.model_dump() | update)
            await self._phases.upsert(updated, uow)
            await self._update_project(phase_id, event, decision, uow)
            payload: JsonDict = {
                "from": phase.state.value,
                "to": target.value,
                "event": event,
                "reason": ctx.payload.get("reason"),
                "gate_round": updated.gate_round,
            }
            await self._append(LedgerEventKind.PHASE_TRANSITION, updated, ctx, payload, uow)
            if decision is not None:
                gate = {
                    "decision": decision.value,
                    "feedback": ctx.payload.get("feedback"),
                    "gate_round": updated.gate_round,
                }
                await self._append(LedgerEventKind.PHASE_GATE_DECISION, updated, ctx, gate, uow)
            hook_ctx = self._hook_context(ctx, updated.project_key, now, payload, phase_id)
            uow.after_commit(lambda: self._fire(row.hooks, hook_ctx))
        return updated

    async def rc_event(
        self, rc_id: ReleaseCandidateId, event: str, ctx: TransitionContext
    ) -> ReleaseCandidate:
        """Apply ``event`` to the candidate; see `DefaultWorkflowManager.rc_event`."""
        async with UnitOfWork(self._db) as uow:
            rc = await self._rcs.get(rc_id)
            if rc is None:
                msg = f"release candidate not found: {rc_id}"
                raise ConfigError(msg, detail={"rc_id": rc_id})
            bug_states = await self._items.states_of(rc.rejection_bug_ids)
            facts: JsonDict = {
                "build_evidence_ids": list(rc.build_evidence_ids),
                "qc_report_evidence_id": rc.qc_report_evidence_id,
                "rejection_bug_ids": list(rc.rejection_bug_ids),
                "rejection_bug_states": {key: state.value for key, state in bug_states.items()},
            }
            ctx = ctx.model_copy(update={"payload": ctx.payload | facts})
            row = self._rc_machine.transition_for(rc.state, event, rc, ctx)
            target = self._rc_machine.resolve_target(row, rc, ctx)
            now = self._clock.now()
            if "next_release_candidate" in row.effects:
                result = self._successor(rc, target, ctx, uow)
                await self._rcs.insert(result, uow)
            else:
                result = rc.model_copy(update={"state": target})
                await self._rcs.upsert(result, uow)
            payload: JsonDict = {
                "rc_id": result.id,
                "from": rc.state.value,
                "to": target.value,
                "event": event,
                "reason": ctx.payload.get("reason"),
            }
            if result.id != rc.id:
                payload["previous_rc_id"] = rc.id
            await self._append(LedgerEventKind.RC_TRANSITION, result, ctx, payload, uow)
            hook_ctx = self._hook_context(ctx, result.project_key, now, payload, None)
            uow.after_commit(lambda: self._fire(row.hooks, hook_ctx))
        return result

    async def _phase_facts(self, phase: Phase) -> JsonDict:
        previous = [p for p in await self._phases.ordered() if p.ordinal < phase.ordinal]
        features = await self._items.list_where(
            "kind = ? AND phase_id = ?", [WorkItemKind.FEATURE.value, phase.id]
        )
        return {
            "previous_phase_state": previous[-1].state.value if previous else None,
            "scope_feature_states": {item.id: item.state.value for item in features},
        }

    async def _update_project(
        self, phase_id: PhaseId, event: str, decision: PhaseDecision | None, uow: UnitOfWork
    ) -> None:
        """``start`` makes the phase current; ``decide:STOP`` pauses the project."""
        update: JsonDict = {}
        if event == "start":
            update["current_phase_id"] = phase_id
        if decision is PhaseDecision.STOP:
            update["paused"] = True
        if update:
            project = await self._projects.single()
            await self._projects.upsert(project.model_copy(update=update), uow)

    def _successor(
        self,
        rc: ReleaseCandidate,
        state: ReleaseCandidateState,
        ctx: TransitionContext,
        uow: UnitOfWork,
    ) -> ReleaseCandidate:
        commit = ctx.payload.get("commit")
        if not commit:
            msg = "next_rc needs payload 'commit' (the commit the new candidate is built from)"
            raise ConfigError(msg, detail={"rc_id": rc.id})
        try:
            return ReleaseCandidate(
                id=self._ids.bind(uow).next_sequence("RC"),
                project_key=rc.project_key,
                number=rc.number + 1,
                state=state,
                commit=commit,
                created_at=self._clock.now(),
            )
        except ValidationError as exc:
            msg = f"invalid commit for the next release candidate: {commit!r}"
            raise ConfigError(msg, detail={"rc_id": rc.id}) from exc

    async def _append(
        self,
        kind: LedgerEventKind,
        subject: Phase | ReleaseCandidate,
        ctx: TransitionContext,
        payload: JsonDict,
        uow: UnitOfWork,
    ) -> None:
        event = LedgerEvent(
            kind=kind,
            project_key=subject.project_key,
            actor_role=ctx.actor_role,
            run_id=ctx.run_id,
            phase_id=subject.id if isinstance(subject, Phase) else None,
            outcome="OK",
            payload=payload,
        )
        await self._ledger.append(event, uow=uow)

    @staticmethod
    def _hook_context(
        ctx: TransitionContext,
        project_key: ProjectKey,
        at: datetime,
        payload: JsonDict,
        phase_id: PhaseId | None,
    ) -> HookContext:
        return HookContext(
            name=HookName.ON_STATE_TRANSITION,
            at=at,
            project_key=project_key,
            run_id=ctx.run_id,
            phase_id=phase_id,
            role=ctx.actor_role,
            payload=payload,
        )

    async def _fire(self, hooks: tuple[HookName, ...], ctx: HookContext) -> None:
        for name in hooks:
            await self._hooks.fire(name, ctx.model_copy(update={"name": name}))


def _decision(event: str) -> PhaseDecision | None:
    if not event.startswith(_DECIDE_PREFIX):
        return None
    return PhaseDecision(event.removeprefix(_DECIDE_PREFIX))
