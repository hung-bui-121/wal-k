import subprocess
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.hooks.conftest import BuiltinEnvFactory, holding_adapters
from tests.runtime.conftest import RUN_A, RUN_B, RunFactory, make_run
from walk.common.errors import ConfigError
from walk.common.models import Actor
from walk.common.roles import AgentRole
from walk.hooks import (
    DefaultHookManager,
    HookExecutionRepository,
    HookFailed,
    HookFailPolicy,
    HookName,
)
from walk.memory import MemoryDocType, doc_path_for, skeleton_for
from walk.orchestrator import register_builtins
from walk.orchestrator.builtin_hooks import MUST_HOOK_IDS
from walk.permissions import Approver
from walk.runtime import AgentRun, AgentRunState, CheckpointKind, branch_name_for

MUST_TABLE = (
    (HookName.ON_PROJECT_PAUSE, "builtin.pause_all_runs"),
    (HookName.ON_TASK_START, "builtin.ensure_branch"),
    (HookName.ON_TASK_COMPLETE, "builtin.remaining_work_check"),
    (HookName.ON_AGENT_CHECKPOINT, "builtin.wip_commit"),
    (HookName.ON_AGENT_END, "builtin.final_checkpoint"),
    (HookName.ON_AGENT_HANDOFF, "builtin.handoff_checkpoint_and_handover"),
    (HookName.ON_MODEL_FALLBACK, "builtin.fallback_chain"),
    (HookName.ON_BUDGET_EXHAUSTED, "builtin.budget_escalate"),
    (HookName.ON_PROTECTED_ACTION_REQUESTED, "builtin.approval_recorded"),
    (HookName.ON_TASK_CANCELLED, "builtin.cancel_cleanup"),
    (HookName.ON_RECOVERY_RESUME, "builtin.load_handover"),
)
BUDGET_ID = "TASK:STORY-0001:TOOL_CALLS"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def _is_dir(path: str) -> bool:
    return Path(path).is_dir()


def _budget_payload(hard_action: str) -> dict[str, object]:
    return {
        "budget_id": BUDGET_ID,
        "scope": "TASK",
        "scope_id": "STORY-0001",
        "dimension": "TOOL_CALLS",
        "consumed": 2.0,
        "limit": 2.0,
        "hard_action": hard_action,
    }


async def test_all_must_hooks_registered_required_low_priority(
    make_builtin_env: BuiltinEnvFactory,
) -> None:
    built = await make_builtin_env()

    assert tuple(hook_id for _, hook_id in MUST_TABLE) == MUST_HOOK_IDS
    for name, hook_id in MUST_TABLE:
        hook = next(h for h in built.env.hooks.hooks_for(name) if h.id == hook_id)
        assert hook.required is True
        assert hook.kind == "builtin"
        assert hook.priority < 50
        assert hook.fail_policy is HookFailPolicy.FAIL_CLOSED


async def test_memory_index_is_a_default_attachment(make_builtin_env: BuiltinEnvFactory) -> None:
    built = await make_builtin_env()

    hooks = built.env.hooks.hooks_for(HookName.ON_PROJECT_START)

    assert [h.id for h in hooks] == ["builtin.memory_index"]
    assert hooks[0].required is False
    assert hooks[0].priority == 60
    assert hooks[0].fail_policy is HookFailPolicy.LOG_AND_CONTINUE
    results = await built.fire(HookName.ON_PROJECT_START)
    assert [r.status for r in results] == ["OK"]


async def test_register_builtins_twice_raises(make_builtin_env: BuiltinEnvFactory) -> None:
    built = await make_builtin_env()

    with pytest.raises(ConfigError, match="builtin hooks already registered"):
        register_builtins(built.env.hooks, built.deps)


async def test_project_pause_pauses_all_running_runs(
    make_builtin_env: BuiltinEnvFactory, fake_clock: FakeClock
) -> None:
    built = await make_builtin_env(adapters=holding_adapters(fake_clock), max_parallel_runs=2)
    first = await built.start_held()
    second = await built.start_held(await built.add_story(2))

    results = await built.fire(HookName.ON_PROJECT_PAUSE)

    assert [r.status for r in results] == ["OK"]
    for run in (first, second):
        stored = await built.env.runs.get(run.id)
        assert stored is not None
        assert stored.state is AgentRunState.PAUSED_BY_USER
    pauses = [
        c
        for run in (first, second)
        for c in built.checkpoints(run.id)
        if c.kind is CheckpointKind.PAUSE
    ]
    assert len(pauses) == 2
    assert built.env.executor.running() == []


