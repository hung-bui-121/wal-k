"""Guard registry and the guards of ``story_workflow`` (INTERFACES §3, WBS §3.4).

Guards are pure predicates over the work item and the facts the caller put in
`TransitionContext.payload` under the fixed WBS §3.4 keys. The kernel adds the facts it owns
(``dependency_states``, ``resume_state``) before evaluating them. The registry is filled once,
at import time, by the ``@register_guard`` decorators in this module.
"""

from collections.abc import Callable
from typing import Final

from walk.common.errors import ConfigError
from walk.workflow.models import GuardResult, TransitionContext, WorkItem, WorkItemState
from walk.workflow.protocols import Guard

_REGISTRY: dict[str, Guard] = {}
_OK: Final = GuardResult(ok=True)
_MISSING: Final = GuardResult(ok=False, reason="payload missing")
_DEFAULT_MAX_FIX_LOOPS: Final = 3  # WBS §3.4: RuntimePolicy / project config default


def register_guard(name: str) -> Callable[[Guard], Guard]:
    """Return a decorator that registers a guard under ``name``.

    Raises:
        ConfigError: If ``name`` is already registered.
    """

    def decorator(guard: Guard) -> Guard:
        if name in _REGISTRY:
            msg = f"guard {name!r} is already registered"
            raise ConfigError(msg, detail={"guard": name})
        _REGISTRY[name] = guard
        return guard

    return decorator


def get_guard(name: str) -> Guard:
    """Return the guard registered as ``name``.

    Raises:
        ConfigError: If no guard has that name.
    """
    guard = _REGISTRY.get(name)
    if guard is None:
        msg = f"unknown guard {name!r}"
        raise ConfigError(msg, detail={"guard": name})
    return guard


def registered_guards() -> dict[str, Guard]:
    """Return a copy of the registry (name → guard)."""
    return dict(_REGISTRY)


def _flag(ctx: TransitionContext, key: str) -> GuardResult:
    """Pass when ``payload[key] is True``."""
    value = ctx.payload.get(key)
    if value is None:
        return _MISSING
    return _OK if value is True else GuardResult(ok=False, reason=f"{key} is false")


def _output_status(ctx: TransitionContext, expected: str) -> GuardResult:
    status = ctx.payload.get("output_status")
    if status is None:
        return _MISSING
    if status == expected:
        return _OK
    return GuardResult(ok=False, reason=f"output_status is {status}, expected {expected}")


def _max_fix_loops(ctx: TransitionContext) -> int:
    return int(ctx.payload.get("max_fix_loops", _DEFAULT_MAX_FIX_LOOPS))


@register_guard("definition_of_ready")
def definition_of_ready(item: WorkItem, ctx: TransitionContext) -> GuardResult:
    """§58 subset until E01-S10: the contract has a goal and acceptance criteria."""
    del ctx
    contract = getattr(item, "contract", None)
    if contract is None:
        return GuardResult(ok=False, reason="no contract")
    missing = [
        name
        for name, present in (
            ("goal", bool(contract.goal.strip())),
            ("acceptance_criteria", bool(contract.acceptance_criteria)),
        )
        if not present
    ]
    return GuardResult(ok=False, reason=f"missing {', '.join(missing)}") if missing else _OK


@register_guard("dependencies_complete")
def dependencies_complete(item: WorkItem, ctx: TransitionContext) -> GuardResult:
    """Every contract dependency is COMPLETE (``dependency_states``, supplied by the kernel)."""
    contract = getattr(item, "contract", None)
    if contract is None or not contract.dependencies:
        return _OK
    states = ctx.payload.get("dependency_states")
    if states is None:
        return _MISSING
    for dependency in contract.dependencies:
        state = states.get(dependency)
        if state is None:
            return GuardResult(ok=False, reason=f"dependency {dependency} not found")
        if state != WorkItemState.COMPLETE:
            return GuardResult(ok=False, reason=f"dependency {dependency} is {state}")
    return _OK


@register_guard("branch_available")
def branch_available(item: WorkItem, ctx: TransitionContext) -> GuardResult:
    """No other running item uses the work branch (``branch_available``)."""
    del item
    return _flag(ctx, "branch_available")


@register_guard("budget_available")
def budget_available(item: WorkItem, ctx: TransitionContext) -> GuardResult:
    """The scheduler found budget headroom (``budget_ok``)."""
    del item
    return _flag(ctx, "budget_ok")


