"""Worktree lifecycle across an item's runs (E01-B01): release on completion, adopt leftovers."""

import logging
import subprocess
from pathlib import Path

import pytest

from tests.fakes.fake_model_adapter import FakeScript
from tests.runtime.executor_env import (
    CLAUDE_MODEL,
    LEAD,
    EnvFactory,
    ExecutorEnv,
    completed_output,
    script,
)
from walk.agents import AgentInput, AgentOutputStatus
from walk.common.enums import Effort
from walk.common.errors import ConfigError
from walk.hooks import Hook, HookContext, HookName
from walk.runtime import WORKTREES_DIR, AgentRunState, CheckpointKind
from walk.telemetry import LedgerEventKind
from walk.workflow import WorkItemState

K = LedgerEventKind
RESIDUE = "src/Residue.cs"


def _git(cwd: Path | str, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def _exists(path: str) -> bool:
    return Path(path).exists()


def _resolved(path: str) -> Path:
    return Path(path).resolve()


def _worktrees(repo: Path) -> list[Path]:
    listed = _git(repo, "worktree", "list", "--porcelain").splitlines()
    return [
        Path(line.removeprefix("worktree ")).resolve()
        for line in listed
        if line.startswith("worktree ")
    ]


def _review_or_implement(agent_input: AgentInput) -> FakeScript:
    """IMPLEMENT (SENIOR_DEV): 3 edits, COMPLETED. REVIEW (LEAD_DEV): 4 edits, APPROVED."""
    if agent_input.role is LEAD:
        return script(tool_calls=4, output=completed_output(status=AgentOutputStatus.APPROVED))
    return script(tool_calls=3)


async def _state(env: ExecutorEnv) -> WorkItemState:
    item = await env.items.get(env.story.id)
    assert item is not None
    return item.state


async def test_completed_run_removes_worktree_and_keeps_branch(
    make_executor_env: EnvFactory,
) -> None:
    env = await make_executor_env(script(tool_calls=3))

    run = await env.run_to_end()

    assert run.state is AgentRunState.COMPLETED
    assert run.worktree_path is not None
    assert run.branch is not None
    assert not _exists(run.worktree_path)
    assert _resolved(run.worktree_path) not in _worktrees(env.repo)
    end = env.checkpoints_of(run.id)[-1]
    assert end.kind is CheckpointKind.END
    assert _git(env.repo, "rev-parse", run.branch) == end.head_sha
    subject = _git(env.repo, "log", "--format=%s", "-1", run.branch)
    assert subject == f"wip({env.story.id}): checkpoint {end.seq}"


async def test_next_run_after_completed_run_starts(make_executor_env: EnvFactory) -> None:
    env = await make_executor_env(_review_or_implement)
    first = await env.run_to_end()
    assert first.state is AgentRunState.COMPLETED
    assert await _state(env) is WorkItemState.READY_FOR_REVIEW
    item = await env.items.get(env.story.id)
    assert item is not None
    reviewer = await env.agents.instantiate(LEAD, item, CLAUDE_MODEL, Effort.MEDIUM, [], {"git"})

    started = await env.executor.start(reviewer, item, "REVIEW")
    review = await env.executor.wait(started.id)

    assert review.state is AgentRunState.COMPLETED, review.failure_reason
    assert review.failure_reason is None
    assert review.purpose == "REVIEW"
    assert review.branch == first.branch
    expected = _resolved(str(env.repo / WORKTREES_DIR / review.id))
    assert review.worktree_path is not None
    assert _resolved(review.worktree_path) == expected
    assert await env.events(review.id, K.ERROR) == []
    assert len(await env.events(review.id, K.AGENT_RUN_STARTED)) == 1
    assert _worktrees(env.repo) == [env.repo.resolve()]
    assert first.branch is not None
    log = _git(env.repo, "log", "--format=%s", first.branch).splitlines()
    assert log[:2] == [f"wip({env.story.id}): checkpoint 2"] * 2


async def test_next_run_after_failed_run_adopts_kept_worktree(
    make_executor_env: EnvFactory,
) -> None:
    plans = iter([script(tool_calls=5, fail_after_tool_calls=2), script(tool_calls=3)])
    env = await make_executor_env(lambda _input: next(plans))
    seen: dict[str, bool] = {}

    async def residue_at_first_call(ctx: HookContext) -> None:
        run = await env.runs.get(str(ctx.run_id))
        assert run is not None
        assert run.worktree_path is not None
        seen.setdefault(run.id, (Path(run.worktree_path) / RESIDUE).is_file())

    env.hooks.register(
        Hook(name=HookName.ON_TOOL_BEFORE, id="test.residue", kind="builtin"),
        residue_at_first_call,
    )
    failed = await env.run_to_end()
    assert failed.state is AgentRunState.FAILED
    assert failed.worktree_path is not None
    (Path(failed.worktree_path) / RESIDUE).write_bytes(b"// uncommitted residue\n")

    second = await env.run_to_end()

    assert second.parent_run_id is None
    assert second.worktree_path == failed.worktree_path
    assert second.branch == failed.branch
    assert seen[second.id] is True
    assert second.state is AgentRunState.COMPLETED, second.failure_reason
    assert await env.events(second.id, K.ERROR) == []


async def test_worktree_removal_failure_does_not_fail_run(
    make_executor_env: EnvFactory,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    env = await make_executor_env(script(tool_calls=3))
    removed: list[str] = []

    async def refuse(run: object, *, keep_branch: bool = True) -> None:
        del keep_branch
        removed.append(getattr(run, "id", ""))
        msg = "worktree is locked"
        raise ConfigError(msg)

    monkeypatch.setattr(env.sandbox, "remove", refuse)

    with caplog.at_level(logging.WARNING, logger="walk.runtime.executor"):
        run = await env.run_to_end()

    assert removed == [run.id]
    assert run.state is AgentRunState.COMPLETED
    (ended,) = await env.events(run.id, K.AGENT_RUN_ENDED)
    assert ended.outcome == "OK"
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any(r.getMessage() == "worktree removal failed" for r in warnings)
    assert run.worktree_path is not None
    assert _exists(run.worktree_path)
