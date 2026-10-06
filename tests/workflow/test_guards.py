from typing import Any

import pytest

from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.workflow import (
    Bug,
    DoneDimension,
    Feature,
    GuardResult,
    Phase,
    PhaseState,
    Story,
    TransitionContext,
    TransitionSource,
    WorkItem,
)
from walk.workflow.guards import get_guard, register_guard, registered_guards

STORY_GUARDS = {
    "definition_of_ready",
    "dependencies_complete",
    "branch_available",
    "budget_available",
    "output_status_is_completed",
    "output_status_is_approved",
    "has_commit",
    "required_evidence_present",
    "handover_present",
    "escalations_non_empty",
    "reviewer_role_differs",
    "reviewer_model_differs_or_disabled",
    "ci_green",
    "fix_loops_below_max",
    "fix_loops_at_max",
    "blocker_resolved",
}


def _story(**fields: object) -> Story:
    contract = {
        "goal": "g",
        "acceptance_criteria": ["a"],
        "dependencies": ["STORY-0002"],
        "required_evidence": ["AUTOMATED_TEST"],
        "complexity": "SMALL",
    }
    return Story.model_validate(
        {"id": "STORY-0001", "project_key": "DEMO", "title": "S", "contract": contract, **fields}
    )


def _ctx(**payload: object) -> TransitionContext:
    return TransitionContext(
        actor_role=AgentRole.KERNEL, source=TransitionSource.KERNEL, payload=payload
    )


# guard, item, payload that passes, payload that fails
CASES: list[tuple[str, WorkItem, dict[str, Any], dict[str, Any]]] = [
    (
        "definition_of_ready",
        _story(),
        {"definition_of_ready": {"ok": True, "reason": ""}},
        {},
    ),
    (
        "dependencies_complete",
        _story(),
        {"dependency_states": {"STORY-0002": "COMPLETE"}},
        {"dependency_states": {"STORY-0002": "QC"}},
    ),
    ("branch_available", _story(), {"branch_available": True}, {"branch_available": False}),
    ("budget_available", _story(), {"budget_ok": True}, {"budget_ok": False}),
    (
        "output_status_is_completed",
        _story(),
        {"output_status": "COMPLETED"},
        {"output_status": "PARTIAL"},
    ),
    (
        "output_status_is_approved",
        _story(),
        {"output_status": "APPROVED"},
        {"output_status": "REJECTED"},
    ),
    ("has_commit", _story(), {"has_commit": True}, {"has_commit": False}),
    (
        "required_evidence_present",
        _story(),
        {"evidence_kinds_present": ["LOG", "AUTOMATED_TEST"]},
        {"evidence_kinds_present": ["LOG"]},
    ),
    ("handover_present", _story(), {"handover_present": True}, {"handover_present": False}),
    (
        "escalations_non_empty",
        _story(),
        {"escalations_non_empty": True},
        {"escalations_non_empty": False},
    ),
    (
        "reviewer_role_differs",
        _story(),
        {"implementer_role": "SENIOR_DEV", "reviewer_role": "LEAD_DEV"},
        {"implementer_role": "SENIOR_DEV", "reviewer_role": "SENIOR_DEV"},
    ),
    (
        "reviewer_model_differs_or_disabled",
        _story(),
        {
            "implementer_model_id": "codex/a",
            "reviewer_model_id": "claude/b",
            "cross_model_review": True,
        },
        {
            "implementer_model_id": "codex/a",
            "reviewer_model_id": "codex/a",
            "cross_model_review": True,
        },
    ),
    ("ci_green", _story(), {"ci_green": True}, {"ci_green": False}),
    ("fix_loops_below_max", _story(fix_loops=2), {"max_fix_loops": 3}, {"max_fix_loops": 2}),
    ("fix_loops_at_max", _story(fix_loops=3), {}, {"max_fix_loops": 4}),
    ("blocker_resolved", _story(), {"blocker_resolved": True}, {"blocker_resolved": False}),
]


def test_story_guards_are_registered() -> None:
    assert set(registered_guards()) >= STORY_GUARDS
    assert {case[0] for case in CASES} == STORY_GUARDS


@pytest.mark.parametrize(("name", "item", "passing", "failing"), CASES, ids=[c[0] for c in CASES])
def test_payload_guards_evaluate_payload_keys(
    name: str, item: WorkItem, passing: dict[str, Any], failing: dict[str, Any]
) -> None:
    guard = get_guard(name)
    assert guard(item, _ctx(**passing)) == GuardResult(ok=True)
    result = guard(item, _ctx(**failing))
    assert not result.ok
    assert result.reason


