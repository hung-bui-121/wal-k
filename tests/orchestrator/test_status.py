import pytest

from tests.orchestrator.conftest import KernelFactory
from tests.runtime.conftest import make_run
from walk.budgets import BudgetDimension, BudgetScope
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.model_router import UsageReport
from walk.orchestrator import StatusBuilder
from walk.permissions import ApprovalRequest
from walk.persistence import UnitOfWork
from walk.runtime import AgentRunState
from walk.telemetry import LedgerEvent, LedgerEventKind
from walk.workflow import (
    Phase,
    PhaseRepository,
    ProjectRepository,
    WorkItemState,
)


def _cost(model_id: str, input_tokens: int, output_tokens: int, cost: float) -> LedgerEvent:
    return LedgerEvent(
        kind=LedgerEventKind.COST_RECORDED,
        project_key="DEMO",
        actor_role=AgentRole.SENIOR_DEV,
        model_id=model_id,
        cost_usd=cost,
        payload={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": None,
        },
    )


async def test_status_snapshot_from_db_and_ledger(make_kernel: KernelFactory) -> None:
    kernel = await make_kernel()
    env = kernel.env
    await kernel.make_ready()
    await kernel.add_story(2, "Wall slide", state=WorkItemState.BLOCKED)
    await kernel.add_story(3, "Dash")
    running = make_run(
        "RUN-01J0000000000000000000000R", state=AgentRunState.RUNNING, model_id="fake-codex/sim"
    )
    done = make_run("RUN-01J0000000000000000000000D", state=AgentRunState.COMPLETED)
    async with UnitOfWork(env.db) as uow:
        await env.runs.insert(running, uow)
        await env.runs.insert(done, uow)
    await env.ledger.append(_cost("fake-codex/sim", 1000, 200, 0.002))
    await env.ledger.append(_cost("fake-codex/sim", 500, 100, 0.001))
    await env.ledger.append(_cost("fake-claude/sim", 10, 1, 0.0001))
    await env.budgets.ensure(BudgetScope.PROJECT, "DEMO", None, {BudgetDimension.COST_USD: 100.0})

    status = await kernel.status.build()

    assert status.project_key == "DEMO"
    assert status.paused is False
    assert status.current_phase is None
    assert status.phase_progress == {WorkItemState.READY: 2, WorkItemState.BLOCKED: 1}
    assert status.blocked_items == ["STORY-0002"]
    assert [run.id for run in status.active_runs] == [running.id]
    assert status.model_usage["fake-codex/sim"] == UsageReport(
        input_tokens=1500,
        output_tokens=300,
        cache_read_tokens=0,
        cost_usd=0.003,
        turns=0,
        tool_calls=0,
        duration_s=0.0,
    )
    assert status.model_usage["fake-claude/sim"].input_tokens == 10
    assert {budget.scope for budget in status.budgets} == {BudgetScope.PROJECT}
    assert status.pending_approvals == []
    assert status.gdd_coverage == {}
    assert status.open_debates == []
    assert status.qc_status == {}
    assert status.build_status is None
    assert status.open_improvement_candidates == 0


async def test_status_scopes_progress_to_current_phase(make_kernel: KernelFactory) -> None:
    kernel = await make_kernel()
    env = kernel.env
    phase = Phase(id="PHASE-01", project_key="DEMO", ordinal=1, name="Prototype")
    projects = ProjectRepository(env.db)
    project = await projects.get("DEMO")
    assert project is not None
    async with UnitOfWork(env.db) as uow:
        await PhaseRepository(env.db).insert(phase, uow)
        await projects.upsert(project.model_copy(update={"current_phase_id": "PHASE-01"}), uow)
    await kernel.add_story(2, "In phase", phase_id="PHASE-01")
    await env.ledger.append(
        LedgerEvent(
            kind=LedgerEventKind.COST_RECORDED,
            project_key="DEMO",
            actor_role=AgentRole.KERNEL,
            payload={},
        )
    )
    approvals: list[ApprovalRequest] = []

    async def pending() -> list[ApprovalRequest]:
        return approvals

    builder = StatusBuilder(
        projects,
        env.workflow,
        PhaseRepository(env.db),
        env.runs,
        env.budgets,
        env.ledger,
        project_key="DEMO",
        pending_approvals=pending,
    )

    status = await builder.build()

    assert status.current_phase == phase
    assert status.phase_progress == {WorkItemState.READY: 1}
    assert status.model_usage == {}


async def test_status_requires_the_project(make_kernel: KernelFactory) -> None:
    kernel = await make_kernel()
    env = kernel.env
    builder = StatusBuilder(
        ProjectRepository(env.db),
        env.workflow,
        PhaseRepository(env.db),
        env.runs,
        env.budgets,
        env.ledger,
        project_key="NOPE",
    )

    with pytest.raises(ConfigError, match="project NOPE not found"):
        await builder.build()
    with pytest.raises(ConfigError, match="project NOPE not found"):
        await kernel.scheduler.__class__(
            env.db,
            ProjectRepository(env.db),
            env.workflow,
            kernel.router,
            env.agents,
            kernel.scheduler._effort,  # noqa: SLF001 - reuse the wired effort manager
            env.budgets,
            env.router,
            env.executor,
            env.checkpoints,
            kernel.idempotency,
            kernel.telemetry,
            env.executor._clock,  # noqa: SLF001 - the environment's clock
            project_key="NOPE",
        ).tick()
