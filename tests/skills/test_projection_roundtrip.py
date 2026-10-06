import hashlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

import walk.skills
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_model_adapter import FakeModelAdapter, FakeScript, fake_descriptor
from walk.agents import AgentOutput, AgentOutputStatus
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.integrations import AsyncioSubprocessRunner, GitCliProvider
from walk.model_router.adapters.claude.projector import ClaudeSkillProjector
from walk.model_router.adapters.codex.projector import CodexSkillProjector
from walk.persistence import Database, IdempotencyStore, IdSequenceStore
from walk.runtime import AgentRun, DefaultSandboxManager
from walk.runtime.sandbox import WORKTREES_DIR
from walk.skills import DefaultSkillRegistry, Skill, SkillProjection, SkillProjector
from walk.skills.lockfile import ProjectionLock
from walk.skills.repository import SkillProjectionRepository
from walk.telemetry import DefaultLedgerManager, LedgerRepository
from walk.workflow import Story, StoryContract, WorkItem

AT = datetime(2026, 1, 1, tzinfo=UTC)
BUILTIN = Path(walk.skills.__file__).resolve().parent / "builtin"
RUN_ID = "RUN-01J0000000000000000000000A"
_DONE = AgentOutput(
    status=AgentOutputStatus.COMPLETED, result="done", no_context_change_reason="test"
)


@pytest.fixture
def git(db: Database, tmp_game_repo: Path, fake_clock: FakeClock) -> GitCliProvider:
    ledger = DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), fake_clock)
    return GitCliProvider(
        tmp_game_repo,
        AsyncioSubprocessRunner(),
        ledger,
        IdempotencyStore(db, fake_clock),
        fake_clock,
        project_key="DEMO",
    )


@pytest.fixture
def registry(db: Database, tmp_game_repo: Path, git: GitCliProvider) -> DefaultSkillRegistry:
    async def exclude_path(worktree: str) -> str:
        return await git.git_path(worktree, "info/exclude")

    return DefaultSkillRegistry(
        BUILTIN,
        None,
        {AgentRole.SENIOR_DEV: ["walk-output-contract", "git-hygiene"]},
        db=db,
        ai_root=tmp_game_repo / ".ai",
        exclude_path=exclude_path,
    )


def _projectors() -> list[SkillProjector]:
    clock = FakeClock(AT)
    return [ClaudeSkillProjector(clock=clock), CodexSkillProjector(clock=clock)]


def _hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }


async def test_projection_is_deterministic_for_both_providers(
    registry: DefaultSkillRegistry, tmp_game_repo: Path, db: Database
) -> None:
    skills = registry.load()
    worktree = str(tmp_game_repo)

    first = await registry.project_all(_projectors(), worktree, skills)
    files = _hashes(tmp_game_repo)
    lock = (tmp_game_repo / ".ai" / "agents" / "projections.lock.yaml").read_bytes()
    second = await registry.project_all(_projectors(), worktree, skills)

    assert first == second
    assert _hashes(tmp_game_repo) == files
    assert (tmp_game_repo / ".ai" / "agents" / "projections.lock.yaml").read_bytes() == lock
    assert len(first) == 2 * len(skills)
    entries = ProjectionLock.load(tmp_game_repo / ".ai").projections
    assert {(p.provider, p.skill) for p in entries} == {
        (provider, s.name) for provider in ("claude", "codex") for s in skills
    }
    assert all(not Path(p.target_path).is_absolute() for p in entries)
    claude = Path(worktree) / ".claude" / "skills" / "git-hygiene" / "SKILL.md"
    assert claude.is_file()
    agents_md = (Path(worktree) / "AGENTS.md").read_text(encoding="utf-8")
    assert agents_md.count("### ") == len(skills)
    rows = await SkillProjectionRepository(db).list("codex")
    assert sorted(row.skill for row in rows) == sorted(s.name for s in skills)
    assert len(await SkillProjectionRepository(db).list()) == 2 * len(skills)


async def test_projection_targets_excluded_from_git(
    registry: DefaultSkillRegistry, tmp_game_repo: Path
) -> None:
    skills = registry.load()

    await registry.project_all(_projectors(), str(tmp_game_repo), skills)
    await registry.project_all(_projectors(), str(tmp_game_repo), skills)

    lines = (tmp_game_repo / ".git" / "info" / "exclude").read_text("utf-8").splitlines()
    expected = ["/AGENTS.md", *(f"/.claude/skills/{s.name}/SKILL.md" for s in skills)]
    for entry in expected:
        assert lines.count(entry) == 1, entry
    status = _git_status(tmp_game_repo)
    assert "AGENTS.md" not in status
    assert ".claude" not in status