@pytest.mark.parametrize(
    "name",
    [
        "branch_available",
        "budget_available",
        "output_status_is_completed",
        "has_commit",
        "required_evidence_present",
        "reviewer_role_differs",
        "reviewer_model_differs_or_disabled",
        "ci_green",
        "blocker_resolved",
        "dependencies_complete",
    ],
)
def test_guards_fail_when_payload_missing(name: str) -> None:
    result = get_guard(name)(_story(), _ctx())
    assert result == GuardResult(ok=False, reason="payload missing")


def test_reviewer_model_guard_respects_disabled_flag() -> None:
    guard = get_guard("reviewer_model_differs_or_disabled")
    same = {"implementer_model_id": "codex/a", "reviewer_model_id": "codex/a"}
    assert guard(_story(), _ctx(**same, cross_model_review=False)).ok
    assert not guard(_story(), _ctx(**same, cross_model_review=True)).ok


def test_guards_without_contract_or_requirements() -> None:
    feature = Feature(id="FEAT-0001", project_key="DEMO", title="F")
    assert not get_guard("definition_of_ready")(feature, _ctx()).ok
    assert get_guard("dependencies_complete")(feature, _ctx()).ok
    assert get_guard("required_evidence_present")(feature, _ctx()).ok
    unknown_dep = _ctx(dependency_states={})
    assert get_guard("dependencies_complete")(_story(), unknown_dep).reason == (
        "dependency STORY-0002 not found"
    )
    assert get_guard("fix_loops_below_max")(_story(fix_loops=3), _ctx()) == GuardResult(
        ok=False, reason="fix_loops 3 >= max_fix_loops 3"
    )


def test_registry_rejects_duplicates_and_unknown_names() -> None:
    with pytest.raises(ConfigError, match="already registered"):
        register_guard("ci_green")(get_guard("ci_green"))
    with pytest.raises(ConfigError, match="unknown guard"):
        get_guard("nope")
    snapshot = registered_guards()
    snapshot.clear()
    assert registered_guards()


def _feature(**fields: object) -> Feature:
    return Feature.model_validate(
        {"id": "FEAT-0001", "project_key": "DEMO", "title": "F", **fields}
    )


def _bug(**fields: object) -> Bug:
    return Bug.model_validate(
        {"id": "BUG-0001", "project_key": "DEMO", "title": "B", "contract": {"goal": "B"}, **fields}
    )


PHASE = Phase(
    id="PHASE-01", project_key="DEMO", ordinal=1, name="Prototype", state=PhaseState.ACTIVE
)
ALL_DONE = dict.fromkeys(_feature().applicable_dimensions, True)

# guard, item, payload that passes, payload that fails (phase is added for in_phase_scope)
FEATURE_BUG_CASES: list[tuple[str, WorkItem, dict[str, Any], dict[str, Any]]] = [
    (
        "in_phase_scope",
        _feature(phase_id="PHASE-01"),
        {"phase_state": "ACTIVE"},
        {"phase_state": "PLANNED"},
    ),
    (
        "has_gdd_refs_or_user_feature",
        _feature(labels=["user-feature"]),
        {},
        {"__item__": _feature()},
    ),
    (
        "technical_design_section_present",
        _feature(),
        {"feature_context_sections": ["Intent", "Architecture"]},
        {"feature_context_sections": ["Intent"]},
    ),
    (
        "required_approved_artifacts_present",
        _feature(),
        {"approved_artifact_ids": []},
        {},
    ),
    (
        "children_created",
        _feature(),
        {"children_states": {"STORY-0001": "READY"}},
        {"children_states": {}},
    ),
    (
        "all_stories_integrated",
        _feature(),
        {"children_states": {"STORY-0001": "QC", "BUG-0001": "COMPLETE"}},
        {"children_states": {"STORY-0001": "QC", "STORY-0002": "IMPLEMENTING"}},
    ),
    ("ci_green_on_integration_branch", _feature(), {"ci_green": True}, {"ci_green": False}),
    (
        "all_applicable_dimensions_done",
        _feature(done_dimensions=ALL_DONE),
        {},
        {"__item__": _feature(done_dimensions={DoneDimension.TESTED: True})},
    ),
    (
        "no_open_blocker_bugs",
        _feature(),
        {"open_blocker_bug_count": 0},
        {"open_blocker_bug_count": 2},
    ),
    (
        "rework_children_created",
        _feature(),
        {"children_states": {"STORY-0001": "COMPLETE", "STORY-0002": "READY"}},
        {"children_states": {"STORY-0001": "COMPLETE"}},
    ),
    (
        "phase_in_evidence_review",
        _feature(),
        {"phase_state": "EVIDENCE_REVIEW"},
        {"phase_state": "ACTIVE"},
    ),
    (
        "has_children_implementing",
        _feature(),
        {"children_states": {"STORY-0001": "IMPLEMENTING"}},
        {"children_states": {"STORY-0001": "READY"}},
    ),
    ("severity_set", _bug(), {"severity_set": True}, {"severity_set": False}),
    ("owner_role_set", _bug(), {"owner_role_set": True}, {"owner_role_set": False}),
    (
        "decision_recorded_quality",
        _bug(),
        {"decision_id": "DEC-0001", "decision_category": "QUALITY"},
        {"decision_id": "DEC-0001", "decision_category": "SCOPE"},
    ),
    (
        "root_cause_section_present",
        _bug(),
        {"feature_context_sections": ["Root Cause", "Fix"]},
        {"feature_context_sections": ["Fix"]},
    ),
    (
        "regression_test_evidence",
        _bug(),
        {"evidence_kinds_present": ["AUTOMATED_TEST"]},
        {"evidence_kinds_present": ["LOG"]},
    ),
    (
        "reproduction_no_longer_reproduces_evidence",
        _bug(),
        {"reproduction_evidence": True},
        {"reproduction_evidence": False},
    ),
    ("reopen_below_max", _bug(reopen_count=1), {"max_reopen": 3}, {"max_reopen": 1}),
    ("reopen_at_max", _bug(reopen_count=3), {}, {"max_reopen": 4}),
]


