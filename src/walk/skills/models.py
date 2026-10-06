"""Skill contracts (§28-§29; DOMAIN-MODEL §4.6; ADR-0007)."""

import hashlib
from datetime import datetime
from typing import Any

from pydantic import Field, model_validator

from walk.common.enums import LearningScope
from walk.common.ids import SkillName, ToolName
from walk.common.models import FrozenModel, WalkModel
from walk.common.roles import AgentRole


class Skill(WalkModel):
    """§28 canonical skill.

    Source: `.ai/agents/skills/<name>/SKILL.md` (project) or
    `walk/skills/builtin/<name>/SKILL.md` (kernel).
    """

    name: SkillName = Field(description="Kebab-case skill name.")
    version: str = Field(description="Skill version, e.g. '1.0'.")
    description: str = Field(description="When the skill applies.")
    scope: LearningScope = Field(description="KERNEL built-in or PROJECT skill.")
    applies_to_roles: list[AgentRole] = Field(
        default_factory=list, description="Roles that receive the skill by default."
    )
    requires_tools: list[ToolName] = Field(
        default_factory=list, description="Tools the skill's instructions use."
    )
    tags: list[str] = Field(default_factory=list, description="Free-form search tags.")
    body_markdown: str = Field(description="SKILL.md body without front matter.")
    source_path: str = Field(description="Path of the canonical SKILL.md.")
    content_sha256: str = Field(
        description="sha256 hex of body_markdown (UTF-8); derived when omitted, checked if given."
    )

    @model_validator(mode="before")
    @classmethod
    def _derive_content_hash(cls, data: Any) -> Any:
        if not isinstance(data, dict) or not isinstance(data.get("body_markdown"), str):
            return data
        digest = hashlib.sha256(data["body_markdown"].encode("utf-8")).hexdigest()
        given = data.get("content_sha256")
        if given is None:
            return {**data, "content_sha256": digest}
        if given != digest:
            msg = "content_sha256 does not match sha256 of body_markdown"
            raise ValueError(msg)
        return data


class SkillProjection(FrozenModel):
    """Generated provider representation (ADR-0007)."""

    skill: SkillName = Field(description="Projected skill.")
    provider: str = Field(description="Provider the projection is for, e.g. 'claude'.")
    target_path: str = Field(
        description="e.g. <worktree>/.claude/skills/<name>/SKILL.md or <worktree>/AGENTS.md section"
    )
    content_sha256: str = Field(description="sha256 of the generated content.")
    generated_from_sha256: str = Field(description="Skill.content_sha256 it was generated from.")
    generated_at: datetime = Field(description="When the projection was generated.")


class DriftReport(FrozenModel):
    """Projection drift against the lock file (ADR-0007)."""

    missing: list[SkillName] = Field(description="Locked projections absent on disk.")
    modified: list[SkillName] = Field(description="Projections edited directly on disk.")
    orphaned: list[str] = Field(description="Projection files with no locked skill.")
    ok: bool = Field(description="True when nothing is missing, modified or orphaned.")
