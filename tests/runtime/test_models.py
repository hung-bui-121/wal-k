import pytest
from pydantic import ValidationError

import walk.agents.models
import walk.runtime.models
from tests.runtime.conftest import AT, RUN_A, STORY_ID, make_run
from walk.common.enums import Effort
from walk.common.errors import PermanentError
from walk.common.roles import AgentRole
from walk.context import ContextBundleRef
from walk.runtime import (
    AgentRunState,
    AppliedEffects,
    Checkpoint,
    CheckpointKind,
    CheckpointNotFound,
    RunNotFound,
)
from walk.workflow import WorkItemState


def _checkpoint() -> Checkpoint:
    return Checkpoint(
        id="CKP-01J00000000000000000000000",
        run_id=RUN_A,
        work_item_id=STORY_ID,
        seq=1,
        kind=CheckpointKind.PERIODIC,
        at=AT,
        role=AgentRole.SENIOR_DEV,
        model_id="codex/gpt-5-codex",
        effort=Effort.MEDIUM,
        workflow_state=WorkItemState.IMPLEMENTING,
        head_sha="3f9c2e1",
        wip_commit_sha=None,
        dirty_files=[],
        tool_calls_so_far=0,
        budget_consumed={},
        provider_session=None,
        handover_id=None,
        context_manifest=ContextBundleRef(item_ids=[], total_tokens_estimate=0),
    )


def test_runtime_enums_and_relocated_status() -> None:
    assert [s.value for s in AgentRunState] == [
        "PENDING",
        "RUNNING",
        "PAUSED_FOR_APPROVAL",
        "PAUSED_BY_USER",
        "INTERRUPTED",
        "HANDED_OVER",
        "COMPLETED",
        "FAILED",
        "FAILED_HOOK",
        "FAILED_BOUNDARY",
        "BLOCKED_BUDGET",
        "BLOCKED_PROVIDER",
        "CANCELLED",
    ]
    assert [k.value for k in CheckpointKind] == [
        "START",
        "PERIODIC",
        "AGENT_REQUESTED",
        "HANDOFF",
        "PAUSE",
        "END",
    ]
    checkpoint = _checkpoint()
    with pytest.raises(ValidationError):
        checkpoint.seq = 2  # type: ignore[misc]  # frozen on purpose
    assert walk.runtime.models.AgentOutputStatus is walk.agents.models.AgentOutputStatus


def test_agent_run_defaults_and_applied_effects() -> None:
    run = make_run()
    assert run.state is AgentRunState.PENDING
    assert (run.tool_calls, run.fallbacks, run.repair_turns) == (0, 0, 0)
    assert run.worktree_path is None
    with pytest.raises(ValidationError):
        make_run(purpose="SING")
    effects = AppliedEffects(
        evidence_ids=[],
        decision_ids=[],
        created_work_items=[],
        escalation_ids=[],
        memory_docs=[],
        commit_sha=None,
        workflow_event=None,
    )
    assert effects.commit_sha is None


def test_runtime_errors_are_permanent() -> None:
    assert issubclass(RunNotFound, PermanentError)
    assert issubclass(CheckpointNotFound, PermanentError)
