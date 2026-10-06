"""Integration service and provider-boundary protocols (INTERFACES §1.12, §2.2-§2.6)."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Literal, Protocol

from walk.common.ids import Sha, WorkItemId
from walk.common.models import Actor, JsonDict
from walk.common.roles import AgentRole
from walk.integrations.models import (
    AssetJob,
    AssetProvenance,
    AssetRequest,
    BuildTarget,
    CommitInfo,
    ComponentStatus,
    EnvironmentManifest,
    GraphNeighborhood,
    GraphNode,
    JobResult,
    PullRequestRef,
    WorkItemRef,
    WorkProviderEvent,
)
from walk.workflow.models import WorkItem, WorkItemKind, WorkItemState


class WorkProvider(Protocol):
    """§55 source of work state.

    Implementations: LocalWorkProvider [MVP], JiraWorkProvider [Stage 3].
    """

    provider: str

    async def health(self) -> ComponentStatus:
        """Report whether the provider is reachable and configured."""
        ...

    async def create(self, item: WorkItem, *, idempotency_key: str) -> WorkItemRef:
        """Create issue/record with label `walk:<item.id>`.

        Idempotent: existing key → return stored ref; else search by label before creating.
        """
        ...

    async def update(
        self, item: WorkItem, fields: dict[str, object], *, idempotency_key: str
    ) -> None:
        """Title/description/priority/labels/parent link."""
        ...

    async def transition(
        self, item: WorkItem, to_state: WorkItemState, *, idempotency_key: str
    ) -> None:
        """Map WorkItemState → provider status via status map; no-op if already there."""
        ...

    async def assign(self, item: WorkItem, role: AgentRole, *, idempotency_key: str) -> None:
        """Assignee = configured account per role (or label `walk-role:<role>`)."""
        ...

    async def comment(self, item: WorkItem, markdown: str, *, idempotency_key: str) -> None:
        """Add a Markdown comment to the item."""
        ...

    async def link(
        self,
        from_item: WorkItem,
        to_item: WorkItem,
        kind: Literal["BLOCKS", "RELATES", "PARENT"],
        *,
        idempotency_key: str,
    ) -> None:
        """Link two items."""
        ...

    async def get(self, external_ref: str) -> JsonDict:
        """Return the provider record of ``external_ref``."""
        ...

    async def query(
        self,
        *,
        states: list[WorkItemState] | None = None,
        kinds: list[WorkItemKind] | None = None,
        limit: int = 200,
    ) -> list[JsonDict]:
        """Return provider records matching the filters."""
        ...

    async def changes_since(self, since: datetime | None) -> list[WorkProviderEvent]:
        """Polling fallback (§56)."""
        ...

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> list[WorkProviderEvent]:
        """Verify signature/secret; normalise. LocalWorkProvider raises NotSupported."""
        ...

    def status_map(self) -> dict[WorkItemState, str]:
        """Kernel state → provider status name (configurable)."""
        ...


class GitProvider(Protocol):
    """§59-§60 local and remote git operations."""

    provider: str  # "git-cli"

    async def head(self, path: str) -> Sha:
        """Return the sha of HEAD in ``path``."""
        ...

    async def current_branch(self, path: str) -> str:
        """Return the checked-out branch name in ``path``."""
        ...

    async def git_path(self, path: str, name: str) -> str:
        """Absolute ``git rev-parse --git-path <name>`` of ``path`` (E02-S06).

        In a linked worktree this resolves shared files such as ``info/exclude`` in the common
        git directory; never build such paths by concatenation.
        """
        ...

    async def ensure_branch(self, name: str, base: str, *, idempotency_key: str) -> str:
        """Create ``name`` from ``base`` if absent; return the branch name."""
        ...

    async def add_worktree(self, path: str, branch: str) -> str:
        """Check out ``branch`` in a new worktree at ``path``; return its absolute path."""
        ...

    async def remove_worktree(self, path: str, *, force: bool = False) -> None:
        """Remove the worktree at ``path`` and prune stale entries."""
        ...

    async def delete_branch(self, name: str, *, protected_branches: list[str]) -> None:
        """Delete local branch ``name`` (kernel cleanup of run branches, E01-S25).

        Raises PermissionDenied if ``name`` matches a protected glob; deleting a protected
        branch is the protected action ``git.delete_branch_protected`` (ToolInvoker).
        """
        ...

    async def status(self, path: str) -> list[str]:
        """Dirty files (porcelain)."""
        ...

    async def diff_names(self, path: str, base: Sha | None = None) -> list[str]:
        """Files changed against ``base`` (default HEAD), untracked files included."""
        ...

    async def discard_changes(self, path: str) -> None:
        """Reset tracked and remove untracked changes of the worktree at ``path`` only.

        `git checkout -- .` + `git clean -fd`; the boundary-violation path (E01-S27).
        """
        ...

    async def commit_all(
        self, path: str, message: str, *, trailer_work_item: WorkItemId, idempotency_key: str
    ) -> CommitInfo | None:
        """Stages everything except forbidden paths.

        The message gets trailer `Walk-Work-Item: <id>` (§59 traceability). None if clean.
        """
        ...

    async def push(self, path: str, branch: str, *, protected_branches: list[str]) -> None:
        """Raises PermissionDenied if branch ∈ protected.

        Protected ops go through ToolInvoker with approval.
        """
        ...

    async def open_pr(
        self, branch: str, base: str, title: str, body: str, *, idempotency_key: str
    ) -> PullRequestRef:
        """Via `gh` CLI when available.

        Else records a local PR stub (LocalWorkProvider dev mode).
        """
        ...

    async def merge(
        self, pr: PullRequestRef, *, strategy: Literal["squash", "merge"], idempotency_key: str
    ) -> Sha:
        """Protected action — caller must hold an approved ApprovalRequest."""
        ...

    async def squash_wip(self, path: str, branch: str, base: Sha, message: str) -> Sha:
        """Collapse `wip(...)` checkpoint commits into one commit before PR (ADR-0002 §D-4)."""
        ...

    async def install_guard_hooks(self, path: str, protected_branches: list[str]) -> None:
        """Install the pre-commit/pre-push guard hooks for ``path`` (ADR-0006 D-1)."""
        ...

    async def is_ancestor(self, ancestor: Sha, descendant: Sha, path: str) -> bool:
        """Whether ``ancestor`` is an ancestor of ``descendant``."""
        ...

    async def merge_base(self, a: str, b: str, path: str) -> Sha:
        """`git merge-base a b`; refs or shas; no common ancestor → GitError.

        Squash base of the integration step (E03-S12).
        """
        ...

    async def changed_between(
        self, a: Sha, b: Sha, path: str, *, paths: list[str] | None = None
    ) -> list[str]:
        """Used by freshness classification (§42)."""
        ...


class UnityProvider(Protocol):
    """Unity batchmode CLI.

    Uses a small editor package `com.walk.ci` installed by bootstrap (ADR-0009 §D-6).
    """

    async def detect(self, project_path: str) -> ComponentStatus:
        """Detect the Unity editor and the `com.walk.ci` package for the project."""
        ...

    async def compile(self, project_path: str) -> JobResult:
        """Compile the project's scripts."""
        ...

    async def run_tests(
        self,
        project_path: str,
        mode: Literal["EditMode", "PlayMode"],
        *,
        filter: str | None = None,  # noqa: A002 - parameter name fixed by INTERFACES §2.4
    ) -> JobResult:
        """Run the EditMode or PlayMode test suite, optionally filtered."""
        ...

    async def build(
        self, project_path: str, target: BuildTarget, output_path: str, *, development: bool = True
    ) -> JobResult:
        """Build ``target`` into ``output_path``."""
        ...

    async def validate_assets(self, project_path: str, paths: list[str]) -> JobResult:
        """§79 [Stage 8]."""
        ...


