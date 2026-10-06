import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_model_adapter import FakeModelAdapter, fake_descriptor
from tests.runtime.executor_env import (
    CLAUDE_MODEL,
    CODEX_MODEL,
    DyingAdapter,
    EnvFactory,
    ExecutorEnv,
    script,
)
from walk.model_router import AgentEventKind, ModelAdapter, NotResumable
from walk.runtime import RESUME_INSTRUCTION, AgentRun, AgentRunState, Checkpoint, CheckpointKind
from walk.telemetry import LedgerEventKind


def _adapters(codex: FakeModelAdapter, clock: FakeClock) -> dict[str, ModelAdapter]:
    claude = FakeModelAdapter(
        "fake-claude", [fake_descriptor(CLAUDE_MODEL, "fake-claude")], script(), clock
    )
    return {"fake-codex": codex, "fake-claude": claude}


async def _orphan(env: ExecutorEnv) -> tuple[AgentRun, Checkpoint]:
    """Run the story until the adapter 'dies'; mark the run INTERRUPTED like recovery does."""
    started = await env.executor.start(env.agent, env.story, "IMPLEMENT")
    orphan = await env.executor.wait(started.id)
    assert orphan.state is AgentRunState.RUNNING
    await env.runs.set_state(orphan.id, AgentRunState.INTERRUPTED)
    checkpoint = await env.checkpoints.latest(orphan.id)
    assert checkpoint is not None
    return orphan, checkpoint


async def test_resume_native_continues_session(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    codex = DyingAdapter("fake-codex", CODEX_MODEL, script(tool_calls=8), fake_clock, die_after=5)
    env = await make_executor_env(adapters=_adapters(codex, fake_clock), checkpoint_every=5)
    orphan, checkpoint = await _orphan(env)

    resumed = await env.executor.resume_native(checkpoint)
    done = await env.executor.wait(resumed.id)

    assert checkpoint.kind is CheckpointKind.PERIODIC
    assert checkpoint.tool_calls_so_far == 5
    assert resumed.parent_run_id == orphan.id
    assert resumed.model_id == CODEX_MODEL
    assert resumed.worktree_path == orphan.worktree_path
    assert resumed.provider_session == checkpoint.provider_session
    assert done.state is AgentRunState.COMPLETED
    assert done.tool_calls == 9  # 5 before the crash + calls 5 to 8 of the continued session
    events = codex.runs[resumed.id]
    assert events[0].kind is AgentEventKind.STARTED
    assert events[0].text == RESUME_INSTRUCTION
    requested = [e.tool_call.paths for e in events if e.tool_call is not None]
    assert requested[0] == ["src/Fake5.cs"]
    selected = (await env.events(resumed.id, LedgerEventKind.MODEL_SELECTED))[0]
    assert selected.payload == {"reason": "native_resume"}


async def test_resume_native_requires_resumable_and_healthy(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    codex = DyingAdapter(
        "fake-codex", CODEX_MODEL, script(tool_calls=8, resumable=False), fake_clock, die_after=5
    )
    env = await make_executor_env(adapters=_adapters(codex, fake_clock), checkpoint_every=5)
    _, not_resumable = await _orphan(env)

    with pytest.raises(NotResumable, match="no resumable provider session"):
        await env.executor.resume_native(not_resumable)

    resumable = not_resumable.model_copy(
        update={
            "provider_session": not_resumable.provider_session.model_copy(
                update={"resumable": True}
            )
            if not_resumable.provider_session is not None
            else None
        }
    )
    codex.set_healthy(False)
    with pytest.raises(NotResumable, match="unhealthy"):
        await env.executor.resume_native(resumable)
    assert len(await env.runs.for_item(env.story.id)) == 1

    codex.set_healthy(True)
    with pytest.raises(NotResumable, match="cannot be resumed"):
        await env.executor.resume_native(resumable)
    refused = (await env.runs.for_item(env.story.id))[-1]
    assert refused.state is AgentRunState.FAILED
    assert refused.failure_reason == "not_resumable"
    item = await env.items.get(env.story.id)
    assert item is not None
    assert item.assigned_run_id is None
