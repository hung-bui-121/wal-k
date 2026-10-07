"""A fully wired `DefaultAgentExecutor` for the executor tests (E01-S27).

One real game repository (worktrees, WIP commits), one migrated database and fake model
adapters; `ExecutorEnv` exposes every service a test asserts on.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

import walk.agents
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from tests.fakes.fake_model_adapter import FakeModelAdapter, FakeScript, fake_descriptor
from walk.agents import (
    AgentInput,
    AgentInstance,
    AgentOutput,
    AgentOutputStatus,
    ConstitutionLoader,
    DefaultAgentManager,
    PolicyLoader,
    TemplateRenderer,
)
from walk.budgets import BudgetRepository, CostRepository, DefaultBudgetManager, DefaultCostManager
from walk.common.enums import Effort
from walk.common.roles import AgentRole
from walk.context import DefaultContextManager
from walk.hooks import DefaultHookManager, Hook, HookContext, HookName
from walk.integrations import GitCliProvider
from walk.memory import DefaultMemoryManager
from walk.model_router import (
    AgentEvent,
    AgentEventKind,
    DefaultModelRouter,
    ModelAdapter,
    ModelsConfig,
    RunSession,
)
from walk.orchestrator import BuiltinHookDeps
from walk.permissions import (
    ApprovalRepository,
    DefaultPermissionManager,
    PermissionEffect,
    PermissionRule,
)
from walk.persistence import Database, IdempotencyStore, IdSequenceStore
from walk.runtime import (
    AgentInputBuilder,
    AgentRun,
    AgentRunRepository,
    Checkpoint,
    CheckpointRepository,
    DefaultAgentExecutor,
    DefaultBoundaryAuditor,
    DefaultCheckpointManager,
    DefaultOutputApplier,
    DefaultSandboxManager,
    DefaultToolInvoker,
    HandoverRepository,
    PollingApprovalWaiter,
)
from walk.telemetry import (
    DefaultEvidenceManager,
    DefaultLedgerManager,
    EvidenceRepository,
    LedgerEvent,
    LedgerEventKind,
    TelemetryManager,
)
from walk.tools import DefaultToolRegistry, load_tool_specs
from walk.workflow import (
    TABLES_DIR,
    DefaultWorkflowManager,
    PhaseRepository,
    ProjectRepository,
    Story,
    WorkflowRepository,
)

AGENT_DEFAULTS = Path(walk.agents.__file__).resolve().parent / "defaults"
AGENT_TEMPLATES = Path(walk.agents.__file__).resolve().parent / "templates"
SENIOR = AgentRole.SENIOR_DEV
LEAD = AgentRole.LEAD_DEV
CODEX_MODEL = "fake-codex/sim"
CLAUDE_MODEL = "fake-claude/sim"
EXECUTOR_RULES = [
    PermissionRule(role=role, tool=tool, effect=PermissionEffect.ALLOW)
    for role in (SENIOR, LEAD)
    for tool in ("read", "write", "edit", "bash")
]
RECORDED_HOOKS = (
    HookName.ON_AGENT_START,
    HookName.ON_AGENT_END,
    HookName.ON_TASK_FAILED,
    HookName.ON_TOOL_AFTER,
    HookName.ON_MODEL_FALLBACK,
    HookName.ON_RECOVERY_RESUME,
)

ScriptSource = FakeScript | Callable[[AgentInput], FakeScript]


def completed_output(**fields: object) -> AgentOutput:
    """A valid COMPLETED output without context updates, with ``fields`` applied."""
    data: dict[str, object] = {
        "status": AgentOutputStatus.COMPLETED,
        "result": "done",
        "no_context_change_reason": "fake run",
    }
    data.update(fields)
    return AgentOutput.model_validate(data)


def script(**fields: object) -> FakeScript:
    """A fake script: 3 tool calls and a COMPLETED output unless overridden."""
    data: dict[str, object] = {"output": completed_output(), "tool_calls": 3}
    data.update(fields)
    return FakeScript.model_validate(data)


def fake_adapters(plan: ScriptSource, clock: FakeClock) -> dict[str, ModelAdapter]:
    """``fake-codex`` and ``fake-claude`` adapters playing ``plan``."""
    return {
        "fake-codex": FakeModelAdapter(
            "fake-codex", [fake_descriptor(CODEX_MODEL, "fake-codex")], plan, clock
        ),
        "fake-claude": FakeModelAdapter(
            "fake-claude", [fake_descriptor(CLAUDE_MODEL, "fake-claude")], plan, clock
        ),
    }


class DyingAdapter(FakeModelAdapter):
    """Fake whose first stream of each run dies like a killed kernel after ``die_after`` results.

    The task ends with `asyncio.CancelledError`, so the run row stays RUNNING with its
    checkpoints; the provider session stays known to this adapter (same process).
    """

    def __init__(
        self, provider: str, model_id: str, plan: ScriptSource, clock: FakeClock, die_after: int
    ) -> None:
        super().__init__(provider, [fake_descriptor(model_id, provider)], plan, clock)
        self._die_after = die_after
        self._died: set[str] = set()

    def run(self, input: AgentInput, session: RunSession) -> AsyncIterator[AgentEvent]:  # noqa: A002 - parameter name fixed by INTERFACES §2.1
        return self._dying(super().run(input, session), session.run_id)

    async def _dying(
        self, inner: AsyncIterator[AgentEvent], run_id: str
    ) -> AsyncIterator[AgentEvent]:
        results = 0
        async for event in inner:
            yield event
            if event.kind is AgentEventKind.TOOL_CALL_RESULT:
                results += 1
                if results == self._die_after and run_id not in self._died:
                    self._died.add(run_id)
                    raise asyncio.CancelledError


def _fake_model_policies(ai_root: Path, max_parallel_runs: int) -> Path:
    """A project `policies.yaml` routing every role to the fake models."""
    path = ai_root / "agents" / "policies.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    policy = f"model_policy: {{preferred: [{CODEX_MODEL}], fallback: [{CLAUDE_MODEL}]}}"
    lines = ["roles:"]
    for role in (SENIOR, LEAD):
        lines += [
            f"  {role.value}:",
            f"    {policy}",
            f"    max_parallel_runs: {max_parallel_runs}",
        ]
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return path


async def no_sleep(seconds: float) -> None:
    """Injected sleep: never waits."""
    del seconds


@dataclass
class ExecutorEnv:
    """The executor and every service around it."""

    executor: DefaultAgentExecutor
    agent: AgentInstance
    story: Story
    repo: Path
    db: Database
    ledger: DefaultLedgerManager
    hooks: DefaultHookManager
    git: GitCliProvider
    runs: AgentRunRepository
    items: WorkflowRepository
    workflow: DefaultWorkflowManager
    budgets: DefaultBudgetManager
    costs: DefaultCostManager
    evidence: DefaultEvidenceManager
    memory: DefaultMemoryManager
    applier: DefaultOutputApplier
    sandbox: DefaultSandboxManager
    inputs: AgentInputBuilder
    agents: DefaultAgentManager
    router: DefaultModelRouter
    tool_invoker: DefaultToolInvoker
    checkpoints: DefaultCheckpointManager
    permissions: DefaultPermissionManager
    adapters: dict[str, ModelAdapter]
    fired: list[HookContext]

    def hooks_fired(self, name: HookName) -> list[HookContext]:
        """Recorded contexts of ``name`` (see `RECORDED_HOOKS`)."""
        return [ctx for ctx in self.fired if ctx.name is name]

    async def kinds(self, run_id: str) -> list[LedgerEventKind]:
        """Kinds of the run's ledger events, in order."""
        return [event.kind for event in await self.ledger.query(run_id=run_id)]

    async def events(self, run_id: str, kind: LedgerEventKind) -> list[LedgerEvent]:
        """The run's ledger events of ``kind``."""
        return await self.ledger.query(run_id=run_id, kinds=[kind])

    def checkpoints_of(self, run_id: str) -> list[Checkpoint]:
        """The run's checkpoints by seq."""
        rows = (
            self.db.connect()
            .execute("SELECT json FROM checkpoints WHERE run_id = ? ORDER BY seq", (run_id,))
            .fetchall()
        )
        return [Checkpoint.model_validate_json(row[0]) for row in rows]

    async def run_to_end(self, purpose: str = "IMPLEMENT") -> AgentRun:
        """Start a run of the story, wait for its end and for every continuation run."""
        run = await self.executor.start(self.agent, self.story, purpose)
        ended = await self.executor.wait(run.id)
        await self.settle()
        return ended

    async def settle(self) -> None:
        """Wait until no run (fallback or repair continuations included) is executing."""
        while running := self.executor.running():
            for run in running:
                await self.executor.wait(run.id)


