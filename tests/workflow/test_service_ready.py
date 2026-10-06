from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from walk.common.errors import ConfigError, GuardRejected
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.persistence import Database, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerEventKind, LedgerRepository
from walk.workflow import (
    TABLES_DIR,
    Bug,
    BugDraft,
    DefaultWorkflowManager,
    DoneDimension,
    Feature,
    Priority,
    Project,
    ProjectRepository,
    Severity,
    StoryContract,
    TransitionContext,
    TransitionSource,
    UnknownTransition,
    WorkflowRepository,
    WorkItemDraft,
    WorkItemKind,
    WorkItemNotFound,
    WorkItemState,
)

NOW = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def ledger(db: Database, fake_clock: FakeClock) -> DefaultLedgerManager:
    return DefaultLedgerManager(db, LedgerRepository(db), SequentialIdFactory(), fake_clock)


@pytest.fixture
def workflow(
    db: Database, ledger: DefaultLedgerManager, fake_clock: FakeClock, project: Project
) -> DefaultWorkflowManager:
    del project
    return DefaultWorkflowManager(
        db,
        WorkflowRepository(db),
        ProjectRepository(db),
        IdSequenceStore(db),
        ledger,
        DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock),
        fake_clock,
        TABLES_DIR,
    )


def _set(db: Database, item_id: str, **fields: object) -> None:
    """Force item fields (state, priority, ...) in both the JSON and the projection columns."""
    for column, value in fields.items():
        db.connect().execute(
            f"UPDATE work_items SET json = json_set(json, '$.{column}', ?) WHERE id = ?",  # noqa: S608 - test helper, fixed names
            (value, item_id),
        )
        if column in {"state", "priority", "assigned_run_id", "phase_id"}:
            db.connect().execute(
                f"UPDATE work_items SET {column} = ? WHERE id = ?",  # noqa: S608 - test helper
                (value, item_id),
            )


def _ctx(role: AgentRole, **payload: object) -> TransitionContext:
    source = TransitionSource.USER if role is AgentRole.USER else TransitionSource.AGENT
    return TransitionContext(actor_role=role, source=source, payload=payload)


async def _feature(workflow: DefaultWorkflowManager) -> Feature:
    feature = await workflow.create(
        WorkItemDraft(kind=WorkItemKind.FEATURE, title="F", description="d"),
        actor=AgentRole.PRODUCT_OWNER,
        phase_id=None,
    )
    assert isinstance(feature, Feature)
    return feature


async def _story(
    workflow: DefaultWorkflowManager,
    fake_clock: FakeClock,
    *,
    deps: list[str] | None = None,
    phase_id: str | None = None,
) -> str:
    fake_clock.advance(1)
    story = await workflow.create(
        WorkItemDraft(
            kind=WorkItemKind.STORY,
            title="S",
            description="",
            parent_id="FEAT-0001",
            contract=StoryContract(
                goal="g", acceptance_criteria=["a"], complexity="SMALL", dependencies=deps or []
            ),
        ),
        actor=AgentRole.PRODUCT_OWNER,
        phase_id=phase_id,
    )
    return story.id


async def test_ready_items_filters_and_orders(
    workflow: DefaultWorkflowManager, db: Database, fake_clock: FakeClock
) -> None:
    await _feature(workflow)
    _set(db, "FEAT-0001", state="IMPLEMENTING")
    low = await _story(workflow, fake_clock)
    idea = await _story(workflow, fake_clock)
    high = await _story(workflow, fake_clock)
    blocked = await _story(workflow, fake_clock)
    waiting = await _story(workflow, fake_clock, deps=[idea])
    running = await _story(workflow, fake_clock)
    for item_id in (low, high, waiting, running):
        _set(db, item_id, state="READY")
    _set(db, low, priority="P1")
    _set(db, high, priority="P0")
    _set(db, blocked, state="BLOCKED")
    _set(db, running, assigned_run_id="RUN-01J00000000000000000000000")
    ready = await workflow.ready_items(None)
    assert [item.id for item in ready] == [high, low]
    _set(db, idea, state="COMPLETE")
    assert [item.id for item in await workflow.ready_items(None)] == [high, low, waiting]
    assert ready[0].priority is Priority.P0


