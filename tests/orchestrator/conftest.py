"""Fixtures of the orchestrator tests: the runtime environment plus scheduler and orchestrator."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import pytest

from tests.runtime import conftest as runtime_fixtures
from tests.runtime.executor_env import EnvFactory, ExecutorEnv
from walk.common.ids import RunId
from walk.effort import DefaultEffortManager, EffortRequest, StaticCostEstimator
from walk.orchestrator import DefaultOrchestrator, DefaultTaskRouter, Scheduler, StatusBuilder
from walk.persistence import IdempotencyStore, UnitOfWork
from walk.runtime import RecoveryManager
from walk.telemetry import RetrospectiveMetrics
from walk.workflow import (
    TABLES_DIR,
    PhaseRepository,
    ProjectRepository,
    Story,
    StoryContract,
    WorkItemState,
)

SCHEDULED_STATES = TABLES_DIR / "scheduled_states.yaml"

# The runtime fixtures, shared with this folder.
checkpoint_fired = runtime_fixtures.checkpoint_fired
git = runtime_fixtures.git
handovers = runtime_fixtures.handovers
hooks = runtime_fixtures.hooks
idempotency = runtime_fixtures.idempotency
ledger = runtime_fixtures.ledger
make_executor_env = runtime_fixtures.make_executor_env
memory = runtime_fixtures.memory
runs = runtime_fixtures.runs
story = runtime_fixtures.story


class RecordingTelemetry:
    """`TelemetryManager` that keeps counters in memory."""

    def __init__(self) -> None:
        self.counters: dict[str, float] = {}

    def counter(self, name: str, value: float = 1.0, **labels: str) -> None:
        del labels
        self.counters[name] = self.counters.get(name, 0.0) + value

    def timer(self, name: str, seconds: float, **labels: str) -> None:
        del name, seconds, labels

    async def metrics(self, **kwargs: Any) -> RetrospectiveMetrics:
        del kwargs
        msg = "not used by the orchestrator tests"
        raise AssertionError(msg)

    def log(self, level: str, message: str, **fields: object) -> None:
        del level, message, fields


@dataclass
class Kernel:
    """An executor environment with the E01-S29 orchestration on top."""

    env: ExecutorEnv
    router: DefaultTaskRouter
    scheduler: Scheduler
    recovery: RecoveryManager
    status: StatusBuilder
    orchestrator: DefaultOrchestrator
    telemetry: RecordingTelemetry
    idempotency: IdempotencyStore

    async def add_story(self, number: int, title: str, **fields: Any) -> Story:
        data: dict[str, Any] = {
            "id": f"STORY-{number:04d}",
            "project_key": "DEMO",
            "title": title,
            "state": WorkItemState.READY,
            "contract": StoryContract(goal=title),
            **fields,
        }
        item = Story.model_validate(data)
        async with UnitOfWork(self.env.db) as uow:
            await self.env.items.insert(item, uow)
        return item

    async def make_ready(self, **fields: Any) -> Story:
        """Turn the shared STORY-0001 (IMPLEMENTING in the runtime fixture) into READY work."""
        item = self.env.story.model_copy(update={"state": WorkItemState.READY, **fields})
        async with UnitOfWork(self.env.db) as uow:
            await self.env.items.upsert(item, uow)
        return item


KernelFactory = Callable[..., Awaitable[Kernel]]


async def _approve(run_id: RunId, request: EffortRequest) -> bool:
    del run_id, request
    return True


@pytest.fixture
def make_kernel(make_executor_env: EnvFactory) -> KernelFactory:
    async def build(
        *,
        max_parallel_agents: int = 2,
        poll_interval_s: float = 30.0,
        kernel_instance: str = "instance-a",
        **env_options: Any,
    ) -> Kernel:
        env = await make_executor_env(kernel_instance=kernel_instance, **env_options)
        clock = env.executor._clock  # noqa: SLF001 - the environment's clock
        effort = DefaultEffortManager(
            StaticCostEstimator(), env.ledger, env.hooks, clock, _approve, project_key="DEMO"
        )
        telemetry = RecordingTelemetry()
        schedule_keys = IdempotencyStore(env.db, clock)
        router = DefaultTaskRouter(SCHEDULED_STATES, env.agents, env.runs, env.workflow)
        scheduler = Scheduler(
            env.db,
            ProjectRepository(env.db),
            env.workflow,
            router,
            env.agents,
            effort,
            env.budgets,
            env.router,
            env.executor,
            env.checkpoints,
            schedule_keys,
            telemetry,
            clock,
            project_key="DEMO",
            max_parallel_agents=max_parallel_agents,
            ready_env_keys=lambda: {"git"},
        )
        recovery = RecoveryManager(
            env.runs,
            env.checkpoints,
            env.executor,
            env.router,
            env.agents,
            env.items,
            env.hooks,
            env.ledger,
            clock,
            kernel_instance=kernel_instance,
            project_key="DEMO",
            ready_env_keys=lambda: {"git"},
        )
        status = StatusBuilder(
            ProjectRepository(env.db),
            env.workflow,
            PhaseRepository(env.db),
            env.runs,
            env.budgets,
            env.ledger,
            project_key="DEMO",
        )
        orchestrator = DefaultOrchestrator(
            scheduler,
            env.executor,
            recovery,
            status,
            env.hooks,
            env.ledger,
            clock,
            project_key="DEMO",
            kernel_instance=kernel_instance,
            poll_interval_s=poll_interval_s,
        )
        return Kernel(
            env, router, scheduler, recovery, status, orchestrator, telemetry, schedule_keys
        )

    return build
