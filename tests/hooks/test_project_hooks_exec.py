import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.cli.conftest import POLICIES, fake_adapters, migrate
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_subprocess import FakeSubprocessRunner
from tests.orchestrator.conftest import RecordingTelemetry
from walk.cli.composition import KernelOverrides, KernelSettings, build_kernel
from walk.common.errors import ConfigError, Timeout
from walk.hooks import (
    DefaultHookManager,
    HookContext,
    HookExecutionRepository,
    HookFailed,
    HookName,
)
from walk.persistence import Database, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerEventKind, LedgerRepository

ManagerFactory = Callable[..., DefaultHookManager]


async def _no_sleep(seconds: float) -> None:
    del seconds


@pytest.fixture
def ledger(db: Database, fake_clock: FakeClock) -> DefaultLedgerManager:
    return DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), fake_clock)


@pytest.fixture
def runner() -> FakeSubprocessRunner:
    return FakeSubprocessRunner()


@pytest.fixture
def make_manager(
    db: Database,
    ledger: DefaultLedgerManager,
    fake_clock: FakeClock,
    runner: FakeSubprocessRunner,
    tmp_path: Path,
) -> Callable[[str], DefaultHookManager]:
    def build(hooks_yaml: str) -> DefaultHookManager:
        path = tmp_path / "hooks.yaml"
        path.write_bytes(hooks_yaml.encode("utf-8"))
        manager = DefaultHookManager(
            HookExecutionRepository(db),
            ledger,
            fake_clock,
            command_runner=runner,
            cwd=str(tmp_path),
            base_env={"PATH": "/bin"},
        )
        manager.load_project_hooks(str(path))
        return manager

    return build


def _ctx(name: HookName, fake_clock: FakeClock) -> HookContext:
    return HookContext(name=name, at=fake_clock.now(), project_key="DEMO", payload={"n": 1})


@pytest.fixture
def kernel_repo(tmp_game_repo: Path) -> Path:
    """`tmp_game_repo` with a migrated database, the DEMO project and fake-model policies."""
    migrate(tmp_game_repo)
    agents = tmp_game_repo / ".ai" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / "policies.yaml").write_bytes(POLICIES.encode("utf-8"))
    return tmp_game_repo


