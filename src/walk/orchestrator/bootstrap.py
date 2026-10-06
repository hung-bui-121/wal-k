"""`walk bootstrap`: Production Kit generation and `.ai/` initialisation (§24, §25; ADR-0020).

`Bootstrapper` runs the §25 steps in a fixed order. Every step is idempotent: an existing file is
never overwritten, only reported in `BootstrapResult.unchanged_paths`. Markdown documents go
through `MemoryManager.write`; the projection lock through `ProjectionLock.write`; everything
else (verbatim copies of kernel defaults, YAML and ignore files) through an atomic temp-file
rename in `_KitFiles`.
"""

import os
import re
from importlib.resources import files
from pathlib import Path
from typing import Final, Literal

import yaml
from pydantic import Field

from walk.common.clock import Clock
from walk.common.errors import ConfigError
from walk.common.ids import ProjectKey, Sha
from walk.common.models import Actor, WalkModel
from walk.common.roles import AgentRole
from walk.integrations.errors import GitError
from walk.integrations.models import EnvironmentManifest, ProductionKit
from walk.integrations.preflight import REQUIRED_DEFAULT
from walk.integrations.protocols import GitProvider, IntegrationManager
from walk.memory.protocols import MemoryManager
from walk.memory.skeletons import project_constitution_skeleton, project_skeleton
from walk.persistence import Database, MigrationRunner, UnitOfWork
from walk.skills.lockfile import ProjectionLock
from walk.workflow.models import Project
from walk.workflow.repository import ProjectRepository

NO_COMMIT_SHA: Sha = "0000000"
"""Stamped as head on documents written in a repository without commits."""

_AI: Final = ".ai"
_SCRATCH: Final = ".walk"
# ARCHITECTURE §8 [MVP] folders and the Production Kit folders (§24) that start empty; `.ai/` and
# `.ai/project/` are made silently (they hold reported files, and the database opens `.ai/`).
_TREE: Final = (
    ".ai/features",
    ".ai/bugs",
    ".ai/decisions",
    ".ai/handovers",
    ".ai/agents/roles",
    ".ai/agents/skills",
)
_PROJECT_MD: Final = ".ai/project/project.md"
_CONSTITUTION_MD: Final = ".ai/project/constitution.md"
_ENVIRONMENT: Final = ".ai/project/environment.yaml"
_KERNEL_VERSIONS: Final = ".ai/project/kernel-versions.yaml"
_WORK_PROVIDER: Final = ".ai/project/work-provider.yaml"
_PRODUCTION_KIT: Final = ".ai/project/production-kit.yaml"
_ROLES: Final = ".ai/agents/roles"
_HOOKS: Final = ".ai/agents/hooks.yaml"
_PERMISSIONS: Final = ".ai/agents/permissions.yaml"
_LOCK: Final = ".ai/agents/projections.lock.yaml"
_PERMISSIONS_TEXT: Final = (
    "# Project narrowing of the kernel permission defaults (ADR-0006 D-6).\n"
    "# Rules may only add DENY/REQUIRE_APPROVAL or restate a default ALLOW (E02-S10).\n"
    "rules: []\n"
    "protected_actions: []\n"
)
_KIND_LINE: Final = re.compile(r"^kind: local$", re.MULTILINE)
_HEADING: Final = re.compile(r"^#{1,2}\s+\S")
_FENCE: Final = "```"
_GDD_DIR: Final = "GDD"
_USER: Final = Actor(role=AgentRole.USER)


class BootstrapOptions(WalkModel):
    """Arguments of `walk bootstrap` (INTERFACES §6), validated by `cmd_bootstrap`."""

    repo_path: str = Field(description="Game repository root.")
    project_key: ProjectKey = Field(description="Key of the project, e.g. DEMO.")
    name: str = Field(description="Human-readable project name.")
    gdd_paths: list[str] = Field(
        default_factory=list, description="Relative to repo root; default: every *.md under GDD/"
    )
    provider: Literal["local", "jira"] = Field(default="local", description="Work provider kind.")
    unity_path: str | None = Field(default=None, description="Unity editor executable, if any.")
    yes: bool = Field(default=False, description="Skip the confirmation prompt.")


