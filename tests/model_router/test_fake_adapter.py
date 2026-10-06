import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

import walk.agents
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_model_adapter import FakeModelAdapter, FakeScript, fake_descriptor
from walk.agents import (
    AgentInput,
    AgentOutput,
    AgentOutputStatus,
    ConstitutionLoader,
    ExpectedOutput,
    Handover,
)
from walk.common.enums import Effort
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.context import ContextBundle, ContextRequest
from walk.model_router import (
    AgentEvent,
    AgentEventKind,
    FallbackTrigger,
    ModelAdapter,
    NotResumable,
    ProviderSessionRef,
    RunSession,
    parse_agent_output,
)
from walk.permissions import PermissionDecision, PermissionEffect, ToolCallRequest
from walk.workflow import Story, StoryContract, WorkItemState

DEFAULTS = Path(walk.agents.__file__).resolve().parent / "defaults"
AT = datetime(2026, 1, 1, tzinfo=UTC)
K = AgentEventKind
DONE = AgentOutput(status=AgentOutputStatus.COMPLETED, result="done", no_context_change_reason="x")


def _input(run_id: str) -> AgentInput:
    constitution = ConstitutionLoader(DEFAULTS, None).load(AgentRole.SENIOR_DEV)
    story = Story(
        id="STORY-0001",
        project_key="DEMO",
        title="Run",
        contract=StoryContract(goal="Run"),
        created_at=AT,
        updated_at=AT,
    )
    request = ContextRequest(
        work_item_id="STORY-0001", role=AgentRole.SENIOR_DEV, effort=Effort.LOW, token_budget=1000
    )
    return AgentInput(
        run_id=run_id,
        role=AgentRole.SENIOR_DEV,
        constitution=constitution,
        authority=constitution.authority,
        task=story,
        workflow_state=WorkItemState.READY,
        phase=None,
        context=ContextBundle(
            request=request,
            items=[],
            total_tokens_estimate=0,
            excluded_count=0,
            built_at=AT,
            head_commit="3f9c2e1",
        ),
        approved_artifacts=[],
        decisions=[],
        skills=[],
        allowed_tools=[],
        permissions=[],
        budget=[],
        effort=Effort.LOW,
        required_evidence=[],
        expected_output=ExpectedOutput(
            status_options=[AgentOutputStatus.COMPLETED], deliverables=[], required_evidence=[]
        ),
        worktree_path="unused",
        branch="feat/x",
    )


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


async def _collect(stream: AsyncIterator[AgentEvent]) -> list[AgentEvent]:
    return [event async for event in stream]


def _adapter(fake_clock: FakeClock, script: FakeScript) -> FakeModelAdapter:
    return FakeModelAdapter(
        "fake-codex", [fake_descriptor("fake-codex/sim", "fake-codex")], script, fake_clock
    )


async def test_run_emits_normalised_stream_and_writes_output(
    fake_codex_adapter: FakeModelAdapter, run_session: RunSession
) -> None:
    adapter: ModelAdapter = fake_codex_adapter

    events = await _collect(adapter.run(_input(run_session.run_id), run_session))

    assert [e.kind for e in events] == [
        K.STARTED,
        *([K.TOOL_CALL_REQUESTED, K.TOOL_CALL_RESULT, K.USAGE] * 3),
        K.FINAL_OUTPUT,
        K.USAGE,
        K.ENDED,
    ]
    started = events[0]
    assert started.session == ProviderSessionRef(
        provider="fake-codex", session_id=f"fake-{run_session.run_id}", resumable=True
    )
    worktree = Path(run_session.worktree_path)
    for i in (1, 2, 3):
        assert (worktree / "src" / f"Fake{i}.cs").read_text(encoding="utf-8") == (
            f"// fake edit {i}\n"
        )
    request = events[1].tool_call
    assert request is not None
    assert request.tool == "edit"
    assert request.arguments == {"path": "src/Fake1.cs"}
    assert request.paths == ["src/Fake1.cs"]
    assert request.worktree_path == run_session.worktree_path
    assert events[2].tool_result == {"ok": True}
    final = events[-3]
    assert final.output is not None
    assert final.output.status is AgentOutputStatus.COMPLETED
    assert parse_agent_output(_read(run_session.output_path)) == final.output
    total = events[-2].usage
    assert total is not None
    assert (total.tool_calls, total.input_tokens) == (3, 3000)
    assert adapter.usage(run_session.run_id) == total
    assert fake_codex_adapter.runs[run_session.run_id] == events
    assert len(fake_codex_adapter.authorizations) == 3
    assert all(e.run_id == run_session.run_id for e in events)
    assert not any(e.text and "thinking" in e.text for e in events)


