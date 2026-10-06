"""Project memory contracts (§22, §33, §36-§42; DOMAIN-MODEL §3 memory enums, §4.7; ADR-0003)."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator

from walk.common.ids import (
    ApprovedArtifactId,
    BugId,
    DecisionId,
    EvidenceId,
    FeatureId,
    Sha,
    WorkItemId,
)
from walk.common.models import Actor, FrozenModel, JsonDict, WalkModel
from walk.workflow.models import GddRef


class FreshnessStatus(StrEnum):
    """§42."""

    CURRENT = "CURRENT"
    POSSIBLY_STALE = "POSSIBLY_STALE"
    INVALID = "INVALID"


class MemoryDocType(StrEnum):
    """Front-matter ``type`` of a `.ai/` document (ARCHITECTURE §8)."""

    PROJECT = "project"
    PROJECT_CONSTITUTION = "project_constitution"
    PHASE = "phase"
    FEATURE = "feature"
    BUG = "bug"
    DECISION = "decision"
    APPROVED = "approved"
    HANDOVER = "handover"
    REPORT = "report"
    EVIDENCE_PACKAGE = "evidence_package"
    RETROSPECTIVE = "retrospective"
    OBSERVATION = "observation"
    IMPROVEMENT_CANDIDATE = "improvement_candidate"
    PATTERN = "pattern"
    ANTI_PATTERN = "anti_pattern"
    CONSTITUTION = "constitution"
    SKILL = "skill"


class ApprovedArtifactKind(StrEnum):
    """§33."""

    GAMEPLAY_CONCEPT = "GAMEPLAY_CONCEPT"
    MECHANIC_SPEC = "MECHANIC_SPEC"
    UX_FLOW = "UX_FLOW"
    UI_CONCEPT = "UI_CONCEPT"
    ART_DIRECTION = "ART_DIRECTION"
    ARCHITECTURE_DIRECTION = "ARCHITECTURE_DIRECTION"
    ASSET = "ASSET"
    PHASE_BASELINE = "PHASE_BASELINE"
    REFERENCE_MATERIAL = "REFERENCE_MATERIAL"


class ApprovalStatus(StrEnum):
    """Lifecycle of an approved artifact (§33)."""

    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    CHANGE_REQUESTED = "CHANGE_REQUESTED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"


class Freshness(WalkModel):
    """§42 stamps. Written by MemoryManager on every write (ADR-0003)."""

    commit: Sha = Field(description="HEAD of the work branch at write time.")
    branch: str = Field(description="Work branch at write time.")
    timestamp: datetime = Field(description="Write time.")
    pr: str | None = Field(default=None, description="Pull request reference, if any.")
    build: str | None = Field(default=None, description="Build identifier, if any.")

    @field_validator("pr", "build", mode="before")
    @classmethod
    def _numbers_as_text(cls, value: object) -> object:
        # YAML reads `pr: 42` as an int (ARCHITECTURE §8.2 sample); the stamp keeps it as text.
        return str(value) if isinstance(value, int | float) else value


class FreshnessAssessment(FrozenModel):
    """Result of INTERFACES.md §5.5 classification."""

    status: FreshnessStatus = Field(description="Classification.")
    reason: str = Field(description="Why this status was chosen.")
    changed_relevant_files: list[str] = Field(
        default_factory=list, description="Relevant files changed since the stamp."
    )
    assessed_against: Sha = Field(description="HEAD the stamp was compared with.")
    assessed_at: datetime = Field(description="When the assessment ran.")


class RelatedLinks(WalkModel):
    """Typed links of a document; ids must resolve."""

    work_items: list[WorkItemId] = Field(default_factory=list, description="Work items.")
    decisions: list[DecisionId] = Field(default_factory=list, description="Decisions.")
    approved: list[ApprovedArtifactId] = Field(
        default_factory=list, description="Approved artifacts."
    )
    evidence: list[EvidenceId] = Field(default_factory=list, description="Evidence records.")
    gdd: list[str] = Field(default_factory=list, description="GDD references.")


class FrontMatter(WalkModel):
    """Common YAML header of every `.ai/**/*.md` (ARCHITECTURE.md §8.2)."""

    id: str = Field(description="Document id; equals the file stem.")
    type: MemoryDocType = Field(description="Document type.")
    title: str = Field(description="Human title.")
    status: str | None = Field(default=None, description="Type-specific status as text.")
    version: int = Field(default=1, description="Monotonically increasing per write.")
    schema_version: int = Field(default=1, description="Front-matter schema version.")
    created_at: datetime = Field(description="First write.")
    updated_at: datetime = Field(description="Last write.")
    updated_by: Actor = Field(description="Who last wrote it.")
    freshness: Freshness | None = Field(default=None, description="§42 stamp.")
    related: RelatedLinks = Field(default_factory=RelatedLinks, description="Typed links.")
    relevant_files: list[str] = Field(
        default_factory=list, description="Repository files used by freshness classification."
    )
    extra: JsonDict = Field(
        default_factory=dict, description="Type-specific scalar fields (e.g. approved_by, scope)"
    )


class MemoryDocument(WalkModel):
    """Parsed Markdown document: front matter + ordered H2 sections."""

    path: str = Field(description="Path relative to `.ai/`, POSIX separators.")
    front_matter: FrontMatter = Field(description="Parsed YAML header.")
    sections: dict[str, str] = Field(description="H2 heading -> markdown body, insertion-ordered")
    raw_sha256: str = Field(description="sha256 of the file text; empty until first written.")


class ProjectContext(WalkModel):
    """§36 `.ai/project/project.md` sections."""

    goals: str = Field(description="Goals.")
    platforms: list[str] = Field(description="Platforms.")
    technical_constraints: str = Field(description="Technical Constraints.")
    performance_targets: str = Field(description="Performance Targets.")
    coding_conventions: str = Field(description="Coding Conventions.")
    architecture_overview: str = Field(description="Architecture Overview.")
    art_direction: str = Field(description="Art Direction.")
    product_constraints: str = Field(description="Product Constraints.")
    major_decisions: list[DecisionId] = Field(description="Major Decisions.")
    known_limitations: str = Field(description="Known Limitations.")


class FeatureContext(WalkModel):
    """§37 `.ai/features/FEAT-NNNN.md` — section names are the H2 headings, in this order."""

    feature_id: FeatureId = Field(description="Feature the context belongs to.")
    intent: str = Field(description="Intent.")
    design_goal: str = Field(description="Design Goal.")
    relevant_gdd: list[GddRef] = Field(description="Relevant GDD.")
    current_status: str = Field(description="Current Status.")
    architecture: str = Field(description="Architecture.")
    affected_systems: list[str] = Field(description="Affected Systems.")
    dependencies: list[str] = Field(description="Dependencies.")
    relevant_files: list[str] = Field(description="Relevant Files.")
    important_decisions: list[DecisionId] = Field(description="Important Decisions.")
    implementation_notes: str = Field(description="Implementation Notes.")
    known_risks: str = Field(description="Known Risks.")
    qc_notes: str = Field(description="QC Notes.")
    evidence: list[EvidenceId] = Field(description="Evidence.")
    remaining_work: str = Field(description="Remaining Work.")
    freshness: Freshness | None = Field(default=None, description="§42 stamp of the document.")


class BugContext(WalkModel):
    """§38 `.ai/bugs/BUG-NNNN.md`."""

    bug_id: BugId = Field(description="Bug the context belongs to.")
    problem: str = Field(description="Problem.")
    reproduction: str = Field(description="Reproduction.")
    expected_behavior: str = Field(description="Expected Behavior.")
    observed_behavior: str = Field(description="Observed Behavior.")
    investigations: str = Field(description="Investigations.")
    hypotheses: str = Field(description="Hypotheses.")
    failed_attempts: str = Field(description="Failed Attempts.")
    root_cause: str = Field(description="Root Cause.")
    affected_systems: list[str] = Field(description="Affected Systems.")
    fix: str = Field(description="Fix.")
    regression_risk: str = Field(description="Regression Risk.")
    verification: str = Field(description="Verification.")
    freshness: Freshness | None = Field(default=None, description="§42 stamp of the document.")


class ContextUpdate(WalkModel):
    """§126 Context Updates — targeted section edits to memory documents (§41).

    Produced by agents, consumed by MemoryManager.apply_updates.
    """

    doc_id: str = Field(description="FEAT-0012 / BUG-0031 / project")
    section: str = Field(description="H2 section name per MemoryDocType schema")
    operation: Literal["REPLACE", "APPEND"] = Field(description="How the section changes.")
    content_markdown: str = Field(description="New or appended section content.")
    relevant_files: list[str] = Field(
        default_factory=list, description="Files merged into the document's relevant_files."
    )


class ApprovedArtifact(WalkModel):
    """§33 first-class approved object; `.ai/approved/APR-NNNN.md` + payload folder."""

    id: ApprovedArtifactId = Field(description="APR-<n>.")
    kind: ApprovedArtifactKind = Field(description="What was approved.")
    title: str = Field(description="Human title.")
    status: ApprovalStatus = Field(description="Lifecycle status.")
    scope: str = Field(description="Project / PHASE-id / FEAT-id")
    version: int = Field(description="Artifact version.")
    approved_by: Actor = Field(description="Who approved it.")
    approved_at: datetime = Field(description="When it was approved.")
    related_requirements: list[GddRef] = Field(description="Requirements it relates to.")
    payload_paths: list[str] = Field(description="Payload files under the artifact folder.")
    content_sha256: str = Field(description="Hash over payload files; drift check (Invariant 10)")
    supersedes: ApprovedArtifactId | None = Field(
        default=None, description="Artifact version this one replaces."
    )
    change_request_decision: DecisionId | None = Field(
        default=None, description="Decision authorising the change that produced this version"
    )
