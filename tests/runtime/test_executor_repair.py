from collections.abc import AsyncIterator

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_model_adapter import FakeModelAdapter, fake_descriptor
from tests.runtime.executor_env import CODEX_MODEL, EnvFactory, script
from walk.model_router import AgentEvent, NotResumable, ProviderSessionRef, RunSession
from walk.runtime import MAX_REPAIR_TURNS, REPAIR_INSTRUCTION, AgentRunState
from walk.telemetry import LedgerEventKind
from walk.workflow import WorkItemState

RETRY = LedgerEventKind.RETRY


async def test_invalid_output_repaired_once(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script(invalid_output_times=1))

    run = await env.run_to_end()

    retries = await env.events(run.id, RETRY)
    assert len(retries) == 1
    assert retries[0].payload["reason"] == "output_invalid"
    assert retries[0].payload["errors"] == "scripted invalid output"
    assert run.repair_turns == 1 == MAX_REPAIR_TURNS
    assert run.state is AgentRunState.COMPLETED
    item = await env.items.get(env.story.id)
    assert item is not None
    assert item.state is WorkItemState.READY_FOR_REVIEW
    adapter = env.adapters["fake-codex"]
    assert isinstance(adapter, FakeModelAdapter)
    resumed = [e for e in adapter.runs[run.id] if e.text is not None]
    assert resumed[0].text == REPAIR_INSTRUCTION.format(errors="scripted invalid output")


async def test_invalid_output_twice_fails(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script(invalid_output_times=2))

    run = await env.run_to_end()

    assert run.state is AgentRunState.FAILED
    assert str(run.failure_reason).startswith("output_invalid")
    assert len(await env.events(run.id, RETRY)) == 1
    error = (await env.events(run.id, LedgerEventKind.ERROR))[0]
    assert error.payload["kind"] == "OUTPUT_INVALID"


async def test_status_outside_expected_options_is_invalid(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script(tool_calls=1))

    run = await env.run_to_end("REVIEW")

    retries = await env.events(run.id, RETRY)
    assert len(retries) == 1
    assert retries[0].payload["errors"] == "status COMPLETED not allowed for REVIEW"
    assert run.repair_turns == 1
    assert run.state is AgentRunState.FAILED
    assert run.failure_reason == "output_invalid: status COMPLETED not allowed for REVIEW"


async def test_no_repair_when_session_not_resumable(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script(invalid_output_times=1, resumable=False))

    run = await env.run_to_end()

    assert await env.events(run.id, RETRY) == []
    assert run.repair_turns == 0
    assert run.state is AgentRunState.FAILED
    assert run.failure_reason == "output_invalid: scripted invalid output"


class _ForgetfulAdapter(FakeModelAdapter):
    """Reports a resumable session but cannot resume it."""

    def resume(
        self, session_ref: ProviderSessionRef, instruction: str, session: RunSession
    ) -> AsyncIterator[AgentEvent]:
        del session_ref, instruction, session
        msg = "session expired"
        raise NotResumable(msg)


async def test_repair_turn_not_resumable_by_adapter_fails(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapter = _ForgetfulAdapter(
        "fake-codex",
        [fake_descriptor(CODEX_MODEL, "fake-codex")],
        script(invalid_output_times=1),
        fake_clock,
    )
    env = await make_executor_env(adapters={"fake-codex": adapter})

    run = await env.run_to_end()

    assert run.state is AgentRunState.FAILED
    assert run.failure_reason == "output_invalid: scripted invalid output"
    assert len(await env.events(run.id, RETRY)) == 1
