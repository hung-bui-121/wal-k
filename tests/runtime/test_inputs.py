from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_model_adapter import FakeModelAdapter, fake_descriptor
from tests.runtime.conftest import STORY_ID, make_run
from tests.runtime.executor_env import CODEX_MODEL, EnvFactory, script
from walk.agents import AgentInput, AgentOutputStatus, Handover
from walk.common.enums import Effort
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.context import token_budget_for
from walk.model_router import OUTPUT_RELATIVE_PATH, AgentEvent, RunSession
from walk.permissions import PermissionDecision, PermissionEffect, ToolCallRequest
from walk.persistence import UnitOfWork
from walk.runtime import RUN_TIMEOUT_S, build_run_session, expected_output_for
from walk.telemetry import EvidenceKind, LedgerEventKind
from walk.tools import ToolKind
from walk.workflow import (
    Bug,
    Feature,
    Phase,
    PhaseRepository,
    Severity,
    StoryContract,
    WorkItemState,
)

AT = datetime(2026, 1, 1, tzinfo=UTC)
RUN_ID = "RUN-01J0000000000000000000000A"
BUILD = [
    AgentOutputStatus.COMPLETED,
    AgentOutputStatus.PARTIAL,
    AgentOutputStatus.BLOCKED,
    AgentOutputStatus.FAILED,
]


class _SessionRecorder(FakeModelAdapter):
    """Keeps every `RunSession` it was started with."""

    sessions: list[RunSession]

    def run(self, input: AgentInput, session: RunSession) -> AsyncIterator[AgentEvent]:  # noqa: A002 - parameter name fixed by INTERFACES §2.1
        self.sessions.append(session)
        return super().run(input, session)


def _handover() -> Handover:
    return Handover(
        id="HO-0001",
        work_item_id=STORY_ID,
        role=AgentRole.SENIOR_DEV,
        from_run_id="RUN-01J0000000000000000000000B",
        from_model_id="fake-claude/sim",
        reason="FALLBACK",
        task_summary="Double jump",
        current_state="IMPLEMENTING",
        completed_work=["input mapped"],
        modified_files=["src/Fake1.cs"],
        findings=[],
        hypotheses=[],
        decisions=[],
        risks=[],
        remaining_work=["tests"],
        next_action="Write the tests",
        worktree_head="a" * 40,
        branch="feat/story-0001-x",
        created_at=AT,
    )


