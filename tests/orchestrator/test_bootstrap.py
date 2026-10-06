import hashlib
import subprocess
from pathlib import Path

import pytest
import yaml

import walk
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_keyring import FakeKeyringBackend
from tests.fakes.fake_subprocess import FakeSubprocessRunner
from tests.integrations.test_preflight import script_environment
from walk.agents import ConstitutionLoader, PolicyLoader
from walk.cli.composition import open_bootstrapper
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.integrations import AsyncioSubprocessRunner, ProductionKit, SubprocessResult
from walk.memory import MemoryDocument, parse_document
from walk.model_router import load_models_config
from walk.orchestrator import BootstrapOptions, BootstrapResult
from walk.orchestrator.bootstrap import NO_COMMIT_SHA
from walk.persistence import Database, MigrationRunner, UnitOfWork
from walk.workflow import Project, ProjectRepository

SRC = Path(walk.__file__).resolve().parent
AGENT_DEFAULTS = SRC / "agents" / "defaults"
BUILTIN_SKILLS = sorted(p.name for p in (SRC / "skills" / "builtin").iterdir() if p.is_dir())
PERMISSIONS = (
    "# Project narrowing of the kernel permission defaults (ADR-0006 D-6).\n"
    "# Rules may only add DENY/REQUIRE_APPROVAL or restate a default ALLOW (E02-S10).\n"
    "rules: []\n"
    "protected_actions: []\n"
)
MVP_DIRS = (
    ".walk",
    ".ai/project",
    ".ai/features",
    ".ai/bugs",
    ".ai/decisions",
    ".ai/handovers",
    ".ai/agents/roles",
    ".ai/agents/skills",
)
MVP_FILES = (
    ".ai/.gitignore",
    ".ai/kernel.db",
    ".ai/project/project.md",
    ".ai/project/constitution.md",
    ".ai/project/environment.yaml",
    ".ai/project/kernel-versions.yaml",
    ".ai/project/work-provider.yaml",
    ".ai/project/production-kit.yaml",
    ".ai/agents/policies.yaml",
    ".ai/agents/models.yaml",
    ".ai/agents/permissions.yaml",
    ".ai/agents/hooks.yaml",
    ".ai/agents/projections.lock.yaml",
)


class ProbeRunner:
    """Scripted preflight probes; every other git command runs for real (HEAD and branch)."""

    def __init__(self, probes: FakeSubprocessRunner) -> None:
        self.probes = probes
        self.real = AsyncioSubprocessRunner()

    async def run(
        self,
        argv: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_s: int = 120,
        input_text: str | None = None,
    ) -> SubprocessResult:
        target = self.real if argv[0] == "git" and argv[1:] != ["--version"] else self.probes
        return await target.run(argv, cwd=cwd, env=env, timeout_s=timeout_s, input_text=input_text)


def _options(repo: Path, **changes: object) -> BootstrapOptions:
    return BootstrapOptions(repo_path=str(repo), project_key="DEMO", name="Demo").model_copy(
        update=changes
    )


async def _bootstrap(
    repo: Path, clock: FakeClock, *, git: str | None = "git version 2.45.0", **changes: object
) -> BootstrapResult:
    options = _options(repo, **changes)
    runner = ProbeRunner(script_environment(FakeSubprocessRunner(), git=git))
    bootstrapper = open_bootstrapper(
        repo, options, runner=runner, keyring_backend=FakeKeyringBackend(), clock=clock
    )
    return await bootstrapper.run(options)


def _with_gdd(repo: Path) -> Path:
    gdd = repo / "GDD"
    gdd.mkdir()
    (gdd / "combat.md").write_text(
        "# Combat\n\nIntro.\n\n```\n# not a heading\n```\n\n## Shotgun\n\n### Spread\n",
        encoding="utf-8",
    )
    return repo


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _project_doc(repo: Path) -> MemoryDocument:
    path = repo / ".ai" / "project" / "project.md"
    return parse_document(Path("project/project.md"), path.read_text(encoding="utf-8"))


