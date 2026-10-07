from collections.abc import Callable
from typing import Any

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_git_provider import FakeGitProvider
from tests.runtime.conftest import RUN_A, STORY_ID, RunFactory
from walk.budgets import (
    BudgetDimension,
    BudgetExhausted,
    BudgetRepository,
    BudgetScope,
    BudgetSubject,
    DefaultBudgetManager,
)
from walk.common.errors import ConfigError, PermissionDenied, ToolCrashed
from walk.common.models import JsonDict
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, Hook, HookContext, HookName
from walk.memory import DefaultMemoryManager
from walk.permissions import (
    ApprovalRepository,
    ApprovalState,
    Approver,
    DefaultPermissionManager,
    PermissionDecision,
    PermissionEffect,
    PermissionRule,
    ProtectedAction,
    ToolCallRequest,
)
from walk.persistence import Database, IdempotencyStore, IdSequenceStore
from walk.runtime import (
    APPROVAL_TIMEOUT_S,
    AgentRun,
    AgentRunRepository,
    AgentRunState,
    CheckpointKind,
    CheckpointRepository,
    DefaultCheckpointManager,
    DefaultToolInvoker,
    HandoverRepository,
    RunNotFound,
    ToolInvoker,
)
from walk.telemetry import DefaultLedgerManager, LedgerEvent, LedgerEventKind
from walk.tools import DefaultToolRegistry, ToolKind, load_tool_specs

DEV = AgentRole.SENIOR_DEV
RULES = [
    PermissionRule(role=DEV, tool="edit", effect=PermissionEffect.ALLOW),
    PermissionRule(role=DEV, tool="bash", effect=PermissionEffect.ALLOW, command_patterns=[".*"]),
    PermissionRule(
        role=DEV, tool="git-cli", effect=PermissionEffect.ALLOW, command_patterns=[r"^git "]
    ),
    PermissionRule(
        role=DEV,
        tool="git-cli",
        effect=PermissionEffect.DENY,
        command_patterns=[r"push\s+--force"],
        reason="no force pushes",
    ),
    PermissionRule(role=DEV, tool="git.commit", effect=PermissionEffect.ALLOW),
    PermissionRule(role=DEV, tool="git.merge_protected", effect=PermissionEffect.ALLOW),
    PermissionRule(role=DEV, tool="jira.comment", effect=PermissionEffect.ALLOW),
    PermissionRule(role=DEV, tool="git.push", effect=PermissionEffect.DENY, reason="CI pushes"),
    PermissionRule(
        role=DEV,
        tool="webfetch",
        effect=PermissionEffect.REQUIRE_APPROVAL,
        approver=Approver.LEAD_DEV,
    ),
]
PROTECTED = [ProtectedAction(name="git.merge_protected")]


class _SpyPermissions(DefaultPermissionManager):
    decided: list[ToolCallRequest]

    def decide(self, request: ToolCallRequest) -> PermissionDecision:
        self.decided.append(request)
        return super().decide(request)


class _ScriptedWaiter:
    """Decides the request through the permission manager, as `walk approve|deny` would."""

    def __init__(
        self, runs: AgentRunRepository, permissions: DefaultPermissionManager, *, approve: bool
    ) -> None:
        self._runs = runs
        self._permissions = permissions
        self._approve = approve
        self.calls: list[tuple[str, int]] = []
        self.states_during_wait: list[AgentRunState] = []

    async def wait(self, approval_id: str, timeout_s: int) -> ApprovalState:
        self.calls.append((approval_id, timeout_s))
        run = await self._runs.get(RUN_A)
        assert run is not None
        self.states_during_wait.append(run.state)
        await self._permissions.decide_approval(
            approval_id, approve=self._approve, by="user", note=None
        )
        return ApprovalState.APPROVED if self._approve else ApprovalState.DENIED


class _Env:
    def __init__(
        self,
        invoker: DefaultToolInvoker,
        permissions: _SpyPermissions,
        waiter: _ScriptedWaiter,
        budgets: DefaultBudgetManager,
        fired: list[HookContext],
    ) -> None:
        self.invoker = invoker
        self.permissions = permissions
        self.waiter = waiter
        self.budgets = budgets
        self.fired = fired

    def hooks_fired(self, name: HookName) -> list[HookContext]:
        return [ctx for ctx in self.fired if ctx.name is name]


