"""Default effort resolution and §19 dynamic effort changes (INTERFACES §5.2)."""

import logging
from collections.abc import Awaitable, Callable

from walk.budgets.models import BudgetDimension
from walk.common.clock import Clock
from walk.common.enums import Effort
from walk.common.errors import ConfigError
from walk.common.ids import ProjectKey, RunId
from walk.common.roles import AgentRole
from walk.effort.models import (
    EFFORT_ORDER,
    STATIC_COST_USD,
    EffortPolicy,
    EffortRequest,
    EffortResolution,
)
from walk.effort.protocols import CostEstimator
from walk.hooks.models import HookContext, HookName
from walk.hooks.protocols import HookManager
from walk.telemetry.models import LedgerEvent, LedgerEventKind
from walk.telemetry.protocols import LedgerManager
from walk.workflow.models import StoryContract, WorkItem, WorkItemState

logger = logging.getLogger(__name__)

# Role used for cost estimates when the caller cannot name one (no owner on the item, or a
# dynamic request that only carries a run id). The static estimator ignores the role.
_UNKNOWN_ROLE = AgentRole.KERNEL


class StaticCostEstimator:
    """`CostEstimator` over `STATIC_COST_USD`; the role is ignored (ADR-0011 D-5 seed)."""

    def estimate(self, role: AgentRole, effort: Effort) -> float:  # noqa: ARG002 - protocol signature; role-specific means arrive in E09-S03
        """Return the static USD estimate of one run at ``effort``."""
        return STATIC_COST_USD[effort]


