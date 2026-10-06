from pathlib import Path
from typing import Any

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from walk.common.errors import ConfigError, GuardRejected, PermissionDenied
from walk.common.roles import AgentRole
from walk.hooks import (
    DefaultHookManager,
    Hook,
    HookContext,
    HookExecutionRepository,
    HookFailed,
    HookFailPolicy,
    HookName,
)
from walk.persistence import Database, IdSequenceStore, UnitOfWork
from walk.telemetry import DefaultLedgerManager, LedgerEvent, LedgerEventKind, LedgerRepository
from walk.workflow import (
    TABLES_DIR,
    Bug,
    BugDraft,
    DefaultWorkflowManager,
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

START_FACTS: dict[str, Any] = {"branch_available": True, "budget_ok": True}


class SwitchableLedger(DefaultLedgerManager):
    """Ledger that fails WORK_ITEM_TRANSITION appends while ``fail`` is set."""

    fail = False

    async def append(self, event: LedgerEvent, *, uow: UnitOfWork | None = None) -> LedgerEvent:
        if self.fail and event.kind is LedgerEventKind.WORK_ITEM_TRANSITION:
            msg = "ledger down"
            raise RuntimeError(msg)
        return await super().append(event, uow=uow)


@pytest.fixture
def ledger(db: Database, fake_clock: FakeClock) -> SwitchableLedger:
    return SwitchableLedger(db, LedgerRepository(db), SequentialIdFactory(), fake_clock)


@pytest.fixture
def hooks(db: Database, ledger: SwitchableLedger, fake_clock: FakeClock) -> DefaultHookManager:
    return DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)


@pytest.fixture
def workflow(
    db: Database,
    ledger: SwitchableLedger,
    hooks: DefaultHookManager,
    fake_clock: FakeClock,
    project: Project,
) -> DefaultWorkflowManager:
    del project
    return DefaultWorkflowManager(
        db,
        WorkflowRepository(db),
        ProjectRepository(db),
        IdSequenceStore(db),
        ledger,
        hooks,
        fake_clock,
        TABLES_DIR,
    )


async def _story(workflow: DefaultWorkflowManager, *, deps: list[str] | None = None) -> str:
    if not await workflow.query(kinds=[WorkItemKind.FEATURE]):
        await workflow.create(
            WorkItemDraft(kind=WorkItemKind.FEATURE, title="F", description=""),
            actor=AgentRole.PRODUCT_OWNER,
            phase_id=None,
        )
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
        phase_id=None,
    )
    return story.id


def _ctx(role: AgentRole = AgentRole.KERNEL, **payload: object) -> TransitionContext:
    source = TransitionSource.USER if role is AgentRole.USER else TransitionSource.KERNEL
    return TransitionContext(actor_role=role, source=source, payload=payload)


async def _to_ready(workflow: DefaultWorkflowManager, item_id: str) -> None:
    await workflow.raise_event(item_id, "ready", _ctx(AgentRole.LEAD_DEV))


def _transition_rows(db: Database) -> list[tuple[object, ...]]:
    sql = "SELECT work_item_id, from_state, to_state, event, source, actor_role, reason "
    sql += "FROM work_item_transitions ORDER BY seq"
    return [tuple(row) for row in db.connect().execute(sql)]


def test_table_for_maps_story_and_task(workflow: DefaultWorkflowManager) -> None:
    assert workflow.table_for(WorkItemKind.STORY).name == "story_workflow"
    assert workflow.table_for(WorkItemKind.TASK).name == "story_workflow"
    with pytest.raises(ConfigError, match="EPIC"):
        workflow.table_for(WorkItemKind.EPIC)


