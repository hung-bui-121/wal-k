from datetime import UTC, datetime

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from walk.common.errors import ConfigError, GuardRejected
from walk.common.roles import AgentRole
from walk.hooks import (
    DefaultHookManager,
    Hook,
    HookContext,
    HookExecutionRepository,
    HookName,
)
from walk.persistence import Database, IdSequenceStore, UnitOfWork
from walk.telemetry import DefaultLedgerManager, LedgerEventKind, LedgerRepository
from walk.workflow import (
    TABLES_DIR,
    BugDraft,
    DefaultWorkflowManager,
    PhaseDecision,
    PhaseRepository,
    PhaseState,
    Project,
    ProjectRepository,
    ReleaseCandidate,
    ReleaseCandidateRepository,
    ReleaseCandidateState,
    Severity,
    TransitionContext,
    TransitionSource,
    UnknownTransition,
    WorkflowRepository,
    WorkItemDraft,
    WorkItemKind,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def ledger(db: Database, fake_clock: FakeClock) -> DefaultLedgerManager:
    return DefaultLedgerManager(db, LedgerRepository(db), SequentialIdFactory(), fake_clock)


@pytest.fixture
def hooks(db: Database, ledger: DefaultLedgerManager, fake_clock: FakeClock) -> DefaultHookManager:
    return DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)


