from pathlib import Path

import pytest

from tests.runtime.conftest import make_run
from tests.runtime.executor_env import (
    CODEX_MODEL,
    EnvFactory,
    ExecutorEnv,
    completed_output,
    script,
)
from walk.agents import AgentOutputStatus
from walk.common.errors import ConfigError, GuardRejected
from walk.memory import ContextUpdate
from walk.persistence import UnitOfWork
from walk.runtime import IMPLEMENT_OUTPUT_EVENTS, AgentRun, AgentRunState, branch_name_for
from walk.telemetry import EvidenceDraft, EvidenceKind, LedgerEventKind
from walk.workflow import (
    Feature,
    StoryContract,
    WorkItem,
    WorkItemDraft,
    WorkItemKind,
    WorkItemState,
)

RUN_ID = "RUN-01J0000000000000000000000A"
RESULTS = "TestResults/results.xml"
NOTE = ContextUpdate(
    doc_id="FEAT-0001",
    section="Implementation Notes",
    operation="APPEND",
    content_markdown="Double jump uses a coyote-time window.",
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


async def _run_in_worktree(
    env: ExecutorEnv, item: WorkItem, *, purpose: str = "IMPLEMENT", run_id: str = RUN_ID
) -> tuple[AgentRun, str]:
    run = make_run(
        run_id,
        work_item_id=item.id,
        purpose=purpose,
        model_id=CODEX_MODEL,
        provider="fake-codex",
        state=AgentRunState.RUNNING,
    )
    async with UnitOfWork(env.db) as uow:
        await env.runs.insert(run, uow)
    worktree = await env.sandbox.create(run, item)
    run = run.model_copy(update={"worktree_path": worktree, "branch": branch_name_for(item)})
    return run, await env.git.head(worktree)


async def _commit_change(env: ExecutorEnv, run: AgentRun) -> None:
    assert run.worktree_path is not None
    _write(Path(run.worktree_path) / "src" / "Jump.cs", "// jump\n")
    await env.git.commit_all(
        run.worktree_path,
        "wip(STORY-0001): checkpoint 1",
        trailer_work_item=run.work_item_id,
        idempotency_key=f"git.commit:{run.id}:1",
    )


async def _require_evidence(env: ExecutorEnv) -> None:
    contract = StoryContract(
        goal="Let the player double jump", required_evidence=[EvidenceKind.AUTOMATED_TEST]
    )
    async with UnitOfWork(env.db) as uow:
        await env.items.upsert(env.story.model_copy(update={"contract": contract}), uow)


async def _state(env: ExecutorEnv, item_id: str) -> WorkItemState:
    item = await env.items.get(item_id)
    assert item is not None
    return item.state


async def test_apply_completed_implement_submits_for_review(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env()
    await _require_evidence(env)
    run, start_head = await _run_in_worktree(env, env.story)
    await _commit_change(env, run)
    assert run.worktree_path is not None
    _write(Path(run.worktree_path) / RESULTS, "<testsuite tests='3'/>\n")
    output = completed_output(
        context_updates=[NOTE],
        no_context_change_reason=None,
        evidence=[
            EvidenceDraft(
                kind=EvidenceKind.AUTOMATED_TEST, path_or_uri=RESULTS, description="EditMode"
            )
        ],
    )

    effects = await env.applier.apply(run, output, start_head=start_head)

    assert effects.memory_docs == ["FEAT-0001"]
    document = await env.memory.read("FEAT-0001")
    assert "coyote-time" in document.sections["Implementation Notes"]
    assert effects.evidence_ids == ["EVD-000001"]
    assert effects.workflow_event == "submit_for_review"
    assert effects.commit_sha == await env.git.head(run.worktree_path)
    assert effects.commit_sha != start_head
    assert effects.decision_ids == []
    assert effects.created_work_items == []
    assert effects.escalation_ids == []
    assert await _state(env, env.story.id) is WorkItemState.READY_FOR_REVIEW
    transition = (await env.items.transitions(env.story.id, limit=1))[0]
    assert transition.event == "submit_for_review"
    assert transition.run_id == RUN_ID
    assert IMPLEMENT_OUTPUT_EVENTS[AgentOutputStatus.COMPLETED] == "submit_for_review"


async def test_missing_evidence_file_skipped(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env()
    run, start_head = await _run_in_worktree(env, env.story)
    await _commit_change(env, run)
    output = completed_output(
        context_updates=[NOTE],
        no_context_change_reason=None,
        evidence=[
            EvidenceDraft(kind=EvidenceKind.LOG, path_or_uri="logs/missing.log", description="x"),
            EvidenceDraft(
                kind=EvidenceKind.BUILD_ARTIFACT,
                path_or_uri="https://ci.example.invalid/builds/7",
                description="CI build",
            ),
        ],
    )

    effects = await env.applier.apply(run, output, start_head=start_head)

    assert effects.evidence_ids == ["EVD-000001"]
    recorded = await env.evidence.for_item(env.story.id)
    assert [e.uri for e in recorded] == ["https://ci.example.invalid/builds/7"]
    assert effects.memory_docs == ["FEAT-0001"]
    assert effects.workflow_event == "submit_for_review"
    assert await _state(env, env.story.id) is WorkItemState.READY_FOR_REVIEW


async def test_guard_rejection_fails_run(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(script(tool_calls=0))
    run, start_head = await _run_in_worktree(env, env.story)

    with pytest.raises(GuardRejected):
        await env.applier.apply(run, completed_output(), start_head=start_head)
    await env.sandbox.remove(run, keep_branch=True)
    async with UnitOfWork(env.db) as uow:
        await env.runs.set_state(run.id, AgentRunState.COMPLETED, conn=uow.conn)

    failed = await env.run_to_end()

    assert failed.state is AgentRunState.FAILED
    assert str(failed.failure_reason).startswith("guard_rejected: ")
    assert "has_commit" in str(failed.failure_reason)
    error = (await env.events(failed.id, LedgerEventKind.ERROR))[0]
    assert error.payload["kind"] == "GUARD_REJECTED"
    assert await _state(env, env.story.id) is WorkItemState.IMPLEMENTING


async def test_non_implement_runs_raise_no_event(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env()
    task = WorkItemDraft(kind=WorkItemKind.TASK, title="Tune jump", description="d")
    review_output = completed_output(status=AgentOutputStatus.APPROVED, new_tasks=[task])
    review, review_head = await _run_in_worktree(env, env.story, purpose="REVIEW")
    review = review.model_copy(update={"output": review_output})

    reviewed = await env.applier.apply(review, review_output, start_head=review_head)

    assert reviewed.workflow_event is None
    assert reviewed.created_work_items == []
    assert review.output is not None
    assert review.output.new_tasks == [task]
    assert await _state(env, env.story.id) is WorkItemState.IMPLEMENTING
    await env.sandbox.remove(review, keep_branch=True)

    feature = Feature(id="FEAT-0002", project_key="DEMO", title="Movement")
    async with UnitOfWork(env.db) as uow:
        await env.items.insert(feature, uow)
    implement, implement_head = await _run_in_worktree(
        env, feature, run_id="RUN-01J0000000000000000000000B"
    )

    applied = await env.applier.apply(implement, completed_output(), start_head=implement_head)

    assert applied.workflow_event is None
    assert applied.commit_sha is None
    assert await _state(env, "FEAT-0002") is WorkItemState.IDEA


async def test_apply_requires_worktree_and_branch(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env()

    with pytest.raises(ConfigError, match="no worktree or branch"):
        await env.applier.apply(make_run(RUN_ID), completed_output(), start_head="a" * 40)