async def test_raise_event_commits_atomically_and_fires_hooks(
    workflow: DefaultWorkflowManager,
    ledger: SwitchableLedger,
    hooks: DefaultHookManager,
    db: Database,
) -> None:
    fired: list[tuple[HookName, dict[str, Any]]] = []

    async def record(ctx: HookContext) -> None:
        fired.append((ctx.name, ctx.payload))

    for name in (HookName.ON_STATE_TRANSITION, HookName.ON_TASK_START):
        hooks.register(Hook(name=name, id=f"test.{name.value}", kind="builtin"), record)
    item_id = await _story(workflow)
    await _to_ready(workflow, item_id)
    fired.clear()
    transition = await workflow.raise_event(item_id, "start_implementation", _ctx(**START_FACTS))
    item = await workflow.get(item_id)
    assert item.state is WorkItemState.IMPLEMENTING
    assert item.state_version == 2
    assert (transition.from_state, transition.to_state) == (
        WorkItemState.READY,
        WorkItemState.IMPLEMENTING,
    )
    assert transition.seq == 2
    assert _transition_rows(db)[-1] == (
        item_id,
        "READY",
        "IMPLEMENTING",
        "start_implementation",
        "KERNEL",
        "KERNEL",
        None,
    )
    events = await ledger.query(kinds=[LedgerEventKind.WORK_ITEM_TRANSITION])
    assert len(events) == 2
    assert events[-1].payload == {
        "from": "READY",
        "to": "IMPLEMENTING",
        "event": "start_implementation",
        "reason": None,
        "state_version": 2,
        "kind": "STORY",
        "fix_loops": 0,
    }
    edge = {"from": "READY", "to": "IMPLEMENTING", "event": "start_implementation"}
    assert fired == [(HookName.ON_STATE_TRANSITION, edge), (HookName.ON_TASK_START, edge)]


async def test_raise_event_first_transition_has_version_one(
    workflow: DefaultWorkflowManager,
) -> None:
    item_id = await _story(workflow)
    await _to_ready(workflow, item_id)
    item = await workflow.get(item_id)
    assert (item.state, item.state_version) == (WorkItemState.READY, 1)


async def test_raise_event_rolls_back_on_ledger_failure(
    workflow: DefaultWorkflowManager, ledger: SwitchableLedger, db: Database
) -> None:
    item_id = await _story(workflow)
    ledger.fail = True
    with pytest.raises(RuntimeError, match="ledger down"):
        await _to_ready(workflow, item_id)
    item = await workflow.get(item_id)
    assert (item.state, item.state_version) == (WorkItemState.IDEA, 0)
    assert _transition_rows(db) == []


async def test_block_and_unblock_restore_previous_state(
    workflow: DefaultWorkflowManager, ledger: SwitchableLedger
) -> None:
    item_id = await _story(workflow)
    await _to_ready(workflow, item_id)
    await workflow.raise_event(item_id, "start_implementation", _ctx(**START_FACTS))
    await workflow.raise_event(
        item_id,
        "block",
        _ctx(AgentRole.SENIOR_DEV, escalations_non_empty=True, reason="needs art"),
    )
    blocked = await workflow.get(item_id)
    assert blocked.state is WorkItemState.BLOCKED
    assert blocked.blocked_reason == "needs art"
    with pytest.raises(GuardRejected, match="blocker_resolved"):
        await workflow.raise_event(item_id, "unblock", _ctx(AgentRole.USER))
    back = await workflow.raise_event(
        item_id, "unblock", _ctx(AgentRole.USER, blocker_resolved=True, resume_state="QC")
    )
    assert back.to_state is WorkItemState.IMPLEMENTING
    item = await workflow.get(item_id)
    assert item.state is WorkItemState.IMPLEMENTING
    assert item.blocked_reason is None
    events = await ledger.query(kinds=[LedgerEventKind.WORK_ITEM_TRANSITION])
    assert events[-2].payload["resume_state"] == "IMPLEMENTING"
    assert events[-2].payload["reason"] == "needs art"
    assert events[-1].payload["resume_state"] == "IMPLEMENTING"


async def test_unblock_without_block_history_is_rejected(
    workflow: DefaultWorkflowManager, db: Database
) -> None:
    item_id = await _story(workflow)
    db.connect().execute(
        "UPDATE work_items SET state = 'BLOCKED', "
        "json = json_set(json, '$.state', 'BLOCKED') WHERE id = ?",
        (item_id,),
    )
    with pytest.raises(GuardRejected, match="no resume_state"):
        await workflow.raise_event(item_id, "unblock", _ctx(AgentRole.USER, blocker_resolved=True))


