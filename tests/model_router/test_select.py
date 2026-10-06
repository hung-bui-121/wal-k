import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_model_adapter import FakeModelAdapter, FakeScript, fake_descriptor
from walk.agents import AgentOutput, AgentOutputStatus, ModelPolicy
from walk.common.enums import Capability, Effort
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.model_router import (
    BlockedProvider,
    DefaultModelRouter,
    ModelDescriptor,
    ModelRouter,
    ModelsConfig,
    ProviderEffortConfig,
    TaskProfile,
)
from walk.workflow import Risk

CODEX = "fake-codex/sim"
CLAUDE = "fake-claude/sim"
ALT = "fake-codex/alt"
DEV = AgentRole.SENIOR_DEV
DONE = AgentOutput(status=AgentOutputStatus.COMPLETED, result="x", no_context_change_reason="x")


def _config(*extra: ModelDescriptor, **overrides: ModelDescriptor) -> ModelsConfig:
    models = {
        CODEX: overrides.get("codex", fake_descriptor(CODEX, "fake-codex")),
        CLAUDE: overrides.get("claude", fake_descriptor(CLAUDE, "fake-claude")),
    }
    models.update({d.id: d for d in extra})
    return ModelsConfig(version="test", models=models, families={})


def _router(
    config: ModelsConfig, codex: FakeModelAdapter, claude: FakeModelAdapter, clock: FakeClock
) -> DefaultModelRouter:
    return DefaultModelRouter(config, {"fake-codex": codex, "fake-claude": claude}, clock)


def _profile(**fields: object) -> TaskProfile:
    data: dict[str, object] = {
        "required_capabilities": [],
        "required_tools": [],
        "required_skills": [],
        "estimated_context_tokens": 10_000,
        "risk": Risk.MEDIUM,
        **fields,
    }
    return TaskProfile.model_validate(data)


POLICY = ModelPolicy(preferred=[CODEX], fallback=[CLAUDE])


async def test_select_prefers_first_healthy_candidate(
    fake_codex_adapter: FakeModelAdapter,
    fake_claude_adapter: FakeModelAdapter,
    fake_clock: FakeClock,
) -> None:
    router: ModelRouter = _router(_config(), fake_codex_adapter, fake_claude_adapter, fake_clock)

    decision = await router.select(DEV, POLICY, _profile(), Effort.HIGH)

    assert decision.model_id == CODEX
    assert decision.provider == "fake-codex"
    assert decision.effort is Effort.HIGH
    assert decision.reason == "preferred"
    assert decision.is_fallback is False
    assert decision.rejected == []
    assert decision.trigger is None


async def test_select_rejects_unhealthy_and_marks_fallback(
    fake_codex_adapter: FakeModelAdapter,
    fake_claude_adapter: FakeModelAdapter,
    fake_clock: FakeClock,
) -> None:
    fake_codex_adapter.set_healthy(False)
    router = _router(_config(), fake_codex_adapter, fake_claude_adapter, fake_clock)

    decision = await router.select(DEV, POLICY, _profile(), Effort.HIGH)

    assert decision.model_id == CLAUDE
    assert decision.reason == "fallback"
    assert decision.is_fallback is True
    assert decision.rejected == [(CODEX, "health")]


async def test_select_rejects_on_capability(
    fake_codex_adapter: FakeModelAdapter,
    fake_claude_adapter: FakeModelAdapter,
    fake_clock: FakeClock,
) -> None:
    weak = fake_descriptor(CODEX, "fake-codex", capabilities={Capability.VISUAL_REASONING: 2})
    router = _router(_config(codex=weak), fake_codex_adapter, fake_claude_adapter, fake_clock)

    decision = await router.select(
        DEV, POLICY, _profile(required_capabilities=[Capability.VISUAL_REASONING]), Effort.LOW
    )
    policy_driven = await router.select(
        DEV,
        POLICY.model_copy(update={"required_capabilities": [Capability.CODING]}),
        _profile(),
        Effort.LOW,
    )

    assert decision.model_id == CLAUDE
    assert decision.rejected == [(CODEX, "capability:VISUAL_REASONING")]
    assert policy_driven.rejected == [(CODEX, "capability:CODING")]


