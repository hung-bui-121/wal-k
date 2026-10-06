import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_git_provider import FakeGitProvider
from tests.runtime.conftest import AT, RUN_A, RUN_B, STORY_ID, RunFactory, make_run
from walk.agents import (
    AgentOutput,
    AgentOutputStatus,
    Finding,
    Handover,
    NextAction,
    from_document,
)
from walk.budgets import BudgetDimension
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.context import ContextBundleRef
from walk.decisions import AutonomyLevel, DecisionCategory, DecisionProposal
from walk.hooks import DefaultHookManager, Hook, HookContext, HookName
from walk.integrations import GitCliProvider, GitError, GitProvider
from walk.memory import DefaultMemoryManager
from walk.persistence import Database, IdempotencyStore, IdSequenceStore, UnitOfWork
from walk.runtime import (
    AgentRun,
    AgentRunRepository,
    AgentRunState,
    CheckpointKind,
    CheckpointRepository,
    DefaultCheckpointManager,
    DefaultSandboxManager,
    HandoverRepository,
)
from walk.telemetry import DefaultLedgerManager, LedgerEvent, LedgerEventKind, LedgerRepository
from walk.workflow import Story, WorkItemState

IMPLEMENTING = WorkItemState.IMPLEMENTING
DEFAULT_NEXT = "Continue the task from the current worktree state"

ManagerFactory = Callable[..., DefaultCheckpointManager]


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return done.stdout.strip()


class _FailingLedger(DefaultLedgerManager):
    async def append(self, event: LedgerEvent, *, uow: UnitOfWork | None = None) -> LedgerEvent:
        if event.kind is LedgerEventKind.CHECKPOINT_CREATED:
            msg = "ledger write failed"
            raise RuntimeError(msg)
        return await super().append(event, uow=uow)


@pytest.fixture
def make_manager(
    *,
    db: Database,
    runs: AgentRunRepository,
    checkpoints: CheckpointRepository,
    handovers: HandoverRepository,
    memory: DefaultMemoryManager,
    hooks: DefaultHookManager,
    ledger: DefaultLedgerManager,
    idempotency: IdempotencyStore,
    fake_clock: FakeClock,
) -> ManagerFactory:
    def build(
        git: GitProvider, *, ledger_override: DefaultLedgerManager | None = None
    ) -> DefaultCheckpointManager:
        return DefaultCheckpointManager(
            db,
            runs,
            checkpoints,
            handovers,
            git,
            memory,
            hooks,
            ledger_override or ledger,
            IdSequenceStore(db),
            idempotency,
            fake_clock,
            project_key="DEMO",
        )

    return build


@pytest.fixture
async def running(
    git: GitCliProvider, tmp_game_repo: Path, insert_run: RunFactory, story: Story
) -> AgentRun:
    run = await insert_run(RUN_A, state=AgentRunState.RUNNING, tool_calls=4)
    sandbox = DefaultSandboxManager(tmp_game_repo, git, ["main"])
    run.worktree_path = await sandbox.create(run, story)
    run.branch = "feat/story-0001-player-jump-double-jump"
    return run


def _ledger_kinds(db: Database) -> list[str]:
    return [
        row["kind"] for row in db.connect().execute("SELECT kind FROM ledger_events ORDER BY seq")
    ]


