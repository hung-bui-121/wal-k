import hashlib
from datetime import UTC, datetime
from pathlib import Path

from tests.fakes.fake_clock import FakeClock
from walk.common.enums import LearningScope
from walk.model_router.adapters.claude.projector import ClaudeSkillProjector
from walk.skills import Skill, SkillProjection, SkillProjector

AT = datetime(2026, 1, 1, tzinfo=UTC)


def _skill(source: Path | None = None, body: str = "# Git hygiene\n\nCommit often.\n") -> Skill:
    return Skill.model_validate(
        {
            "name": "git-hygiene",
            "version": "1.0",
            "description": "Small commits with clear messages",
            "scope": LearningScope.KERNEL,
            "body_markdown": body,
            "source_path": str(source or Path("walk/skills/builtin/git-hygiene/SKILL.md")),
        }
    )


def test_claude_projection_target_and_content(tmp_path: Path) -> None:
    projector: SkillProjector = ClaudeSkillProjector(clock=FakeClock(AT))
    skill = _skill(body="# Git hygiene\n\n" + "x" * 1024 + "\n")
    expected = tmp_path / ".claude" / "skills" / "git-hygiene" / "SKILL.md"

    projection = projector.project(skill, str(tmp_path))
    files = projector.render([skill], str(tmp_path))

    assert isinstance(projection, SkillProjection)
    assert projector.provider == "claude"
    assert Path(projection.target_path) == expected
    content = files[str(expected)].decode("utf-8")
    assert content.startswith(
        "---\nname: git-hygiene\ndescription: Small commits with clear messages\n---\n\n"
    )
    assert content.endswith(skill.body_markdown)
    assert "version" not in content.split("---")[1]
    assert projection.content_sha256 == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert projection.generated_from_sha256 == skill.content_sha256
    assert projection.generated_at == AT
    assert list(tmp_path.iterdir()) == []


def test_claude_render_copies_references_and_scripts(tmp_path: Path) -> None:
    source = tmp_path / "skills" / "git-hygiene"
    (source / "references").mkdir(parents=True)
    (source / "scripts" / "nested").mkdir(parents=True)
    (source / "SKILL.md").write_text("x", encoding="utf-8")
    (source / "references" / "guide.md").write_bytes(b"guide")
    (source / "scripts" / "nested" / "run.sh").write_bytes(b"#!/bin/sh\n")
    (source / "notes.txt").write_bytes(b"not copied")
    worktree = tmp_path / "wt"

    files = ClaudeSkillProjector(clock=FakeClock(AT)).render(
        [_skill(source / "SKILL.md")], str(worktree)
    )

    target = worktree / ".claude" / "skills" / "git-hygiene"
    assert files[str(target / "references" / "guide.md")] == b"guide"
    assert files[str(target / "scripts" / "nested" / "run.sh")] == b"#!/bin/sh\n"
    assert str(target / "notes.txt") not in files
    assert len(files) == 3


def test_default_projector_uses_system_clock(tmp_path: Path) -> None:
    projection = ClaudeSkillProjector().project(_skill(), str(tmp_path))
    assert projection.generated_at.tzinfo is not None
