import re
from pathlib import Path

import pytest

import walk.model_router
from walk.common.enums import Effort
from walk.common.errors import ConfigError
from walk.model_router import FAMILY_PATTERN, load_models_config, resolve_family

DEFAULTS = Path(walk.model_router.__file__).resolve().parent / "defaults" / "models.yaml"
CODEX = "codex/gpt-5-codex"
OPUS = "claude/claude-opus-5-5"

CODEX_DESCRIPTOR = """
    provider: codex
    display_name: Codex
    capabilities: {CODING: 5}
    context_window_tokens: 272000
    max_output_tokens: 32000
    supports_effort_levels: [LOW, MEDIUM, HIGH, VERY_HIGH]
    supports_native_resume: true
    input_cost_per_mtok_usd: 2.0
    output_cost_per_mtok_usd: 12.0
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "models.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _sim_family(model: str) -> str:
    levels = "".join(
        f"    {e.value}: {{model: {model}, params: {{}}, execution_time_s: 60}}\n" for e in Effort
    )
    return f"families:\n  fake-codex/sim:\n{levels}"


def test_project_override_merges_by_id_and_family(tmp_path: Path) -> None:
    project = _write(
        tmp_path,
        f"models:\n  {CODEX}:{CODEX_DESCRIPTOR}"
        "  fake-codex/sim-model:\n    provider: fake-codex\n    display_name: Sim\n"
        "    capabilities: {}\n    context_window_tokens: 1000\n    max_output_tokens: 100\n"
        "    supports_effort_levels: [LOW]\n    supports_native_resume: false\n"
        "    input_cost_per_mtok_usd: 0\n    output_cost_per_mtok_usd: 0\n"
        + _sim_family("fake-codex/sim-model"),
    )

    config = load_models_config(DEFAULTS, project)
    defaults = load_models_config(DEFAULTS, None)

    codex = config.models[CODEX]
    assert (codex.input_cost_per_mtok_usd, codex.output_cost_per_mtok_usd) == (2.0, 12.0)
    assert codex.id == CODEX
    assert config.models[OPUS] == defaults.models[OPUS]
    assert sorted(config.families) == [
        "claude/opus",
        "claude/sonnet",
        "codex/default",
        "fake-codex/sim",
    ]
    assert config.families["codex/default"] == defaults.families["codex/default"]
    assert config.families["fake-codex/sim"][Effort.LOW].model == "fake-codex/sim-model"
    assert config.version == defaults.version


def test_unknown_family_model_rejected(tmp_path: Path) -> None:
    project = _write(tmp_path, _sim_family("fake-codex/missing"))

    with pytest.raises(ConfigError, match="fake-codex/sim") as info:
        load_models_config(DEFAULTS, project)

    assert info.value.detail["family"] == "fake-codex/sim"
    assert info.value.detail["level"] == "LOW"


def test_invalid_overrides_rejected(tmp_path: Path) -> None:
    negative = _write(tmp_path, f"models:\n  {CODEX}:{CODEX_DESCRIPTOR.replace('2.0', '-1.0', 1)}")
    with pytest.raises(ConfigError, match="price"):
        load_models_config(DEFAULTS, negative)

    capability = _write(tmp_path, f"models:\n  {CODEX}:{CODEX_DESCRIPTOR.replace('5}', '9}')}")
    with pytest.raises(ConfigError, match=r"0\.\.5"):
        load_models_config(DEFAULTS, capability)

    for text in (
        "unknown_key: 1\n",
        "- not a mapping\n",
        "families:\n  Bad_Name:\n    LOW: {model: x/y, params: {}, execution_time_s: 1}\n",
        f"models:\n  {CODEX}:{CODEX_DESCRIPTOR}    id: codex/other\n",
        "families:\n  fake/x:\n    LOW: {model: " + OPUS + ", params: {}, execution_time_s: 1, "
        "escalate_to: nope/none}\n",
        "families: [1, 2]\n",
    ):
        with pytest.raises(ConfigError):
            load_models_config(DEFAULTS, _write(tmp_path, text))
    with pytest.raises(ConfigError, match="YAML"):
        load_models_config(DEFAULTS, _write(tmp_path, "models: [unclosed\n"))


def test_missing_project_file_means_defaults(tmp_path: Path) -> None:
    assert load_models_config(DEFAULTS, tmp_path / "absent.yaml") == load_models_config(
        DEFAULTS, None
    )


def test_resolve_family_escalation_and_passthrough() -> None:
    config = load_models_config(DEFAULTS, None)

    escalated_id, escalated = resolve_family(config, "claude/sonnet", Effort.VERY_HIGH)
    plain_id, plain = resolve_family(config, "claude/sonnet", Effort.HIGH)
    concrete_id, concrete = resolve_family(config, OPUS, Effort.LOW)

    assert escalated_id == OPUS
    assert escalated == config.families["claude/opus"][Effort.VERY_HIGH]
    assert escalated.params == {"effort": "xhigh", "max_turns": 300}
    assert plain_id == "claude/claude-sonnet-5-5"
    assert plain.params == {"effort": "high", "max_turns": 150}
    assert concrete_id == OPUS
    assert concrete.model == OPUS
    assert concrete.params == {}
    assert concrete.execution_time_s == 600
    with pytest.raises(ConfigError, match="nope/none"):
        resolve_family(config, "nope/none", Effort.LOW)
    assert re.fullmatch(FAMILY_PATTERN, "fake-codex/sim")
    assert not re.fullmatch(FAMILY_PATTERN, "Claude/Opus")


def test_override_version_empty_file_and_missing_level(tmp_path: Path) -> None:
    versioned = load_models_config(DEFAULTS, _write(tmp_path, 'version: "2.0"\n'))
    empty = load_models_config(DEFAULTS, _write(tmp_path, ""))
    partial = load_models_config(
        DEFAULTS,
        _write(
            tmp_path,
            "families:\n  fake/low-only:\n    LOW: {model: " + OPUS + ", params: {}, "
            "execution_time_s: 1}\n",
        ),
    )

    assert versioned.version == "2.0"
    assert empty == load_models_config(DEFAULTS, None)
    assert resolve_family(partial, "fake/low-only", Effort.LOW)[0] == OPUS
    with pytest.raises(ConfigError, match="HIGH") as info:
        resolve_family(partial, "fake/low-only", Effort.HIGH)
    assert info.value.detail == {"family": "fake/low-only", "level": "HIGH"}
