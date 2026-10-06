"""§58 Definition of Ready checks (pure)."""

from collections.abc import Mapping
from typing import Final

from walk.workflow.models import WorkItem, WorkItemState

_DESIGN_PREFIX: Final = "design:"  # a constraint "design: <what>" requires an approved design
_ASSET_PREFIX: Final = "asset:"  # a constraint "asset: <what>" requires available assets
_SELF_EXPLANATORY: Final = frozenset({"TRIVIAL", "SMALL"})


def definition_of_ready_checks(
    item: WorkItem, deps: list[WorkItem], *, facts: Mapping[str, object] | None = None
) -> list[tuple[str, bool, str]]:
    """Evaluate the §58 checks for ``item``.

    Checks, in order: ``requirement_complete`` (goal non-empty), ``acceptance_criteria``
    (non-empty), ``dependencies_resolved`` (every contract dependency is in ``deps`` and
    COMPLETE), ``design_approved`` (no ``design:`` constraint, or ``facts["design_approved"]``),
    ``assets_available`` (no ``asset:`` constraint, or ``facts["assets_available"]``) and
    ``constraints_known`` (constraints listed, or complexity TRIVIAL/SMALL). An item without a
    contract fails ``requirement_complete`` only (feature checks: E03-S17).

    Args:
        item: The work item to check.
        deps: The items named in ``item.contract.dependencies`` (missing ones fail).
        facts: Caller facts, e.g. a transition payload with the approval flags.

    Returns:
        ``(check name, passed, detail)`` per check; ``detail`` explains a failure and is
        empty for a passing check.
    """
    contract = getattr(item, "contract", None)
    if contract is None:
        return [("requirement_complete", False, "no contract")]
    flags = facts or {}
    by_id = {dep.id: dep for dep in deps}
    unresolved = []
    for dependency in contract.dependencies:
        dep = by_id.get(dependency)
        if dep is None:
            unresolved.append(f"{dependency} not found")
        elif dep.state is not WorkItemState.COMPLETE:
            unresolved.append(f"{dependency} is {dep.state.value}")
    constraints = [c.strip().lower() for c in contract.constraints]
    needs_design = any(c.startswith(_DESIGN_PREFIX) for c in constraints)
    needs_assets = any(c.startswith(_ASSET_PREFIX) for c in constraints)
    checks = [
        ("requirement_complete", bool(contract.goal.strip()), "goal is empty"),
        ("acceptance_criteria", bool(contract.acceptance_criteria), "no acceptance criteria"),
        ("dependencies_resolved", not unresolved, "; ".join(unresolved)),
        (
            "design_approved",
            not needs_design or flags.get("design_approved") is True,
            "design approval missing",
        ),
        (
            "assets_available",
            not needs_assets or flags.get("assets_available") is True,
            "required assets not available",
        ),
        (
            "constraints_known",
            bool(contract.constraints) or contract.complexity in _SELF_EXPLANATORY,
            "no constraints listed",
        ),
    ]
    return [(name, ok, "" if ok else detail) for name, ok, detail in checks]
