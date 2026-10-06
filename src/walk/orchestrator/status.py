"""`StatusBuilder`: the §87 `KernelStatus` snapshot from the database and the ledger (E01-S29)."""

from collections import Counter
from collections.abc import Awaitable, Callable
from typing import Final

from walk.budgets.models import BudgetSubject
from walk.budgets.protocols import BudgetManager
from walk.common.errors import ConfigError
from walk.common.ids import ModelId, ProjectKey
from walk.model_router.models import UsageReport
from walk.orchestrator.models import KernelStatus
from walk.permissions.models import ApprovalRequest
from walk.runtime.models import AgentRunState
from walk.runtime.repository import AgentRunRepository
from walk.telemetry.models import LedgerEvent, LedgerEventKind
from walk.telemetry.protocols import LedgerManager
from walk.workflow.models import WorkItemState
from walk.workflow.protocols import WorkflowManager
from walk.workflow.repository import PhaseRepository, ProjectRepository

_ACTIVE_RUN_STATES: Final = [
    AgentRunState.RUNNING,
    AgentRunState.PAUSED_FOR_APPROVAL,
    AgentRunState.PAUSED_BY_USER,
]
# The ledger query is bounded; a status snapshot reads every COST_RECORDED event of a project.
_COST_EVENTS_LIMIT: Final = 1_000_000
_TOKEN_KEYS: Final = ("input_tokens", "output_tokens", "cache_read_tokens")
_COST_DECIMALS: Final = 6

PendingApprovals = Callable[[], Awaitable[list[ApprovalRequest]]]


class StatusBuilder:
    """Builds `KernelStatus`; read-only, so the CLI can run it on a read-only connection."""

    def __init__(  # noqa: PLR0917 - parameters fixed by the E01-S29 contract
        self,
        projects: ProjectRepository,
        workflow: WorkflowManager,
        phases: PhaseRepository,
        runs: AgentRunRepository,
        budgets: BudgetManager,
        ledger: LedgerManager,
        *,
        project_key: ProjectKey,
        pending_approvals: PendingApprovals | None = None,
    ) -> None:
        """Wire the builder.

        Args:
            projects: Pause flag and current phase.
            workflow: Work items per state.
            phases: The current phase.
            runs: Active runs.
            budgets: Budgets applicable to the project.
            ledger: ``COST_RECORDED`` events for the per-model usage.
            project_key: Project of the kernel.
            pending_approvals: Pending approval requests (wired by E02-S11); none when absent.
        """
        self._projects = projects
        self._workflow = workflow
        self._phases = phases
        self._runs = runs
        self._budgets = budgets
        self._ledger = ledger
        self._project_key = project_key
        self._pending_approvals = pending_approvals

    async def build(self) -> KernelStatus:
        """The current snapshot.

        Raises:
            ConfigError: The project row is missing.
        """
        project = await self._projects.get(self._project_key)
        if project is None:
            msg = f"project {self._project_key} not found"
            raise ConfigError(msg, detail={"project_key": self._project_key})
        phase_id = project.current_phase_id
        phase = await self._phases.get(phase_id) if phase_id is not None else None
        items = await self._workflow.query(phase_id=phase_id)
        progress = Counter(item.state for item in items)
        blocked = await self._workflow.query(states=[WorkItemState.BLOCKED])
        approvals = await self._pending_approvals() if self._pending_approvals is not None else []
        costs = await self._ledger.query(
            kinds=[LedgerEventKind.COST_RECORDED], limit=_COST_EVENTS_LIMIT
        )
        return KernelStatus(
            project_key=project.key,
            paused=project.paused,
            current_phase=phase,
            phase_progress=dict(progress),
            gdd_coverage={},
            active_runs=await self._runs.by_state(_ACTIVE_RUN_STATES),
            blocked_items=[item.id for item in blocked],
            pending_approvals=approvals,
            open_debates=[],
            model_usage=_usage_by_model(costs),
            qc_status={},
            build_status=None,
            budgets=await self._budgets.applicable(BudgetSubject(project_key=project.key)),
            open_improvement_candidates=0,
        )


def _usage_by_model(events: list[LedgerEvent]) -> dict[ModelId, UsageReport]:
    totals: dict[ModelId, dict[str, float]] = {}
    for event in events:
        if event.model_id is None:
            continue
        total = totals.setdefault(event.model_id, dict.fromkeys((*_TOKEN_KEYS, "cost_usd"), 0.0))
        for key in _TOKEN_KEYS:
            total[key] += _number(event.payload.get(key))
        total["cost_usd"] += event.cost_usd or 0.0
    return {
        model_id: UsageReport(
            input_tokens=int(total["input_tokens"]),
            output_tokens=int(total["output_tokens"]),
            cache_read_tokens=int(total["cache_read_tokens"]),
            cost_usd=round(total["cost_usd"], _COST_DECIMALS),
            turns=0,
            tool_calls=0,
            duration_s=0.0,
        )
        for model_id, total in totals.items()
    }


def _number(value: object) -> float:
    return float(value) if isinstance(value, int | float) else 0.0
