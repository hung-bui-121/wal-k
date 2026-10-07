import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import tests.fixtures.codex
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_codex_launcher import FakeCodexProcessLauncher
from tests.fakes.fake_model_adapter import FakeModelAdapter, fake_descriptor
from tests.runtime.executor_env import CODEX_MODEL, SENIOR, EnvFactory, script
from walk.agents import AgentInput
from walk.hooks import Hook, HookContext, HookName
from walk.model_router import AgentEvent, AgentEventKind, RunSession
from walk.model_router.adapters.codex import CodexAdapter
from walk.permissions import Approver, PermissionEffect, PermissionRule
from walk.runtime import AgentRunState, CheckpointKind
from walk.telemetry import LedgerEventKind
from walk.workflow import WorkItemState

FORBIDDEN = ".ai/agents/roles/qc.md"
CODEX_FIXTURES = Path(tests.fixtures.codex.__file__).resolve().parent


def _git(repo: str, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


async def test_violation_detected_before_wip_commit(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script(tool_calls=6), checkpoint_every=5)
    calls: list[str] = []

    async def write_forbidden(ctx: HookContext) -> None:
        calls.append(str(ctx.run_id))
        if len(calls) == 2:
            run = await env.runs.get(str(ctx.run_id))
            assert run is not None
            assert run.worktree_path is not None
            _write(Path(run.worktree_path) / FORBIDDEN, "# rogue role\n")

    env.hooks.register(
        Hook(name=HookName.ON_TOOL_AFTER, id="test.rogue", kind="builtin"), write_forbidden
    )

    run = await env.run_to_end()

    assert run.state is AgentRunState.FAILED_BOUNDARY
    assert run.failure_reason == f"boundary: {FORBIDDEN}"
    assert run.worktree_path is not None
    assert [c.kind for c in env.checkpoints_of(run.id)] == [CheckpointKind.START]
    assert _git(run.worktree_path, "status", "--porcelain") == ""
    assert _git(run.worktree_path, "log", "--format=%s", "-1") == "chore: initial commit"
    error = (await env.events(run.id, LedgerEventKind.ERROR))[0]
    assert error.outcome == "FAILED"
    assert error.payload == {"kind": "BOUNDARY", "violations": [FORBIDDEN]}
    assert len(env.hooks_fired(HookName.ON_TASK_FAILED)) == 1
    item = await env.items.get(env.story.id)
    assert item is not None
    assert item.state is WorkItemState.IMPLEMENTING
    assert item.assigned_run_id is None


class _AdvisoryAdapter(FakeModelAdapter):
    """Reports the second tool result as denied by the kernel, as the Codex adapter does."""

    def run(self, input: AgentInput, session: RunSession) -> AsyncIterator[AgentEvent]:  # noqa: A002 - parameter name fixed by INTERFACES §2.1
        return self._advise(super().run(input, session))

    async def _advise(self, inner: AsyncIterator[AgentEvent]) -> AsyncIterator[AgentEvent]:
        results = 0
        async for event in inner:
            if event.kind is AgentEventKind.TOOL_CALL_RESULT:
                results += 1
                decision = "DENY" if results == 2 else "ALLOW"
                result = {**(event.tool_result or {}), "kernel_decision": decision}
                yield event.model_copy(update={"tool_result": result})
            else:
                yield event


async def test_advisory_deny_fails_run(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    adapter = _AdvisoryAdapter(
        "fake-codex", [fake_descriptor(CODEX_MODEL, "fake-codex")], script(), fake_clock
    )
    env = await make_executor_env(adapters={"fake-codex": adapter})

    run = await env.run_to_end()

    assert run.state is AgentRunState.FAILED_BOUNDARY
    assert run.failure_reason == "boundary: src/Fake2.cs"
    assert run.output is None
    assert [c.kind for c in env.checkpoints_of(run.id)] == [CheckpointKind.START]
    item = await env.items.get(env.story.id)
    assert item is not None
    assert item.state is WorkItemState.IMPLEMENTING
    assert await env.ledger.query(kinds=[LedgerEventKind.WORK_ITEM_TRANSITION]) == []


async def test_codex_run_is_never_paused_for_approval(
    make_executor_env: EnvFactory, fake_clock: FakeClock
) -> None:
    lines = (CODEX_FIXTURES / "exec_success.jsonl").read_text(encoding="utf-8").splitlines()
    adapter = CodexAdapter(
        FakeCodexProcessLauncher(lines),
        [fake_descriptor("codex/gpt-5-codex", "codex")],
        fake_clock,
        system_prompt_builder=lambda agent_input: f"role {agent_input.role.value}",
        user_message_builder=lambda agent_input: agent_input.instructions_markdown,
    )
    rules = [
        PermissionRule(role=SENIOR, tool="edit", effect=PermissionEffect.ALLOW),
        PermissionRule(
            role=SENIOR,
            tool="dotnet",
            effect=PermissionEffect.REQUIRE_APPROVAL,
            approver=Approver.USER,
            command_patterns=[".*"],
        ),
    ]
    env = await make_executor_env(
        adapters={"codex": adapter}, model_id="codex/gpt-5-codex", rules=rules
    )

    run = await env.run_to_end()

    assert run.state is AgentRunState.FAILED_BOUNDARY
    assert run.failure_reason == "boundary: bash"
    states = [
        row[0]
        for row in env.db.connect()
        .execute("SELECT json_extract(json, '$.state') FROM agent_runs")
        .fetchall()
    ]
    assert states == ["FAILED_BOUNDARY"]
    assert await env.ledger.query(kinds=[LedgerEventKind.APPROVAL_REQUESTED]) == []
    assert all(c.kind is not CheckpointKind.PAUSE for c in env.checkpoints_of(run.id))
    denied = await env.events(run.id, LedgerEventKind.TOOL_DENIED)
    assert [event.tool for event in denied] == ["dotnet"]
    assert "requires USER approval" in str(denied[0].payload["reason"])
    assert run.tool_calls == 2


async def test_role_and_kernel_allowed_paths_bound_the_run(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script(tool_calls=2))
    policy = env.agent.runtime_policy.model_copy(update={"allowed_paths": []})  # QC (E02-S14)
    reviewer = env.agent.model_copy(update={"runtime_policy": policy})

    started = await env.executor.start(reviewer, env.story, "IMPLEMENT")
    run = await env.executor.wait(started.id)

    assert run.state is AgentRunState.FAILED_BOUNDARY
    assert "src/Fake1.cs" in str(run.failure_reason)


async def test_kernel_allowed_paths_also_apply(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script(tool_calls=2), allowed_paths=("Assets/**",))

    run = await env.run_to_end()

    assert run.state is AgentRunState.FAILED_BOUNDARY
    assert "src/Fake1.cs" in str(run.failure_reason)