async def test_checkpoint_makes_wip_commit_and_records(
    *,
    running: AgentRun,
    git: GitCliProvider,
    make_manager: ManagerFactory,
    db: Database,
    hooks: DefaultHookManager,
    fake_clock: FakeClock,
    checkpoint_fired: list[HookContext],
) -> None:
    worktree = Path(running.worktree_path or "")
    (worktree / "Jump.cs").write_text("class Jump {}\n", encoding="utf-8")
    in_transaction: list[bool] = []

    async def probe(ctx: HookContext) -> None:
        del ctx
        in_transaction.append(db.connect().in_transaction)

    hooks.register(Hook(name=HookName.ON_AGENT_CHECKPOINT, id="test.tx", kind="builtin"), probe)
    manifest = ContextBundleRef(item_ids=["ctx-1"], total_tokens_estimate=120)

    checkpoint = await make_manager(git).checkpoint(
        running,
        CheckpointKind.PERIODIC,
        workflow_state=IMPLEMENTING,
        budget_consumed={BudgetDimension.TOKENS: 1200.0},
        context_manifest=manifest,
    )

    assert _git(worktree, "log", "-1", "--format=%s") == "wip(STORY-0001): checkpoint 1"
    assert "Walk-Work-Item: STORY-0001" in _git(worktree, "log", "-1", "--format=%B")
    assert checkpoint.head_sha == _git(worktree, "rev-parse", "HEAD")
    assert checkpoint.wip_commit_sha == checkpoint.head_sha
    assert checkpoint.seq == 1
    assert checkpoint.dirty_files == []
    assert checkpoint.tool_calls_so_far == 4
    assert checkpoint.workflow_state is IMPLEMENTING
    assert checkpoint.budget_consumed == {BudgetDimension.TOKENS: 1200.0}
    assert checkpoint.context_manifest == manifest
    assert checkpoint.at == fake_clock.now()
    row = db.connect().execute("SELECT seq, kind, head_sha FROM checkpoints").fetchone()
    assert (row["seq"], row["kind"], row["head_sha"]) == (1, "PERIODIC", checkpoint.head_sha)
    kinds = _ledger_kinds(db)
    assert kinds.count("CHECKPOINT_CREATED") == 1
    assert kinds.index("CHECKPOINT_CREATED") < kinds.index("HOOK_EXECUTED")  # hook after commit
    event = (
        db.connect()
        .execute("SELECT json FROM ledger_events WHERE kind='CHECKPOINT_CREATED'")
        .fetchone()
    )
    stored = LedgerEvent.model_validate_json(event["json"])
    assert stored.payload == {
        "seq": 1,
        "kind": "PERIODIC",
        "head_sha": checkpoint.head_sha,
        "wip_commit_sha": checkpoint.wip_commit_sha,
        "handover_id": None,
    }
    assert stored.run_id == RUN_A
    assert stored.actor_role is AgentRole.SENIOR_DEV
    assert len(checkpoint_fired) == 1
    assert checkpoint_fired[0].payload["checkpoint_id"] == checkpoint.id
    assert in_transaction == [False]  # fired after the commit


async def test_checkpoint_on_clean_worktree(
    running: AgentRun, git: GitCliProvider, make_manager: ManagerFactory, db: Database
) -> None:
    worktree = Path(running.worktree_path or "")
    before = _git(worktree, "rev-parse", "HEAD")

    checkpoint = await make_manager(git).checkpoint(
        running, CheckpointKind.PERIODIC, workflow_state=IMPLEMENTING
    )

    assert checkpoint.wip_commit_sha is None
    assert checkpoint.head_sha == before
    assert checkpoint.context_manifest == ContextBundleRef(item_ids=[], total_tokens_estimate=0)
    assert checkpoint.budget_consumed == {}
    count = db.connect().execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0]
    assert count == 1


async def test_checkpoint_with_handover_writes_document(
    running: AgentRun,
    git: GitCliProvider,
    make_manager: ManagerFactory,
    db: Database,
    runs: AgentRunRepository,
) -> None:
    manager = make_manager(git)
    handover = await manager.build_handover(running, "FALLBACK", None)
    assert handover.id == "HO-0001"

    checkpoint = await manager.checkpoint(
        running, CheckpointKind.HANDOFF, handover=handover, workflow_state=IMPLEMENTING
    )

    assert checkpoint.handover_id == "HO-0001"
    document = db.path.parent / "handovers" / "HO-0001.md"
    text = document.read_text(encoding="utf-8")
    for heading in ("## Task", "## Current State", "## Remaining Work", "## Next Action"):
        assert heading in text
    assert _ledger_kinds(db).count("HANDOVER_CREATED") == 1
    assert running.handover_out_id == "HO-0001"
    stored = await runs.get(RUN_A)
    assert stored is not None
    assert stored.handover_out_id == "HO-0001"
    row = db.connect().execute("SELECT work_item_id, from_run_id, reason FROM handovers").fetchone()
    assert (row["work_item_id"], row["from_run_id"], row["reason"]) == (STORY_ID, RUN_A, "FALLBACK")
    assert await manager.latest_open_handover(STORY_ID) == handover
    doc = await manager.latest_open_handover_doc(STORY_ID)
    assert doc is not None
    assert doc.front_matter.id == "HO-0001"
    closed = await manager.close_handover("HO-0001", RUN_B)
    assert closed.to_run_id == RUN_B
    assert await manager.latest_open_handover(STORY_ID) is None
    assert await manager.latest_open_handover_doc(STORY_ID) is None


