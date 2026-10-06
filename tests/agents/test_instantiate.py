from pathlib import Path

import pytest

import walk.agents
from tests.agents.conftest import DEFAULTS, make_story
from tests.fakes.fake_clock import FakeClock
from walk.agents import (
    AgentInstance,
    AgentManager,
    ConstitutionLoader,
    DefaultAgentManager,
    PolicyLoader,
    TemplateRenderer,
)
from walk.common.enums import Effort
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.permissions import (
    ApprovalRepository,
    DefaultPermissionManager,
    PermissionEffect,
    PermissionRule,
)
from walk.persistence import Database, IdSequenceStore
from walk.skills import DriftReport, Skill, SkillProjection, SkillProjector
from walk.telemetry import DefaultLedgerManager, EvidenceKind, LedgerRepository
from walk.tools import DefaultToolRegistry, load_tool_specs
from walk.workflow import Feature

POLICIES = DEFAULTS / "policies.yaml"
TEMPLATES = Path(walk.agents.__file__).resolve().parent / "templates"
DEV = AgentRole.SENIOR_DEV
KERNEL_RULES = [
    PermissionRule(role=DEV, tool="write", effect=PermissionEffect.DENY),
    PermissionRule(role=DEV, tool="read", effect=PermissionEffect.ALLOW),
]


class RecordingSkills:
    """Minimal `SkillRegistry` stand-in that knows a fixed set of skill names."""

    def __init__(self, known: set[str]) -> None:
        self.known = known
        self.calls: list[tuple[AgentRole, list[str]]] = []

    def for_role(self, role: AgentRole, required: list[str]) -> list[Skill]:
        self.calls.append((role, list(required)))
        missing = [name for name in required if name not in self.known]
        if missing:
            msg = f"required skills missing: {missing}"
            raise ConfigError(msg)
        return []

    def load(self) -> list[Skill]:
        raise NotImplementedError

    def get(self, name: str) -> Skill:
        raise NotImplementedError(name)

    async def project_all(
        self, projectors: list[SkillProjector], worktree_path: str, skills: list[Skill]
    ) -> list[SkillProjection]:
        raise NotImplementedError(worktree_path)

    async def check_drift(
        self, projectors: list[SkillProjector], worktree_path: str
    ) -> DriftReport:
        raise NotImplementedError(worktree_path)


def _permissions(db: Database, clock: FakeClock) -> DefaultPermissionManager:
    ids = IdSequenceStore(db)
    ledger = DefaultLedgerManager(db, LedgerRepository(db), ids, clock)
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, clock)
    return DefaultPermissionManager(
        KERNEL_RULES, [], ApprovalRepository(db), ledger, hooks, ids, clock, project_key="DEMO"
    )


@pytest.fixture
def project_policies(tmp_path: Path) -> Path:
    path = tmp_path / "policies.yaml"
    path.write_text("roles:\n  SENIOR_DEV:\n    default_skills: [git-hygiene]\n", encoding="utf-8")
    return path


@pytest.fixture
def manager(db: Database, fake_clock: FakeClock, project_policies: Path) -> DefaultAgentManager:
    return DefaultAgentManager(
        ConstitutionLoader(DEFAULTS, None),
        PolicyLoader(POLICIES, project_policies),
        _permissions(db, fake_clock),
        DefaultToolRegistry(load_tool_specs([])),
        TemplateRenderer(TEMPLATES),
    )