@dataclass
class BaseFixtures:
    """The shared runtime fixtures the environment is built on."""

    db: Database
    story: Story
    repo: Path
    ledger: DefaultLedgerManager
    hooks: DefaultHookManager
    memory: DefaultMemoryManager
    idempotency: IdempotencyStore
    git: GitCliProvider
    runs: AgentRunRepository
    clock: FakeClock
    ids: SequentialIdFactory = field(default_factory=SequentialIdFactory)


EnvFactory = Callable[..., Awaitable[ExecutorEnv]]


def register_recorders(hooks: DefaultHookManager) -> list[HookContext]:
    """Record every context of `RECORDED_HOOKS` into the returned list."""
    fired: list[HookContext] = []

    async def record(ctx: HookContext) -> None:
        fired.append(ctx)

    for name in RECORDED_HOOKS:
        hooks.register(Hook(name=name, id=f"test.{name.value}", kind="builtin"), record)
    return fired


async def build_executor_env(
    base: BaseFixtures,
    fired: list[HookContext],
    plan: ScriptSource | None = None,
    *,
    adapters: dict[str, ModelAdapter] | None = None,
    checkpoint_every: int = 10,
    model_id: str = CODEX_MODEL,
    prompt_version: Callable[[str], str] | None = None,
    rules: list[PermissionRule] | None = None,
    kernel_instance: str = "instance-a",
    sleep: Callable[[float], Awaitable[None]] = no_sleep,
    max_parallel_runs: int = 1,
    approval_sleep: Callable[[float], Awaitable[None]] = no_sleep,
) -> ExecutorEnv:
    """Wire the executor over ``base``; ``plan`` drives both fake adapters.

    ``approval_sleep`` is awaited between approval polls; a real (short) sleep keeps a run
    paused for approval alive until the test decides the request.
    """
    db, clock = base.db, base.clock
    adapters = adapters if adapters is not None else fake_adapters(plan or script(), clock)
    descriptors = {d.id: d for adapter in adapters.values() for d in adapter.descriptors()}
    router = DefaultModelRouter(
        ModelsConfig(version="test", models=descriptors, families={}), adapters, clock
    )
    items = WorkflowRepository(db)
    workflow = DefaultWorkflowManager(
        db,
        items,
        ProjectRepository(db),
        IdSequenceStore(db),
        base.ledger,
        base.hooks,
        clock,
        TABLES_DIR,
    )
    permissions = DefaultPermissionManager(
        EXECUTOR_RULES if rules is None else rules,
        [],
        ApprovalRepository(db),
        base.ledger,
        base.hooks,
        IdSequenceStore(db),
        clock,
        project_key="DEMO",
    )
    tools = DefaultToolRegistry(load_tool_specs([]))
    agents = DefaultAgentManager(
        ConstitutionLoader(AGENT_DEFAULTS, None),
        PolicyLoader(
            AGENT_DEFAULTS / "policies.yaml",
            _fake_model_policies(db.path.parent, max_parallel_runs),
        ),
        permissions,
        tools,
        TemplateRenderer(AGENT_TEMPLATES),
    )
    budgets = DefaultBudgetManager(db, BudgetRepository(db), base.ledger, base.hooks, clock)
    costs = DefaultCostManager(db, CostRepository(db), base.ledger, budgets, items)

    async def head() -> str:
        return await base.git.head(str(base.repo))

    context = DefaultContextManager(
        workflow, items, base.memory, base.hooks, base.ledger, clock, head_resolver=head
    )
    inputs = AgentInputBuilder(
        agents, context, tools, budgets, PhaseRepository(db), clock, project_key="DEMO"
    )
    sandbox = DefaultSandboxManager(base.repo, base.git, ["main"])
    checkpoints = DefaultCheckpointManager(
        db,
        base.runs,
        CheckpointRepository(db),
        HandoverRepository(db),
        base.git,
        base.memory,
        base.hooks,
        base.ledger,
        IdSequenceStore(db),
        base.idempotency,
        clock,
        project_key="DEMO",
    )
    waiter = PollingApprovalWaiter(
        ApprovalRepository(db), clock, permissions=permissions, sleep=approval_sleep
    )
    tool_invoker = DefaultToolInvoker(
        permissions,
        tools,
        budgets,
        base.hooks,
        base.ledger,
        base.runs,
        checkpoints,
        waiter,
        clock,
        project_key="DEMO",
    )
    evidence = DefaultEvidenceManager(
        db, db.path.parent, EvidenceRepository(db), base.ledger, IdSequenceStore(db), clock
    )
    applier = DefaultOutputApplier(base.memory, evidence, workflow, base.git, clock)
    executor = DefaultAgentExecutor(
        db,
        base.runs,
        items,
        workflow,
        router,
        inputs,
        sandbox,
        checkpoints,
        tool_invoker,
        DefaultBoundaryAuditor(),
        applier,
        base.git,
        budgets,
        costs,
        base.hooks,
        base.ledger,
        base.ids,
        clock,
        agents,
        permissions,
        project_key="DEMO",
        kernel_instance=kernel_instance,
        ready_env_keys=lambda: {"git"},
        sleep=sleep,
        prompt_version=prompt_version,
    )
    agent = await agents.instantiate(SENIOR, base.story, model_id, Effort.MEDIUM, [], {"git"})
    policy = agent.runtime_policy.model_copy(
        update={"checkpoint_every_tool_calls": checkpoint_every}
    )
    return ExecutorEnv(
        executor=executor,
        agent=agent.model_copy(update={"runtime_policy": policy}),
        story=base.story,
        repo=base.repo,
        db=db,
        ledger=base.ledger,
        hooks=base.hooks,
        git=base.git,
        runs=base.runs,
        items=items,
        workflow=workflow,
        budgets=budgets,
        costs=costs,
        evidence=evidence,
        memory=base.memory,
        applier=applier,
        sandbox=sandbox,
        inputs=inputs,
        agents=agents,
        router=router,
        tool_invoker=tool_invoker,
        checkpoints=checkpoints,
        permissions=permissions,
        adapters=adapters,
        fired=fired,
    )


def builtin_deps(env: ExecutorEnv, telemetry: TelemetryManager) -> BuiltinHookDeps:
    """The E02-S08 builtin hook dependencies over ``env`` (default branch ``main``)."""
    return BuiltinHookDeps(
        hooks=env.hooks,
        checkpoints=env.checkpoints,
        memory=env.memory,
        git=env.git,
        executor=env.executor,
        permissions=env.permissions,
        telemetry=telemetry,
        workflow=env.workflow,
        runs=env.runs,
        default_branch="main",
    )
