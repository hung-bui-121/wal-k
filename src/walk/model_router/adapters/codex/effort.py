"""Codex effort mapping (ADR-0011 D-2/D-4, ADR-0014)."""

from typing import Final

from walk.common.enums import Effort
from walk.common.errors import ConfigError
from walk.model_router.models import ModelDescriptor, ProviderEffortConfig
from walk.model_router.registry import FamilyLevel

_EFFORT_ORDER: Final = list(Effort)
# ADR-0011 D-2: `model_reasoning_effort` per kernel effort (Codex `minimal` is unused).
_REASONING: Final[dict[Effort, str]] = {
    Effort.LOW: "low",
    Effort.MEDIUM: "medium",
    Effort.HIGH: "high",
    Effort.VERY_HIGH: "xhigh",
}


def map_codex_effort(
    effort: Effort, descriptor: ModelDescriptor, level: FamilyLevel | None
) -> ProviderEffortConfig:
    """``params = {"model_reasoning_effort": low|medium|high|xhigh}`` for ``descriptor``.

    A family ``level`` supplies the params when the descriptor supports ``effort``. An
    unsupported level (e.g. ``xhigh`` on a model without it) degrades to the nearest lower
    supported one, the lowest supported when none is lower, and records ``degraded_from``.

    Raises:
        ConfigError: The descriptor supports no effort level at all.
    """
    chosen = _supported_level(effort, descriptor)
    params: dict[str, object] = {"model_reasoning_effort": _REASONING[chosen]}
    if chosen is effort and level is not None:
        params.update(level.params)
    if chosen is not effort:
        params["degraded_from"] = effort.value
    return ProviderEffortConfig(model_id=descriptor.id, params=params)


def _supported_level(effort: Effort, descriptor: ModelDescriptor) -> Effort:
    supported = descriptor.supports_effort_levels
    if not supported:
        msg = f"model {descriptor.id} declares no effort levels"
        raise ConfigError(msg, detail={"model_id": descriptor.id})
    if effort in supported:
        return effort
    rank = _EFFORT_ORDER.index(effort)
    lower = [e for e in supported if _EFFORT_ORDER.index(e) < rank]
    if lower:
        return max(lower, key=_EFFORT_ORDER.index)
    return min(supported, key=_EFFORT_ORDER.index)
