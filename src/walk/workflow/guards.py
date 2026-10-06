"""Guard registry and the guards of ``story_workflow`` (INTERFACES §3, WBS §3.4).

Guards are pure predicates over the work item and the facts the caller put in
`TransitionContext.payload` under the fixed WBS §3.4 keys. The kernel adds the facts it owns
(``dependency_states``, ``resume_state``) before evaluating them. The registry is filled once,
at import time, by the ``@register_guard`` decorators in this module.
"""

from collections.abc import Callable
from typing import Final

from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.workflow.models import (
    Bug,
    Feature,
    GuardResult,
    GuardSubject,
    Phase,
    ReleaseCandidate,
    TransitionContext,
    WorkItem,
    WorkItemState,
)
from walk.workflow.protocols import Guard
from walk.workflow.readiness import definition_of_ready_checks

_REGISTRY: dict[str, Guard] = {}
_OK: Final = GuardResult(ok=True)
_MISSING: Final = GuardResult(ok=False, reason="payload missing")
_DEFAULT_MAX_FIX_LOOPS: Final = 3  # WBS §3.4: RuntimePolicy / project config default
_DEFAULT_MAX_REOPEN: Final = 3  # WBS §3.4: RuntimePolicy / project config default
_USER_FEATURE_LABEL: Final = "user-feature"  # set by `walk feature add` (E03-S09)
_TECHNICAL_DESIGN_SECTION: Final = "Architecture"  # FeatureContext section (E03-S09)
_ROOT_CAUSE_SECTION: Final = "Root Cause"  # BugContext section (§38)
_INTEGRATED: Final = frozenset(
    {WorkItemState.INTEGRATION, WorkItemState.QC, WorkItemState.COMPLETE}
)
_SCOPE_TERMINAL: Final = frozenset(
    {WorkItemState.COMPLETE, WorkItemState.CANCELLED, WorkItemState.BLOCKED}
)
_REWORK_STARTED: Final = frozenset(
    {WorkItemState.READY, WorkItemState.IMPLEMENTING, WorkItemState.REWORK}
)


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


def _readiness_result(checks: list[tuple[str, bool, str]]) -> GuardResult:
    """Fold `definition_of_ready_checks` output into a result naming the failing checks."""
    failing = [name for name, ok, _ in checks if not ok]
    return GuardResult(ok=not failing, reason=", ".join(failing))


def _work_item(item: GuardSubject) -> WorkItem | None:
    """Return ``item`` when it is a work item (not a phase or release candidate)."""
    return None if isinstance(item, Phase | ReleaseCandidate) else item


def _not_applicable(item: GuardSubject, what: str) -> GuardResult:
    if isinstance(item, Phase):
        label = "PHASE"
    elif isinstance(item, ReleaseCandidate):
        label = "RC"
    else:
        label = item.kind.value
    return GuardResult(ok=False, reason=f"{label} has no {what}")


def _children(ctx: TransitionContext) -> dict[str, str] | None:
    states = ctx.payload.get("children_states")
    return None if states is None else dict(states)


def _section(ctx: TransitionContext, section: str) -> GuardResult:
    sections = ctx.payload.get("feature_context_sections")
    if sections is None:
        return _MISSING
    return _OK if section in sections else GuardResult(ok=False, reason=f"no {section} section")


def _max_fix_loops(ctx: TransitionContext) -> int:
    return int(ctx.payload.get("max_fix_loops", _DEFAULT_MAX_FIX_LOOPS))