async def test_ready_items_respects_phase_scope(
    workflow: DefaultWorkflowManager, db: Database, fake_clock: FakeClock
) -> None:
    for ordinal in (1, 2):
        db.connect().execute(
            "INSERT INTO phases (id, project_key, ordinal, state, json, updated_at) "
            "VALUES (?, 'DEMO', ?, 'ACTIVE', '{}', ?)",
            (f"PHASE-0{ordinal}", ordinal, NOW),
        )
    await _feature(workflow)
    _set(db, "FEAT-0001", state="IMPLEMENTING")
    mine = await _story(workflow, fake_clock, phase_id="PHASE-01")
    other = await _story(workflow, fake_clock, phase_id="PHASE-02")
    free = await _story(workflow, fake_clock)
    for item_id in (mine, other, free):
        _set(db, item_id, state="READY")
    assert [item.id for item in await workflow.ready_items("PHASE-01")] == [mine, free]
    assert len(await workflow.ready_items(None)) == 3


async def test_ready_items_includes_scheduled_feature_and_bug_states(
    workflow: DefaultWorkflowManager, db: Database, fake_clock: FakeClock
) -> None:
    await _feature(workflow)
    fake_clock.advance(1)
    bug = await workflow.create(
        BugDraft(title="B", severity=Severity.MINOR, reproduction="r", expected="e", observed="o"),
        actor=AgentRole.QC,
        phase_id=None,
    )
    assert [item.id for item in await workflow.ready_items(None)] == ["FEAT-0001"]
    _set(db, bug.id, state="DISCOVERY")
    assert [item.id for item in await workflow.ready_items(None)] == ["FEAT-0001", bug.id]


async def test_set_done_dimension_updates_or_rejects(
    workflow: DefaultWorkflowManager, ledger: DefaultLedgerManager, fake_clock: FakeClock
) -> None:
    await _feature(workflow)
    before = len(await ledger.query())
    fake_clock.advance(5)
    feature = await workflow.set_done_dimension("FEAT-0001", DoneDimension.TESTED, True, None)  # noqa: FBT003 - positional per INTERFACES §1.3
    assert feature.done_dimensions == {DoneDimension.TESTED: True}
    assert feature.updated_at == fake_clock.now()
    stored = await workflow.get("FEAT-0001")
    assert isinstance(stored, Feature)
    assert stored.done_dimensions == {DoneDimension.TESTED: True}
    assert len(await ledger.query()) == before
    with pytest.raises(ConfigError, match="UX_COMPLETE"):
        await workflow.set_done_dimension("FEAT-0001", DoneDimension.UX_COMPLETE, True, None)  # noqa: FBT003 - positional per INTERFACES §1.3


async def test_set_done_dimension_requires_a_feature(workflow: DefaultWorkflowManager) -> None:
    with pytest.raises(WorkItemNotFound, match="FEAT-0009"):
        await workflow.set_done_dimension("FEAT-0009", DoneDimension.TESTED, True, None)  # noqa: FBT003 - positional per INTERFACES §1.3


async def _bug_in(workflow: DefaultWorkflowManager, db: Database, state: str) -> str:
    bug = await workflow.create(
        BugDraft(title="B", severity=Severity.MAJOR, reproduction="r", expected="e", observed="o"),
        actor=AgentRole.QC,
        phase_id=None,
    )
    _set(db, bug.id, state=state)
    return bug.id


async def test_bug_reopen_increments_count(
    workflow: DefaultWorkflowManager, db: Database, ledger: DefaultLedgerManager
) -> None:
    bug_id = await _bug_in(workflow, db, "QC")
    transition = await workflow.raise_event(bug_id, "reopen", _ctx(AgentRole.QC, max_reopen=3))
    assert transition.to_state is WorkItemState.REWORK
    bug = await workflow.get(bug_id)
    assert isinstance(bug, Bug)
    assert bug.reopen_count == 1
    assert bug.fix_loops == 0
    _set(db, bug_id, state="QC", reopen_count=3)
    blocked = await workflow.raise_event(bug_id, "reopen", _ctx(AgentRole.QC))
    assert blocked.to_state is WorkItemState.BLOCKED
    events = await ledger.query(kinds=[LedgerEventKind.WORK_ITEM_TRANSITION])
    assert events[-1].payload["kind"] == "BUG"


async def test_wont_fix_requires_quality_decision(
    workflow: DefaultWorkflowManager, db: Database
) -> None:
    bug_id = await _bug_in(workflow, db, "DISCOVERY")
    with pytest.raises(GuardRejected, match="decision_recorded_quality"):
        await workflow.raise_event(bug_id, "wont_fix", _ctx(AgentRole.PRODUCT_OWNER))
    done = await workflow.raise_event(
        bug_id,
        "wont_fix",
        _ctx(AgentRole.PRODUCT_OWNER, decision_id="DEC-0001", decision_category="QUALITY"),
    )
    assert done.to_state is WorkItemState.CANCELLED