EnvFactory = Callable[..., _Env]


@pytest.fixture
def make_env(
    *,
    db: Database,
    ledger: DefaultLedgerManager,
    hooks: DefaultHookManager,
    memory: DefaultMemoryManager,
    idempotency: IdempotencyStore,
    runs: AgentRunRepository,
    fake_clock: FakeClock,
) -> EnvFactory:
    fired: list[HookContext] = []

    async def record(ctx: HookContext) -> None:
        fired.append(ctx)

    for name in (HookName.ON_TOOL_BEFORE, HookName.ON_TOOL_AFTER, HookName.ON_TOOL_DENIED):
        hooks.register(Hook(name=name, id=f"test.{name.value}", kind="builtin"), record)

    def build(*, approve: bool = True) -> _Env:
        permissions = _SpyPermissions(
            RULES,
            PROTECTED,
            ApprovalRepository(db),
            ledger,
            hooks,
            IdSequenceStore(db),
            fake_clock,
            project_key="DEMO",
        )
        permissions.decided = []
        budgets = DefaultBudgetManager(db, BudgetRepository(db), ledger, hooks, fake_clock)
        checkpoints = DefaultCheckpointManager(
            db,
            runs,
            CheckpointRepository(db),
            HandoverRepository(db),
            FakeGitProvider(),
            memory,
            hooks,
            ledger,
            IdSequenceStore(db),
            idempotency,
            fake_clock,
            project_key="DEMO",
        )
        waiter = _ScriptedWaiter(runs, permissions, approve=approve)
        invoker = DefaultToolInvoker(
            permissions,
            DefaultToolRegistry(load_tool_specs([])),
            budgets,
            hooks,
            ledger,
            runs,
            checkpoints,
            waiter,
            fake_clock,
            project_key="DEMO",
        )
        return _Env(invoker, permissions, waiter, budgets, fired)

    return build


@pytest.fixture
async def run(insert_run: RunFactory) -> AgentRun:
    return await insert_run(
        RUN_A, state=AgentRunState.RUNNING, worktree_path="/wt", branch="feat/x"
    )


def _request(tool: str, kind: ToolKind, **fields: object) -> ToolCallRequest:
    data: dict[str, object] = {
        "run_id": RUN_A,
        "role": DEV,
        "tool": tool,
        "kind": kind,
        "arguments": {},
        "worktree_path": "/wt",
    }
    data.update(fields)
    return ToolCallRequest.model_validate(data)


async def _events(ledger: DefaultLedgerManager, kind: LedgerEventKind) -> list[LedgerEvent]:
    return await ledger.query(kinds=[kind])


async def test_authorize_allow_fires_hook_and_logs(
    make_env: EnvFactory, run: AgentRun, ledger: DefaultLedgerManager
) -> None:
    env = make_env()
    invoker: ToolInvoker = env.invoker
    request = _request("edit", ToolKind.PROVIDER_NATIVE, paths=["/wt/src/A.cs"])

    decision = await invoker.authorize(request)

    assert decision.effect is PermissionEffect.ALLOW
    before = env.hooks_fired(HookName.ON_TOOL_BEFORE)
    assert len(before) == 1
    assert before[0].payload == {"tool": "edit", "command": None, "paths": ["/wt/src/A.cs"]}
    assert before[0].run_id == RUN_A
    events = await _events(ledger, LedgerEventKind.TOOL_INVOKED)
    assert len(events) == 1
    assert events[0].outcome == "OK"
    assert events[0].payload["phase"] == "pre"
    assert events[0].payload["matched_rule"] == "edit"
    assert (events[0].run_id, events[0].work_item_id, events[0].tool) == (RUN_A, STORY_ID, "edit")
    assert events[0].actor_role is DEV
    del run


