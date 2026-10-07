from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookContext, HookExecutionRepository, HookName
from walk.hooks.project import HOOK_ENV_PREFIX, KERNEL_ACTIONS, ProjectHooksFile, hook_env
from walk.persistence import Database, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerRepository

AT = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def manager(db: Database, fake_clock: FakeClock) -> DefaultHookManager:
    ledger = DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), fake_clock)
    return DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock)


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "hooks.yaml"
    path.write_bytes(text.encode("utf-8"))
    return path


async def test_load_valid_file(manager: DefaultHookManager, tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "hooks:\n"
        "  - {name: on_project_start, id: project.echo, command: echo hello, timeout_s: 5}\n",
    )

    hooks = manager.load_project_hooks(str(path))

    assert len(hooks) == 1
    hook = hooks[0]
    assert (hook.kind, hook.id, hook.name) == ("project", "project.echo", HookName.ON_PROJECT_START)
    assert (hook.command, hook.priority, hook.timeout_s) == ("echo hello", 100, 5)
    assert hook.required is False
    assert manager.hooks_for(HookName.ON_PROJECT_START) == hooks


async def test_load_missing_file_returns_empty(manager: DefaultHookManager, tmp_path: Path) -> None:
    assert manager.load_project_hooks(str(tmp_path / "absent.yaml")) == []
    assert manager.load_project_hooks(str(_write(tmp_path, ""))) == []
    assert manager.load_project_hooks(str(_write(tmp_path, "hooks: []\n"))) == []


async def test_load_rejects_command_and_action_together(
    manager: DefaultHookManager, tmp_path: Path
) -> None:
    path = _write(
        tmp_path,
        "hooks:\n"
        "  - {name: on_commit, id: project.both, command: echo, kernel_action: skills.sync}\n",
    )

    with pytest.raises(ConfigError, match=r"project\.both"):
        manager.load_project_hooks(str(path))
    with pytest.raises(ConfigError, match=r"project\.none"):
        ProjectHooksFile.load(_write(tmp_path, "hooks:\n  - {name: on_commit, id: project.none}\n"))


async def test_load_rejects_priority_below_fifty(
    manager: DefaultHookManager, tmp_path: Path
) -> None:
    path = _write(
        tmp_path, "hooks:\n  - {name: on_commit, id: project.early, command: echo, priority: 10}\n"
    )

    with pytest.raises(ConfigError, match=r"project\.early"):
        manager.load_project_hooks(str(path))
    assert manager.hooks_for(HookName.ON_COMMIT) == []


async def test_load_rejects_unknown_kernel_action(
    manager: DefaultHookManager, tmp_path: Path
) -> None:
    path = _write(
        tmp_path, "hooks:\n  - {name: on_commit, id: project.x, kernel_action: foo.bar}\n"
    )

    with pytest.raises(ConfigError, match="unknown kernel action"):
        manager.load_project_hooks(str(path))


@pytest.mark.parametrize(
    "text",
    [
        "hooks: [unclosed\n",
        "- not a mapping\n",
        "hooks: {}\n",
        "hooks: []\nextra: 1\n",
        "hooks:\n  - {name: on_commit, id: builtin.final_checkpoint, command: echo}\n",
        "hooks:\n  - {name: on_commit, id: project.slow, command: echo, timeout_s: 0}\n",
        "hooks:\n  - {name: on_nothing, id: project.x, command: echo}\n",
        "hooks:\n  - just-a-string\n",
    ],
)
def test_load_rejects_invalid_files(tmp_path: Path, text: str) -> None:
    with pytest.raises(ConfigError):
        ProjectHooksFile.load(_write(tmp_path, text))


async def test_disabled_project_hook_is_registered_but_not_run(
    manager: DefaultHookManager, tmp_path: Path
) -> None:
    path = _write(
        tmp_path,
        "hooks:\n  - {name: on_commit, id: project.off, command: echo, enabled: false}\n",
    )

    hooks = manager.load_project_hooks(str(path))

    assert [h.enabled for h in hooks] == [False]
    assert manager.hooks_for(HookName.ON_COMMIT) == []


async def test_duplicate_project_hook_id_is_rejected(
    manager: DefaultHookManager, tmp_path: Path
) -> None:
    path = _write(
        tmp_path,
        "hooks:\n"
        "  - {name: on_commit, id: project.twice, command: echo 1}\n"
        "  - {name: on_commit, id: project.twice, command: echo 2}\n",
    )

    with pytest.raises(ConfigError, match="duplicate"):
        manager.load_project_hooks(str(path))


def test_hook_env_carries_the_context() -> None:
    ctx = HookContext(
        name=HookName.ON_COMMIT,
        at=AT,
        project_key="DEMO",
        work_item_id="STORY-0001",
        role=AgentRole.SENIOR_DEV,
        payload={"sha": "abc"},
    )

    env = hook_env(ctx, {"PATH": "/bin", f"{HOOK_ENV_PREFIX}NAME": "stale"})

    assert env == {
        "PATH": "/bin",
        "WALK_HOOK_NAME": "on_commit",
        "WALK_HOOK_PROJECT_KEY": "DEMO",
        "WALK_HOOK_WORK_ITEM_ID": "STORY-0001",
        "WALK_HOOK_RUN_ID": "",
        "WALK_HOOK_PHASE_ID": "",
        "WALK_HOOK_ROLE": "SENIOR_DEV",
        "WALK_HOOK_AT": "2026-01-01T00:00:00+00:00",
        "WALK_HOOK_PAYLOAD": '{"sha": "abc"}',
    }
    assert KERNEL_ACTIONS == ("memory.rebuild_index", "skills.sync", "telemetry.counter")
