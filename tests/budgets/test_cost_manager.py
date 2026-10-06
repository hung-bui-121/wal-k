from datetime import UTC, datetime
from itertools import count

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from walk.budgets import (
    BudgetDimension,
    BudgetRepository,
    BudgetScope,
    BudgetSubject,
    CostCategory,
    CostManager,
    CostRecord,
    CostRepository,
    DefaultBudgetManager,
    DefaultCostManager,
)
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.persistence import Database, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerEventKind, LedgerRepository
from walk.workflow import (
    TABLES_DIR,
    BugDraft,
    DefaultWorkflowManager,
    Project,
    ProjectRepository,
    Severity,
    StoryContract,
    WorkflowRepository,
    WorkItemDraft,
    WorkItemKind,
)
from walk.workflow.errors import WorkItemNotFound

T0 = datetime(2026, 1, 1, tzinfo=UTC)
_IDS = count(1)


@pytest.fixture
def ledger(db: Database, fake_clock: FakeClock) -> DefaultLedgerManager:
    return DefaultLedgerManager(db, LedgerRepository(db), SequentialIdFactory(), fake_clock)


@pytest.fixture
def budgets(
    db: Database, ledger: DefaultLedgerManager, fake_clock: FakeClock
) -> DefaultBudgetManager:
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)
    return DefaultBudgetManager(db, BudgetRepository(db), ledger, hooks, fake_clock)


@pytest.fixture
def costs(
    db: Database, ledger: DefaultLedgerManager, budgets: DefaultBudgetManager
) -> DefaultCostManager:
    return DefaultCostManager(db, CostRepository(db), ledger, budgets, WorkflowRepository(db))


def _record(
    usd: float,
    *,
    category: CostCategory = CostCategory.LLM,
    item: str | None = None,
    phase: str | None = None,
    dimension: BudgetDimension = BudgetDimension.TOKENS,
    quantity: float = 1000,
) -> CostRecord:
    return CostRecord(
        id=f"COST-{next(_IDS)}",
        at=T0,
        project_key="DEMO",
        category=category,
        provider="claude",
        model_id="claude/opus",
        dimension=dimension,
        quantity=quantity,
        unit="tokens",
        cost_usd=usd,
        run_id="RUN-01J00000000000000000000000",
        work_item_id=item,
        phase_id=phase,
        role=AgentRole.SENIOR_DEV,
        input_tokens=600,
        output_tokens=400,
    )


def test_default_manager_satisfies_protocol(costs: DefaultCostManager) -> None:
    protocol: CostManager = costs
    assert protocol is costs


async def test_record_persists_and_meters(
    costs: DefaultCostManager,
    budgets: DefaultBudgetManager,
    ledger: DefaultLedgerManager,
    db: Database,
) -> None:
    await budgets.ensure(
        BudgetScope.TASK,
        "STORY-0001",
        None,
        {BudgetDimension.COST_USD: 10.0, BudgetDimension.TOKENS: 50_000},
    )
    await costs.record(_record(1.25, item="STORY-0001"))
    row = db.connect().execute("SELECT category, cost_usd, work_item_id FROM cost_records")
    assert tuple(row.fetchone()) == ("LLM", 1.25, "STORY-0001")
    events = await ledger.query(kinds=[LedgerEventKind.COST_RECORDED])
    assert len(events) == 1
    assert events[0].cost_usd == 1.25
    assert events[0].model_id == "claude/opus"
    assert (events[0].payload["input_tokens"], events[0].payload["output_tokens"]) == (600, 400)
    subject = BudgetSubject(project_key="DEMO", work_item_id="STORY-0001")
    consumed = {b.dimension: b.consumed for b in await budgets.applicable(subject)}
    assert consumed == {BudgetDimension.COST_USD: 1.25, BudgetDimension.TOKENS: 1000}