class _StubExecutor:
    """Two running runs; pausing the first one fails."""

    def __init__(self) -> None:
        self.paused: list[str] = []

    def running(self) -> list[AgentRun]:
        return [make_run(RUN_A), make_run(RUN_B)]

    async def pause(self, run_id: str) -> AgentRun:
        if run_id == RUN_A:
            msg = "worktree gone"
            raise ConfigError(msg)
        self.paused.append(run_id)
        return make_run(run_id)


async def test_project_pause_reports_every_run_it_could_not_pause(
    make_builtin_env: BuiltinEnvFactory, fake_clock: FakeClock
) -> None:
    built = await make_builtin_env()
    stub = _StubExecutor()
    manager = DefaultHookManager(
        HookExecutionRepository(built.env.db), built.env.ledger, fake_clock
    )
    register_builtins(manager, built.deps.model_copy(update={"executor": stub}))

    with pytest.raises(HookFailed):
        await manager.fire(HookName.ON_PROJECT_PAUSE, built.context(HookName.ON_PROJECT_PAUSE))

    assert stub.paused == [RUN_B]
    failed = built.env.db.connect().execute(
        "SELECT message FROM hook_executions WHERE hook_id = 'builtin.pause_all_runs'"
    )
    message = str(failed.fetchone()[0])
    assert RUN_A in message
    assert RUN_B not in message


async def test_task_start_ensures_branch_idempotently(make_builtin_env: BuiltinEnvFactory) -> None:
    built = await make_builtin_env()
    branch = branch_name_for(built.env.story)

    first = await built.fire(HookName.ON_TASK_START, work_item_id=built.env.story.id)
    assert _git(built.env.repo, "branch", "--list", branch).endswith(branch)
    _git(built.env.repo, "branch", "-D", branch)
    second = await built.fire(HookName.ON_TASK_START, work_item_id=built.env.story.id)

    assert [r.status for r in first] == ["OK"]
    assert [r.status for r in second] == ["OK"]
    assert _git(built.env.repo, "branch", "--list", branch) == ""  # replayed, git untouched
    assert (
        await built.env.git.ensure_branch(
            branch, "main", idempotency_key=f"git.branch:{built.env.story.id}"
        )
        == branch
    )


async def test_task_start_without_work_item_fails_closed(
    make_builtin_env: BuiltinEnvFactory,
) -> None:
    built = await make_builtin_env()

    with pytest.raises(HookFailed):
        await built.fire(HookName.ON_TASK_START)

    assert built.executions("builtin.ensure_branch") == ["FAILED"]


async def test_model_fallback_chains_handoff_checkpoint_and_handover(
    make_builtin_env: BuiltinEnvFactory, insert_run: RunFactory, tmp_game_repo: Path
) -> None:
    built = await make_builtin_env()
    run = await insert_run(worktree_path=str(tmp_game_repo), branch="main")
    handover = await built.env.checkpoints.build_handover(run, "FALLBACK", None)
    payload = {"trigger": "PROVIDER_OUTAGE", "handover": handover.model_dump(mode="json")}

    results = await built.fire(
        HookName.ON_MODEL_FALLBACK, run_id=run.id, work_item_id=run.work_item_id, payload=payload
    )

    assert {r.status for r in results} == {"OK"}
    assert [c.kind for c in built.checkpoints(run.id)] == [CheckpointKind.HANDOFF]
    assert built.checkpoints(run.id)[0].handover_id == "HO-0001"
    assert (built.env.db.path.parent / "handovers" / "HO-0001.md").is_file()
    assert built.executions("builtin.handoff_checkpoint_and_handover") == ["OK"]


async def test_handoff_without_handover_fails_closed(make_builtin_env: BuiltinEnvFactory) -> None:
    built = await make_builtin_env()

    with pytest.raises(HookFailed) as raised:
        await built.fire(HookName.ON_AGENT_HANDOFF, run_id="RUN-01J0000000000000000000000A")

    assert "handover" in str(raised.value.detail["results"])
    assert built.executions("builtin.handoff_checkpoint_and_handover") == ["FAILED"]


