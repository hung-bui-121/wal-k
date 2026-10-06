"""Model configuration: `models.yaml` loading, the capability registry and family resolution.

ADR-0011 D-1/D-2/D-4: policies name model families (`claude/opus`); a family maps every effort
level to a concrete model and its provider parameters. Kernel defaults live in
`walk/model_router/defaults/models.yaml`; a project overrides them in `.ai/agents/models.yaml`.
"""

import re
from pathlib import Path
from typing import Final

import yaml
from pydantic import Field, ValidationError

from walk.common.enums import Effort
from walk.common.errors import ConfigError
from walk.common.ids import ModelId
from walk.common.models import FrozenModel, JsonDict, WalkModel
from walk.model_router.models import CapabilityRegistry, ModelDescriptor

FAMILY_PATTERN = r"^[a-z0-9-]+/[a-z0-9-]+$"  # "claude/opus", "codex/default", "fake-codex/sim"

_FAMILY_RE: Final = re.compile(FAMILY_PATTERN)
_TOP_LEVEL_KEYS: Final = frozenset({"version", "models", "families"})
_PRICE_FIELDS: Final = (
    "input_cost_per_mtok_usd",
    "output_cost_per_mtok_usd",
    "cache_read_cost_per_mtok_usd",
)
# ADR-0011 D-2 wall-clock bound per effort, used for a concrete model without a family level.
_DEFAULT_EXECUTION_TIME_S: Final[dict[Effort, int]] = {
    Effort.LOW: 600,
    Effort.MEDIUM: 1500,
    Effort.HIGH: 2700,
    Effort.VERY_HIGH: 5400,
}


class FamilyLevel(FrozenModel):
    """What one effort level of a family resolves to."""

    model: ModelId = Field(description="Concrete model serving the level.")
    params: JsonDict = Field(
        description="Provider params for this effort (effort, max_turns, model_reasoning_effort …)"
    )
    execution_time_s: int = Field(description="ADR-0011 D-2 wall-clock bound in seconds.")
    escalate_to: str | None = Field(
        default=None,
        description="Family serving this level instead (sonnet VERY_HIGH → claude/opus).",
    )


class ModelsConfig(WalkModel):
    """Merged `models.yaml`: descriptors by id and families by name."""

    version: str = Field(description="Configuration version.")
    models: dict[ModelId, ModelDescriptor] = Field(description="Descriptors by model id.")
    families: dict[str, dict[Effort, FamilyLevel]] = Field(
        description="Family name → effort → level."
    )


def load_models_config(default_path: Path, project_path: Path | None) -> ModelsConfig:
    """Load the kernel defaults and merge the project override over them.

    Project ``models`` entries replace defaults by id; project ``families`` replace by family
    name; a project ``version`` replaces the default's. A missing project file means none.

    Raises:
        ConfigError: Invalid YAML or schema, an id differing from its key, a negative price,
            a family name not matching `FAMILY_PATTERN`, or a family level naming an unknown
            model or family (``detail`` names family and level).
    """
    merged = _read(default_path)
    if project_path is not None and project_path.is_file():
        override = _read(project_path)
        for key in ("models", "families"):
            merged[key] = {**merged.get(key, {}), **override.get(key, {})}
        if "version" in override:
            merged["version"] = override["version"]
    for model_id, entry in merged.get("models", {}).items():
        if isinstance(entry, dict):
            if entry.get("id", model_id) != model_id:
                msg = f"model {model_id} declares a different id {entry['id']!r}"
                raise ConfigError(msg, detail={"model_id": model_id})
            entry["id"] = model_id
    try:
        config = ModelsConfig.model_validate(merged)
    except ValidationError as exc:
        msg = f"invalid models configuration: {exc.errors()[0]['msg']}"
        errors = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        raise ConfigError(msg, detail={"errors": errors}) from exc
    _check(config)
    return config


def build_registry(config: ModelsConfig) -> CapabilityRegistry:
    """The `CapabilityRegistry` of ``config``."""
    return CapabilityRegistry(models=dict(config.models), version=config.version)


def resolve_family(
    config: ModelsConfig, family_or_model: str, effort: Effort
) -> tuple[ModelId, FamilyLevel]:
    """Resolve a family (or pass a concrete model id through) for ``effort``.

    A family level with ``escalate_to`` is replaced by that family's level, once. A concrete
    model gets a synthesised level: no params, the ADR-0011 D-2 wall-clock bound. A name that
    is both a family and a model id resolves as the family.

    Raises:
        ConfigError: Unknown family or model, or the family lacks ``effort``.
    """
    if family_or_model in config.families:
        level = _level(config, family_or_model, effort)
        if level.escalate_to is not None:
            level = _level(config, level.escalate_to, effort)
        return level.model, level
    if family_or_model in config.models:
        level = FamilyLevel(
            model=family_or_model,
            params={},
            execution_time_s=_DEFAULT_EXECUTION_TIME_S[effort],
        )
        return family_or_model, level
    msg = f"unknown model or family: {family_or_model}"
    raise ConfigError(msg, detail={"name": family_or_model})


def _level(config: ModelsConfig, family: str, effort: Effort) -> FamilyLevel:
    level = config.families.get(family, {}).get(effort)
    if level is None:
        msg = f"family {family} has no {effort.value} level"
        raise ConfigError(msg, detail={"family": family, "level": effort.value})
    return level


def _read(path: Path) -> JsonDict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        msg = f"invalid YAML in {path}"
        raise ConfigError(msg, detail={"path": str(path)}) from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        msg = f"{path} must be a mapping"
        raise ConfigError(msg, detail={"path": str(path)})
    unknown = sorted(set(data) - _TOP_LEVEL_KEYS)
    if unknown:
        msg = f"{path} has unknown keys: {', '.join(unknown)}"
        raise ConfigError(msg, detail={"path": str(path), "keys": unknown})
    for key in ("models", "families"):
        if not isinstance(data.get(key, {}), dict):
            msg = f"{path}: {key} must be a mapping"
            raise ConfigError(msg, detail={"path": str(path), "key": key})
    return data


def _check(config: ModelsConfig) -> None:
    for model_id, descriptor in config.models.items():
        negative = [f for f in _PRICE_FIELDS if getattr(descriptor, f) < 0]
        if negative:
            msg = f"model {model_id} has a negative price: {', '.join(negative)}"
            raise ConfigError(msg, detail={"model_id": model_id, "fields": negative})
    for family, levels in config.families.items():
        if not _FAMILY_RE.fullmatch(family):
            msg = f"family name {family!r} does not match {FAMILY_PATTERN}"
            raise ConfigError(msg, detail={"family": family})
        for effort, level in levels.items():
            where = {"family": family, "level": effort.value}
            if level.model not in config.models:
                msg = f"family {family} level {effort.value} names unknown model {level.model}"
                raise ConfigError(msg, detail={**where, "model": level.model})
            if level.escalate_to is not None and level.escalate_to not in config.families:
                msg = (
                    f"family {family} level {effort.value} escalates to unknown family "
                    f"{level.escalate_to}"
                )
                raise ConfigError(msg, detail={**where, "escalate_to": level.escalate_to})
