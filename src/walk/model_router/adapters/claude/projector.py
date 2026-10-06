"""Claude skill projection (ADR-0007): `<worktree>/.claude/skills/<name>/SKILL.md`."""

import hashlib
from pathlib import Path

import yaml

from walk.common.clock import Clock, SystemClock
from walk.skills.models import Skill, SkillProjection


class ClaudeSkillProjector:
    """Pure `SkillProjector` for Claude; E02-S06 writes the projected files."""

    provider = "claude"

    def __init__(self, clock: Clock | None = None) -> None:
        """Stamp projections with ``clock`` (the system clock by default)."""
        self._clock: Clock = clock if clock is not None else SystemClock()

    def project(self, skill: Skill, worktree_path: str) -> SkillProjection:
        """Target path and content hash of ``skill`` for Claude; nothing is written.

        The content is YAML front matter ``{name, description, version}`` followed by a blank
        line and ``skill.body_markdown``.
        """
        target = Path(worktree_path) / ".claude" / "skills" / skill.name / "SKILL.md"
        content = _render(skill)
        return SkillProjection(
            skill=skill.name,
            provider=self.provider,
            target_path=str(target),
            content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            generated_from_sha256=skill.content_sha256,
            generated_at=self._clock.now(),
        )


def _render(skill: Skill) -> str:
    front_matter = yaml.safe_dump(
        {"name": skill.name, "description": skill.description, "version": skill.version},
        sort_keys=False,
        allow_unicode=True,
    )
    return f"---\n{front_matter}---\n\n{skill.body_markdown}"
