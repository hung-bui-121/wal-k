"""§126 `AgentInput` assembly and the adapter `RunSession` of a run (E01-S27).

`expected_output_for` repeats the purpose → status table of `walk.agents.service` (E01-S18
rule 8, private there): ``runtime`` may not import ``agents.service`` (ARCHITECTURE §2.2), so
E01-R01 checks that both tables agree.
"""

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Final

from walk.agents.models import (
    AgentInput,
    AgentInstance,
    AgentOutputStatus,
    ExpectedOutput,
    Handover,
)
from walk.agents.protocols import AgentManager
from walk.budgets.models import BudgetSubject
from walk.budgets.protocols import BudgetManager
from walk.common.clock import Clock
from walk.common.errors import ConfigError
from walk.common.ids import ProjectKey, RunId
from walk.context.models import ContextRequest
from walk.context.protocols import ContextManager
from walk.debate.models import Debate
from walk.model_router.models import ModelDescriptor, RunSession
from walk.model_router.output import OUTPUT_RELATIVE_PATH
from walk.permissions.models import PermissionDecision, ToolCallRequest
from walk.runtime.models import AgentRun
from walk.tools.protocols import ToolRegistry
from walk.workflow.models import Bug, Phase, Story, Task, WorkItem
from walk.workflow.repository import PhaseRepository

_BUILD: Final = (
    AgentOutputStatus.COMPLETED,
    AgentOutputStatus.PARTIAL,
    AgentOutputStatus.BLOCKED,
    AgentOutputStatus.FAILED,
)
_VERDICT: Final = (
    AgentOutputStatus.APPROVED,
    AgentOutputStatus.REJECTED,
    AgentOutputStatus.NEEDS_INPUT,
)
_ADVISORY: Final = (
    AgentOutputStatus.COMPLETED,
    AgentOutputStatus.NEEDS_INPUT,
    AgentOutputStatus.FAILED,
)
_STATUS_OPTIONS: Final[dict[str, tuple[AgentOutputStatus, ...]]] = {
    "IMPLEMENT": _BUILD,
    "REVIEW": _VERDICT,
    "QC": _VERDICT,
    "TRIAGE": _ADVISORY,
    "PLAN": _ADVISORY,
    "DESIGN": _ADVISORY,
    "ANALYSIS": _ADVISORY,
    "RETRO": _ADVISORY,
    "DEBATE": _ADVISORY,
}


def expected_output_for(purpose: str, item: WorkItem) -> ExpectedOutput:
    """The §126 Expected Output of a run of ``purpose`` on ``item``.

    Status options per purpose (E01-S18 rule 8); ``required_evidence`` from the item's
    contract (none without one); no deliverables in E01.

    Raises:
        ConfigError: ``purpose`` is not a template purpose.
    """
    options = _STATUS_OPTIONS.get(purpose)
    if options is None:
        msg = f"unknown template purpose: {purpose}"
        raise ConfigError(msg, detail={"purpose": purpose, "known": sorted(_STATUS_OPTIONS)})
    contract = item.contract if isinstance(item, Story | Task | Bug) else None
    return ExpectedOutput(
        status_options=list(options),
        deliverables=[],
        required_evidence=list(contract.required_evidence) if contract is not None else [],
    )


class AgentInputBuilder:
    """Assembles the §126 `AgentInput` of one run from the kernel services."""

    def __init__(  # noqa: PLR0917 - positional parameters fixed by the E01-S27 contract
        self,
        agents: AgentManager,
        context: ContextManager,
        tools: ToolRegistry,
        budgets: BudgetManager,
        phases: PhaseRepository,
        clock: Clock,
        *,
        project_key: ProjectKey,
    ) -> None:
        """Wire the builder.

        Args:
            agents: Renders the versioned task prompt.
            context: Builds the context bundle within the model's token budget.
            tools: Resolves the instance's tool names to specs.
            budgets: Budgets applicable to the run.
            phases: The item's phase, when it has one.
            clock: Kernel clock (kept for the context-first enrichments of E04).
            project_key: Project of the budget subject.
        """
        self._agents = agents
        self._context = context
        self._tools = tools
        self._budgets = budgets
        self._phases = phases
        self._clock = clock
        self._project_key = project_key

    async def build(
        self,
        agent: AgentInstance,
        item: WorkItem,
        purpose: str,
        *,
        run_id: RunId,
        worktree_path: str,
        branch: str,
        descriptor: ModelDescriptor,
        handover: Handover | None = None,
        debate: Debate | None = None,
    ) -> AgentInput:
        """Every §126 field of the run's input.

        Approved artifacts, decisions (E04) and resolved skills (E02-S05) are empty in E01.

        Raises:
            ConfigError: Unknown purpose or tool, a template error, or the item's phase does
                not exist.
            WorkItemNotFound: From the context build.
        """
        expected = expected_output_for(purpose, item)
        budget = self._context.token_budget_for(
            agent.effort, descriptor.context_window_tokens, descriptor.max_output_tokens
        )
        bundle = await self._context.build(
            ContextRequest(
                work_item_id=item.id, role=agent.role, effort=agent.effort, token_budget=budget
            )
        )
        subject = BudgetSubject(
            project_key=self._project_key,
            phase_id=item.phase_id,
            role=agent.role,
            work_item_id=item.id,
            run_id=run_id,
        )
        return AgentInput(
            run_id=run_id,
            role=agent.role,
            constitution=agent.constitution,
            authority=agent.constitution.authority,
            task=item,
            workflow_state=item.state,
            phase=await self._phase(item),
            context=bundle,
            approved_artifacts=[],
            decisions=[],
            skills=[],
            allowed_tools=[self._tools.get(name) for name in agent.tools],
            permissions=list(agent.permissions),
            budget=await self._budgets.applicable(subject),
            effort=agent.effort,
            required_evidence=list(expected.required_evidence),
            expected_output=expected,
            handover=handover,
            worktree_path=worktree_path,
            branch=branch,
            debate=debate,
            instructions_markdown=self._agents.render_instructions(agent, item, purpose),
        )

    async def _phase(self, item: WorkItem) -> Phase | None:
        if item.phase_id is None:
            return None
        phase = await self._phases.get(item.phase_id)
        if phase is None:
            msg = f"work item {item.id} references unknown phase {item.phase_id}"
            raise ConfigError(msg, detail={"work_item_id": item.id, "phase_id": item.phase_id})
        return phase


def build_run_session(
    run: AgentRun,
    agent_input: AgentInput,
    authorizer: Callable[[ToolCallRequest], Awaitable[PermissionDecision]],
    *,
    max_turns: int,
    timeout_s: int,
    env_allowlist: dict[str, str],
) -> RunSession:
    """The adapter configuration of ``run``; ``output_path`` = `<worktree>/.walk/output.json`.

    Raises:
        ConfigError: The run has no worktree yet.
    """
    if run.worktree_path is None:
        msg = f"run {run.id} has no worktree"
        raise ConfigError(msg, detail={"run_id": run.id})
    return RunSession(
        run_id=run.id,
        worktree_path=run.worktree_path,
        allowed_tools=list(agent_input.allowed_tools),
        permission_authorizer=authorizer,
        effort=run.effort,
        model_id=run.model_id,
        max_turns=max_turns,
        timeout_s=timeout_s,
        env_allowlist=dict(env_allowlist),
        output_path=str(Path(run.worktree_path) / OUTPUT_RELATIVE_PATH),
    )
