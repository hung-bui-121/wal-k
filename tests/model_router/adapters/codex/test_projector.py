import hashlib
from datetime import UTC, datetime
from pathlib import Path

from tests.fakes.fake_clock import FakeClock
from walk.common.enums import LearningScope
from walk.model_router.adapters.codex.projector import (
    AGENTS_MD_END,
    AGENTS_MD_START,
    INLINE_LIMIT_BYTES,
    CodexSkillProjector,
)
from walk.skills import Skill, SkillProjector

AT = datetime(2026, 1, 1, tzinfo=UTC)
BODY = "Commit often.\n"


def _skill(name: str = "git-hygiene", body: str = BODY) -> Skill:
    return Skill.model_validate(
        {
            "name": name,
            "version": "1.0",
            "description": f"About {name}",
            "scope": LearningScope.KERNEL,
            "body_markdown": body,
            "source_path": f"walk/skills/builtin/{name}/SKILL.md",
        }
    )


def test_projection_targets_agents_md_and_hashes_the_sub_section(tmp_path: Path) -> None:
    projector: SkillProjector = CodexSkillProjector(clock=FakeClock(AT))
    skill = _skill()

    projection = projector.project(skill, str(tmp_path))

    assert projector.provider == "codex"
    assert Path(projection.target_path) == tmp_path / "AGENTS.md"
    entry = "### git-hygiene (v1.0)\n\nAbout git-hygiene\n\n" + BODY
    assert projection.content_sha256 == hashlib.sha256(entry.encode("utf-8")).hexdigest()
    assert projection.generated_from_sha256 == skill.content_sha256
    assert projection.generated_at == AT
    assert list(tmp_path.iterdir()) == []
    assert AGENTS_MD_START == "<!-- walk:skills:start -->"
    assert AGENTS_MD_END == "<!-- walk:skills:end -->"
    assert INLINE_LIMIT_BYTES == 4096


def test_codex_section_inlines_small_and_links_large(tmp_path: Path) -> None:
    projector = CodexSkillProjector(clock=FakeClock(AT))
    small = _skill("git-hygiene")
    large = _skill("big-skill", body="y" * 5 * 1024 + "\n")

    section = projector.render_section([small, large], str(tmp_path))
    files = projector.render([small, large], str(tmp_path))

    assert section.startswith(AGENTS_MD_START + "\n")
    assert section.endswith(AGENTS_MD_END + "\n")
    assert "### git-hygiene (v1.0)\n\nAbout git-hygiene\n\nCommit often.\n" in section
    assert "### big-skill (v1.0)\n\nAbout big-skill\n\nSee .walk/skills/big-skill/SKILL.md\n" in (
        section
    )
    assert "yyyy" not in section
    linked = tmp_path / ".walk" / "skills" / "big-skill" / "SKILL.md"
    assert files[str(linked)].decode("utf-8").endswith(large.body_markdown)
    assert files[str(tmp_path / "AGENTS.md")].decode("utf-8") == section
    linked_projection = projector.project(large, str(tmp_path))
    assert Path(linked_projection.target_path) == tmp_path / "AGENTS.md"


def test_codex_preserves_content_outside_markers(tmp_path: Path) -> None:
    projector = CodexSkillProjector(clock=FakeClock(AT))
    before = "# Agents\r\n\r\nUser text stays.\r\n"
    after = "\n## Footer\nmore user text"
    old_section = f"{AGENTS_MD_START}\nstale\n{AGENTS_MD_END}\n"
    (tmp_path / "AGENTS.md").write_bytes((before + old_section + after).encode("utf-8"))

    first = projector.render([_skill()], str(tmp_path))[str(tmp_path / "AGENTS.md")]
    (tmp_path / "AGENTS.md").write_bytes(first)
    second = projector.render([_skill()], str(tmp_path))[str(tmp_path / "AGENTS.md")]

    text = second.decode("utf-8")
    assert second == first
    assert text.startswith(before)
    assert text.endswith(after)
    assert text.count(AGENTS_MD_START) == 1
    assert text.count(AGENTS_MD_END) == 1
    assert "stale" not in text


def test_codex_appends_section_to_file_without_markers(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_bytes(b"# Rules\nno newline at end")

    text = CodexSkillProjector(clock=FakeClock(AT)).render([_skill()], str(tmp_path))[
        str(tmp_path / "AGENTS.md")
    ]

    assert text.startswith(b"# Rules\nno newline at end\n\n" + AGENTS_MD_START.encode())


def test_default_projector_uses_system_clock(tmp_path: Path) -> None:
    assert CodexSkillProjector().project(_skill(), str(tmp_path)).generated_at.tzinfo is not None