async def test_command_hook_runs_with_context_env(
    kernel_repo: Path,
    fake_clock: FakeClock,
    runner: FakeSubprocessRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_game_repo = kernel_repo
    agents = tmp_game_repo / ".ai" / "agents"
    (agents / "hooks.yaml").write_bytes(
        b"hooks:\n  - {name: on_project_start, id: project.echo, command: echo hello}\n"
    )
    monkeypatch.setenv("JIRA_API_TOKEN", "secret-token")
    runner.script([], exit_code=0, stdout="hello\n")
    overrides = KernelOverrides(
        adapters=fake_adapters(fake_clock),
        clock=fake_clock,
        sleep=_no_sleep,
        kernel_instance="test-instance",
        ready_env_keys={"git"},
        subprocess_runner=runner,
    )
    handle = build_kernel(KernelSettings(repo_path=tmp_game_repo), overrides=overrides)
    try:
        results = await handle.hooks.fire(
            HookName.ON_PROJECT_START, _ctx(HookName.ON_PROJECT_START, fake_clock)
        )
    finally:
        await handle.aclose()

    assert [(r.hook_id, r.status) for r in results] == [
        ("builtin.memory_index", "OK"),
        ("project.echo", "OK"),
    ]
    call = runner.calls[-1]
    assert call.argv[-1] == "echo hello"
    assert call.cwd == str(tmp_game_repo)
    assert call.env is not None
    assert call.env["WALK_HOOK_NAME"] == "on_project_start"
    assert call.env["WALK_HOOK_PAYLOAD"] == '{"n": 1}'
    assert "JIRA_API_TOKEN" not in call.env
    assert "secret-token" not in call.env.values()


@pytest.mark.parametrize(
    ("platform", "shell"),
    [("win32", ["cmd.exe", "/d", "/s", "/c"]), ("linux", ["/bin/sh", "-c"])],
)
async def test_command_runs_in_the_platform_shell(  # noqa: PLR0917 - fixtures and parameters
    make_manager: ManagerFactory,
    runner: FakeSubprocessRunner,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    shell: list[str],
) -> None:
    manager = make_manager("hooks:\n  - {name: on_commit, id: project.x, command: make lint}\n")
    runner.script([], exit_code=0)
    monkeypatch.setattr(sys, "platform", platform)

    await manager.fire(HookName.ON_COMMIT, _ctx(HookName.ON_COMMIT, fake_clock))

    assert runner.calls[-1].argv == [*shell, "make lint"]


async def test_command_hook_timeout(
    make_manager: ManagerFactory,
    runner: FakeSubprocessRunner,
    ledger: DefaultLedgerManager,
    fake_clock: FakeClock,
) -> None:
    manager = make_manager(
        "hooks:\n  - {name: on_commit, id: project.slow, command: sleep 9, timeout_s: 3}\n"
    )
    runner.script([], error=Timeout("command timed out", detail={}))

    results = await manager.fire(HookName.ON_COMMIT, _ctx(HookName.ON_COMMIT, fake_clock))

    assert [(r.hook_id, r.status) for r in results] == [("project.slow", "TIMEOUT")]
    assert runner.calls[-1].timeout_s == 3
    failed = await ledger.query(kinds=[LedgerEventKind.HOOK_FAILED])
    assert [e.payload["hook_id"] for e in failed] == ["project.slow"]
    assert failed[0].payload["status"] == "TIMEOUT"


async def test_fail_closed_project_hook_raises(
    make_manager: ManagerFactory, runner: FakeSubprocessRunner, fake_clock: FakeClock
) -> None:
    manager = make_manager(
        "hooks:\n"
        "  - {name: on_commit, id: project.gate, command: lint, fail_policy: fail_closed}\n"
        "  - {name: on_commit, id: project.after, command: notify, priority: 200}\n"
    )
    runner.script([], exit_code=1, stderr="warning: x\nerror: lint failed\n")

    with pytest.raises(HookFailed) as raised:
        await manager.fire(HookName.ON_COMMIT, _ctx(HookName.ON_COMMIT, fake_clock))

    results = raised.value.detail["results"]
    assert [(r["hook_id"], r["status"], r["message"]) for r in results] == [
        ("project.gate", "FAILED", "error: lint failed")
    ]
    assert len(runner.calls) == 1


async def test_log_and_continue_project_hook_records_and_continues(
    make_manager: ManagerFactory, runner: FakeSubprocessRunner, fake_clock: FakeClock
) -> None:
    manager = make_manager(
        "hooks:\n"
        "  - {name: on_commit, id: project.soft, command: lint}\n"
        "  - {name: on_commit, id: project.after, command: notify, priority: 200}\n"
    )
    runner.script([], exit_code=2)

    results = await manager.fire(HookName.ON_COMMIT, _ctx(HookName.ON_COMMIT, fake_clock))

    assert [(r.hook_id, r.status, r.message) for r in results] == [
        ("project.soft", "FAILED", "exit code 2"),
        ("project.after", "FAILED", "exit code 2"),
    ]


async def test_kernel_action_counter(make_manager: ManagerFactory, fake_clock: FakeClock) -> None:
    manager = make_manager(
        "hooks:\n  - {name: on_commit, id: project.x, kernel_action: telemetry.counter}\n"
    )
    telemetry = RecordingTelemetry()

    async def count(ctx: HookContext) -> None:
        telemetry.counter(f"hook.{ctx.payload['hook_id']}")

    manager.set_kernel_actions({"telemetry.counter": count})
    results = await manager.fire(HookName.ON_COMMIT, _ctx(HookName.ON_COMMIT, fake_clock))

    assert [(r.hook_id, r.status) for r in results] == [("project.x", "OK")]
    assert telemetry.counters == {"hook.project.x": 1.0}


async def test_kernel_action_not_wired_fails_by_policy(
    make_manager: ManagerFactory, fake_clock: FakeClock
) -> None:
    manager = make_manager(
        "hooks:\n  - {name: on_commit, id: project.x, kernel_action: skills.sync}\n"
    )

    results = await manager.fire(HookName.ON_COMMIT, _ctx(HookName.ON_COMMIT, fake_clock))

    assert [(r.status, r.message) for r in results] == [
        ("FAILED", "kernel action 'skills.sync' is not available")
    ]
    with pytest.raises(ConfigError, match="unknown kernel action"):
        manager.set_kernel_actions({"foo.bar": _never})


async def test_command_hook_without_runner_fails_by_policy(
    db: Database, ledger: DefaultLedgerManager, fake_clock: FakeClock, tmp_path: Path
) -> None:
    path = tmp_path / "hooks.yaml"
    path.write_bytes(b"hooks:\n  - {name: on_commit, id: project.x, command: echo}\n")
    manager = DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)
    manager.load_project_hooks(str(path))

    results = await manager.fire(HookName.ON_COMMIT, _ctx(HookName.ON_COMMIT, fake_clock))

    assert [(r.status, r.message) for r in results] == [("FAILED", "no command runner")]


async def _never(ctx: HookContext) -> None:
    del ctx
    msg = "not called"
    raise AssertionError(msg)


async def test_kernel_actions_wired_by_the_composition_root(
    kernel_repo: Path, fake_clock: FakeClock
) -> None:
    tmp_game_repo = kernel_repo
    agents = tmp_game_repo / ".ai" / "agents"
    (agents / "hooks.yaml").write_bytes(
        b"hooks:\n"
        b"  - {name: on_commit, id: project.index, kernel_action: memory.rebuild_index}\n"
        b"  - {name: on_commit, id: project.count, kernel_action: telemetry.counter}\n"
        b"  - {name: on_commit, id: project.sync, kernel_action: skills.sync}\n"
    )
    overrides = KernelOverrides(
        adapters=fake_adapters(fake_clock),
        clock=fake_clock,
        sleep=_no_sleep,
        kernel_instance="test-instance",
        ready_env_keys={"git"},
    )
    handle = build_kernel(KernelSettings(repo_path=tmp_game_repo), overrides=overrides)
    try:
        results = await handle.hooks.fire(HookName.ON_COMMIT, _ctx(HookName.ON_COMMIT, fake_clock))
    finally:
        await handle.aclose()

    assert [(r.hook_id, r.status) for r in results] == [
        ("project.count", "OK"),
        ("project.index", "OK"),
        ("project.sync", "OK"),
    ]
    assert (tmp_game_repo / ".walk" / "projections").is_dir()