async def test_checkpoint_row_and_ledger_are_atomic(
    *,
    running: AgentRun,
    git: GitCliProvider,
    make_manager: ManagerFactory,
    db: Database,
    fake_clock: FakeClock,
    checkpoint_fired: list[HookContext],
) -> None:
    worktree = Path(running.worktree_path or "")
    (worktree / "Jump.cs").write_text("class Jump {}\n", encoding="utf-8")
    failing = _FailingLedger(db, LedgerRepository(db), IdSequenceStore(db), fake_clock)
    handover = await make_manager(git).build_handover(running, "PAUSE", None)

    with pytest.raises(RuntimeError, match="ledger write failed"):
        await make_manager(git, ledger_override=failing).checkpoint(
            running, CheckpointKind.HANDOFF, handover=handover, workflow_state=IMPLEMENTING
        )

    assert db.connect().execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0] == 0
    assert db.connect().execute("SELECT COUNT(*) FROM handovers").fetchone()[0] == 0
    assert checkpoint_fired == []
    wip = _git(worktree, "rev-parse", "HEAD")  # the git commit exists already

    replayed = await make_manager(git).checkpoint(
        running, CheckpointKind.HANDOFF, handover=handover, workflow_state=IMPLEMENTING
    )

    assert replayed.seq == 1
    assert replayed.wip_commit_sha == wip
    assert _git(worktree, "rev-list", "--count", "HEAD", "^main") == "1"
    assert _ledger_kinds(db).count("HANDOVER_CREATED") == 1  # document written once
    assert db.connect().execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0] == 1


def _partial_output() -> AgentOutput:
    embedded = Handover(
        id="HO-0042",
        work_item_id=STORY_ID,
        role=AgentRole.SENIOR_DEV,
        from_run_id=RUN_A,
        from_model_id="codex/gpt-5-codex",
        reason="PARTIAL",
        task_summary="agent's own summary",
        current_state="agent's own state",
        completed_work=[],
        modified_files=[],
        findings=[],
        hypotheses=["Coyote time interferes"],
        decisions=[],
        proposed_decisions=[],
        risks=["Physics tuning may regress"],
        remaining_work=["Wire the jump button", "Tune gravity"],
        next_action="Wire the jump button",
        worktree_head="3f9c2e1",
        branch="feat/story-0001",
        created_at=AT,
    )
    proposal = DecisionProposal(
        category=DecisionCategory.TECH,
        topic="Jump state",
        position="Use a counter",
        rationale="Simple",
        autonomy_level=AutonomyLevel.LOCAL,
    )
    return AgentOutput(
        status=AgentOutputStatus.PARTIAL,
        result="Added DoubleJump component\n\n- Unit tests for the jump counter\n* Landing reset",
        findings=[Finding(summary="Jump count resets on landing")],
        decisions=[proposal],
        next_actions=[NextAction(description="Wire the jump button")],
        handover=embedded,
        no_context_change_reason="partial",
    )


