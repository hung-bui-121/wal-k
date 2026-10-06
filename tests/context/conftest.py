"""Fixtures shared by the context tests: a wired workflow, memory and hook stack."""

from collections.abc import Callable

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from walk.common.models import Actor
from walk.common.roles import AgentRole
from walk.context import (
    ArtifactLookup,
    DecisionLookup,
    DefaultContextManager,
    FreshnessProbe,
    HandoverLookup,
)
from walk.hooks import DefaultHookManager, Hook, HookContext, HookExecutionRepository, HookName
from walk.memory import DefaultMemoryManager, MemoryDocType, MemoryIndexRepository, skeleton_for
from walk.persistence import Database, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerRepository
from walk.workflow import (
    TABLES_DIR,
    DefaultWorkflowManager,
    Project,
    ProjectRepository,
    StoryContract,
    WorkflowRepository,
    WorkItemDraft,
    WorkItemKind,
)

HEAD = "3f9c2e1"
WRITER = Actor(role=AgentRole.SENIOR_DEV)

ManagerFactory = Callable[..., DefaultContextManager]


@pytest.fixture
def ledger(db: Database, fake_clock: FakeClock) -> DefaultLedgerManager:
    return DefaultLedgerManager(db, LedgerRepository(db), SequentialIdFactory(), fake_clock)


@pytest.fixture
def stale_fired() -> list[HookContext]:
    return []


@pytest.fixture
def hooks(
    db: Database,
    ledger: DefaultLedgerManager,
    fake_clock: FakeClock,
    stale_fired: list[HookContext],
) -> DefaultHookManager:
    manager = DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)

    async def record(ctx: HookContext) -> None:
        stale_fired.append(ctx)

    manager.register(Hook(name=HookName.ON_CONTEXT_STALE, id="test.stale", kind="builtin"), record)
    return manager


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


@pytest.fixture
def memory(
    db: Database, ledger: DefaultLedgerManager, hooks: DefaultHookManager, fake_clock: FakeClock
) -> DefaultMemoryManager:
    return DefaultMemoryManager(
        db.path.parent,
        MemoryIndexRepository(db),
        ledger,
        hooks,
        IdSequenceStore(db),
        fake_clock,
        project_key="DEMO",
    )


@pytest.fixture
def make_manager(
    db: Database,
    workflow: DefaultWorkflowManager,
    memory: DefaultMemoryManager,
    *,
    hooks: DefaultHookManager,
    ledger: DefaultLedgerManager,
    fake_clock: FakeClock,
) -> ManagerFactory:
    async def head() -> str:
        return HEAD

    def build(
        *,
        freshness: FreshnessProbe | None = None,
        handovers: HandoverLookup | None = None,
        decisions: DecisionLookup | None = None,
        artifacts: ArtifactLookup | None = None,
    ) -> DefaultContextManager:
        return DefaultContextManager(
            workflow,
            WorkflowRepository(db),
            memory,
            hooks,
            ledger,
            fake_clock,
            head_resolver=head,
            freshness=freshness,
            handovers=handovers,
            decisions=decisions,
            artifacts=artifacts,
        )

    return build


def draft(kind: WorkItemKind, title: str, parent: str | None = None) -> WorkItemDraft:
    """A work-item draft; stories and tasks get a minimal contract."""
    needs_contract = kind in {WorkItemKind.STORY, WorkItemKind.TASK}
    contract = StoryContract(goal=title, acceptance_criteria=["works"]) if needs_contract else None
    return WorkItemDraft(
        kind=kind, title=title, description=f"{title} text", parent_id=parent, contract=contract
    )


async def write_feature_doc(memory: DefaultMemoryManager, fake_clock: FakeClock) -> None:
    """Write `.ai/features/FEAT-0001.md` with an Intent section."""
    doc = skeleton_for(MemoryDocType.FEATURE, "FEAT-0001", "Movement", WRITER, fake_clock.now())
    doc.sections["Intent"] = "Walk and run."
    await memory.write(doc, actor=WRITER, head=HEAD, branch="main")


async def write_project_doc(memory: DefaultMemoryManager, fake_clock: FakeClock) -> None:
    """Write `.ai/project/project.md` with every section filled."""
    doc = skeleton_for(MemoryDocType.PROJECT, "project", "Demo", WRITER, fake_clock.now())
    for name in doc.sections:
        doc.sections[name] = f"{name} body."
    await memory.write(doc, actor=WRITER, head=HEAD, branch="main")


async def story_under_feature(workflow: DefaultWorkflowManager) -> str:
    """Create FEAT-0001 with STORY-0001 below it; return the story id."""
    await workflow.create(
        draft(WorkItemKind.FEATURE, "Movement"), actor=AgentRole.USER, phase_id=None
    )
    story = await workflow.create(
        draft(WorkItemKind.STORY, "Run", "FEAT-0001"), actor=AgentRole.USER, phase_id=None
    )
    return story.id
