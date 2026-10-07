"""The tool permission enforcement point (ADR-0006 D-1 points 1-3, D-3/D-4/D-7; §30-§32, §92).

Provider-native calls are authorised through the run session's authorizer (`authorizer_for`,
e.g. Claude's ``can_use_tool``) and reported back with `record_result`; KERNEL tools are
authorised, metered and dispatched by `invoke`. ``REQUIRE_APPROVAL`` pauses the run until the
approval is decided or times out, except for an advisory authorizer (``wait_for_approval=False``,
a provider that reports tool calls after they ran, e.g. Codex): it records the decision and
returns it unchanged, and the executor rejects the run's effects (ADR-0006 D-5).
``APPROVAL_REQUESTED``/``APPROVAL_DECIDED`` belong to the permission manager; this module writes
only ``TOOL_INVOKED``/``TOOL_DENIED`` (WBS §3.5).
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Final, Literal, Protocol

from walk.budgets.errors import BudgetExhausted
from walk.budgets.models import BudgetDimension, BudgetSubject
from walk.budgets.protocols import BudgetManager
from walk.common.clock import Clock
from walk.common.errors import (
    ConfigError,
    GuardRejected,
    PermissionDenied,
    ToolCrashed,
    WalkError,
)
from walk.common.ids import ApprovalRequestId, ProjectKey, ToolName
from walk.common.models import JsonDict
from walk.hooks.models import HookContext, HookName
from walk.hooks.protocols import HookManager
from walk.permissions.models import (
    ApprovalRequest,
    ApprovalState,
    Approver,
    PermissionDecision,
    PermissionEffect,
    ToolCallRequest,
)
from walk.permissions.protocols import PermissionManager
from walk.permissions.repository import ApprovalRepository
from walk.runtime.errors import RunNotFound
from walk.runtime.models import AgentRun, AgentRunState, CheckpointKind
from walk.runtime.protocols import CheckpointManager
from walk.runtime.repository import AgentRunRepository
from walk.telemetry.models import LedgerEvent, LedgerEventKind
from walk.telemetry.protocols import LedgerManager
from walk.tools.models import ToolKind
from walk.tools.protocols import ToolRegistry

KernelToolHandler = Callable[[ToolCallRequest], Awaitable[JsonDict]]
APPROVAL_TIMEOUT_S = 24 * 3600  # ADR-0006 D-4 default

_SHELL_TOOL: Final = "bash"
_DENIED_REASONS: Final = {
    ApprovalState.DENIED: "approval denied",
    ApprovalState.EXPIRED: "approval expired",
}
_REUSABLE: Final = frozenset({ApprovalState.PENDING, ApprovalState.APPROVED})
_MS_PER_S: Final = 1000
_EXPIRY_NOTE: Final = "timeout"
_KERNEL_ACTOR: Final = "kernel"
_Outcome = Literal["OK", "FAILED", "DENIED"]


class ApprovalWaiter(Protocol):
    """Waits until an approval request is decided (E02-S11: `EventApprovalWaiter`)."""

    async def wait(self, approval_id: ApprovalRequestId, timeout_s: int) -> ApprovalState:
        """APPROVED, DENIED or EXPIRED (a timeout expires the request)."""
        ...


class PollingApprovalWaiter:
    """`ApprovalWaiter` that polls ``approval_requests``; expires the request on timeout."""

    def __init__(
        self,
        approvals: ApprovalRepository,
        clock: Clock,
        *,
        permissions: PermissionManager,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        interval_s: float = 1.0,
    ) -> None:
        """Wire the waiter.

        Args:
            approvals: Read side of the approval requests.
            clock: Measures the timeout.
            permissions: Expires a timed-out request (it owns ``APPROVAL_DECIDED``).
            sleep: Awaited between polls; injected so tests do not wait.
            interval_s: Seconds between polls.
        """
        self._approvals = approvals
        self._clock = clock
        self._permissions = permissions
        self._sleep = sleep
        self._interval_s = interval_s

    async def wait(self, approval_id: ApprovalRequestId, timeout_s: int) -> ApprovalState:
        """Poll until APPROVED, DENIED or EXPIRED; expire the request after ``timeout_s``.

        Raises:
            ConfigError: The approval request does not exist.
        """
        started = self._clock.now()
        while True:
            state = await self._state(approval_id)
            if state is not ApprovalState.PENDING:
                return state
            if (self._clock.now() - started).total_seconds() >= timeout_s:
                return await self._expire(approval_id)
            await self._sleep(self._interval_s)

    async def _state(self, approval_id: ApprovalRequestId) -> ApprovalState:
        approval = await self._approvals.get(approval_id)
        if approval is None:
            msg = f"unknown approval request {approval_id}"
            raise ConfigError(msg, detail={"approval_id": approval_id})
        return approval.state

    async def _expire(self, approval_id: ApprovalRequestId) -> ApprovalState:
        try:
            await self._permissions.decide_approval(
                approval_id, approve=False, by=_KERNEL_ACTOR, note=_EXPIRY_NOTE, expired=True
            )
        except GuardRejected:
            # Decided between the last poll and the expiry: the decision stands.
            return await self._state(approval_id)
        return ApprovalState.EXPIRED


class DefaultToolInvoker:
    """`ToolInvoker`: decides, logs, hooks, meters and dispatches every tool call."""

    def __init__(  # noqa: PLR0917 - positional parameters fixed by the E01-S26 contract
        self,
        permissions: PermissionManager,
        tools: ToolRegistry,
        budgets: BudgetManager,
        hooks: HookManager,
        ledger: LedgerManager,
        runs: AgentRunRepository,
        checkpoints: CheckpointManager,
        waiter: ApprovalWaiter,
        clock: Clock,
        *,
        handlers: dict[ToolName, KernelToolHandler] | None = None,
        approval_timeout_s: int = APPROVAL_TIMEOUT_S,
        project_key: ProjectKey,
        approvals: ApprovalRepository | None = None,
    ) -> None:
        """Wire the invoker.

        Args:
            permissions: Decides requests and records approval requests.
            tools: Identifies CLI sub-tools inside shell commands; knows protected actions.
            budgets: Meters ``TOOL_CALLS``.
            hooks: Fires ``ON_TOOL_BEFORE``/``ON_TOOL_AFTER``/``ON_TOOL_DENIED``.
            ledger: Write point for ``TOOL_INVOKED``/``TOOL_DENIED``.
            runs: Run lookup and the pause/resume state changes.
            checkpoints: Takes the PAUSE checkpoint while an approval is pending.
            waiter: Waits for approval decisions.
            clock: Stamps events and measures handler durations.
            handlers: KERNEL tool handlers by tool name.
            approval_timeout_s: How long a run waits for an approval.
            project_key: Project of the ledger events, hook contexts and budgets.
            approvals: Approval requests of earlier runs of the item; a run that continues an
                interrupted one (recovery) reuses its PENDING or unused APPROVED request for
                the same tool instead of asking again (E02-S11). None disables the reuse.
        """
        self._permissions = permissions
        self._tools = tools
        self._budgets = budgets
        self._hooks = hooks
        self._ledger = ledger
        self._runs = runs
        self._checkpoints = checkpoints
        self._waiter = waiter
        self._clock = clock
        self._handlers: dict[ToolName, KernelToolHandler] = dict(handlers or {})
        self._approval_timeout_s = approval_timeout_s
        self._project_key = project_key
        self._approvals = approvals

    def register_handler(self, tool: ToolName, handler: KernelToolHandler) -> None:
        """Dispatch ``tool`` to ``handler``.

        Raises:
            ConfigError: ``tool`` already has a handler.
        """
        if tool in self._handlers:
            msg = f"a kernel handler for {tool} is already registered"
            raise ConfigError(msg, detail={"tool": tool})
        self._handlers[tool] = handler

    def authorizer_for(
        self, run: AgentRun, *, wait_for_approval: bool = True
    ) -> Callable[[ToolCallRequest], Awaitable[PermissionDecision]]:
        """The `RunSession.permission_authorizer` of ``run``.

        The bound run is authoritative: requests are evaluated with ``run.id`` and
        ``run.role``, and with ``run.worktree_path`` when the adapter left the worktree empty.
        ``wait_for_approval=False`` gives the post-hoc (advisory) authorizer of a provider whose
        tool calls already ran (E01-S27 Notes): REQUIRE_APPROVAL is recorded like a denial and
        returned unchanged; the run is never paused.
        """

        async def authorize(request: ToolCallRequest) -> PermissionDecision:
            given = {name: getattr(request, name) for name in request.model_fields_set}
            bound: JsonDict = {**given, "run_id": run.id, "role": run.role}
            if not given.get("worktree_path"):
                bound["worktree_path"] = run.worktree_path or ""
            return await self._authorize(
                ToolCallRequest.model_validate(bound), wait_for_approval=wait_for_approval
            )

        return authorize

    async def authorize(self, request: ToolCallRequest) -> PermissionDecision:
        """Decide ``request``; ALLOW → ON_TOOL_BEFORE + TOOL_INVOKED(pre).

        DENY → TOOL_DENIED + ON_TOOL_DENIED. REQUIRE_APPROVAL → approval request, run
        PAUSED_FOR_APPROVAL with a PAUSE checkpoint, wait, run RUNNING again; approved → ALLOW
        (with ``approval_request_id``), otherwise DENY. A shell command naming a CLI tool
        (``git push …``) is evaluated as that tool.

        Raises:
            RunNotFound: ``request.run_id`` is not a known run.
        """
        return await self._authorize(request, wait_for_approval=True)

    async def _authorize(
        self, request: ToolCallRequest, *, wait_for_approval: bool
    ) -> PermissionDecision:
        run = await self._run(request)
        evaluated = self._identify(request)
        decision = self._permissions.decide(evaluated)
        if decision.effect is PermissionEffect.REQUIRE_APPROVAL and wait_for_approval:
            decision = await self._await_approval(run, evaluated, decision)
        if decision.effect is PermissionEffect.ALLOW:
            await self._fire(
                HookName.ON_TOOL_BEFORE,
                run,
                evaluated,
                {"tool": evaluated.tool, "command": evaluated.command, "paths": evaluated.paths},
            )
            await self._log(
                LedgerEventKind.TOOL_INVOKED, run, evaluated, "OK", _pre_payload(decision)
            )
            return decision
        await self._log(
            LedgerEventKind.TOOL_DENIED, run, evaluated, "DENIED", _denied_payload(decision)
        )
        await self._fire(
            HookName.ON_TOOL_DENIED,
            run,
            evaluated,
            {"tool": evaluated.tool, "reason": decision.reason},
        )
        return decision

    async def invoke(self, request: ToolCallRequest) -> JsonDict:
        """Authorise, meter ``TOOL_CALLS`` and dispatch a KERNEL tool to its handler.

        Raises:
            ConfigError: Not a KERNEL tool, or no handler is registered for it.
            PermissionDenied: The call was denied (also after a denied approval).
            BudgetExhausted: The ``TOOL_CALLS`` budget is exhausted.
            ToolCrashed: The handler failed with a non-kernel exception (kernel errors
                propagate unchanged); ``TOOL_INVOKED(outcome=FAILED)`` is written either way.
        """
        if request.kind is not ToolKind.KERNEL:
            msg = f"invoke dispatches KERNEL tools only, not {request.kind.value} {request.tool}"
            raise ConfigError(msg, detail={"tool": request.tool, "kind": request.kind.value})
        handler = self._handlers.get(request.tool)
        if handler is None:
            msg = f"no kernel handler for {request.tool}"
            raise ConfigError(msg, detail={"tool": request.tool})
        decision = await self.authorize(request)
        if decision.effect is not PermissionEffect.ALLOW:
            raise PermissionDenied(decision.reason, detail={"tool": request.tool})
        run = await self._run(request)
        await self._meter(run, request)
        started = self._clock.now()
        try:
            result = await handler(request)
        except Exception as exc:
            duration_ms = self._elapsed_ms(started)
            await self._log(
                LedgerEventKind.TOOL_INVOKED,
                run,
                request,
                "FAILED",
                {"phase": "post", "error": str(exc)},
                duration_ms=duration_ms,
            )
            if isinstance(exc, WalkError):
                raise
            msg = f"kernel tool {request.tool} failed: {exc}"
            raise ToolCrashed(msg, detail={"tool": request.tool}) from exc
        duration_ms = self._elapsed_ms(started)
        await self._log(
            LedgerEventKind.TOOL_INVOKED,
            run,
            request,
            "OK",
            {"phase": "post"},
            duration_ms=duration_ms,
        )
        await self._fire(
            HookName.ON_TOOL_AFTER,
            run,
            request,
            {"tool": request.tool, "paths": request.paths, "ok": True},
        )
        return result

    async def record_result(
        self, request: ToolCallRequest, result: JsonDict, *, duration_ms: int
    ) -> None:
        """Post event for a provider-native call (the executor calls it on TOOL_CALL_RESULT).

        Writes ``TOOL_INVOKED(phase=post)`` (``outcome`` from ``result["ok"]``), meters
        ``TOOL_CALLS`` by 1 and fires ``ON_TOOL_AFTER``.

        Raises:
            BudgetExhausted: The call was recorded but the ``TOOL_CALLS`` budget is exhausted.
        """
        run = await self._run(request)
        ok = bool(result.get("ok", True))
        await self._log(
            LedgerEventKind.TOOL_INVOKED,
            run,
            request,
            "OK" if ok else "FAILED",
            {"phase": "post"},
            duration_ms=duration_ms,
        )
        await self._fire(
            HookName.ON_TOOL_AFTER,
            run,
            request,
            {"tool": request.tool, "paths": request.paths, "ok": ok},
        )
        await self._meter(run, request)

    async def _await_approval(
        self, run: AgentRun, request: ToolCallRequest, decision: PermissionDecision
    ) -> PermissionDecision:
        approval = await self._inherited_approval(run, request)
        if approval is None:
            protected = self._protected_action(request.tool)
            rule = decision.matched_rule
            approver = (
                rule.approver if rule is not None and rule.approver is not None else Approver.USER
            )
            approval = await self._permissions.request_approval(
                request,
                kind="PROTECTED_ACTION" if protected else "TOOL_CALL",
                approver=approver,
                requested_by=request.role,
                run_id=run.id,
                work_item_id=run.work_item_id,
            )
        state = approval.state
        if state is ApprovalState.PENDING:
            paused = await self._runs.set_state(run.id, AgentRunState.PAUSED_FOR_APPROVAL)
            await self._checkpoints.checkpoint(paused, CheckpointKind.PAUSE)
            state = await self._waiter.wait(approval.id, timeout_s=self._approval_timeout_s)
            await self._runs.set_state(run.id, AgentRunState.RUNNING)
        if state is ApprovalState.APPROVED:
            return decision.model_copy(
                update={"effect": PermissionEffect.ALLOW, "approval_request_id": approval.id}
            )
        return decision.model_copy(
            update={
                "effect": PermissionEffect.DENY,
                "reason": _DENIED_REASONS.get(state, _DENIED_REASONS[ApprovalState.DENIED]),
                "approval_request_id": approval.id,
            }
        )

    async def _inherited_approval(
        self, run: AgentRun, request: ToolCallRequest
    ) -> ApprovalRequest | None:
        """The PENDING or unused APPROVED request an ancestor run made for the same tool.

        After a restart the continuing run (``parent_run_id`` chain) repeats the tool call the
        interrupted run was waiting on; it waits on, or uses, that request instead of asking
        again (E02-S11 Behavior 5). An APPROVED request is used once: a ``TOOL_INVOKED``
        carrying its id means it was consumed.
        """
        if self._approvals is None or run.parent_run_id is None:
            return None
        ancestors = await self._ancestors(run)
        for approval in await self._approvals.for_work_item(run.work_item_id):
            if (
                approval.run_id in ancestors
                and approval.state in _REUSABLE
                and approval.payload.get("tool") == request.tool
                and not await self._consumed(approval)
            ):
                return approval
        return None

    async def _ancestors(self, run: AgentRun) -> set[str]:
        found: set[str] = set()
        parent_id = run.parent_run_id
        while parent_id is not None and parent_id not in found:
            found.add(parent_id)
            parent = await self._runs.get(parent_id)
            parent_id = parent.parent_run_id if parent is not None else None
        return found

    async def _consumed(self, approval: ApprovalRequest) -> bool:
        if approval.state is not ApprovalState.APPROVED:
            return False
        events = await self._ledger.query(
            kinds=[LedgerEventKind.TOOL_INVOKED], work_item_id=approval.work_item_id
        )
        return any(e.payload.get("approval_request_id") == approval.id for e in events)

    def _identify(self, request: ToolCallRequest) -> ToolCallRequest:
        if request.tool != _SHELL_TOOL or request.command is None:
            return request
        spec = self._tools.identify(request.command)
        if spec is None:
            return request
        return request.model_copy(update={"tool": spec.name, "kind": spec.kind})

    def _protected_action(self, tool: ToolName) -> bool:
        try:
            return self._tools.get(tool).protected_action is not None
        except ConfigError:
            return False  # not in the catalogue (e.g. an unknown provider-native tool)

    async def _run(self, request: ToolCallRequest) -> AgentRun:
        run = await self._runs.get(request.run_id)
        if run is None:
            msg = f"tool call for unknown run {request.run_id}"
            raise RunNotFound(msg, detail={"run_id": request.run_id, "tool": request.tool})
        return run

    async def _meter(self, run: AgentRun, request: ToolCallRequest) -> None:
        subject = BudgetSubject(
            project_key=self._project_key,
            phase_id=None,
            role=request.role,
            work_item_id=run.work_item_id,
            run_id=run.id,
        )
        verdict = await self._budgets.meter(subject, BudgetDimension.TOOL_CALLS, 1)
        if verdict.status == "EXHAUSTED":
            budget_id = verdict.budget.id if verdict.budget is not None else None
            hard_action = verdict.hard_action.value if verdict.hard_action is not None else None
            msg = f"TOOL_CALLS budget exhausted ({budget_id})"
            raise BudgetExhausted(
                msg,
                detail={"budget_id": budget_id, "hard_action": hard_action, "tool": request.tool},
            )

    async def _log(
        self,
        kind: LedgerEventKind,
        run: AgentRun,
        request: ToolCallRequest,
        outcome: _Outcome,
        payload: JsonDict,
        *,
        duration_ms: int | None = None,
    ) -> None:
        event = LedgerEvent(
            kind=kind,
            at=self._clock.now(),
            project_key=self._project_key,
            actor_role=request.role,
            work_item_id=run.work_item_id,
            run_id=run.id,
            model_id=run.model_id,
            tool=request.tool,
            duration_ms=duration_ms,
            outcome=outcome,
            payload=payload,
        )
        await self._ledger.append(event)

    async def _fire(
        self, name: HookName, run: AgentRun, request: ToolCallRequest, payload: JsonDict
    ) -> None:
        context = HookContext(
            name=name,
            at=self._clock.now(),
            project_key=self._project_key,
            work_item_id=run.work_item_id,
            run_id=run.id,
            role=request.role,
            payload=payload,
        )
        await self._hooks.fire(name, context)

    def _elapsed_ms(self, started: datetime) -> int:
        return int((self._clock.now() - started).total_seconds() * _MS_PER_S)


def _pre_payload(decision: PermissionDecision) -> JsonDict:
    payload: JsonDict = {
        "phase": "pre",
        "matched_rule": decision.matched_rule.tool if decision.matched_rule else None,
    }
    if decision.approval_request_id is not None:
        payload["approval_request_id"] = decision.approval_request_id
    return payload


def _denied_payload(decision: PermissionDecision) -> JsonDict:
    payload: JsonDict = {
        "reason": decision.reason,
        "matched_rule": decision.matched_rule.tool if decision.matched_rule else None,
    }
    if decision.approval_request_id is not None:
        payload["approval_request_id"] = decision.approval_request_id
    return payload