class CiProvider(Protocol):
    """§62 orchestration of jobs for a commit; default implementation runs UnityProvider locally."""

    async def run_pipeline(
        self,
        worktree_path: str,
        commit: Sha,
        jobs: list[str],
        *,
        idempotency_key: str,
        work_item_id: WorkItemId | None = None,
    ) -> list[JobResult]:
        """Fires ON_BUILD_START/SUCCESS/FAILURE and ON_TEST_RESULT.

        Each result → EvidenceManager.record. `work_item_id` attributes hook contexts,
        evidence and BUILD_RESULT/TEST_RESULT ledger events to the item (E03-S11).
        """
        ...


class AssetProvider(Protocol):
    """§78-§80 generated-asset provider [Stage 8]."""

    provider: str

    async def health(self) -> ComponentStatus:
        """Report whether the provider is reachable and configured."""
        ...

    async def generate(self, request: AssetRequest, *, idempotency_key: str) -> AssetJob:
        """Submit a generation job."""
        ...

    async def poll(self, job_id: str) -> AssetJob:
        """Return the current job state."""
        ...

    async def download(self, job_id: str, target_dir: str) -> list[str]:
        """Download the job's outputs into ``target_dir``; return the file paths."""
        ...

    def provenance(
        self, job: AssetJob, request: AssetRequest, paths: list[str], actor: Actor
    ) -> AssetProvenance:
        """Build the §80 provenance record of a finished job."""
        ...