async def test_authorize_deny_logs_and_fires(
    make_env: EnvFactory, run: AgentRun, ledger: DefaultLedgerManager
) -> None:
    env = make_env()
    request = _request("write", ToolKind.PROVIDER_NATIVE, role=AgentRole.QC)

    decision = await env.invoker.authorize(request)

    assert decision.effect is PermissionEffect.DENY
    denied = await _events(ledger, LedgerEventKind.TOOL_DENIED)
    assert len(denied) == 1
    assert denied[0].outcome == "DENIED"
    assert denied[0].payload["reason"] == "no matching rule"
    assert denied[0].actor_role is AgentRole.QC
    assert len(env.hooks_fired(HookName.ON_TOOL_DENIED)) == 1
    assert await _events(ledger, LedgerEventKind.TOOL_INVOKED) == []
    del run


async def test_authorize_identifies_cli_subtool(make_env: EnvFactory, run: AgentRun) -> None:
    env = make_env()
    request = _request("bash", ToolKind.PROVIDER_NATIVE, command="git push --force origin main")

    decision = await env.invoker.authorize(request)

    assert decision.effect is PermissionEffect.DENY
    assert "push" in decision.reason
    evaluated = env.permissions.decided[-1]
    assert (evaluated.tool, evaluated.kind) == ("git-cli", ToolKind.CLI)
    allowed = await env.invoker.authorize(
        _request("bash", ToolKind.PROVIDER_NATIVE, command="dotnet test")
    )
    assert allowed.effect is PermissionEffect.DENY  # dotnet is identified; no rule allows it
    assert env.permissions.decided[-1].tool == "dotnet"
    plain = await env.invoker.authorize(_request("bash", ToolKind.PROVIDER_NATIVE, command="ls"))
    assert plain.effect is PermissionEffect.ALLOW
    assert env.permissions.decided[-1].tool == "bash"
    del run


async def test_require_approval_pauses_then_allows(
    make_env: EnvFactory,
    run: AgentRun,
    ledger: DefaultLedgerManager,
    runs: AgentRunRepository,
    checkpoints: CheckpointRepository,
) -> None:
    env = make_env(approve=True)
    request = _request("git.merge_protected", ToolKind.KERNEL, arguments={"branch": "main"})

    decision = await env.invoker.authorize(request)

    assert decision.effect is PermissionEffect.ALLOW
    assert decision.approval_request_id is not None
    assert env.waiter.calls == [(decision.approval_request_id, APPROVAL_TIMEOUT_S)]
    assert env.waiter.states_during_wait == [AgentRunState.PAUSED_FOR_APPROVAL]
    stored = await runs.get(RUN_A)
    assert stored is not None
    assert stored.state is AgentRunState.RUNNING
    pause = await checkpoints.latest(RUN_A)
    assert pause is not None
    assert pause.kind is CheckpointKind.PAUSE
    requested = await _events(ledger, LedgerEventKind.APPROVAL_REQUESTED)
    assert len(requested) == 1
    assert requested[0].payload["kind"] == "PROTECTED_ACTION"
    invoked = await _events(ledger, LedgerEventKind.TOOL_INVOKED)
    assert invoked[-1].payload["approval_request_id"] == decision.approval_request_id
    sequence = [
        e.kind
        for e in await ledger.query(run_id=RUN_A)
        if e.kind is not LedgerEventKind.HOOK_EXECUTED
    ]
    assert sequence == [
        LedgerEventKind.APPROVAL_REQUESTED,
        LedgerEventKind.CHECKPOINT_CREATED,
        LedgerEventKind.APPROVAL_DECIDED,
        LedgerEventKind.TOOL_INVOKED,
    ]
    del run


async def test_require_approval_denied(
    make_env: EnvFactory, run: AgentRun, ledger: DefaultLedgerManager, runs: AgentRunRepository
) -> None:
    env = make_env(approve=False)

    decision = await env.invoker.authorize(_request("git.merge_protected", ToolKind.KERNEL))

    assert decision.effect is PermissionEffect.DENY
    assert decision.reason == "approval denied"
    assert decision.approval_request_id is not None
    denied = await _events(ledger, LedgerEventKind.TOOL_DENIED)
    assert len(denied) == 1
    assert denied[0].payload["approval_request_id"] == decision.approval_request_id
    stored = await runs.get(RUN_A)
    assert stored is not None
    assert stored.state is AgentRunState.RUNNING
    del run