class BootstrapResult(WalkModel):
    """What one bootstrap run did."""

    kit: ProductionKit = Field(description="The Production Kit as written (or found).")
    manifest: EnvironmentManifest = Field(description="The preflight manifest of this run.")
    created_paths: list[str] = Field(
        description="Repo-relative POSIX paths created or extended by this run; folders end in /."
    )
    unchanged_paths: list[str] = Field(
        description="Repo-relative POSIX paths that already existed and were left untouched."
    )


class Bootstrapper:
    """Turns a game repository into a Production Kit (§24, §25).

    Constructed only by `walk.cli.composition.open_bootstrapper` (ADR-0020 D-2).
    """

    def __init__(
        self,
        *,
        integrations: IntegrationManager,
        memory: MemoryManager,
        git: GitProvider,
        database: Database,
        migrations: MigrationRunner,
        projects: ProjectRepository,
        clock: Clock,
        kit_version: str,
    ) -> None:
        """Wire the bootstrapper.

        Args:
            integrations: Runs the §26 preflight and writes `environment.yaml`.
            memory: Writes `project.md` and `constitution.md`.
            git: Supplies HEAD and branch for the document freshness stamps.
            database: The project database `<repo>/.ai/kernel.db`.
            migrations: Brings ``database`` to the latest schema.
            projects: The `projects` table of ``database``.
            clock: Stamps the project row and the kit.
            kit_version: Version recorded in `production-kit.yaml` (the kernel version).
        """
        self._integrations = integrations
        self._memory = memory
        self._git = git
        self._database = database
        self._migrations = migrations
        self._projects = projects
        self._clock = clock
        self._kit_version = kit_version

    async def run(self, options: BootstrapOptions) -> BootstrapResult:
        """Run the §25 steps (E02-S03 Behavior 1); a second run creates nothing.

        Raises:
            ConfigError: A GDD file does not exist or lies outside the repository; the
                database belongs to another project; a required component is MISSING
                (``detail["missing_components"]``, nothing copied yet); or a write failed.
        """
        repo = _resolved(options.repo_path)
        gdd_paths = _gdd_paths(repo, options.gdd_paths)
        kit = _KitFiles(repo)
        (repo / _AI).mkdir(exist_ok=True)  # (a)
        kit.folder(_SCRATCH)
        self._migrations.apply_pending()  # (b)
        known = await self._known_project(options.project_key)
        manifest = await self._integrations.preflight(list(REQUIRED_DEFAULT))  # (c)
        _copy_defaults(kit)  # (d)
        kit.text(_WORK_PROVIDER, _work_provider(options.provider))  # (e)
        await self._write_documents(kit, repo, options, gdd_paths)  # (f)
        kit.text(_KERNEL_VERSIONS, "{}\n")  # (g)
        kit.text(f"{_AI}/.gitignore", _resource("integrations", "ai.gitignore"))  # (h)
        kit.append_lines(".gitignore", _resource("integrations", "root.gitignore.fragment"))
        if not known:  # (i)
            await self._insert_project(repo, options, gdd_paths)
        production_kit = self._production_kit(kit)  # (j)
        return BootstrapResult(
            kit=production_kit,
            manifest=manifest,
            created_paths=kit.created,
            unchanged_paths=kit.unchanged,
        )

    async def _known_project(self, key: ProjectKey) -> bool:
        """Whether the database already holds ``key`` (Behavior 10: one project per database).

        Raises:
            ConfigError: The database belongs to another project.
        """
        keys = [project.key for project in await self._projects.list_where(order_by="key")]
        foreign = [other for other in keys if other != key]
        if foreign:
            msg = f"database belongs to project {foreign[0]}"
            raise ConfigError(msg, detail={"db": str(self._database.path), "projects": keys})
        return key in keys

    async def _write_documents(
        self, kit: "_KitFiles", repo: Path, options: BootstrapOptions, gdd_paths: list[str]
    ) -> None:
        """`project.md` and `constitution.md` through `MemoryManager.write` (Behavior 1 f)."""
        now = self._clock.now()
        documents = {
            _PROJECT_MD: lambda: project_skeleton(
                options.project_key,
                options.name,
                gdd_paths,
                _gdd_headings(repo, gdd_paths),
                _USER,
                now,
            ),
            _CONSTITUTION_MD: lambda: project_constitution_skeleton(
                options.project_key, options.name, _USER, now
            ),
        }
        missing = [path for path in documents if not kit.claim(path)]
        if not missing:
            return
        head, branch = await self._head_and_branch(repo)
        for path in missing:
            await self._memory.write(documents[path](), actor=_USER, head=head, branch=branch)

    async def _head_and_branch(self, repo: Path) -> tuple[Sha, str]:
        """HEAD and branch, or `NO_COMMIT_SHA` and the default branch without commits."""
        try:
            return await self._git.head(str(repo)), await self._git.current_branch(str(repo))
        except GitError:
            return NO_COMMIT_SHA, str(Project.model_fields["default_branch"].default)

    async def _insert_project(
        self, repo: Path, options: BootstrapOptions, gdd_paths: list[str]
    ) -> None:
        project = Project(
            key=options.project_key,
            name=options.name,
            repo_path=str(repo),
            gdd_paths=gdd_paths,
            work_provider=options.provider,
            created_at=self._clock.now(),
        )
        async with UnitOfWork(self._database) as uow:
            await self._projects.insert(project, uow)

    def _production_kit(self, kit: "_KitFiles") -> ProductionKit:
        """`production-kit.yaml`: the existing kit when present, else a new one (Behavior 6)."""
        path = kit.repo / _PRODUCTION_KIT
        if path.is_file():
            kit.unchanged.append(_PRODUCTION_KIT)
            return _load_kit(path)
        roles = sorted(p.name for p in (kit.repo / _ROLES).glob("*.md"))
        production_kit = ProductionKit(
            project_constitution_path=_CONSTITUTION_MD,
            project_constraints_path=f"{_PROJECT_MD}#technical-constraints",
            agent_instruction_paths=[f"{_ROLES}/{name}" for name in roles],
            skill_names=_builtin_skill_names(),
            hook_config_path=_HOOKS,
            approved_artifact_ids=[],
            tool_config_path=_PERMISSIONS,
            environment_manifest_path=_ENVIRONMENT,
            initial_memory_paths=[_PROJECT_MD, _KERNEL_VERSIONS],
            kernel_versions_path=_KERNEL_VERSIONS,
            kit_version=self._kit_version,
            validated_at=self._clock.now(),
        )
        data = production_kit.model_dump(mode="json")
        kit.text(_PRODUCTION_KIT, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
        return production_kit


class _KitFiles:
    """Creates kit files without overwriting, recording created and unchanged paths."""

    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self.created: list[str] = []
        self.unchanged: list[str] = []

    def claim(self, relative: str) -> bool:
        """Record ``relative``; True when it already exists (the caller must not write it)."""
        if (self.repo / relative).exists():
            self.unchanged.append(relative)
            return True
        self.created.append(relative)
        return False

    def folder(self, relative: str) -> None:
        if (self.repo / relative).is_dir():
            self.unchanged.append(f"{relative}/")
            return
        (self.repo / relative).mkdir(parents=True, exist_ok=True)
        self.created.append(f"{relative}/")

    def text(self, relative: str, content: str) -> None:
        self.data(relative, content.encode("utf-8"))

    def data(self, relative: str, content: bytes) -> None:
        if not self.claim(relative):
            _atomic_write(self.repo / relative, content)

    def lock(self, relative: str) -> None:
        if not self.claim(relative):
            ProjectionLock().write(self.repo / _AI)

    def append_lines(self, relative: str, lines: str) -> None:
        """Append each line of ``lines`` that ``relative`` lacks (the file is created if absent)."""
        path = self.repo / relative
        current = path.read_text(encoding="utf-8") if path.is_file() else ""
        present = set(current.splitlines())
        absent = [line for line in lines.splitlines() if line and line not in present]
        if not absent:
            self.unchanged.append(relative)
            return
        prefix = current if not current or current.endswith("\n") else f"{current}\n"
        _atomic_write(path, (prefix + "".join(f"{line}\n" for line in absent)).encode("utf-8"))
        self.created.append(relative)


def _copy_defaults(kit: _KitFiles) -> None:
    """Step (d): the kit folders, kernel defaults copied verbatim, empty configuration files."""
    for folder in _TREE:
        kit.folder(folder)
    agent_defaults = files("walk.agents") / "defaults"
    for role in sorted(agent_defaults.iterdir(), key=lambda entry: entry.name):
        if role.name.endswith(".md"):
            kit.data(f"{_ROLES}/{role.name}", role.read_bytes())
    kit.data(".ai/agents/policies.yaml", (agent_defaults / "policies.yaml").read_bytes())
    kit.data(
        ".ai/agents/models.yaml", (files("walk.model_router.defaults") / "models.yaml").read_bytes()
    )
    kit.text(_PERMISSIONS, _PERMISSIONS_TEXT)
    kit.text(_HOOKS, "hooks: []\n")
    kit.lock(_LOCK)


def _work_provider(provider: str) -> str:
    """The `work-provider.yaml` template with ``kind`` set to ``provider``."""
    template = _resource("integrations", "work-provider.yaml")
    return _KIND_LINE.sub(f"kind: {provider}", template, count=1)


def _resource(package: str, name: str) -> str:
    return (files(f"walk.{package}") / "defaults" / name).read_text(encoding="utf-8")


def _builtin_skill_names() -> list[str]:
    builtin = files("walk.skills") / "builtin"
    return sorted(entry.name for entry in builtin.iterdir() if entry.is_dir())


def _resolved(path: str) -> Path:
    return Path(path).resolve()


def _gdd_paths(repo: Path, given: list[str]) -> list[str]:
    """Repo-relative POSIX GDD paths: ``given``, else every ``*.md`` under ``GDD/`` (Behavior 5).

    Raises:
        ConfigError: A given path is not a file inside the repository.
    """
    if not given:
        folder = repo / _GDD_DIR
        found = sorted(folder.rglob("*.md")) if folder.is_dir() else []
        return [path.relative_to(repo).as_posix() for path in found if path.is_file()]
    paths: list[str] = []
    for entry in given:
        path = (repo / entry).resolve()
        if not path.is_file() or not path.is_relative_to(repo):
            msg = f"GDD file not found in the repository: {entry}"
            raise ConfigError(msg, detail={"gdd": entry, "repo": str(repo)})
        paths.append(path.relative_to(repo).as_posix())
    return paths


def _gdd_headings(repo: Path, gdd_paths: list[str]) -> list[str]:
    """H1/H2 heading lines of the GDD files in reading order; fenced code is skipped."""
    headings: list[str] = []
    for relative in gdd_paths:
        fenced = False
        for line in (repo / relative).read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith(_FENCE):
                fenced = not fenced
            elif not fenced and _HEADING.match(line):
                headings.append(line.strip())
    return headings


def _load_kit(path: Path) -> ProductionKit:
    try:
        return ProductionKit.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (yaml.YAMLError, ValueError) as exc:
        msg = f"invalid production kit {path}: {exc}"
        raise ConfigError(msg, detail={"path": str(path)}) from exc


def _atomic_write(path: Path, content: bytes) -> None:
    """Write ``content`` through a temp file in the same folder, then rename (CONVENTIONS §2)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_bytes(content)
        tmp.replace(path)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        msg = f"cannot write {path}: {exc}"
        raise ConfigError(msg, detail={"path": str(path)}) from exc