async def test_build_handover_from_output_and_git(
    running: AgentRun, git: GitCliProvider, make_manager: ManagerFactory, fake_clock: FakeClock
) -> None:
    worktree = Path(running.worktree_path or "")
    (worktree / "Committed.cs").write_text("class C {}\n", encoding="utf-8")
    _git(worktree, "add", "Committed.cs")
    _git(worktree, "commit", "-m", "wip: committed")
    (worktree / "README.md").write_text("changed\n", encoding="utf-8")
    (worktree / "Untracked.cs").write_text("class U {}\n", encoding="utf-8")
    output = _partial_output()

    handover = await make_manager(git).build_handover(running, "FALLBACK", output)

    head = _git(worktree, "rev-parse", "HEAD")
    assert handover.id == "HO-0001"
    assert handover.reason == "FALLBACK"
    assert handover.task_summary == "Let the player double jump"
    assert handover.current_state == (
        f"IMPLEMENTING; 4 tool calls; branch feat/story-0001-player-jump-double-jump @ {head}"
    )
    assert handover.completed_work == [
        "Added DoubleJump component",
        "Unit tests for the jump counter",
        "Landing reset",
        "Jump count resets on landing",
    ]
    assert handover.modified_files == ["Committed.cs", "README.md", "Untracked.cs"]
    assert handover.findings == output.findings
    assert handover.hypotheses == ["Coyote time interferes"]
    assert handover.risks == ["Physics tuning may regress"]
    assert handover.remaining_work == ["Wire the jump button", "Tune gravity"]
    assert handover.next_action == "Wire the jump button"  # the first next action
    assert handover.decisions == []
    assert handover.proposed_decisions == output.decisions
    assert handover.worktree_head == head
    assert handover.branch == running.branch
    assert handover.from_run_id == RUN_A
    assert handover.from_model_id == "codex/gpt-5-codex"
    assert handover.role is AgentRole.SENIOR_DEV
    assert handover.created_at == fake_clock.now()


async def test_build_handover_without_embedded_handover_uses_next_actions(
    running: AgentRun, git: GitCliProvider, make_manager: ManagerFactory
) -> None:
    output = _partial_output().model_copy(
        update={
            "status": AgentOutputStatus.COMPLETED,
            "handover": None,
            "next_actions": [NextAction(description="Review"), NextAction(description="QC")],
        }
    )

    handover = await make_manager(git).build_handover(running, "REASSIGN", output)

    assert handover.remaining_work == ["Review", "QC"]
    assert handover.next_action == "Review"
    assert handover.hypotheses == []
    assert handover.risks == []


async def test_build_handover_without_output(
    running: AgentRun, git: GitCliProvider, make_manager: ManagerFactory
) -> None:
    handover = await make_manager(git).build_handover(running, "RECOVERY", None)

    assert handover.completed_work == []
    assert handover.modified_files == []
    assert handover.findings == []
    assert handover.hypotheses == []
    assert handover.risks == []
    assert handover.remaining_work == []
    assert handover.proposed_decisions == []
    assert handover.next_action == DEFAULT_NEXT
    with pytest.raises(ConfigError, match="reason"):
        await make_manager(git).build_handover(running, "BORED", None)


async def test_checkpoint_propagates_git_errors(
    make_manager: ManagerFactory, insert_run: RunFactory, db: Database
) -> None:
    fake = FakeGitProvider()
    run = await insert_run(RUN_A, worktree_path="/wt", branch="feat/x")
    fake.dirty["/wt"] = ["A.cs"]
    manager = make_manager(fake)

    first = await manager.checkpoint(run, CheckpointKind.PERIODIC, workflow_state=IMPLEMENTING)

    assert [name for name, _ in fake.calls] == ["commit_all", "head", "status"]
    assert fake.calls[0][1] == (
        "/wt",
        "wip(STORY-0001): checkpoint 1",
        STORY_ID,
        f"git.commit:{RUN_A}:1",
    )
    assert first.wip_commit_sha == fake.commits[0].sha
    fake.fail_on["commit_all"] = GitError("git commit failed", detail={"exit_code": 128})
    with pytest.raises(GitError, match="git commit failed"):
        await manager.checkpoint(run, CheckpointKind.PERIODIC, workflow_state=IMPLEMENTING)
    assert db.connect().execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0] == 1


