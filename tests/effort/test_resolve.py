from typing import Literal

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from walk.budgets import BudgetDimension
from walk.common.enums import Effort
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.effort import (
    EFFORT_ORDER,
    STATIC_COST_USD,
    CostEstimator,
    DefaultEffortManager,
    EffortManager,
    EffortPolicy,
    EffortResolution,
    StaticCostEstimator,
)
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.persistence import Database
from walk.telemetry import DefaultLedgerManager, LedgerRepository
from walk.workflow import Feature, Risk, Story, StoryContract, WorkItemState

COST = BudgetDimension.COST_USD
UNLIMITED: dict[BudgetDimension, float] = {}
Complexity = Literal["TRIVIAL", "SMALL", "NORMAL", "LARGE", "CORE"]


def _story(
    complexity: Complexity = "NORMAL", risk: Risk = Risk.MEDIUM, owner: AgentRole | None = None
) -> Story:
    return Story(
        id="STORY-0001",
        project_key="DEMO",
        title="Jump",
        risk=risk,
        owner_role=owner,
        contract=StoryContract(goal="jump", complexity=complexity),
    )


def _manager(db: Database, clock: FakeClock, estimator: CostEstimator) -> DefaultEffortManager:
    ledger = DefaultLedgerManager(db, LedgerRepository(db), SequentialIdFactory(), clock)
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, clock)

    async def never_called(*_: object) -> bool:
        raise AssertionError

    return DefaultEffortManager(estimator, ledger, hooks, clock, never_called, project_key="DEMO")


@pytest.fixture
def effort(db: Database, fake_clock: FakeClock) -> DefaultEffortManager:
    return _manager(db, fake_clock, StaticCostEstimator())


class RecordingEstimator:
    def __init__(self) -> None:
        self.calls: list[tuple[AgentRole, Effort]] = []

    def estimate(self, role: AgentRole, effort: Effort) -> float:
        self.calls.append((role, effort))
        return STATIC_COST_USD[effort]


def test_default_manager_satisfies_protocol(effort: DefaultEffortManager) -> None:
    protocol: EffortManager = effort
    assert protocol is effort


def test_resolve_baseline_medium(effort: DefaultEffortManager) -> None:
    resolution = effort.resolve(EffortPolicy(), _story(), WorkItemState.READY, 0, UNLIMITED)
    assert resolution == EffortResolution(
        role_default=Effort.MEDIUM,
        complexity_component=Effort.MEDIUM,
        risk_bump=0,
        stage_bump=0,
        escalation_bump=0,
        effective=Effort.MEDIUM,
        clamped_by_policy=False,
        clamped_by_budget=False,
    )


def test_role_default_is_a_floor(effort: DefaultEffortManager) -> None:
    resolution = effort.resolve(
        EffortPolicy(), _story(complexity="SMALL"), WorkItemState.READY, 0, UNLIMITED
    )
    assert resolution.complexity_component is Effort.LOW
    assert resolution.effective is Effort.MEDIUM


def test_risk_bump_and_policy_clamp(effort: DefaultEffortManager) -> None:
    resolution = effort.resolve(
        EffortPolicy(default=Effort.HIGH),
        _story(risk=Risk.CRITICAL),
        WorkItemState.READY,
        0,
        UNLIMITED,
    )
    assert resolution.risk_bump == 2
    assert resolution.effective is Effort.HIGH
    assert resolution.clamped_by_policy is True
    assert resolution.clamped_by_budget is False


def test_stage_bump_for_rework(effort: DefaultEffortManager) -> None:
    resolution = effort.resolve(EffortPolicy(), _story(), WorkItemState.REWORK, 0, UNLIMITED)
    assert resolution.stage_bump == 1
    assert resolution.effective is Effort.HIGH
    assert resolution.clamped_by_policy is False


def test_escalation_bump_applied(effort: DefaultEffortManager) -> None:
    resolution = effort.resolve(EffortPolicy(), _story(), WorkItemState.READY, 1, UNLIMITED)
    assert resolution.escalation_bump == 1
    assert resolution.effective is Effort.HIGH


