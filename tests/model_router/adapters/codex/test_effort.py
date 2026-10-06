from pathlib import Path

import pytest

import walk.model_router
from tests.fakes.fake_model_adapter import fake_descriptor
from walk.common.enums import Effort
from walk.common.errors import ConfigError
from walk.model_router import load_models_config, resolve_family
from walk.model_router.adapters.codex.effort import map_codex_effort

DEFAULTS = Path(walk.model_router.__file__).resolve().parent / "defaults" / "models.yaml"
CODEX = "codex/gpt-5-codex"
ADR_0011_D2 = {
    Effort.LOW: "low",
    Effort.MEDIUM: "medium",
    Effort.HIGH: "high",
    Effort.VERY_HIGH: "xhigh",
}


def test_map_codex_effort_matches_adr() -> None:
    config = load_models_config(DEFAULTS, None)
    codex = config.models[CODEX]
    for effort, expected in ADR_0011_D2.items():
        result = map_codex_effort(effort, codex, None)
        assert result.model_id == CODEX
        assert result.params == {"model_reasoning_effort": expected}
        _, level = resolve_family(config, "codex/default", effort)
        assert map_codex_effort(effort, codex, level).params == {"model_reasoning_effort": expected}

    without_xhigh = codex.model_copy(
        update={"supports_effort_levels": [Effort.LOW, Effort.MEDIUM, Effort.HIGH]}
    )
    degraded = map_codex_effort(Effort.VERY_HIGH, without_xhigh, None)
    assert degraded.params == {"model_reasoning_effort": "high", "degraded_from": "VERY_HIGH"}


def test_map_codex_effort_degrades_up_when_nothing_lower_and_rejects_empty() -> None:
    only_medium = fake_descriptor(CODEX, "codex", supports_effort_levels=[Effort.MEDIUM])
    assert map_codex_effort(Effort.LOW, only_medium, None).params == {
        "model_reasoning_effort": "medium",
        "degraded_from": "LOW",
    }
    with pytest.raises(ConfigError, match="no effort levels"):
        map_codex_effort(
            Effort.LOW, fake_descriptor(CODEX, "codex", supports_effort_levels=[]), None
        )