async def test_checkpoint_needs_workflow_state_and_worktree(
    make_manager: ManagerFactory, insert_run: RunFactory
) -> None:
    fake = FakeGitProvider()
    manager = make_manager(fake)
    run = await insert_run(RUN_A, worktree_path="/wt", branch="feat/x")

    with pytest.raises(ConfigError, match="workflow_state"):
        await manager.checkpoint(run, CheckpointKind.PERIODIC)
    start = await manager.checkpoint(run, CheckpointKind.START)
    assert start.workflow_state is IMPLEMENTING  # read from the work item
    pause = await manager.checkpoint(run, CheckpointKind.PAUSE)  # E01-S26 approval pause
    assert pause.workflow_state is IMPLEMENTING
    orphan = make_run(
        "RUN-01J0000000000000000000000C", worktree_path="/c", work_item_id="STORY-0099"
    )
    with pytest.raises(ConfigError, match="unknown work item"):
        await manager.checkpoint(orphan, CheckpointKind.START)

    no_worktree = await insert_run(RUN_B)
    with pytest.raises(ConfigError, match="worktree"):
        await manager.checkpoint(no_worktree, CheckpointKind.END, workflow_state=IMPLEMENTING)
    assert fake.calls[0][0] == "commit_all"


async def test_latest_queries_and_interrupted_runs(
    make_manager: ManagerFactory, insert_run: RunFactory
) -> None:
    fake = FakeGitProvider()
    manager = make_manager(fake)
    run_a = await insert_run(RUN_A, worktree_path="/a", state=AgentRunState.RUNNING)
    run_b = await insert_run(
        RUN_B, worktree_path="/b", state=AgentRunState.PAUSED_FOR_APPROVAL, kernel_instance="other"
    )
    assert await manager.latest(RUN_A) is None

    await manager.checkpoint(run_a, CheckpointKind.PERIODIC, workflow_state=IMPLEMENTING)
    second = await manager.checkpoint(run_a, CheckpointKind.PERIODIC, workflow_state=IMPLEMENTING)
    other = await manager.checkpoint(run_b, CheckpointKind.PAUSE, workflow_state=IMPLEMENTING)

    assert await manager.latest(RUN_A) == second
    assert second.seq == 2
    assert await manager.latest_for_item(STORY_ID) == other
    interrupted = await manager.interrupted_runs("instance-a")
    assert [r.id for r in interrupted] == [RUN_B]


async def test_handover_head_matches_handoff_checkpoint(
    running: AgentRun,
    git: GitCliProvider,
    make_manager: ManagerFactory,
    memory: DefaultMemoryManager,
    handovers: HandoverRepository,
) -> None:
    worktree = Path(running.worktree_path or "")
    (worktree / "Jump.cs").write_text("class Jump {}\n", encoding="utf-8")
    manager = make_manager(git)
    handover = await manager.build_handover(running, "FALLBACK", None)
    before_commit = handover.worktree_head

    checkpoint = await manager.checkpoint(
        running, CheckpointKind.HANDOFF, handover=handover, workflow_state=IMPLEMENTING
    )

    assert checkpoint.wip_commit_sha is not None
    assert checkpoint.head_sha != before_commit
    row = await handovers.get("HO-0001")
    assert row is not None
    document = await memory.read_handover("HO-0001")
    assert document.front_matter.freshness is not None
    heads = {
        row.worktree_head,
        document.front_matter.extra["worktree_head"],
        document.front_matter.freshness.commit,
        checkpoint.head_sha,
    }
    assert heads == {checkpoint.head_sha}
    assert checkpoint.head_sha in row.current_state
    assert before_commit not in row.current_state
    assert from_document(document) == row


async def test_close_handover_updates_document(
    *,
    running: AgentRun,
    git: GitCliProvider,
    make_manager: ManagerFactory,
    memory: DefaultMemoryManager,
    handovers: HandoverRepository,
    db: Database,
) -> None:
    manager = make_manager(git)
    handover = await manager.build_handover(running, "FALLBACK", None)
    await manager.checkpoint(
        running, CheckpointKind.HANDOFF, handover=handover, workflow_state=IMPLEMENTING
    )

    closed = await manager.close_handover("HO-0001", RUN_B)

    document = await memory.read_handover("HO-0001")
    assert document.front_matter.extra["to_run_id"] == RUN_B
    assert document.front_matter.version == 2
    assert document.front_matter.updated_by.run_id == RUN_B
    kinds = _ledger_kinds(db)
    assert kinds.count("HANDOVER_CREATED") == 1
    assert kinds.count("CONTEXT_UPDATED") == 2
    row = await handovers.get("HO-0001")
    assert row == closed
    assert from_document(document) == row
