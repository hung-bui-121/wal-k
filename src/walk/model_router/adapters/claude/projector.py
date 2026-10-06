"""Claude skill projection (ADR-0007 D-2): `<worktree>/.claude/skills/<name>/SKILL.md`."""

import hashlib
from pathlib import Path
from typing import Final

import yaml

from walk.common.clock import Clock, SystemClock
from walk.skills.models import Skill, SkillProjection

_COPIED_FOLDERS: Final = ("references", "scripts")


class ClaudeSkillProjector:
    """`SkillProjector` for Claude: one skill folder per skill under ``.claude/skills/``."""

    provider = "claude"

    def __init__(self, clock: Clock | None = None) -> None:
        """Stamp projections with ``clock`` (the system clock by default)."""
        self._clock: Clock = clock if clock is not None else SystemClock()

    def project(self, skill: Skill, worktree_path: str) -> SkillProjection:
        """Target path and content hash of ``skill``'s ``SKILL.md``; nothing is written.

        The content is the canonical front matter reduced to ``name`` and ``description``,
        a blank line, then ``skill.body_markdown`` verbatim.
        """
        content = _render(skill).encode("utf-8")
        return SkillProjection(
            skill=skill.name,
            provider=self.provider,
            target_path=str(_skill_dir(worktree_path, skill) / "SKILL.md"),
            content_sha256=hashlib.sha256(content).hexdigest(),
            generated_from_sha256=skill.content_sha256,
            generated_at=self._clock.now(),
        )

    def render(self, skills: list[Skill], worktree_path: str) -> dict[str, bytes]:
        """``SKILL.md`` of every skill plus the files of its ``references/`` and ``scripts/``."""
        files: dict[str, bytes] = {}
        for skill in skills:
            target = _skill_dir(worktree_path, skill)
            files[str(target / "SKILL.md")] = _render(skill).encode("utf-8")
            source = Path(skill.source_path).parent
            for folder in _COPIED_FOLDERS:
                root = source / folder
                if not root.is_dir():
                    continue
                for path in sorted(p for p in root.rglob("*") if p.is_file()):
                    files[str(target / path.relative_to(source))] = path.read_bytes()
        return files

    def scan(self, worktree_path: str) -> dict[str, str]:
        """``.claude/skills/<name>/SKILL.md`` files present → sha256 of their bytes."""
        root = Path(worktree_path) / ".claude" / "skills"
        if not root.is_dir():
            return {}
        return {
            path.parent.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.glob("*/SKILL.md"))
        }


def _skill_dir(worktree_path: str, skill: Skill) -> Path:
    return Path(worktree_path) / ".claude" / "skills" / skill.name


def _render(skill: Skill) -> str:
    front_matter = yaml.safe_dump(
        {"name": skill.name, "description": skill.description},
        sort_keys=False,
        allow_unicode=True,
        width=1_000_000,  # one line per value: stable output whatever the description length
    )
    return f"---\n{front_matter}---\n\n{skill.body_markdown}"