async def test_bug_triage_flow(workflow: DefaultWorkflowManager, db: Database) -> None:
    bug_id = await _bug_in(workflow, db, "IDEA")
    await workflow.raise_event(bug_id, "triage", _ctx(AgentRole.KERNEL))
    triaged = await workflow.raise_event(
        bug_id, "triaged", _ctx(AgentRole.LEAD_DEV, severity_set=True, owner_role_set=True)
    )
    assert (triaged.from_state, triaged.to_state) == (WorkItemState.DISCOVERY, WorkItemState.READY)


async def test_check_definition_of_ready_reads_dependencies(
    workflow: DefaultWorkflowManager, db: Database, fake_clock: FakeClock
) -> None:
    await _feature(workflow)
    first = await _story(workflow, fake_clock)
    second = await _story(workflow, fake_clock, deps=[first])
    item = await workflow.get(second)
    result = workflow.check_definition_of_ready(item)
    assert (result.ok, result.reason) == (False, "dependencies_resolved")
    _set(db, first, state="COMPLETE")
    assert workflow.check_definition_of_ready(item).ok
    feature = await workflow.get("FEAT-0001")
    assert workflow.check_definition_of_ready(feature).reason == "requirement_complete"


async def test_kernel_readiness_cannot_be_overridden_by_payload(
    workflow: DefaultWorkflowManager, fake_clock: FakeClock
) -> None:
    await _feature(workflow)
    first = await _story(workflow, fake_clock)
    second = await _story(workflow, fake_clock, deps=[first])
    forged = {"definition_of_ready": {"ok": True, "reason": ""}}
    with pytest.raises(GuardRejected, match="dependencies_resolved"):
        await workflow.raise_event(second, "ready", _ctx(AgentRole.LEAD_DEV, **forged))


async def test_feature_force_review_moves_implementing_children(
    workflow: DefaultWorkflowManager, db: Database, fake_clock: FakeClock
) -> None:
    await _feature(workflow)
    _set(db, "FEAT-0001", state="IMPLEMENTING")
    busy = await _story(workflow, fake_clock)
    idle = await _story(workflow, fake_clock)
    _set(db, busy, state="IMPLEMENTING")
    _set(db, idle, state="READY")
    with pytest.raises(GuardRejected, match="has_children_implementing"):
        await workflow.raise_event(
            "FEAT-0001", "force_review", _ctx(AgentRole.USER, children_states={idle: "READY"})
        )
    states = {busy: "IMPLEMENTING", idle: "READY"}
    transition = await workflow.raise_event(
        "FEAT-0001", "force_review", _ctx(AgentRole.USER, children_states=states)
    )
    assert transition.to_state is WorkItemState.IMPLEMENTING
    feature = await workflow.get("FEAT-0001")
    assert (feature.state, feature.state_version) == (WorkItemState.IMPLEMENTING, 1)
    assert (await workflow.get(busy)).state is WorkItemState.READY_FOR_REVIEW
    assert (await workflow.get(idle)).state is WorkItemState.READY
    rows = await WorkflowRepository(db).transitions(busy)
    assert [(r.event, r.to_state) for r in rows] == [
        ("force_review", WorkItemState.READY_FOR_REVIEW)
    ]


async def test_feature_cancel_excludes_complete_and_cancelled(
    workflow: DefaultWorkflowManager, db: Database
) -> None:
    await _feature(workflow)
    _set(db, "FEAT-0001", state="CANCELLED")
    with pytest.raises(UnknownTransition, match="no transition"):
        await workflow.raise_event("FEAT-0001", "cancel", _ctx(AgentRole.USER))


@pytest.mark.parametrize(
    ("content", "fragment"),
    [
        ("- {kind: STORY, state: READY, role: JANITOR, purpose: IMPLEMENT}\n", "JANITOR"),
        ("- {kind: STORY, state: READY, role: QC, purpose: SING}\n", "SING"),
        ("[unclosed\n", "scheduled_states.yaml"),
        (None, "scheduled_states.yaml"),
    ],
)
def test_scheduled_states_are_validated(
    db: Database,
    ledger: DefaultLedgerManager,
    fake_clock: FakeClock,
    tmp_path: Path,
    *,
    content: str | None,
    fragment: str,
) -> None:
    folder = tmp_path / "tables"
    folder.mkdir()
    for name in ("story_workflow.yaml", "feature_workflow.yaml", "bug_workflow.yaml"):
        (folder / name).write_text(
            (TABLES_DIR / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    if content is not None:
        (folder / "scheduled_states.yaml").write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError, match=fragment):
        DefaultWorkflowManager(
            db,
            WorkflowRepository(db),
            ProjectRepository(db),
            IdSequenceStore(db),
            ledger,
            DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock),
            fake_clock,
            folder,
        )
