"""Behavior versions of the kernel's builtin artifacts and the project's pins (§105; ADR-0008).

`BehaviorVersionCatalog` reads the version of every builtin behavior artifact of the installed
kernel. `KernelVersionPins` is `.ai/project/kernel-versions.yaml`: the versions a project
expects. Until E10-S05 each artifact has exactly one version, which must equal its pin.
"""

import hashlib
import os
import re
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Final, NoReturn, Self

import yaml
from pydantic import Field, ValidationError

from walk.common.clock import Clock
from walk.common.enums import ImprovementScope
from walk.common.errors import ConfigError
from walk.common.models import JsonDict, WalkModel
from walk.improvement.errors import VersionPinError
from walk.improvement.models import BehaviorVersion, RolloutStage

PINS_PATH: str = "project/kernel-versions.yaml"
"""Path of the pin file relative to `.ai/`."""

_VERSION: Final = re.compile(r"^\d+\.\d+$")
_TEMPLATE_VERSION: Final = re.compile(r"^\{#\s*version:\s*(\S+)\s*#\}\s*$")
_FRONT_MATTER: Final = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_GUIDANCE: Final = "run 'walk version' and update .ai/project/kernel-versions.yaml"
# Single-file artifacts: (kind, name, path relative to the package). A file that is absent is
# not catalogued (`context/ranking.yaml` arrives with a later epic).
_SINGLE_FILES: Final = (
    (ImprovementScope.MODEL_ROUTING, "models", "model_router/defaults/models.yaml"),
    (ImprovementScope.TOOL_USAGE, "tools", "tools/builtin/tools.yaml"),
    (ImprovementScope.CONTEXT_FORMAT, "ranking", "context/ranking.yaml"),
)
_POLICIES: Final = "agents/defaults/policies.yaml"


class BehaviorVersionCatalog:
    """Scans builtin behaviour files and yields one BehaviorVersion per artifact (stage=DEFAULT)."""

    def __init__(self, package_root: Path, clock: Clock) -> None:
        """Scan below ``package_root`` (the installed ``walk`` package).

        Args:
            package_root: Directory of the ``walk`` package.
            clock: Stamps ``introduced_at`` (not persisted in E02).
        """
        self._root = package_root
        self._clock = clock

    def scan(self) -> list[BehaviorVersion]:
        """Every builtin behavior artifact, in a stable order.

        - WORKFLOW: ``workflow/tables/*_workflow.yaml`` (top-level ``version``).
        - CONSTITUTION: ``agents/defaults/*.md`` (front matter ``version``, named by ``id``).
        - SKILL: ``skills/builtin/*/SKILL.md`` (front matter ``version``).
        - PROMPT: ``agents/templates/*.md.j2`` (first line ``{# version: X.Y #}``).
        - MODEL_ROUTING: ``model_router/defaults/models.yaml``.
        - TOOL_USAGE: ``tools/builtin/tools.yaml``.
        - CONTEXT_FORMAT: ``context/ranking.yaml``, if present.
        - EFFORT_POLICY: ``agents/defaults/policies.yaml``, one entry per role
          (``roles.<ROLE>.version``).

        Raises:
            ConfigError: An artifact has no version (``<path>: missing version``), a version that
                is not a quoted ``MAJOR.MINOR`` string, or invalid YAML.
        """
        now = self._clock.now()
        return [
            self._entry(kind, name, version, path, now)
            for kind, name, version, path in self._artifacts()
        ]

    def key(self, v: BehaviorVersion) -> str:
        """The pin key of ``v``: ``<KIND>/<name>``."""
        return _key(v)

    def _artifacts(self) -> Iterator[tuple[ImprovementScope, str, object, Path]]:
        root = self._root
        for path in sorted((root / "workflow" / "tables").glob("*_workflow.yaml")):
            yield ImprovementScope.WORKFLOW, path.stem, _yaml_mapping(path).get("version"), path
        for path in sorted((root / "agents" / "defaults").glob("*.md")):
            header = _front_matter(path)
            name = str(header.get("id", path.stem))
            yield ImprovementScope.CONSTITUTION, name, header.get("version"), path
        for path in sorted((root / "skills" / "builtin").glob("*/SKILL.md")):
            yield ImprovementScope.SKILL, path.parent.name, _front_matter(path).get("version"), path
        for path in sorted((root / "agents" / "templates").glob("*.md.j2")):
            name = path.name.removesuffix(".md.j2")
            yield ImprovementScope.PROMPT, name, _template_version(path), path
        for kind, name, relative in _SINGLE_FILES:
            path = root / relative
            if path.is_file():
                yield kind, name, _yaml_mapping(path).get("version"), path
        policies = root / _POLICIES
        if policies.is_file():
            roles = _yaml_mapping(policies).get("roles")
            if not isinstance(roles, dict) or not roles:
                _fail(policies, "missing version")
            for role, policy in roles.items():
                version = policy.get("version") if isinstance(policy, dict) else None
                yield ImprovementScope.EFFORT_POLICY, str(role), version, policies

    def _entry(
        self, kind: ImprovementScope, name: str, version: object, path: Path, now: datetime
    ) -> BehaviorVersion:
        if version is None:
            _fail(path, f"missing version{_where(kind, name)}")
        if not isinstance(version, str) or not _VERSION.match(version):
            _fail(path, f"version {version!r} is not a quoted 'MAJOR.MINOR' string")
        return BehaviorVersion(
            kind=kind,
            name=name,
            version=version,
            stage=RolloutStage.DEFAULT,
            content_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            source_path=path.relative_to(self._root).as_posix(),
            introduced_at=now,
        )


