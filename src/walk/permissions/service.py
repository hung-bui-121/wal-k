"""Default permission manager: pure rule evaluation plus approval persistence (ADR-0006)."""

import fnmatch
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from walk.common.clock import Clock
from walk.common.errors import ConfigError
from walk.common.ids import ApprovalRequestId, ProjectKey, RunId, WorkItemId
from walk.common.models import JsonDict, WalkModel
from walk.common.roles import AgentRole
from walk.hooks.models import HookContext, HookName
from walk.hooks.protocols import HookManager
from walk.permissions.matching import (
    _deny_pattern_hit,  # package-internal helper shared with command_allowed
    command_allowed,
    match_tool,
    path_inside_worktree,
    tool_pattern_specificity,
)
from walk.permissions.models import (
    ApprovalRequest,
    ApprovalState,
    Approver,
    PermissionDecision,
    PermissionEffect,
    PermissionRule,
    ProtectedAction,
    ToolCallRequest,
)
from walk.permissions.repository import ApprovalRepository
from walk.persistence import IdSequenceStore, UnitOfWork
from walk.telemetry.models import LedgerEvent, LedgerEventKind
from walk.telemetry.protocols import LedgerManager

logger = logging.getLogger(__name__)

_APPROVAL_PREFIX: Final = "APV"
# Higher = more restrictive; an extra rule may not be less restrictive than an overlapping
# kernel rule that denies or requires approval (ADR-0013 D-4).
_RESTRICTIVENESS: Final = {
    PermissionEffect.ALLOW: 0,
    PermissionEffect.REQUIRE_APPROVAL: 1,
    PermissionEffect.DENY: 2,
}


def _deny(rule: PermissionRule | None, reason: str) -> PermissionDecision:
    return PermissionDecision(effect=PermissionEffect.DENY, matched_rule=rule, reason=reason)


def _overlaps(a: str, b: str) -> bool:
    """True iff two tool patterns can name a common tool."""
    return match_tool(a, b) or match_tool(b, a)


def _relative_posix(path: str, worktree: str) -> str:
    root = Path(worktree).resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve().relative_to(root).as_posix()


