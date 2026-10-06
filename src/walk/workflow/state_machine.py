"""Transition tables as data (YAML) and the state machines that evaluate them (ADR-0010 D-4).

One engine (`_Engine`) is generic over the state enum; `StateMachine` drives work items,
`PhaseStateMachine` phases and `RcStateMachine` release candidates.
"""

from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from walk.common.errors import ConfigError, GuardRejected, PermissionDenied
from walk.common.roles import AgentRole
from walk.hooks.models import HookName
from walk.workflow.errors import UnknownTransition
from walk.workflow.guards import get_guard
from walk.workflow.models import (
    GuardResult,
    GuardSubject,
    Phase,
    PhaseState,
    ReleaseCandidate,
    ReleaseCandidateState,
    Transition,
    TransitionContext,
    TransitionTable,
    WorkItem,
    WorkItemKind,
    WorkItemState,
)

TABLES_DIR: Final = Path(__file__).resolve().parent / "tables"
"""Packaged transition tables (``<name>.yaml``)."""

_EFFECTS: Final = frozenset(
    {
        "increment_fix_loops",
        "increment_reopen_count",
        "store_resume_state",
        "force_children_review",
        "increment_gate_round",
        "next_release_candidate",
    }
)
_ANY_AGENT: Final = "ANY_AGENT"
_AGENT_ROLES: Final = tuple(r for r in AgentRole if r not in {AgentRole.USER, AgentRole.KERNEL})
_EXCEPT: Final = "* except "


