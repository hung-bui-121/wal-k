"""`DefaultContextManager`: the §40 mandatory tier (INTERFACES §5.4 steps 1-3, 7-8; ADR-0012).

Ranked candidates (steps 4-6: code graph, source slices, evidence) arrive in E04-S08; until then
`excluded_count` is always 0. Output is deterministic for the same DB, `.ai/` tree, HEAD and
request (ADR-0012 D-7): contents never contain the clock and JSON is rendered with sorted keys.
"""

import json
import logging
from collections.abc import Awaitable, Callable

from walk.common.clock import Clock
from walk.common.enums import Effort
from walk.common.ids import Sha, WorkItemId
from walk.context.budget import estimate_tokens, token_budget_for
from walk.context.models import ContextBundle, ContextItem, ContextItemKind, ContextRequest
from walk.decisions.models import Decision, DecisionStatus
from walk.hooks.models import HookContext, HookName
from walk.hooks.protocols import HookManager
from walk.memory.errors import DocumentNotFound
from walk.memory.frontmatter import render_document
from walk.memory.models import (
    ApprovedArtifact,
    FreshnessAssessment,
    FreshnessStatus,
    MemoryDocument,
)
from walk.memory.protocols import MemoryManager
from walk.telemetry.protocols import LedgerManager
from walk.workflow import WorkflowRepository
from walk.workflow.models import Bug, WorkItem, WorkItemKind, WorkItemTransition
from walk.workflow.protocols import WorkflowManager

_LOG = logging.getLogger(__name__)

FreshnessProbe = Callable[[MemoryDocument, Sha], Awaitable[FreshnessAssessment | None]]
HandoverLookup = Callable[[WorkItemId], Awaitable[MemoryDocument | None]]
DecisionLookup = Callable[[WorkItem, list[str]], Awaitable[list[Decision]]]
ArtifactLookup = Callable[[WorkItem], Awaitable[list[ApprovedArtifact]]]

PROJECT_CONTEXT_SECTIONS: tuple[str, ...] = (
    "Goals",
    "Technical Constraints",
    "Coding Conventions",
    "Architecture Overview",
)  # matched case-insensitively against SECTION_ORDER[PROJECT] headings
MANDATORY_ORDER: tuple[ContextItemKind, ...] = (
    ContextItemKind.WORK_ITEM,
    ContextItemKind.WORKFLOW_STATE,
    ContextItemKind.HANDOVER,
    ContextItemKind.FEATURE_CONTEXT,
    ContextItemKind.BUG_CONTEXT,
    ContextItemKind.PROJECT_CONTEXT,
    ContextItemKind.DECISION,
    ContextItemKind.APPROVED_ARTIFACT,
)

_PROJECT_DOC_ID = "project"
_TRANSITION_TAIL = 5  # §40 step 5: transition history tail
_MANDATORY_SCORE = 1.0
_AI_PREFIX = ".ai/"
_TRANSITION_HEADER = (
    "| seq | at | from | to | event | actor | reason |",
    "|---|---|---|---|---|---|---|",
)


