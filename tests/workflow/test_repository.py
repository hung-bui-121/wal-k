import itertools
from datetime import UTC, datetime, timedelta

import pytest

from tests.fakes.fake_clock import FakeClock
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.persistence import Database, IdSequenceStore, UnitOfWork
from walk.telemetry import DefaultLedgerManager, LedgerRepository
from walk.workflow import (
    TABLES_DIR,
    Bug,
    DefaultWorkflowManager,
    Feature,
    Project,
    ProjectRepository,
    Story,
    StoryContract,
    TransitionSource,
    WorkflowRepository,
    WorkItem,
    WorkItemNotFound,
    WorkItemState,
    WorkItemTransition,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def items(db: Database) -> WorkflowRepository:
    return WorkflowRepository(db)


def _feature(n: int, **fields: object) -> Feature:
    at = T0 + timedelta(minutes=n)
    return Feature.model_validate(
        {
            "id": f"FEAT-{n:04d}",
            "project_key": "DEMO",
            "title": f"Feature {n}",
            "created_at": at,
            "updated_at": at,
            **fields,
        }
    )


def _story(n: int, parent: str) -> Story:
    at = T0 + timedelta(minutes=10 + n)
    return Story(
        id=f"STORY-{n:04d}",
        project_key="DEMO",
        title=f"Story {n}",
        parent_id=parent,
        contract=StoryContract(goal=f"goal {n}"),
        created_at=at,
        updated_at=at,
    )


async def _insert(db: Database, repo: WorkflowRepository, *objs: WorkItem) -> None:
    async with UnitOfWork(db) as uow:
        for obj in objs:
            await repo.insert(obj, uow)


async def test_insert_and_get_feature(
    db: Database, items: WorkflowRepository, project: Project
) -> None:
    feature = _feature(1, state=WorkItemState.DESIGN, external_ref="LOCAL-1")
    await _insert(db, items, feature)
    assert await items.get("FEAT-0001") == feature
    row = (
        db.connect()
        .execute(
            "SELECT kind, project_key, state, state_version, title, priority, risk, fix_loops, "
            "created_at FROM work_items"
        )
        .fetchone()
    )
    assert tuple(row) == (
        "FEATURE",
        project.key,
        "DESIGN",
        0,
        "Feature 1",
        "P2",
        "MEDIUM",
        0,
        "2026-01-01T00:01:00.000000+00:00",
    )


async def test_get_restores_subclass(
    db: Database, items: WorkflowRepository, project: Project
) -> None:
    del project
    bug = Bug(
        id="BUG-0001",
        project_key="DEMO",
        title="Crash",
        contract=StoryContract(goal="Crash"),
        created_at=T0,
        updated_at=T0,
    )
    await _insert(db, items, bug)
    restored = await items.get("BUG-0001")
    assert isinstance(restored, Bug)
    assert await items.get("BUG-0002") is None


async def test_by_external_ref(db: Database, items: WorkflowRepository, project: Project) -> None:
    del project
    await _insert(db, items, _feature(1, external_ref="LOCAL-1"), _feature(2))
    found = await items.by_external_ref("LOCAL-1")
    assert found is not None
    assert found.id == "FEAT-0001"
    assert await items.by_external_ref("LOCAL-9") is None


async def test_children_returns_direct_children(
    db: Database, items: WorkflowRepository, project: Project
) -> None:
    del project
    await _insert(
        db,
        items,
        _feature(1),
        _feature(2),
        _story(2, "FEAT-0001"),
        _story(1, "FEAT-0001"),
        _story(3, "FEAT-0002"),
    )
    children = await items.children("FEAT-0001")
    assert [child.id for child in children] == ["STORY-0001", "STORY-0002"]
    assert await items.children("STORY-0001") == []


async def test_project_repository_round_trip_and_single(db: Database) -> None:
    projects = ProjectRepository(db)
    with pytest.raises(ConfigError, match="found 0"):
        await projects.single()
    demo = Project(key="DEMO", name="Demo", repo_path="/repo", created_at=T0)
    async with UnitOfWork(db) as uow:
        await projects.insert(demo, uow)
    assert await projects.get("DEMO") == demo
    assert await projects.single() == demo
    other = Project(key="OTHER", name="Other", repo_path="/other", created_at=T0)
    async with UnitOfWork(db) as uow:
        await projects.insert(other, uow)
    with pytest.raises(ConfigError, match="found 2"):
        await projects.single()


async def test_transitions_returns_newest_first(
    db: Database, items: WorkflowRepository, project: Project
) -> None:
    del project
    await _insert(db, items, _feature(1))
    states = [WorkItemState.IDEA, WorkItemState.READY, WorkItemState.IMPLEMENTING]
    async with UnitOfWork(db) as uow:
        for n, (before, after) in enumerate(itertools.pairwise(states)):
            row = WorkItemTransition(
                seq=0,
                work_item_id="FEAT-0001",
                from_state=before,
                to_state=after,
                event=f"e{n}",
                source=TransitionSource.KERNEL,
                actor_role=AgentRole.ORCHESTRATOR,
                at=T0 + timedelta(minutes=n),
            )
            await items.add_transition(row, uow)
        await items.add_transition(
            row.model_copy(update={"event": "e2", "at": T0 + timedelta(minutes=5)}), uow
        )

    newest = await items.transitions("FEAT-0001", limit=2)
    default = await items.transitions("FEAT-0001")
    everything = await items.transitions("FEAT-0001", limit=None)

    assert [t.event for t in newest] == ["e2", "e1"]
    assert newest[0].seq > newest[1].seq
    assert [t.event for t in default] == ["e2", "e1", "e0"]
    assert [t.event for t in everything] == ["e2", "e1", "e0"]
    assert await items.transitions("FEAT-0002") == []


async def test_set_assigned_run_round_trip(
    db: Database, items: WorkflowRepository, project: Project, fake_clock: FakeClock
) -> None:
    del project
    story = _story(1, "FEAT-0001").model_copy(update={"state": WorkItemState.READY})
    await _insert(db, items, _feature(1), story)
    ledger = DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), fake_clock)
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)
    workflow = DefaultWorkflowManager(
        db,
        items,
        ProjectRepository(db),
        IdSequenceStore(db),
        ledger,
        hooks,
        fake_clock,
        TABLES_DIR,
    )
    run_id = "RUN-01J0000000000000000000000A"

    assigned = await items.set_assigned_run("STORY-0001", run_id)
    stored = await items.get("STORY-0001")
    ready_while_assigned = [item.id for item in await workflow.ready_items(None)]
    async with UnitOfWork(db) as uow:
        cleared = await items.set_assigned_run("STORY-0001", None, conn=uow.conn)
    ready_after = [item.id for item in await workflow.ready_items(None)]
    column = db.connect().execute("SELECT assigned_run_id FROM work_items WHERE id = 'STORY-0001'")

    assert assigned.assigned_run_id == run_id
    assert stored is not None
    assert stored.assigned_run_id == run_id
    assert stored.state is WorkItemState.READY
    assert "STORY-0001" not in ready_while_assigned
    assert cleared.assigned_run_id is None
    assert column.fetchone()[0] is None
    assert "STORY-0001" in ready_after


async def test_set_assigned_run_unknown_item_raises(
    db: Database, items: WorkflowRepository
) -> None:
    with pytest.raises(WorkItemNotFound):
        await items.set_assigned_run("STORY-0099", None)