async def test_invoke_dispatches_meters_and_logs(
    make_env: EnvFactory, run: AgentRun, ledger: DefaultLedgerManager, fake_clock: FakeClock
) -> None:
    env = make_env()
    await env.budgets.ensure(BudgetScope.TASK, STORY_ID, None, {BudgetDimension.TOOL_CALLS: 10})
    calls: list[ToolCallRequest] = []

    async def commit(request: ToolCallRequest) -> JsonDict:
        calls.append(request)
        fake_clock.advance(0.25)
        return {"sha": "3f9c2e1"}

    env.invoker.register_handler("git.commit", commit)

    result = await env.invoker.invoke(_request("git.commit", ToolKind.KERNEL))

    assert result == {"sha": "3f9c2e1"}
    assert len(calls) == 1
    budget = (await env.budgets.headroom(_subject()))[BudgetDimension.TOOL_CALLS]
    assert budget == 9
    invoked = await _events(ledger, LedgerEventKind.TOOL_INVOKED)
    post = [e for e in invoked if e.payload["phase"] == "post"]
    assert len(post) == 1
    assert post[0].duration_ms == 250
    assert post[0].outcome == "OK"
    after = env.hooks_fired(HookName.ON_TOOL_AFTER)
    assert len(after) == 1
    assert after[0].payload["ok"] is True
    with pytest.raises(ConfigError, match="already registered"):
        env.invoker.register_handler("git.commit", commit)
    del run


def _subject() -> BudgetSubject:
    return BudgetSubject(project_key="DEMO", role=DEV, work_item_id=STORY_ID, run_id=RUN_A)


async def test_invoke_denied_raises_without_dispatch(make_env: EnvFactory, run: AgentRun) -> None:
    env = make_env()
    calls: list[ToolCallRequest] = []

    async def push(request: ToolCallRequest) -> JsonDict:
        calls.append(request)
        return {}

    env.invoker.register_handler("git.push", push)

    with pytest.raises(PermissionDenied, match="CI pushes"):
        await env.invoker.invoke(_request("git.push", ToolKind.KERNEL))
    assert calls == []
    del run


async def test_invoke_budget_exhausted_raises(make_env: EnvFactory, run: AgentRun) -> None:
    env = make_env()
    await env.budgets.ensure(BudgetScope.TASK, STORY_ID, None, {BudgetDimension.TOOL_CALLS: 1})
    calls: list[ToolCallRequest] = []

    async def commit(request: ToolCallRequest) -> JsonDict:
        calls.append(request)
        return {}

    env.invoker.register_handler("git.commit", commit)

    with pytest.raises(BudgetExhausted) as caught:
        await env.invoker.invoke(_request("git.commit", ToolKind.KERNEL))
    assert calls == []
    assert caught.value.detail["budget_id"] == f"TASK:{STORY_ID}:TOOL_CALLS"
    assert caught.value.detail["hard_action"] == "BLOCK"
    del run


async def test_invoke_handler_failure_logged_and_wrapped(
    make_env: EnvFactory, run: AgentRun, ledger: DefaultLedgerManager
) -> None:
    env = make_env()

    async def broken(request: ToolCallRequest) -> JsonDict:
        del request
        msg = "disk full"
        raise RuntimeError(msg)

    async def typed(request: ToolCallRequest) -> JsonDict:
        del request
        msg = "permission revoked"
        raise PermissionDenied(msg)

    env.invoker.register_handler("git.commit", broken)
    env.invoker.register_handler("jira.comment", typed)

    with pytest.raises(ToolCrashed, match="disk full") as caught:
        await env.invoker.invoke(_request("git.commit", ToolKind.KERNEL))
    assert isinstance(caught.value.__cause__, RuntimeError)
    with pytest.raises(PermissionDenied, match="revoked"):
        await env.invoker.invoke(_request("jira.comment", ToolKind.KERNEL))
    failed = [
        e for e in await _events(ledger, LedgerEventKind.TOOL_INVOKED) if e.outcome == "FAILED"
    ]
    assert [e.tool for e in failed] == ["git.commit", "jira.comment"]
    assert env.hooks_fired(HookName.ON_TOOL_AFTER) == []
    del run