async def test_qc_rejected_increments_fix_loops(
    workflow: DefaultWorkflowManager, ledger: SwitchableLedger, db: Database
) -> None:
    item_id = await _story(workflow)
    db.connect().execute(
        "UPDATE work_items SET state = 'QC', json = json_set(json, '$.state', 'QC') WHERE id = ?",
        (item_id,),
    )
    transition = await workflow.raise_event(item_id, "qc_rejected", _ctx(AgentRole.QC))
    assert transition.to_state is WorkItemState.REWORK
    item = await workflow.get(item_id)
    assert item.fix_loops == 1
    row = db.connect().execute("SELECT fix_loops FROM work_items WHERE id = ?", (item_id,))
    assert row.fetchone()[0] == 1
    events = await ledger.query(kinds=[LedgerEventKind.WORK_ITEM_TRANSITION])
    assert events[-1].payload["fix_loops"] == 1


async def test_stale_state_version_rejected(workflow: DefaultWorkflowManager) -> None:
    item_id = await _story(workflow)
    with pytest.raises(GuardRejected, match="stale state_version"):
        await workflow.raise_event(
            item_id, "ready", _ctx(AgentRole.LEAD_DEV, expected_state_version=3)
        )
    await workflow.raise_event(item_id, "ready", _ctx(AgentRole.LEAD_DEV, expected_state_version=0))
    assert (await workflow.get(item_id)).state is WorkItemState.READY


async def test_hook_failure_after_commit_does_not_roll_back(
    workflow: DefaultWorkflowManager, hooks: DefaultHookManager
) -> None:
    async def boom(ctx: HookContext) -> None:
        del ctx
        msg = "hook down"
        raise RuntimeError(msg)

    hooks.register(
        Hook(
            name=HookName.ON_STATE_TRANSITION,
            id="test.guard",
            kind="builtin",
            fail_policy=HookFailPolicy.FAIL_CLOSED,
        ),
        boom,
    )
    item_id = await _story(workflow)
    with pytest.raises(HookFailed):
        await _to_ready(workflow, item_id)
    assert (await workflow.get(item_id)).state is WorkItemState.READY


async def test_dependencies_are_supplied_by_the_kernel(
    workflow: DefaultWorkflowManager, db: Database
) -> None:
    first = await _story(workflow)
    second = await _story(workflow, deps=[first])
    with pytest.raises(GuardRejected, match="dependencies_resolved"):
        await _to_ready(workflow, second)
    set_state = "UPDATE work_items SET state = ?, json = json_set(json, '$.state', ?) WHERE id = ?"
    db.connect().execute(set_state, ("COMPLETE", "COMPLETE", first))
    await _to_ready(workflow, second)
    db.connect().execute(set_state, ("QC", "QC", first))
    with pytest.raises(GuardRejected, match=f"dependency {first} is QC"):
        await workflow.raise_event(second, "start_implementation", _ctx(**START_FACTS))
    db.connect().execute(set_state, ("COMPLETE", "COMPLETE", first))
    await workflow.raise_event(second, "start_implementation", _ctx(**START_FACTS))


async def test_raise_event_errors(workflow: DefaultWorkflowManager) -> None:
    item_id = await _story(workflow)
    with pytest.raises(WorkItemNotFound):
        await workflow.raise_event("STORY-0099", "ready", _ctx(AgentRole.USER))
    with pytest.raises(UnknownTransition):
        await workflow.raise_event(item_id, "explode", _ctx(AgentRole.USER))
    with pytest.raises(PermissionDenied):
        await workflow.raise_event(item_id, "ready", _ctx(AgentRole.QC))
    with pytest.raises(UnknownTransition, match="FEATURE"):
        await workflow.raise_event("FEAT-0001", "ready", _ctx(AgentRole.USER))
    with pytest.raises(ConfigError, match="reason"):
        await workflow.raise_event(item_id, "ready", _ctx(AgentRole.USER, reason=42))


async def test_cancel_and_complete_stamp_the_item(
    workflow: DefaultWorkflowManager, db: Database, fake_clock: FakeClock
) -> None:
    item_id = await _story(workflow)
    db.connect().execute(
        "UPDATE work_items SET state = 'QC', json = json_set(json, '$.state', 'QC') WHERE id = ?",
        (item_id,),
    )
    fake_clock.advance(60)
    await workflow.raise_event(
        item_id,
        "qc_passed",
        _ctx(AgentRole.QC, output_status="APPROVED", evidence_kinds_present=[]),
    )
    done = await workflow.get(item_id)
    assert done.completed_at == fake_clock.now()
    assert done.updated_at == fake_clock.now()
    other = await _story(workflow)
    cancelled = await workflow.raise_event(other, "cancel", _ctx(AgentRole.USER, reason="dup"))
    assert cancelled.reason == "dup"
    assert (await workflow.get(other)).state is WorkItemState.CANCELLED