class _RawRow(BaseModel):
    """One YAML row before name resolution."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: str = Field(alias="from")
    event: str
    to: str
    guards: list[str] = Field(default_factory=list)
    roles: list[str]
    hooks: list[str] = Field(default_factory=list)
    effects: list[str] = Field(default_factory=list)


class _RawTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    kinds: list[WorkItemKind] = Field(default_factory=list)
    transitions: list[dict[str, object]]


class TableLoader:
    """Loads and validates a ``<name>_workflow.yaml`` transition table."""

    def load(self, path: Path) -> TransitionTable[WorkItemState]:
        """Parse a work-item table (states are `WorkItemState`).

        Every state, guard, role, hook and effect name must resolve.

        Raises:
            ConfigError: If the file is missing, is not valid YAML, does not match the schema,
                or names something unknown (the message names the file and the row).
        """
        return self.load_lifecycle(path, WorkItemState)

    def load_lifecycle[S: StrEnum](self, path: Path, states: type[S]) -> TransitionTable[S]:
        """Parse a table whose states belong to ``states`` (e.g. `PhaseState`).

        Raises:
            ConfigError: As `load`.
        """
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            raw = _RawTable.model_validate(data)
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            msg = f"invalid transition table {path.name}: {exc}"
            raise ConfigError(msg, detail={"path": str(path)}) from exc
        rows = tuple(
            _row(path, number, row, states) for number, row in enumerate(raw.transitions, start=1)
        )
        return TransitionTable[S](
            name=raw.name, version=raw.version, kinds=tuple(raw.kinds), transitions=rows
        )


def _row[S: StrEnum](
    path: Path, number: int, data: dict[str, object], states: type[S]
) -> Transition[S]:
    label = f"{data.get('from')} --{data.get('event')}-->"

    def fail(problem: str) -> ConfigError:
        msg = f"{path.name} row {number} ({label}): {problem}"
        return ConfigError(msg, detail={"path": str(path), "row": number})

    try:
        raw = _RawRow.model_validate(data)
    except ValidationError as exc:
        raise fail(str(exc)) from exc
    for guard in raw.guards:
        try:
            get_guard(guard)
        except ConfigError as exc:
            problem = f"unknown guard {guard!r}"
            raise fail(problem) from exc
    unknown_effects = [effect for effect in raw.effects if effect not in _EFFECTS]
    if unknown_effects:
        problem = f"unknown effect {unknown_effects[0]!r}"
        raise fail(problem)
    try:
        from_state, excluded = _from_side(raw.from_, states)
        to_state = _to_side(raw.to, states)
        hooks = tuple(HookName(hook) for hook in raw.hooks)
        roles = _roles(raw.roles)
    except ValueError as exc:
        raise fail(str(exc)) from exc
    return Transition[S](
        from_state=from_state,
        excluded_states=excluded,
        event=raw.event,
        to_state=to_state,
        guards=tuple(raw.guards),
        allowed_roles=roles,
        hooks=hooks,
        effects=tuple(raw.effects),
    )


def _from_side[S: StrEnum](text: str, states: type[S]) -> tuple[S | Literal["*"], tuple[S, ...]]:
    if text == "*":
        return "*", ()
    if text.startswith(_EXCEPT):
        names = [name.strip() for name in text.removeprefix(_EXCEPT).split(",")]
        return "*", tuple(states(name) for name in names)
    return states(text), ()


def _to_side[S: StrEnum](
    text: str, states: type[S]
) -> S | Literal["PREVIOUS", "CHILDREN_READY_FOR_REVIEW"]:
    if text == "PREVIOUS":
        return "PREVIOUS"
    if text == "CHILDREN_READY_FOR_REVIEW":
        return "CHILDREN_READY_FOR_REVIEW"
    return states(text)


def _roles(names: list[str]) -> tuple[AgentRole, ...]:
    roles: list[AgentRole] = []
    for name in names:
        expanded = _AGENT_ROLES if name == _ANY_AGENT else (AgentRole(name),)
        roles.extend(role for role in expanded if role not in roles)
    return tuple(roles)


class _Engine[S: StrEnum]:
    """Row selection and target resolution over one table; pure, no I/O."""

    def __init__(self, table: TransitionTable[S] | None, states: type[S], scope: str) -> None:
        self._table = table
        self._states = states
        self._scope = scope

    def select(
        self, state: S, event: str, subject: GuardSubject, ctx: TransitionContext
    ) -> Transition[S]:
        rows = () if self._table is None else self._table.transitions
        candidates = [row for row in rows if row.event == event and row.applies_to(state)]
        detail: dict[str, object] = {"kind": self._scope, "state": state.value, "event": event}
        if not candidates:
            msg = f"no transition for event {event!r} from {state.value} ({self._scope})"
            raise UnknownTransition(msg, detail=detail)
        permitted = [row for row in candidates if _role_allowed(ctx.actor_role, row)]
        if not permitted:
            allowed = sorted({role.value for row in candidates for role in row.allowed_roles})
            msg = f"{ctx.actor_role.value} may not raise {event!r}; allowed: {', '.join(allowed)}"
            detail |= {"actor_role": ctx.actor_role.value, "allowed_roles": allowed}
            raise PermissionDenied(msg, detail=detail)
        failures: list[dict[str, str]] = []
        for row in permitted:
            failed = [
                (name, result)
                for name in row.guards
                if not (result := _evaluate(name, subject, ctx)).ok
            ]
            if not failed:
                return row
            failures.extend({"guard": name, "reason": result.reason} for name, result in failed)
        reasons = "; ".join(f"{f['guard']}: {f['reason']}" for f in failures)
        msg = f"{event!r} rejected for {subject.id}: {reasons}"
        raise GuardRejected(msg, detail=detail | {"failed_guards": failures})

    def resolve(
        self, transition: Transition[S], current: S, subject_id: str, ctx: TransitionContext
    ) -> S:
        if transition.to_state == "CHILDREN_READY_FOR_REVIEW":
            return current
        if transition.to_state != "PREVIOUS":
            return self._states(transition.to_state)
        resume = ctx.payload.get("resume_state")
        try:
            return self._states(str(resume))
        except ValueError as exc:
            msg = f"no resume_state for {subject_id}"
            detail = {"subject_id": subject_id, "resume_state": resume}
            raise GuardRejected(msg, detail=detail) from exc


class StateMachine:
    """Selects and resolves work-item transitions; pure, no I/O."""

    def __init__(self, tables: dict[WorkItemKind, TransitionTable[WorkItemState]]) -> None:
        """Bind the machine to the table of each work-item kind."""
        self._engines = {
            kind: _Engine(table, WorkItemState, kind.value) for kind, table in tables.items()
        }

    def transition_for(
        self,
        kind: WorkItemKind,
        state: WorkItemState,
        event: str,
        item: WorkItem,
        ctx: TransitionContext,
    ) -> Transition[WorkItemState]:
        """Return the first row for ``(state, event)`` whose guards all pass.

        Rows are evaluated in table order, wildcard rows included. ``USER`` may raise any event
        (owner authority, INTERFACES §6); guards still apply.

        Raises:
            UnknownTransition: No row matches ``(state, event)``.
            PermissionDenied: Rows exist but none allows ``ctx.actor_role``.
            GuardRejected: Allowed rows exist but each has a failing guard; ``detail`` lists
                every failing guard and its reason.
        """
        engine = self._engines.get(kind, _Engine(None, WorkItemState, kind.value))
        return engine.select(state, event, item, ctx)

    def resolve_target(
        self, transition: Transition[WorkItemState], item: WorkItem, ctx: TransitionContext
    ) -> WorkItemState:
        """Return ``to_state`` or resolve a pseudo-state.

        PREVIOUS resolves to ``payload['resume_state']``; CHILDREN_READY_FOR_REVIEW keeps the
        item's own state (its children move through the ``force_children_review`` effect).

        Raises:
            GuardRejected: ``no resume_state`` when PREVIOUS has no valid stored state.
        """
        engine = _Engine(None, WorkItemState, item.kind.value)
        return engine.resolve(transition, item.state, item.id, ctx)


class PhaseStateMachine:
    """Selects and resolves phase transitions (``phase_workflow``); pure, no I/O."""

    def __init__(self, table: TransitionTable[PhaseState]) -> None:
        """Bind the machine to the phase table."""
        self._engine = _Engine(table, PhaseState, "PHASE")

    def transition_for(
        self, state: PhaseState, event: str, phase: Phase, ctx: TransitionContext
    ) -> Transition[PhaseState]:
        """Return the first permitted row whose guards pass (errors as `StateMachine`)."""
        return self._engine.select(state, event, phase, ctx)

    def resolve_target(
        self, transition: Transition[PhaseState], phase: Phase, ctx: TransitionContext
    ) -> PhaseState:
        """Return the row's target state."""
        return self._engine.resolve(transition, phase.state, phase.id, ctx)


class RcStateMachine:
    """Selects and resolves release-candidate transitions (``rc_workflow``); pure, no I/O."""

    def __init__(self, table: TransitionTable[ReleaseCandidateState]) -> None:
        """Bind the machine to the RC table."""
        self._engine = _Engine(table, ReleaseCandidateState, "RC")

    def transition_for(
        self,
        state: ReleaseCandidateState,
        event: str,
        rc: ReleaseCandidate,
        ctx: TransitionContext,
    ) -> Transition[ReleaseCandidateState]:
        """Return the first permitted row whose guards pass (errors as `StateMachine`)."""
        return self._engine.select(state, event, rc, ctx)

    def resolve_target(
        self,
        transition: Transition[ReleaseCandidateState],
        rc: ReleaseCandidate,
        ctx: TransitionContext,
    ) -> ReleaseCandidateState:
        """Return the row's target state."""
        return self._engine.resolve(transition, rc.state, rc.id, ctx)


def _role_allowed[S: StrEnum](role: AgentRole, row: Transition[S]) -> bool:
    return role is AgentRole.USER or role in row.allowed_roles


def _evaluate(name: str, subject: GuardSubject, ctx: TransitionContext) -> GuardResult:
    return get_guard(name)(subject, ctx)