async def test_bootstrap_creates_full_ai_tree(tmp_game_repo: Path, fake_clock: FakeClock) -> None:
    repo = _with_gdd(tmp_game_repo)

    result = await _bootstrap(repo, fake_clock)

    for directory in MVP_DIRS:
        assert (repo / directory).is_dir(), directory
    for file in MVP_FILES:
        assert (repo / file).is_file(), file
    roles = sorted(p.name for p in (repo / ".ai" / "agents" / "roles").iterdir())
    assert roles == sorted(p.name for p in AGENT_DEFAULTS.glob("*.md"))
    for role in roles:
        copied = (repo / ".ai" / "agents" / "roles" / role).read_bytes()
        assert copied == (AGENT_DEFAULTS / role).read_bytes()
    assert (repo / ".ai" / "agents" / "hooks.yaml").read_text(encoding="utf-8") == "hooks: []\n"
    assert yaml.safe_load((repo / ".ai" / "project" / "kernel-versions.yaml").read_text()) == {}
    work_provider = yaml.safe_load((repo / ".ai" / "project" / "work-provider.yaml").read_text())
    assert work_provider == {"kind": "local"}
    assert (repo / ".ai" / ".gitignore").read_text(encoding="utf-8").splitlines() == [
        "kernel.db*",
        "kernel.lock",
    ]
    root_ignore = (repo / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert root_ignore == [".walk/", ".ai/kernel.db", "graphify-out/"]
    doc = _project_doc(repo)
    assert doc.sections["Goals"] == "- Combat"
    assert doc.front_matter.related.gdd == ["GDD/combat.md"]
    assert ".ai/agents/permissions.yaml" in result.created_paths
    assert ".gitignore" in result.created_paths
    assert ".ai/project/environment.yaml" not in result.created_paths
    assert result.unchanged_paths == []
    assert result.manifest.tools["git"].version == "2.45.0"
    # The copies are valid project overrides of the kernel defaults.
    ai = repo / ".ai" / "agents"
    ConstitutionLoader(AGENT_DEFAULTS, ai / "roles").load(AgentRole.LEAD_DEV)
    PolicyLoader(AGENT_DEFAULTS / "policies.yaml", ai / "policies.yaml").load(AgentRole.QC)
    load_models_config(SRC / "model_router" / "defaults" / "models.yaml", ai / "models.yaml")


async def test_bootstrap_is_idempotent(tmp_game_repo: Path, fake_clock: FakeClock) -> None:
    repo = _with_gdd(tmp_game_repo)
    first = await _bootstrap(repo, fake_clock)
    files = [repo / p for p in first.created_paths if not p.endswith("/")]
    hashes = {path: _sha(path) for path in files}

    second = await _bootstrap(repo, fake_clock)

    assert second.created_paths == []
    assert sorted(second.unchanged_paths) == sorted(first.created_paths)
    assert {path: _sha(path) for path in files} == hashes


async def test_bootstrap_aborts_on_preflight_failure(
    tmp_game_repo: Path, fake_clock: FakeClock
) -> None:
    with pytest.raises(ConfigError) as info:
        await _bootstrap(tmp_game_repo, fake_clock, git=None)

    assert info.value.detail["missing_components"] == ["git"]
    assert not (tmp_game_repo / ".ai" / "agents").exists()
    assert not (tmp_game_repo / ".ai" / "project" / "project.md").exists()


async def test_bootstrap_writes_production_kit_file(
    tmp_game_repo: Path, fake_clock: FakeClock
) -> None:
    result = await _bootstrap(tmp_game_repo, fake_clock)

    text = (tmp_game_repo / ".ai" / "project" / "production-kit.yaml").read_text(encoding="utf-8")
    kit = ProductionKit.model_validate(yaml.safe_load(text))

    assert kit == result.kit
    assert kit.kit_version == walk.__version__
    assert kit.validated_at == fake_clock.now()
    assert kit.skill_names == BUILTIN_SKILLS
    assert kit.approved_artifact_ids == []
    assert kit.project_constitution_path == ".ai/project/constitution.md"
    assert kit.environment_manifest_path == ".ai/project/environment.yaml"
    assert kit.kernel_versions_path == ".ai/project/kernel-versions.yaml"
    assert kit.hook_config_path == ".ai/agents/hooks.yaml"
    assert kit.agent_instruction_paths == [
        f".ai/agents/roles/{p.name}" for p in sorted(AGENT_DEFAULTS.glob("*.md"))
    ]
    for path in (*kit.agent_instruction_paths, *kit.initial_memory_paths, kit.tool_config_path):
        assert (tmp_game_repo / path).is_file(), path


async def test_bootstrap_inserts_project_row(tmp_game_repo: Path, fake_clock: FakeClock) -> None:
    await _bootstrap(tmp_game_repo, fake_clock, provider="jira", gdd_paths=[])

    db = Database(tmp_game_repo / ".ai" / "kernel.db")
    try:
        rows = db.connect().execute("SELECT key, repo_path, json FROM projects").fetchall()
    finally:
        db.close()
    assert len(rows) == 1
    project = Project.model_validate_json(rows[0]["json"])
    assert rows[0]["key"] == "DEMO"
    assert Path(rows[0]["repo_path"]) == tmp_game_repo.resolve()  # noqa: ASYNC240 - test assertion
    assert project.work_provider == "jira"
    assert project.created_at == fake_clock.now()
    provider = yaml.safe_load(
        (tmp_game_repo / ".ai" / "project" / "work-provider.yaml").read_text()
    )
    assert provider["kind"] == "jira"


@pytest.fixture
def fresh_repo(tmp_path: Path) -> Path:
    """A git repository on ``main`` without any commit."""
    repo = tmp_path / "fresh"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    return repo


async def test_bootstrap_without_commits_stamps_placeholder_head(
    fresh_repo: Path, fake_clock: FakeClock
) -> None:
    repo = fresh_repo

    await _bootstrap(repo, fake_clock)

    doc = _project_doc(repo)
    freshness = doc.front_matter.freshness
    assert freshness is not None
    assert freshness.commit == NO_COMMIT_SHA == "0000000"
    assert freshness.branch == "main"
    assert doc.sections["Goals"] == "- (no GDD provided)"


async def test_bootstrap_writes_empty_permissions_narrowing(
    tmp_game_repo: Path, fake_clock: FakeClock
) -> None:
    await _bootstrap(tmp_game_repo, fake_clock)

    path = tmp_game_repo / ".ai" / "agents" / "permissions.yaml"
    assert path.read_text(encoding="utf-8") == PERMISSIONS
    assert yaml.safe_load(PERMISSIONS) == {"rules": [], "protected_actions": []}


async def test_bootstrap_refuses_database_of_another_project(
    tmp_game_repo: Path, fake_clock: FakeClock
) -> None:
    db = Database(tmp_game_repo / ".ai" / "kernel.db")
    MigrationRunner(db, "project").apply_pending()
    other = Project(key="OTHER", name="Other", repo_path=str(tmp_game_repo))
    async with UnitOfWork(db) as uow:
        await ProjectRepository(db).insert(other, uow)
    db.close()

    with pytest.raises(ConfigError, match="database belongs to project OTHER"):
        await _bootstrap(tmp_game_repo, fake_clock)

    assert not (tmp_game_repo / ".ai" / "agents").exists()
    assert not (tmp_game_repo / ".ai" / "project" / "environment.yaml").exists()


async def test_bootstrap_keeps_the_project_row_of_the_same_key(
    tmp_game_repo: Path, fake_clock: FakeClock
) -> None:
    db = Database(tmp_game_repo / ".ai" / "kernel.db")
    MigrationRunner(db, "project").apply_pending()
    same = Project(key="DEMO", name="Original", repo_path=str(tmp_game_repo))
    async with UnitOfWork(db) as uow:
        await ProjectRepository(db).insert(same, uow)
    db.close()

    await _bootstrap(tmp_game_repo, fake_clock)

    db = Database(tmp_game_repo / ".ai" / "kernel.db")
    try:
        names = [row[0] for row in db.connect().execute("SELECT name FROM projects")]
    finally:
        db.close()
    assert names == ["Original"]


async def test_bootstrap_rejects_missing_gdd_file(
    tmp_game_repo: Path, fake_clock: FakeClock
) -> None:
    with pytest.raises(ConfigError, match="GDD file not found"):
        await _bootstrap(tmp_game_repo, fake_clock, gdd_paths=["GDD/absent.md"])

    assert not (tmp_game_repo / ".ai" / "agents").exists()


async def test_bootstrap_uses_explicit_gdd_paths_and_appends_root_ignore(
    tmp_game_repo: Path, fake_clock: FakeClock
) -> None:
    (tmp_game_repo / "design.md").write_text("# Vision\n## Core loop\n", encoding="utf-8")
    (tmp_game_repo / ".gitignore").write_bytes(b"graphify-out/")  # no trailing newline

    result = await _bootstrap(tmp_game_repo, fake_clock, gdd_paths=["design.md"])

    doc = _project_doc(tmp_game_repo)
    assert doc.sections["Goals"] == "- Vision"
    ignore = (tmp_game_repo / ".gitignore").read_text(encoding="utf-8")
    assert ignore == "graphify-out/\n.walk/\n"
    assert ".gitignore" in result.created_paths


async def test_bootstrap_rejects_an_invalid_production_kit_file(
    tmp_game_repo: Path, fake_clock: FakeClock
) -> None:
    await _bootstrap(tmp_game_repo, fake_clock)
    kit_file = tmp_game_repo / ".ai" / "project" / "production-kit.yaml"
    kit_file.write_text("kit_version: 1\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="invalid production kit"):
        await _bootstrap(tmp_game_repo, fake_clock)


async def test_bootstrap_reports_a_failed_write(
    tmp_game_repo: Path, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_replace = Path.replace

    def refuse(self: Path, target: Path) -> Path:
        if Path(target).parent.name != "roles":  # only the role copies fail
            return real_replace(self, target)
        msg = f"locked: {target}"
        raise PermissionError(msg)

    monkeypatch.setattr(Path, "replace", refuse)

    with pytest.raises(ConfigError, match="cannot write"):
        await _bootstrap(tmp_game_repo, fake_clock)

    leftovers = list((tmp_game_repo / ".ai" / "agents" / "roles").glob(".*.tmp"))
    assert leftovers == []
