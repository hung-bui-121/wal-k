"""Context contracts (DOMAIN-MODEL §4.9; §40-§43)."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from walk.common.enums import Effort
from walk.common.ids import Sha, WorkItemId
from walk.common.models import FrozenModel, WalkModel, utcnow
from walk.common.roles import AgentRole
from walk.memory.models import FreshnessAssessment


class ContextItemKind(StrEnum):
    """What a context item holds."""

    WORK_ITEM = "WORK_ITEM"
    FEATURE_CONTEXT = "FEATURE_CONTEXT"
    BUG_CONTEXT = "BUG_CONTEXT"
    PROJECT_CONTEXT = "PROJECT_CONTEXT"
    DECISION = "DECISION"
    APPROVED_ARTIFACT = "APPROVED_ARTIFACT"
    HANDOVER = "HANDOVER"
    WORKFLOW_STATE = "WORKFLOW_STATE"
    CODE_GRAPH = "CODE_GRAPH"
    SOURCE_FILE = "SOURCE_FILE"
    EVIDENCE = "EVIDENCE"
    SKILL = "SKILL"


class ContextItem(WalkModel):
    """One piece of context given to an agent."""

    id: str = Field(
        description="Stable id `<KIND>:<subject id>`, e.g. 'FEATURE_CONTEXT:FEAT-0001'."
    )
    kind: ContextItemKind = Field(description="What the item holds.")
    title: str = Field(description="Human title.")
    content: str = Field(description="Text handed to the agent.")
    tokens_estimate: int = Field(description="Estimated tokens of `content` (ADR-0012 D-3).")
    score: float = Field(description="Ranking score; 1.0 for mandatory items.")
    freshness: FreshnessAssessment | None = Field(
        description="§42 assessment of the backing document, if one was made."
    )
    requires_verification: bool = Field(
        default=False, description="Stale content: verify against source before relying on it."
    )
    source_path: str | None = Field(
        default=None, description="Repository-relative path of the backing file, if any."
    )
    mandatory: bool = Field(default=False, description="Mandatory tier (never trimmed).")


class ContextRequest(WalkModel):
    """Input of `ContextManager.build`."""

    work_item_id: WorkItemId = Field(description="Work item the context is for.")
    role: AgentRole = Field(description="Role that will receive the context.")
    effort: Effort = Field(description="Effective effort of the run.")
    token_budget: int = Field(description="Token budget for the whole bundle.")
    include_source: bool = Field(default=True, description="Admit SOURCE_FILE candidates.")
    code_graph_depth: int = Field(default=2, description="Neighbourhood depth for CODE_GRAPH.")


class ContextBundle(WalkModel):
    """Output of ContextManager.build (§40 order preserved in `items`)."""

    request: ContextRequest = Field(description="The request that produced the bundle.")
    items: list[ContextItem] = Field(description="Context items in §40 order.")
    total_tokens_estimate: int = Field(description="Sum of the items' token estimates.")
    excluded_count: int = Field(description="Candidates left out for lack of budget.")
    built_at: datetime = Field(default_factory=utcnow, description="When the bundle was built.")
    head_commit: Sha = Field(description="HEAD the bundle was built against.")

    def ref(self) -> "ContextBundleRef":
        """Manifest for checkpoints (ids + stale flags, no contents)."""
        return ContextBundleRef(
            item_ids=[i.id for i in self.items],
            total_tokens_estimate=self.total_tokens_estimate,
            stale_item_ids=[i.id for i in self.items if i.requires_verification],
        )


class ContextBundleRef(FrozenModel):
    """Manifest of what context was given; stored in Checkpoint.context_manifest."""

    item_ids: list[str] = Field(description="Ids of the bundle's items, in order.")
    total_tokens_estimate: int = Field(description="Token estimate of the bundle.")
    stale_item_ids: list[str] = Field(
        default_factory=list, description="Items flagged requires_verification."
    )