async def test_build_run_session_fields(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapter = _SessionRecorder(
        "fake-codex", [fake_descriptor(CODEX_MODEL, "fake-codex")], script(), fake_clock
    )
    adapter.sessions = []
    env = await make_executor_env(adapters={"fake-codex": adapter})

    run = await env.run_to_end()

    session = adapter.sessions[0]
    assert run.worktree_path is not None
    assert session.run_id == run.id
    assert session.worktree_path == run.worktree_path
    assert session.output_path.replace("\\", "/").endswith(OUTPUT_RELATIVE_PATH)
    assert [tool.name for tool in session.allowed_tools] == env.agent.tools
    assert session.model_id == CODEX_MODEL
    assert session.effort is Effort.MEDIUM
    assert session.timeout_s == RUN_TIMEOUT_S
    assert session.max_turns == 50
    assert session.env_allowlist == {}
    request = ToolCallRequest(
        run_id="RUN-01J0000000000000000000ZZZZ",
        role=AgentRole.QC,
        tool="edit",
        kind=ToolKind.PROVIDER_NATIVE,
        arguments={},
        paths=["src/X.cs"],
        worktree_path="",
    )
    decision = await session.permission_authorizer(request)
    assert decision.effect is PermissionEffect.ALLOW
    pre = [
        event
        for event in await env.events(run.id, LedgerEventKind.TOOL_INVOKED)
        if event.payload["phase"] == "pre"
    ]
    assert pre[-1].run_id == run.id
    assert pre[-1].actor_role is AgentRole.SENIOR_DEV


async def test_agent_input_builder_populates_contract(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env()
    contract = StoryContract(
        goal="Let the player double jump",
        acceptance_criteria=["second jump in the air"],
        required_evidence=[EvidenceKind.AUTOMATED_TEST],
    )
    story = env.story.model_copy(update={"contract": contract})
    descriptor = fake_descriptor(CODEX_MODEL, "fake-codex")
    handover = _handover()

    built = await env.inputs.build(
        env.agent,
        story,
        "IMPLEMENT",
        run_id=RUN_ID,
        worktree_path="/wt",
        branch="feat/story-0001-x",
        descriptor=descriptor,
        handover=handover,
    )

    assert set(built.model_fields_set) >= set(AgentInput.model_fields) - {"debate"}
    assert built.run_id == RUN_ID
    assert built.role is AgentRole.SENIOR_DEV
    assert built.constitution == env.agent.constitution
    assert built.authority == env.agent.constitution.authority
    assert built.task == story
    assert built.workflow_state is WorkItemState.IMPLEMENTING
    assert built.phase is None
    assert built.expected_output.status_options == BUILD
    assert built.expected_output.deliverables == []
    assert built.required_evidence == [EvidenceKind.AUTOMATED_TEST]
    assert built.expected_output.required_evidence == [EvidenceKind.AUTOMATED_TEST]
    assert built.handover == handover
    assert built.debate is None
    assert built.context.request.token_budget == token_budget_for(
        Effort.MEDIUM, descriptor.context_window_tokens, descriptor.max_output_tokens
    )
    assert built.context.request.work_item_id == STORY_ID
    assert [tool.name for tool in built.allowed_tools] == env.agent.tools
    assert built.permissions == env.agent.permissions
    assert built.approved_artifacts == []
    assert built.decisions == []
    assert built.skills == []
    assert built.effort is Effort.MEDIUM
    assert built.worktree_path == "/wt"
    assert built.branch == "feat/story-0001-x"
    assert "AUTOMATED_TEST" in built.instructions_markdown
    assert built.instructions_markdown.startswith("# Task: IMPLEMENT STORY-0001")


async def test_agent_input_builder_reads_phase(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env()
    phase = Phase(id="PHASE-01", project_key="DEMO", ordinal=1, name="Prototype")
    async with UnitOfWork(env.db) as uow:
        await PhaseRepository(env.db).insert(phase, uow)
    descriptor = fake_descriptor(CODEX_MODEL, "fake-codex")

    async def build(phase_id: str) -> AgentInput:
        return await env.inputs.build(
            env.agent,
            env.story.model_copy(update={"phase_id": phase_id}),
            "IMPLEMENT",
            run_id=RUN_ID,
            worktree_path="/wt",
            branch="b",
            descriptor=descriptor,
        )

    in_phase = await build("PHASE-01")

    assert in_phase.phase == phase
    with pytest.raises(ConfigError, match="unknown phase"):
        await build("PHASE-02")


def test_expected_output_for_purposes_and_contracts() -> None:
    feature = Feature(id="FEAT-0001", project_key="DEMO", title="Movement")
    bug = Bug(
        id="BUG-0001",
        project_key="DEMO",
        title="Falls through floor",
        severity=Severity.MAJOR,
        contract=StoryContract(goal="fix", required_evidence=[EvidenceKind.REPRODUCTION_PROOF]),
    )

    review = expected_output_for("REVIEW", feature)
    fix = expected_output_for("IMPLEMENT", bug)
    plan = expected_output_for("PLAN", feature)

    assert review.status_options == [
        AgentOutputStatus.APPROVED,
        AgentOutputStatus.REJECTED,
        AgentOutputStatus.NEEDS_INPUT,
    ]
    assert review.required_evidence == []
    assert fix.status_options == BUILD
    assert fix.required_evidence == [EvidenceKind.REPRODUCTION_PROOF]
    assert plan.status_options == [
        AgentOutputStatus.COMPLETED,
        AgentOutputStatus.NEEDS_INPUT,
        AgentOutputStatus.FAILED,
    ]
    with pytest.raises(ConfigError, match="unknown template purpose"):
        expected_output_for("DANCE", feature)


async def test_build_run_session_requires_worktree(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env()
    built = await env.inputs.build(
        env.agent,
        env.story,
        "IMPLEMENT",
        run_id=RUN_ID,
        worktree_path="/wt",
        branch="b",
        descriptor=fake_descriptor(CODEX_MODEL, "fake-codex"),
    )

    async def allow(request: ToolCallRequest) -> PermissionDecision:
        del request
        return PermissionDecision(effect=PermissionEffect.ALLOW, matched_rule=None, reason="ok")

    with pytest.raises(ConfigError, match="has no worktree"):
        build_run_session(
            make_run(RUN_ID), built, allow, max_turns=5, timeout_s=10, env_allowlist={}
        )
    session = build_run_session(
        make_run(RUN_ID, worktree_path="/wt"),
        built,
        allow,
        max_turns=5,
        timeout_s=10,
        env_allowlist={"PATH": "/bin"},
    )
    assert session.max_turns == 5
    assert session.env_allowlist == {"PATH": "/bin"}
