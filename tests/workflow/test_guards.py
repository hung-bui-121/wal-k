from typing import Any

import pytest

from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.workflow import (
    Feature,
    GuardResult,
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
    ("definition_of_ready", _story(), {}, {}),
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
    if name == "definition_of_ready":
        item = _story(contract={"goal": "g", "acceptance_criteria": []})
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
