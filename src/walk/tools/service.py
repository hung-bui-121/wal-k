"""Tool catalogue loading and the default registry (§30, §91)."""

import logging
import re
from pathlib import Path
from typing import Final

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from walk.common.errors import ConfigError
from walk.common.ids import ToolName
from walk.tools.models import ToolKind, ToolSpec

logger = logging.getLogger(__name__)

_BUILTIN_TOOLS: Final = Path(__file__).resolve().parent / "builtin" / "tools.yaml"
_ALTERNATIVE: Final = "|"


class _ToolFile(BaseModel):
    """Top level of a ``tools.yaml`` file: ``tools:`` followed by a list of ToolSpec rows."""

    model_config = ConfigDict(extra="forbid")

    version: str | None = None  # behavior version of the catalogue (§105; E02-S04)
    tools: list[dict[str, object]]


def load_tool_specs(paths: list[Path]) -> list[ToolSpec]:
    """Load the packaged catalogue, then each project file in ``paths`` in order.

    A project row whose name already exists replaces that tool in place; new names are appended.

    Args:
        paths: Project override files (e.g. ``.ai/agents/tools.yaml``); may be empty.

    Returns:
        The merged catalogue in load order.

    Raises:
        ConfigError: If a file is missing or malformed, a row is invalid (message and detail
            name the file and the 1-based row) or a name repeats within one file.
    """
    merged: dict[str, ToolSpec] = {}
    for path in [_BUILTIN_TOOLS, *paths]:
        for spec in _load_file(path):
            merged[spec.name] = spec
    return list(merged.values())


def _load_file(path: Path) -> list[ToolSpec]:
    try:
        raw = _ToolFile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        msg = f"invalid tool file {path.name}: {exc}"
        raise ConfigError(msg, detail={"path": str(path)}) from exc
    specs: list[ToolSpec] = []
    seen: set[str] = set()
    for row, data in enumerate(raw.tools, start=1):
        try:
            spec = ToolSpec.model_validate(data)
        except ValidationError as exc:
            msg = f"{path.name} row {row}: {exc}"
            raise ConfigError(msg, detail={"path": str(path), "row": row}) from exc
        if spec.name in seen:
            msg = f"{path.name} row {row}: duplicate tool {spec.name!r}"
            raise ConfigError(msg, detail={"path": str(path), "row": row})
        seen.add(spec.name)
        specs.append(spec)
    return specs


def _env_ready(spec: ToolSpec, ready_env_keys: set[str]) -> bool:
    return all(
        any(key in ready_env_keys for key in requirement.split(_ALTERNATIVE))
        for requirement in spec.requires_env
    )


class DefaultToolRegistry:
    """`ToolRegistry` over an in-memory catalogue (usually from `load_tool_specs`)."""

    def __init__(self, specs: list[ToolSpec]) -> None:
        """Index ``specs`` by name and precompile the CLI command patterns.

        Raises:
            ConfigError: If two specs share a name.
        """
        self._specs: dict[str, ToolSpec] = {}
        for spec in specs:
            if spec.name in self._specs:
                msg = f"duplicate tool {spec.name!r}"
                raise ConfigError(msg, detail={"tool": spec.name})
            self._specs[spec.name] = spec
        self._cli_patterns: list[tuple[ToolSpec, list[re.Pattern[str]]]] = [
            (spec, [re.compile(pattern) for pattern in spec.command_patterns])
            for spec in specs
            if spec.kind is ToolKind.CLI
        ]

    def all(self) -> list[ToolSpec]:
        """Every tool in catalogue order."""
        return list(self._specs.values())

    def get(self, name: ToolName) -> ToolSpec:
        """The tool called ``name``.

        Raises:
            ConfigError: If no tool has that name.
        """
        spec = self._specs.get(name)
        if spec is None:
            msg = f"unknown tool {name!r}"
            raise ConfigError(msg, detail={"tool": name})
        return spec

    def available(self, ready_env_keys: set[str]) -> list[ToolSpec]:
        """Tools whose every ``requires_env`` entry has a ready key ('a|b': either one)."""
        return [spec for spec in self._specs.values() if _env_ready(spec, ready_env_keys)]

    def for_role(
        self, allowed: list[ToolName], ready_env_keys: set[str], required: list[ToolName]
    ) -> list[ToolSpec]:
        """Available tools named in ``allowed`` or ``required``, in catalogue order.

        Unknown names in ``allowed`` are skipped with a warning.

        Raises:
            ConfigError: If a required tool is unknown or unavailable; ``detail["missing"]``
                lists every such tool.
        """
        available = {spec.name for spec in self.available(ready_env_keys)}
        missing = list(dict.fromkeys(name for name in required if name not in available))
        if missing:
            msg = f"required tools unavailable: {', '.join(missing)}"
            raise ConfigError(msg, detail={"missing": missing})
        unknown = [name for name in allowed if name not in self._specs]
        if unknown:
            logger.warning("allowed tools not in catalogue", extra={"tools": unknown})
        wanted = {*allowed, *required}
        return [spec for spec in self._specs.values() if spec.name in wanted & available]

    def identify(self, command: str) -> ToolSpec | None:
        """The first CLI tool with a pattern matching the start of ``command``, else None."""
        stripped = command.lstrip()
        for spec, patterns in self._cli_patterns:
            if any(pattern.match(stripped) for pattern in patterns):
                return spec
        return None
