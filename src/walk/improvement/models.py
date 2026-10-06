"""Improvement contracts (DOMAIN-MODEL §3, §4.14; §97, §104, §105, §109)."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from walk.common.enums import ImprovementScope
from walk.common.ids import ImprovementId
from walk.common.models import WalkModel


class RolloutStage(StrEnum):
    """§109."""

    DRAFT = "DRAFT"
    EXPERIMENTAL = "EXPERIMENTAL"
    LIMITED = "LIMITED"
    DEFAULT = "DEFAULT"
    DEPRECATED = "DEPRECATED"


class ImprovementRisk(StrEnum):
    """§104 authority tiers."""

    LOW = "LOW"  # auto-approvable
    MEDIUM = "MEDIUM"  # maintainer / PO review
    HIGH = "HIGH"  # user approval


class CandidateState(StrEnum):
    """§97 lifecycle before rollout."""

    OBSERVATION = "OBSERVATION"
    HYPOTHESIS = "HYPOTHESIS"
    CANDIDATE = "CANDIDATE"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class BehaviorVersion(WalkModel):
    """§105 versioned kernel behavior artifact.

    A workflow table, constitution, skill, template or routing policy (DOMAIN-MODEL §4.14).
    """

    kind: ImprovementScope = Field(description="Kind of behavior artifact.")
    name: str = Field(
        description="e.g. 'feature_workflow', 'LEAD_DEV', 'unity-debugging', 'story_template'"
    )
    version: str = Field(description="semver-ish 'MAJOR.MINOR'")
    stage: RolloutStage = Field(description="Rollout stage of this version.")
    content_sha256: str = Field(description="SHA-256 of the artifact file bytes.")
    source_path: str = Field(description="Artifact file relative to the kernel package (POSIX).")
    candidate_id: ImprovementId | None = Field(
        default=None, description="Improvement candidate that produced this version, if any."
    )
    changelog_entry: str | None = Field(default=None, description="Changelog entry (§120).")
    introduced_at: datetime = Field(description="When this version was introduced.")
    deprecated_at: datetime | None = Field(
        default=None, description="When this version was deprecated, if it was."
    )
    shadow_of: str | None = Field(
        default=None,
        description="§108 version this one shadows, when stage == EXPERIMENTAL in shadow mode",
    )
