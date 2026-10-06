from datetime import UTC, datetime
from pathlib import Path

import pytest

import walk.skills
from tests.cli.conftest import fake_adapters, migrate
from tests.fakes.fake_clock import FakeClock
from walk.cli.composition import KernelOverrides, KernelSettings, build_kernel
from walk.common.enums import LearningScope
from walk.common.errors import ConfigError
from walk.integrations import AsyncioSubprocessRunner, GitCliProvider
from walk.model_router.adapters.claude.projector import ClaudeSkillProjector
from walk.model_router.adapters.codex.projector import CodexSkillProjector
from walk.persistence import Database, IdempotencyStore, IdSequenceStore
from walk.skills import DefaultSkillRegistry, Skill, SkillProjection, SkillProjector
from walk.skills.drift import compute_drift
from walk.skills.lockfile import ProjectionLock
from walk.telemetry import DefaultLedgerManager, LedgerEventKind, LedgerRepository

AT = datetime(2026, 1, 1, tzinfo=UTC)
BUILTIN = Path(walk.skills.__file__).resolve().parent / "builtin"
SHA_A = "a" * 64
SHA_B = "b" * 64


def _skill(name: str, body: str = "body\n") -> Skill:
    return Skill.model_validate(
        {
            "name": name,
            "version": "1.0",
            "description": name,
            "scope": LearningScope.KERNEL,
            "body_markdown": body,
            "source_path": f"skills/{name}/SKILL.md",
        }
    )


def _locked(skill: Skill, target: str, content: str = SHA_A) -> SkillProjection:
    return SkillProjection(
        skill=skill.name,
        provider="claude",
        target_path=target,
        content_sha256=content,
        generated_from_sha256=skill.content_sha256,
        generated_at=AT,
    )


def _key(projection: SkillProjection) -> str:
    return f"{projection.target_path}#{projection.skill}"


def test_drift_ok_when_lock_matches_disk() -> None:
    skills = [_skill("a-skill"), _skill("b-skill")]
    lock = [_locked(s, f".claude/skills/{s.name}/SKILL.md") for s in skills]

    report = compute_drift(skills, lock, {_key(p): SHA_A for p in lock})

    assert report.ok
    assert (report.missing, report.modified, report.orphaned) == ([], [], [])


def test_drift_detects_edited_claude_projection() -> None:
    skill = _skill("git-hygiene")
    lock = [_locked(skill, ".claude/skills/git-hygiene/SKILL.md")]

    report = compute_drift([skill], lock, {_key(lock[0]): SHA_B})

    assert report.modified == ["git-hygiene"]
    assert not report.ok


def test_drift_attributes_codex_edit_to_single_skill(tmp_game_repo: Path) -> None:
    projector = CodexSkillProjector(clock=FakeClock(AT))
    skills = [_skill("a-skill", "alpha\n"), _skill("b-skill", "beta\n")]
    projections = [projector.project(s, str(tmp_game_repo)) for s in skills]
    agents_md = tmp_game_repo / "AGENTS.md"
    section = projector.render_section(skills, str(tmp_game_repo))
    agents_md.write_bytes(section.replace("beta", "BETA").encode("utf-8"))
    lock = [p.model_copy(update={"target_path": "AGENTS.md"}) for p in projections]

    scanned = projector.scan(str(tmp_game_repo))
    report = compute_drift(skills, lock, {_key(p): scanned.get(p.skill) for p in lock})

    assert report.modified == ["b-skill"]
    assert report.missing == []


def test_drift_detects_canonical_change() -> None:
    old = _skill("git-hygiene", "old\n")
    lock = [_locked(old, ".claude/skills/git-hygiene/SKILL.md")]

    report = compute_drift([_skill("git-hygiene", "new\n")], lock, {_key(lock[0]): SHA_A})

    assert report.modified == ["git-hygiene"]


def test_drift_detects_orphaned_projection() -> None:
    kept = _skill("kept")
    gone = _skill("gone")
    lock = [_locked(s, f".claude/skills/{s.name}/SKILL.md") for s in (kept, gone)]
    on_disk: dict[str, str | None] = {_key(p): SHA_A for p in lock}
    on_disk["AGENTS.md#stray"] = SHA_B

    report = compute_drift([kept], lock, on_disk)

    assert report.orphaned == ["gone", "stray"]
    assert report.missing == []


def test_drift_detects_missing_projection() -> None:
    present = _skill("present")
    deleted = _skill("deleted")
    lock = [_locked(s, f".claude/skills/{s.name}/SKILL.md") for s in (present, deleted)]
    on_disk: dict[str, str | None] = {_key(lock[0]): SHA_A, _key(lock[1]): None}

    report = compute_drift([present, deleted, _skill("brand-new")], lock, on_disk)

    assert report.missing == ["brand-new", "deleted"]
    assert report.modified == []


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
def ledger(db: Database, fake_clock: FakeClock) -> DefaultLedgerManager:
    return DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), fake_clock)


@pytest.fixture
def registry(
    db: Database,
    tmp_game_repo: Path,
    git: GitCliProvider,
    ledger: DefaultLedgerManager,
    fake_clock: FakeClock,
) -> DefaultSkillRegistry:
    async def exclude_path(worktree: str) -> str:
        return await git.git_path(worktree, "info/exclude")

    return DefaultSkillRegistry(
        BUILTIN,
        tmp_game_repo / ".ai" / "agents" / "skills",
        {},
        db=db,
        ai_root=tmp_game_repo / ".ai",
        exclude_path=exclude_path,
        ledger=ledger,
        clock=fake_clock,
        project_key="DEMO",
    )