@pytest.fixture
def workflow(
    db: Database,
    ledger: DefaultLedgerManager,
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


def _ctx(role: AgentRole = AgentRole.USER, **payload: object) -> TransitionContext:
    source = TransitionSource.USER if role is AgentRole.USER else TransitionSource.KERNEL
    return TransitionContext(actor_role=role, source=source, payload=payload)


async def _force(db: Database, phase_id: str, state: PhaseState) -> None:
    phases = PhaseRepository(db)
    phase = await phases.get(phase_id)
    assert phase is not None
    async with UnitOfWork(db) as uow:
        await phases.upsert(phase.model_copy(update={"state": state}), uow)


async def _active_phase(workflow: DefaultWorkflowManager) -> str:
    phase = await workflow.create_phase("Prototype", 1, scope_epic_ids=["EPIC-001"])
    await workflow.phase_event(phase.id, "start", _ctx())
    return phase.id


async def test_create_phase_allocates_id_and_unique_ordinal(
    workflow: DefaultWorkflowManager,
) -> None:
    phase = await workflow.create_phase("Prototype", 1, goal="prove the loop")
    assert (phase.id, phase.state, phase.project_key, phase.goal) == (
        "PHASE-01",
        PhaseState.PLANNED,
        "DEMO",
        "prove the loop",
    )
    with pytest.raises(ConfigError, match="ordinal 1"):
        await workflow.create_phase("Again", 1)
    second = await workflow.create_phase("Vertical Slice", 2)
    assert second.id == "PHASE-02"
    assert [p.id for p in await workflow.list_phases()] == ["PHASE-01", "PHASE-02"]


async def test_phase_start_transitions_and_fires_hook(
    workflow: DefaultWorkflowManager,
    hooks: DefaultHookManager,
    ledger: DefaultLedgerManager,
    db: Database,
    fake_clock: FakeClock,
) -> None:
    fired: list[HookContext] = []

    async def record(ctx: HookContext) -> None:
        fired.append(ctx)

    hooks.register(Hook(name=HookName.ON_PHASE_START, id="test.start", kind="builtin"), record)
    phase = await workflow.create_phase("Prototype", 1, scope_epic_ids=["EPIC-001"])
    fake_clock.advance(10)
    started = await workflow.phase_event(phase.id, "start", _ctx())
    assert started.state is PhaseState.ACTIVE
    assert started.started_at == fake_clock.now()
    events = await ledger.query(kinds=[LedgerEventKind.PHASE_TRANSITION])
    assert [(e.phase_id, e.payload["from"], e.payload["to"]) for e in events] == [
        ("PHASE-01", "PLANNED", "ACTIVE")
    ]
    assert [(c.name, c.phase_id, c.payload["event"]) for c in fired] == [
        (HookName.ON_PHASE_START, "PHASE-01", "start")
    ]
    project = await ProjectRepository(db).single()
    assert project.current_phase_id == "PHASE-01"


async def test_phase_start_requires_scope(workflow: DefaultWorkflowManager) -> None:
    phase = await workflow.create_phase("Prototype", 1)
    with pytest.raises(GuardRejected, match="scope_non_empty"):
        await workflow.phase_event(phase.id, "start", _ctx())
    with pytest.raises(GuardRejected, match="kit_validated"):
        await workflow.phase_event(phase.id, "start", _ctx(kit_validated=False))


async def test_phase_start_requires_previous_complete(
    workflow: DefaultWorkflowManager, db: Database
) -> None:
    await workflow.create_phase("Prototype", 1, scope_epic_ids=["EPIC-001"])
    second = await workflow.create_phase("Slice", 2, scope_epic_ids=["EPIC-002"])
    with pytest.raises(GuardRejected, match="previous_phase_complete_or_first"):
        await workflow.phase_event(second.id, "start", _ctx())
    await _force(db, "PHASE-01", PhaseState.COMPLETE)
    started = await workflow.phase_event(second.id, "start", _ctx())
    assert started.state is PhaseState.ACTIVE


async def test_request_review_guard_and_user_force(workflow: DefaultWorkflowManager) -> None:
    phase_id = await _active_phase(workflow)
    await workflow.create(
        WorkItemDraft(kind=WorkItemKind.FEATURE, title="F", description=""),
        actor=AgentRole.PRODUCT_OWNER,
        phase_id=phase_id,
    )
    with pytest.raises(GuardRejected, match="all_scope_features_terminal"):
        await workflow.phase_event(phase_id, "request_review", _ctx(AgentRole.KERNEL))
    forced = await workflow.phase_event(phase_id, "request_review", _ctx(AgentRole.USER))
    assert forced.state is PhaseState.EVIDENCE_REVIEW


async def _at_gate(workflow: DefaultWorkflowManager, db: Database) -> str:
    phase_id = await _active_phase(workflow)
    await _force(db, phase_id, PhaseState.USER_GATE)
    return phase_id


async def test_gate_rework_requires_feedback(
    workflow: DefaultWorkflowManager, db: Database, ledger: DefaultLedgerManager
) -> None:
    phase_id = await _at_gate(workflow, db)
    with pytest.raises(GuardRejected, match="feedback_non_empty"):
        await workflow.phase_event(phase_id, "decide:REWORK", _ctx(feedback="  "))
    phase = await workflow.phase_event(phase_id, "decide:REWORK", _ctx(feedback="jump feels slow"))
    assert phase.state is PhaseState.REWORK
    assert phase.last_decision is PhaseDecision.REWORK
    decisions = await ledger.query(kinds=[LedgerEventKind.PHASE_GATE_DECISION])
    assert [(e.phase_id, e.payload) for e in decisions] == [
        (phase_id, {"decision": "REWORK", "feedback": "jump feels slow", "gate_round": 0})
    ]
    transitions = await ledger.query(kinds=[LedgerEventKind.PHASE_TRANSITION])
    assert transitions[-1].payload["to"] == "REWORK"


async def test_gate_go_completes_phase(
    workflow: DefaultWorkflowManager, db: Database, fake_clock: FakeClock
) -> None:
    phase_id = await _at_gate(workflow, db)
    fake_clock.advance(30)
    phase = await workflow.phase_event(phase_id, "decide:GO", _ctx())
    assert (phase.state, phase.last_decision) == (PhaseState.COMPLETE, PhaseDecision.GO)
    assert phase.completed_at == fake_clock.now()


async def test_gate_stop_pauses_project(workflow: DefaultWorkflowManager, db: Database) -> None:
    phase_id = await _at_gate(workflow, db)
    phase = await workflow.phase_event(phase_id, "decide:STOP", _ctx())
    assert phase.state is PhaseState.STOPPED
    assert (await ProjectRepository(db).single()).paused is True
    reopened = await workflow.phase_event(phase_id, "reopen", _ctx())
    assert reopened.state is PhaseState.PLANNED


async def test_package_ready_increments_gate_round(
    workflow: DefaultWorkflowManager, db: Database
) -> None:
    phase_id = await _active_phase(workflow)
    await _force(db, phase_id, PhaseState.EVIDENCE_REVIEW)
    facts = {"evidence_package_written": True, "retrospective_written": True}
    phase = await workflow.phase_event(phase_id, "package_ready", _ctx(AgentRole.KERNEL, **facts))
    assert (phase.state, phase.gate_round) == (PhaseState.USER_GATE, 1)


async def test_phase_event_errors(workflow: DefaultWorkflowManager) -> None:
    with pytest.raises(ConfigError, match="PHASE-09"):
        await workflow.phase_event("PHASE-09", "start", _ctx())
    phase = await workflow.create_phase("Prototype", 1, scope_epic_ids=["EPIC-001"])
    with pytest.raises(UnknownTransition, match="PHASE"):
        await workflow.phase_event(phase.id, "decide:GO", _ctx())
    stopped = await workflow.phase_event(phase.id, "stop", _ctx())
    assert stopped.state is PhaseState.STOPPED


async def _rc(db: Database, state: ReleaseCandidateState, **fields: object) -> ReleaseCandidate:
    rc = ReleaseCandidate.model_validate(
        {
            "id": "RC-01",
            "project_key": "DEMO",
            "number": 1,
            "state": state,
            "commit": "abc1234",
            "created_at": T0,
            **fields,
        }
    )
    async with UnitOfWork(db) as uow:
        await ReleaseCandidateRepository(db).insert(rc, uow)
        uow.conn.execute(
            "INSERT INTO id_sequences (prefix, next) VALUES ('RC', 2) "
            "ON CONFLICT(prefix) DO UPDATE SET next = 2"
        )
    return rc


async def test_rc_next_creates_successor(
    workflow: DefaultWorkflowManager, db: Database, ledger: DefaultLedgerManager
) -> None:
    await workflow.create(
        BugDraft(title="B", severity=Severity.MAJOR, reproduction="r", expected="e", observed="o"),
        actor=AgentRole.QC,
        phase_id=None,
    )
    await _rc(db, ReleaseCandidateState.REJECTED, rejection_bug_ids=["BUG-0001"])
    with pytest.raises(GuardRejected, match="rejection_bugs_complete"):
        await workflow.rc_event("RC-01", "next_rc", _ctx(AgentRole.KERNEL, commit="def5678"))
    db.connect().execute(
        "UPDATE work_items SET state = 'COMPLETE', "
        "json = json_set(json, '$.state', 'COMPLETE') WHERE id = 'BUG-0001'"
    )
    with pytest.raises(ConfigError, match="commit"):
        await workflow.rc_event("RC-01", "next_rc", _ctx(AgentRole.KERNEL))
    successor = await workflow.rc_event(
        "RC-01", "next_rc", _ctx(AgentRole.KERNEL, commit="def5678")
    )
    assert (successor.id, successor.number, successor.state, successor.commit) == (
        "RC-02",
        2,
        ReleaseCandidateState.BUILDING,
        "def5678",
    )
    previous = await ReleaseCandidateRepository(db).get("RC-01")
    assert previous is not None
    assert previous.state is ReleaseCandidateState.REJECTED
    events = await ledger.query(kinds=[LedgerEventKind.RC_TRANSITION])
    assert [(e.payload["rc_id"], e.payload["from"], e.payload["to"]) for e in events] == [
        ("RC-02", "REJECTED", "BUILDING")
    ]


async def test_rc_lifecycle_guards(workflow: DefaultWorkflowManager, db: Database) -> None:
    await _rc(db, ReleaseCandidateState.BUILDING)
    with pytest.raises(GuardRejected, match="build_evidence_present"):
        await workflow.rc_event("RC-01", "build_ok", _ctx(AgentRole.KERNEL))
    rcs = ReleaseCandidateRepository(db)
    rc = await rcs.get("RC-01")
    assert rc is not None
    async with UnitOfWork(db) as uow:
        await rcs.upsert(rc.model_copy(update={"build_evidence_ids": ["EVD-000001"]}), uow)
    built = await workflow.rc_event("RC-01", "build_ok", _ctx(AgentRole.KERNEL))
    assert built.state is ReleaseCandidateState.QC
    with pytest.raises(GuardRejected, match="qc_report_evidence"):
        await workflow.rc_event("RC-01", "qc_pass", _ctx(AgentRole.QC, open_blocker_bug_count=0))
    with pytest.raises(GuardRejected, match="rejection_bugs_created"):
        await workflow.rc_event("RC-01", "qc_reject", _ctx(AgentRole.QC))
    with pytest.raises(ConfigError, match="RC-09"):
        await workflow.rc_event("RC-09", "build_ok", _ctx(AgentRole.KERNEL))


async def test_rc_release_requires_user_approval(
    workflow: DefaultWorkflowManager, db: Database
) -> None:
    await _rc(db, ReleaseCandidateState.PASSED)
    with pytest.raises(GuardRejected, match="approval_user"):
        await workflow.rc_event("RC-01", "release", _ctx(AgentRole.UA_RELEASE))
    released = await workflow.rc_event(
        "RC-01", "release", _ctx(AgentRole.UA_RELEASE, approval_id="APV-0001")
    )
    assert released.state is ReleaseCandidateState.RELEASED


async def test_create_phase_rejects_ordinal_below_one(workflow: DefaultWorkflowManager) -> None:
    with pytest.raises(ConfigError, match="ordinal must be >= 1"):
        await workflow.create_phase("Zero", 0)


async def test_rc_next_rejects_invalid_commit(
    workflow: DefaultWorkflowManager, db: Database
) -> None:
    await _rc(db, ReleaseCandidateState.REJECTED)
    with pytest.raises(ConfigError, match="invalid commit"):
        await workflow.rc_event("RC-01", "next_rc", _ctx(AgentRole.KERNEL, commit="not a sha"))
