"""Permission service protocol (INTERFACES §1.10)."""

from collections.abc import Sequence
from typing import Protocol

from walk.common.ids import ApprovalRequestId, RunId, WorkItemId
from walk.common.models import JsonDict, WalkModel
from walk.common.roles import AgentRole
from walk.permissions.models import (
    ApprovalRequest,
    Approver,
    PermissionDecision,
    PermissionRule,
    ToolCallRequest,
)


class PermissionManager(Protocol):
    """§31, §92. Policy evaluation. Hosted by walk.permissions. Enforcement points: ADR-0006."""

    def rules_for(
        self, role: AgentRole, extra: Sequence[PermissionRule] = ()
    ) -> list[PermissionRule]:
        """Kernel defaults + `.ai/agents/permissions.yaml` + `extra`, de-duplicated.

        `extra` is the constitution's tool_permissions, passed by AgentManager. Project/extra
        rules may only narrow (ADR-0013 D-4).
        """
        ...

    def decide(self, request: ToolCallRequest) -> PermissionDecision:
        """Pure. Most-specific `tool` pattern wins; tie → DENY > REQUIRE_APPROVAL > ALLOW.

        Shell: command must match an ALLOW command_pattern and no DENY pattern. Paths outside
        worktree → DENY. Protected action → REQUIRE_APPROVAL(approver).
        """
        ...

    async def request_approval(
        self,
        request: ToolCallRequest | WalkModel | JsonDict,
        *,
        kind: str,
        approver: Approver,
        requested_by: AgentRole,
        run_id: RunId | None,
        work_item_id: WorkItemId | None,
    ) -> ApprovalRequest:
        """Persists PENDING; fires ON_PROTECTED_ACTION_REQUESTED; ledger APPROVAL_REQUESTED.

        `request` is a `ToolCallRequest`, an `Escalation` (any kernel model) or plain JSON.
        """
        ...

    async def decide_approval(
        self,
        approval_id: ApprovalRequestId,
        approve: bool,  # noqa: FBT001 - positional flag fixed by INTERFACES §1.10
        *,
        by: str,
        note: str | None,
        expired: bool = False,
    ) -> ApprovalRequest:
        """CLI `walk approve|deny`. Ledger APPROVAL_DECIDED; wakes the paused run.

        ``expired=True`` (kernel timeout, ``approve=False``) records EXPIRED instead of DENIED.
        """
        ...

    async def pending(self, approver: Approver | None = None) -> list[ApprovalRequest]:
        """PENDING approval requests, optionally for one approver, oldest first."""
        ...