async def test_record_meters_cost_only_for_other_dimensions(
    costs: DefaultCostManager, budgets: DefaultBudgetManager
) -> None:
    await budgets.ensure(BudgetScope.PROJECT, "DEMO", None, {BudgetDimension.COST_USD: 5.0})
    await costs.record(
        _record(
            0.5,
            category=CostCategory.COMPUTE,
            dimension=BudgetDimension.EXECUTION_TIME_S,
            quantity=30,
        )
    )
    budget = (await budgets.applicable(BudgetSubject(project_key="DEMO")))[0]
    assert budget.consumed == 0.5


@pytest.fixture
async def tree(
    db: Database, ledger: DefaultLedgerManager, fake_clock: FakeClock, project: Project
) -> None:
    """FEAT-0001 with STORY-0001/0002 and BUG-0001 (related), FEAT-0002 elsewhere."""
    del project
    workflow = DefaultWorkflowManager(
        db,
        WorkflowRepository(db),
        ProjectRepository(db),
        IdSequenceStore(db),
        ledger,
        DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock),
        fake_clock,
        TABLES_DIR,
    )
    po = AgentRole.PRODUCT_OWNER
    for _ in range(2):
        await workflow.create(
            WorkItemDraft(kind=WorkItemKind.FEATURE, title="F", description=""),
            actor=po,
            phase_id=None,
        )
    for _ in range(2):
        await workflow.create(
            WorkItemDraft(
                kind=WorkItemKind.STORY,
                title="S",
                description="",
                parent_id="FEAT-0001",
                contract=StoryContract(goal="g"),
            ),
            actor=po,
            phase_id=None,
        )
    await workflow.create(
        BugDraft(
            title="B",
            severity=Severity.MINOR,
            reproduction="r",
            expected="e",
            observed="o",
            related_feature_id="FEAT-0001",
        ),
        actor=AgentRole.QC,
        phase_id=None,
    )


@pytest.mark.usefixtures("tree")
async def test_cost_of_rolls_up_descendants(costs: DefaultCostManager) -> None:
    await costs.record(_record(1.0, item="FEAT-0001"))
    await costs.record(_record(2.0, item="STORY-0001"))
    await costs.record(_record(3.0, item="STORY-0002", category=CostCategory.COMPUTE))
    await costs.record(_record(4.0, item="BUG-0001"))
    await costs.record(_record(100.0, item="FEAT-0002"))
    totals = await costs.cost_of(work_item_id="FEAT-0001")
    assert totals == {
        CostCategory.LLM: 7.0,
        CostCategory.ASSETS: 0.0,
        CostCategory.COMPUTE: 3.0,
        CostCategory.TIME: 0.0,
    }
    assert (await costs.cost_of(work_item_id="STORY-0001"))[CostCategory.LLM] == 2.0


async def test_cost_of_phase(costs: DefaultCostManager) -> None:
    await costs.record(_record(1.5, phase="PHASE-01"))
    await costs.record(_record(2.5, phase="PHASE-01", category=CostCategory.ASSETS))
    await costs.record(_record(9.0, phase="PHASE-02"))
    phase = await costs.cost_of(phase_id="PHASE-01")
    assert (phase[CostCategory.LLM], phase[CostCategory.ASSETS]) == (1.5, 2.5)
    project = await costs.cost_of(project_key="DEMO")
    assert sum(project.values()) == 13.0


async def test_cost_of_requires_exactly_one_subject(costs: DefaultCostManager) -> None:
    with pytest.raises(ConfigError, match="exactly one"):
        await costs.cost_of()
    with pytest.raises(ConfigError, match="exactly one"):
        await costs.cost_of(phase_id="PHASE-01", project_key="DEMO")


@pytest.mark.usefixtures("tree")
async def test_cost_of_unknown_item_raises(costs: DefaultCostManager, db: Database) -> None:
    with pytest.raises(WorkItemNotFound, match="STORY-0042"):
        await costs.cost_of(work_item_id="STORY-0042")
    totals = await CostRepository(db).totals("phase_id", [])
    assert totals == dict.fromkeys(CostCategory, 0.0)
    assert await BudgetRepository(db).for_scopes([]) == []
