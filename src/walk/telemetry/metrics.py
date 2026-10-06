"""Retrospective metrics computed from the ledger only (§83, §115-§116).

Each `METRIC_QUERIES` entry is one read-only SELECT over ``ledger_events`` returning a single
value, scoped by the named parameters ``:phase_id`` and ``:since`` (``NULL`` = unscoped).
Payload keys are read from the event JSON with ``json_extract``.
"""

from datetime import UTC, datetime
from typing import Final

from walk.common.ids import PhaseId
from walk.persistence import Database
from walk.telemetry.models import RetrospectiveMetrics

_SCOPE = "(:phase_id IS NULL OR e.phase_id = :phase_id) AND (:since IS NULL OR e.at >= :since)"
_COMPLETED_STORY = (
    "e.kind = 'WORK_ITEM_TRANSITION' AND json_extract(e.json, '$.payload.to') = 'COMPLETE' "
    # payload.kind when the writer sets it, else the id prefix (DOMAIN-MODEL §2 encodes kind)
    "AND COALESCE(json_extract(e.json, '$.payload.kind'), "
    "substr(e.work_item_id, 1, instr(e.work_item_id, '-') - 1)) IN ('STORY', 'TASK')"
)


def _count(condition: str) -> str:
    return f"SELECT COUNT(*) FROM ledger_events e WHERE {condition} AND {_SCOPE}"  # noqa: S608 - fixed fragments


METRIC_QUERIES: Final[dict[str, str]] = {
    "stories": (
        f"SELECT COUNT(DISTINCT e.work_item_id) FROM ledger_events e "  # noqa: S608 - fixed fragments
        f"WHERE {_COMPLETED_STORY} AND {_SCOPE}"
    ),
    "first_pass_success_rate": (
        "SELECT COALESCE(CAST(SUM(first_pass) AS REAL) / COUNT(*), 0.0) FROM ("  # noqa: S608 - fixed fragments
        "SELECT CASE WHEN MAX(json_extract(e.json, '$.payload.fix_loops')) = 0 THEN 1 ELSE 0 END "
        f"AS first_pass FROM ledger_events e WHERE {_COMPLETED_STORY} AND {_SCOPE} "
        "GROUP BY e.work_item_id)"
    ),
    "reworked_stories": (
        "SELECT COUNT(DISTINCT e.work_item_id) FROM ledger_events e "  # noqa: S608 - fixed fragments
        "WHERE e.kind = 'WORK_ITEM_TRANSITION' AND json_extract(e.json, '$.payload.to') = 'REWORK' "
        f"AND {_SCOPE}"
    ),
    "qc_bugs": _count("e.kind = 'BUG_CREATED'"),
    "escaped_bugs": _count(
        "e.kind = 'BUG_CREATED' AND json_extract(e.json, '$.payload.found_in_state') = 'COMPLETE'"
    ),
    "context_stale_incidents": _count(
        "e.kind = 'CONTEXT_FRESHNESS' AND json_extract(e.json, '$.payload.status') != 'CURRENT'"
    ),
    "fallbacks": _count("e.kind = 'MODEL_FALLBACK'"),
    "failed_handoffs": _count(
        "e.kind = 'AGENT_RUN_ENDED' AND e.outcome = 'FAILED' "
        "AND json_extract(e.json, '$.payload.handover_in_id') IS NOT NULL"
    ),
    "build_failures": _count("e.kind = 'BUILD_RESULT' AND e.outcome = 'FAILED'"),
    "debate_rounds": (
        "SELECT COUNT(*) FROM (SELECT DISTINCT json_extract(e.json, '$.payload.debate_id'), "  # noqa: S608 - fixed fragments
        "json_extract(e.json, '$.payload.round') FROM ledger_events e "
        f"WHERE e.kind = 'DEBATE_POSITION' AND {_SCOPE})"
    ),
    "user_escalations": _count(
        "e.kind = 'ESCALATION_RAISED' AND json_extract(e.json, '$.payload.to_level') = 3"
    ),
    "total_cost_usd": (
        "SELECT COALESCE(SUM(e.cost_usd), 0.0) FROM ledger_events e "  # noqa: S608 - fixed fragments
        f"WHERE e.kind = 'COST_RECORDED' AND {_SCOPE}"
    ),
    "total_tokens": (
        "SELECT COALESCE(SUM(COALESCE(json_extract(e.json, '$.payload.input_tokens'), 0) "  # noqa: S608 - fixed fragments
        "+ COALESCE(json_extract(e.json, '$.payload.output_tokens'), 0)), 0) "
        f"FROM ledger_events e WHERE e.kind = 'COST_RECORDED' AND {_SCOPE}"
    ),
    # julianday() carries about 10 microseconds of float error: round to milliseconds.
    "mean_task_duration_s": (
        "SELECT COALESCE(ROUND(AVG((julianday(e.at) - julianday(s.at)) * 86400.0), 3), 0.0) "  # noqa: S608 - fixed fragments
        "FROM ledger_events e JOIN ledger_events s "
        "ON s.run_id = e.run_id AND s.kind = 'AGENT_RUN_STARTED' "
        f"WHERE e.kind = 'AGENT_RUN_ENDED' AND e.run_id IS NOT NULL AND {_SCOPE}"
    ),
}
"""One read-only SQL statement per `RetrospectiveMetrics` field (E01-S06 definitions)."""


async def compute_metrics(
    db: Database, *, phase_id: PhaseId | None = None, since: datetime | None = None
) -> RetrospectiveMetrics:
    """Evaluate every `METRIC_QUERIES` statement; empty ledgers give zeros.

    Args:
        db: Database holding ``ledger_events``.
        phase_id: Count only events of this phase.
        since: Count only events at or after this time.
    """
    params = {
        "phase_id": phase_id,
        # Same fixed-width UTC text as the ledger_events.at column.
        "since": None
        if since is None
        else since.astimezone(UTC).isoformat(timespec="microseconds"),
    }
    conn = db.connect()
    values = {
        field: conn.execute(sql, params).fetchone()[0] or 0 for field, sql in METRIC_QUERIES.items()
    }
    return RetrospectiveMetrics.model_validate(values)
