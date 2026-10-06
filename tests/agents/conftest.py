"""Builders shared by the execution-contract tests (E01-S18)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

import walk.agents
from walk.agents import (
    AgentInput,
    AgentOutputStatus,
    ConstitutionLoader,
    ExpectedOutput,
    Finding,
    Handover,
)
from walk.budgets import Budget, BudgetDimension, BudgetScope
from walk.common.enums import Effort, LearningScope
from walk.common.models import Actor
from walk.common.roles import AgentRole
from walk.context import ContextBundle, ContextItem, ContextItemKind, ContextRequest
from walk.decisions import (
    AutonomyLevel,
    Decision,
    DecisionCategory,
    DecisionProposal,
    DecisionStatus,
)
from walk.memory import ApprovalStatus, ApprovedArtifact, ApprovedArtifactKind
from walk.skills import Skill
from walk.telemetry import EvidenceKind
from walk.tools import ToolKind, ToolSpec
from walk.workflow import Story, StoryContract, WorkItemState

DEFAULTS = Path(walk.agents.__file__).resolve().parent / "defaults"
AT = datetime(2026, 1, 1, tzinfo=UTC)
RUN_A = "RUN-01J00000000000000000000000"
RUN_B = "RUN-01J00000000000000000000001"


def make_story(**contract: object) -> Story:
    """STORY-0001 under FEAT-0001 with a contract built from ``contract``."""
    return Story(
        id="STORY-0001",
        project_key="DEMO",
        title="Run with shift",
        parent_id="FEAT-0001",
        state=WorkItemState.READY,
        contract=StoryContract.model_validate(
            {"goal": "Run with shift", "acceptance_criteria": ["shift doubles speed"], **contract}
        ),
        created_at=AT,
        updated_at=AT,
    )


@pytest.fixture
def handover() -> Handover:
    return Handover(
        id="HO-0001",
        work_item_id="STORY-0001",
        role=AgentRole.SENIOR_DEV,
        from_run_id=RUN_A,
        from_model_id="codex/default",
        to_run_id=RUN_B,
        reason="FALLBACK",
        task_summary="Add running to the player controller.",
        current_state="Input handling done; animation pending.",
        completed_work=["Shift input mapped", "Speed multiplier\nwith a second line"],
        modified_files=["Assets/Scripts/Player.cs"],
        findings=[
            Finding(
                summary="Animator lacks a run state",
                detail="Needs a blend tree.",
                evidence_ids=["EVD-000001"],
                affected_files=["Assets/Anim/Player.controller"],
                severity="RISK",
            )
        ],
        hypotheses=["Blend tree avoids popping"],
        decisions=["DEC-0001"],
        proposed_decisions=[
            DecisionProposal(
                category=DecisionCategory.TECH,
                topic="Run speed source",
                position="Scriptable object",
                rationale="Designers tune it",
                autonomy_level=AutonomyLevel.LOCAL,
            )
        ],
        risks=[],
        remaining_work=["Animation", "Tests"],
        next_action="Create the run blend tree.",
        worktree_head="3f9c2e1",
        branch="feat/STORY-0001-run",
        created_at=AT,
    )


@pytest.fixture
def agent_input(handover: Handover) -> AgentInput:
    constitution = ConstitutionLoader(DEFAULTS, None).load(AgentRole.SENIOR_DEV)
    request = ContextRequest(
        work_item_id="STORY-0001",
        role=AgentRole.SENIOR_DEV,
        effort=Effort.MEDIUM,
        token_budget=50_000,
    )
    items = [
        ContextItem(
            id="WORK_ITEM:STORY-0001",
            kind=ContextItemKind.WORK_ITEM,
            title="STORY-0001 Run with shift",
            content='{"id": "STORY-0001"}',
            tokens_estimate=6,
            score=1.0,
            freshness=None,
            mandatory=True,
        ),
        ContextItem(
            id="FEATURE_CONTEXT:FEAT-0001",
            kind=ContextItemKind.FEATURE_CONTEXT,
            title="Movement",
            content="## Intent\n\nWalk and run.",
            tokens_estimate=7,
            score=1.0,
            freshness=None,
            requires_verification=True,
            mandatory=True,
        ),
    ]
    return AgentInput(
        run_id=RUN_B,
        role=AgentRole.SENIOR_DEV,
        constitution=constitution,
        authority=constitution.authority,
        task=make_story(required_evidence=[EvidenceKind.AUTOMATED_TEST]),
        workflow_state=WorkItemState.READY,
        phase=None,
        context=ContextBundle(
            request=request,
            items=items,
            total_tokens_estimate=13,
            excluded_count=0,
            built_at=AT,
            head_commit="3f9c2e1",
        ),
        approved_artifacts=[
            ApprovedArtifact(
                id="APR-0001",
                kind=ApprovedArtifactKind.MECHANIC_SPEC,
                title="Movement spec",
                status=ApprovalStatus.APPROVED,
                scope="FEAT-0001",
                version=1,
                approved_by=Actor(role=AgentRole.USER),
                approved_at=AT,
                related_requirements=[],
                payload_paths=["spec.md"],
                content_sha256="ab" * 32,
            )
        ],
        decisions=[
            Decision(
                id="DEC-0001",
                category=DecisionCategory.TECH,
                status=DecisionStatus.ACCEPTED,
                topic="Movement state machine",
                participants=[AgentRole.LEAD_DEV],
                positions=[],
                evidence_ids=[],
                outcome="Use a state machine",
                owner=AgentRole.LEAD_DEV,
                rationale="Predictable",
                alternatives=[],
                affected_systems=["movement"],
                related_work_items=["FEAT-0001"],
                autonomy_level=AutonomyLevel.MULTI_AGENT,
                decided_at=AT,
            )
        ],
        skills=[
            Skill.model_validate(
                {
                    "name": "git-hygiene",
                    "version": "1.0",
                    "description": "Commit hygiene",
                    "scope": LearningScope.KERNEL,
                    "body_markdown": "Small commits.",
                    "source_path": "walk/skills/builtin/git-hygiene/SKILL.md",
                }
            )
        ],
        allowed_tools=[ToolSpec(name="read", kind=ToolKind.PROVIDER_NATIVE, description="Read")],
        permissions=constitution.tool_permissions,
        budget=[
            Budget(
                id="TASK:STORY-0001:COST_USD",
                scope=BudgetScope.TASK,
                scope_id="STORY-0001",
                dimension=BudgetDimension.COST_USD,
                limit=15.0,
                updated_at=AT,
            )
        ],
        effort=Effort.MEDIUM,
        required_evidence=[EvidenceKind.AUTOMATED_TEST],
        expected_output=ExpectedOutput(
            status_options=[AgentOutputStatus.COMPLETED, AgentOutputStatus.PARTIAL],
            deliverables=["passing EditMode tests"],
            required_evidence=[EvidenceKind.AUTOMATED_TEST],
        ),
        handover=handover,
        worktree_path="/repo/.walk/worktrees/RUN1",
        branch="feat/STORY-0001-run",
    )
