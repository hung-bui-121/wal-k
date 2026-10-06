"""Codex skill projection (ADR-0007 D-2): a managed section of `<worktree>/AGENTS.md`.

Each skill is one ``### <name> (v<version>)`` sub-section between `AGENTS_MD_START` and
`AGENTS_MD_END`. A body larger than `INLINE_LIMIT_BYTES` is linked to
``.walk/skills/<name>/SKILL.md`` instead of inlined. Text outside the markers is kept.
"""

import hashlib
from pathlib import Path
from typing import Final

import yaml

from walk.common.clock import Clock, SystemClock
from walk.skills.models import Skill, SkillProjection

AGENTS_MD_START: Final = "<!-- walk:skills:start -->"
AGENTS_MD_END: Final = "<!-- walk:skills:end -->"
INLINE_LIMIT_BYTES: Final = 4096
_AGENTS_MD: Final = "AGENTS.md"
_HEADER: Final = (
    "## Skills\n\nManaged by WAL-K from the canonical skills; edits here are overwritten.\n"
)


class CodexSkillProjector:
    """`SkillProjector` for Codex: one managed section in ``AGENTS.md``."""

    provider = "codex"

    def __init__(self, clock: Clock | None = None) -> None:
        """Stamp projections with ``clock`` (the system clock by default)."""
        self._clock: Clock = clock if clock is not None else SystemClock()

    def project(self, skill: Skill, worktree_path: str) -> SkillProjection:
        """Target ``<worktree>/AGENTS.md``; the hash covers the skill's own sub-section text.

        Nothing is written.
        """
        entry = _entry(skill).encode("utf-8")
        return SkillProjection(
            skill=skill.name,
            provider=self.provider,
            target_path=str(Path(worktree_path) / _AGENTS_MD),
            content_sha256=hashlib.sha256(entry).hexdigest(),
            generated_from_sha256=skill.content_sha256,
            generated_at=self._clock.now(),
        )

    def render_section(self, skills: list[Skill], worktree_path: str) -> str:
        """The full managed section, markers included, ending with a newline."""
        del worktree_path  # the section text does not depend on where it is written
        entries = "\n".join(_entry(skill) for skill in skills)
        return f"{AGENTS_MD_START}\n{_HEADER}\n{entries}{AGENTS_MD_END}\n"

    def render(self, skills: list[Skill], worktree_path: str) -> dict[str, bytes]:
        """``AGENTS.md`` with the section merged in, plus one file per linked (large) skill.

        An existing ``AGENTS.md`` keeps everything before its first start marker and after its
        last end marker byte for byte; without markers the section is appended.
        """
        target = Path(worktree_path) / _AGENTS_MD
        section = self.render_section(skills, worktree_path).encode("utf-8")
        files = {str(target): _merge(target, section)}
        for skill in skills:
            if not _inline(skill):
                linked = Path(worktree_path) / ".walk" / "skills" / skill.name / "SKILL.md"
                files[str(linked)] = _linked_file(skill).encode("utf-8")
        return files


def _inline(skill: Skill) -> bool:
    return len(skill.body_markdown.encode("utf-8")) <= INLINE_LIMIT_BYTES


def _entry(skill: Skill) -> str:
    body = skill.body_markdown if _inline(skill) else f"See .walk/skills/{skill.name}/SKILL.md\n"
    if not body.endswith("\n"):
        body += "\n"
    return f"### {skill.name} (v{skill.version})\n\n{skill.description}\n\n{body}"


def _merge(target: Path, section: bytes) -> bytes:
    if not target.is_file():
        return section
    existing = target.read_bytes()
    start, end = AGENTS_MD_START.encode("utf-8"), AGENTS_MD_END.encode("utf-8")
    first, last = existing.find(start), existing.rfind(end)
    if first != -1 and last > first:
        after = existing[last + len(end) :]
        after = after.removeprefix(b"\r\n").removeprefix(b"\n")
        return existing[:first] + section + after
    separator = b"\n" if existing.endswith(b"\n") else b"\n\n"
    return existing + separator + section if existing else section


def _linked_file(skill: Skill) -> str:
    front_matter = yaml.safe_dump(
        {"name": skill.name, "description": skill.description, "version": skill.version},
        sort_keys=False,
        allow_unicode=True,
        width=1_000_000,
    )
    return f"---\n{front_matter}---\n\n{skill.body_markdown}"