async def test_budget_exhausted_non_block_does_not_escalate(
    make_builtin_env: BuiltinEnvFactory,
) -> None:
    built = await make_builtin_env()

    for action in ("FALLBACK_MODEL", "DOWNGRADE_EFFORT"):
        results = await built.fire(
            HookName.ON_BUDGET_EXHAUSTED,
            work_item_id=built.env.story.id,
            payload=_budget_payload(action),
        )
        assert [r.status for r in results] == ["OK"]

    assert await built.env.permissions.pending() == []


async def test_budget_escalation_is_once_per_budget(make_builtin_env: BuiltinEnvFactory) -> None:
    built = await make_builtin_env()

    for _ in range(2):
        await built.fire(
            HookName.ON_BUDGET_EXHAUSTED,
            work_item_id=built.env.story.id,
            payload=_budget_payload("BLOCK"),
        )

    pending = await built.env.permissions.pending(Approver.USER)
    assert [(a.kind, a.payload["budget_id"]) for a in pending] == [("ESCALATION", BUDGET_ID)]
    assert pending[0].requested_by_role is AgentRole.KERNEL
    assert pending[0].work_item_id == built.env.story.id
    assert built.executions("builtin.budget_escalate") == ["OK", "OK"]
    assert built.executions("builtin.approval_recorded") == ["OK"]


async def test_budget_exhausted_without_hard_action_fails_closed(
    make_builtin_env: BuiltinEnvFactory,
) -> None:
    built = await make_builtin_env()

    with pytest.raises(HookFailed) as raised:
        await built.fire(HookName.ON_BUDGET_EXHAUSTED, payload={"budget_id": BUDGET_ID})

    assert "hard_action" in str(raised.value.detail["results"])


async def test_approval_recorded_guard_needs_approval_id_and_kind(
    make_builtin_env: BuiltinEnvFactory,
) -> None:
    built = await make_builtin_env()

    ok = await built.fire(
        HookName.ON_PROTECTED_ACTION_REQUESTED, payload={"approval_id": "APV-0001", "kind": "X"}
    )
    with pytest.raises(HookFailed) as raised:
        await built.fire(HookName.ON_PROTECTED_ACTION_REQUESTED, payload={"kind": "X"})

    assert [r.status for r in ok] == ["OK"]
    assert "approval_id" in str(raised.value.detail["results"])


async def test_load_handover_accepts_native_resume_without_handover(
    make_builtin_env: BuiltinEnvFactory,
) -> None:
    built = await make_builtin_env()

    native = await built.fire(
        HookName.ON_RECOVERY_RESUME, payload={"mode": "native", "handover_id": None}
    )
    with pytest.raises(HookFailed) as raised:
        await built.fire(
            HookName.ON_RECOVERY_RESUME, payload={"mode": "handover", "handover_id": None}
        )

    assert {r.status for r in native} == {"OK"}
    assert "handover_id" in str(raised.value.detail["results"])
    assert built.executions("builtin.load_handover") == ["OK", "FAILED"]


async def test_load_handover_reads_the_handover_document(
    make_builtin_env: BuiltinEnvFactory, insert_run: RunFactory, tmp_game_repo: Path
) -> None:
    built = await make_builtin_env()
    run = await insert_run(worktree_path=str(tmp_game_repo), branch="main")
    handover = await built.env.checkpoints.build_handover(run, "RECOVERY", None)
    await built.env.checkpoints.checkpoint(
        run, CheckpointKind.HANDOFF, handover=handover, workflow_state=built.env.story.state
    )

    found = await built.fire(
        HookName.ON_RECOVERY_RESUME, payload={"mode": "handover", "handover_id": "HO-0001"}
    )
    with pytest.raises(HookFailed):
        await built.fire(
            HookName.ON_RECOVERY_RESUME, payload={"mode": "handover", "handover_id": "HO-0099"}
        )
    with pytest.raises(HookFailed):
        await built.fire(HookName.ON_RECOVERY_RESUME, payload={"mode": "sideways"})

    assert {r.status for r in found} == {"OK"}


