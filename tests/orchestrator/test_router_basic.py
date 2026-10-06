from pathlib import Path

import pytest

from tests.orchestrator.conftest import SCHEDULED_STATES, KernelFactory
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.orchestrator import DefaultTaskRouter, NoScheduledRole
from walk.telemetry import EvidenceKind
from walk.workflow import Feature, Risk, Story, StoryContract, Task, WorkItemState


def _story(number: int, **fields: object) -> Story:
    data: dict[str, object] = {
        "id": f"STORY-{number:04d}",
        "project_key": "DEMO",
        "title": f"Story {number}",
        "contract": StoryContract(goal="g"),
        **fields,
    }
    return Story.model_validate(data)


async def test_route_literal_and_contract_roles(make_kernel: KernelFactory) -> None:
    router = (await make_kernel()).router
    contract = StoryContract(
        goal="g",
        owner_role=AgentRole.SENIOR_DEV,
        reviewer_role=AgentRole.LEAD_DEV,
        required_skills=["git-hygiene"],
        required_evidence=[EvidenceKind.AUTOMATED_TEST],
    )
    story = _story(1, contract=contract, risk=Risk.HIGH)
    feature = Feature(id="FEAT-0001", project_key="DEMO", title="Movement")

    implement = router.route(story, WorkItemState.READY)
    review = router.route(story, WorkItemState.READY_FOR_REVIEW)
    plan = router.route(feature, WorkItemState.IDEA)

    assert (implement.role, implement.purpose) == (AgentRole.SENIOR_DEV, "IMPLEMENT")
    assert (review.role, review.purpose) == (AgentRole.LEAD_DEV, "REVIEW")
    assert (plan.role, plan.purpose) == (AgentRole.ORCHESTRATOR, "PLAN")
    assert implement.profile.required_skills == ["git-hygiene"]
    assert implement.profile.risk is Risk.HIGH
    assert "edit" in implement.profile.required_tools
    assert implement.profile.estimated_context_tokens == 0
    assert implement.profile.implementer_model_id is None
    assert implement.cross_model_review is True
    assert plan.profile.required_skills == []


async def test_route_uses_fallback_role(make_kernel: KernelFactory) -> None:
    router = (await make_kernel()).router
    feature = Feature(id="FEAT-0001", project_key="DEMO", title="Movement")

    decision = router.route(feature, WorkItemState.DISCOVERY)

    assert decision.role is AgentRole.ORCHESTRATOR
    assert decision.purpose == "DESIGN"


async def test_route_unknown_state_raises(make_kernel: KernelFactory) -> None:
    router = (await make_kernel()).router

    with pytest.raises(NoScheduledRole, match="STORY in COMPLETE"):
        router.route(_story(1), WorkItemState.COMPLETE)


async def test_can_run_parallel_basic_rules(make_kernel: KernelFactory) -> None:
    router = (await make_kernel()).router
    base = _story(1)
    dependent = _story(2, contract=StoryContract(goal="g", dependencies=["STORY-0001"]))
    same_branch_a = _story(3, branch="feat/shared")
    same_branch_b = Task(
        id="TASK-0004",
        project_key="DEMO",
        title="t",
        contract=StoryContract(goal="g"),
        branch="feat/shared",
    )
    unrelated = _story(5)

    assert router.can_run_parallel(base, dependent) is False
    assert router.can_run_parallel(dependent, base) is False
    assert router.can_run_parallel(same_branch_a, same_branch_b) is False
    assert router.can_run_parallel(same_branch_b, same_branch_a) is False
    assert router.can_run_parallel(base, base) is False
    assert router.can_run_parallel(base, unrelated) is True
    assert router.can_run_parallel(unrelated, same_branch_a) is True


async def test_router_rejects_invalid_rows(make_kernel: KernelFactory, tmp_path: Path) -> None:
    kernel = await make_kernel()
    env = kernel.env
    bad = tmp_path / "states.yaml"
    bad.write_text("- {kind: STORY, state: READY, role: WIZARD, purpose: IMPLEMENT}\n", "utf-8")

    with pytest.raises(ConfigError, match=r"invalid states.yaml"):
        DefaultTaskRouter(bad, env.agents, env.runs, env.workflow)
    with pytest.raises(ConfigError, match=r"invalid missing.yaml"):
        DefaultTaskRouter(tmp_path / "missing.yaml", env.agents, env.runs, env.workflow)
    assert SCHEDULED_STATES.is_file()


async def test_contract_roles_default_without_contract(
    make_kernel: KernelFactory, tmp_path: Path
) -> None:
    kernel = await make_kernel()
    env = kernel.env
    rows = tmp_path / "states.yaml"
    rows.write_text(
        "- {kind: FEATURE, state: IDEA, role: contract.owner_role, purpose: PLAN}\n"
        "- {kind: FEATURE, state: QC, role: contract.reviewer_role, purpose: QC}\n",
        "utf-8",
    )
    router = DefaultTaskRouter(rows, env.agents, env.runs, env.workflow)
    feature = Feature(id="FEAT-0001", project_key="DEMO", title="Movement")

    assert router.route(feature, WorkItemState.IDEA).role is AgentRole.SENIOR_DEV
    assert router.route(feature, WorkItemState.QC).role is AgentRole.LEAD_DEV