class CodeGraphProvider(Protocol):
    """§43 code graph (ADR-0009 §D-9)."""

    provider: str  # "graphify"

    async def health(self, repo_path: str) -> ComponentStatus:
        """Report whether the graph tool is installed and the graph is usable."""
        ...

    async def build(self, repo_path: str, *, incremental: bool = True) -> str:
        """Returns graph version/sha. Output under `<repo>/graphify-out/` (gitignored)."""
        ...

    async def mark_dirty(self, paths: list[str]) -> None:
        """Mark ``paths`` for the next incremental build."""
        ...

    async def neighbors(self, repo_path: str, seeds: list[str], depth: int) -> GraphNeighborhood:
        """Return the graph around ``seeds``.

        seeds = file paths or symbol names (feature_context.relevant_files / affected_systems).
        """
        ...

    async def impact(self, repo_path: str, changed_paths: list[str]) -> list[GraphNode]:
        """Reverse dependencies — used by §72 CHANGE analysis and Lead Dev review context."""
        ...

    async def query(self, repo_path: str, question: str) -> str:
        """Free-text graph query (graphify query) returned as markdown.

        Used sparingly at HIGH+ effort.
        """
        ...


class IntegrationManager(Protocol):
    """§26-§27, §55-§56, §59. Facade over providers.

    Owns idempotency and inbound event ingestion. Hosted by walk.integrations.
    """

    work: WorkProvider
    git: GitProvider
    unity: UnityProvider | None
    code_graph: CodeGraphProvider | None
    assets: dict[str, AssetProvider]
    ci: CiProvider | None

    async def preflight(self, required: list[str]) -> EnvironmentManifest:
        """§26 checks; writes `.ai/project/environment.yaml`.

        Compares with previous manifest → drift (§27).
        """
        ...

    async def ingest(self, event: WorkProviderEvent) -> None:
        """Dedup by delivery_id (webhook_deliveries).

        Then WorkflowManager.apply_external_transition; Orchestrator.wake().
        """
        ...

    async def reconcile(self, since: datetime | None) -> int:
        """Poll `work.changes_since(since)` and ingest each.

        Updates work_provider_sync. Returns count.
        """
        ...

    async def with_idempotency(
        self, key: str, operation: str, fn: Callable[[], Awaitable[str]]
    ) -> str:
        """If key exists → return stored result_ref.

        Else run fn, store (key, result_ref) in the caller's transaction.
        """
        ...