async def test_select_rejects_on_context_window(
    fake_codex_adapter: FakeModelAdapter,
    fake_claude_adapter: FakeModelAdapter,
    fake_clock: FakeClock,
) -> None:
    small = fake_descriptor(CODEX, "fake-codex", context_window_tokens=100_000)
    router = _router(_config(codex=small), fake_codex_adapter, fake_claude_adapter, fake_clock)

    exact = await router.select(DEV, POLICY, _profile(estimated_context_tokens=60_000), Effort.LOW)
    over = await router.select(DEV, POLICY, _profile(estimated_context_tokens=60_001), Effort.LOW)

    assert exact.model_id == CODEX
    assert over.model_id == CLAUDE
    assert over.rejected == [(CODEX, "context")]


async def test_select_rejects_on_effort(
    fake_codex_adapter: FakeModelAdapter,
    fake_claude_adapter: FakeModelAdapter,
    fake_clock: FakeClock,
) -> None:
    no_levels = fake_descriptor(CODEX, "fake-codex", supports_effort_levels=[])
    degradable = fake_descriptor(CODEX, "fake-codex", supports_effort_levels=[Effort.LOW])
    fussy = _router(_config(codex=no_levels), fake_codex_adapter, fake_claude_adapter, fake_clock)
    flexible = _router(
        _config(codex=degradable), fake_codex_adapter, fake_claude_adapter, fake_clock
    )

    rejected = await fussy.select(DEV, POLICY, _profile(), Effort.HIGH)
    degraded = await flexible.select(DEV, POLICY, _profile(), Effort.HIGH)

    assert rejected.rejected == [(CODEX, "effort")]
    assert degraded.model_id == CODEX


async def test_select_defers_implementer_model_for_review(
    fake_codex_adapter: FakeModelAdapter,
    fake_claude_adapter: FakeModelAdapter,
    fake_clock: FakeClock,
) -> None:
    router = _router(_config(), fake_codex_adapter, fake_claude_adapter, fake_clock)
    review = _profile(implementer_model_id=CODEX)

    decision = await router.select(AgentRole.LEAD_DEV, POLICY, review, Effort.MEDIUM)
    same_model_ok = await router.select(
        AgentRole.LEAD_DEV,
        POLICY.model_copy(update={"cross_model_review": False}),
        review,
        Effort.MEDIUM,
    )
    fake_claude_adapter.set_healthy(False)
    only_choice = await router.select(AgentRole.LEAD_DEV, POLICY, review, Effort.MEDIUM)

    assert decision.model_id == CLAUDE
    assert decision.is_fallback is True
    assert decision.rejected == [(CODEX, "cross_model_review")]
    assert same_model_ok.model_id == CODEX
    assert only_choice.model_id == CODEX
    assert only_choice.rejected == [(CODEX, "cross_model_review"), (CLAUDE, "health")]


async def test_select_task_override_respects_policy(
    fake_codex_adapter: FakeModelAdapter,
    fake_claude_adapter: FakeModelAdapter,
    fake_clock: FakeClock,
) -> None:
    config = _config(fake_descriptor(ALT, "fake-codex"))
    router = _router(config, fake_codex_adapter, fake_claude_adapter, fake_clock)
    strict = POLICY.model_copy(update={"allow_task_override": False})

    ignored = await router.select(DEV, strict, _profile(), Effort.LOW, task_override=ALT)
    honoured = await router.select(DEV, POLICY, _profile(), Effort.LOW, task_override=ALT)

    assert ignored.model_id == CODEX
    assert honoured.model_id == ALT
    assert honoured.reason == "override"
    assert honoured.is_fallback is True