class DefaultContextManager:
    """Builds the mandatory context tier for one work item."""

    def __init__(  # noqa: PLR0917 - positional parameters fixed by the E01-S24 contract
        self,
        workflow: WorkflowManager,
        items: WorkflowRepository,
        memory: MemoryManager,
        hooks: HookManager,
        ledger: LedgerManager,
        clock: Clock,
        *,
        head_resolver: Callable[[], Awaitable[Sha]],
        freshness: FreshnessProbe | None = None,
        handovers: HandoverLookup | None = None,
        decisions: DecisionLookup | None = None,
        artifacts: ArtifactLookup | None = None,
    ) -> None:
        """Wire the manager.

        Args:
            workflow: Loads the item and its ancestors.
            items: Transition history of the item.
            memory: Reads feature, bug and project documents.
            hooks: Fires ``ON_CONTEXT_STALE``.
            ledger: Kept for the ranked tier; ``CONTEXT_FRESHNESS`` belongs to `MemoryManager`
                (E04-S03), so nothing is written here (WBS §3.5).
            clock: Stamps ``built_at`` and hook contexts.
            head_resolver: HEAD of the run's worktree.
            freshness: Assesses a document against HEAD; without it no item is flagged.
            handovers: Latest open handover document of an item.
            decisions: ACCEPTED decisions relevant to an item and affected systems.
            artifacts: Approved artifacts whose scope covers the item.
        """
        self._workflow = workflow
        self._items = items
        self._memory = memory
        self._hooks = hooks
        self._ledger = ledger
        self._clock = clock
        self._head = head_resolver
        self._freshness = freshness
        self._handovers = handovers
        self._decisions = decisions
        self._artifacts = artifacts

    def token_budget_for(
        self, effort: Effort, context_window_tokens: int, max_output_tokens: int
    ) -> int:
        """See `walk.context.budget.token_budget_for`."""
        return token_budget_for(effort, context_window_tokens, max_output_tokens)

    async def build(self, request: ContextRequest) -> ContextBundle:
        """Build the mandatory tier in §40 order; mandatory items are never trimmed.

        Raises:
            WorkItemNotFound: The item (or an ancestor on its parent chain) does not exist.
            HookFailed: A FAIL_CLOSED ``ON_CONTEXT_STALE`` hook failed.
        """
        item = await self._workflow.get(request.work_item_id)
        head = await self._head()
        stale = _StaleReporter(self._hooks, self._clock, item, request)
        items = [_work_item(item), await self._workflow_state(item)]
        if self._handovers is not None:
            handover = await self._handovers(item.id)
            if handover is not None:
                items.append(await self._doc_item(ContextItemKind.HANDOVER, handover, head, stale))
        for kind, doc_id in await self._context_documents(item):
            items.append(await self._context_item(kind, doc_id, head, stale))
        project = await self._project_item(head, stale)
        if project is not None:
            items.append(project)
        if self._decisions is not None:
            accepted = [
                d for d in await self._decisions(item, []) if d.status is DecisionStatus.ACCEPTED
            ]
            items.extend(_decision_item(d) for d in sorted(accepted, key=lambda d: d.id))
        if self._artifacts is not None:
            artifacts = sorted(await self._artifacts(item), key=lambda a: a.id)
            items.extend(_artifact_item(a) for a in artifacts)
        total = sum(i.tokens_estimate for i in items)
        if total > request.token_budget:
            _LOG.warning(
                "mandatory context exceeds the token budget",
                extra={"work_item_id": item.id, "tokens": total, "budget": request.token_budget},
            )
        return ContextBundle(
            request=request,
            items=items,
            total_tokens_estimate=total,
            excluded_count=0,
            built_at=self._clock.now(),
            head_commit=head,
        )

    async def _workflow_state(self, item: WorkItem) -> ContextItem:
        rows = await self._items.transitions(item.id, limit=_TRANSITION_TAIL)
        lines = [
            f"state: {item.state.value}",
            f"state_version: {item.state_version}",
            f"fix_loops: {item.fix_loops}",
            f"blocked_reason: {item.blocked_reason or 'none'}",
            "",
            "Recent transitions (newest first):",
        ]
        lines.extend(
            [*_TRANSITION_HEADER, *map(_transition_row, rows)] if rows else ["(no transitions yet)"]
        )
        return _mandatory(
            f"{ContextItemKind.WORKFLOW_STATE.value}:{item.id}",
            ContextItemKind.WORKFLOW_STATE,
            f"Workflow state of {item.id}",
            "\n".join(lines),
        )

    async def _context_documents(self, item: WorkItem) -> list[tuple[ContextItemKind, str]]:
        if isinstance(item, Bug):
            docs = [(ContextItemKind.BUG_CONTEXT, item.id)]
            if item.related_feature_id is not None:
                docs.append((ContextItemKind.FEATURE_CONTEXT, item.related_feature_id))
            return docs
        feature_id = await self._nearest_feature(item)
        return [] if feature_id is None else [(ContextItemKind.FEATURE_CONTEXT, feature_id)]

    async def _nearest_feature(self, item: WorkItem) -> str | None:
        if item.kind is WorkItemKind.FEATURE:
            return item.id
        seen: set[str] = set()
        parent = item.parent_id
        while parent is not None and parent not in seen:
            seen.add(parent)
            ancestor = await self._workflow.get(parent)
            if ancestor.kind is WorkItemKind.FEATURE:
                return ancestor.id
            parent = ancestor.parent_id
        return None

    async def _context_item(
        self, kind: ContextItemKind, doc_id: str, head: Sha, stale: "_StaleReporter"
    ) -> ContextItem:
        try:
            doc = await self._memory.read(doc_id)
        except DocumentNotFound:
            # Tell the agent explicitly instead of letting it assume (§138 hallucinated state).
            content = f"(no context document yet for {doc_id})"
            return _mandatory(f"{kind.value}:{doc_id}", kind, f"{doc_id} context", content)
        return await self._doc_item(kind, doc, head, stale)

    async def _project_item(self, head: Sha, stale: "_StaleReporter") -> ContextItem | None:
        try:
            doc = await self._memory.read(_PROJECT_DOC_ID)
        except DocumentNotFound:
            return None
        by_name = {name.casefold(): body for name, body in doc.sections.items()}
        parts = [
            f"## {name}\n\n{by_name[name.casefold()]}"
            for name in PROJECT_CONTEXT_SECTIONS
            if name.casefold() in by_name
        ]
        content = "\n\n".join(parts) or (
            f"(project context has none of: {', '.join(PROJECT_CONTEXT_SECTIONS)})"
        )
        assessment, flagged = await stale.check(self._freshness, doc, head)
        return _mandatory(
            f"{ContextItemKind.PROJECT_CONTEXT.value}:{_PROJECT_DOC_ID}",
            ContextItemKind.PROJECT_CONTEXT,
            doc.front_matter.title,
            content,
            source_path=_AI_PREFIX + doc.path,
            freshness=assessment,
            requires_verification=flagged,
        )

    async def _doc_item(
        self, kind: ContextItemKind, doc: MemoryDocument, head: Sha, stale: "_StaleReporter"
    ) -> ContextItem:
        assessment, flagged = await stale.check(self._freshness, doc, head)
        return _mandatory(
            f"{kind.value}:{doc.front_matter.id}",
            kind,
            doc.front_matter.title,
            render_document(doc),
            source_path=_AI_PREFIX + doc.path,
            freshness=assessment,
            requires_verification=flagged,
        )


