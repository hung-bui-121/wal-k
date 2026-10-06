import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from walk.common.roles import AgentRole
from walk.hooks import HookName
from walk.workflow import (
    Bug,
    Feature,
    Project,
    Story,
    StoryContract,
    Transition,
    TransitionContext,
    TransitionSource,
    WorkItem,
    WorkItemKind,
    WorkItemState,
)

ADR_0010 = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "01-architecture"
    / "adr"
    / "ADR-0010-unified-work-item-state-enum.md"
)
T0 = datetime(2026, 1, 1, tzinfo=UTC)


def test_work_item_state_matches_adr_0010() -> None:
    text = ADR_0010.read_text(encoding="utf-8")
    d1 = text[text.index("**D-1") : text.index("**D-2")]
    match = re.search(r"values: `([A-Z_, ]+)`", d1)
    assert match is not None
    documented = match.group(1).split(", ")
    assert len(documented) == 15
    assert [state.value for state in WorkItemState] == documented


def test_work_item_union_discriminates_on_kind() -> None:
    bug = Bug(
        id="BUG-0001",
        project_key="DEMO",
        title="Crash on load",
        contract=StoryContract(goal="Crash on load"),
        created_at=T0,
        updated_at=T0,
    )
    adapter: TypeAdapter[WorkItem] = TypeAdapter(WorkItem)
    restored = adapter.validate_json(bug.model_dump_json())
    assert isinstance(restored, Bug)
    assert restored == bug
    feature = adapter.validate_python(
        {"id": "FEAT-0001", "kind": "FEATURE", "project_key": "DEMO", "title": "F"}
    )
    assert isinstance(feature, Feature)


def test_work_item_rejects_mismatched_kind() -> None:
    with pytest.raises(ValidationError):
        Story.model_validate(
            {
                "id": "STORY-0001",
                "kind": "BUG",
                "project_key": "DEMO",
                "title": "x",
                "contract": {"goal": "g"},
            }
        )


def test_feature_defaults_and_project_defaults() -> None:
    feature = Feature(id="FEAT-0001", project_key="DEMO", title="F")
    assert feature.kind is WorkItemKind.FEATURE
    assert feature.state is WorkItemState.IDEA
    assert feature.state_version == 0
    assert len(feature.applicable_dimensions) == 4
    project = Project(key="DEMO", name="Demo", repo_path="/repo")
    assert project.protected_branches == ["main", "release/*"]
    with pytest.raises(ValidationError):
        Project(key="DEMO", name="Demo", repo_path="/repo", autonomy_level_max=4)


def test_transition_value_objects() -> None:
    ctx = TransitionContext(actor_role=AgentRole.USER, source=TransitionSource.USER)
    assert ctx.run_id is None
    assert ctx.payload == {}
    assert ctx.phase is None
    row = Transition(
        from_state=WorkItemState.READY,
        event="start_implementation",
        to_state=WorkItemState.IMPLEMENTING,
        guards=("budget_available",),
        allowed_roles=(AgentRole.KERNEL,),
        hooks=(HookName.ON_TASK_START,),
    )
    assert row.hooks == (HookName.ON_TASK_START,)
