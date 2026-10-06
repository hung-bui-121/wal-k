from walk.workflow import Feature, Story, StoryContract, WorkItemState
from walk.workflow.readiness import definition_of_ready_checks

CHECK_NAMES = [
    "requirement_complete",
    "acceptance_criteria",
    "dependencies_resolved",
    "design_approved",
    "assets_available",
    "constraints_known",
]


def _story(item_id: str = "STORY-0001", **contract: object) -> Story:
    fields: dict[str, object] = {
        "goal": "Pick up loot",
        "acceptance_criteria": ["item in bag"],
        "constraints": ["no new dependencies"],
    }
    return Story(
        id=item_id,
        project_key="DEMO",
        title="S",
        contract=StoryContract.model_validate(fields | contract),
    )


def _failing(checks: list[tuple[str, bool, str]]) -> list[str]:
    return [name for name, ok, _ in checks if not ok]


def test_dor_reports_all_failing_checks() -> None:
    dep = _story("STORY-0002").model_copy(update={"state": WorkItemState.QC})
    item = _story(acceptance_criteria=[], dependencies=["STORY-0002", "STORY-0003"])
    checks = definition_of_ready_checks(item, [dep])
    assert [name for name, _, _ in checks] == CHECK_NAMES
    assert _failing(checks) == ["acceptance_criteria", "dependencies_resolved"]
    detail = {name: text for name, _, text in checks}["dependencies_resolved"]
    assert detail == "STORY-0002 is QC; STORY-0003 not found"


def test_dor_passes_when_ready() -> None:
    dep = _story("STORY-0002").model_copy(update={"state": WorkItemState.COMPLETE})
    checks = definition_of_ready_checks(_story(dependencies=["STORY-0002"]), [dep])
    assert all(ok for _, ok, _ in checks)


def test_dor_design_assets_and_constraints() -> None:
    gated = _story(constraints=["design: combat feel review", "asset: sword model"])
    assert _failing(definition_of_ready_checks(gated, [])) == [
        "design_approved",
        "assets_available",
    ]
    facts = {"design_approved": True, "assets_available": True}
    assert _failing(definition_of_ready_checks(gated, [], facts=facts)) == []
    vague = _story(goal=" ", constraints=[], complexity="NORMAL")
    assert _failing(definition_of_ready_checks(vague, [])) == [
        "requirement_complete",
        "constraints_known",
    ]
    small = _story(constraints=[], complexity="SMALL")
    assert _failing(definition_of_ready_checks(small, [])) == []


def test_dor_without_contract_fails() -> None:
    feature = Feature(id="FEAT-0001", project_key="DEMO", title="F")
    assert definition_of_ready_checks(feature, []) == [
        ("requirement_complete", False, "no contract")
    ]