async def test_instantiate_assembles_instance(manager: DefaultAgentManager) -> None:
    protocol: AgentManager = manager
    story = make_story(required_skills=["unity-csharp-conventions", "git-hygiene"])

    agent = await protocol.instantiate(
        DEV, story, "codex/default", Effort.HIGH, ["TASK:STORY-0001:COST_USD"], {"git"}
    )

    assert isinstance(agent, AgentInstance)
    assert agent.role is DEV
    assert agent.constitution == manager.load_constitution(DEV)
    assert agent.runtime_policy == manager.load_runtime_policy(DEV)
    assert agent.skills == ["git-hygiene", "unity-csharp-conventions"]
    available = {spec.name for spec in DefaultToolRegistry(load_tool_specs([])).available({"git"})}
    assert agent.tools
    assert set(agent.tools) <= available
    assert set(agent.tools) <= set(agent.runtime_policy.allowed_tools)
    assert "unity.compile" not in agent.tools
    assert agent.permissions[: len(KERNEL_RULES)] == KERNEL_RULES
    assert len(agent.permissions) > len(KERNEL_RULES)
    assert (agent.model_id, agent.effort, agent.budget_ids) == (
        "codex/default",
        Effort.HIGH,
        ["TASK:STORY-0001:COST_USD"],
    )


async def test_instantiate_without_contract_uses_policy_skills(
    manager: DefaultAgentManager,
) -> None:
    feature = Feature(id="FEAT-0001", project_key="DEMO", title="Movement")

    agent = await manager.instantiate(DEV, feature, "codex/default", Effort.LOW, [], set())

    assert agent.skills == ["git-hygiene"]


async def test_instantiate_permissions_only_narrow(manager: DefaultAgentManager) -> None:
    constitution = manager.load_constitution(DEV)
    widening = [r for r in constitution.tool_permissions if r.tool == "write"]
    assert widening
    assert widening[0].effect is PermissionEffect.ALLOW

    agent = await manager.instantiate(DEV, make_story(), "codex/default", Effort.LOW, [], {"git"})

    write_rules = [r for r in agent.permissions if r.tool == "write"]
    assert write_rules == [KERNEL_RULES[0]]


async def test_instantiate_missing_required_tool_raises(manager: DefaultAgentManager) -> None:
    story = make_story(constraints=["tool:unity.compile", "keep 60 fps"])

    with pytest.raises(ConfigError, match=r"unity\.compile"):
        await manager.instantiate(DEV, story, "codex/default", Effort.LOW, [], {"git"})

    agent = await manager.instantiate(DEV, story, "codex/default", Effort.LOW, [], {"git", "unity"})
    assert "unity.compile" in agent.tools


async def test_instantiate_validates_skills_with_registry(
    db: Database, fake_clock: FakeClock, project_policies: Path
) -> None:
    skills = RecordingSkills({"git-hygiene"})
    manager = DefaultAgentManager(
        ConstitutionLoader(DEFAULTS, None),
        PolicyLoader(POLICIES, project_policies),
        _permissions(db, fake_clock),
        DefaultToolRegistry(load_tool_specs([])),
        TemplateRenderer(TEMPLATES),
        skills=skills,
    )

    agent = await manager.instantiate(DEV, make_story(), "codex/default", Effort.LOW, [], set())
    with pytest.raises(ConfigError, match="missing"):
        await manager.instantiate(
            DEV, make_story(required_skills=["nope"]), "codex/default", Effort.LOW, [], set()
        )

    assert agent.skills == ["git-hygiene"]
    assert skills.calls == [(DEV, ["git-hygiene"]), (DEV, ["git-hygiene", "nope"])]


async def test_render_instructions_per_purpose(manager: DefaultAgentManager) -> None:
    story = make_story(required_evidence=[EvidenceKind.AUTOMATED_TEST])
    agent = await manager.instantiate(DEV, story, "codex/default", Effort.MEDIUM, [], {"git"})

    implement = manager.render_instructions(agent, story, "IMPLEMENT")
    review = manager.render_instructions(agent, story, "REVIEW")
    triage = manager.render_instructions(agent, story, "TRIAGE")

    assert "STORY-0001" in implement
    assert "COMPLETED" in implement
    assert "PARTIAL" in implement
    assert "AUTOMATED_TEST" in implement
    assert "APPROVED" in review
    assert "REJECTED" in review
    assert "PARTIAL" not in review
    assert "NEEDS_INPUT" in triage
    with pytest.raises(ConfigError, match="NOPE"):
        manager.render_instructions(agent, story, "NOPE")
