"""Transition tables as data (YAML) and the state machine that evaluates them (ADR-0010 D-4)."""

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
    Transition,
    TransitionContext,
    TransitionTable,
    WorkItem,
    WorkItemKind,
    WorkItemState,
)

TABLES_DIR: Final = Path(__file__).resolve().parent / "tables"
"""Packaged transition tables (``<name>.yaml``)."""

_EFFECTS: Final = frozenset({"increment_fix_loops", "increment_reopen_count", "store_resume_state"})
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

    def load(self, path: Path) -> TransitionTable:
        """Parse ``path`` into a `TransitionTable`.

        Every state, guard, role, hook and effect name must resolve.

        Raises:
            ConfigError: If the file is missing, is not valid YAML, does not match the schema,
                or names something unknown (the message names the file and the row).
        """
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            raw = _RawTable.model_validate(data)
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            msg = f"invalid transition table {path.name}: {exc}"
            raise ConfigError(msg, detail={"path": str(path)}) from exc
        rows = tuple(_row(path, number, row) for number, row in enumerate(raw.transitions, start=1))
        return TransitionTable(
            name=raw.name, version=raw.version, kinds=tuple(raw.kinds), transitions=rows
        )


def _row(path: Path, number: int, data: dict[str, object]) -> Transition:
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
        from_state, excluded = _from_side(raw.from_)
        to_state = _to_side(raw.to)
        hooks = tuple(HookName(hook) for hook in raw.hooks)
        roles = _roles(raw.roles)
    except ValueError as exc:
        raise fail(str(exc)) from exc
    return Transition(
        from_state=from_state,
        excluded_states=excluded,
        event=raw.event,
        to_state=to_state,
        guards=tuple(raw.guards),
        allowed_roles=roles,
        hooks=hooks,
        effects=tuple(raw.effects),
    )


def _from_side(text: str) -> tuple[WorkItemState | Literal["*"], tuple[WorkItemState, ...]]:
    if text == "*":
        return "*", ()
    if text.startswith(_EXCEPT):
        names = [name.strip() for name in text.removeprefix(_EXCEPT).split(",")]
        return "*", tuple(WorkItemState(name) for name in names)
    return WorkItemState(text), ()


def _to_side(text: str) -> WorkItemState | Literal["PREVIOUS"]:
    return "PREVIOUS" if text == "PREVIOUS" else WorkItemState(text)


def _roles(names: list[str]) -> tuple[AgentRole, ...]:
    roles: list[AgentRole] = []
    for name in names:
        expanded = _AGENT_ROLES if name == _ANY_AGENT else (AgentRole(name),)
        roles.extend(role for role in expanded if role not in roles)
    return tuple(roles)


class StateMachine:
    """Selects and resolves transitions; pure, no I/O."""

    def __init__(self, tables: dict[WorkItemKind, TransitionTable]) -> None:
        """Bind the machine to the table of each work-item kind."""
        self._tables = dict(tables)

    def transition_for(
        self,
        kind: WorkItemKind,
        state: WorkItemState,
        event: str,
        item: WorkItem,
        ctx: TransitionContext,
    ) -> Transition:
        """Return the first row for ``(state, event)`` whose guards all pass.

        Rows are evaluated in table order, wildcard rows included. ``USER`` may raise any event
        (owner authority, INTERFACES §6); guards still apply.

        Raises:
            UnknownTransition: No row matches ``(state, event)``.
            PermissionDenied: Rows exist but none allows ``ctx.actor_role``.
            GuardRejected: Allowed rows exist but each has a failing guard; ``detail`` lists
                every failing guard and its reason.
        """
        table = self._tables.get(kind)
        candidates = (
            []
            if table is None
            else [row for row in table.transitions if row.event == event and row.applies_to(state)]
        )
        detail: dict[str, object] = {"kind": kind.value, "state": state.value, "event": event}
        if not candidates:
            msg = f"no transition for event {event!r} from {state.value} ({kind.value})"
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
                if not (result := _evaluate(name, item, ctx)).ok
            ]
            if not failed:
                return row
            failures.extend({"guard": name, "reason": result.reason} for name, result in failed)
        reasons = "; ".join(f"{f['guard']}: {f['reason']}" for f in failures)
        msg = f"{event!r} rejected for {item.id}: {reasons}"
        raise GuardRejected(msg, detail=detail | {"failed_guards": failures})

    def resolve_target(
        self, transition: Transition, item: WorkItem, ctx: TransitionContext
    ) -> WorkItemState:
        """Return ``to_state``, or ``payload['resume_state']`` for the pseudo-state PREVIOUS.

        Raises:
            GuardRejected: ``no resume_state`` when PREVIOUS has no valid stored state.
        """
        if transition.to_state != "PREVIOUS":
            return WorkItemState(transition.to_state)
        resume = ctx.payload.get("resume_state")
        try:
            return WorkItemState(str(resume))
        except ValueError as exc:
            msg = f"no resume_state for {item.id}"
            detail = {"work_item_id": item.id, "resume_state": resume}
            raise GuardRejected(msg, detail=detail) from exc


def _role_allowed(role: AgentRole, row: Transition) -> bool:
    return role is AgentRole.USER or role in row.allowed_roles


def _evaluate(name: str, item: WorkItem, ctx: TransitionContext) -> GuardResult:
    return get_guard(name)(item, ctx)
