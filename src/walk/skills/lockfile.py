"""`.ai/agents/projections.lock.yaml`: the projections each provider should have (ADR-0007).

`SkillRegistry.project_all` is the designated writer of this file (INTERFACES §1.11). Target
paths are stored relative to the projected worktree, so the lock does not change from one run
worktree to the next.
"""

import os
from pathlib import Path
from typing import Final, Self

import yaml
from pydantic import Field, ValidationError

from walk.common.errors import ConfigError
from walk.common.models import WalkModel
from walk.skills.models import SkillProjection

LOCK_PATH: Final[str] = "agents/projections.lock.yaml"
"""Path of the lock file relative to `.ai/`."""


class ProjectionLock(WalkModel):
    """The locked projections, at most one entry per (provider, skill, target path)."""

    projections: list[SkillProjection] = Field(
        default_factory=list, description="Locked projections, target paths worktree-relative."
    )

    @classmethod
    def load(cls, ai_root: Path) -> Self:
        """The lock under ``ai_root``; empty when the file does not exist.

        Raises:
            ConfigError: The file is not valid YAML or not a valid lock.
        """
        path = ai_root / LOCK_PATH
        if not path.is_file():
            return cls()
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return cls.model_validate(data)
        except (yaml.YAMLError, ValidationError) as exc:
            msg = f"invalid projection lock {path}: {exc}"
            raise ConfigError(msg, detail={"path": str(path)}) from exc

    def write(self, ai_root: Path) -> Path:
        """Write the lock atomically, entries sorted by provider, skill and target path."""
        path = ai_root / LOCK_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(self.projections, key=lambda p: (p.provider, p.skill, p.target_path))
        data = {"projections": [p.model_dump(mode="json") for p in ordered]}
        text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_bytes(text.encode("utf-8"))
        tmp.replace(path)
        return path

    def for_provider(self, provider: str) -> list[SkillProjection]:
        """The entries of ``provider``, sorted by skill name."""
        return sorted(
            (p for p in self.projections if p.provider == provider), key=lambda p: p.skill
        )
