from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_model_adapter import FakeModelAdapter, FakeScript, fake_descriptor
from walk.agents import AgentOutput, AgentOutputStatus
from walk.budgets import BudgetExhausted, BudgetHardAction
from walk.common.errors import (
    OutputInvalid,
    ProviderUnavailable,
    QuotaExhausted,
    RateLimited,
    Timeout,
    ToolCrashed,
    TransientError,
)
from walk.model_router import (
    ERROR_TRIGGER_MAP,
    DefaultModelRouter,
    FallbackTrigger,
    ModelsConfig,
)

DONE = AgentOutput(status=AgentOutputStatus.COMPLETED, result="x", no_context_change_reason="x")


class ClassifyingAdapter(FakeModelAdapter):
    """Adapter that recognises its own provider error."""

    def classify_error(self, exc: BaseException) -> FallbackTrigger | None:
        return FallbackTrigger.CONTEXT_OVERFLOW if "too long" in str(exc) else None


def _router(adapter: FakeModelAdapter, clock: FakeClock) -> DefaultModelRouter:
    config = ModelsConfig(
        version="t",
        models={"fake-codex/sim": fake_descriptor("fake-codex/sim", "fake-codex")},
        families={},
    )
    return DefaultModelRouter(config, {"fake-codex": adapter}, clock)


def test_classify_error_maps_taxonomy(
    fake_codex_adapter: FakeModelAdapter, fake_clock: FakeClock
) -> None:
    router = _router(fake_codex_adapter, fake_clock)
    fallback = BudgetExhausted(
        "hard limit", detail={"budget_id": "b", "hard_action": BudgetHardAction.FALLBACK_MODEL}
    )
    blocking = BudgetExhausted("hard limit", detail={"budget_id": "b", "hard_action": "BLOCK"})

    for error_type, trigger in ERROR_TRIGGER_MAP.items():
        if error_type is BudgetExhausted:
            assert router.classify_error(fallback, fake_codex_adapter) is trigger
            continue
        assert router.classify_error(error_type("boom"), fake_codex_adapter) is trigger
    assert dict(ERROR_TRIGGER_MAP) == {
        ProviderUnavailable: FallbackTrigger.PROVIDER_OUTAGE,
        RateLimited: FallbackTrigger.RATE_LIMIT,
        QuotaExhausted: FallbackTrigger.QUOTA_EXHAUSTED,
        Timeout: FallbackTrigger.TIMEOUT,
        ToolCrashed: FallbackTrigger.TOOL_INCOMPATIBILITY,
        BudgetExhausted: FallbackTrigger.BUDGET_RESTRICTION,
        OutputInvalid: FallbackTrigger.REPEATED_OUTPUT_INVALID,
    }
    assert router.classify_error(ValueError("x"), fake_codex_adapter) is None
    assert router.classify_error(blocking, fake_codex_adapter) is None
    assert router.classify_error(BudgetExhausted("no detail"), fake_codex_adapter) is None
    assert router.classify_error(TransientError("generic"), fake_codex_adapter) is None


def test_classify_error_uses_most_derived_mapping(
    fake_codex_adapter: FakeModelAdapter, fake_clock: FakeClock
) -> None:
    class SlowProvider(Timeout):
        """A provider-specific timeout."""

    router = _router(fake_codex_adapter, fake_clock)

    assert (
        router.classify_error(SlowProvider("slow"), fake_codex_adapter) is FallbackTrigger.TIMEOUT
    )


def test_adapter_classification_takes_precedence(fake_clock: FakeClock) -> None:
    adapter = ClassifyingAdapter(
        "fake-codex",
        [fake_descriptor("fake-codex/sim", "fake-codex")],
        FakeScript(output=DONE),
        fake_clock,
    )
    router = _router(adapter, fake_clock)

    assert (
        router.classify_error(ProviderUnavailable("prompt too long"), adapter)
        is FallbackTrigger.CONTEXT_OVERFLOW
    )
    assert (
        router.classify_error(ProviderUnavailable("down"), adapter)
        is FallbackTrigger.PROVIDER_OUTAGE
    )
