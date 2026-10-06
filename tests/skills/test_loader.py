import hashlib
from pathlib import Path

import pytest

from walk.common.enums import LearningScope
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.skills.errors import SkillLoadError
from walk.skills.loader import SkillFrontMatter, discover_skill_dirs, parse_skill_file
from walk.skills.service import DefaultSkillRegistry

BODY = "# Bar\n\nDo the thing.\n"


def write_skill(
    root: Path,
    directory: str,
    *,
    name: str | None = None,
    scope: str = "PROJECT",
    version: str = "1.0",
    body: str = BODY,
    roles: str = "[QC]",
) -> Path:
    """Write ``<root>/<directory>/SKILL.md`` and return its path."""
    path = root / directory / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f'---\nname: {name or directory}\nversion: "{version}"\ndescription: A skill.\n'
        f"scope: {scope}\napplies_to_roles: {roles}\nrequires_tools: []\ntags: [demo]\n---\n"
    )
    path.write_bytes((header + body).encode("utf-8"))
    return path


def test_parse_reads_front_matter_and_body(tmp_path: Path) -> None:
    path = write_skill(tmp_path, "bar")

    skill = parse_skill_file(path)

    assert skill.name == "bar"
    assert skill.version == "1.0"
    assert skill.scope is LearningScope.PROJECT
    assert skill.applies_to_roles == [AgentRole.QC]
    assert skill.tags == ["demo"]
    assert skill.body_markdown == BODY
    assert skill.source_path == str(path)
    assert skill.content_sha256 == hashlib.sha256(BODY.encode("utf-8")).hexdigest()


def test_parse_rejects_name_directory_mismatch(tmp_path: Path) -> None:
    path = write_skill(tmp_path, "foo", name="bar")

    with pytest.raises(SkillLoadError, match="foo") as raised:
        parse_skill_file(path)

    assert "bar" in raised.value.message
    assert isinstance(raised.value, ConfigError)


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("no front matter\n", "front matter"),
        ("---\nname: [broken\n---\nbody\n", "front matter"),
        ("---\n- a list\n---\nbody\n", "front matter"),
        ("---\nname: bar\nversion: '1'\ndescription: d\nscope: PROJECT\n---\nb\n", "version"),
        (
            "---\nname: bar\nversion: '1.0'\ndescription: ''\nscope: PROJECT\n---\nb\n",
            "description",
        ),
    ],
)
def test_parse_rejects_invalid_front_matter(tmp_path: Path, text: str, reason: str) -> None:
    path = tmp_path / "bar" / "SKILL.md"
    path.parent.mkdir()
    path.write_text(text, encoding="utf-8")

    with pytest.raises(SkillLoadError, match=reason):
        parse_skill_file(path)


def test_parse_rejects_oversized_body(tmp_path: Path) -> None:
    path = write_skill(tmp_path, "bar", body="x" * (64 * 1024 + 1))

    with pytest.raises(SkillLoadError, match="64 KB"):
        parse_skill_file(path)


def test_project_skill_cannot_claim_kernel_scope(tmp_path: Path) -> None:
    builtin = tmp_path / "builtin"
    project = tmp_path / "project"
    write_skill(builtin, "kernel-skill", scope="KERNEL")
    write_skill(project, "sneaky", scope="KERNEL")
    registry = DefaultSkillRegistry(builtin, project, {})

    with pytest.raises(SkillLoadError, match="KERNEL"):
        registry.load()


def test_discover_skill_dirs_lists_folders_with_skill_md(tmp_path: Path) -> None:
    write_skill(tmp_path, "b-skill")
    write_skill(tmp_path, "a-skill")
    (tmp_path / "no-skill").mkdir()
    (tmp_path / "README.md").write_text("x", encoding="utf-8")

    assert discover_skill_dirs(tmp_path) == [tmp_path / "a-skill", tmp_path / "b-skill"]
    assert discover_skill_dirs(tmp_path / "absent") == []


def test_front_matter_model_limits() -> None:
    data = {"name": "bar", "version": "1.0", "description": "d", "scope": "PROJECT"}

    front = SkillFrontMatter.model_validate(data)

    assert front.applies_to_roles == []
    with pytest.raises(ValueError, match="300"):
        SkillFrontMatter.model_validate({**data, "description": "x" * 301})
