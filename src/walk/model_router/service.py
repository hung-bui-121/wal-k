"""`DefaultModelRouter`: model selection, the fallback decision and error triage (INTERFACES §5.3).

Selection writes nothing to the ledger; the executor records ``MODEL_SELECTED`` with the
decision, including its ``rejected`` reasons, whose strings are part of that payload:
``capability:<c>``, ``context``, ``effort``, ``cross_model_review``, ``health``,
``MODEL_DISABLED``, ``restricted``, ``excluded``.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

from walk.agents.models import ModelPolicy
from walk.budgets.errors import BudgetExhausted
from walk.budgets.models import BudgetHardAction
from walk.common.clock import Clock
from walk.common.enums import Capability, Effort
from walk.common.errors import (
    ConfigError,
    OutputInvalid,
    ProviderUnavailable,
    QuotaExhausted,
    RateLimited,
    Timeout,
    ToolCrashed,
    WalkError,
)
from walk.common.ids import ModelId
from walk.common.roles import AgentRole
from walk.model_router.errors import BlockedProvider
from walk.model_router.models import (
    AdapterHealth,
    CapabilityRegistry,
    FallbackRequest,
    FallbackTrigger,
    ModelDescriptor,
    RoutingDecision,
    TaskProfile,
)
from walk.model_router.protocols import ModelAdapter
from walk.model_router.registry import ModelsConfig, build_registry, resolve_family

ERROR_TRIGGER_MAP: dict[type[BaseException], FallbackTrigger] = {
    ProviderUnavailable: FallbackTrigger.PROVIDER_OUTAGE,
    RateLimited: FallbackTrigger.RATE_LIMIT,
    QuotaExhausted: FallbackTrigger.QUOTA_EXHAUSTED,
    Timeout: FallbackTrigger.TIMEOUT,
    ToolCrashed: FallbackTrigger.TOOL_INCOMPATIBILITY,
    BudgetExhausted: FallbackTrigger.BUDGET_RESTRICTION,
    OutputInvalid: FallbackTrigger.REPEATED_OUTPUT_INVALID,
}

PROVIDER_WIDE_TRIGGERS: frozenset[FallbackTrigger] = frozenset(
    {
        FallbackTrigger.PROVIDER_OUTAGE,
        FallbackTrigger.QUOTA_EXHAUSTED,
        FallbackTrigger.RATE_LIMIT,
    }
)
"""Triggers that exclude every model of the failing model's provider (INTERFACES §5.3 step 8)."""

_MIN_CAPABILITY: Final = 3  # §16: a score below 3 does not qualify for a required capability
_CONTEXT_SHARE: Final = 0.6  # estimated context must fit in 60 % of the window
_MAX_FALLBACKS: Final = "max_fallbacks"

_Order = Callable[[ModelDescriptor], float]


@dataclass
class _Candidate:
    model_id: ModelId
    origin: str  # "override" | "preferred" | "fallback"
    deferred: bool = False