def _projectors() -> list[SkillProjector]:
    clock = FakeClock(AT)
    return [ClaudeSkillProjector(clock=clock), CodexSkillProjector(clock=clock)]


async def test_check_drift_reads_disk_and_never_writes(
    registry: DefaultSkillRegistry, tmp_game_repo: Path
) -> None:
    worktree = tmp_game_repo / ".walk" / "projections" / "all"
    worktree.mkdir(parents=True)

    fresh = await registry.check_drift(_projectors(), str(worktree))
    await registry.project_all(_projectors(), str(worktree), registry.load())
    clean = await registry.check_drift(_projectors(), str(worktree))
    target = worktree / ".claude" / "skills" / "git-hygiene" / "SKILL.md"
    target.write_text("edited by hand\n", encoding="utf-8")
    before = {p: p.read_bytes() for p in worktree.rglob("*") if p.is_file()}
    edited = await registry.check_drift(_projectors(), str(worktree))

    assert sorted(fresh.missing) == sorted(s.name for s in registry.load())
    assert clean.ok
    assert edited.modified == ["git-hygiene"]
    assert {p: p.read_bytes() for p in worktree.rglob("*") if p.is_file()} == before


async def test_regenerate_restores_and_logs(
    registry: DefaultSkillRegistry, tmp_game_repo: Path, ledger: DefaultLedgerManager
) -> None:
    worktree = tmp_game_repo / ".walk" / "projections" / "all"
    worktree.mkdir(parents=True)
    orphan_dir = tmp_game_repo / ".ai" / "agents" / "skills" / "old-skill"
    orphan_dir.mkdir(parents=True)
    (orphan_dir / "SKILL.md").write_text(
        "---\nname: old-skill\nversion: '1.0'\ndescription: d\nscope: PROJECT\n---\nold\n",
        encoding="utf-8",
    )
    await registry.project_all(_projectors(), str(worktree), registry.load())
    original = (worktree / ".claude" / "skills" / "git-hygiene" / "SKILL.md").read_bytes()
    (worktree / ".claude" / "skills" / "git-hygiene" / "SKILL.md").write_text("x", "utf-8")
    agents_md = worktree / "AGENTS.md"
    for path in sorted(orphan_dir.iterdir()):
        path.unlink()
    orphan_dir.rmdir()
    registry.load()
    report = await registry.check_drift(_projectors(), str(worktree))

    regenerated = await registry.regenerate(_projectors(), str(worktree), report)

    assert report.modified == ["git-hygiene"]
    assert report.orphaned == ["old-skill"]
    assert (worktree / ".claude" / "skills" / "git-hygiene" / "SKILL.md").read_bytes() == original
    assert not (worktree / ".claude" / "skills" / "old-skill").exists()
    assert "old-skill" not in agents_md.read_text("utf-8")
    assert (await registry.check_drift(_projectors(), str(worktree))).ok
    lock = ProjectionLock.load(tmp_game_repo / ".ai")
    assert "old-skill" not in {p.skill for p in lock.projections}
    assert {p.skill for p in regenerated} == {s.name for s in registry.load()}
    events = await ledger.query(kinds=[LedgerEventKind.CONTEXT_UPDATED])
    assert len(events) == 1
    assert events[0].payload["skills_drift"]["modified"] == ["git-hygiene"]


async def test_check_drift_and_regenerate_require_wiring(tmp_path: Path) -> None:
    bare = DefaultSkillRegistry(BUILTIN, None, {})
    report = compute_drift([], [], {})

    with pytest.raises(ConfigError, match="not configured"):
        await bare.check_drift(_projectors(), str(tmp_path))
    with pytest.raises(ConfigError, match="not configured"):
        await bare.regenerate(_projectors(), str(tmp_path), report)


@pytest.fixture
def migrated_repo(tmp_game_repo: Path) -> Path:
    migrate(tmp_game_repo)  # runs its own event loop: keep it out of the async test
    return tmp_game_repo


async def test_startup_strict_fails_on_drift(migrated_repo: Path, fake_clock: FakeClock) -> None:
    tmp_game_repo = migrated_repo

    async def no_sleep(seconds: float) -> None:
        del seconds

    overrides = KernelOverrides(
        adapters=fake_adapters(fake_clock),
        clock=fake_clock,
        sleep=no_sleep,
        kernel_instance="test-instance",
        ready_env_keys={"git"},
    )
    strict = build_kernel(KernelSettings(repo_path=tmp_game_repo, strict=True), overrides=overrides)
    try:
        with pytest.raises(ConfigError, match="drift"):
            await strict.orchestrator.run_once()
        started = await strict.ledger.query(kinds=[LedgerEventKind.PROJECT_STARTED])
        assert started == []
    finally:
        await strict.aclose()

    lenient = build_kernel(KernelSettings(repo_path=tmp_game_repo), overrides=overrides)
    try:
        await lenient.orchestrator.run_once()
        drift_events = await lenient.ledger.query(kinds=[LedgerEventKind.CONTEXT_UPDATED])
        assert len(drift_events) == 2  # one regeneration per fake provider
        projected = tmp_game_repo / ".walk" / "projections" / "fake-codex" / ".walk"
        assert (projected / "fake-skills" / "walk-output-contract.md").is_file()
    finally:
        await lenient.aclose()