class DefaultPermissionManager:
    """`PermissionManager` over an in-memory rule set and the ``approval_requests`` table."""

    def __init__(  # noqa: PLR0917 - positional parameters fixed by the E01-S15 contract
        self,
        rules: list[PermissionRule],
        protected: list[ProtectedAction],
        repo: ApprovalRepository,
        ledger: LedgerManager,
        hooks: HookManager,
        ids: IdSequenceStore,
        clock: Clock,
        *,
        project_key: ProjectKey,
    ) -> None:
        """Wire the manager.

        Args:
            rules: Kernel rule set (defaults merged with the project's permissions.yaml).
            protected: §92 protected actions, by tool name.
            repo: Approval request rows.
            ledger: Write point for ``APPROVAL_REQUESTED`` / ``APPROVAL_DECIDED``.
            hooks: Fires ``ON_PROTECTED_ACTION_REQUESTED``.
            ids: Allocates ``APV-`` ids.
            clock: Stamps requests and decisions.
            project_key: Project of this kernel database; ledger events and hook contexts
                require it and the approval methods do not receive one.
        """
        self._rules = list(rules)
        self._protected = {action.name: action for action in protected}
        self._repo = repo
        self._ledger = ledger
        self._hooks = hooks
        self._ids = ids
        self._clock = clock
        self._project_key = project_key

    def rules_for(
        self, role: AgentRole, extra: Sequence[PermissionRule] = ()
    ) -> list[PermissionRule]:
        """Kernel rules of ``role`` followed by the surviving ``extra`` rules of ``role``.

        An extra rule is dropped (with a warning) when it is less restrictive than an
        overlapping kernel rule that denies the whole tool or requires approval, e.g. an ALLOW
        on a tool the kernel denies. Rules repeating an earlier ``(tool, effect)`` are dropped.
        """
        kernel = [rule for rule in self._rules if rule.role == role]
        guarding = [
            rule
            for rule in kernel
            if rule.effect is PermissionEffect.REQUIRE_APPROVAL
            or (rule.effect is PermissionEffect.DENY and not rule.command_patterns)
        ]
        merged: list[PermissionRule] = []
        seen: set[tuple[str, PermissionEffect]] = set()
        for rule in [*kernel, *(r for r in extra if r.role == role)]:
            key = (rule.tool, rule.effect)
            if key in seen:
                continue
            if rule not in kernel and any(
                _overlaps(rule.tool, k.tool)
                and _RESTRICTIVENESS[rule.effect] < _RESTRICTIVENESS[k.effect]
                for k in guarding
            ):
                logger.warning(
                    "widening permission rule dropped",
                    extra={"role": role.value, "tool": rule.tool, "effect": rule.effect.value},
                )
                continue
            seen.add(key)
            merged.append(rule)
        return merged

    def decide(self, request: ToolCallRequest) -> PermissionDecision:
        """Evaluate ``request`` against the role's rules (ADR-0006 D-3).

        Most specific matching tool pattern wins; within it DENY > REQUIRE_APPROVAL > ALLOW.
        A DENY rule with command patterns denies matching commands only. Shell commands must
        match an ALLOW pattern of the winning group (unless it requires approval) and no DENY
        pattern of any matching rule. Every path must resolve inside the worktree and match
        the ALLOW rules' path patterns when they have any. A protected action turns ALLOW and
        REQUIRE_APPROVAL into REQUIRE_APPROVAL by its approver; DENY stays DENY. No matching
        rule → DENY ``no matching rule``. Reads the filesystem only to resolve paths.
        """
        scored = [
            (tool_pattern_specificity(rule.tool, request.tool), rule)
            for rule in self._rules
            if rule.role == request.role
        ]
        matching = [(score, rule) for score, rule in scored if score > 0]
        if not matching:
            return _deny(None, "no matching rule")
        top = max(score for score, _ in matching)
        group = [rule for score, rule in matching if score == top]
        for rule in group:
            if rule.effect is PermissionEffect.DENY and (
                not rule.command_patterns or request.command is None
            ):
                return _deny(rule, rule.reason or f"denied by rule {rule.tool!r}")
        approvals = [r for r in group if r.effect is PermissionEffect.REQUIRE_APPROVAL]
        allows = [r for r in group if r.effect is PermissionEffect.ALLOW]
        pattern_denies = [
            r for _, r in matching if r.effect is PermissionEffect.DENY and r.command_patterns
        ]
        if request.command is not None:
            denied = self._check_command(request.command, approvals, allows, pattern_denies)
            if denied is not None:
                return denied
        for path in request.paths:
            denied = _check_path(path, request.worktree_path, allows or approvals)
            if denied is not None:
                return denied
        return self._grant(request.tool, approvals, allows)

    def _grant(
        self, tool: str, approvals: list[PermissionRule], allows: list[PermissionRule]
    ) -> PermissionDecision:
        """Final effect once no check denied: protected action, then approval, then allow."""
        protected = self._protected.get(tool)
        if protected is not None:
            reason = (
                f"protected action {protected.name} requires {protected.approver.value} approval"
            )
            return PermissionDecision(
                effect=PermissionEffect.REQUIRE_APPROVAL,
                matched_rule=(approvals or allows)[0],
                reason=reason,
            )
        if approvals:
            rule = approvals[0]
            approver = rule.approver.value if rule.approver else Approver.USER.value
            return PermissionDecision(
                effect=PermissionEffect.REQUIRE_APPROVAL,
                matched_rule=rule,
                reason=rule.reason or f"rule {rule.tool!r} requires {approver} approval",
            )
        return PermissionDecision(
            effect=PermissionEffect.ALLOW,
            matched_rule=allows[0],
            reason=allows[0].reason or f"allowed by rule {allows[0].tool!r}",
        )

    @staticmethod
    def _check_command(
        command: str,
        approvals: list[PermissionRule],
        allows: list[PermissionRule],
        pattern_denies: list[PermissionRule],
    ) -> PermissionDecision | None:
        hit = _deny_pattern_hit(command, pattern_denies)
        if hit is not None:
            rule = next(r for r in pattern_denies if hit in r.command_patterns)
            return _deny(rule, f"command matches deny pattern {hit!r}")
        if approvals:
            return None
        allowed, reason = command_allowed(command, allows, [])
        return None if allowed else _deny(allows[0] if allows else None, reason)

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
        """Persist a PENDING request with ``APPROVAL_REQUESTED``; then fire the hook.

        Raises:
            ConfigError: If ``kind`` is not an approval kind.
        """
        payload = request.model_dump(mode="json") if isinstance(request, WalkModel) else request
        async with UnitOfWork(self._repo.db) as uow:
            approval_id = self._ids.bind(uow).next_sequence(_APPROVAL_PREFIX)
            try:
                approval = ApprovalRequest.model_validate(
                    {
                        "id": approval_id,
                        "kind": kind,
                        "approver": approver,
                        "requested_by_role": requested_by,
                        "run_id": run_id,
                        "work_item_id": work_item_id,
                        "payload": payload,
                        "requested_at": self._clock.now(),
                    }
                )
            except ValidationError as exc:
                msg = f"invalid approval kind or payload: {kind!r}"
                raise ConfigError(msg, detail={"kind": kind}) from exc
            await self._repo.insert(approval, uow)
            facts: JsonDict = {
                "approval_id": approval.id,
                "kind": approval.kind,
                "approver": approval.approver.value,
            }
            event = LedgerEvent(
                kind=LedgerEventKind.APPROVAL_REQUESTED,
                at=approval.requested_at,
                project_key=self._project_key,
                actor_role=requested_by,
                work_item_id=work_item_id,
                run_id=run_id,
                outcome="OK",
                payload=facts,
            )
            await self._ledger.append(event, uow=uow)
            context = HookContext(
                name=HookName.ON_PROTECTED_ACTION_REQUESTED,
                at=approval.requested_at,
                project_key=self._project_key,
                work_item_id=work_item_id,
                run_id=run_id,
                role=requested_by,
                payload=facts,
            )
            uow.after_commit(lambda: self._fire(context))
        return approval

    async def decide_approval(
        self,
        approval_id: ApprovalRequestId,
        approve: bool,  # noqa: FBT001 - positional flag fixed by INTERFACES §1.10
        *,
        by: str,
        note: str | None,
    ) -> ApprovalRequest:
        """Set APPROVED or DENIED with ``APPROVAL_DECIDED`` (actor = the approver's role).

        Raises:
            ConfigError: If the id is unknown or the request is no longer PENDING.
        """
        async with UnitOfWork(self._repo.db) as uow:
            current = await self._repo.get(approval_id)
            if current is None:
                msg = f"unknown approval request: {approval_id}"
                raise ConfigError(msg, detail={"approval_id": approval_id})
            if current.state is not ApprovalState.PENDING:
                msg = f"approval request {approval_id} is not pending ({current.state.value})"
                raise ConfigError(msg, detail={"approval_id": approval_id})
            decided = current.model_copy(
                update={
                    "state": ApprovalState.APPROVED if approve else ApprovalState.DENIED,
                    "decided_at": self._clock.now(),
                    "decided_by": by,
                    "decision_note": note,
                }
            )
            await self._repo.upsert(decided, uow)
            event = LedgerEvent(
                kind=LedgerEventKind.APPROVAL_DECIDED,
                at=decided.decided_at,
                project_key=self._project_key,
                actor_role=AgentRole(decided.approver.value),
                work_item_id=decided.work_item_id,
                run_id=decided.run_id,
                outcome="OK",
                payload={
                    "approval_id": decided.id,
                    "kind": decided.kind,
                    "approver": decided.approver.value,
                    "state": decided.state.value,
                    "decided_by": by,
                },
            )
            await self._ledger.append(event, uow=uow)
        return decided

    async def pending(self, approver: Approver | None = None) -> list[ApprovalRequest]:
        """PENDING requests, optionally for one approver, oldest first."""
        return await self._repo.pending(approver)

    async def _fire(self, context: HookContext) -> None:
        await self._hooks.fire(context.name, context)


def _check_path(path: str, worktree: str, rules: list[PermissionRule]) -> PermissionDecision | None:
    rule = rules[0] if rules else None
    if not path_inside_worktree(path, worktree):
        return _deny(rule, f"path {path!r} is outside the worktree")
    patterns = [pattern for r in rules for pattern in r.path_patterns]
    if patterns:
        relative = _relative_posix(path, worktree)
        if not any(fnmatch.fnmatchcase(relative, pattern) for pattern in patterns):
            return _deny(rule, f"path {path!r} matches no allowed path pattern")
    return None