class DefaultModelRouter:
    """`ModelRouter` over a `ModelsConfig` and one adapter per provider."""

    def __init__(
        self, config: ModelsConfig, adapters: dict[str, ModelAdapter], clock: Clock
    ) -> None:
        """Wire the router.

        Args:
            config: Merged `models.yaml`.
            adapters: Adapters keyed by provider.
            clock: Kernel clock.

        Raises:
            ConfigError: An enabled descriptor's provider has no adapter.
        """
        missing = sorted({d.provider for d in config.models.values() if d.enabled} - set(adapters))
        if missing:
            msg = f"no adapter for provider(s): {', '.join(missing)}"
            raise ConfigError(msg, detail={"providers": missing})
        self._config = config
        self._adapters = dict(adapters)
        self._clock = clock
        self._registry = build_registry(config)

    def registry(self) -> CapabilityRegistry:
        """The descriptors of every configured model."""
        return self._registry

    def adapter_for(self, model_id: ModelId) -> ModelAdapter:
        """The adapter of the provider serving ``model_id``.

        Raises:
            ConfigError: Unknown model, or its provider has no adapter.
        """
        descriptor = self._config.models.get(model_id)
        if descriptor is None:
            msg = f"unknown model: {model_id}"
            raise ConfigError(msg, detail={"model_id": model_id})
        adapter = self._adapters.get(descriptor.provider)
        if adapter is None:
            msg = f"no adapter for provider {descriptor.provider} (model {model_id})"
            raise ConfigError(msg, detail={"model_id": model_id, "provider": descriptor.provider})
        return adapter

    async def select(
        self,
        role: AgentRole,
        policy: ModelPolicy,
        profile: TaskProfile,
        effort: Effort,
        *,
        exclude: Sequence[ModelId] = (),
        task_override: ModelId | None = None,
    ) -> RoutingDecision:
        """INTERFACES §5.3 steps 1-4; ``role`` is not used by the MVP rules.

        Raises:
            BlockedProvider: No candidate survives; ``detail["rejected"]`` lists
                ``[model_id, reason]`` pairs.
            ConfigError: A policy names an unknown family or model.
        """
        del role
        return await self._select(policy, profile, effort, exclude, task_override, None)

    async def fallback(self, request: FallbackRequest) -> RoutingDecision:
        """INTERFACES §5.3 steps 7-9: the decision only (no ledger, checkpoint or run).

        Step 7: the chain's fallback count must be below ``max_fallbacks``. Step 8: the
        current model is excluded, with every model of its provider for a
        `PROVIDER_WIDE_TRIGGERS` trigger; CONTEXT_OVERFLOW selects with the measured context
        size and tries the largest window first, BUDGET_RESTRICTION the cheapest output price
        first. Step 9: `select`; the decision has ``is_fallback=True`` and the trigger.

        Raises:
            BlockedProvider: The chain reached ``max_fallbacks`` (rejection ``max_fallbacks``)
                or no candidate survives.
            ConfigError: A policy names an unknown family or model.
        """
        current = request.current_model_id
        if request.fallbacks_so_far >= request.max_fallbacks:
            msg = f"run chain reached {request.max_fallbacks} fallbacks"
            raise BlockedProvider(msg, detail={"rejected": [[current, _MAX_FALLBACKS]]})
        exclude = [current]
        failing = self._config.models.get(current)
        if request.trigger in PROVIDER_WIDE_TRIGGERS and failing is not None:
            exclude += [
                model_id
                for model_id, descriptor in self._config.models.items()
                if descriptor.provider == failing.provider and model_id != current
            ]
        profile = request.profile
        order: _Order | None = None
        if request.trigger is FallbackTrigger.CONTEXT_OVERFLOW:
            if request.measured_context_tokens is not None:
                profile = profile.model_copy(
                    update={"estimated_context_tokens": request.measured_context_tokens}
                )
            order = _largest_window_first
        elif request.trigger is FallbackTrigger.BUDGET_RESTRICTION:
            order = _cheapest_output_first
        decision = await self._select(request.policy, profile, request.effort, exclude, None, order)
        return decision.model_copy(update={"is_fallback": True, "trigger": request.trigger})

    async def _select(  # noqa: PLR0917 - private core of select and fallback
        self,
        policy: ModelPolicy,
        profile: TaskProfile,
        effort: Effort,
        exclude: Sequence[ModelId],
        task_override: ModelId | None,
        order: _Order | None,
    ) -> RoutingDecision:
        rejected: list[tuple[ModelId, str]] = []
        preferred = {resolve_family(self._config, p, effort)[0] for p in policy.preferred}
        queue = self._candidates(policy, effort, exclude, task_override, rejected)
        if order is not None:
            queue.sort(key=lambda candidate: order(self._config.models[candidate.model_id]))
        required = list(
            dict.fromkeys([*profile.required_capabilities, *policy.required_capabilities])
        )
        health: dict[str, AdapterHealth] = {}
        while queue:
            candidate = queue.pop(0)
            descriptor = self._config.models[candidate.model_id]
            reason = self._static_rejection(descriptor, required, profile, effort)
            if reason is None and (
                policy.cross_model_review
                and profile.implementer_model_id == candidate.model_id
                and queue
                and not candidate.deferred
            ):
                rejected.append((candidate.model_id, "cross_model_review"))
                candidate.deferred = True
                queue.append(candidate)
                continue
            if reason is None and not (await self._health(descriptor, health)).ok:
                reason = "health"
            if reason is not None:
                rejected.append((candidate.model_id, reason))
                continue
            return RoutingDecision(
                model_id=candidate.model_id,
                provider=descriptor.provider,
                effort=effort,
                reason=candidate.origin,
                rejected=rejected,
                is_fallback=candidate.model_id not in preferred,
            )
        msg = "no routing candidate survived"
        raise BlockedProvider(msg, detail={"rejected": [[m, r] for m, r in rejected]})

    def classify_error(self, exc: BaseException, adapter: ModelAdapter) -> FallbackTrigger | None:
        """Map ``exc`` to a §21 trigger; None = not a fallback condition.

        An adapter's own optional ``classify_error(exc)`` wins when it returns a trigger;
        otherwise the most-derived `ERROR_TRIGGER_MAP` class matches. `BudgetExhausted`
        counts only when its ``detail["hard_action"]`` is FALLBACK_MODEL.
        """
        own = getattr(adapter, "classify_error", None)
        if callable(own):
            trigger = own(exc)
            if isinstance(trigger, FallbackTrigger):
                return trigger
        for cls in type(exc).__mro__:
            trigger = ERROR_TRIGGER_MAP.get(cls)
            if trigger is None:
                continue
            if cls is BudgetExhausted and not _falls_back(exc):
                return None
            return trigger
        return None

    async def health_all(self) -> dict[ModelId, AdapterHealth]:
        """Health of every model whose provider has an adapter; one query per adapter."""
        cache: dict[str, AdapterHealth] = {}
        result: dict[ModelId, AdapterHealth] = {}
        for model_id, descriptor in self._config.models.items():
            if descriptor.provider in self._adapters:
                result[model_id] = await self._health(descriptor, cache)
        return result

    def _candidates(
        self,
        policy: ModelPolicy,
        effort: Effort,
        exclude: Sequence[ModelId],
        task_override: ModelId | None,
        rejected: list[tuple[ModelId, str]],
    ) -> list[_Candidate]:
        raw: list[tuple[str, str]] = []
        if task_override is not None and policy.allow_task_override:
            raw.append((task_override, "override"))
        raw += [(p, "preferred") for p in policy.preferred]
        raw += [(f, "fallback") for f in policy.fallback]
        restricted = set(policy.restricted) | {
            resolve_family(self._config, r, effort)[0]
            for r in policy.restricted
            if r in self._config.families or r in self._config.models
        }
        queue: list[_Candidate] = []
        seen: set[str] = set()
        for name, origin in raw:
            model_id, _ = resolve_family(self._config, name, effort)
            if model_id in seen:
                continue
            seen.add(model_id)
            if name in restricted or model_id in restricted:
                rejected.append((model_id, "restricted"))
            elif not self._config.models[model_id].enabled:
                rejected.append((model_id, FallbackTrigger.MODEL_DISABLED.value))
            elif name in exclude or model_id in exclude:
                rejected.append((model_id, "excluded"))
            else:
                queue.append(_Candidate(model_id, origin))
        return queue

    def _static_rejection(
        self,
        descriptor: ModelDescriptor,
        required: list[Capability],
        profile: TaskProfile,
        effort: Effort,
    ) -> str | None:
        for capability in required:
            if descriptor.capabilities.get(capability, 0) < _MIN_CAPABILITY:
                return f"capability:{capability.value}"
        if profile.estimated_context_tokens > _CONTEXT_SHARE * descriptor.context_window_tokens:
            return "context"
        if effort not in descriptor.supports_effort_levels and not self._can_degrade(
            descriptor, effort
        ):
            return "effort"
        return None

    def _can_degrade(self, descriptor: ModelDescriptor, effort: Effort) -> bool:
        if not descriptor.supports_effort_levels:
            return False
        try:
            self._adapters[descriptor.provider].map_effort(effort, descriptor.id)
        except WalkError:
            return False
        return True

    async def _health(
        self, descriptor: ModelDescriptor, cache: dict[str, AdapterHealth]
    ) -> AdapterHealth:
        if descriptor.provider not in cache:
            cache[descriptor.provider] = await self._adapters[descriptor.provider].health()
        return cache[descriptor.provider]


def _largest_window_first(descriptor: ModelDescriptor) -> float:
    return -float(descriptor.context_window_tokens)


def _cheapest_output_first(descriptor: ModelDescriptor) -> float:
    return descriptor.output_cost_per_mtok_usd


def _falls_back(exc: BaseException) -> bool:
    detail = exc.detail if isinstance(exc, WalkError) else {}
    return str(detail.get("hard_action")) == BudgetHardAction.FALLBACK_MODEL.value
