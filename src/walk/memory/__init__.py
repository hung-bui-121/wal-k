"""Project memory: `.ai/` documents, their single write path and index (§34-§42; ADR-0003)."""

from walk.memory.errors import ApprovedWriteRefused, DocumentNotFound, SecretDetected
from walk.memory.frontmatter import parse_document, render_document, split_document
from walk.memory.models import (
    ApprovalStatus,
    ApprovedArtifact,
    ApprovedArtifactKind,
    BugContext,
    ContextUpdate,
    FeatureContext,
    Freshness,
    FreshnessAssessment,
    FreshnessStatus,
    FrontMatter,
    MemoryDocType,
    MemoryDocument,
    ProjectContext,
    RelatedLinks,
)
from walk.memory.paths import doc_path_for, folder_for_type
from walk.memory.protocols import MemoryManager
from walk.memory.repository import MemoryIndexRepository, MemoryIndexRow
from walk.memory.secrets import SECRET_PATTERNS, find_secrets
from walk.memory.sections import SECTION_ORDER, sections_for, skeleton_for
from walk.memory.service import DefaultMemoryManager

__all__ = [
    "SECRET_PATTERNS",
    "SECTION_ORDER",
    "ApprovalStatus",
    "ApprovedArtifact",
    "ApprovedArtifactKind",
    "ApprovedWriteRefused",
    "BugContext",
    "ContextUpdate",
    "DefaultMemoryManager",
    "DocumentNotFound",
    "FeatureContext",
    "Freshness",
    "FreshnessAssessment",
    "FreshnessStatus",
    "FrontMatter",
    "MemoryDocType",
    "MemoryDocument",
    "MemoryIndexRepository",
    "MemoryIndexRow",
    "MemoryManager",
    "ProjectContext",
    "RelatedLinks",
    "SecretDetected",
    "doc_path_for",
    "find_secrets",
    "folder_for_type",
    "parse_document",
    "render_document",
    "sections_for",
    "skeleton_for",
    "split_document",
]
