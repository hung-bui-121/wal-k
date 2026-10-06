from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from walk.budgets import Budget, BudgetDimension, BudgetScope, CostCategory
from walk.common.enums import Effort
from walk.common.roles import AgentRole
from walk.model_router import TaskProfile, UsageReport
from walk.orchestrator import KernelStatus, PhaseEvidencePackage, RouteDecision
from walk.runtime import AgentRun, AgentRunState
from walk.workflow import Phase, Risk, WorkItemState

AT = datetime(2026, 1, 1, tzinfo=UTC)


def _profile() -> TaskProfile:
    return TaskProfile(
        required_capabilities=[],
        required_tools=["edit"],
        required_skills=[],
        estimated_context_tokens=0,
        risk=Risk.HIGH,
    )


def test_orchestrator_models_round_trip() -> None:
    route = RouteDecision(
        role=AgentRole.SENIOR_DEV, purpose="IMPLEMENT", profile=_profile(), cross_model_review=True
    )
    run = AgentRun(
        id="RUN-01J0000000000000000000000A",
        project_key="DEMO",
        work_item_id="STORY-0001",
        role=AgentRole.SENIOR_DEV,
        model_id="fake-codex/sim",
        provider="fake-codex",
        effort=Effort.MEDIUM,
        state=AgentRunState.RUNNING,
        purpose="IMPLEMENT",
        kernel_instance="k1",
    )
    status = KernelStatus(
        project_key="DEMO",
        paused=False,
        current_phase=Phase(id="PHASE-01", project_key="DEMO", ordinal=1, name="Prototype"),
        phase_progress={WorkItemState.READY: 2},
        gdd_coverage={},
        active_runs=[run],
        blocked_items=["STORY-0002"],
        pending_approvals=[],
        open_debates=[],
        model_usage={
            "fake-codex/sim": UsageReport(
                input_tokens=10, output_tokens=2, cost_usd=0.1, turns=0, tool_calls=0, duration_s=0
            )
        },
        qc_status={},
        build_status=None,
        budgets=[
            Budget(
                id="PROJECT:DEMO:COST_USD",
                scope=BudgetScope.PROJECT,
                scope_id="DEMO",
                dimension=BudgetDimension.COST_USD,
                limit=100.0,
                updated_at=AT,
            )
        ],
        open_improvement_candidates=0,
    )
    package = PhaseEvidencePackage(
        phase_id="PHASE-01",
        gate_round=1,
        generated_at=AT,
        gdd_coverage={"movement": 0.5},
        stories_completed=["STORY-0001"],
        stories_open=[],
        open_issues=["BUG-0001"],
        known_limitations=["no audio"],
        qc_status="2 passed",
        automated_tests=["EVD-000001"],
        performance_metrics=[],
        playable_build=None,
        gameplay_recordings=[],
        screenshots=[],
        design_review=None,
        technical_review=None,
        risk_summary="low",
        production_cost={CostCategory.LLM: 1.5},
    )

    for model in (route, status, package):
        assert type(model).model_validate_json(model.model_dump_json()) == model
    with pytest.raises(ValidationError):
        route.role = AgentRole.QC  # type: ignore[misc]  # frozen model: the assignment must fail
    with pytest.raises(ValidationError):
        status.paused = True  # type: ignore[misc]  # frozen model: the assignment must fail
    package.qc_status = "3 passed"
    assert package.retrospective_id is None