async def test_select_raises_blocked_provider(
    fake_codex_adapter: FakeModelAdapter,
    fake_claude_adapter: FakeModelAdapter,
    fake_clock: FakeClock,
) -> None:
    disabled = fake_descriptor(CLAUDE, "fake-claude", enabled=False)
    config = _config(fake_descriptor(ALT, "fake-codex"), claude=disabled)
    router = _router(config, fake_codex_adapter, fake_claude_adapter, fake_clock)
    policy = ModelPolicy(preferred=[CODEX], fallback=[CLAUDE, ALT], restricted=[ALT])

    with pytest.raises(BlockedProvider) as info:
        await router.select(DEV, policy, _profile(), Effort.LOW, exclude=[CODEX])

    assert info.value.detail["rejected"] == [
        [CODEX, "excluded"],
        [CLAUDE, "MODEL_DISABLED"],
        [ALT, "restricted"],
    ]


async def test_select_resolves_families_and_deduplicates(
    fake_codex_adapter: FakeModelAdapter,
    fake_claude_adapter: FakeModelAdapter,
    fake_clock: FakeClock,
) -> None:
    config = ModelsConfig.model_validate(
        {
            **_config().model_dump(),
            "families": {
                "fake-codex/default": {
                    e.value: {"model": CODEX, "params": {}, "execution_time_s": 60} for e in Effort
                }
            },
        }
    )
    router = _router(config, fake_codex_adapter, fake_claude_adapter, fake_clock)
    policy = ModelPolicy(preferred=["fake-codex/default", CODEX], fallback=[CLAUDE])
    fake_codex_adapter.set_healthy(False)

    decision = await router.select(DEV, policy, _profile(), Effort.LOW)

    assert decision.model_id == CLAUDE
    assert decision.rejected == [(CODEX, "health")]


async def test_adapter_for_and_health_all(
    fake_codex_adapter: FakeModelAdapter,
    fake_claude_adapter: FakeModelAdapter,
    fake_clock: FakeClock,
) -> None:
    config = _config(fake_descriptor(ALT, "fake-codex"))
    router = _router(config, fake_codex_adapter, fake_claude_adapter, fake_clock)
    fake_claude_adapter.set_healthy(False)

    health = await router.health_all()

    assert router.adapter_for(ALT) is fake_codex_adapter
    assert router.adapter_for(CLAUDE) is fake_claude_adapter
    with pytest.raises(ConfigError, match="nope"):
        router.adapter_for("nope/x")
    assert sorted(health) == sorted([CODEX, CLAUDE, ALT])
    assert health[ALT].ok is True
    assert health[CLAUDE].ok is False
    assert router.registry().models == config.models
    assert router.registry().version == "test"


async def test_router_requires_an_adapter_per_enabled_provider(
    fake_codex_adapter: FakeModelAdapter, fake_clock: FakeClock
) -> None:
    with pytest.raises(ConfigError, match="fake-claude"):
        DefaultModelRouter(_config(), {"fake-codex": fake_codex_adapter}, fake_clock)

    disabled = fake_descriptor(CLAUDE, "fake-claude", enabled=False)
    router = DefaultModelRouter(
        _config(claude=disabled), {"fake-codex": fake_codex_adapter}, fake_clock
    )
    with pytest.raises(ConfigError, match="fake-claude"):
        router.adapter_for(CLAUDE)
    assert sorted(await router.health_all()) == [CODEX]


class RefusingAdapter(FakeModelAdapter):
    """Adapter that cannot translate efforts the model does not list."""

    def map_effort(self, effort: Effort, model_id: str) -> ProviderEffortConfig:
        msg = f"{model_id} cannot run at {effort.value}"
        raise ConfigError(msg)


async def test_select_rejects_effort_the_adapter_cannot_map(
    fake_claude_adapter: FakeModelAdapter, fake_clock: FakeClock
) -> None:
    low_only = fake_descriptor(CODEX, "fake-codex", supports_effort_levels=[Effort.LOW])
    refusing = RefusingAdapter("fake-codex", [low_only], FakeScript(output=DONE), fake_clock)
    router = _router(_config(codex=low_only), refusing, fake_claude_adapter, fake_clock)

    decision = await router.select(DEV, POLICY, _profile(), Effort.HIGH)

    assert decision.model_id == CLAUDE
    assert decision.rejected == [(CODEX, "effort")]