def test_budget_headroom_downgrades(effort: DefaultEffortManager) -> None:
    resolution = effort.resolve(
        EffortPolicy(default=Effort.HIGH), _story(), WorkItemState.READY, 0, {COST: 2.5}
    )
    assert resolution.effective is Effort.LOW
    assert resolution.clamped_by_budget is True
    assert resolution.clamped_by_policy is False


def test_missing_headroom_is_unlimited(effort: DefaultEffortManager) -> None:
    resolution = effort.resolve(
        EffortPolicy(default=Effort.HIGH),
        _story(),
        WorkItemState.READY,
        0,
        {BudgetDimension.TOOL_CALLS: 0.0},
    )
    assert resolution.effective is Effort.HIGH
    assert resolution.clamped_by_budget is False


def test_items_without_contract_use_default(effort: DefaultEffortManager) -> None:
    feature = Feature(id="FEAT-0001", project_key="DEMO", title="Movement")
    resolution = effort.resolve(
        EffortPolicy(default=Effort.HIGH), feature, WorkItemState.READY, 0, UNLIMITED
    )
    assert resolution.complexity_component is Effort.HIGH
    assert resolution.effective is Effort.HIGH


def test_budget_clamp_never_goes_below_lowest_effort(effort: DefaultEffortManager) -> None:
    resolution = effort.resolve(EffortPolicy(), _story(), WorkItemState.READY, 0, {COST: 0.0})
    assert resolution.effective is Effort.LOW
    assert resolution.clamped_by_budget is True


def test_policy_min_raises_low_result(effort: DefaultEffortManager) -> None:
    resolution = effort.resolve(
        EffortPolicy(default=Effort.LOW, min=Effort.MEDIUM),
        _story(complexity="TRIVIAL"),
        WorkItemState.READY,
        0,
        UNLIMITED,
    )
    assert resolution.effective is Effort.MEDIUM
    assert resolution.clamped_by_policy is True


def test_estimates_use_the_item_owner_role(db: Database, fake_clock: FakeClock) -> None:
    estimator = RecordingEstimator()
    manager = _manager(db, fake_clock, estimator)
    manager.resolve(EffortPolicy(), _story(), WorkItemState.READY, 0, {COST: 1.0})
    manager.resolve(EffortPolicy(), _story(owner=AgentRole.QC), WorkItemState.READY, 0, {COST: 1.0})
    feature = Feature(id="FEAT-0001", project_key="DEMO", title="Movement")
    manager.resolve(EffortPolicy(), feature, WorkItemState.READY, 0, {COST: 1.0})
    assert {role for role, _ in estimator.calls} == {
        AgentRole.SENIOR_DEV,
        AgentRole.QC,
        AgentRole.KERNEL,
    }


def test_unmapped_complexity_is_a_config_error(effort: DefaultEffortManager) -> None:
    policy = EffortPolicy(complexity_map={"NORMAL": Effort.MEDIUM})
    with pytest.raises(ConfigError, match="complexity"):
        effort.resolve(policy, _story(complexity="CORE"), WorkItemState.READY, 0, UNLIMITED)


def test_unmapped_risk_is_a_config_error(effort: DefaultEffortManager) -> None:
    policy = EffortPolicy(risk_bump={Risk.LOW: 0})
    with pytest.raises(ConfigError, match="risk"):
        effort.resolve(policy, _story(), WorkItemState.READY, 0, UNLIMITED)


def test_static_cost_table_matches_adr_0011() -> None:
    assert EFFORT_ORDER == (Effort.LOW, Effort.MEDIUM, Effort.HIGH, Effort.VERY_HIGH)
    estimator = StaticCostEstimator()
    assert [estimator.estimate(AgentRole.SENIOR_DEV, e) for e in EFFORT_ORDER] == [1, 3, 8, 20]
