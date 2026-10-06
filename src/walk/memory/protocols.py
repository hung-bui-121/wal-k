"""Memory service protocol (INTERFACES §1.8)."""

from typing import Protocol

from walk.common.ids import ApprovedArtifactId, BugId, FeatureId, HandoverId, Sha
from walk.common.models import Actor
from walk.memory.models import (
    ApprovedArtifact,
    BugContext,
    ContextUpdate,
    FeatureContext,
    FreshnessAssessment,
    MemoryDocument,
    ProjectContext,
)


class MemoryManager(Protocol):
    """§34-§42, §22, §33. Hosted by walk.memory. All writes go through `write()`."""

    def root(self) -> str:
        """Absolute path of `.ai/`."""
        ...

    async def read(self, doc_id: str) -> MemoryDocument:
        """The document ``doc_id``; DocumentNotFound when absent."""
        ...

    async def read_feature_context(self, feature_id: FeatureId) -> FeatureContext:
        """Typed §37 feature context."""
        ...

    async def read_bug_context(self, bug_id: BugId) -> BugContext:
        """Typed §38 bug context."""
        ...

    async def read_project_context(self) -> ProjectContext:
        """Typed §36 project context."""
        ...

    async def read_handover(self, handover_id: HandoverId) -> MemoryDocument:
        """Raw document; `walk.agents.handover.from_document()` converts it to the typed Handover.

        (agents is above memory.)
        """
        ...

    async def write(
        self, doc: MemoryDocument, *, actor: Actor, head: Sha, branch: str
    ) -> MemoryDocument:
        """Validate, bump version, stamp freshness, refuse secrets and unauthorised approved/.

        Writes atomically (tmp + rename), updates memory_index, fires ON_CONTEXT_UPDATED,
        ledger CONTEXT_UPDATED (ARCHITECTURE.md §6, Invariant 10).
        """
        ...

    async def apply_updates(
        self, updates: list[ContextUpdate], *, actor: Actor, head: Sha, branch: str
    ) -> list[MemoryDocument]:
        """Section-level REPLACE/APPEND from AgentOutput.context_updates.

        Creates a FeatureContext/BugContext skeleton if missing.
        """
        ...

    async def write_handover(
        self, doc: MemoryDocument, *, actor: Actor, head: Sha, branch: str
    ) -> str:
        """Writes `.ai/handovers/HO-NNNN.md`; ledger HANDOVER_CREATED. Returns path.

        The doc is built by `walk.agents.handover.to_document(handover)`; the `handovers`
        table row is written by runtime.CheckpointManager.
        """
        ...

    async def assess_freshness(self, doc: MemoryDocument, head: Sha) -> FreshnessAssessment:
        """INTERFACES §5.5."""
        ...

    async def rebuild_index(self) -> int:
        """Scan `.ai/**/*.md`, parse front matter, upsert memory_index. Returns doc count."""
        ...

    async def approve_artifact(
        self, artifact: ApprovedArtifact, *, actor: Actor
    ) -> ApprovedArtifact:
        """§33. Requires actor role ∈ authority.may_approve[kind] or USER.

        Ledger ARTIFACT_APPROVED.
        """
        ...

    async def verify_approved_artifacts(self) -> list[ApprovedArtifactId]:
        """Hash check; returns drifted ids and fires ON_CONTEXT_STALE(INVALID) for each."""
        ...

    async def write_report(self, kind: str, subject_id: str, markdown: str) -> str:
        """`.ai/reports/<kind>/<subject_id>.md` (generated, overwritten)."""
        ...
