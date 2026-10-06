"""Agent run execution: runs, worktree sandboxes, checkpoints, the boundary audit and the executor.

§41, §54, §81, §89, §126.
"""

from walk.runtime.boundary import (
    DEFAULT_ALLOWED_PATHS,
    DEFAULT_FORBIDDEN_PATHS,
    DefaultBoundaryAuditor,
)
from walk.runtime.checkpoints import DefaultCheckpointManager
from walk.runtime.errors import CheckpointNotFound, RunNotFound
from walk.runtime.executor import (
    MAX_REPAIR_TURNS,
    REPAIR_INSTRUCTION,
    RESUME_INSTRUCTION,
    RETRY_DELAYS_S,
    RUN_TIMEOUT_S,
    DefaultAgentExecutor,
)
from walk.runtime.inputs import AgentInputBuilder, build_run_session, expected_output_for
from walk.runtime.metering import UsageMeter
from walk.runtime.models import (
    AgentOutputStatus,
    AgentRun,
    AgentRunState,
    AppliedEffects,
    Checkpoint,
    CheckpointKind,
)
from walk.runtime.output_applier import IMPLEMENT_OUTPUT_EVENTS, DefaultOutputApplier
from walk.runtime.protocols import (
    AgentExecutor,
    BoundaryAuditor,
    CheckpointManager,
    OutputApplier,
    SandboxManager,
    ToolInvoker,
)
from walk.runtime.recovery import RecoveryManager, RecoveryReport
from walk.runtime.repository import AgentRunRepository, CheckpointRepository, HandoverRepository
from walk.runtime.sandbox import WORKTREES_DIR, DefaultSandboxManager, branch_name_for
from walk.runtime.tool_invoker import (
    APPROVAL_TIMEOUT_S,
    ApprovalWaiter,
    DefaultToolInvoker,
    KernelToolHandler,
    PollingApprovalWaiter,
)

__all__ = [
    "APPROVAL_TIMEOUT_S",
    "DEFAULT_ALLOWED_PATHS",
    "DEFAULT_FORBIDDEN_PATHS",
    "IMPLEMENT_OUTPUT_EVENTS",
    "MAX_REPAIR_TURNS",
    "REPAIR_INSTRUCTION",
    "RESUME_INSTRUCTION",
    "RETRY_DELAYS_S",
    "RUN_TIMEOUT_S",
    "WORKTREES_DIR",
    "AgentExecutor",
    "AgentInputBuilder",
    "AgentOutputStatus",
    "AgentRun",
    "AgentRunRepository",
    "AgentRunState",
    "AppliedEffects",
    "ApprovalWaiter",
    "BoundaryAuditor",
    "Checkpoint",
    "CheckpointKind",
    "CheckpointManager",
    "CheckpointNotFound",
    "CheckpointRepository",
    "DefaultAgentExecutor",
    "DefaultBoundaryAuditor",
    "DefaultCheckpointManager",
    "DefaultOutputApplier",
    "DefaultSandboxManager",
    "DefaultToolInvoker",
    "HandoverRepository",
    "KernelToolHandler",
    "OutputApplier",
    "PollingApprovalWaiter",
    "RecoveryManager",
    "RecoveryReport",
    "RunNotFound",
    "SandboxManager",
    "ToolInvoker",
    "UsageMeter",
    "branch_name_for",
    "build_run_session",
    "expected_output_for",
]