async def test_run_respects_denied_authorization(
    fake_codex_adapter: FakeModelAdapter, run_session: RunSession
) -> None:
    async def deny(request: ToolCallRequest) -> PermissionDecision:
        del request
        return PermissionDecision(effect=PermissionEffect.DENY, matched_rule=None, reason="nope")

    session = run_session.model_copy(update={"permission_authorizer": deny})

    events = await _collect(fake_codex_adapter.run(_input(session.run_id), session))

    results = [e.tool_result for e in events if e.kind is K.TOOL_CALL_RESULT]
    assert results == [{"ok": False, "reason": "nope"}] * 3
    assert not (Path(session.worktree_path) / "src").exists()
    assert events[-1].kind is K.ENDED


async def test_run_scripted_failure_emits_error_and_stops(
    fake_clock: FakeClock, run_session: RunSession
) -> None:
    script = FakeScript(
        tool_calls=12,
        output=DONE,
        fail_after_tool_calls=3,
        fail_trigger=FallbackTrigger.PROVIDER_OUTAGE,
        checkpoint_hint_at=[2],
    )
    adapter = _adapter(fake_clock, script)

    events = await _collect(adapter.run(_input(run_session.run_id), run_session))

    kinds = [e.kind for e in events]
    assert kinds.count(K.TOOL_CALL_RESULT) == 3
    assert kinds.count(K.CHECKPOINT_HINT) == 1
    assert kinds.index(K.CHECKPOINT_HINT) == 7
    assert events[-1].kind is K.ERROR
    assert events[-1].trigger is FallbackTrigger.PROVIDER_OUTAGE
    assert events[-1].error == "scripted failure"
    assert K.FINAL_OUTPUT not in kinds
    assert K.ENDED not in kinds


async def test_resume_continues_from_recorded_index(
    fake_clock: FakeClock, run_session: RunSession
) -> None:
    script = FakeScript(
        tool_calls=12,
        output=DONE,
        fail_after_tool_calls=3,
        fail_trigger=FallbackTrigger.PROVIDER_OUTAGE,
    )
    adapter = _adapter(fake_clock, script)
    first = await _collect(adapter.run(_input(run_session.run_id), run_session))
    ref = first[0].session
    assert ref is not None

    resumed = await _collect(adapter.resume(ref, "continue", run_session))

    kinds = [e.kind for e in resumed]
    assert resumed[0].kind is K.STARTED
    assert resumed[0].text == "continue"
    assert kinds.count(K.TOOL_CALL_RESULT) == 9
    paths = [e.tool_call.paths[0] for e in resumed if e.tool_call is not None]
    assert paths == [f"src/Fake{i}.cs" for i in range(4, 13)]
    assert kinds[-3:] == [K.FINAL_OUTPUT, K.USAGE, K.ENDED]
    assert adapter.usage(run_session.run_id).tool_calls == 12
    assert adapter.runs[run_session.run_id] == first + resumed


async def test_resume_not_resumable_raises(fake_clock: FakeClock, run_session: RunSession) -> None:
    adapter = _adapter(fake_clock, FakeScript(output=DONE, resumable=False))
    events = await _collect(adapter.run(_input(run_session.run_id), run_session))
    ref = events[0].session
    assert ref is not None
    assert ref.resumable is False

    with pytest.raises(NotResumable):
        await _collect(adapter.resume(ref, "continue", run_session))
    unknown = ProviderSessionRef(provider="fake-codex", session_id="fake-unknown", resumable=True)
    with pytest.raises(NotResumable):
        await _collect(adapter.resume(unknown, "continue", run_session))


async def test_invalid_output_then_repair(fake_clock: FakeClock, run_session: RunSession) -> None:
    adapter = _adapter(fake_clock, FakeScript(tool_calls=1, output=DONE, invalid_output_times=1))

    first = await _collect(adapter.run(_input(run_session.run_id), run_session))
    bad = next(e for e in first if e.kind is K.FINAL_OUTPUT)
    written = json.loads(_read(run_session.output_path))
    ref = first[0].session
    assert ref is not None
    repaired = await _collect(adapter.resume(ref, "fix status: BOGUS", run_session))

    assert bad.output is None
    assert bad.error == "scripted invalid output"
    assert written == {"status": "BOGUS"}
    good = next(e for e in repaired if e.kind is K.FINAL_OUTPUT)
    assert good.output == DONE
    assert K.TOOL_CALL_REQUESTED not in [e.kind for e in repaired]