async def test_lock_keeps_other_providers_and_unchanged_entries(
    registry: DefaultSkillRegistry, tmp_game_repo: Path
) -> None:
    skills = registry.load()
    await registry.project_all(_projectors(), str(tmp_game_repo), skills)
    later: list[SkillProjector] = [
        ClaudeSkillProjector(clock=FakeClock(datetime(2027, 1, 1, tzinfo=UTC)))
    ]

    await registry.project_all(later, str(tmp_game_repo), skills[:1])

    entries = ProjectionLock.load(tmp_game_repo / ".ai").projections
    assert len(entries) == 2 * len(skills)
    assert {entry.generated_at for entry in entries} == {AT}


async def test_project_all_requires_wiring(tmp_path: Path) -> None:
    bare = DefaultSkillRegistry(BUILTIN, None, {})

    with pytest.raises(ConfigError, match="not configured"):
        await bare.project_all(_projectors(), str(tmp_path), bare.load())


async def test_sandbox_create_projects_skills(
    registry: DefaultSkillRegistry, git: GitCliProvider, tmp_game_repo: Path
) -> None:
    adapter = FakeModelAdapter(
        "fake-codex",
        [fake_descriptor("fake-codex/sim", "fake-codex")],
        FakeScript(output=_DONE),
        FakeClock(AT),
    )

    async def project(run: AgentRun, item: WorkItem, worktree: str) -> None:
        del item
        skills = registry.for_role(run.role, [])
        await registry.project_all([adapter.skill_projector()], worktree, skills)

    sandbox = DefaultSandboxManager(tmp_game_repo, git, ["main"], project_skills=project)

    path = Path(await sandbox.create(_run(), _story()))

    assert (path / ".walk" / "fake-skills" / "walk-output-contract.md").is_file()
    assert (path / ".walk" / "fake-skills" / "git-hygiene.md").is_file()
    assert _git_status(path) == ""


async def test_sandbox_create_removes_worktree_on_projection_failure(
    git: GitCliProvider, tmp_game_repo: Path
) -> None:
    class Exploding:
        provider = "boom"

        def project(self, skill: Skill, worktree_path: str) -> SkillProjection:
            msg = f"cannot project {skill.name} into {worktree_path}"
            raise OSError(msg)

        def render(self, skills: list[Skill], worktree_path: str) -> dict[str, bytes]:
            msg = f"cannot render {len(skills)} skills into {worktree_path}"
            raise OSError(msg)

    async def project(run: AgentRun, item: WorkItem, worktree: str) -> None:
        del run, item
        Exploding().render([], worktree)

    sandbox = DefaultSandboxManager(tmp_game_repo, git, ["main"], project_skills=project)

    with pytest.raises(ConfigError, match="skill projection failed"):
        await sandbox.create(_run(), _story())

    assert not (tmp_game_repo / WORKTREES_DIR / RUN_ID).exists()
    assert str((tmp_game_repo / WORKTREES_DIR / RUN_ID).resolve()) not in _git(
        tmp_game_repo, "worktree", "list"
    )


async def test_sandbox_adopt_projects_for_the_continuing_run(
    git: GitCliProvider, tmp_game_repo: Path
) -> None:
    seen: list[str] = []

    async def project(run: AgentRun, item: WorkItem, worktree: str) -> None:
        del item
        seen.append(f"{run.id}:{Path(worktree).name}")

    sandbox = DefaultSandboxManager(tmp_game_repo, git, ["main"], project_skills=project)
    path = await sandbox.create(_run(), _story())
    parent = _run().model_copy(update={"worktree_path": path, "branch": "feat/story-0001-jump"})

    await sandbox.adopt(_run("RUN-01J0000000000000000000000B"), parent, _story())

    assert seen == [f"{RUN_ID}:{RUN_ID}", f"RUN-01J0000000000000000000000B:{RUN_ID}"]


def _run(run_id: str = RUN_ID) -> AgentRun:
    return AgentRun.model_validate(
        {
            "id": run_id,
            "project_key": "DEMO",
            "work_item_id": "STORY-0001",
            "role": AgentRole.SENIOR_DEV,
            "model_id": "fake-codex/sim",
            "provider": "fake-codex",
            "effort": "MEDIUM",
            "purpose": "IMPLEMENT",
            "kernel_instance": "instance-a",
            "started_at": AT,
        }
    )


def _story() -> Story:
    return Story(
        id="STORY-0001",
        project_key="DEMO",
        title="Jump",
        contract=StoryContract(goal="Jump"),
        created_at=AT,
        updated_at=AT,
    )


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


def _git_status(repo: Path) -> str:
    return _git(repo, "status", "--porcelain")