async def test_task_complete_counts_remaining_work_without_failing(
    make_builtin_env: BuiltinEnvFactory,
) -> None:
    built = await make_builtin_env()
    actor = Actor(role=AgentRole.KERNEL)
    clock = built.env.executor._clock  # noqa: SLF001 - the environment's clock
    doc = skeleton_for(MemoryDocType.FEATURE, "FEAT-0001", "Jump", actor, clock.now())
    doc.sections["Remaining Work"] = "- Wire the jump button"
    done = skeleton_for(MemoryDocType.FEATURE, "FEAT-0002", "Run", actor, clock.now())
    done.sections["Remaining Work"] = "- none"
    head = _git(built.env.repo, "rev-parse", "HEAD")
    for document in (doc, done):
        await built.env.memory.write(document, actor=actor, head=head, branch="main")

    open_work = await built.fire(HookName.ON_TASK_COMPLETE, work_item_id="FEAT-0001")
    cleared = await built.fire(HookName.ON_TASK_COMPLETE, work_item_id="FEAT-0002")
    missing = await built.fire(HookName.ON_TASK_COMPLETE, work_item_id="FEAT-0003")
    no_item = await built.fire(HookName.ON_TASK_COMPLETE)

    assert built.telemetry.counters == {"remaining_work_nonempty": 1.0}
    for results in (open_work, cleared, missing, no_item):
        assert [r.status for r in results] == ["OK"]


async def test_task_cancelled_cancels_running_run_only(
    make_builtin_env: BuiltinEnvFactory, fake_clock: FakeClock
) -> None:
    built = await make_builtin_env(adapters=holding_adapters(fake_clock))
    run = await built.start_held()

    cancelled = await built.fire(
        HookName.ON_TASK_CANCELLED,
        run_id=run.id,
        work_item_id=run.work_item_id,
        payload={"reason": "user"},
    )
    again = await built.fire(
        HookName.ON_TASK_CANCELLED, run_id=run.id, work_item_id=run.work_item_id, payload={}
    )
    no_run = await built.fire(HookName.ON_TASK_CANCELLED, work_item_id=run.work_item_id)

    stored = await built.env.runs.get(run.id)
    assert stored is not None
    assert stored.state is AgentRunState.CANCELLED
    assert stored.failure_reason == "user"
    assert not _is_dir(run.worktree_path or "")
    for results in (cancelled, again, no_run):
        assert [r.status for r in results] == ["OK"]
    assert len([c for c in built.checkpoints(run.id) if c.kind is CheckpointKind.PAUSE]) == 1


async def test_wip_commit_guard(make_builtin_env: BuiltinEnvFactory) -> None:
    built = await make_builtin_env()

    with pytest.raises(HookFailed):
        await built.fire(HookName.ON_AGENT_CHECKPOINT, payload={"wip_commit_done": False})
    with pytest.raises(HookFailed) as missing:
        await built.fire(HookName.ON_AGENT_CHECKPOINT, payload={})
    ok = await built.fire(HookName.ON_AGENT_CHECKPOINT, payload={"wip_commit_done": True})

    assert "wip_commit_done" in str(missing.value.detail["results"])
    assert ok[-1].hook_id == "test.checkpoint"
    assert built.executions("builtin.wip_commit") == ["FAILED", "FAILED", "OK"]


async def test_task_complete_ignores_an_unreadable_document(
    make_builtin_env: BuiltinEnvFactory,
) -> None:
    built = await make_builtin_env()
    path = doc_path_for(built.env.db.path.parent, MemoryDocType.FEATURE, "FEAT-0009")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"---\nid: [unclosed\n---\n")

    results = await built.fire(HookName.ON_TASK_COMPLETE, work_item_id="FEAT-0009")

    assert [r.status for r in results] == ["OK"]
    assert built.telemetry.counters == {}


async def test_handoff_for_an_unknown_run_fails_closed(
    make_builtin_env: BuiltinEnvFactory, insert_run: RunFactory, tmp_game_repo: Path
) -> None:
    built = await make_builtin_env()
    run = await insert_run(worktree_path=str(tmp_game_repo), branch="main")
    handover = await built.env.checkpoints.build_handover(run, "FALLBACK", None)
    payload = {"handover": handover.model_dump(mode="json")}

    with pytest.raises(HookFailed) as raised:
        await built.fire(HookName.ON_AGENT_HANDOFF, run_id=RUN_B, payload=payload)

    assert RUN_B in str(raised.value.detail["results"])
    assert built.checkpoints(RUN_B) == []
