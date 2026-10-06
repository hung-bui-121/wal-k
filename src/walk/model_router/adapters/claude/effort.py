"""Claude effort mapping (ADR-0011 D-2/D-4)."""

from typing import Final

from walk.common.enums import Effort
from walk.common.errors import ConfigError
from walk.model_router.models import ModelDescriptor, ProviderEffortConfig
from walk.model_router.registry import FamilyLevel

_EFFORT_ORDER: Final = list(Effort)
# ADR-0011 D-2: SDK effort level and turn limit per kernel effort.
_DEFAULT_PARAMS: Final[dict[Effort, tuple[str, int]]] = {
    Effort.LOW: ("low", 40),
    Effort.MEDIUM: ("medium", 80),
    Effort.HIGH: ("high", 150),
    Effort.VERY_HIGH: ("xhigh", 300),
}


def map_claude_effort(
    effort: Effort, descriptor: ModelDescriptor, level: FamilyLevel | None
) -> ProviderEffortConfig:
    """``params = {"effort": low|medium|high|xhigh, "max_turns": n}`` for ``descriptor``.

    A family ``level`` supplies the params when the descriptor supports ``effort``; otherwise
    the ADR-0011 D-2 defaults apply. An unsupported level degrades to the nearest lower
    supported one (the lowest supported when none is lower) and records ``degraded_from``
    (ADR-0011 D-4).

    Raises:
        ConfigError: The descriptor supports no effort level at all.
    """
    chosen = _supported_level(effort, descriptor)
    default_effort, default_turns = _DEFAULT_PARAMS[chosen]
    params: dict[str, object] = {"effort": default_effort, "max_turns": default_turns}
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
