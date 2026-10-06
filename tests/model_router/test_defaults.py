from pathlib import Path

import walk.model_router
from walk.common.enums import Capability, Effort
from walk.model_router import ModelsConfig, build_registry, load_models_config

DEFAULTS = Path(walk.model_router.__file__).resolve().parent / "defaults" / "models.yaml"
OPUS = "claude/claude-opus-5-5"
SONNET = "claude/claude-sonnet-5-5"
CODEX = "codex/gpt-5-codex"


def _config() -> ModelsConfig:
    return load_models_config(DEFAULTS, None)


def test_default_models_yaml_matches_adr_0011() -> None:
    config = _config()

    assert sorted(config.models) == sorted([OPUS, SONNET, CODEX])
    assert sorted(config.families) == ["claude/opus", "claude/sonnet", "codex/default"]
    for levels in config.families.values():
        assert list(levels) == list(Effort)
        assert [level.execution_time_s for level in levels.values()] == [600, 1500, 2700, 5400]
    sonnet = config.families["claude/sonnet"]
    assert sonnet[Effort.VERY_HIGH].escalate_to == "claude/opus"
    assert all(level.escalate_to is None for e, level in sonnet.items() if e != Effort.VERY_HIGH)
    opus = config.families["claude/opus"]
    assert [opus[e].params for e in Effort] == [
        {"effort": "low", "max_turns": 40},
        {"effort": "medium", "max_turns": 80},
        {"effort": "high", "max_turns": 150},
        {"effort": "xhigh", "max_turns": 300},
    ]
    assert [sonnet[e].model for e in Effort] == [SONNET, SONNET, SONNET, OPUS]
    codex = config.families["codex/default"]
    assert [codex[e].params for e in Effort] == [
        {"model_reasoning_effort": "low"},
        {"model_reasoning_effort": "medium"},
        {"model_reasoning_effort": "high"},
        {"model_reasoning_effort": "xhigh"},
    ]
    assert {codex[e].model for e in Effort} == {CODEX}


def test_default_descriptors_match_adr_0011() -> None:
    models = _config().models
    opus, sonnet, codex = models[OPUS], models[SONNET], models[CODEX]

    assert (opus.provider, sonnet.provider, codex.provider) == ("claude", "claude", "codex")
    assert all(d.supports_effort_levels == list(Effort) for d in models.values())
    assert all(d.supports_native_resume for d in models.values())
    assert [d.context_window_tokens for d in (opus, sonnet, codex)] == [200_000, 200_000, 272_000]
    assert {d.max_output_tokens for d in models.values()} == {32_000}
    assert [
        (d.input_cost_per_mtok_usd, d.output_cost_per_mtok_usd, d.cache_read_cost_per_mtok_usd)
        for d in (opus, sonnet, codex)
    ] == [(15.0, 75.0, 1.5), (3.0, 15.0, 0.3), (1.25, 10.0, 0.125)]
    assert opus.capabilities == {
        c: 4 if c is Capability.VISUAL_REASONING else 5 for c in Capability
    }
    assert sonnet.capabilities == {
        c: 3 if c is Capability.VISUAL_REASONING else 4 for c in Capability
    }
    assert codex.capabilities == {
        Capability.CODING: 5,
        Capability.ARCHITECTURE: 3,
        Capability.REPOSITORY_NAVIGATION: 5,
        Capability.LONG_CONTEXT_REASONING: 4,
        Capability.DESIGN_REASONING: 2,
        Capability.VISUAL_REASONING: 1,
        Capability.TOOL_USE: 5,
        Capability.REVIEW: 4,
        Capability.PLANNING: 3,
    }
    registry = build_registry(_config())
    assert registry.version == "1.0"
    assert registry.models == models
