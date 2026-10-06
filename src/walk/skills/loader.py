"""Canonical ``SKILL.md`` parsing (§28; ADR-0007 D-1).

A skill is a kebab-case folder holding ``SKILL.md``: a YAML front matter block between ``---``
lines, then the Markdown body.
"""

from pathlib import Path
from typing import Final

import yaml
from pydantic import Field, ValidationError

from walk.common.enums import LearningScope
from walk.common.ids import SkillName, ToolName
from walk.common.models import WalkModel
from walk.common.roles import AgentRole
from walk.skills.errors import SkillLoadError
from walk.skills.models import Skill

_SKILL_FILE: Final = "SKILL.md"
_MAX_BODY_BYTES: Final = 64 * 1024
_DELIMITER: Final = "---"


class SkillFrontMatter(WalkModel):
    """The YAML header of a ``SKILL.md`` (ADR-0007 D-1)."""

    name: SkillName = Field(description="Kebab-case skill name; equals the folder name.")
    version: str = Field(pattern=r"^\d+\.\d+$", description="MAJOR.MINOR.")
    description: str = Field(min_length=1, max_length=300, description="When the skill applies.")
    scope: LearningScope = Field(description="KERNEL built-in or PROJECT skill.")
    applies_to_roles: list[AgentRole] = Field(
        default_factory=list, description="Roles that receive the skill by default."
    )
    requires_tools: list[ToolName] = Field(
        default_factory=list, description="Tools the skill's instructions use."
    )
    tags: list[str] = Field(default_factory=list, description="Free-form search tags.")


def discover_skill_dirs(root: Path) -> list[Path]:
    """Sub-folders of ``root`` that contain a ``SKILL.md``, sorted by name; ``[]`` if absent."""
    if not root.is_dir():
        return []
    return sorted(child for child in root.iterdir() if (child / _SKILL_FILE).is_file())


def parse_skill_file(path: Path) -> Skill:
    """Front matter + body of ``<folder>/SKILL.md``.

    ``content_sha256`` is the SHA-256 of the body: the `Skill` model derives it and rejects any
    other value (E01-S14), so the hash covers what a projection is generated from.

    Raises:
        SkillLoadError: Missing or invalid front matter, a body over 64 KB, or a front-matter
            ``name`` that differs from the folder name.
    """
    text = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
    header, body = _split(path, text)
    try:
        front = SkillFrontMatter.model_validate(header)
    except ValidationError as exc:
        msg = f"{path}: invalid skill front matter: {exc}"
        raise SkillLoadError(msg, detail={"path": str(path)}) from exc
    folder = path.parent.name
    if front.name != folder:
        msg = f"{path}: skill folder {folder!r} does not match front-matter name {front.name!r}"
        raise SkillLoadError(msg, detail={"path": str(path), "folder": folder, "name": front.name})
    if len(body.encode("utf-8")) > _MAX_BODY_BYTES:
        msg = f"{path}: skill body exceeds 64 KB"
        raise SkillLoadError(msg, detail={"path": str(path)})
    return Skill(**front.model_dump(), body_markdown=body, source_path=str(path))


def _split(path: Path, text: str) -> tuple[dict[str, object], str]:
    lines = text.split("\n")
    if lines[0].strip() != _DELIMITER or _DELIMITER not in lines[1:]:
        msg = f"{path}: SKILL.md must start with a '---' front matter block"
        raise SkillLoadError(msg, detail={"path": str(path)})
    end = lines.index(_DELIMITER, 1)
    try:
        header = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as exc:
        msg = f"{path}: invalid front matter YAML: {exc}"
        raise SkillLoadError(msg, detail={"path": str(path)}) from exc
    if not isinstance(header, dict):
        msg = f"{path}: front matter must be a mapping"
        raise SkillLoadError(msg, detail={"path": str(path)})
    return header, "\n".join(lines[end + 1 :])
