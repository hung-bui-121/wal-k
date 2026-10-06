import sqlite3
from datetime import timedelta

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.runtime.conftest import AT, RUN_A, RUN_B, STORY_ID, RunFactory
from walk.agents import Handover
from walk.common.enums import Effort
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.context import ContextBundleRef
from walk.model_router import ProviderSessionRef
from walk.persistence import Database, UnitOfWork
from walk.runtime import (
    AgentRunRepository,
    AgentRunState,
    Checkpoint,
    CheckpointKind,
    CheckpointRepository,
    HandoverRepository,
    RunNotFound,
)
from walk.workflow import WorkItemState

RUN_C = "RUN-01J0000000000000000000000C"


def _checkpoint(run_id: str, seq: int, *, at_offset_s: int = 0) -> Checkpoint:
    return Checkpoint(
        id=f"CKP-01J0000000000000000000{seq:02d}{run_id[-2:]}",
        run_id=run_id,
        work_item_id=STORY_ID,
        seq=seq,
        kind=CheckpointKind.PERIODIC,
        at=AT + timedelta(seconds=at_offset_s),
        role=AgentRole.SENIOR_DEV,
        model_id="codex/gpt-5-codex",
        effort=Effort.MEDIUM,
        workflow_state=WorkItemState.IMPLEMENTING,
        head_sha="3f9c2e1",
        wip_commit_sha=None,
        dirty_files=[],
        tool_calls_so_far=seq,
        budget_consumed={},
        provider_session=None,
        handover_id=None,
        context_manifest=ContextBundleRef(item_ids=[], total_tokens_estimate=0),
    )


def _handover(handover_id: str, run_id: str, *, to_run_id: str | None = None) -> Handover:
    return Handover(
        id=handover_id,
        work_item_id=STORY_ID,
        role=AgentRole.SENIOR_DEV,
        from_run_id=run_id,
        from_model_id="codex/gpt-5-codex",
        to_run_id=to_run_id,
        reason="FALLBACK",
        task_summary="t",
        current_state="s",
        completed_work=[],
        modified_files=[],
        findings=[],
        hypotheses=[],
        decisions=[],
        proposed_decisions=[],
        risks=[],
        remaining_work=[],
        next_action="n",
        worktree_head="3f9c2e1",
        branch="feat/story-0001",
        created_at=AT,
    )


async def test_run_repository_state_updates(
    db: Database, runs: AgentRunRepository, insert_run: RunFactory, fake_clock: FakeClock
) -> None:
    await insert_run(RUN_A, state=AgentRunState.RUNNING)
    fake_clock.advance(30)

    done = await runs.set_state(RUN_A, AgentRunState.COMPLETED)

    assert done.state is AgentRunState.COMPLETED
    assert done.ended_at == fake_clock.now()
    assert [r.id for r in await runs.by_state([AgentRunState.COMPLETED])] == [RUN_A]
    stored = await runs.get(RUN_A)
    assert stored == done
    row = db.connect().execute("SELECT state, ended_at FROM agent_runs").fetchone()
    assert row["state"] == "COMPLETED"
    assert row["ended_at"] == fake_clock.now().isoformat()
    with pytest.raises(RunNotFound):
        await runs.set_state("RUN-01J99999999999999999999999", AgentRunState.FAILED)


async def test_set_state_on_caller_connection_and_failure_reason(
    db: Database, runs: AgentRunRepository, insert_run: RunFactory
) -> None:
    await insert_run(RUN_A, state=AgentRunState.RUNNING)

    async def fail_inside_transaction() -> None:
        async with UnitOfWork(db) as uow:
            await runs.set_state(RUN_A, AgentRunState.FAILED, failure_reason="boom", conn=uow.conn)
            raise RuntimeError

    with pytest.raises(RuntimeError):
        await fail_inside_transaction()
    assert (await runs.get(RUN_A)).state is AgentRunState.RUNNING  # type: ignore[union-attr]  # inserted above

    paused = await runs.set_state(RUN_A, AgentRunState.PAUSED_FOR_APPROVAL)
    assert paused.ended_at is None
    failed = await runs.set_state(RUN_A, AgentRunState.FAILED, failure_reason="boom")
    assert failed.failure_reason == "boom"
    assert failed.ended_at is not None


