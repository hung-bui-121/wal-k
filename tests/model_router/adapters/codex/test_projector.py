import hashlib
from datetime import UTC, datetime
from pathlib import Path

from tests.fakes.fake_clock import FakeClock
from walk.common.enums import LearningScope
from walk.model_router.adapters.codex.projector import (
    AGENTS_MD_END,
    AGENTS_MD_START,
    CodexSkillProjector,
)
from walk.skills import Skill, SkillProjector

AT = datetime(2026, 1, 1, tzinfo=UTC)
BODY = "Commit often.\n"


def _skill() -> Skill:
    return Skill.model_validate(
        {
            "name": "git-hygiene",
            "version": "1.0",
            "description": "Small commits",
            "scope": LearningScope.KERNEL,
            "body_markdown": BODY,
            "source_path": "walk/skills/builtin/git-hygiene/SKILL.md",
        }
    )


def test_projection_targets_agents_md(tmp_path: Path) -> None:
    projector: SkillProjector = CodexSkillProjector(clock=FakeClock(AT))
    skill = _skill()

    projection = projector.project(skill, str(tmp_path))

    assert projector.provider == "codex"
    assert Path(projection.target_path) == tmp_path / "AGENTS.md"
    content = "## Skill: git-hygiene (v1.0)\n\n" + BODY
    assert content.startswith("## Skill: git-hygiene")
    assert projection.content_sha256 == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert projection.generated_from_sha256 == skill.content_sha256
    assert projection.generated_at == AT
    assert projection.skill == "git-hygiene"
    assert projection.provider == "codex"
    assert list(tmp_path.iterdir()) == []
    assert AGENTS_MD_START == "<!-- walk:skills:start -->"
    assert AGENTS_MD_END == "<!-- walk:skills:end -->"


def test_default_projector_uses_system_clock(tmp_path: Path) -> None:
    assert CodexSkillProjector().project(_skill(), str(tmp_path)).generated_at.tzinfo is not None