@register_guard("output_status_is_completed")
def output_status_is_completed(item: WorkItem, ctx: TransitionContext) -> GuardResult:
    """The agent output status is COMPLETED (``output_status``)."""
    del item
    return _output_status(ctx, "COMPLETED")


@register_guard("output_status_is_approved")
def output_status_is_approved(item: WorkItem, ctx: TransitionContext) -> GuardResult:
    """The agent output status is APPROVED (``output_status``)."""
    del item
    return _output_status(ctx, "APPROVED")


@register_guard("has_commit")
def has_commit(item: WorkItem, ctx: TransitionContext) -> GuardResult:
    """The run committed work (``has_commit``)."""
    del item
    return _flag(ctx, "has_commit")


@register_guard("required_evidence_present")
def required_evidence_present(item: WorkItem, ctx: TransitionContext) -> GuardResult:
    """Every ``contract.required_evidence`` kind is in ``evidence_kinds_present``."""
    contract = getattr(item, "contract", None)
    required = [] if contract is None else list(contract.required_evidence)
    if not required:
        return _OK
    present = ctx.payload.get("evidence_kinds_present")
    if present is None:
        return _MISSING
    missing = [kind.value for kind in required if kind.value not in present]
    if missing:
        return GuardResult(ok=False, reason=f"missing evidence {', '.join(missing)}")
    return _OK


@register_guard("handover_present")
def handover_present(item: WorkItem, ctx: TransitionContext) -> GuardResult:
    """The partial run left a handover (``handover_present``)."""
    del item
    return _flag(ctx, "handover_present")


@register_guard("escalations_non_empty")
def escalations_non_empty(item: WorkItem, ctx: TransitionContext) -> GuardResult:
    """The output raised at least one escalation (``escalations_non_empty``)."""
    del item
    return _flag(ctx, "escalations_non_empty")


@register_guard("reviewer_role_differs")
def reviewer_role_differs(item: WorkItem, ctx: TransitionContext) -> GuardResult:
    """``reviewer_role != implementer_role`` (Invariant 4)."""
    del item
    implementer = ctx.payload.get("implementer_role")
    reviewer = ctx.payload.get("reviewer_role")
    if implementer is None or reviewer is None:
        return _MISSING
    if implementer == reviewer:
        return GuardResult(ok=False, reason=f"reviewer role equals implementer role {reviewer}")
    return _OK


@register_guard("reviewer_model_differs_or_disabled")
def reviewer_model_differs_or_disabled(item: WorkItem, ctx: TransitionContext) -> GuardResult:
    """Reviewer model differs from the implementer's, or ``cross_model_review`` is false (§23)."""
    del item
    if ctx.payload.get("cross_model_review") is False:
        return _OK
    implementer = ctx.payload.get("implementer_model_id")
    reviewer = ctx.payload.get("reviewer_model_id")
    if implementer is None or reviewer is None:
        return _MISSING
    if implementer == reviewer:
        return GuardResult(ok=False, reason=f"reviewer model equals implementer model {reviewer}")
    return _OK


@register_guard("ci_green")
def ci_green(item: WorkItem, ctx: TransitionContext) -> GuardResult:
    """The CI pipeline passed (``ci_green``)."""
    del item
    return _flag(ctx, "ci_green")


@register_guard("fix_loops_below_max")
def fix_loops_below_max(item: WorkItem, ctx: TransitionContext) -> GuardResult:
    """``item.fix_loops < max_fix_loops`` (default 3)."""
    limit = _max_fix_loops(ctx)
    if item.fix_loops < limit:
        return _OK
    return GuardResult(ok=False, reason=f"fix_loops {item.fix_loops} >= max_fix_loops {limit}")


@register_guard("fix_loops_at_max")
def fix_loops_at_max(item: WorkItem, ctx: TransitionContext) -> GuardResult:
    """``item.fix_loops >= max_fix_loops`` (default 3)."""
    limit = _max_fix_loops(ctx)
    if item.fix_loops >= limit:
        return _OK
    return GuardResult(ok=False, reason=f"fix_loops {item.fix_loops} < max_fix_loops {limit}")


@register_guard("blocker_resolved")
def blocker_resolved(item: WorkItem, ctx: TransitionContext) -> GuardResult:
    """The blocker was resolved (``blocker_resolved``)."""
    del item
    return _flag(ctx, "blocker_resolved")
