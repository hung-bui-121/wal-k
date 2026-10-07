from collections import Counter
from pathlib import Path

import pytest

from tests.hooks.conftest import BuiltinEnv, BuiltinEnvFactory
from tests.runtime.conftest import RunFactory
from walk.common.errors import ConfigError
from walk.hooks import Hook, HookName
from walk.runtime import CheckpointKind


def _ledger_kinds(built: BuiltinEnv) -> Counter[str]:
    rows = built.env.db.connect().execute("SELECT kind FROM ledger_events").fetchall()
    return Counter(str(row[0]) for row in rows)


def _checkpoint_count(built: BuiltinEnv) -> int:
    row = built.env.db.connect().execute("SELECT COUNT(*) FROM checkpoints").fetchone()
    return int(row[0])


def _handover_docs(built: BuiltinEnv) -> list[Path]:
    return sorted((built.env.db.path.parent / "handovers").glob("*.md"))


async def test_project_cannot_disable_required_builtin(
    make_builtin_env: BuiltinEnvFactory,
) -> None:
    built = await make_builtin_env()
    disabled = Hook(
        name=HookName.ON_AGENT_END,
        id="builtin.final_checkpoint",
        kind="project",
        command="echo off",
        enabled=False,
    )

    with pytest.raises(ConfigError):
        built.env.hooks.register(disabled)

    assert "builtin.final_checkpoint" in [
        h.id for h in built.env.hooks.hooks_for(HookName.ON_AGENT_END)
    ]


async def test_hooks_do_not_duplicate_ledger_events(
    make_builtin_env: BuiltinEnvFactory, insert_run: RunFactory, tmp_game_repo: Path
) -> None:
    built = await make_builtin_env()
    run = await insert_run(worktree_path=str(tmp_game_repo), branch="main")
    before = _ledger_kinds(built)

    results = await built.fire(
        HookName.ON_AGENT_END,
        run_id=run.id,
        work_item_id=run.work_item_id,
        payload={"status": "COMPLETED"},
    )

    assert [r.hook_id for r in results if r.status == "OK"] == [
        "builtin.final_checkpoint",
        "test.on_agent_end",
    ]
    assert [c.kind for c in built.checkpoints(run.id)] == [CheckpointKind.END]
    added = _ledger_kinds(built) - before
    assert set(added) == {"HOOK_EXECUTED", "CHECKPOINT_CREATED"}
    assert added["CHECKPOINT_CREATED"] == 1


async def test_checkpoint_hooks_noop_when_executor_already_checkpointed(
    make_builtin_env: BuiltinEnvFactory, insert_run: RunFactory, tmp_game_repo: Path
) -> None:
    built = await make_builtin_env()
    run = await insert_run(worktree_path=str(tmp_game_repo), branch="main")
    handover = await built.env.checkpoints.build_handover(run, "FALLBACK", None)
    handoff = await built.env.checkpoints.checkpoint(
        run, CheckpointKind.HANDOFF, handover=handover, workflow_state=built.env.story.state
    )
    checkpoints, documents = _checkpoint_count(built), _handover_docs(built)
    fired = {"count": 0}

    async def count(ctx: object) -> None:
        del ctx
        fired["count"] += 1

    built.env.hooks.register(
        Hook(name=HookName.ON_AGENT_HANDOFF, id="test.handoff_seen", kind="builtin"), count
    )

    await built.fire(
        HookName.ON_AGENT_END,
        run_id=run.id,
        work_item_id=run.work_item_id,
        payload={"checkpoint_id": handoff.id},
    )
    await built.fire(
        HookName.ON_MODEL_FALLBACK,
        run_id=run.id,
        work_item_id=run.work_item_id,
        payload={"checkpoint_id": handoff.id, "handover_id": handoff.handover_id},
    )

    assert _checkpoint_count(built) == checkpoints
    assert _handover_docs(built) == documents
    assert fired["count"] == 1
    for hook_id in (
        "builtin.final_checkpoint",
        "builtin.fallback_chain",
        "builtin.handoff_checkpoint_and_handover",
    ):
        assert built.executions(hook_id) == ["OK"]
