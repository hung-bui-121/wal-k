from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.persistence import Database, IdSequenceStore, UnitOfWork
from walk.telemetry import DefaultLedgerManager, LedgerEvent, LedgerEventKind, LedgerRepository
from walk.workflow import (
    TABLES_DIR,
    Bug,
    BugDraft,
    DefaultWorkflowManager,
    Feature,
    Project,
    ProjectRepository,
    Severity,
    Story,
    StoryContract,
    TransitionContext,
    TransitionSource,
    WorkflowManager,
    WorkflowRepository,
    WorkItemDraft,
    WorkItemKind,
    WorkItemNotFound,
    WorkItemState,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

PM = AgentRole.PRODUCT_OWNER


class FailingLedger(DefaultLedgerManager):
    """Ledger whose append always fails, to prove the create transaction rolls back."""

    async def append(self, event: LedgerEvent, *, uow: UnitOfWork | None = None) -> LedgerEvent:
        del event, uow
        msg = "ledger down"
        raise RuntimeError(msg)


@pytest.fixture
def ledger(db: Database, fake_clock: FakeClock) -> DefaultLedgerManager:
    return DefaultLedgerManager(db, LedgerRepository(db), SequentialIdFactory(), fake_clock)


def _manager(
    db: Database, ledger: DefaultLedgerManager, clock: FakeClock, tmp_path: Path
) -> DefaultWorkflowManager:
    return DefaultWorkflowManager(
        db,
        WorkflowRepository(db),
        ProjectRepository(db),
        IdSequenceStore(db),
        ledger,
        DefaultHookManager(HookExecutionRepository(db), ledger, clock),
        clock,
        TABLES_DIR,
    )


@pytest.fixture
def workflow(
    db: Database,
    ledger: DefaultLedgerManager,
    fake_clock: FakeClock,
    tmp_path: Path,
    project: Project,
) -> DefaultWorkflowManager:
    del project
    return _manager(db, ledger, fake_clock, tmp_path)


def _draft(
    kind: WorkItemKind, title: str, parent: str | None = None, *, contract: bool = True
) -> WorkItemDraft:
    return WorkItemDraft(
        kind=kind,
        title=title,
        description=f"{title} description",
        parent_id=parent,
        contract=StoryContract(goal=title, acceptance_criteria=["works"]) if contract else None,
    )


def _bug_draft() -> BugDraft:
    return BugDraft(
        title="Crash on load",
        severity=Severity.BLOCKER,
        reproduction="open save",
        expected="loads",
        observed="crash",
        related_feature_id="FEAT-0001",
        against_commit="abc1234",
    )


def test_default_manager_satisfies_protocol(workflow: DefaultWorkflowManager) -> None:
    protocol: WorkflowManager = workflow
    assert protocol is workflow


async def test_create_feature_allocates_id_and_logs(
    workflow: DefaultWorkflowManager, ledger: DefaultLedgerManager, fake_clock: FakeClock
) -> None:
    feature = await workflow.create(
        _draft(WorkItemKind.FEATURE, "Inventory", contract=False), actor=PM, phase_id=None
    )
    assert isinstance(feature, Feature)
    assert feature.id == "FEAT-0001"
    assert feature.state is WorkItemState.IDEA
    assert feature.project_key == "DEMO"
    assert feature.description == "Inventory description"
    assert feature.created_at == fake_clock.now()
    assert await workflow.get("FEAT-0001") == feature
    events = await ledger.query(kinds=[LedgerEventKind.WORK_ITEM_CREATED])
    assert len(events) == 1
    assert events[0].work_item_id == "FEAT-0001"
    assert events[0].actor_role is PM
    assert events[0].payload == {"kind": "FEATURE", "title": "Inventory", "parent_id": None}


async def test_create_story_under_feature(workflow: DefaultWorkflowManager) -> None:
    await workflow.create(
        _draft(WorkItemKind.FEATURE, "F", contract=False), actor=PM, phase_id=None
    )
    story = await workflow.create(
        _draft(WorkItemKind.STORY, "S", "FEAT-0001"), actor=PM, phase_id=None
    )
    assert isinstance(story, Story)
    assert story.id == "STORY-0001"
    assert story.parent_id == "FEAT-0001"
    assert story.owner_role is AgentRole.SENIOR_DEV
    task = await workflow.create(
        _draft(WorkItemKind.TASK, "T", "FEAT-0001"), actor=PM, phase_id=None
    )
    assert task.id == "TASK-0001"


async def test_create_epic_and_feature_under_epic(workflow: DefaultWorkflowManager) -> None:
    epic = await workflow.create(
        _draft(WorkItemKind.EPIC, "E", contract=False), actor=PM, phase_id=None
    )
    assert epic.id == "EPIC-001"
    feature = await workflow.create(
        _draft(WorkItemKind.FEATURE, "F", epic.id, contract=False), actor=PM, phase_id=None
    )
    assert feature.parent_id == "EPIC-001"


async def test_create_rejects_invalid_parent_kind(workflow: DefaultWorkflowManager) -> None:
    await workflow.create(_draft(WorkItemKind.EPIC, "E", contract=False), actor=PM, phase_id=None)
    with pytest.raises(ConfigError, match="parent"):
        await workflow.create(_draft(WorkItemKind.STORY, "S", "EPIC-001"), actor=PM, phase_id=None)
    with pytest.raises(ConfigError, match="parent"):
        await workflow.create(_draft(WorkItemKind.STORY, "S"), actor=PM, phase_id=None)
    with pytest.raises(ConfigError, match="parent"):
        await workflow.create(
            _draft(WorkItemKind.EPIC, "E2", "EPIC-001", contract=False), actor=PM, phase_id=None
        )
    with pytest.raises(WorkItemNotFound):
        await workflow.create(
            _draft(WorkItemKind.FEATURE, "F", "EPIC-009", contract=False), actor=PM, phase_id=None
        )
    assert [item.id for item in await workflow.query()] == ["EPIC-001"]


async def test_create_story_requires_contract(workflow: DefaultWorkflowManager) -> None:
    await workflow.create(
        _draft(WorkItemKind.FEATURE, "F", contract=False), actor=PM, phase_id=None
    )
    with pytest.raises(ConfigError, match="contract"):
        await workflow.create(
            _draft(WorkItemKind.STORY, "S", "FEAT-0001", contract=False), actor=PM, phase_id=None
        )
    with pytest.raises(ConfigError, match="contract"):
        await workflow.create(_draft(WorkItemKind.FEATURE, "F2"), actor=PM, phase_id=None)


async def test_create_rejects_bug_kind_work_item_draft(workflow: DefaultWorkflowManager) -> None:
    with pytest.raises(ConfigError, match="BugDraft"):
        await workflow.create(_draft(WorkItemKind.BUG, "B"), actor=PM, phase_id=None)


async def test_create_rejects_unknown_phase(workflow: DefaultWorkflowManager) -> None:
    with pytest.raises(ConfigError, match="PHASE-01"):
        await workflow.create(
            _draft(WorkItemKind.FEATURE, "F", contract=False), actor=PM, phase_id="PHASE-01"
        )


async def test_create_bug_from_draft(
    workflow: DefaultWorkflowManager, ledger: DefaultLedgerManager
) -> None:
    await workflow.create(
        _draft(WorkItemKind.FEATURE, "F", contract=False), actor=PM, phase_id=None
    )
    bug = await workflow.create(_bug_draft(), actor=AgentRole.QC, phase_id=None)
    assert isinstance(bug, Bug)
    assert bug.id == "BUG-0001"
    assert bug.severity is Severity.BLOCKER
    assert bug.owner_role is None
    assert bug.contract.goal == "Crash on load"
    assert (bug.reproduction, bug.expected, bug.observed) == ("open save", "loads", "crash")
    assert bug.related_feature_id == "FEAT-0001"
    assert bug.found_against_commit == "abc1234"
    assert bug.parent_id is None
    assert isinstance(await workflow.get("BUG-0001"), Bug)
    events = await ledger.query(kinds=[LedgerEventKind.WORK_ITEM_CREATED], work_item_id=bug.id)
    assert events[0].payload == {"kind": "BUG", "title": "Crash on load", "parent_id": None}


async def test_create_bug_rejects_unknown_related_feature(
    workflow: DefaultWorkflowManager,
) -> None:
    with pytest.raises(WorkItemNotFound):
        await workflow.create(_bug_draft(), actor=AgentRole.QC, phase_id=None)


async def test_create_is_atomic_with_ledger(
    db: Database, fake_clock: FakeClock, tmp_path: Path, project: Project
) -> None:
    del project
    failing = FailingLedger(db, LedgerRepository(db), SequentialIdFactory(), fake_clock)
    workflow = _manager(db, failing, fake_clock, tmp_path)
    with pytest.raises(RuntimeError, match="ledger down"):
        await workflow.create(
            _draft(WorkItemKind.FEATURE, "F", contract=False), actor=PM, phase_id=None
        )
    assert await workflow.query() == []
    assert db.connect().execute("SELECT COUNT(*) FROM id_sequences").fetchone()[0] == 0


async def test_create_requires_a_project(
    db: Database, ledger: DefaultLedgerManager, fake_clock: FakeClock, tmp_path: Path
) -> None:
    workflow = _manager(db, ledger, fake_clock, tmp_path)
    with pytest.raises(ConfigError, match="project"):
        await workflow.create(
            _draft(WorkItemKind.FEATURE, "F", contract=False), actor=PM, phase_id=None
        )


async def test_get_unknown_raises(workflow: DefaultWorkflowManager) -> None:
    with pytest.raises(WorkItemNotFound) as raised:
        await workflow.get("STORY-9999")
    assert raised.value.detail == {"work_item_id": "STORY-9999"}


async def test_query_filters(workflow: DefaultWorkflowManager, fake_clock: FakeClock) -> None:
    await workflow.create(
        _draft(WorkItemKind.FEATURE, "F", contract=False), actor=PM, phase_id=None
    )
    for title in ("S1", "S2"):
        fake_clock.advance(1)
        await workflow.create(
            _draft(WorkItemKind.STORY, title, "FEAT-0001"), actor=PM, phase_id=None
        )
    fake_clock.advance(1)
    await workflow.create(_draft(WorkItemKind.TASK, "T1", "FEAT-0001"), actor=PM, phase_id=None)
    stories = await workflow.query(states=[WorkItemState.IDEA], kinds=[WorkItemKind.STORY])
    assert [item.id for item in stories] == ["STORY-0001", "STORY-0002"]
    assert await workflow.query(states=[WorkItemState.READY]) == []
    children = await workflow.query(parent_id="FEAT-0001", kinds=[WorkItemKind.TASK])
    assert [item.id for item in children] == ["TASK-0001"]
    assert await workflow.query(phase_id="PHASE-01") == []
    assert len(await workflow.query()) == 4


@pytest.mark.parametrize(
    ("method", "story"),
    [
        ("phase_event", "E01-S11"),
        ("rc_event", "E01-S11"),
        ("children_states", "E03-S17"),
        ("open_blocker_bug_count", "E03-S17"),
        ("gdd_coverage", "E06-S06"),
    ],
)
async def test_deferred_methods_name_their_story(
    workflow: DefaultWorkflowManager, method: str, story: str
) -> None:
    ctx = TransitionContext(actor_role=AgentRole.USER, source=TransitionSource.USER)
    calls: dict[str, Callable[[], Awaitable[object]]] = {
        "phase_event": lambda: workflow.phase_event("PHASE-01", "start", ctx),
        "rc_event": lambda: workflow.rc_event("RC-01", "qc_passed", ctx),
        "children_states": lambda: workflow.children_states("FEAT-0001"),
        "open_blocker_bug_count": lambda: workflow.open_blocker_bug_count("FEAT-0001"),
        "gdd_coverage": lambda: workflow.gdd_coverage("DEMO"),
    }
    with pytest.raises(ConfigError, match=story):
        await calls[method]()
