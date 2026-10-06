"""`.ai/project/environment.yaml`: the §26 `EnvironmentManifest` on disk and its §27 drift.

`IntegrationManager.preflight` owns this file (INTERFACES §1.12); it is configuration YAML,
not a memory document, so it is written here atomically (temp file + rename).
"""

import os
from pathlib import Path
from typing import Final

import yaml
from pydantic import ValidationError

from walk.common.clock import Clock
from walk.common.errors import ConfigError
from walk.integrations.models import ComponentStatus, EnvironmentManifest, ReadinessState

_RELATIVE: Final = Path("project") / "environment.yaml"
_ABSENT: Final = "absent"
_SINGLE: Final = ("unity", "work_provider")
_SECTIONS: Final = (  # EnvironmentManifest field order
    "unity",
    "unity_packages",
    "tools",
    "providers",
    "work_provider",
    "credentials",
    "required_skills",
    "build_targets",
)

_Value = ComponentStatus | ReadinessState | None


class ManifestStore:
    """Reads, writes and compares the project's environment manifest."""

    def __init__(self, ai_root: Path, clock: Clock) -> None:
        """Bind to ``<ai_root>/project/environment.yaml``.

        Args:
            ai_root: The repository's `.ai/` folder.
            clock: Names the temporary file of a write.
        """
        self._ai_root = ai_root
        self._clock = clock

    def path(self) -> Path:
        """``<ai_root>/project/environment.yaml``."""
        return self._ai_root / _RELATIVE

    def read(self) -> EnvironmentManifest | None:
        """The stored manifest, or ``None`` when the file does not exist.

        Raises:
            ConfigError: The file is not valid YAML or not a valid manifest.
        """
        path = self.path()
        if not path.is_file():
            return None
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            return EnvironmentManifest.model_validate(data)
        except (yaml.YAMLError, ValidationError) as exc:
            msg = f"invalid environment manifest {path}: {exc}"
            raise ConfigError(msg, detail={"path": str(path)}) from exc

    def write(self, manifest: EnvironmentManifest) -> Path:
        """Write ``manifest`` atomically (temp file in the same folder, then rename)."""
        path = self.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = self._clock.now().strftime("%Y%m%dT%H%M%S%f")
        tmp = path.with_name(f".{path.name}.{os.getpid()}.{stamp}.tmp")
        text = yaml.safe_dump(manifest.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
        tmp.write_bytes(text.encode("utf-8"))
        tmp.replace(path)
        return path

    def diff(self, previous: EnvironmentManifest, current: EnvironmentManifest) -> list[str]:
        """'<section>.<key>: <old state/version> -> <new state/version>' per changed component.

        Only state and version are compared (details are free text). The single components
        ``unity`` and ``work_provider`` are reported as ``<section>: ...``; a key present on
        one side only reads ``absent`` on the other.
        """
        items: list[str] = []
        pairs: list[tuple[str, _Value, _Value]]
        for section in _SECTIONS:
            if section in _SINGLE:
                pairs = [(section, getattr(previous, section), getattr(current, section))]
            else:
                old: dict[str, _Value] = getattr(previous, section)
                new: dict[str, _Value] = getattr(current, section)
                keys = list(old) + [key for key in new if key not in old]
                pairs = [(f"{section}.{key}", old.get(key), new.get(key)) for key in keys]
            for name, before, after in pairs:
                was, now = _render(before), _render(after)
                if was != now:
                    items.append(f"{name}: {was} -> {now}")
        return items


def _render(value: _Value) -> str:
    if value is None:
        return _ABSENT
    if isinstance(value, ReadinessState):
        return value.value
    return f"{value.state.value} {value.version}" if value.version else value.state.value