class DefaultEffortManager:
    """`EffortManager`: pure resolution plus approved, budget-checked change requests."""

    def __init__(
        self,
        estimator: CostEstimator,
        ledger: LedgerManager,
        hooks: HookManager,
        clock: Clock,
        request_approval: Callable[[RunId, EffortRequest], Awaitable[bool]],
        *,
        project_key: ProjectKey,
    ) -> None:
        """Wire the manager.

        Args:
            estimator: Cost of one run per role and effort (resolution step 7, request check c).
            ledger: Write point for ``EFFORT_CHANGED``.
            hooks: Fires ``ON_EFFORT_CHANGE``.
            clock: Stamps the ledger event and hook context.
            request_approval: Asks for an upgrade when the policy disables auto-approval;
                resolves to True when approved.
            project_key: Project of this kernel database; ledger events and hook contexts
                require it and ``request_change`` only receives a run id.
        """
        self._estimator = estimator
        self._ledger = ledger
        self._hooks = hooks
        self._clock = clock
        self._request_approval = request_approval
        self._project_key = project_key

    def resolve(
        self,
        policy: EffortPolicy,
        item: WorkItem,
        state: WorkItemState,
        escalation_bump: int,
        budget_headroom: dict[BudgetDimension, float],
    ) -> EffortResolution:
        """Resolve the effective effort of the next run of ``item`` (INTERFACES §5.2, pure).

        Items without a contract (EPIC/FEATURE) start from ``policy.default``. A missing
        ``COST_USD`` headroom means unlimited.

        Raises:
            ConfigError: If the policy does not map the item's complexity or its risk.
        """
        contract: StoryContract | None = getattr(item, "contract", None)
        if contract is None:
            base = policy.default
        elif contract.complexity in policy.complexity_map:
            base = policy.complexity_map[contract.complexity]
        else:
            msg = f"effort policy has no complexity mapping for {contract.complexity}"
            raise ConfigError(msg, detail={"work_item_id": item.id})
        if item.risk not in policy.risk_bump:
            msg = f"effort policy has no risk bump for {item.risk.value}"
            raise ConfigError(msg, detail={"work_item_id": item.id})
        risk_bump = policy.risk_bump[item.risk]
        stage_bump = policy.stage_bump.get(state, 0)
        idx = max(EFFORT_ORDER.index(base), EFFORT_ORDER.index(policy.default))
        idx += risk_bump + stage_bump + escalation_bump
        clamped = min(max(idx, EFFORT_ORDER.index(policy.min)), EFFORT_ORDER.index(policy.max))
        clamped_by_policy = clamped != idx
        idx = clamped
        clamped_by_budget = False
        limit = budget_headroom.get(BudgetDimension.COST_USD)
        if limit is not None:
            role = item.owner_role or (contract.owner_role if contract else None) or _UNKNOWN_ROLE
            while idx > 0 and self._estimator.estimate(role, EFFORT_ORDER[idx]) > limit:
                idx -= 1
                clamped_by_budget = True
        return EffortResolution(
            role_default=policy.default,
            complexity_component=base,
            risk_bump=risk_bump,
            stage_bump=stage_bump,
            escalation_bump=escalation_bump,
            effective=EFFORT_ORDER[idx],
            clamped_by_policy=clamped_by_policy,
            clamped_by_budget=clamped_by_budget,
        )

    async def request_change(
        self,
        run_id: RunId,
        current: Effort,
        request: EffortRequest,
        policy: EffortPolicy,
        headroom: dict[BudgetDimension, float],
    ) -> Effort:
        """Decide a §19 change; returns the effort for the next run of the work item.

        Denied (``current`` returned, nothing fired or written) when the target is outside
        ``[policy.min, policy.max]``, does not move in ``request.direction``, is an upgrade the
        approval callback refuses (only asked when auto-approval is off), or is an upgrade
        whose extra estimated cost exceeds the ``COST_USD`` headroom (absent = unlimited).
        Downgrades need neither approval nor budget. An accepted change writes
        ``EFFORT_CHANGED`` and then fires ``ON_EFFORT_CHANGE``.
        """
        target = EFFORT_ORDER.index(request.target)
        now = EFFORT_ORDER.index(current)
        upgrade = request.direction == "UPGRADE"
        if not EFFORT_ORDER.index(policy.min) <= target <= EFFORT_ORDER.index(policy.max):
            return self._deny(run_id, current, request, "outside_policy")
        if (target > now) is not upgrade or target == now:
            return self._deny(run_id, current, request, "direction_mismatch")
        if upgrade:
            if not policy.auto_approve_upgrade_within_budget and not await self._request_approval(
                run_id, request
            ):
                return self._deny(run_id, current, request, "approval_denied")
            limit = headroom.get(BudgetDimension.COST_USD)
            cost_after = self._estimator.estimate(_UNKNOWN_ROLE, request.target)
            cost_before = self._estimator.estimate(_UNKNOWN_ROLE, current)
            if limit is not None and cost_after - cost_before > limit:
                return self._deny(run_id, current, request, "budget")
        await self._record_change(run_id, current, request)
        return request.target

    def _deny(self, run_id: RunId, current: Effort, request: EffortRequest, reason: str) -> Effort:
        logger.info(
            "effort change denied",
            extra={
                "run_id": run_id,
                "from": current.value,
                "to": request.target.value,
                "direction": request.direction,
                "deny_reason": reason,
            },
        )
        return current

    async def _record_change(self, run_id: RunId, current: Effort, request: EffortRequest) -> None:
        at = self._clock.now()
        payload = {
            "from": current.value,
            "to": request.target.value,
            "direction": request.direction,
            "reason": request.reason,
        }
        event = LedgerEvent(
            kind=LedgerEventKind.EFFORT_CHANGED,
            at=at,
            project_key=self._project_key,
            actor_role=AgentRole.KERNEL,
            run_id=run_id,
            effort=request.target,
            outcome="OK",
            payload=payload,
        )
        await self._ledger.append(event)
        context = HookContext(
            name=HookName.ON_EFFORT_CHANGE,
            at=at,
            project_key=self._project_key,
            run_id=run_id,
            payload=payload,
        )
        await self._hooks.fire(HookName.ON_EFFORT_CHANGE, context)