async def test_by_state_excludes_current_instance(
    runs: AgentRunRepository, insert_run: RunFactory
) -> None:
    await insert_run(RUN_A, state=AgentRunState.RUNNING, kernel_instance="A")
    await insert_run(RUN_B, state=AgentRunState.RUNNING, kernel_instance="B")
    await insert_run(RUN_C, state=AgentRunState.COMPLETED, kernel_instance="A")

    found = await runs.by_state([AgentRunState.RUNNING], kernel_instance_not="B")

    assert [r.id for r in found] == [RUN_A]
    both = await runs.by_state([AgentRunState.RUNNING, AgentRunState.COMPLETED])
    assert {r.id for r in both} == {RUN_A, RUN_B, RUN_C}
    assert await runs.by_state([]) == []
    assert [r.id for r in await runs.for_item(STORY_ID)] == [RUN_A, RUN_B, RUN_C]


async def test_run_projection_columns(db: Database, insert_run: RunFactory) -> None:
    ref = ProviderSessionRef(provider="codex", session_id="thr_1", resumable=True)
    await insert_run(RUN_A, provider_session=ref, parent_run_id=RUN_B)
    row = db.connect().execute("SELECT * FROM agent_runs").fetchone()
    assert row["provider_session_id"] == "thr_1"
    assert row["parent_run_id"] == RUN_B
    assert row["purpose"] == "IMPLEMENT"
    assert row["kernel_instance"] == "instance-a"
    assert row["started_at"] == AT.isoformat()


async def test_checkpoints_immutable_and_sequenced(
    db: Database, checkpoints: CheckpointRepository, insert_run: RunFactory
) -> None:
    await insert_run(RUN_A)
    await insert_run(RUN_B)
    assert await checkpoints.next_seq(RUN_A) == 1
    assert await checkpoints.latest(RUN_A) is None
    assert await checkpoints.latest_for_item(STORY_ID) is None

    async with UnitOfWork(db) as uow:
        await checkpoints.insert(_checkpoint(RUN_A, 1), uow.conn)
        await checkpoints.insert(_checkpoint(RUN_A, 2, at_offset_s=1), uow.conn)
        await checkpoints.insert(_checkpoint(RUN_B, 1, at_offset_s=2), uow.conn)

    assert await checkpoints.next_seq(RUN_A) == 3
    latest = await checkpoints.latest(RUN_A)
    assert latest is not None
    assert latest.seq == 2
    newest = await checkpoints.latest_for_item(STORY_ID)
    assert newest is not None
    assert newest.run_id == RUN_B
    with pytest.raises(sqlite3.IntegrityError):
        db.connect().execute("UPDATE checkpoints SET kind = 'END'")
    db.connect().rollback()
    with pytest.raises(sqlite3.IntegrityError):
        async with UnitOfWork(db) as uow:
            await checkpoints.insert(
                _checkpoint(RUN_A, 2).model_copy(update={"id": "CKP-01J0000000000000000000XXXX"}),
                uow.conn,
            )
    assert not hasattr(checkpoints, "update")
    assert not hasattr(checkpoints, "delete")


async def test_handover_latest_open_and_close(
    db: Database, handovers: HandoverRepository, insert_run: RunFactory
) -> None:
    await insert_run(RUN_A)
    async with UnitOfWork(db) as uow:
        await handovers.insert(_handover("HO-0001", RUN_A, to_run_id=RUN_B), uow)
        await handovers.insert(_handover("HO-0002", RUN_A), uow)

    open_one = await handovers.latest_open(STORY_ID)
    assert open_one is not None
    assert open_one.id == "HO-0002"

    closed = await handovers.close("HO-0002", RUN_C)

    assert closed.to_run_id == RUN_C
    assert await handovers.latest_open(STORY_ID) is None
    row = (
        db.connect()
        .execute("SELECT to_run_id, ai_path FROM handovers WHERE id='HO-0002'")
        .fetchone()
    )
    assert row["to_run_id"] == RUN_C
    assert row["ai_path"] == "handovers/HO-0002.md"
    with pytest.raises(ConfigError, match="unknown handover"):
        await handovers.close("HO-0099", RUN_C)