def test_manager_requires_tables_dir(
    db: Database, ledger: SwitchableLedger, hooks: DefaultHookManager, fake_clock: FakeClock
) -> None:
    with pytest.raises(ConfigError, match="transition tables"):
        DefaultWorkflowManager(
            db,
            WorkflowRepository(db),
            ProjectRepository(db),
            IdSequenceStore(db),
            ledger,
            hooks,
            fake_clock,
            Path("does-not-exist"),
        )


def _write_table(folder: Path, name: str, kinds: str, rows: list[str]) -> None:
    body = "\n".join(f"  - {row}" for row in rows)
    text = f"name: {name}\nversion: '1.0'\nkinds: [{kinds}]\ntransitions:\n{body}\n"
    (folder / f"{name}.yaml").write_text(text, encoding="utf-8")


def _manager_for(
    db: Database,
    ledger: SwitchableLedger,
    hooks: DefaultHookManager,
    clock: FakeClock,
    folder: Path,
) -> DefaultWorkflowManager:
    return DefaultWorkflowManager(
        db,
        WorkflowRepository(db),
        ProjectRepository(db),
        IdSequenceStore(db),
        ledger,
        hooks,
        clock,
        folder,
    )


@pytest.mark.usefixtures("project")
async def test_custom_table_effects_and_wildcard(
    db: Database,
    ledger: SwitchableLedger,
    hooks: DefaultHookManager,
    fake_clock: FakeClock,
    tmp_path: Path,
) -> None:
    folder = tmp_path / "tables"
    folder.mkdir()
    reopen = (
        "{from: '*', event: reopen, to: REWORK, roles: [QC], effects: [increment_reopen_count]}"
    )
    _write_table(folder, "bug_workflow", "BUG", [reopen])
    _write_table(folder, "story_workflow", "STORY", [reopen])
    scheduled = (TABLES_DIR / "scheduled_states.yaml").read_text(encoding="utf-8")
    (folder / "scheduled_states.yaml").write_text(scheduled, encoding="utf-8")
    workflow = _manager_for(db, ledger, hooks, fake_clock, folder)
    await workflow.create(
        WorkItemDraft(kind=WorkItemKind.FEATURE, title="F", description=""),
        actor=AgentRole.PRODUCT_OWNER,
        phase_id=None,
    )
    bug = await workflow.create(
        BugDraft(title="B", severity=Severity.MINOR, reproduction="r", expected="e", observed="o"),
        actor=AgentRole.QC,
        phase_id=None,
    )
    await workflow.raise_event(bug.id, "reopen", _ctx(AgentRole.QC))
    reopened = await workflow.get(bug.id)
    assert isinstance(reopened, Bug)
    assert (reopened.state, reopened.reopen_count) == (WorkItemState.REWORK, 1)
    story = await workflow.create(
        WorkItemDraft(
            kind=WorkItemKind.STORY,
            title="S",
            description="",
            parent_id="FEAT-0001",
            contract=StoryContract(goal="g"),
        ),
        actor=AgentRole.PRODUCT_OWNER,
        phase_id=None,
    )
    with pytest.raises(ConfigError, match="needs a bug"):
        await workflow.raise_event(story.id, "reopen", _ctx(AgentRole.QC))
    assert await WorkflowRepository(db).states_of([]) == {}


def test_tables_may_not_share_a_kind(
    db: Database,
    ledger: SwitchableLedger,
    hooks: DefaultHookManager,
    fake_clock: FakeClock,
    tmp_path: Path,
) -> None:
    row = "{from: IDEA, event: ready, to: READY, roles: [USER]}"
    _write_table(tmp_path, "a_workflow", "STORY", [row])
    _write_table(tmp_path, "b_workflow", "STORY, TASK", [row])
    with pytest.raises(ConfigError, match="governed by both"):
        _manager_for(db, ledger, hooks, fake_clock, tmp_path)