@register_guard("definition_of_ready")
def definition_of_ready(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """§58 checks (`definition_of_ready_checks`).

    `WorkflowManager.raise_event` supplies its own verdict (``definition_of_ready``, with the
    dependencies read from the database). Without it, dependencies count as unresolved.
    """
    verdict = ctx.payload.get("definition_of_ready")
    if isinstance(verdict, dict):
        return GuardResult.model_validate(verdict)
    work_item = _work_item(item)
    if work_item is None:
        return _not_applicable(item, "contract")
    return _readiness_result(definition_of_ready_checks(work_item, [], facts=ctx.payload))


@register_guard("dependencies_complete")
def dependencies_complete(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
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
def branch_available(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """No other running item uses the work branch (``branch_available``)."""
    del item
    return _flag(ctx, "branch_available")


@register_guard("budget_available")
def budget_available(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The scheduler found budget headroom (``budget_ok``)."""
    del item
    return _flag(ctx, "budget_ok")


@register_guard("output_status_is_completed")
def output_status_is_completed(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The agent output status is COMPLETED (``output_status``)."""
    del item
    return _output_status(ctx, "COMPLETED")


@register_guard("output_status_is_approved")
def output_status_is_approved(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The agent output status is APPROVED (``output_status``)."""
    del item
    return _output_status(ctx, "APPROVED")


@register_guard("has_commit")
def has_commit(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The run committed work (``has_commit``)."""
    del item
    return _flag(ctx, "has_commit")


@register_guard("required_evidence_present")
def required_evidence_present(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
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
def handover_present(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The partial run left a handover (``handover_present``)."""
    del item
    return _flag(ctx, "handover_present")


@register_guard("escalations_non_empty")
def escalations_non_empty(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The output raised at least one escalation (``escalations_non_empty``)."""
    del item
    return _flag(ctx, "escalations_non_empty")


@register_guard("reviewer_role_differs")
def reviewer_role_differs(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
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
def reviewer_model_differs_or_disabled(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
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
def ci_green(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The CI pipeline passed (``ci_green``)."""
    del item
    return _flag(ctx, "ci_green")


@register_guard("fix_loops_below_max")
def fix_loops_below_max(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """``item.fix_loops < max_fix_loops`` (default 3)."""
    work_item = _work_item(item)
    if work_item is None:
        return _not_applicable(item, "fix loops")
    limit = _max_fix_loops(ctx)
    if work_item.fix_loops < limit:
        return _OK
    loops = work_item.fix_loops
    return GuardResult(ok=False, reason=f"fix_loops {loops} >= max_fix_loops {limit}")


@register_guard("fix_loops_at_max")
def fix_loops_at_max(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """``item.fix_loops >= max_fix_loops`` (default 3)."""
    work_item = _work_item(item)
    if work_item is None:
        return _not_applicable(item, "fix loops")
    limit = _max_fix_loops(ctx)
    if work_item.fix_loops >= limit:
        return _OK
    loops = work_item.fix_loops
    return GuardResult(ok=False, reason=f"fix_loops {loops} < max_fix_loops {limit}")


@register_guard("blocker_resolved")
def blocker_resolved(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The blocker was resolved (``blocker_resolved``)."""
    del item
    return _flag(ctx, "blocker_resolved")


@register_guard("in_phase_scope")
def in_phase_scope(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """Placeholder until E06-S07: phase-less items, or items of the ACTIVE phase in ``ctx``."""
    work_item = _work_item(item)
    if work_item is None:
        return _not_applicable(item, "phase scope")
    if work_item.phase_id is None:
        return _OK
    if ctx.phase is None or ctx.phase.id != work_item.phase_id:
        return GuardResult(ok=False, reason=f"{work_item.id} is not in the current phase")
    if ctx.payload.get("phase_state") != "ACTIVE":
        return GuardResult(ok=False, reason=f"phase {work_item.phase_id} is not ACTIVE")
    return _OK


@register_guard("has_gdd_refs_or_user_feature")
def has_gdd_refs_or_user_feature(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The feature cites the GDD, or the user entered it (label ``user-feature``)."""
    del ctx
    if getattr(item, "gdd_refs", None) or _USER_FEATURE_LABEL in getattr(item, "labels", ()):
        return _OK
    return GuardResult(ok=False, reason="no GDD reference and not a user feature")


@register_guard("technical_design_section_present")
def technical_design_section_present(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The feature context has an ``Architecture`` section (``feature_context_sections``)."""
    del item
    return _section(ctx, _TECHNICAL_DESIGN_SECTION)


@register_guard("required_approved_artifacts_present")
def required_approved_artifacts_present(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The approved-artifact facts were gathered (``approved_artifact_ids``).

    No artifact is required in E01; the guard checks that the caller looked them up.
    """
    del item
    return _MISSING if ctx.payload.get("approved_artifact_ids") is None else _OK


@register_guard("children_created")
def children_created(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The feature has at least one child (``children_states``)."""
    del item
    children = _children(ctx)
    if children is None:
        return _MISSING
    return _OK if children else GuardResult(ok=False, reason="no children")


@register_guard("all_stories_integrated")
def all_stories_integrated(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """Every child is in INTEGRATION, QC or COMPLETE (``children_states``)."""
    del item
    children = _children(ctx)
    if children is None:
        return _MISSING
    if not children:
        return GuardResult(ok=False, reason="no children")
    pending = sorted(key for key, state in children.items() if state not in _INTEGRATED)
    if pending:
        return GuardResult(ok=False, reason=f"not integrated: {', '.join(pending)}")
    return _OK


@register_guard("ci_green_on_integration_branch")
def ci_green_on_integration_branch(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """CI passed on the feature integration branch (``ci_green``)."""
    del item
    return _flag(ctx, "ci_green")


@register_guard("all_applicable_dimensions_done")
def all_applicable_dimensions_done(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """Every ``applicable_dimensions`` entry is True in ``done_dimensions`` (§6.5)."""
    del ctx
    if not isinstance(item, Feature):
        return _not_applicable(item, "done dimensions")
    missing = [d.value for d in item.applicable_dimensions if not item.done_dimensions.get(d)]
    if missing:
        return GuardResult(ok=False, reason=f"dimensions not done: {', '.join(missing)}")
    return _OK


@register_guard("no_open_blocker_bugs")
def no_open_blocker_bugs(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """No BLOCKER bug of the feature is open (``open_blocker_bug_count``)."""
    del item
    count = ctx.payload.get("open_blocker_bug_count")
    if count is None:
        return _MISSING
    return _OK if count == 0 else GuardResult(ok=False, reason=f"{count} open blocker bug(s)")


@register_guard("rework_children_created")
def rework_children_created(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """At least one child is in READY, IMPLEMENTING or REWORK (``children_states``)."""
    del item
    children = _children(ctx)
    if children is None:
        return _MISSING
    if any(state in _REWORK_STARTED for state in children.values()):
        return _OK
    return GuardResult(ok=False, reason="no rework child created")


@register_guard("phase_in_evidence_review")
def phase_in_evidence_review(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The phase is in EVIDENCE_REVIEW (``phase_state``)."""
    del item
    state = ctx.payload.get("phase_state")
    if state is None:
        return _MISSING
    if state == "EVIDENCE_REVIEW":
        return _OK
    return GuardResult(ok=False, reason=f"phase is {state}")


@register_guard("has_children_implementing")
def has_children_implementing(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """At least one child is IMPLEMENTING (``children_states``)."""
    del item
    children = _children(ctx)
    if children is None:
        return _MISSING
    if any(state == WorkItemState.IMPLEMENTING for state in children.values()):
        return _OK
    return GuardResult(ok=False, reason="no child is IMPLEMENTING")


@register_guard("severity_set")
def severity_set(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """Triage confirmed the severity (``severity_set``)."""
    del item
    return _flag(ctx, "severity_set")


@register_guard("owner_role_set")
def owner_role_set(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """Triage assigned an owner role (``owner_role_set``)."""
    del item
    return _flag(ctx, "owner_role_set")


@register_guard("decision_recorded_quality")
def decision_recorded_quality(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """A QUALITY decision backs the change (``decision_id`` + ``decision_category``)."""
    del item
    if ctx.payload.get("decision_id") is None:
        return _MISSING
    category = ctx.payload.get("decision_category")
    if category == "QUALITY":
        return _OK
    return GuardResult(ok=False, reason=f"decision category is {category}, expected QUALITY")


@register_guard("root_cause_section_present")
def root_cause_section_present(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The bug context has a ``Root Cause`` section (``feature_context_sections``)."""
    del item
    return _section(ctx, _ROOT_CAUSE_SECTION)


@register_guard("regression_test_evidence")
def regression_test_evidence(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """An AUTOMATED_TEST was recorded (``evidence_kinds_present``)."""
    del item
    present = ctx.payload.get("evidence_kinds_present")
    if present is None:
        return _MISSING
    return _OK if "AUTOMATED_TEST" in present else GuardResult(ok=False, reason="no AUTOMATED_TEST")


@register_guard("reproduction_no_longer_reproduces_evidence")
def reproduction_no_longer_reproduces_evidence(
    item: GuardSubject, ctx: TransitionContext
) -> GuardResult:
    """QC proved the reproduction no longer reproduces (``reproduction_evidence``)."""
    del item
    return _flag(ctx, "reproduction_evidence")


def _max_reopen(ctx: TransitionContext) -> int:
    return int(ctx.payload.get("max_reopen", _DEFAULT_MAX_REOPEN))


@register_guard("reopen_below_max")
def reopen_below_max(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """``bug.reopen_count < max_reopen`` (default 3)."""
    if not isinstance(item, Bug):
        return _not_applicable(item, "reopen count")
    limit = _max_reopen(ctx)
    if item.reopen_count < limit:
        return _OK
    return GuardResult(ok=False, reason=f"reopen_count {item.reopen_count} >= max_reopen {limit}")


@register_guard("reopen_at_max")
def reopen_at_max(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """``bug.reopen_count >= max_reopen`` (default 3)."""
    if not isinstance(item, Bug):
        return _not_applicable(item, "reopen count")
    limit = _max_reopen(ctx)
    if item.reopen_count >= limit:
        return _OK
    return GuardResult(ok=False, reason=f"reopen_count {item.reopen_count} < max_reopen {limit}")


# --- phase lifecycle (INTERFACES §3.4); kernel facts come from WorkflowManager.phase_event ---


@register_guard("previous_phase_complete_or_first")
def previous_phase_complete_or_first(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The previous phase is COMPLETE, or there is none (``previous_phase_state``, kernel)."""
    del item
    if "previous_phase_state" not in ctx.payload:
        return _MISSING
    state = ctx.payload["previous_phase_state"]
    if state is None or state == "COMPLETE":
        return _OK
    return GuardResult(ok=False, reason=f"previous phase is {state}")


@register_guard("scope_non_empty")
def scope_non_empty(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The phase has an approved epic scope (§67)."""
    del ctx
    if not isinstance(item, Phase):
        return _not_applicable(item, "scope")
    return _OK if item.scope_epic_ids else GuardResult(ok=False, reason="no scope epics")


@register_guard("kit_validated")
def kit_validated(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The Production Kit is valid (``kit_validated``; True until E02-S03 supplies it)."""
    del item
    if ctx.payload.get("kit_validated", True) is True:
        return _OK
    return GuardResult(ok=False, reason="kit_validated is false")


@register_guard("all_scope_features_terminal")
def all_scope_features_terminal(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """Every feature of the phase is COMPLETE, CANCELLED or BLOCKED (``scope_feature_states``)."""
    del item
    states = ctx.payload.get("scope_feature_states")
    if states is None:
        return _MISSING
    open_ids = sorted(key for key, state in states.items() if state not in _SCOPE_TERMINAL)
    if open_ids:
        return GuardResult(ok=False, reason=f"features still open: {', '.join(open_ids)}")
    return _OK


@register_guard("evidence_package_written")
def evidence_package_written(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The §69 evidence package exists (``evidence_package_written``)."""
    del item
    return _flag(ctx, "evidence_package_written")


@register_guard("retrospective_written")
def retrospective_written(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The phase retrospective exists (``retrospective_written``)."""
    del item
    return _flag(ctx, "retrospective_written")


@register_guard("feedback_non_empty")
def feedback_non_empty(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The gate decision carries user feedback (``feedback``)."""
    del item
    feedback = ctx.payload.get("feedback")
    if isinstance(feedback, str) and feedback.strip():
        return _OK
    return GuardResult(ok=False, reason="feedback is empty")


@register_guard("rework_work_items_created")
def rework_work_items_created(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """§71 rework was decomposed into work items (``rework_work_items_created``)."""
    del item
    return _flag(ctx, "rework_work_items_created")


@register_guard("impact_analysis_evidence_present")
def impact_analysis_evidence_present(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The §72 impact analysis exists (``impact_analysis_evidence_present``)."""
    del item
    return _flag(ctx, "impact_analysis_evidence_present")


@register_guard("approval_user")
def approval_user(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The user acts, or an approved request backs the actor (``approval_id``)."""
    del item
    if ctx.actor_role is AgentRole.USER or ctx.payload.get("approval_id"):
        return _OK
    return GuardResult(ok=False, reason="user approval missing")


# --- release-candidate lifecycle (INTERFACES §3.6); kernel facts from WorkflowManager.rc_event --


@register_guard("build_evidence_present")
def build_evidence_present(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The candidate has build evidence (``build_evidence_ids``)."""
    del item
    evidence = ctx.payload.get("build_evidence_ids")
    if evidence is None:
        return _MISSING
    return _OK if evidence else GuardResult(ok=False, reason="no build evidence")


@register_guard("qc_report_evidence")
def qc_report_evidence(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The candidate has a QC report (``qc_report_evidence_id``)."""
    del item
    if ctx.payload.get("qc_report_evidence_id"):
        return _OK
    return GuardResult(ok=False, reason="no QC report evidence")


@register_guard("rejection_bugs_created")
def rejection_bugs_created(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """The rejection is backed by bugs (``rejection_bug_ids``)."""
    del item
    if ctx.payload.get("rejection_bug_ids"):
        return _OK
    return GuardResult(ok=False, reason="no rejection bugs")


@register_guard("rejection_bugs_complete")
def rejection_bugs_complete(item: GuardSubject, ctx: TransitionContext) -> GuardResult:
    """Every rejection bug is COMPLETE (``rejection_bug_states``)."""
    del item
    states = ctx.payload.get("rejection_bug_states")
    if states is None:
        return _MISSING
    open_ids = sorted(key for key, state in states.items() if state != WorkItemState.COMPLETE)
    if open_ids:
        return GuardResult(ok=False, reason=f"bugs not complete: {', '.join(open_ids)}")
    return _OK
