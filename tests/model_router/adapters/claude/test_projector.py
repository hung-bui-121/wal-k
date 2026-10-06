import hashlib
from datetime import UTC, datetime
from pathlib import Path

from tests.fakes.fake_clock import FakeClock
from walk.common.enums import LearningScope
from walk.model_router.adapters.claude.projector import ClaudeSkillProjector
from walk.skills import Skill, SkillProjection, SkillProjector

AT = datetime(2026, 1, 1, tzinfo=UTC)


def _skill() -> Skill:
    return Skill.model_validate(
        {
            "name": "git-hygiene",
            "version": "1.0",
            "description": "Small commits with clear messages",
            "scope": LearningScope.KERNEL,
            "body_markdown": "# Git hygiene\n\nCommit often.\n",
            "source_path": "walk/skills/builtin/git-hygiene/SKILL.md",
        }
    )


def test_projection_is_pure_and_targets_claude_dir(tmp_path: Path) -> None:
    projector: SkillProjector = ClaudeSkillProjector(clock=FakeClock(AT))
    skill = _skill()

    projection = projector.project(skill, str(tmp_path))

    assert isinstance(projection, SkillProjection)
    assert projector.provider == "claude"
    expected = tmp_path / ".claude" / "skills" / "git-hygiene" / "SKILL.md"
    assert Path(projection.target_path) == expected
    assert projection.skill == "git-hygiene"
    assert projection.provider == "claude"
    assert projection.generated_from_sha256 == skill.content_sha256
    assert projection.generated_at == AT
    assert len(projection.content_sha256) == 64
    assert list(tmp_path.iterdir()) == []


def test_projection_hash_covers_front_matter_and_body(tmp_path: Path) -> None:
    projector = ClaudeSkillProjector(clock=FakeClock(AT))
    skill = _skill()
    expected_content = (
        "---\n"
        "name: git-hygiene\n"
        "description: Small commits with clear messages\n"
        "version: '1.0'\n"
        "---\n"
        "\n"
        "# Git hygiene\n\nCommit often.\n"
    )
    digest = hashlib.sha256(expected_content.encode("utf-8")).hexdigest()
    assert projector.project(skill, str(tmp_path)).content_sha256 == digest

    other = skill.model_copy(update={"version": "1.1"})
    assert projector.project(other, str(tmp_path)).content_sha256 != digest


def test_default_projector_uses_system_clock(tmp_path: Path) -> None:
    projection = ClaudeSkillProjector().project(_skill(), str(tmp_path))
    assert projection.generated_at.tzinfo is not None
