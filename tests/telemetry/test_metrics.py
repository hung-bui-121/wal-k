from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from walk.common.roles import AgentRole
from walk.persistence import Database
from walk.telemetry import (
    METRIC_QUERIES,
    DefaultLedgerManager,
    DefaultTelemetryManager,
    LedgerEvent,
    LedgerEventKind,
    LedgerRepository,
    RetrospectiveMetrics,
    compute_metrics,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)
RUN_A = "RUN-" + "A" * 26
RUN_B = "RUN-" + "B" * 26
K = LedgerEventKind


@pytest.fixture
def ledger(db: Database, fake_clock: FakeClock) -> DefaultLedgerManager:
    return DefaultLedgerManager(db, LedgerRepository(db), SequentialIdFactory(), fake_clock)


async def _add(
    ledger: DefaultLedgerManager,
    event_kind: LedgerEventKind,
    /,
    *,
    at: datetime = T0,
    item: str | None = None,
    phase: str | None = "PHASE-01",
    run: str | None = None,
    outcome: str | None = None,
    cost: float | None = None,
    **payload: object,
) -> None:
    await ledger.append(
        LedgerEvent.model_validate(
            {
                "kind": event_kind,
                "at": at,
                "project_key": "DEMO",
                "actor_role": AgentRole.KERNEL,
                "work_item_id": item,
                "phase_id": phase,
                "run_id": run,
                "outcome": outcome,
                "cost_usd": cost,
                "payload": payload,
            }
        )
    )


async def _seed(ledger: DefaultLedgerManager) -> None:
    # Two stories complete: one first-pass, one after a fix loop (via REWORK).
    await _add(ledger, K.WORK_ITEM_TRANSITION, item="STORY-0001", to="COMPLETE", fix_loops=0)
    await _add(ledger, K.WORK_ITEM_TRANSITION, item="STORY-0002", to="REWORK")
    await _add(
        ledger, K.WORK_ITEM_TRANSITION, item="STORY-0002", to="COMPLETE", kind="STORY", fix_loops=1
    )
    # A feature completing is not a story.
    await _add(ledger, K.WORK_ITEM_TRANSITION, item="FEAT-0001", to="COMPLETE", fix_loops=0)
    await _add(ledger, K.MODEL_FALLBACK, item="STORY-0002", run=RUN_A)
    await _add(ledger, K.COST_RECORDED, cost=0.25, input_tokens=1000, output_tokens=200)
    await _add(ledger, K.COST_RECORDED, cost=0.5, input_tokens=10)
    await _add(ledger, K.BUG_CREATED, item="BUG-0001", found_in_state="COMPLETE")
    await _add(ledger, K.BUG_CREATED, item="BUG-0002", found_in_state="QC")
    await _add(ledger, K.CONTEXT_FRESHNESS, status="STALE")
    await _add(ledger, K.CONTEXT_FRESHNESS, status="CURRENT")
    await _add(ledger, K.AGENT_RUN_STARTED, run=RUN_A, at=T0)
    await _add(ledger, K.AGENT_RUN_ENDED, run=RUN_A, at=T0 + timedelta(seconds=30), outcome="OK")
    await _add(ledger, K.AGENT_RUN_STARTED, run=RUN_B, at=T0)
    await _add(
        ledger,
        K.AGENT_RUN_ENDED,
        run=RUN_B,
        at=T0 + timedelta(seconds=90),
        outcome="FAILED",
        handover_in_id="HO-0001",
    )
    await _add(ledger, K.BUILD_RESULT, outcome="FAILED")
    await _add(ledger, K.BUILD_RESULT, outcome="OK")
    await _add(ledger, K.DEBATE_POSITION, debate_id="DEB-0001", round=1)
    await _add(ledger, K.DEBATE_POSITION, debate_id="DEB-0001", round=1)
    await _add(ledger, K.DEBATE_POSITION, debate_id="DEB-0001", round=2)
    await _add(ledger, K.ESCALATION_RAISED, to_level=3)
    await _add(ledger, K.ESCALATION_RAISED, to_level=2)


def test_metric_queries_cover_every_field() -> None:
    assert set(METRIC_QUERIES) == set(RetrospectiveMetrics.model_fields)


async def test_metrics_zero_on_empty_ledger(
    db: Database, fake_clock: FakeClock, tmp_path: Path
) -> None:
    telemetry = DefaultTelemetryManager(tmp_path, LedgerRepository(db), fake_clock)
    try:
        metrics = await telemetry.metrics()
    finally:
        telemetry.close()
    assert all(value == 0 for value in metrics.model_dump().values())
    assert isinstance(metrics.first_pass_success_rate, float)
    assert isinstance(metrics.total_cost_usd, float)


async def test_metrics_computed_from_seeded_ledger(
    db: Database, ledger: DefaultLedgerManager
) -> None:
    await _seed(ledger)
    metrics = await compute_metrics(db)
    assert metrics == RetrospectiveMetrics(
        stories=2,
        first_pass_success_rate=0.5,
        reworked_stories=1,
        qc_bugs=2,
        escaped_bugs=1,
        context_stale_incidents=1,
        fallbacks=1,
        failed_handoffs=1,
        build_failures=1,
        debate_rounds=2,
        user_escalations=1,
        total_cost_usd=0.75,
        total_tokens=1210,
        mean_task_duration_s=60.0,
    )


async def test_metrics_scoped_by_phase(db: Database, ledger: DefaultLedgerManager) -> None:
    await _seed(ledger)
    await _add(ledger, K.MODEL_FALLBACK, phase="PHASE-02")
    await _add(ledger, K.WORK_ITEM_TRANSITION, phase="PHASE-02", item="TASK-0001", to="COMPLETE")
    other = await compute_metrics(db, phase_id="PHASE-02")
    assert (other.fallbacks, other.stories, other.first_pass_success_rate) == (1, 1, 0.0)
    assert other.qc_bugs == 0
    first = await compute_metrics(db, phase_id="PHASE-01")
    assert (first.fallbacks, first.stories) == (1, 2)


async def test_metrics_scoped_by_since(
    db: Database, ledger: DefaultLedgerManager, fake_clock: FakeClock, tmp_path: Path
) -> None:
    await _seed(ledger)
    await _add(ledger, K.MODEL_FALLBACK, at=T0 + timedelta(days=1))
    telemetry = DefaultTelemetryManager(tmp_path, LedgerRepository(db), fake_clock)
    try:
        later = await telemetry.metrics(since=T0 + timedelta(hours=1))
    finally:
        telemetry.close()
    assert later.fallbacks == 1
    assert later.stories == 0