async def test_partial_output_before_last_tool_call(
    fake_clock: FakeClock, run_session: RunSession
) -> None:
    handover = Handover(
        id="HO-0001",
        work_item_id="STORY-0001",
        role=AgentRole.SENIOR_DEV,
        from_run_id=run_session.run_id,
        from_model_id="fake-codex/sim",
        reason="PARTIAL",
        task_summary="t",
        current_state="c",
        completed_work=[],
        modified_files=[],
        findings=[],
        hypotheses=[],
        decisions=[],
        risks=[],
        remaining_work=[],
        next_action="n",
        worktree_head="3f9c2e1",
        branch="feat/x",
        created_at=AT,
    )
    partial = AgentOutput(
        status=AgentOutputStatus.PARTIAL,
        result="half",
        handover=handover,
        no_context_change_reason="x",
    )
    adapter = _adapter(fake_clock, FakeScript(tool_calls=2, output=DONE, partial_output=partial))

    events = await _collect(adapter.run(_input(run_session.run_id), run_session))

    kinds = [e.kind for e in events]
    assert kinds.index(K.PARTIAL_OUTPUT) == 4
    assert events[4].output == partial


async def test_cancel_stops_stream(fake_clock: FakeClock, run_session: RunSession) -> None:
    adapter = _adapter(fake_clock, FakeScript(tool_calls=5, output=DONE))
    events: list[AgentEvent] = []

    async for event in adapter.run(_input(run_session.run_id), run_session):
        events.append(event)
        if event.kind is K.TOOL_CALL_RESULT:
            await adapter.cancel(run_session.run_id)

    kinds = [e.kind for e in events]
    assert kinds[-1] is K.ENDED
    assert K.FINAL_OUTPUT not in kinds
    assert kinds.count(K.TOOL_CALL_RESULT) == 1
    await adapter.cancel("RUN-01J0000000000000000000ZZZZ")


async def test_map_effort_degrades(fake_clock: FakeClock) -> None:
    descriptor = fake_descriptor(
        "fake-codex/sim",
        "fake-codex",
        supports_effort_levels=[Effort.LOW, Effort.HIGH],
    )
    adapter = FakeModelAdapter("fake-codex", [descriptor], FakeScript(output=DONE), fake_clock)

    degraded = adapter.map_effort(Effort.VERY_HIGH, "fake-codex/sim")
    middle = adapter.map_effort(Effort.MEDIUM, "fake-codex/sim")
    exact = adapter.map_effort(Effort.HIGH, "fake-codex/sim")

    assert degraded.params == {"fake_effort": "HIGH", "degraded_from": "VERY_HIGH"}
    assert middle.params == {"fake_effort": "LOW", "degraded_from": "MEDIUM"}
    assert exact.params == {"fake_effort": "HIGH"}
    assert degraded.model_id == "fake-codex/sim"
    upward = FakeModelAdapter(
        "fake-codex",
        [fake_descriptor("fake-codex/sim", "fake-codex", supports_effort_levels=[Effort.HIGH])],
        FakeScript(output=DONE),
        fake_clock,
    )
    assert upward.map_effort(Effort.LOW, "fake-codex/sim").params == {
        "fake_effort": "HIGH",
        "degraded_from": "LOW",
    }
    with pytest.raises(ConfigError, match="nope/x"):
        adapter.map_effort(Effort.LOW, "nope/x")


async def test_health_toggle(fake_claude_adapter: FakeModelAdapter, fake_clock: FakeClock) -> None:
    healthy = await fake_claude_adapter.health()
    fake_claude_adapter.set_healthy(False)
    sick = await fake_claude_adapter.health()

    assert healthy.ok is True
    assert sick.ok is False
    assert sick.provider == "fake-claude"
    assert sick.checked_at == fake_clock.now()
    assert [d.id for d in fake_claude_adapter.descriptors()] == ["fake-claude/sim"]


async def test_skill_projector_and_parse_output_delegate(
    fake_codex_adapter: FakeModelAdapter,
) -> None:
    projector = fake_codex_adapter.skill_projector()
    assert projector.provider == "fake-codex"
    assert fake_codex_adapter.parse_output(DONE.model_dump_json()) == DONE
    assert fake_codex_adapter.usage("RUN-01J0000000000000000000ZZZZ").tool_calls == 0


async def test_script_factory_receives_input(
    fake_clock: FakeClock, run_session: RunSession
) -> None:
    seen: list[str] = []

    def factory(agent_input: AgentInput) -> FakeScript:
        seen.append(agent_input.task.id)
        return FakeScript(tool_calls=1, tool_name="write", output=DONE)

    adapter = FakeModelAdapter(
        "fake-codex", [fake_descriptor("fake-codex/sim", "fake-codex")], factory, fake_clock
    )

    events = await _collect(adapter.run(_input(run_session.run_id), run_session))

    assert seen == ["STORY-0001"]
    assert events[1].tool_call is not None
    assert events[1].tool_call.tool == "write"
