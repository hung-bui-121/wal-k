"""Fixtures shared by the runtime tests: a persisted story, runs and the wired managers."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.runtime.executor_env import (
    BaseFixtures,
    EnvFactory,
    ExecutorEnv,
    build_executor_env,
    register_recorders,
)
from walk.common.enums import Effort
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, Hook, HookContext, HookExecutionRepository, HookName
from walk.integrations import AsyncioSubprocessRunner, GitCliProvider
from walk.memory import DefaultMemoryManager, MemoryIndexRepository
from walk.persistence import Database, IdempotencyStore, IdSequenceStore, UnitOfWork
from walk.runtime import (
    AgentRun,
    AgentRunRepository,
    CheckpointRepository,
    HandoverRepository,
)
from walk.telemetry import DefaultLedgerManager, LedgerRepository
from walk.workflow import Project, Story, StoryContract, WorkflowRepository, WorkItemState

AT = datetime(2026, 1, 1, tzinfo=UTC)
RUN_A = "RUN-01J0000000000000000000000A"
RUN_B = "RUN-01J0000000000000000000000B"
STORY_ID = "STORY-0001"

RunFactory = Callable[..., Awaitable[AgentRun]]


def make_run(run_id: str = RUN_A, **overrides: object) -> AgentRun:
    data: dict[str, object] = {
        "id": run_id,
        "project_key": "DEMO",
        "work_item_id": STORY_ID,
        "role": AgentRole.SENIOR_DEV,
        "model_id": "codex/gpt-5-codex",
        "provider": "codex",
        "effort": Effort.MEDIUM,
        "purpose": "IMPLEMENT",
        "kernel_instance": "instance-a",
        "started_at": AT,
    }
    data.update(overrides)
    return AgentRun.model_validate(data)


@pytest.fixture
async def story(db: Database, project: Project) -> Story:
    item = Story(
        id=STORY_ID,
        project_key=project.key,
        title="Player jump: double jump!",
        state=WorkItemState.IMPLEMENTING,
        contract=StoryContract(goal="Let the player double jump"),
        created_at=AT,
        updated_at=AT,
    )
    async with UnitOfWork(db) as uow:
        await WorkflowRepository(db).insert(item, uow)
    return item


@pytest.fixture
def runs(db: Database, fake_clock: FakeClock) -> AgentRunRepository:
    return AgentRunRepository(db, clock=fake_clock)


@pytest.fixture
def checkpoints(db: Database) -> CheckpointRepository:
    return CheckpointRepository(db)


@pytest.fixture
def handovers(db: Database) -> HandoverRepository:
    return HandoverRepository(db)


@pytest.fixture
def insert_run(db: Database, runs: AgentRunRepository, story: Story) -> RunFactory:
    async def insert(run_id: str = RUN_A, **overrides: object) -> AgentRun:
        run = make_run(run_id, **overrides)
        async with UnitOfWork(db) as uow:
            await runs.insert(run, uow)
        return run

    del story
    return insert


@pytest.fixture
def ledger(db: Database, fake_clock: FakeClock) -> DefaultLedgerManager:
    return DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), fake_clock)


@pytest.fixture
def checkpoint_fired() -> list[HookContext]:
    return []


@pytest.fixture
def hooks(
    db: Database,
    ledger: DefaultLedgerManager,
    fake_clock: FakeClock,
    checkpoint_fired: list[HookContext],
) -> DefaultHookManager:
    manager = DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)

    async def record(ctx: HookContext) -> None:
        checkpoint_fired.append(ctx)

    hook = Hook(name=HookName.ON_AGENT_CHECKPOINT, id="test.checkpoint", kind="builtin")
    manager.register(hook, record)
    return manager


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
def idempotency(db: Database, fake_clock: FakeClock) -> IdempotencyStore:
    return IdempotencyStore(db, fake_clock)


@pytest.fixture
def git(
    tmp_game_repo: Path,
    ledger: DefaultLedgerManager,
    idempotency: IdempotencyStore,
    fake_clock: FakeClock,
) -> GitCliProvider:
    return GitCliProvider(
        tmp_game_repo,
        AsyncioSubprocessRunner(),
        ledger,
        idempotency,
        fake_clock,
        project_key="DEMO",
    )


@pytest.fixture
def make_executor_env(  # noqa: PLR0917 - fixture parameters are the shared fixtures
    db: Database,
    story: Story,
    tmp_game_repo: Path,
    ledger: DefaultLedgerManager,
    hooks: DefaultHookManager,
    memory: DefaultMemoryManager,
    idempotency: IdempotencyStore,
    git: GitCliProvider,
    runs: AgentRunRepository,
    fake_clock: FakeClock,
) -> EnvFactory:
    """Build an `ExecutorEnv` (once per test: the hook recorders register on first use)."""
    base = BaseFixtures(
        db, story, tmp_game_repo, ledger, hooks, memory, idempotency, git, runs, fake_clock
    )
    fired = register_recorders(hooks)

    async def build(*args: Any, **kwargs: Any) -> ExecutorEnv:
        return await build_executor_env(base, fired, *args, **kwargs)

    return build
