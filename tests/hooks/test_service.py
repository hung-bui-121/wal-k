import asyncio
from datetime import UTC, datetime

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.hooks import (
    DefaultHookManager,
    Hook,
    HookCallable,
    HookContext,
    HookExecutionRepository,
    HookFailed,
    HookFailPolicy,
    HookManager,
    HookName,
)
from walk.persistence import Database
from walk.telemetry import DefaultLedgerManager, LedgerEventKind, LedgerRepository

AT = datetime(2025, 12, 31, 23, 59, tzinfo=UTC)
NAME = HookName.ON_TASK_START
RUN = "RUN-01J00000000000000000000000"


@pytest.fixture
def ledger(db: Database, fake_clock: FakeClock) -> DefaultLedgerManager:
    return DefaultLedgerManager(db, LedgerRepository(db), SequentialIdFactory(), fake_clock)


@pytest.fixture
def manager(
    db: Database, ledger: DefaultLedgerManager, fake_clock: FakeClock
) -> DefaultHookManager:
    return DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)


def _ctx(name: HookName = NAME) -> HookContext:
    return HookContext(
        name=name,
        at=AT,
        project_key="DEMO",
        work_item_id="STORY-0001",
        run_id=RUN,
        role=AgentRole.SENIOR_DEV,
    )


def _hook(
    hook_id: str,
    *,
    name: HookName = NAME,
    kind: str = "builtin",
    priority: int = 100,
    policy: HookFailPolicy = HookFailPolicy.LOG_AND_CONTINUE,
    required: bool = False,
    enabled: bool = True,
    timeout_s: int = 120,
    callable_path: str | None = None,
) -> Hook:
    return Hook.model_validate(
        {
            "name": name,
            "id": hook_id,
            "kind": kind,
            "priority": priority,
            "fail_policy": policy,
            "required": required,
            "enabled": enabled,
            "timeout_s": timeout_s,
            "callable_path": callable_path,
        }
    )


def _recorder(log: list[str], label: str) -> HookCallable:
    async def run(ctx: HookContext) -> None:
        del ctx
        log.append(f"{label}:start")
        await asyncio.sleep(0)
        log.append(f"{label}:end")

    return run


async def _boom(ctx: HookContext) -> None:
    del ctx
    msg = "hook exploded"
    raise RuntimeError(msg)


async def _hang(ctx: HookContext) -> None:
    del ctx
    await asyncio.Event().wait()


def _rows(db: Database) -> list[tuple[object, ...]]:
    return [
        tuple(row)
        for row in db.connect().execute(
            "SELECT hook_name, hook_id, status, duration_ms, run_id, work_item_id "
            "FROM hook_executions ORDER BY id"
        )
    ]


async def _hook_events(ledger: DefaultLedgerManager) -> list[tuple[LedgerEventKind, str]]:
    events = await ledger.query(kinds=[LedgerEventKind.HOOK_EXECUTED, LedgerEventKind.HOOK_FAILED])
    return [(event.kind, event.payload["hook_id"]) for event in events]


def test_default_manager_satisfies_protocol(manager: DefaultHookManager) -> None:
    protocol: HookManager = manager
    assert protocol is manager


def test_hooks_ordered_by_priority_then_id(manager: DefaultHookManager) -> None:
    log: list[str] = []
    manager.register(_hook("c", priority=100), _recorder(log, "c"))
    manager.register(_hook("b", priority=10), _recorder(log, "b"))
    manager.register(_hook("a", priority=10), _recorder(log, "a"))
    ordered = [(h.priority, h.id) for h in manager.hooks_for(NAME)]
    assert ordered == [(10, "a"), (10, "b"), (100, "c")]
    assert manager.hooks_for(HookName.ON_COMMIT) == []


def test_register_rejects_duplicate_id(manager: DefaultHookManager) -> None:
    manager.register(_hook("builtin.x"), _recorder([], "x"))
    manager.register(_hook("builtin.x", name=HookName.ON_COMMIT), _recorder([], "x"))
    with pytest.raises(ConfigError, match="duplicate hook"):
        manager.register(_hook("builtin.x"), _recorder([], "x"))


