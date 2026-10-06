import asyncio
from collections.abc import AsyncIterator

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_model_adapter import FakeModelAdapter, FakeScript, fake_descriptor
from tests.runtime.executor_env import (
    CLAUDE_MODEL,
    CODEX_MODEL,
    EnvFactory,
    ExecutorEnv,
    script,
)
from walk.agents import AgentInput
from walk.common.errors import PermissionDenied, ProviderUnavailable, RateLimited
from walk.integrations import GitError
from walk.model_router import (
    AgentEvent,
    AgentEventKind,
    ModelAdapter,
    NotResumable,
    ProviderSessionRef,
    RunSession,
)
from walk.runtime import RESUME_INSTRUCTION, RETRY_DELAYS_S, AgentRun, AgentRunState
from walk.telemetry import LedgerEventKind

RETRY = LedgerEventKind.RETRY


class FlakyAdapter(FakeModelAdapter):
    """Raises the queued errors right after STARTED, one per stream, then behaves."""

    def __init__(
        self,
        provider: str,
        model_id: str,
        plan: FakeScript,
        clock: FakeClock,
        errors: list[Exception],
        *,
        refuse_resume: bool = False,
    ) -> None:
        super().__init__(provider, [fake_descriptor(model_id, provider)], plan, clock)
        self.errors = errors
        self.refuse_resume = refuse_resume
        self.resumed: list[str] = []

    def run(self, input: AgentInput, session: RunSession) -> AsyncIterator[AgentEvent]:  # noqa: A002 - parameter name fixed by INTERFACES §2.1
        return self._flaky(super().run(input, session))

    def resume(
        self, session_ref: ProviderSessionRef, instruction: str, session: RunSession
    ) -> AsyncIterator[AgentEvent]:
        if self.refuse_resume:
            msg = "forgotten session"
            raise NotResumable(msg)
        self.resumed.append(instruction)
        return self._flaky(super().resume(session_ref, instruction, session))

    async def _flaky(self, inner: AsyncIterator[AgentEvent]) -> AsyncIterator[AgentEvent]:
        async for event in inner:
            yield event
            if event.kind is AgentEventKind.STARTED and self.errors:
                raise self.errors.pop(0)


class RecordingSleep:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


def _adapters(codex: FakeModelAdapter, clock: FakeClock) -> dict[str, ModelAdapter]:
    claude = FakeModelAdapter(
        "fake-claude", [fake_descriptor(CLAUDE_MODEL, "fake-claude")], script(), clock
    )
    return {"fake-codex": codex, "fake-claude": claude}


async def _retries(env: ExecutorEnv, run_id: str) -> list[dict[str, object]]:
    return [event.payload for event in await env.events(run_id, RETRY)]


async def test_transient_error_retried_with_backoff(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    errors: list[Exception] = [RateLimited("slow down"), RateLimited("still too fast")]
    codex = FlakyAdapter("fake-codex", CODEX_MODEL, script(), fake_clock, errors)
    sleep = RecordingSleep()
    env = await make_executor_env(adapters=_adapters(codex, fake_clock), sleep=sleep)

    run = await env.run_to_end()

    retries = await _retries(env, run.id)
    assert [(r["attempt"], r["delay"], r["error"]) for r in retries] == [
        (1, 1.0, "RateLimited"),
        (2, 2.0, "RateLimited"),
    ]
    assert sleep.delays == [1.0, 2.0]
    assert codex.resumed == [RESUME_INSTRUCTION, RESUME_INSTRUCTION]
    assert run.state is AgentRunState.COMPLETED
    assert run.tool_calls == 3


async def test_retries_exhausted_then_fallback(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    errors: list[Exception] = [ProviderUnavailable(f"down {n}") for n in range(6)]
    codex = FlakyAdapter("fake-codex", CODEX_MODEL, script(), fake_clock, errors)
    sleep = RecordingSleep()
    env = await make_executor_env(adapters=_adapters(codex, fake_clock), sleep=sleep)

    run = await env.run_to_end()

    assert len(await _retries(env, run.id)) == len(RETRY_DELAYS_S) == 5
    assert sleep.delays == list(RETRY_DELAYS_S)
    assert run.state is AgentRunState.HANDED_OVER
    fallback = (await env.events(run.id, LedgerEventKind.MODEL_FALLBACK))[0]
    assert fallback.payload["trigger"] == "PROVIDER_OUTAGE"
    assert fallback.payload["to"] == CLAUDE_MODEL
    child = [r for r in await env.runs.for_item(env.story.id) if r.parent_run_id == run.id]
    assert [c.state for c in child] == [AgentRunState.COMPLETED]


async def test_permanent_error_not_retried(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    errors: list[Exception] = [PermissionDenied("not allowed")]
    codex = FlakyAdapter("fake-codex", CODEX_MODEL, script(), fake_clock, errors)
    env = await make_executor_env(adapters=_adapters(codex, fake_clock))

    run = await env.run_to_end()

    assert await _retries(env, run.id) == []
    assert run.state is AgentRunState.FAILED
    assert run.failure_reason == "error: none: not allowed"


async def test_unclassified_transient_error_fails_after_retries(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    errors: list[Exception] = [GitError(f"git broke {n}") for n in range(6)]
    codex = FlakyAdapter("fake-codex", CODEX_MODEL, script(resumable=False), fake_clock, errors)
    env = await make_executor_env(adapters=_adapters(codex, fake_clock))

    run = await env.run_to_end()

    assert len(await _retries(env, run.id)) == 5
    assert codex.resumed == []
    assert run.state is AgentRunState.FAILED
    assert run.failure_reason == "error: none: git broke 5"
    assert await env.events(run.id, LedgerEventKind.MODEL_FALLBACK) == []


async def test_retry_restarts_when_session_cannot_resume(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    errors: list[Exception] = [RateLimited("slow down")]
    codex = FlakyAdapter(
        "fake-codex", CODEX_MODEL, script(), fake_clock, errors, refuse_resume=True
    )
    env = await make_executor_env(adapters=_adapters(codex, fake_clock))

    run = await env.run_to_end()

    assert run.state is AgentRunState.COMPLETED
    assert len(await _retries(env, run.id)) == 1
    assert len([e for e in codex.runs[run.id] if e.kind is AgentEventKind.STARTED]) == 2


async def test_cancel_during_retry_backoff_stops_the_run(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    errors: list[Exception] = [RateLimited("slow down")]
    codex = FlakyAdapter("fake-codex", CODEX_MODEL, script(), fake_clock, errors)
    holder: dict[str, ExecutorEnv] = {}
    cancels: list[asyncio.Task[AgentRun]] = []

    async def cancel_while_waiting(seconds: float) -> None:
        del seconds
        executor = holder["env"].executor
        run_id = executor.running()[0].id
        cancels.append(asyncio.create_task(executor.cancel(run_id, "user")))
        await asyncio.sleep(0)  # the cancel request lands while the run backs off

    env = await make_executor_env(adapters=_adapters(codex, fake_clock), sleep=cancel_while_waiting)
    holder["env"] = env

    await env.run_to_end()
    cancelled = await cancels[0]

    assert cancelled.state is AgentRunState.CANCELLED
    assert cancelled.tool_calls == 0
    assert codex.resumed == []