async def test_invoke_rejects_non_kernel_or_unhandled(make_env: EnvFactory, run: AgentRun) -> None:
    env = make_env()

    with pytest.raises(ConfigError, match="KERNEL"):
        await env.invoker.invoke(_request("edit", ToolKind.PROVIDER_NATIVE))
    with pytest.raises(ConfigError, match=r"no kernel handler for jira\.comment"):
        await env.invoker.invoke(_request("jira.comment", ToolKind.KERNEL))
    del run


async def test_record_result_posts_event_and_meters(
    make_env: EnvFactory, run: AgentRun, ledger: DefaultLedgerManager
) -> None:
    env = make_env()
    await env.budgets.ensure(BudgetScope.TASK, STORY_ID, None, {BudgetDimension.TOOL_CALLS: 5})
    request = _request("edit", ToolKind.PROVIDER_NATIVE, paths=["src/A.cs"])

    await env.invoker.record_result(request, {"ok": True}, duration_ms=42)
    await env.invoker.record_result(request, {"ok": False}, duration_ms=7)

    invoked = await _events(ledger, LedgerEventKind.TOOL_INVOKED)
    assert [(e.payload["phase"], e.duration_ms, e.outcome) for e in invoked] == [
        ("post", 42, "OK"),
        ("post", 7, "FAILED"),
    ]
    headroom = await env.budgets.headroom(_subject())
    assert headroom[BudgetDimension.TOOL_CALLS] == 3
    after = env.hooks_fired(HookName.ON_TOOL_AFTER)
    assert [ctx.payload for ctx in after] == [
        {"tool": "edit", "paths": ["src/A.cs"], "ok": True},
        {"tool": "edit", "paths": ["src/A.cs"], "ok": False},
    ]
    del run


async def test_record_result_raises_when_budget_exhausted(
    make_env: EnvFactory, run: AgentRun, ledger: DefaultLedgerManager
) -> None:
    env = make_env()
    await env.budgets.ensure(BudgetScope.TASK, STORY_ID, None, {BudgetDimension.TOOL_CALLS: 1})

    with pytest.raises(BudgetExhausted):
        await env.invoker.record_result(
            _request("edit", ToolKind.PROVIDER_NATIVE), {"ok": True}, duration_ms=1
        )
    assert len(await _events(ledger, LedgerEventKind.TOOL_INVOKED)) == 1  # recorded first
    del run


async def test_authorizer_for_binds_run(make_env: EnvFactory, run: AgentRun) -> None:
    env = make_env()
    authorizer = env.invoker.authorizer_for(run)
    fields: dict[str, Any] = {  # no run_id: the adapter left it out
        "role": AgentRole.QC,
        "tool": "edit",
        "kind": ToolKind.PROVIDER_NATIVE,
        "arguments": {},
        "paths": ["/wt/src/A.cs"],
        "worktree_path": "",
    }
    partial = ToolCallRequest.model_construct(**fields)

    decision = await authorizer(partial)

    evaluated = env.permissions.decided[-1]
    assert (evaluated.run_id, evaluated.role, evaluated.worktree_path) == (RUN_A, DEV, "/wt")
    assert decision.effect is PermissionEffect.ALLOW


async def test_unknown_run_is_rejected(make_env: EnvFactory, run: AgentRun) -> None:
    env = make_env()
    request = _request("edit", ToolKind.PROVIDER_NATIVE, run_id="RUN-01J99999999999999999999999")
    with pytest.raises(RunNotFound):
        await env.invoker.authorize(request)
    del run


async def test_rule_approval_for_uncatalogued_tool(
    make_env: EnvFactory, run: AgentRun, ledger: DefaultLedgerManager
) -> None:
    env = make_env(approve=True)

    decision = await env.invoker.authorize(_request("webfetch", ToolKind.PROVIDER_NATIVE))

    assert decision.effect is PermissionEffect.ALLOW
    requested = await _events(ledger, LedgerEventKind.APPROVAL_REQUESTED)
    assert requested[0].payload["kind"] == "TOOL_CALL"
    assert requested[0].payload["approver"] == "LEAD_DEV"
    del run
