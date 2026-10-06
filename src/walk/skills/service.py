"""`DefaultSkillRegistry`: kernel built-ins plus project skills (§28-§29; ADR-0007)."""

from collections.abc import Mapping
from pathlib import Path
from typing import Final

from walk.common.enums import LearningScope
from walk.common.errors import ConfigError
from walk.common.ids import SkillName
from walk.common.roles import AgentRole
from walk.skills.errors import SkillLoadError
from walk.skills.loader import discover_skill_dirs, parse_skill_file
from walk.skills.models import DriftReport, Skill, SkillProjection
from walk.skills.protocols import SkillProjector

_SKILL_FILE: Final = "SKILL.md"
_PROJECTIONS: Final = "E02-S06"
_DRIFT: Final = "E02-S07"


class DefaultSkillRegistry:
    """`SkillRegistry` over ``walk/skills/builtin/`` and ``.ai/agents/skills/``."""

    def __init__(
        self,
        builtin_root: Path,
        project_root: Path | None,
        role_defaults: Mapping[AgentRole, list[SkillName]],
    ) -> None:
        """Wire the registry (nothing is read until `load`).

        Args:
            builtin_root: Kernel skills, ``walk/skills/builtin``.
            project_root: ``.ai/agents/skills``; ``None`` or a missing folder = none.
            role_defaults: ``RuntimePolicy.default_skills`` per role.
        """
        self._builtin_root = builtin_root
        self._project_root = project_root
        self._role_defaults = {role: list(names) for role, names in role_defaults.items()}
        self._skills: dict[SkillName, Skill] | None = None

    def load(self) -> list[Skill]:
        """Read built-ins, then project skills; a project skill replaces a built-in by name.

        The result is cached until `load` is called again.

        Raises:
            SkillLoadError: A skill file is invalid, or a project skill claims ``scope: KERNEL``.
        """
        skills: dict[SkillName, Skill] = {}
        for directory in discover_skill_dirs(self._builtin_root):
            skill = parse_skill_file(directory / _SKILL_FILE)
            skills[skill.name] = skill
        if self._project_root is not None:
            for directory in discover_skill_dirs(self._project_root):
                skill = parse_skill_file(directory / _SKILL_FILE)
                if skill.scope is LearningScope.KERNEL:
                    msg = f"{skill.source_path}: project skills cannot claim scope KERNEL"
                    raise SkillLoadError(msg, detail={"path": skill.source_path})
                skills[skill.name] = skill
        self._skills = skills
        return list(skills.values())

    def get(self, name: SkillName) -> Skill:
        """The skill called ``name`` (loads on first use).

        Raises:
            ConfigError: No such skill.
        """
        skill = self._loaded().get(name)
        if skill is None:
            msg = f"unknown skill {name}"
            raise ConfigError(msg, detail={"skill": name})
        return skill

    def for_role(self, role: AgentRole, required: list[SkillName]) -> list[Skill]:
        """``role_defaults[role]`` then ``required``, de-duplicated in that order (§29).

        Raises:
            ConfigError: A name does not resolve; ``detail["missing"]`` lists every such name.
        """
        names = list(dict.fromkeys([*self._role_defaults.get(role, []), *required]))
        skills = self._loaded()
        missing = [name for name in names if name not in skills]
        if missing:
            msg = f"required skills missing for {role.value}: {', '.join(missing)}"
            raise ConfigError(msg, detail={"role": role.value, "missing": missing})
        return [skills[name] for name in names]

    async def project_all(
        self, projectors: list[SkillProjector], worktree_path: str, skills: list[Skill]
    ) -> list[SkillProjection]:
        """Deferred to E02-S06.

        Raises:
            ConfigError: Always.
        """
        del projectors, skills
        msg = f"implemented in {_PROJECTIONS}"
        raise ConfigError(msg, detail={"story": _PROJECTIONS, "worktree": worktree_path})

    async def check_drift(
        self, projectors: list[SkillProjector], worktree_path: str
    ) -> DriftReport:
        """Deferred to E02-S07.

        Raises:
            ConfigError: Always.
        """
        del projectors
        msg = f"implemented in {_DRIFT}"
        raise ConfigError(msg, detail={"story": _DRIFT, "worktree": worktree_path})

    def _loaded(self) -> dict[SkillName, Skill]:
        if self._skills is None:
            return {skill.name: skill for skill in self.load()}
        return self._skills
