"""`DefaultSkillRegistry`: kernel built-ins plus project skills (§28-§29; ADR-0007)."""

import os
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Final

from walk.common.enums import LearningScope
from walk.common.errors import ConfigError
from walk.common.ids import SkillName
from walk.common.roles import AgentRole
from walk.persistence import Database, UnitOfWork
from walk.skills.errors import SkillLoadError
from walk.skills.loader import discover_skill_dirs, parse_skill_file
from walk.skills.lockfile import LOCK_PATH, ProjectionLock
from walk.skills.models import DriftReport, Skill, SkillProjection
from walk.skills.protocols import SkillProjector
from walk.skills.repository import SkillProjectionRepository

_SKILL_FILE: Final = "SKILL.md"
_DRIFT: Final = "E02-S07"
_NOT_CONFIGURED: Final = (
    "skill projection is not configured (database, .ai root and git exclude resolver)"
)

ExcludePath = Callable[[str], Awaitable[str]]
"""Absolute ``info/exclude`` file of a worktree (``GitProvider.git_path``, E02-S06)."""


class DefaultSkillRegistry:
    """`SkillRegistry` over ``walk/skills/builtin/`` and ``.ai/agents/skills/``."""

    def __init__(
        self,
        builtin_root: Path,
        project_root: Path | None,
        role_defaults: Mapping[AgentRole, list[SkillName]],
        *,
        db: Database | None = None,
        ai_root: Path | None = None,
        exclude_path: ExcludePath | None = None,
    ) -> None:
        """Wire the registry (nothing is read until `load`).

        Args:
            builtin_root: Kernel skills, ``walk/skills/builtin``.
            project_root: ``.ai/agents/skills``; ``None`` or a missing folder = none.
            role_defaults: ``RuntimePolicy.default_skills`` per role.
            db: ``skill_projections`` rows (needed by `project_all`).
            ai_root: `.ai/` folder holding the projection lock (needed by `project_all`).
            exclude_path: Resolves a worktree's ``info/exclude`` through git (needed by
                `project_all`); `walk.skills` may not import `GitProvider` (ARCHITECTURE §2.2).
        """
        self._builtin_root = builtin_root
        self._project_root = project_root
        self._role_defaults = {role: list(names) for role, names in role_defaults.items()}
        self._db = db
        self._ai_root = ai_root
        self._exclude_path = exclude_path
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
        """Write every projector's projection of ``skills`` into ``worktree_path``.

        Each file is written atomically; every written path is appended once to the worktree's
        ``info/exclude`` (resolved through git); the projections are upserted into
        ``skill_projections`` (absolute targets) and merged into the lock (worktree-relative
        targets; an unchanged entry keeps its ``generated_at`` so the lock only changes when a
        projection does). Re-running with the same skills writes identical files.

        Raises:
            ConfigError: The registry was built without ``db``, ``ai_root`` or
                ``exclude_path``, or the lock file is invalid.
        """
        if self._db is None or self._ai_root is None or self._exclude_path is None:
            raise ConfigError(_NOT_CONFIGURED, detail={"worktree": worktree_path})
        worktree = Path(worktree_path)
        projections: list[SkillProjection] = []
        written: list[Path] = []
        for projector in projectors:
            for target, content in projector.render(skills, worktree_path).items():
                _atomic_write(Path(target), content)
                written.append(Path(target))
            projections.extend(projector.project(skill, worktree_path) for skill in skills)
        _exclude(Path(await self._exclude_path(worktree_path)), worktree, written)
        async with UnitOfWork(self._db) as uow:
            await SkillProjectionRepository(self._db).upsert(uow, projections)
        _merge_lock(self._ai_root, worktree, projections)
        return projections

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


def _atomic_write(target: Path, content: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    tmp.write_bytes(content)
    tmp.replace(target)


def _exclude(exclude_file: Path, worktree: Path, written: list[Path]) -> None:
    """Append ``/<worktree-relative path>`` for each written file not listed yet."""
    present = (
        exclude_file.read_text(encoding="utf-8").splitlines() if exclude_file.is_file() else []
    )
    wanted = [f"/{_relative(path, worktree)}" for path in written]
    missing = [line for line in dict.fromkeys(wanted) if line not in present]
    if not missing:
        return
    text = exclude_file.read_text(encoding="utf-8") if exclude_file.is_file() else ""
    if text and not text.endswith("\n"):
        text += "\n"
    _atomic_write(exclude_file, (text + "\n".join(missing) + "\n").encode("utf-8"))


def _merge_lock(ai_root: Path, worktree: Path, projections: list[SkillProjection]) -> None:
    lock = ProjectionLock.load(ai_root)
    entries = {(p.provider, p.skill, p.target_path): p for p in lock.projections}
    changed = False
    for projection in projections:
        relative = projection.model_copy(
            update={"target_path": _relative(Path(projection.target_path), worktree)}
        )
        key = (relative.provider, relative.skill, relative.target_path)
        current = entries.get(key)
        if current is not None and (
            current.content_sha256,
            current.generated_from_sha256,
        ) == (relative.content_sha256, relative.generated_from_sha256):
            continue
        entries[key] = relative
        changed = True
    if changed or not (ai_root / LOCK_PATH).is_file():
        ProjectionLock(projections=list(entries.values())).write(ai_root)


def _relative(path: Path, worktree: Path) -> str:
    return path.resolve().relative_to(worktree.resolve()).as_posix()
