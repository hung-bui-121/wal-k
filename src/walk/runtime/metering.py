"""Token usage of a run → cost records (§84; ADR-0004 D-9, E01-S27 rule 16)."""

from collections.abc import Callable

from walk.budgets.models import BudgetSubject, CostRecord
from walk.budgets.protocols import CostManager
from walk.common.clock import Clock
from walk.common.errors import ConfigError
from walk.model_router.costing import usage_to_cost_record
from walk.model_router.models import ModelDescriptor, UsageReport

_COST_DECIMALS = 6
_ZERO = UsageReport(
    input_tokens=0, output_tokens=0, cost_usd=0.0, turns=0, tool_calls=0, duration_s=0.0
)


class UsageMeter:
    """Meters the growth of a run's cumulative usage, once per token.

    Adapters report cumulative usage (`ModelAdapter.usage`); `observe` records only what is new
    since the previous observation, so per-call and cumulative ``USAGE`` events meter the same
    tokens exactly once.
    """

    def __init__(
        self,
        costs: CostManager,
        descriptor: ModelDescriptor,
        subject: BudgetSubject,
        clock: Clock,
        *,
        new_id: Callable[[], str],
    ) -> None:
        """Wire the meter.

        Args:
            costs: Records each delta (``COST_RECORDED`` and ``COST_USD``/``TOKENS`` metering).
            descriptor: Model of the run; its prices convert tokens to USD.
            subject: Budget subject the cost is charged to.
            clock: Stamps the records.
            new_id: Mints cost record ids.
        """
        self._costs = costs
        self._descriptor = descriptor
        self._subject = subject
        self._clock = clock
        self._new_id = new_id
        self._last = _ZERO
        self._cost_usd = 0.0

    async def observe(self, cumulative: UsageReport) -> CostRecord | None:
        """Record the token delta since the last observation; None when nothing is new.

        Raises:
            ConfigError: A token count is lower than in the previous report (adapter defect).
        """
        delta = {
            "input_tokens": cumulative.input_tokens - self._last.input_tokens,
            "output_tokens": cumulative.output_tokens - self._last.output_tokens,
            "cache_read_tokens": cumulative.cache_read_tokens - self._last.cache_read_tokens,
        }
        decreased = {name: value for name, value in delta.items() if value < 0}
        if decreased:
            msg = "cumulative usage decreased"
            raise ConfigError(msg, detail={"decreased": decreased, "run_id": self._subject.run_id})
        self._last = cumulative
        if not any(delta.values()):
            return None
        step = UsageReport(
            input_tokens=delta["input_tokens"],
            output_tokens=delta["output_tokens"],
            cache_read_tokens=delta["cache_read_tokens"],
            cost_usd=0.0,
            turns=0,
            tool_calls=0,
            duration_s=0.0,
        )
        record = usage_to_cost_record(
            step,
            self._descriptor,
            self._subject,
            record_id=self._new_id(),
            at=self._clock.now(),
        )
        await self._costs.record(record)
        self._cost_usd += record.cost_usd
        return record

    @property
    def total(self) -> UsageReport:
        """The last cumulative report, with ``cost_usd`` = the USD recorded by this meter."""
        return self._last.model_copy(update={"cost_usd": round(self._cost_usd, _COST_DECIMALS)})
