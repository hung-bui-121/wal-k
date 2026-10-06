from typing import Any

import pytest

from walk.common.errors import GuardRejected, PermissionDenied
from walk.common.roles import AgentRole
from walk.workflow import (
    TABLES_DIR,
    StateMachine,
    Story,
    StoryContract,
    TableLoader,
    TransitionContext,
    TransitionSource,
    UnknownTransition,
    WorkItemKind,
    WorkItemState,
)

ALL_FACTS: dict[str, Any] = {
    "dependency_states": {},
    "branch_available": True,
    "budget_ok": True,
}


@pytest.fixture(scope="module")
def machine() -> StateMachine:
    table = TableLoader().load(TABLES_DIR / "story_workflow.yaml")
    return StateMachine({WorkItemKind.STORY: table, WorkItemKind.TASK: table})


def _story(state: WorkItemState, **fields: object) -> Story:
    return Story.model_validate(
        {
            "id": "STORY-0001",
            "project_key": "DEMO",
            "title": "S",
            "state": state,
            "contract": StoryContract(goal="g", acceptance_criteria=["a"]),
            **fields,
        }
    )


def _ctx(role: AgentRole = AgentRole.KERNEL, **payload: object) -> TransitionContext:
    return TransitionContext(actor_role=role, source=TransitionSource.KERNEL, payload=payload)


def test_transition_for_selects_matching_row(machine: StateMachine) -> None:
    item = _story(WorkItemState.READY)
    row = machine.transition_for(
        WorkItemKind.STORY, item.state, "start_implementation", item, _ctx(**ALL_FACTS)
    )
    assert row.to_state is WorkItemState.IMPLEMENTING
    assert row.guards == ("dependencies_complete", "branch_available", "budget_available")


def test_unknown_transition_raises(machine: StateMachine) -> None:
    item = _story(WorkItemState.IDEA)
    with pytest.raises(UnknownTransition, match="qc_passed") as raised:
        machine.transition_for(WorkItemKind.STORY, item.state, "qc_passed", item, _ctx())
    assert raised.value.detail["state"] == "IDEA"
    with pytest.raises(UnknownTransition):
        machine.transition_for(WorkItemKind.EPIC, item.state, "ready", item, _ctx())


def test_guard_order_selects_second_row(machine: StateMachine) -> None:
    item = _story(WorkItemState.QC, fix_loops=3)
    ctx = _ctx(AgentRole.QC, max_fix_loops=3)
    row = machine.transition_for(WorkItemKind.STORY, item.state, "qc_rejected", item, ctx)
    assert row.to_state is WorkItemState.BLOCKED
    below = _story(WorkItemState.QC, fix_loops=1)
    first = machine.transition_for(WorkItemKind.STORY, below.state, "qc_rejected", below, ctx)
    assert first.to_state is WorkItemState.REWORK


def test_guard_rejection_lists_failing_guards(machine: StateMachine) -> None:
    item = _story(WorkItemState.READY)
    ctx = _ctx(dependency_states={}, branch_available=False)
    with pytest.raises(GuardRejected) as raised:
        machine.transition_for(WorkItemKind.STORY, item.state, "start_implementation", item, ctx)
    failures = raised.value.detail["failed_guards"]
    assert failures == [
        {"guard": "branch_available", "reason": "branch_available is false"},
        {"guard": "budget_available", "reason": "payload missing"},
    ]
    assert "branch_available: branch_available is false" in raised.value.message


def test_role_not_allowed_raises_permission_denied(machine: StateMachine) -> None:
    item = _story(WorkItemState.LEAD_DEV_REVIEW)
    ctx = _ctx(AgentRole.SENIOR_DEV, output_status="APPROVED")
    with pytest.raises(PermissionDenied) as raised:
        machine.transition_for(WorkItemKind.STORY, item.state, "review_approved", item, ctx)
    assert raised.value.detail["actor_role"] == "SENIOR_DEV"
    assert raised.value.detail["allowed_roles"] == ["LEAD_DEV"]


def test_user_may_raise_any_event_but_guards_apply(machine: StateMachine) -> None:
    item = _story(WorkItemState.IDEA)
    row = machine.transition_for(
        WorkItemKind.STORY, item.state, "ready", item, _ctx(AgentRole.USER)
    )
    assert row.to_state is WorkItemState.READY
    empty = _story(WorkItemState.IDEA, contract=StoryContract(goal=""))
    with pytest.raises(GuardRejected):
        machine.transition_for(
            WorkItemKind.STORY, empty.state, "ready", empty, _ctx(AgentRole.USER)
        )


def test_wildcard_except_excludes_states(machine: StateMachine) -> None:
    done = _story(WorkItemState.COMPLETE)
    with pytest.raises(UnknownTransition):
        machine.transition_for(WorkItemKind.STORY, done.state, "cancel", done, _ctx(AgentRole.USER))
    for state in (WorkItemState.IDEA, WorkItemState.QC, WorkItemState.BLOCKED):
        item = _story(state)
        row = machine.transition_for(
            WorkItemKind.STORY, state, "cancel", item, _ctx(AgentRole.USER)
        )
        assert row.to_state is WorkItemState.CANCELLED


def test_resolve_target_previous_uses_resume_state(machine: StateMachine) -> None:
    item = _story(WorkItemState.BLOCKED)
    ctx = _ctx(AgentRole.USER, blocker_resolved=True, resume_state="QC")
    row = machine.transition_for(WorkItemKind.STORY, item.state, "unblock", item, ctx)
    assert machine.resolve_target(row, item, ctx) is WorkItemState.QC
    for payload in ({}, {"resume_state": "NOWHERE"}):
        with pytest.raises(GuardRejected, match="no resume_state"):
            machine.resolve_target(row, item, _ctx(AgentRole.USER, **payload))
    ready = machine.transition_for(
        WorkItemKind.STORY, WorkItemState.IDEA, "ready", _story(WorkItemState.IDEA), ctx
    )
    assert machine.resolve_target(ready, item, ctx) is WorkItemState.READY
