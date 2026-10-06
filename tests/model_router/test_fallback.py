import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_model_adapter import FakeModelAdapter, fake_descriptor
from walk.agents import ModelPolicy
from walk.common.enums import Effort
from walk.common.roles import AgentRole
from walk.model_router import (
    MAX_FALLBACKS_PER_RUN,
    PROVIDER_WIDE_TRIGGERS,
    BlockedProvider,
    DefaultModelRouter,
    FallbackRequest,
    FallbackTrigger,
    ModelDescriptor,
    ModelRouter,
    ModelsConfig,
    TaskProfile,
)
from walk.workflow import Risk

CODEX = "fake-codex/sim"
ALT = "fake-codex/alt"
CLAUDE = "fake-claude/sim"
BIG = "fake-claude/big"
DEV = AgentRole.SENIOR_DEV
T = FallbackTrigger


def _profile(tokens: int = 10_000) -> TaskProfile:
    return TaskProfile(
        required_capabilities=[],
        required_tools=[],
        required_skills=[],
        estimated_context_tokens=tokens,
        risk=Risk.MEDIUM,
    )


def _router(
    clock: FakeClock,
    codex: FakeModelAdapter,
    claude: FakeModelAdapter,
    *descriptors: ModelDescriptor,
) -> ModelRouter:
    config = ModelsConfig(version="test", models={d.id: d for d in descriptors}, families={})
    return DefaultModelRouter(config, {"fake-codex": codex, "fake-claude": claude}, clock)


def _request(trigger: FallbackTrigger, policy: ModelPolicy, **fields: object) -> FallbackRequest:
    data: dict[str, object] = {
        "role": DEV,
        "policy": policy,
        "current_model_id": CODEX,
        "trigger": trigger,
        "profile": _profile(),
        "effort": Effort.MEDIUM,
        "fallbacks_so_far": 0,
        **fields,
    }
    return FallbackRequest.model_validate(data)


async def test_fallback_excludes_failed_provider(
    fake_codex_adapter: FakeModelAdapter,
    fake_claude_adapter: FakeModelAdapter,
    fake_clock: FakeClock,
) -> None:
    router = _router(
        fake_clock,
        fake_codex_adapter,
        fake_claude_adapter,
        fake_descriptor(CODEX, "fake-codex"),
        fake_descriptor(CLAUDE, "fake-claude"),
    )
    policy = ModelPolicy(preferred=[CODEX], fallback=[CLAUDE])

    decision = await router.fallback(_request(T.PROVIDER_OUTAGE, policy))

    assert decision.model_id == CLAUDE
    assert decision.provider == "fake-claude"
    assert decision.is_fallback is True
    assert decision.trigger is T.PROVIDER_OUTAGE
    assert decision.effort is Effort.MEDIUM
    assert (CODEX, "excluded") in decision.rejected
    assert T.PROVIDER_OUTAGE in PROVIDER_WIDE_TRIGGERS
    assert MAX_FALLBACKS_PER_RUN == 2


async def test_provider_wide_triggers_exclude_whole_provider(
    fake_codex_adapter: FakeModelAdapter,
    fake_claude_adapter: FakeModelAdapter,
    fake_clock: FakeClock,
) -> None:
    router = _router(
        fake_clock,
        fake_codex_adapter,
        fake_claude_adapter,
        fake_descriptor(CODEX, "fake-codex"),
        fake_descriptor(ALT, "fake-codex"),
        fake_descriptor(CLAUDE, "fake-claude"),
    )
    policy = ModelPolicy(preferred=[CODEX, ALT], fallback=[CLAUDE])

    rate_limited = await router.fallback(_request(T.RATE_LIMIT, policy))
    timed_out = await router.fallback(_request(T.TIMEOUT, policy))

    assert rate_limited.model_id == CLAUDE
    assert {(CODEX, "excluded"), (ALT, "excluded")} <= set(rate_limited.rejected)
    assert timed_out.model_id == ALT
    assert timed_out.is_fallback is True
    assert timed_out.trigger is T.TIMEOUT
    assert timed_out.rejected == [(CODEX, "excluded")]


async def test_fallback_respects_max_fallbacks(
    fake_codex_adapter: FakeModelAdapter,
    fake_claude_adapter: FakeModelAdapter,
    fake_clock: FakeClock,
) -> None:
    router = _router(
        fake_clock,
        fake_codex_adapter,
        fake_claude_adapter,
        fake_descriptor(CODEX, "fake-codex"),
        fake_descriptor(CLAUDE, "fake-claude"),
    )
    policy = ModelPolicy(preferred=[CODEX], fallback=[CLAUDE])

    with pytest.raises(BlockedProvider) as caught:
        await router.fallback(_request(T.PROVIDER_OUTAGE, policy, fallbacks_so_far=2))

    assert caught.value.detail == {"rejected": [[CODEX, "max_fallbacks"]]}
    with pytest.raises(BlockedProvider):
        await router.fallback(_request(T.PROVIDER_OUTAGE, ModelPolicy(preferred=[CODEX])))


async def test_context_and_budget_triggers_reorder_candidates(
    fake_codex_adapter: FakeModelAdapter,
    fake_claude_adapter: FakeModelAdapter,
    fake_clock: FakeClock,
) -> None:
    small = fake_descriptor(CLAUDE, "fake-claude", output_cost_per_mtok_usd=2.0)
    big = fake_descriptor(
        BIG, "fake-claude", context_window_tokens=1_000_000, output_cost_per_mtok_usd=9.0
    )
    router = _router(
        fake_clock,
        fake_codex_adapter,
        fake_claude_adapter,
        fake_descriptor(CODEX, "fake-codex"),
        small,
        big,
    )
    policy = ModelPolicy(preferred=[CODEX], fallback=[CLAUDE, BIG])

    overflow = await router.fallback(
        _request(T.CONTEXT_OVERFLOW, policy, measured_context_tokens=100_000)
    )
    unmeasured = await router.fallback(_request(T.CONTEXT_OVERFLOW, policy))
    budget = await router.fallback(
        _request(T.BUDGET_RESTRICTION, ModelPolicy(preferred=[CODEX], fallback=[BIG, CLAUDE]))
    )

    assert overflow.model_id == BIG
    assert overflow.trigger is T.CONTEXT_OVERFLOW
    assert unmeasured.model_id == BIG
    assert budget.model_id == CLAUDE
    assert budget.trigger is T.BUDGET_RESTRICTION