class _StaleReporter:
    """Runs the freshness probe and fires ``ON_CONTEXT_STALE`` for non-current documents."""

    def __init__(
        self, hooks: HookManager, clock: Clock, item: WorkItem, request: ContextRequest
    ) -> None:
        self._hooks = hooks
        self._clock = clock
        self._item = item
        self._request = request

    async def check(
        self, probe: FreshnessProbe | None, doc: MemoryDocument, head: Sha
    ) -> tuple[FreshnessAssessment | None, bool]:
        if probe is None:
            return None, False
        assessment = await probe(doc, head)
        if assessment is None or assessment.status is FreshnessStatus.CURRENT:
            return assessment, False
        ctx = HookContext(
            name=HookName.ON_CONTEXT_STALE,
            at=self._clock.now(),
            project_key=self._item.project_key,
            work_item_id=self._item.id,
            role=self._request.role,
            payload={
                "doc_id": doc.front_matter.id,
                "status": assessment.status.value,
                "reason": assessment.reason,
            },
        )
        await self._hooks.fire(HookName.ON_CONTEXT_STALE, ctx)
        return assessment, True


def _mandatory(
    item_id: str,
    kind: ContextItemKind,
    title: str,
    content: str,
    *,
    source_path: str | None = None,
    freshness: FreshnessAssessment | None = None,
    requires_verification: bool = False,
) -> ContextItem:
    return ContextItem(
        id=item_id,
        kind=kind,
        title=title,
        content=content,
        tokens_estimate=estimate_tokens(content),
        score=_MANDATORY_SCORE,
        freshness=freshness,
        requires_verification=requires_verification,
        source_path=source_path,
        mandatory=True,
    )


def _work_item(item: WorkItem) -> ContextItem:
    content = json.dumps(item.model_dump(mode="json"), sort_keys=True, indent=2)
    return _mandatory(
        f"{ContextItemKind.WORK_ITEM.value}:{item.id}",
        ContextItemKind.WORK_ITEM,
        f"{item.id} {item.title}",
        content,
    )


def _transition_row(row: WorkItemTransition) -> str:
    cells = [
        str(row.seq),
        row.at.isoformat(),
        row.from_state.value,
        row.to_state.value,
        row.event,
        row.actor_role.value,
        row.reason or "",
    ]
    return "| " + " | ".join(cells) + " |"


def _decision_item(decision: Decision) -> ContextItem:
    lines = [
        f"# {decision.id}: {decision.topic}",
        "",
        f"- category: {decision.category.value}",
        f"- status: {decision.status.value}",
        f"- owner: {decision.owner.value}",
        f"- decided_at: {decision.decided_at.isoformat()}",
        f"- affected_systems: {', '.join(decision.affected_systems) or 'none'}",
        f"- related_work_items: {', '.join(decision.related_work_items) or 'none'}",
        "",
        "## Outcome",
        "",
        decision.outcome,
        "",
        "## Rationale",
        "",
        decision.rationale,
        "",
        "## Alternatives",
        "",
        *([f"- {alt}" for alt in decision.alternatives] or ["(none recorded)"]),
    ]
    return _mandatory(
        f"{ContextItemKind.DECISION.value}:{decision.id}",
        ContextItemKind.DECISION,
        decision.topic,
        "\n".join(lines),
    )


def _artifact_item(artifact: ApprovedArtifact) -> ContextItem:
    # Metadata only: the payload never enters the context (§40 step 4).
    metadata = {
        "id": artifact.id,
        "kind": artifact.kind.value,
        "title": artifact.title,
        "status": artifact.status.value,
        "version": artifact.version,
        "scope": artifact.scope,
        "content_sha256": artifact.content_sha256,
    }
    return _mandatory(
        f"{ContextItemKind.APPROVED_ARTIFACT.value}:{artifact.id}",
        ContextItemKind.APPROVED_ARTIFACT,
        artifact.title,
        json.dumps(metadata, sort_keys=True),
    )
