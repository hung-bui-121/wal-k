from pathlib import Path

import pytest

import walk.model_router
from tests.fakes.fake_model_adapter import fake_descriptor
from walk.common.enums import Effort
from walk.common.errors import ConfigError
from walk.model_router import load_models_config, resolve_family
from walk.model_router.adapters.claude.effort import map_claude_effort

DEFAULTS = Path(walk.model_router.__file__).resolve().parent / "defaults" / "models.yaml"
OPUS = "claude/claude-opus-5-5"
ADR_0011_D2 = {
    Effort.LOW: {"effort": "low", "max_turns": 40},
    Effort.MEDIUM: {"effort": "medium", "max_turns": 80},
    Effort.HIGH: {"effort": "high", "max_turns": 150},
    Effort.VERY_HIGH: {"effort": "xhigh", "max_turns": 300},
}


def test_map_claude_effort_matches_adr_and_degrades() -> None:
    config = load_models_config(DEFAULTS, None)
    opus = config.models[OPUS]
    for effort, expected in ADR_0011_D2.items():
        config_out = map_claude_effort(effort, opus, None)
        assert config_out.model_id == OPUS
        assert config_out.params == expected
        _, level = resolve_family(config, "claude/opus", effort)
        assert map_claude_effort(effort, opus, level).params == expected

    up_to_high = opus.model_copy(
        update={"supports_effort_levels": [Effort.LOW, Effort.MEDIUM, Effort.HIGH]}
    )
    degraded = map_claude_effort(Effort.VERY_HIGH, up_to_high, None)
    assert degraded.params == {"effort": "high", "max_turns": 150, "degraded_from": "VERY_HIGH"}


def test_map_claude_effort_uses_family_level_params() -> None:
    config = load_models_config(DEFAULTS, None)
    opus = config.models[OPUS]
    _, level = resolve_family(config, "claude/opus", Effort.LOW)
    custom = level.model_copy(update={"params": {"effort": "medium", "max_turns": 12}})
    assert map_claude_effort(Effort.LOW, opus, custom).params == {
        "effort": "medium",
        "max_turns": 12,
    }


def test_map_claude_effort_degrades_upwards_only_when_nothing_lower() -> None:
    only_high = fake_descriptor(OPUS, "claude", supports_effort_levels=[Effort.HIGH])
    result = map_claude_effort(Effort.LOW, only_high, None)
    assert result.params == {"effort": "high", "max_turns": 150, "degraded_from": "LOW"}


def test_map_claude_effort_without_levels_is_config_error() -> None:
    none = fake_descriptor(OPUS, "claude", supports_effort_levels=[])
    with pytest.raises(ConfigError, match="no effort levels"):
        map_claude_effort(Effort.LOW, none, None)