class KernelVersionPins(WalkModel):
    """`.ai/project/kernel-versions.yaml`: the behavior version a project pins per artifact."""

    pins: dict[str, str] = Field(description="'<KIND>/<name>' -> 'MAJOR.MINOR'")

    @classmethod
    def from_catalog(cls, catalog: list[BehaviorVersion]) -> Self:
        """Pins every catalogued artifact at its current version."""
        return cls(pins={_key(v): v.version for v in catalog})

    @classmethod
    def load(cls, ai_root: Path) -> Self:
        """The pins under ``ai_root``; empty when the file is absent or is the ``{}`` placeholder.

        Raises:
            ConfigError: The file is not valid YAML or not a valid pin file.
        """
        path = ai_root / PINS_PATH
        if not path.is_file():
            return cls(pins={})
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            return cls.model_validate(data or {"pins": {}})
        except (yaml.YAMLError, ValidationError) as exc:
            msg = f"invalid kernel version pins {path}: {exc}"
            raise ConfigError(msg, detail={"path": str(path)}) from exc

    def write(self, ai_root: Path) -> Path:
        """Write the pins atomically with sorted keys (stable diffs); returns the file path."""
        path = ai_root / PINS_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"pins": dict(sorted(self.pins.items()))}
        text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_bytes(text.encode("utf-8"))
        tmp.replace(path)
        return path

    def validate(self, catalog: list[BehaviorVersion]) -> None:  # type: ignore[override]  # contract name (E02-S04); shadows pydantic v1's deprecated BaseModel.validate classmethod
        """Check the pins against ``catalog``; all problems are collected before raising.

        Raises:
            VersionPinError: Listing pins without catalog entry (``unknown pin: X``), catalog
                entries without pin (``missing pin: X``) and version mismatches
                (``pin X wants A, kernel provides B``), with the guidance to fix the file.
        """
        provided = {_key(v): v.version for v in catalog}
        problems = [f"missing pin: {key}" for key in sorted(provided.keys() - self.pins.keys())]
        problems += [f"unknown pin: {key}" for key in sorted(self.pins.keys() - provided.keys())]
        problems += [
            f"pin {key} wants {wanted}, kernel provides {provided[key]}"
            for key, wanted in sorted(self.pins.items())
            if key in provided and provided[key] != wanted
        ]
        if problems:
            msg = f"kernel version pins do not match ({'; '.join(problems)}); {_GUIDANCE}"
            raise VersionPinError(msg, detail={"problems": problems})


def _key(v: BehaviorVersion) -> str:
    return f"{v.kind.value}/{v.name}"


def _where(kind: ImprovementScope, name: str) -> str:
    return f" (roles.{name})" if kind is ImprovementScope.EFFORT_POLICY else ""


def _yaml_mapping(path: Path) -> JsonDict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        _fail(path, f"invalid YAML: {exc}")
    return data if isinstance(data, dict) else {}


def _front_matter(path: Path) -> JsonDict:
    match = _FRONT_MATTER.match(path.read_text(encoding="utf-8"))
    if match is None:
        return {}
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        _fail(path, f"invalid YAML: {exc}")
    return data if isinstance(data, dict) else {}


def _template_version(path: Path) -> str | None:
    lines = path.read_text(encoding="utf-8").splitlines()
    match = _TEMPLATE_VERSION.match(lines[0]) if lines else None
    return match.group(1) if match else None


def _fail(path: Path, problem: str) -> NoReturn:
    msg = f"{path}: {problem}"
    raise ConfigError(msg, detail={"path": str(path)})
