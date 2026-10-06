from pathlib import Path

import pytest

import walk.skills
from tests.skills.test_loader import write_skill
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.skills import DefaultSkillRegistry, SkillRegistry

BUILTIN = Path(walk.skills.__file__).resolve().parent / "builtin"
BUILTIN_NAMES = [
    "code-review-checklist",
    "git-hygiene",
    "qc-exploratory-testing",
    "unity-csharp-conventions",
    "walk-output-contract",
]
QC_DEFAULTS = ["walk-output-contract", "qc-exploratory-testing", "git-hygiene"]


def _registry(project: Path | None = None) -> DefaultSkillRegistry:
    return DefaultSkillRegistry(BUILTIN, project, {AgentRole.QC: list(QC_DEFAULTS)})


def test_load_returns_builtin_skills() -> None:
    registry = _registry()
    protocol: SkillRegistry = registry

    skills = protocol.load()

    assert sorted(skill.name for skill in skills) == BUILTIN_NAMES
    for skill in skills:
        assert Path(skill.source_path) == BUILTIN / skill.name / "SKILL.md"
        assert len(skill.content_sha256) == 64
        assert skill.version == "1.0"
        assert skill.scope.value == "KERNEL"


def test_project_skill_shadows_builtin(tmp_path: Path) -> None:
    path = write_skill(tmp_path, "git-hygiene", body="# Project git rules\n")
    write_skill(tmp_path, "project-only")

    skills = {skill.name: skill for skill in _registry(tmp_path).load()}

    assert skills["git-hygiene"].source_path == str(path)
    assert skills["git-hygiene"].body_markdown == "# Project git rules\n"
    assert "project-only" in skills
    assert len(skills) == len(BUILTIN_NAMES) + 1


def test_load_is_cached_until_called_again(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.load()
    write_skill(tmp_path, "late-skill")

    with pytest.raises(ConfigError):
        registry.get("late-skill")
    registry.load()

    assert registry.get("late-skill").name == "late-skill"


def test_get_unknown_raises_config_error() -> None:
    registry = _registry()

    with pytest.raises(ConfigError, match="unknown skill nope"):
        registry.get("nope")
    assert registry.get("git-hygiene").name == "git-hygiene"


def test_for_role_merges_defaults_and_required() -> None:
    registry = _registry()

    skills = registry.for_role(AgentRole.QC, ["unity-csharp-conventions", "git-hygiene"])

    assert [skill.name for skill in skills] == [*QC_DEFAULTS, "unity-csharp-conventions"]
    assert registry.for_role(AgentRole.LEAD_DEV, []) == []


def test_for_role_missing_required_raises() -> None:
    with pytest.raises(ConfigError, match="missing-skill") as raised:
        _registry().for_role(AgentRole.QC, ["missing-skill", "git-hygiene", "other-missing"])

    assert raised.value.detail["missing"] == ["missing-skill", "other-missing"]


async def test_projection_and_drift_name_their_stories() -> None:
    registry = _registry()

    with pytest.raises(ConfigError, match="E02-S06"):
        await registry.project_all([], "/wt", [])
    with pytest.raises(ConfigError, match="E02-S07"):
        await registry.check_drift([], "/wt")
