"""Fixtures of the builtin hook tests (E02-S08): the runtime environment plus the builtins."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_model_adapter import FakeModelAdapter, FakeScript, fake_descriptor
from tests.orchestrator.conftest import RecordingTelemetry
from tests.runtime import conftest as runtime_fixtures
from tests.runtime.executor_env import (
    CLAUDE_MODEL,
    CODEX_MODEL,
    EnvFactory,
    ExecutorEnv,
    builtin_deps,
    script,
)
from walk.agents import AgentInput
from walk.common.ids import RunId
from walk.hooks import HookContext, HookName, HookResult
from walk.model_router import AgentEvent, AgentEventKind, ModelAdapter, RunSession
from walk.orchestrator import BuiltinHookDeps, register_builtins
from walk.persistence import UnitOfWork
from walk.runtime import AgentRun, Checkpoint
from walk.workflow import Story, StoryContract, WorkItemState

# The runtime fixtures, shared with this folder.
checkpoint_fired = runtime_fixtures.checkpoint_fired
git = runtime_fixtures.git
handovers = runtime_fixtures.handovers
hooks = runtime_fixtures.hooks
idempotency = runtime_fixtures.idempotency
insert_run = runtime_fixtures.insert_run
ledger = runtime_fixtures.ledger
make_executor_env = runtime_fixtures.make_executor_env
memory = runtime_fixtures.memory
runs = runtime_fixtures.runs
story = runtime_fixtures.story

DEADLOCK_GUARD_S = 5  # AC 8/9: a regression fails the test instead of hanging the suite
POLL_S = 0.01


class HoldingAdapter(FakeModelAdapter):
    """Fake whose runs stop after ``hold_after`` tool results until the run is cancelled.

    A held run keeps its task alive without advancing, so a test can stop it from outside.
    """

    def __init__(
        self, provider: str, model_id: str, plan: FakeScript, clock: FakeClock, hold_after: int
    ) -> None:
        super().__init__(provider, [fake_descriptor(model_id, provider)], plan, clock)
        self._hold_after = hold_after
        self._gates: dict[RunId, asyncio.Event] = {}
        self._held: dict[RunId, asyncio.Event] = {}

    def run(self, input: AgentInput, session: RunSession) -> AsyncIterator[AgentEvent]:  # noqa: A002 - parameter name fixed by INTERFACES §2.1
        return self._holding(super().run(input, session), session.run_id)

    async def cancel(self, run_id: RunId) -> None:
        await super().cancel(run_id)
        self._gate(run_id).set()

    def release(self, run_id: RunId) -> None:
        """Let a held run go on (without cancelling it)."""
        self._gate(run_id).set()

    def held(self, run_id: RunId) -> asyncio.Event:
        """Set once the run is held."""
        return self._held.setdefault(run_id, asyncio.Event())

    def _gate(self, run_id: RunId) -> asyncio.Event:
        return self._gates.setdefault(run_id, asyncio.Event())

    async def _holding(
        self, inner: AsyncIterator[AgentEvent], run_id: RunId
    ) -> AsyncIterator[AgentEvent]:
        results = 0
        async for event in inner:
            yield event
            if event.kind is AgentEventKind.TOOL_CALL_RESULT:
                results += 1
                if results == self._hold_after:
                    self.held(run_id).set()
                    await self._gate(run_id).wait()


def holding_adapters(clock: FakeClock, hold_after: int = 2) -> dict[str, ModelAdapter]:
    """``fake-codex``/``fake-claude`` holding after ``hold_after`` of 12 tool calls."""
    plan = script(tool_calls=12)
    return {
        "fake-codex": HoldingAdapter("fake-codex", CODEX_MODEL, plan, clock, hold_after),
        "fake-claude": HoldingAdapter("fake-claude", CLAUDE_MODEL, plan, clock, hold_after),
    }


@dataclass
class BuiltinEnv:
    """An executor environment with the builtin hooks registered."""

    env: ExecutorEnv
    telemetry: RecordingTelemetry
    deps: BuiltinHookDeps

    def context(self, name: HookName, **fields: Any) -> HookContext:
        """A context of ``name`` for project ``DEMO`` at the environment's clock."""
        clock = self.env.executor._clock  # noqa: SLF001 - the environment's clock
        return HookContext(name=name, at=clock.now(), project_key="DEMO", **fields)

    async def fire(self, name: HookName, **fields: Any) -> list[HookResult]:
        """Fire ``name`` with a context built from ``fields``."""
        return await self.env.hooks.fire(name, self.context(name, **fields))

    def executions(self, hook_id: str) -> list[str]:
        """Statuses of the recorded executions of ``hook_id``, oldest first."""
        rows = (
            self.env.db.connect()
            .execute("SELECT status FROM hook_executions WHERE hook_id = ? ORDER BY id", (hook_id,))
            .fetchall()
        )
        return [str(row[0]) for row in rows]

    def checkpoints(self, run_id: str) -> list[Checkpoint]:
        """The run's checkpoints by seq."""
        return self.env.checkpoints_of(run_id)

    async def add_story(self, number: int) -> Story:
        """Persist ``STORY-<number>`` in IMPLEMENTING."""
        item = Story(
            id=f"STORY-{number:04d}",
            project_key="DEMO",
            title=f"Story {number}",
            state=WorkItemState.IMPLEMENTING,
            contract=StoryContract(goal=f"Story {number}"),
        )
        async with UnitOfWork(self.env.db) as uow:
            await self.env.items.insert(item, uow)
        return item

    async def start_held(self, item: Story | None = None) -> AgentRun:
        """Start an IMPLEMENT run on ``item`` (default STORY-0001) and wait until it is held."""
        run = await self.env.executor.start(self.env.agent, item or self.env.story, "IMPLEMENT")
        adapter = self.env.adapters[run.provider]
        assert isinstance(adapter, HoldingAdapter)
        await asyncio.wait_for(adapter.held(run.id).wait(), DEADLOCK_GUARD_S)
        return run


BuiltinEnvFactory = Callable[..., Awaitable[BuiltinEnv]]


@pytest.fixture
def make_builtin_env(make_executor_env: EnvFactory) -> BuiltinEnvFactory:
    """Build an executor environment and register the builtins on its hook manager."""

    async def build(**env_options: Any) -> BuiltinEnv:
        env = await make_executor_env(**env_options)
        telemetry = RecordingTelemetry()
        deps = builtin_deps(env, telemetry)
        register_builtins(env.hooks, deps)
        return BuiltinEnv(env, telemetry, deps)

    return build
