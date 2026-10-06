from datetime import UTC, datetime
from pathlib import Path

import pytest

from walk.common.errors import ConfigError
from walk.skills import SkillProjection
from walk.skills.lockfile import LOCK_PATH, ProjectionLock

AT = datetime(2026, 1, 1, tzinfo=UTC)


def _projection(skill: str, provider: str) -> SkillProjection:
    return SkillProjection(
        skill=skill,
        provider=provider,
        target_path=f".claude/skills/{skill}/SKILL.md",
        content_sha256="a" * 64,
        generated_from_sha256="b" * 64,
        generated_at=AT,
    )


def test_lock_roundtrip(tmp_path: Path) -> None:
    lock = ProjectionLock(
        projections=[
            _projection("git-hygiene", "codex"),
            _projection("git-hygiene", "claude"),
            _projection("code-review-checklist", "claude"),
        ]
    )

    path = lock.write(tmp_path)
    loaded = ProjectionLock.load(tmp_path)

    assert path == tmp_path / LOCK_PATH
    assert LOCK_PATH == "agents/projections.lock.yaml"
    assert sorted(loaded.projections, key=repr) == sorted(lock.projections, key=repr)
    assert [(p.provider, p.skill) for p in loaded.projections] == [
        ("claude", "code-review-checklist"),
        ("claude", "git-hygiene"),
        ("codex", "git-hygiene"),
    ]
    assert [p.skill for p in loaded.for_provider("claude")] == [
        "code-review-checklist",
        "git-hygiene",
    ]
    assert lock.write(tmp_path).read_bytes() == path.read_bytes()


def test_lock_load_absent_and_invalid(tmp_path: Path) -> None:
    assert ProjectionLock.load(tmp_path).projections == []
    (tmp_path / "agents").mkdir()
    (tmp_path / LOCK_PATH).write_text("projections: []\n", encoding="utf-8")
    assert ProjectionLock.load(tmp_path).projections == []
    (tmp_path / LOCK_PATH).write_text("projections: [{skill: x}]\n", encoding="utf-8")

    with pytest.raises(ConfigError, match=r"projections\.lock\.yaml"):
        ProjectionLock.load(tmp_path)
    (tmp_path / LOCK_PATH).write_text("projections: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigError, match=r"projections\.lock\.yaml"):
        ProjectionLock.load(tmp_path)
