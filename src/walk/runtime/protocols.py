"""Runtime protocols (INTERFACES §1.13)."""

from typing import Protocol

from walk.agents.models import AgentInstance, AgentOutput, Handover
from walk.budgets.models import BudgetDimension
from walk.common.ids import RunId, Sha, WorkItemId
from walk.common.models import JsonDict
from walk.context.models import ContextBundleRef
from walk.debate.models import Debate
from walk.effort.models import EffortResolution
from walk.model_router.models import RoutingDecision
from walk.permissions.models import PermissionDecision, ToolCallRequest
from walk.runtime.models import AgentRun, AppliedEffects, Checkpoint, CheckpointKind
from walk.workflow.models import WorkItem, WorkItemState


class CheckpointManager(Protocol):
    """§41, §54, §89; ADR-0002. Hosted by walk.runtime."""

    async def checkpoint(
        self,
        run: AgentRun,
        kind: CheckpointKind,
        *,
        handover: Handover | None = None,
        workflow_state: WorkItemState | None = None,
        budget_consumed: dict[BudgetDimension, float] | None = None,
        context_manifest: ContextBundleRef | None = None,
    ) -> Checkpoint:
        """WIP commit, checkpoints row, optional handover document, ON_AGENT_CHECKPOINT.

        1) WIP commit on run.branch (`wip(<work_item>): checkpoint <seq>`; skipped if clean)
        via GitProvider (idempotent key); 2) insert checkpoints row; 3) if handover given →
        MemoryManager.write_handover; 4) fire ON_AGENT_CHECKPOINT; ledger CHECKPOINT_CREATED.
        ``workflow_state`` is required except for START and PAUSE (read from the work item);
        ``budget_consumed``/``context_manifest`` default to empty (E01-S25).
        """
        ...

    async def latest(self, run_id: RunId) -> Checkpoint | None:
        """The run's newest checkpoint."""
        ...

    async def latest_for_item(self, work_item_id: WorkItemId) -> Checkpoint | None:
        """The newest checkpoint of any run of the item."""
        ...

    async def build_handover(
        self, run: AgentRun, reason: str, partial_output: AgentOutput | None
    ) -> Handover:
        """From run's accumulated findings/changes/decisions + git diff names.

        Never from the model transcript (§22).
        """
        ...

    async def interrupted_runs(self, current_instance: str) -> list[AgentRun]:
        """Runs another kernel instance left RUNNING or PAUSED_FOR_APPROVAL."""
        ...


class AgentExecutor(Protocol):
    """Runs AgentRun tasks. Hosted by walk.runtime (the engine behind Orchestrator)."""

    async def start(
        self,
        agent: AgentInstance,
        item: WorkItem,
        purpose: str,
        *,
        handover: Handover | None = None,
        parent_run_id: RunId | None = None,
        debate: Debate | None = None,
        routing: RoutingDecision | None = None,
        effort_resolution: EffortResolution | None = None,
    ) -> AgentRun:
        """ARCHITECTURE.md §3.2 steps 3-7.

        Returns immediately with RUNNING run; completion wakes the orchestrator. ``routing``
        and ``effort_resolution`` are the scheduler's decisions, written by the executor as
        ``MODEL_SELECTED``/``EFFORT_SET`` (E01-S27).
        """
        ...

    async def resume_native(self, checkpoint: Checkpoint) -> AgentRun:
        """Same model, provider-side session resume (ModelAdapter.resume).

        Raises NotResumable when the session cannot be continued; the caller (RecoveryManager)
        then continues with `start(handover=…)` (E01-S28).
        """
        ...

    async def cancel(self, run_id: RunId, reason: str) -> AgentRun:
        """Cancel the run; ConfigError when called from the run's own task (E02-S08)."""
        ...

    async def pause(self, run_id: RunId) -> AgentRun:
        """Pause the run; ConfigError when called from the run's own task (E02-S08)."""
        ...

    def running(self) -> list[AgentRun]:
        """Runs currently executing in this process."""
        ...


class ToolInvoker(Protocol):
    """Permission enforcement point for KERNEL tools and the authorizer for native tools."""

    async def authorize(self, request: ToolCallRequest) -> PermissionDecision:
        """PermissionManager.decide; ALLOW → ON_TOOL_BEFORE; DENY → ON_TOOL_DENIED + TOOL_DENIED.

        REQUIRE_APPROVAL → request_approval, pause run, await decision (timeout → DENY).
        """
        ...

    async def invoke(self, request: ToolCallRequest) -> JsonDict:
        """authorize() then dispatch a KERNEL tool to IntegrationManager.

        Meters TOOL_CALLS; ON_TOOL_AFTER; ledger TOOL_INVOKED.
        """
        ...


class OutputApplier(Protocol):
    """Applies AgentOutput effects in a fixed order (ARCHITECTURE.md §3.2 step 6)."""

    async def apply(
        self,
        run: AgentRun,
        output: AgentOutput,
        *,
        start_head: Sha,
        handoff: Checkpoint | None = None,
    ) -> AppliedEffects:
        """Apply ``output`` for ``run``; ``start_head`` is the worktree HEAD at run start.

        ``handoff``: the PARTIAL output's HANDOFF checkpoint; its ids reach the transition
        hooks (E02-S08).
        """
        ...


class SandboxManager(Protocol):
    """§60 isolated worktrees; ADR-0009 §D-5."""

    async def create(self, run: AgentRun, item: WorkItem) -> str:
        """`git worktree add <repo>/.walk/worktrees/<run_id> <branch>`; installs guard hooks.

        branch = item.branch or feat/<id>-<slug>; writes projections; returns path.
        """
        ...

    async def adopt(self, run: AgentRun, previous: AgentRun, item: WorkItem) -> str:
        """Child run (fallback / recovery / native resume) reuses previous.worktree_path.

        Re-adds it on previous.branch with guard hooks when the directory is missing. Never
        `create` for a child run (one branch, one worktree). E01-S28.
        """
        ...

    async def remove(self, run: AgentRun, *, keep_branch: bool = True) -> None:
        """Remove the run's worktree; delete the branch only when asked and not protected."""
        ...


class BoundaryAuditor(Protocol):
    """Post-run repository boundary audit (§91; ADR-0006 D-5)."""

    def audit(
        self,
        worktree_path: str,
        changed_files: list[str],
        allowed_paths: list[str],
        forbidden_paths: list[str],
    ) -> list[str]:
        """Returns violations (paths).

        Non-empty → run FAILED_BOUNDARY, changes discarded (git checkout -- .).
        """
        ...