@pytest.mark.parametrize(
    ("name", "item", "passing", "failing"),
    FEATURE_BUG_CASES,
    ids=[c[0] for c in FEATURE_BUG_CASES],
)
def test_feature_and_bug_guards_evaluate_payload_keys(
    name: str, item: WorkItem, passing: dict[str, Any], failing: dict[str, Any]
) -> None:
    guard = get_guard(name)
    phase_ctx = {"phase": PHASE}
    ctx = TransitionContext(
        actor_role=AgentRole.KERNEL, source=TransitionSource.KERNEL, payload=passing, **phase_ctx
    )
    assert guard(item, ctx) == GuardResult(ok=True)
    failing = dict(failing)
    failing_item = failing.pop("__item__", item)
    ctx = TransitionContext(
        actor_role=AgentRole.KERNEL, source=TransitionSource.KERNEL, payload=failing, **phase_ctx
    )
    result = guard(failing_item, ctx)
    assert not result.ok
    assert result.reason


def test_new_guards_are_registered() -> None:
    assert set(registered_guards()) >= {case[0] for case in FEATURE_BUG_CASES}


def test_all_dimensions_guard_names_missing_dimension() -> None:
    done = dict(ALL_DONE) | {DoneDimension.INTEGRATED: False}
    result = get_guard("all_applicable_dimensions_done")(_feature(done_dimensions=done), _ctx())
    assert result == GuardResult(ok=False, reason="dimensions not done: INTEGRATED")
    assert not get_guard("all_applicable_dimensions_done")(_story(), _ctx()).ok


def test_scope_and_bug_guards_edge_cases() -> None:
    scope = get_guard("in_phase_scope")
    assert scope(_feature(), _ctx()).ok
    assert not scope(_feature(phase_id="PHASE-01"), _ctx(phase_state="ACTIVE")).ok
    assert not get_guard("reopen_below_max")(_story(), _ctx()).ok
    assert get_guard("decision_recorded_quality")(_bug(), _ctx()) == GuardResult(
        ok=False, reason="payload missing"
    )
    assert get_guard("has_gdd_refs_or_user_feature")(
        _feature(gdd_refs=[{"path": "GDD/combat.md"}]), _ctx()
    ).ok
    for name in ("children_created", "no_open_blocker_bugs", "phase_in_evidence_review"):
        assert get_guard(name)(_feature(), _ctx()) == GuardResult(
            ok=False, reason="payload missing"
        )


@pytest.mark.parametrize(
    "name",
    [
        "technical_design_section_present",
        "root_cause_section_present",
        "all_stories_integrated",
        "rework_children_created",
        "has_children_implementing",
        "regression_test_evidence",
        "required_approved_artifacts_present",
        "severity_set",
    ],
)
def test_new_guards_fail_when_payload_missing(name: str) -> None:
    assert get_guard(name)(_feature(), _ctx()) == GuardResult(ok=False, reason="payload missing")


def test_children_guards_with_no_children() -> None:
    result = get_guard("all_stories_integrated")(_feature(), _ctx(children_states={}))
    assert result == GuardResult(ok=False, reason="no children")
    assert not get_guard("reopen_at_max")(_story(), _ctx()).ok
