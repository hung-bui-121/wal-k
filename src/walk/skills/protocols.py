"""Skill protocols (INTERFACES §1.11); `SkillRegistry` is implemented in E02-S05."""

from typing import Protocol

from walk.common.ids import SkillName
from walk.common.roles import AgentRole
from walk.skills.models import DriftReport, Skill, SkillProjection


class SkillProjector(Protocol):
    """Implemented by each ModelAdapter (ADR-0007)."""

    provider: str

    def project(self, skill: Skill, worktree_path: str) -> SkillProjection:
        """Pure: compute target path + content for this provider (no write)."""
        ...


class SkillRegistry(Protocol):
    """§28-§29. Hosted by walk.skills."""

    def load(self) -> list[Skill]:
        """Kernel built-ins and project skills; project wins on name clash.

        Built-ins: `walk/skills/builtin/*/SKILL.md`; project: `.ai/agents/skills/*/SKILL.md`.
        """
        ...

    def get(self, name: SkillName) -> Skill:
        """The skill called ``name``."""
        ...

    def for_role(self, role: AgentRole, required: list[SkillName]) -> list[Skill]:
        """Role defaults plus ``required``; a missing required skill → ConfigError (§29)."""
        ...

    async def project_all(
        self, projectors: list[SkillProjector], worktree_path: str, skills: list[Skill]
    ) -> list[SkillProjection]:
        """Write projections into the worktree.

        Records skill_projections rows and `.ai/agents/projections.lock.yaml`.
        """
        ...

    async def check_drift(
        self, projectors: list[SkillProjector], worktree_path: str
    ) -> DriftReport:
        """Compare on-disk projection hashes to lock.

        Modified = someone edited a projection directly.
        """
        ...
