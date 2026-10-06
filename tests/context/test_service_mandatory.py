import json
import logging
import re
from datetime import UTC, datetime, timedelta

import pytest

from tests.context.conftest import (
    HEAD,
    WRITER,
    ManagerFactory,
    draft,
    story_under_feature,
    write_feature_doc,
    write_project_doc,
)
from tests.fakes.fake_clock import FakeClock
from walk.common.enums import Effort
from walk.common.models import Actor
from walk.common.roles import AgentRole
from walk.context import (
    MANDATORY_ORDER,
    PROJECT_CONTEXT_SECTIONS,
    ContextItemKind,
    ContextManager,
    ContextRequest,
)
from walk.decisions import AutonomyLevel, Decision, DecisionCategory, DecisionStatus
from walk.hooks import HookContext, HookName
from walk.memory import (
    ApprovalStatus,
    ApprovedArtifact,
    ApprovedArtifactKind,
    DefaultMemoryManager,
    FreshnessAssessment,
    FreshnessStatus,
    MemoryDocType,
    MemoryDocument,
    skeleton_for,
)
from walk.persistence import Database, UnitOfWork
from walk.telemetry import DefaultLedgerManager, LedgerEventKind
from walk.workflow import (
    BugDraft,
    DefaultWorkflowManager,
    Severity,
    StoryContract,
    Task,
    TransitionSource,
    WorkflowRepository,
    WorkItem,
    WorkItemKind,
    WorkItemState,
    WorkItemTransition,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _request(item_id: str, budget: int = 50_000) -> ContextRequest:
    return ContextRequest(
        work_item_id=item_id, role=AgentRole.SENIOR_DEV, effort=Effort.MEDIUM, token_budget=budget
    )


def _kinds(ids: list[str]) -> list[str]:
    return [item_id.split(":", 1)[0] for item_id in ids]


async def test_build_includes_mandatory_items_in_order(
    make_manager: ManagerFactory,
    workflow: DefaultWorkflowManager,
    memory: DefaultMemoryManager,
    fake_clock: FakeClock,
) -> None:
    story_id = await story_under_feature(workflow)
    await write_feature_doc(memory, fake_clock)
    await write_project_doc(memory, fake_clock)
    manager: ContextManager = make_manager()

    bundle = await manager.build(_request(story_id))

    assert [item.id for item in bundle.items] == [
        "WORK_ITEM:STORY-0001",
        "WORKFLOW_STATE:STORY-0001",
        "FEATURE_CONTEXT:FEAT-0001",
        "PROJECT_CONTEXT:project",
    ]
    assert all(item.mandatory and item.score == 1.0 for item in bundle.items)
    work_item = json.loads(bundle.items[0].content)
    assert work_item["id"] == "STORY-0001"
    assert work_item["contract"]["goal"] == "Run"
    feature = bundle.items[2]
    assert "Walk and run." in feature.content
    assert feature.source_path == ".ai/features/FEAT-0001.md"
    project = bundle.items[3].content
    for name in PROJECT_CONTEXT_SECTIONS:
        assert f"## {name}\n\n{name} body." in project
    for excluded in ("Platforms", "Performance Targets", "Art Direction", "Known Limitations"):
        assert excluded not in project
    assert bundle.head_commit == HEAD
    assert bundle.built_at == fake_clock.now()
    assert bundle.excluded_count == 0
    assert bundle.total_tokens_estimate == sum(item.tokens_estimate for item in bundle.items)
    assert all(item.tokens_estimate > 0 for item in bundle.items)
    assert bundle.request == _request(story_id)


async def test_build_without_project_document_omits_project_item(
    make_manager: ManagerFactory, workflow: DefaultWorkflowManager
) -> None:
    await workflow.create(draft(WorkItemKind.EPIC, "Core"), actor=AgentRole.USER, phase_id=None)

    bundle = await make_manager().build(_request("EPIC-001"))

    assert _kinds([item.id for item in bundle.items]) == ["WORK_ITEM", "WORKFLOW_STATE"]


async def test_build_includes_open_handover(
    make_manager: ManagerFactory, workflow: DefaultWorkflowManager, fake_clock: FakeClock
) -> None:
    story_id = await story_under_feature(workflow)
    handover = skeleton_for(MemoryDocType.HANDOVER, "HO-0001", "Handover", WRITER, fake_clock.now())
    handover.sections["Next Action"] = "Finish the run animation."
    asked: list[str] = []

    async def lookup(work_item_id: str) -> MemoryDocument | None:
        asked.append(work_item_id)
        return handover

    bundle = await make_manager(handovers=lookup).build(_request(story_id))

    ids = [item.id for item in bundle.items]
    assert ids[:3] == ["WORK_ITEM:STORY-0001", "WORKFLOW_STATE:STORY-0001", "HANDOVER:HO-0001"]
    assert "Finish the run animation." in bundle.items[2].content
    assert bundle.items[2].kind is ContextItemKind.HANDOVER
    assert asked == ["STORY-0001"]


async def test_missing_feature_context_is_explicit(
    make_manager: ManagerFactory, workflow: DefaultWorkflowManager
) -> None:
    story_id = await story_under_feature(workflow)

    bundle = await make_manager().build(_request(story_id))

    feature = next(item for item in bundle.items if item.kind is ContextItemKind.FEATURE_CONTEXT)
    assert feature.content == "(no context document yet for FEAT-0001)"
    assert feature.source_path is None
    assert feature.mandatory


async def test_feature_item_uses_its_own_context(
    make_manager: ManagerFactory,
    workflow: DefaultWorkflowManager,
    memory: DefaultMemoryManager,
    fake_clock: FakeClock,
) -> None:
    await story_under_feature(workflow)
    await write_feature_doc(memory, fake_clock)

    bundle = await make_manager().build(_request("FEAT-0001"))

    assert _kinds([item.id for item in bundle.items]) == [
        "WORK_ITEM",
        "WORKFLOW_STATE",
        "FEATURE_CONTEXT",
    ]


async def test_task_under_epic_feature_chain_finds_nearest_feature(
    make_manager: ManagerFactory, workflow: DefaultWorkflowManager
) -> None:
    await workflow.create(draft(WorkItemKind.EPIC, "Core"), actor=AgentRole.USER, phase_id=None)
    await workflow.create(
        draft(WorkItemKind.FEATURE, "Movement", "EPIC-001"), actor=AgentRole.USER, phase_id=None
    )
    await workflow.create(
        draft(WorkItemKind.TASK, "Tune", "FEAT-0001"), actor=AgentRole.USER, phase_id=None
    )

    bundle = await make_manager().build(_request("TASK-0001"))

    assert "FEATURE_CONTEXT:FEAT-0001" in [item.id for item in bundle.items]


async def test_bug_includes_bug_then_feature_context(
    make_manager: ManagerFactory,
    workflow: DefaultWorkflowManager,
    memory: DefaultMemoryManager,
    fake_clock: FakeClock,
) -> None:
    await story_under_feature(workflow)
    await write_feature_doc(memory, fake_clock)
    bug = await workflow.create(
        BugDraft(
            title="Run stutters",
            severity=Severity.MAJOR,
            reproduction="hold shift",
            expected="smooth",
            observed="stutter",
            related_feature_id="FEAT-0001",
        ),
        actor=AgentRole.QC,
        phase_id=None,
    )
    lonely = await workflow.create(
        BugDraft(
            title="Crash", severity=Severity.MINOR, reproduction="r", expected="e", observed="o"
        ),
        actor=AgentRole.QC,
        phase_id=None,
    )
    manager = make_manager()

    bundle = await manager.build(_request(bug.id))
    alone = await manager.build(_request(lonely.id))

    assert _kinds([item.id for item in bundle.items]) == [
        "WORK_ITEM",
        "WORKFLOW_STATE",
        "BUG_CONTEXT",
        "FEATURE_CONTEXT",
    ]
    assert bundle.items[2].content == f"(no context document yet for {bug.id})"
    assert "Walk and run." in bundle.items[3].content
    assert _kinds([item.id for item in alone.items]) == [
        "WORK_ITEM",
        "WORKFLOW_STATE",
        "BUG_CONTEXT",
    ]


async def test_stale_item_flagged_and_hook_fired(
    make_manager: ManagerFactory,
    workflow: DefaultWorkflowManager,
    memory: DefaultMemoryManager,
    *,
    ledger: DefaultLedgerManager,
    fake_clock: FakeClock,
    stale_fired: list[HookContext],
) -> None:
    story_id = await story_under_feature(workflow)
    await write_feature_doc(memory, fake_clock)
    await write_project_doc(memory, fake_clock)
    probed: list[tuple[str, str]] = []

    async def probe(doc: MemoryDocument, head: str) -> FreshnessAssessment | None:
        probed.append((doc.front_matter.id, head))
        if doc.front_matter.id == "project":
            return FreshnessAssessment(
                status=FreshnessStatus.CURRENT,
                reason="fresh",
                assessed_against=head,
                assessed_at=T0,
            )
        return FreshnessAssessment(
            status=FreshnessStatus.POSSIBLY_STALE,
            reason="relevant files changed",
            changed_relevant_files=["Assets/Run.cs"],
            assessed_against=head,
            assessed_at=T0,
        )

    bundle = await make_manager(freshness=probe).build(_request(story_id))

    feature = next(item for item in bundle.items if item.kind is ContextItemKind.FEATURE_CONTEXT)
    project = next(item for item in bundle.items if item.kind is ContextItemKind.PROJECT_CONTEXT)
    assert feature.requires_verification
    assert feature.freshness is not None
    assert feature.freshness.status is FreshnessStatus.POSSIBLY_STALE
    assert not project.requires_verification
    assert project.freshness is not None
    assert bundle.ref().stale_item_ids == ["FEATURE_CONTEXT:FEAT-0001"]
    assert sorted(probed) == [("FEAT-0001", HEAD), ("project", HEAD)]
    assert len(stale_fired) == 1
    fired = stale_fired[0]
    assert fired.name is HookName.ON_CONTEXT_STALE
    assert fired.work_item_id == "STORY-0001"
    assert fired.role is AgentRole.SENIOR_DEV
    assert fired.payload == {
        "doc_id": "FEAT-0001",
        "status": "POSSIBLY_STALE",
        "reason": "relevant files changed",
    }
    assert await ledger.query(kinds=[LedgerEventKind.CONTEXT_FRESHNESS]) == []


async def test_decisions_and_artifact_metadata_included(
    make_manager: ManagerFactory, workflow: DefaultWorkflowManager
) -> None:
    story_id = await story_under_feature(workflow)
    accepted = Decision(
        id="DEC-0001",
        category=DecisionCategory.TECH,
        status=DecisionStatus.ACCEPTED,
        topic="Use a state machine for movement",
        participants=[AgentRole.LEAD_DEV],
        positions=[],
        evidence_ids=[],
        outcome="State machine",
        owner=AgentRole.LEAD_DEV,
        rationale="Predictable transitions",
        alternatives=["Flags"],
        affected_systems=["movement"],
        related_work_items=["FEAT-0001"],
        autonomy_level=AutonomyLevel.MULTI_AGENT,
        decided_at=T0,
    )
    proposed = accepted.model_copy(update={"id": "DEC-0002", "status": DecisionStatus.PROPOSED})
    artifact = ApprovedArtifact(
        id="APR-0001",
        kind=ApprovedArtifactKind.MECHANIC_SPEC,
        title="Movement spec",
        status=ApprovalStatus.APPROVED,
        scope="FEAT-0001",
        version=2,
        approved_by=Actor(role=AgentRole.USER),
        approved_at=T0,
        related_requirements=[],
        payload_paths=["spec.pdf"],
        content_sha256="ab" * 32,
    )
    asked: list[tuple[str, list[str]]] = []

    async def decisions(item: WorkItem, systems: list[str]) -> list[Decision]:
        asked.append((item.id, systems))
        return [proposed, accepted]

    async def artifacts(item: WorkItem) -> list[ApprovedArtifact]:
        del item
        return [artifact]

    bundle = await make_manager(decisions=decisions, artifacts=artifacts).build(_request(story_id))

    ids = [item.id for item in bundle.items]
    assert ids[-2:] == ["DECISION:DEC-0001", "APPROVED_ARTIFACT:APR-0001"]
    assert "DECISION:DEC-0002" not in ids
    assert asked == [("STORY-0001", [])]
    decision = bundle.items[-2]
    assert "Use a state machine for movement" in decision.content
    assert "Predictable transitions" in decision.content
    metadata = json.loads(bundle.items[-1].content)
    assert metadata == {
        "content_sha256": "ab" * 32,
        "id": "APR-0001",
        "kind": "MECHANIC_SPEC",
        "scope": "FEAT-0001",
        "status": "APPROVED",
        "title": "Movement spec",
        "version": 2,
    }
    assert "payload" not in bundle.items[-1].content


async def test_workflow_state_lists_recent_transitions(
    make_manager: ManagerFactory, workflow: DefaultWorkflowManager, db: Database
) -> None:
    story_id = await story_under_feature(workflow)
    repo = WorkflowRepository(db)
    async with UnitOfWork(db) as uow:
        for n in range(7):
            await repo.add_transition(
                WorkItemTransition(
                    seq=0,
                    work_item_id=story_id,
                    from_state=WorkItemState.IDEA,
                    to_state=WorkItemState.READY,
                    event=f"event{n}",
                    source=TransitionSource.KERNEL,
                    actor_role=AgentRole.ORCHESTRATOR,
                    at=T0 + timedelta(minutes=n),
                ),
                uow,
            )

    bundle = await make_manager().build(_request(story_id))

    state = bundle.items[1]
    assert state.kind is ContextItemKind.WORKFLOW_STATE
    assert "state: IDEA" in state.content
    assert "fix_loops: 0" in state.content
    rows = [line for line in state.content.splitlines() if re.match(r"^\| \d", line)]
    assert [row.split("|")[5].strip() for row in rows] == [f"event{n}" for n in (6, 5, 4, 3, 2)]


async def test_workflow_state_without_transitions(
    make_manager: ManagerFactory, workflow: DefaultWorkflowManager
) -> None:
    story_id = await story_under_feature(workflow)

    bundle = await make_manager().build(_request(story_id))

    assert "(no transitions yet)" in bundle.items[1].content


async def test_mandatory_items_never_trimmed(
    make_manager: ManagerFactory,
    workflow: DefaultWorkflowManager,
    memory: DefaultMemoryManager,
    fake_clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    story_id = await story_under_feature(workflow)
    await write_feature_doc(memory, fake_clock)
    await write_project_doc(memory, fake_clock)

    with caplog.at_level(logging.WARNING, logger="walk.context.service"):
        bundle = await make_manager().build(_request(story_id, budget=1))

    assert len(bundle.items) == 4
    assert bundle.excluded_count == 0
    assert bundle.total_tokens_estimate > 1
    assert any("exceed" in record.getMessage() for record in caplog.records)


def test_mandatory_order_constant() -> None:
    assert MANDATORY_ORDER == (
        ContextItemKind.WORK_ITEM,
        ContextItemKind.WORKFLOW_STATE,
        ContextItemKind.HANDOVER,
        ContextItemKind.FEATURE_CONTEXT,
        ContextItemKind.BUG_CONTEXT,
        ContextItemKind.PROJECT_CONTEXT,
        ContextItemKind.DECISION,
        ContextItemKind.APPROVED_ARTIFACT,
    )


def test_manager_token_budget_delegates(make_manager: ManagerFactory) -> None:
    assert make_manager().token_budget_for(Effort.HIGH, 200_000, 16_000) == 84_000


async def test_nested_item_walks_up_to_the_feature(
    make_manager: ManagerFactory, workflow: DefaultWorkflowManager, db: Database
) -> None:
    story_id = await story_under_feature(workflow)
    nested = Task(
        id="TASK-0009",
        project_key="DEMO",
        title="Nested",
        parent_id=story_id,
        contract=StoryContract(goal="nested"),
        created_at=T0,
        updated_at=T0,
    )
    async with UnitOfWork(db) as uow:
        await WorkflowRepository(db).insert(nested, uow)

    bundle = await make_manager().build(_request("TASK-0009"))

    assert "FEATURE_CONTEXT:FEAT-0001" in [item.id for item in bundle.items]
