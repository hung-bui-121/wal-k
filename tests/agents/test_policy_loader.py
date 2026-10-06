from pathlib import Path

import pytest

import walk.agents
from tests.fakes.fake_clock import FakeClock
from walk.agents import (
    AgentManager,
    ConstitutionError,
    ConstitutionLoader,
    DefaultAgentManager,
    PolicyLoader,
)
from walk.budgets import BudgetDimension
from walk.common.enums import Effort
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.permissions import ApprovalRepository, DefaultPermissionManager
from walk.persistence import Database, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerRepository
from walk.workflow import Feature

DEFAULTS = Path(walk.agents.__file__).resolve().parent / "defaults"
POLICIES = DEFAULTS / "policies.yaml"
DEV = AgentRole.SENIOR_DEV


def test_policy_deep_merge(tmp_path: Path) -> None:
    project = tmp_path / "policies.yaml"
    project.write_text(
        "roles:\n"
        "  SENIOR_DEV:\n"
        "    checkpoint_every_tool_calls: 5\n"
        "    model_policy: {fallback: [claude/sonnet]}\n"
        "    budget_policy: {per_task: {COST_USD: 4.0}}\n",
        encoding="utf-8",
    )
    merged = PolicyLoader(POLICIES, project).load(DEV)
    default = PolicyLoader(POLICIES, None).load(DEV)
    assert merged.checkpoint_every_tool_calls == 5
    assert merged.model_policy.fallback == ["claude/sonnet"]
    assert merged.model_policy.preferred == default.model_policy.preferred
    assert merged.allowed_tools == default.allowed_tools
    assert merged.effort_policy == default.effort_policy
    assert merged.budget_policy.per_task[BudgetDimension.COST_USD] == 4.0
    assert merged.budget_policy.per_task[BudgetDimension.TOOL_CALLS] == 400
    assert PolicyLoader(POLICIES, project).load(AgentRole.QC) == PolicyLoader(POLICIES, None).load(
        AgentRole.QC
    )


def test_missing_project_policy_file_means_defaults(tmp_path: Path) -> None:
    loader = PolicyLoader(POLICIES, tmp_path / "absent.yaml")
    assert loader.load(DEV).model_policy.preferred == ["codex/default"]
    assert loader.load(DEV) is loader.load(DEV)


@pytest.mark.parametrize(
    "text",
    [
        "roles: [\n",
        "other: {}\n",
        "roles:\n  SENIOR_DEV:\n    max_parallel_runs: many\n",
        "roles:\n  SENIOR_DEV:\n    surprise: 1\n",
    ],
)
def test_invalid_policy_files_rejected(tmp_path: Path, text: str) -> None:
    project = tmp_path / "policies.yaml"
    project.write_text(text, encoding="utf-8")
    with pytest.raises(ConstitutionError, match=r"policies\.yaml"):
        PolicyLoader(POLICIES, project).load(DEV)


def test_unknown_role_and_list_roles(db: Database, fake_clock: FakeClock) -> None:
    constitutions = ConstitutionLoader(DEFAULTS, None)
    with pytest.raises(ConstitutionError, match="UA_RELEASE"):
        constitutions.load(AgentRole.UA_RELEASE)
    with pytest.raises(ConstitutionError, match="USER"):
        PolicyLoader(POLICIES, None).load(AgentRole.USER)
    ids = IdSequenceStore(db)
    ledger = DefaultLedgerManager(db, LedgerRepository(db), ids, fake_clock)
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)
    permissions = DefaultPermissionManager(
        [], [], ApprovalRepository(db), ledger, hooks, ids, fake_clock, project_key="DEMO"
    )
    manager = DefaultAgentManager(constitutions, PolicyLoader(POLICIES, None), permissions)
    protocol: AgentManager = manager
    assert protocol.list_roles() == [
        AgentRole.ORCHESTRATOR,
        AgentRole.LEAD_DEV,
        AgentRole.SENIOR_DEV,
        AgentRole.QC,
    ]
    assert manager.load_constitution(AgentRole.QC).role is AgentRole.QC
    assert manager.load_runtime_policy(AgentRole.QC).role is AgentRole.QC


async def test_execution_contract_methods_arrive_in_e01_s18(
    db: Database, fake_clock: FakeClock
) -> None:
    ids = IdSequenceStore(db)
    ledger = DefaultLedgerManager(db, LedgerRepository(db), ids, fake_clock)
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)
    permissions = DefaultPermissionManager(
        [], [], ApprovalRepository(db), ledger, hooks, ids, fake_clock, project_key="DEMO"
    )
    manager = DefaultAgentManager(
        ConstitutionLoader(DEFAULTS, None), PolicyLoader(POLICIES, None), permissions
    )
    feature = Feature(id="FEAT-0001", project_key="DEMO", title="Movement")
    with pytest.raises(ConfigError, match="E01-S18"):
        await manager.instantiate(DEV, feature, "codex/default", Effort.LOW, [], set())
    with pytest.raises(ConfigError, match="E01-S18"):
        manager.render_instructions(None, feature, "IMPLEMENT")  # type: ignore[arg-type]  # never reached
