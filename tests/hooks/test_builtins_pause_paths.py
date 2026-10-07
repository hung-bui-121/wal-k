import asyncio

from tests.hooks.conftest import DEADLOCK_GUARD_S, POLL_S, BuiltinEnv, BuiltinEnvFactory
from tests.runtime.conftest import AT, STORY_ID
from tests.runtime.executor_env import EXECUTOR_RULES, SENIOR, script
from walk.agents import AgentOutput, AgentOutputStatus, Handover, from_document
from walk.budgets import BudgetDimension, BudgetScope
from walk.hooks import Hook, HookContext, HookName
from walk.permissions import Approver, PermissionEffect, PermissionRule
from walk.runtime import AgentRunState, CheckpointKind
from walk.telemetry import LedgerEventKind
from walk.workflow import WorkItemState


async def _short_sleep(seconds: float) -> None:
    del seconds
    await asyncio.sleep(POLL_S)


async def _until_paused_for_approval(built: BuiltinEnv, run_id: str) -> None:
    """Wait for PAUSED_FOR_APPROVAL and its PAUSE checkpoint (taken right after the state)."""
    while True:
        run = await built.env.runs.get(run_id)
        paused = run is not None and run.state is AgentRunState.PAUSED_FOR_APPROVAL
        if paused and any(c.kind is CheckpointKind.PAUSE for c in built.checkpoints(run_id)):
            return
        await asyncio.sleep(POLL_S)


def _partial_output() -> AgentOutput:
    embedded = Handover(
        id="HO-0042",
        work_item_id=STORY_ID,
        role=SENIOR,
        from_run_id="RUN-01J0000000000000000000000A",
        from_model_id="fake-codex/sim",
        reason="PARTIAL",
        task_summary="double jump",
        current_state="half done",
        completed_work=[],
        modified_files=[],
        findings=[],
        hypotheses=[],
        decisions=[],
        risks=[],
        remaining_work=["Wire the jump button", "Tune gravity"],
        next_action="Wire the jump button",
        worktree_head="3f9c2e1",
        branch="feat/story-0001",
        created_at=AT,
    )
    return AgentOutput(
        status=AgentOutputStatus.PARTIAL,
        result="Added the DoubleJump component",
        handover=embedded,
        no_context_change_reason="partial",
    )


async def test_budget_exhausted_blocks_once_and_escalates_without_deadlock(
    make_builtin_env: BuiltinEnvFactory,
) -> None:
    built = await make_builtin_env(plan=script(tool_calls=6))
    await built.env.budgets.ensure(
        BudgetScope.TASK, built.env.story.id, None, {BudgetDimension.TOOL_CALLS: 2}
    )

    run = await asyncio.wait_for(built.env.run_to_end(), DEADLOCK_GUARD_S)

    assert run.state is AgentRunState.BLOCKED_BUDGET
    pauses = [c for c in built.checkpoints(run.id) if c.kind is CheckpointKind.PAUSE]
    assert len(pauses) == 1
    pending = await built.env.permissions.pending()
    assert [(a.kind, a.approver) for a in pending] == [("ESCALATION", Approver.USER)]
    assert pending[0].payload["hard_action"] == "BLOCK"
    assert built.executions("builtin.budget_escalate") == ["OK"]
    assert built.executions("builtin.approval_recorded") == ["OK"]


async def test_protected_action_pause_is_done_by_the_tool_invoker(
    make_builtin_env: BuiltinEnvFactory,
) -> None:
    approval = PermissionRule(
        role=SENIOR, tool="edit", effect=PermissionEffect.REQUIRE_APPROVAL, approver=Approver.USER
    )
    built = await make_builtin_env(
        plan=script(tool_calls=1),
        rules=[*EXECUTOR_RULES, approval],
        approval_sleep=_short_sleep,
    )

    run = await built.env.executor.start(built.env.agent, built.env.story, "IMPLEMENT")
    try:
        await asyncio.wait_for(_until_paused_for_approval(built, run.id), DEADLOCK_GUARD_S)

        assert [c.kind for c in built.checkpoints(run.id)] == [
            CheckpointKind.START,
            CheckpointKind.PAUSE,
        ]
        assert run.id in [r.id for r in built.env.executor.running()]
        assert built.executions("builtin.approval_recorded") == ["OK"]
        assert [a.kind for a in await built.env.permissions.pending()] == ["TOOL_CALL"]
    finally:  # release the waiting run, whatever the assertions found
        for pending in await built.env.permissions.pending():
            await built.env.permissions.decide_approval(
                pending.id, approve=True, by="user", note=None
            )
    ended = await asyncio.wait_for(built.env.executor.wait(run.id), DEADLOCK_GUARD_S)
    assert ended.state is AgentRunState.COMPLETED


async def test_partial_implement_run_hands_over_without_failing(
    make_builtin_env: BuiltinEnvFactory,
) -> None:
    built = await make_builtin_env(plan=script(output=_partial_output()))
    handoffs: list[HookContext] = []

    async def record(ctx: HookContext) -> None:
        handoffs.append(ctx)

    built.env.hooks.register(
        Hook(name=HookName.ON_AGENT_HANDOFF, id="test.handoff", kind="builtin"), record
    )

    run = await asyncio.wait_for(built.env.run_to_end(), DEADLOCK_GUARD_S)

    assert run.state is AgentRunState.HANDED_OVER
    assert run.handover_out_id == "HO-0001"
    ended = (await built.env.events(run.id, LedgerEventKind.AGENT_RUN_ENDED))[0]
    assert ended.outcome == "OK"
    assert ended.payload["status"] == "PARTIAL"
    assert ended.payload["effects"]["workflow_event"] == "partial"
    item = await built.env.items.get(built.env.story.id)
    assert item is not None
    assert item.state is WorkItemState.IMPLEMENTING
    assert item.assigned_run_id is None
    transitions = await built.env.ledger.query(kinds=[LedgerEventKind.WORK_ITEM_TRANSITION])
    assert [t.payload["event"] for t in transitions] == ["partial"]
    kinds = [c.kind for c in built.checkpoints(run.id)]
    assert kinds == [CheckpointKind.START, CheckpointKind.HANDOFF]
    handoff = built.checkpoints(run.id)[-1]
    assert [(c.payload["checkpoint_id"], c.payload["handover_id"]) for c in handoffs] == [
        (handoff.id, "HO-0001")
    ]
    assert built.executions("builtin.handoff_checkpoint_and_handover") == ["OK"]
    document = await built.env.memory.read_handover("HO-0001")
    stored = from_document(document)
    assert stored.reason == "PARTIAL"
    assert stored.remaining_work == ["Wire the jump button", "Tune gravity"]
    open_handover = await built.env.checkpoints.latest_open_handover(built.env.story.id)
    assert open_handover is not None
    assert open_handover.id == "HO-0001"
