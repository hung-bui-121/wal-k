"""Codex skill projection (ADR-0007): a section of the managed block in `<worktree>/AGENTS.md`."""

import hashlib
from pathlib import Path
from typing import Final

from walk.common.clock import Clock, SystemClock
from walk.skills.models import Skill, SkillProjection

AGENTS_MD_START: Final = "<!-- walk:skills:start -->"
AGENTS_MD_END: Final = "<!-- walk:skills:end -->"


class CodexSkillProjector:
    """Pure `SkillProjector` for Codex; E02-S06 merges the sections between the markers."""

    provider = "codex"

    def __init__(self, clock: Clock | None = None) -> None:
        """Stamp projections with ``clock`` (the system clock by default)."""
        self._clock: Clock = clock if clock is not None else SystemClock()

    def project(self, skill: Skill, worktree_path: str) -> SkillProjection:
        """Target `<worktree>/AGENTS.md` and the hash of ``## Skill: <name> (v<version>)`` + body.

        Nothing is written.
        """
        content = f"## Skill: {skill.name} (v{skill.version})\n\n{skill.body_markdown}"
        return SkillProjection(
            skill=skill.name,
            provider=self.provider,
            target_path=str(Path(worktree_path) / "AGENTS.md"),
            content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            generated_from_sha256=skill.content_sha256,
            generated_at=self._clock.now(),
        )