def test_project_hook_cannot_replace_required_builtin(manager: DefaultHookManager) -> None:
    manager.register(
        _hook("builtin.branch", required=True, policy=HookFailPolicy.FAIL_CLOSED),
        _recorder([], "b"),
    )
    with pytest.raises(ConfigError, match="required builtin"):
        manager.register(_hook("builtin.branch", kind="project", enabled=False))
    with pytest.raises(ConfigError, match="required builtin"):
        manager.register(_hook("builtin.branch", name=HookName.ON_COMMIT, kind="project"))
    assert [h.id for h in manager.hooks_for(NAME)] == ["builtin.branch"]
    assert manager.hooks_for(HookName.ON_COMMIT) == []


def test_register_rejects_disabled_required_hook(manager: DefaultHookManager) -> None:
    with pytest.raises(ConfigError, match="cannot be disabled"):
        manager.register(_hook("builtin.x", required=True, enabled=False), _recorder([], "x"))


def test_register_builtin_requires_callable(manager: DefaultHookManager) -> None:
    with pytest.raises(ConfigError, match="needs a callable"):
        manager.register(_hook("builtin.x"))
    with pytest.raises(ConfigError, match="needs a callable"):
        manager.register(_hook("builtin.y", callable_path="walk.nowhere:fn"))


def test_register_project_hook_rejects_callable(manager: DefaultHookManager) -> None:
    with pytest.raises(ConfigError, match="project hook"):
        manager.register(_hook("project.x", kind="project"), _recorder([], "x"))


async def test_register_resolves_callable_path(
    db: Database, ledger: DefaultLedgerManager, fake_clock: FakeClock
) -> None:
    log: list[str] = []
    path = "walk.orchestrator.builtin_hooks:x"
    manager = DefaultHookManager(
        HookExecutionRepository(db), ledger, fake_clock, callables={path: _recorder(log, "x")}
    )
    manager.register(_hook("builtin.x", callable_path=path))
    results = await manager.fire(NAME, _ctx())
    assert [r.status for r in results] == ["OK"]
    assert log == ["x:start", "x:end"]


async def test_fire_runs_sequentially_and_records(
    manager: DefaultHookManager, ledger: DefaultLedgerManager, db: Database, fake_clock: FakeClock
) -> None:
    log: list[str] = []
    first = _recorder(log, "first")

    async def slow(ctx: HookContext) -> None:
        await first(ctx)
        fake_clock.advance(1.5)

    manager.register(_hook("first", priority=1), slow)
    manager.register(_hook("second", priority=2), _recorder(log, "second"))
    results = await manager.fire(NAME, _ctx())
    assert log == ["first:start", "first:end", "second:start", "second:end"]
    assert [(r.hook_id, r.status, r.duration_ms) for r in results] == [
        ("first", "OK", 1500),
        ("second", "OK", 0),
    ]
    assert _rows(db) == [
        ("on_task_start", "first", "OK", 1500, RUN, "STORY-0001"),
        ("on_task_start", "second", "OK", 0, RUN, "STORY-0001"),
    ]
    events = await ledger.query(kinds=[LedgerEventKind.HOOK_EXECUTED])
    assert [(e.payload["hook_id"], e.duration_ms, e.outcome) for e in events] == [
        ("first", 1500, "OK"),
        ("second", 0, "OK"),
    ]
    assert events[0].work_item_id == "STORY-0001"
    assert events[0].run_id == RUN
    assert events[0].actor_role is AgentRole.KERNEL
    assert events[0].payload["hook_name"] == "on_task_start"


async def test_fail_closed_aborts_and_raises(
    manager: DefaultHookManager, ledger: DefaultLedgerManager, db: Database
) -> None:
    log: list[str] = []
    manager.register(_hook("ok", priority=1), _recorder(log, "ok"))
    manager.register(_hook("guard", priority=2, policy=HookFailPolicy.FAIL_CLOSED), _boom)
    manager.register(_hook("after", priority=3), _recorder(log, "after"))
    with pytest.raises(HookFailed) as raised:
        await manager.fire(NAME, _ctx())
    assert raised.value.detail["hook_id"] == "guard"
    assert [r["status"] for r in raised.value.detail["results"]] == ["OK", "FAILED"]
    assert "hook exploded" in raised.value.detail["results"][1]["message"]
    assert log == ["ok:start", "ok:end"]
    assert [row[1:3] for row in _rows(db)] == [("ok", "OK"), ("guard", "FAILED")]
    assert await _hook_events(ledger) == [
        (LedgerEventKind.HOOK_EXECUTED, "ok"),
        (LedgerEventKind.HOOK_FAILED, "guard"),
    ]


