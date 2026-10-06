"""Permission contracts (§31, §92; DOMAIN-MODEL §3 permissions enums, §4.5; ADR-0006)."""

import re
from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from walk.common.ids import ApprovalRequestId, RunId, ToolName, WorkItemId
from walk.common.models import FrozenModel, JsonDict, WalkModel, utcnow
from walk.common.roles import AgentRole
from walk.tools.models import ToolKind


class PermissionEffect(StrEnum):
    """§31: allow / deny / conditional (= REQUIRE_APPROVAL)."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class Approver(StrEnum):
    """Who may decide an approval request; every value is also an `AgentRole` value."""

    USER = "USER"
    PRODUCT_OWNER = "PRODUCT_OWNER"
    LEAD_DEV = "LEAD_DEV"
    ORCHESTRATOR = "ORCHESTRATOR"


class ApprovalState(StrEnum):
    """Lifecycle of an `ApprovalRequest`."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"


class PermissionRule(WalkModel):
    """§31 one rule.

    Matching: most specific `tool` pattern wins, then DENY > REQUIRE_APPROVAL > ALLOW (ADR-0006).
    """

    role: AgentRole = Field(description="Role the rule applies to.")
    tool: str = Field(description="ToolName or glob: 'git.commit', 'git.*', 'bash', '*'")
    effect: PermissionEffect = Field(description="What the rule decides.")
    command_patterns: list[str] = Field(
        default_factory=list,
        description=(
            "For shell tools: regexes the command must match (ALLOW) or must not match (DENY)"
        ),
    )
    path_patterns: list[str] = Field(
        default_factory=list, description="For file tools: globs relative to worktree"
    )
    approver: Approver | None = Field(
        default=None, description="Required when effect == REQUIRE_APPROVAL"
    )
    reason: str = Field(default="", description="Why the rule exists; shown on denial.")

    @field_validator("command_patterns")
    @classmethod
    def _patterns_compile(cls, patterns: list[str]) -> list[str]:
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                msg = f"invalid command pattern {pattern!r}: {exc}"
                raise ValueError(msg) from exc
        return patterns

    @model_validator(mode="after")
    def _approval_needs_approver(self) -> Self:
        if self.effect is PermissionEffect.REQUIRE_APPROVAL and self.approver is None:
            msg = "a REQUIRE_APPROVAL rule needs an approver"
            raise ValueError(msg)
        return self


class ProtectedAction(WalkModel):
    """§92 configurable protected actions."""

    name: str = Field(description="git.merge_protected, store.publish, credentials.change, …")
    approver: Approver = Field(default=Approver.USER, description="Who must approve it.")
    description: str = Field(default="", description="What the action does.")


class ToolCallRequest(FrozenModel):
    """What the enforcement point evaluates."""

    run_id: RunId = Field(description="Run asking for the tool call.")
    role: AgentRole = Field(description="Role of the run.")
    tool: ToolName = Field(description="Requested tool.")
    kind: ToolKind = Field(description="Kind of the requested tool.")
    arguments: JsonDict = Field(description="Tool arguments as sent by the agent.")
    command: str | None = Field(default=None, description="Shell command, for shell tools.")
    paths: list[str] = Field(default_factory=list, description="Paths a file tool touches.")
    worktree_path: str = Field(description="Sandbox worktree of the run.")


class PermissionDecision(FrozenModel):
    """Outcome of `PermissionManager.decide`."""

    effect: PermissionEffect = Field(description="Decided effect.")
    matched_rule: PermissionRule | None = Field(description="Rule that decided; None = default.")
    reason: str = Field(description="Human-readable justification.")
    approval_request_id: ApprovalRequestId | None = Field(
        default=None, description="Set by the enforcement point once an approval is requested."
    )


class ApprovalRequest(WalkModel):
    """Pending human/authority approval (§92, §51 Level 3). Persisted in `approval_requests`."""

    id: ApprovalRequestId = Field(description="APV-<n>.")
    kind: Literal[
        "TOOL_CALL", "PROTECTED_ACTION", "ESCALATION", "ARTIFACT_CHANGE", "IMPROVEMENT"
    ] = Field(description="What needs approval.")
    approver: Approver = Field(description="Who must decide.")
    requested_by_role: AgentRole = Field(description="Role that asked.")
    run_id: RunId | None = Field(description="Run waiting for the decision.")
    work_item_id: WorkItemId | None = Field(description="Work item concerned.")
    payload: JsonDict = Field(description="The request being approved, as JSON.")
    state: ApprovalState = Field(default=ApprovalState.PENDING, description="Lifecycle state.")
    requested_at: datetime = Field(default_factory=utcnow, description="When it was requested.")
    decided_at: datetime | None = Field(default=None, description="When it was decided.")
    decided_by: str | None = Field(default=None, description="Who decided it.")
    decision_note: str | None = Field(default=None, description="Note given with the decision.")
    expires_at: datetime | None = Field(default=None, description="Deadline (E02-S11).")
