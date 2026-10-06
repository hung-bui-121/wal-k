import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from walk.common.enums import LearningScope
from walk.common.roles import AgentRole
from walk.skills import DriftReport, Skill, SkillProjection

BODY = "# Git hygiene\n\nCommit small.\n"


def _skill(**overrides: object) -> Skill:
    data: dict[str, object] = {
        "name": "git-hygiene",
        "version": "1.0",
        "description": "How to commit",
        "scope": LearningScope.KERNEL,
        "applies_to_roles": [AgentRole.SENIOR_DEV],
        "requires_tools": ["git.commit"],
        "body_markdown": BODY,
        "source_path": "walk/skills/builtin/git-hygiene/SKILL.md",
    }
    data.update(overrides)
    return Skill.model_validate(data)


def test_skill_hash_and_projection_frozen() -> None:
    skill = _skill()
    assert skill.content_sha256 == hashlib.sha256(BODY.encode("utf-8")).hexdigest()
    projection = SkillProjection(
        skill=skill.name,
        provider="claude",
        target_path="wt/.claude/skills/git-hygiene/SKILL.md",
        content_sha256="ab" * 32,
        generated_from_sha256=skill.content_sha256,
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    with pytest.raises(ValidationError):
        projection.provider = "codex"  # type: ignore[misc]  # asserting the frozen model rejects it


def test_skill_rejects_a_hash_that_does_not_match_the_body() -> None:
    assert _skill(content_sha256=hashlib.sha256(BODY.encode()).hexdigest()).name == "git-hygiene"
    with pytest.raises(ValidationError, match="content_sha256"):
        _skill(content_sha256="0" * 64)
    with pytest.raises(ValidationError, match="body_markdown"):
        _skill(body_markdown=None)


def test_skill_body_cannot_change_without_its_hash() -> None:
    skill = _skill()
    with pytest.raises(ValidationError, match="content_sha256"):
        skill.body_markdown = "changed"


def test_drift_report_fields() -> None:
    report = DriftReport(missing=["git-hygiene"], modified=[], orphaned=["x/SKILL.md"], ok=False)
    assert report.model_dump() == {
        "missing": ["git-hygiene"],
        "modified": [],
        "orphaned": ["x/SKILL.md"],
        "ok": False,
    }