async def test_log_and_continue_continues(
    manager: DefaultHookManager, ledger: DefaultLedgerManager
) -> None:
    log: list[str] = []
    manager.register(_hook("flaky", priority=1), _boom)
    manager.register(_hook("next", priority=2), _recorder(log, "next"))
    results = await manager.fire(NAME, _ctx())
    assert [(r.hook_id, r.status) for r in results] == [("flaky", "FAILED"), ("next", "OK")]
    assert results[0].message == "RuntimeError: hook exploded"
    assert log == ["next:start", "next:end"]
    failed = await ledger.query(kinds=[LedgerEventKind.HOOK_FAILED])
    assert [(e.payload["hook_id"], e.outcome) for e in failed] == [("flaky", "FAILED")]


async def test_timeout_is_recorded_and_policy_applied(
    manager: DefaultHookManager, ledger: DefaultLedgerManager
) -> None:
    log: list[str] = []
    manager.register(_hook("slow", priority=1, timeout_s=0), _hang)
    manager.register(_hook("next", priority=2), _recorder(log, "next"))
    results = await manager.fire(NAME, _ctx())
    assert [(r.hook_id, r.status) for r in results] == [("slow", "TIMEOUT"), ("next", "OK")]

    guard = _hook("guard", name=HookName.ON_COMMIT, timeout_s=0, policy=HookFailPolicy.FAIL_CLOSED)
    manager.register(guard, _hang)
    with pytest.raises(HookFailed):
        await manager.fire(HookName.ON_COMMIT, _ctx(HookName.ON_COMMIT))
    failed = await ledger.query(kinds=[LedgerEventKind.HOOK_FAILED])
    assert [(e.payload["hook_id"], e.payload["status"]) for e in failed] == [
        ("slow", "TIMEOUT"),
        ("guard", "TIMEOUT"),
    ]


async def test_hook_raising_timeout_error_is_a_failure(manager: DefaultHookManager) -> None:
    async def inner_timeout(ctx: HookContext) -> None:
        del ctx
        raise TimeoutError

    manager.register(_hook("x"), inner_timeout)
    results = await manager.fire(NAME, _ctx())
    assert [r.status for r in results] == ["FAILED"]


async def test_fire_without_hooks_is_noop(
    manager: DefaultHookManager, ledger: DefaultLedgerManager, db: Database
) -> None:
    assert await manager.fire(NAME, _ctx()) == []
    assert await ledger.query() == []
    assert _rows(db) == []


async def test_fire_rejects_context_for_other_hook(manager: DefaultHookManager) -> None:
    with pytest.raises(ConfigError, match="context"):
        await manager.fire(HookName.ON_COMMIT, _ctx())


async def test_project_hook_without_executor_fails_by_policy(
    manager: DefaultHookManager,
) -> None:
    manager.register(_hook("project.notify", kind="project"))
    results = await manager.fire(NAME, _ctx())
    assert [(r.hook_id, r.status) for r in results] == [("project.notify", "FAILED")]
    gate = _hook(
        "project.gate", name=HookName.ON_COMMIT, kind="project", policy=HookFailPolicy.FAIL_CLOSED
    )
    manager.register(gate)
    with pytest.raises(HookFailed):
        await manager.fire(HookName.ON_COMMIT, _ctx(HookName.ON_COMMIT))


def test_load_project_hooks_not_supported_yet(manager: DefaultHookManager) -> None:
    with pytest.raises(ConfigError, match="E02-S09"):
        manager.load_project_hooks(".ai/agents/hooks.yaml")


async def test_disabled_hook_is_skipped(
    manager: DefaultHookManager, ledger: DefaultLedgerManager, db: Database
) -> None:
    log: list[str] = []
    manager.register(_hook("off", enabled=False), _recorder(log, "off"))
    manager.register(_hook("on"), _recorder(log, "on"))
    assert [h.id for h in manager.hooks_for(NAME)] == ["on"]
    results = await manager.fire(NAME, _ctx())
    assert [r.hook_id for r in results] == ["on"]
    assert log == ["on:start", "on:end"]
    assert [row[1] for row in _rows(db)] == ["on"]
    assert await _hook_events(ledger) == [(LedgerEventKind.HOOK_EXECUTED, "on")]
