"""Composition root: the only place that wires concrete implementations together.

`build_kernel` (E01-S30) constructs every E01 service in dependency order from the repository's
configuration, or from `KernelOverrides` in tests and epic gates (WBS §3.6). It performs no
network or provider call and starts no task. The ``open_*`` helpers wire the subsets the
offline CLI commands use.
"""

import asyncio
import importlib.util
import logging
import os
import random
import shutil
import socket
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Final

from pydantic import ConfigDict, Field, SkipValidation

import walk.agents
import walk.model_router
from walk.agents import (
    AgentInput,
    ConstitutionLoader,
    DefaultAgentManager,
    PolicyLoader,
    TemplateRenderer,
    render_constitution,
    render_input_sections,
)
from walk.budgets import (
    BudgetRepository,
    CostRepository,
    DefaultBudgetManager,
    DefaultCostManager,
)
from walk.common.clock import Clock, SystemClock
from walk.common.errors import ConfigError
from walk.common.ids import IdFactory, ProjectKey, RunId
from walk.common.models import WalkModel
from walk.context import DefaultContextManager
from walk.effort import DefaultEffortManager, EffortRequest, StaticCostEstimator
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.integrations import (
    AsyncioSubprocessRunner,
    CredentialStore,
    DefaultIntegrationManager,
    GitCliProvider,
    GitProvider,
    ManifestStore,
    SubprocessRunner,
)
from walk.integrations.credentials import KeyringBackend, SystemKeyringBackend
from walk.memory import DefaultMemoryManager, MemoryIndexRepository, split_document
from walk.model_router import (
    DefaultModelRouter,
    ModelAdapter,
    ModelDescriptor,
    ModelsConfig,
    load_models_config,
)
from walk.model_router.adapters.claude import ClaudeAdapter
from walk.model_router.adapters.claude.client import SdkClaudeClient, missing_sdk_options
from walk.model_router.adapters.codex import CodexAdapter
from walk.model_router.adapters.codex.process import AsyncioCodexProcessLauncher
from walk.orchestrator import (
    DEFAULT_MAX_PARALLEL_AGENTS,
    DEFAULT_POLL_INTERVAL_S,
    DefaultOrchestrator,
    DefaultTaskRouter,
    Scheduler,
    StatusBuilder,
)
from walk.permissions import ApprovalRepository, DefaultPermissionManager, PermissionRule
from walk.persistence import Database, IdempotencyStore, IdSequenceStore, MigrationRunner
from walk.runtime import (
    AgentInputBuilder,
    AgentRun,
    AgentRunRepository,
    CheckpointRepository,
    DefaultAgentExecutor,
    DefaultBoundaryAuditor,
    DefaultCheckpointManager,
    DefaultOutputApplier,
    DefaultSandboxManager,
    DefaultToolInvoker,
    HandoverRepository,
    PollingApprovalWaiter,
    RecoveryManager,
)
from walk.telemetry import (
    DefaultEvidenceManager,
    DefaultLedgerManager,
    DefaultTelemetryManager,
    EvidenceRepository,
    LedgerRepository,
)
from walk.tools import DefaultToolRegistry, load_tool_specs
from walk.workflow import (
    TABLES_DIR,
    DefaultWorkflowManager,
    PhaseRepository,
    Project,
    ProjectRepository,
    WorkflowRepository,
)

_LOG = logging.getLogger(__name__)

DEFAULT_READY_ENV_KEYS: frozenset[str] = frozenset({"git"})
"""Environment keys assumed available when git is on PATH (E02-S02 derives them)."""

_AI_DIR = ".ai"
_DB_FILE = "kernel.db"
_AGENTS_PACKAGE: Final = Path(walk.agents.__file__).resolve().parent
_AGENT_DEFAULTS: Final = _AGENTS_PACKAGE / "defaults"
_AGENT_TEMPLATES: Final = _AGENTS_PACKAGE / "templates"
_DEFAULT_MODELS: Final = (
    Path(walk.model_router.__file__).resolve().parent / "defaults" / "models.yaml"
)
_SCHEDULED_STATES: Final = TABLES_DIR / "scheduled_states.yaml"
_CLAUDE_SDK: Final = "claude_agent_sdk"
_GIT: Final = "git"
_JITTER: Final = 0.1  # ARCHITECTURE §5.1 retry backoff jitter: up to +10 %
_NO_PROJECT: Final = "no project in .ai/kernel.db; run 'walk bootstrap'"
_PROBE_TIMEOUT_S: Final = 30  # `claude --version` health probe


class KernelSettings(WalkModel):
    """Inputs of `build_kernel` from the command line (WBS §3.6)."""

    repo_path: Path = Field(description="Game repository root.")
    max_parallel: int = Field(
        default=DEFAULT_MAX_PARALLEL_AGENTS, description="Runs executing at once."
    )
    poll_interval_s: float = Field(
        default=DEFAULT_POLL_INTERVAL_S, description="Seconds between ticks without a wake-up."
    )
    webhook_port: int | None = Field(
        default=None, description="Jira webhook port (accepted, unused until E03-S05)."
    )
    skip_preflight: bool = Field(default=False, description="Skip the §26 preflight (E02-S02).")
    json_output: bool = Field(default=False, description="Machine-readable CLI output.")


class KernelOverrides(WalkModel):
    """Test doubles for `build_kernel` (tests and epic gates only; WBS §3.6)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    adapters: SkipValidation[dict[str, ModelAdapter] | None] = Field(
        default=None, description="Adapters by provider; replace ClaudeAdapter/CodexAdapter."
    )
    git: SkipValidation[GitProvider | None] = Field(
        default=None, description="Replaces GitCliProvider."
    )
    clock: SkipValidation[Clock | None] = Field(
        default=None, description="Replaces the system clock."
    )
    id_factory: SkipValidation[IdFactory | None] = Field(
        default=None, description="ULIDs only; sequences always come from IdSequenceStore."
    )
    subprocess_runner: SkipValidation[SubprocessRunner | None] = Field(
        default=None, description="Runner of git subprocesses."
    )
    sleep: SkipValidation[Callable[[float], Awaitable[None]] | None] = Field(
        default=None, description="Back-off and approval-poll sleep (no jitter)."
    )
    kernel_instance: str | None = Field(default=None, description="Kernel instance id.")
    ready_env_keys: set[str] | None = Field(
        default=None, description="Environment keys available to tools."
    )
    keyring_backend: SkipValidation[KeyringBackend | None] = Field(
        default=None, description="Replaces the OS keyring behind the CredentialStore."
    )


class KernelHandle:
    """Every service of one kernel process (`build_kernel`)."""

    def __init__(
        self,
        *,
        settings: KernelSettings,
        project_key: ProjectKey,
        kernel_instance: str,
        db: Database,
        ledger: DefaultLedgerManager,
        telemetry: DefaultTelemetryManager,
        evidence: DefaultEvidenceManager,
        hooks: DefaultHookManager,
        workflow: DefaultWorkflowManager,
        budgets: DefaultBudgetManager,
        costs: DefaultCostManager,
        effort: DefaultEffortManager,
        tools: DefaultToolRegistry,
        permissions: DefaultPermissionManager,
        memory: DefaultMemoryManager,
        agents: DefaultAgentManager,
        router: DefaultModelRouter,
        git: GitProvider,
        context: DefaultContextManager,
        checkpoints: DefaultCheckpointManager,
        tool_invoker: DefaultToolInvoker,
        executor: DefaultAgentExecutor,
        recovery: RecoveryManager,
        scheduler: Scheduler,
        orchestrator: DefaultOrchestrator,
        status_builder: StatusBuilder,
        credentials: CredentialStore,
        integrations: DefaultIntegrationManager,
    ) -> None:
        """Hold the wired services (built by `build_kernel` only)."""
        self.settings = settings
        self.project_key = project_key
        self.kernel_instance = kernel_instance
        self.db = db
        self.ledger = ledger
        self.telemetry = telemetry
        self.evidence = evidence
        self.hooks = hooks
        self.workflow = workflow
        self.budgets = budgets
        self.costs = costs
        self.effort = effort
        self.tools = tools
        self.permissions = permissions
        self.memory = memory
        self.agents = agents
        self.router = router
        self.git = git
        self.context = context
        self.checkpoints = checkpoints
        self.tool_invoker = tool_invoker
        self.executor = executor
        self.recovery = recovery
        self.scheduler = scheduler
        self.orchestrator = orchestrator
        self.status_builder = status_builder
        self.credentials = credentials
        self.integrations = integrations
        self._closed = False

    async def aclose(self) -> None:
        """Cancel running run tasks without a checkpoint and close the database.

        The runs stay RUNNING; the next kernel instance's recovery resumes them. Idempotent.
        """
        if self._closed:
            return
        self._closed = True
        await self.executor.shutdown()
        self.db.close()


def build_kernel(
    settings: KernelSettings, *, overrides: KernelOverrides | None = None
) -> KernelHandle:
    """Wire every E01 service for ``settings.repo_path`` (ARCHITECTURE §1.2, §3.4).

    Opens (and creates) `<repo>/.ai/kernel.db`, applies pending migrations and constructs the
    services in dependency order. No network or provider call is made and no task starts.

    Raises:
        ConfigError: The database holds no project or several, or a configuration file
            (constitutions, policies, models, transition tables) is invalid.
    """
    o = overrides or KernelOverrides()
    repo = settings.repo_path
    ai_root = repo / _AI_DIR
    clock: Clock = o.clock or SystemClock()
    sleep = o.sleep or _jittered_sleep
    db = open_database(repo)
    MigrationRunner(db, "project").apply_pending()
    project = _single_project(db)
    key = project.key
    instance = o.kernel_instance or str(uuid.uuid4())
    ready_env_keys = o.ready_env_keys if o.ready_env_keys is not None else _ready_env_keys()
    credentials = CredentialStore(os.environ, o.keyring_backend or SystemKeyringBackend())
    ids = IdSequenceStore(db)
    ulids: IdFactory = o.id_factory or ids
    idempotency = IdempotencyStore(db, clock)
    ledger = DefaultLedgerManager(db, LedgerRepository(db), ulids, clock)
    telemetry = DefaultTelemetryManager(repo, LedgerRepository(db), clock)
    evidence = DefaultEvidenceManager(db, ai_root, EvidenceRepository(db), ledger, ids, clock)
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, clock)
    items = WorkflowRepository(db)
    workflow = DefaultWorkflowManager(
        db, items, ProjectRepository(db), ids, ledger, hooks, clock, TABLES_DIR
    )
    budgets = DefaultBudgetManager(db, BudgetRepository(db), ledger, hooks, clock)
    costs = DefaultCostManager(db, CostRepository(db), ledger, budgets, items)
    effort = DefaultEffortManager(
        StaticCostEstimator(), ledger, hooks, clock, _effort_approval, project_key=key
    )
    tools, permissions, agents, renderer = _agent_services(
        db, ai_root, ledger, hooks, ids, clock, key
    )
    memory = DefaultMemoryManager(
        ai_root, MemoryIndexRepository(db), ledger, hooks, ids, clock, project_key=key
    )
    runner = o.subprocess_runner or AsyncioSubprocessRunner()
    git = o.git or GitCliProvider(repo, runner, ledger, idempotency, clock, project_key=key)
    integrations = _integrations(repo, runner, credentials, tools, clock)
    runs = AgentRunRepository(db, clock=clock)
    checkpoints = DefaultCheckpointManager(
        db,
        runs,
        CheckpointRepository(db),
        HandoverRepository(db),
        git,
        memory,
        hooks,
        ledger,
        ids,
        idempotency,
        clock,
        project_key=key,
        default_branch=project.default_branch,
    )

    async def head() -> str:
        return await git.head(str(repo))

    context = DefaultContextManager(
        workflow,
        items,
        memory,
        hooks,
        ledger,
        clock,
        head_resolver=head,
        handovers=checkpoints.latest_open_handover_doc,
    )
    router = _model_router(ai_root, o, clock, sleep, runner)
    inputs = AgentInputBuilder(
        agents, context, tools, budgets, PhaseRepository(db), clock, project_key=key
    )
    sandbox = DefaultSandboxManager(
        repo, git, list(project.protected_branches), default_branch=project.default_branch
    )
    waiter = PollingApprovalWaiter(
        ApprovalRepository(db), clock, permissions=permissions, sleep=sleep
    )
    tool_invoker = DefaultToolInvoker(
        permissions,
        tools,
        budgets,
        hooks,
        ledger,
        runs,
        checkpoints,
        waiter,
        clock,
        project_key=key,
    )
    applier = DefaultOutputApplier(memory, evidence, workflow, git, clock)
    executor = DefaultAgentExecutor(
        db,
        runs,
        items,
        workflow,
        router,
        inputs,
        sandbox,
        checkpoints,
        tool_invoker,
        DefaultBoundaryAuditor(),
        applier,
        git,
        budgets,
        costs,
        hooks,
        ledger,
        ulids,
        clock,
        agents,
        permissions,
        project_key=key,
        kernel_instance=instance,
        ready_env_keys=lambda: set(ready_env_keys),
        sleep=sleep,
        prompt_version=renderer.version_of,
    )
    recovery = RecoveryManager(
        runs,
        checkpoints,
        executor,
        router,
        agents,
        items,
        hooks,
        ledger,
        clock,
        kernel_instance=instance,
        project_key=key,
        ready_env_keys=lambda: set(ready_env_keys),
        sandbox=sandbox,
    )
    scheduler = Scheduler(
        db,
        ProjectRepository(db),
        workflow,
        DefaultTaskRouter(_SCHEDULED_STATES, agents, runs, workflow),
        agents,
        effort,
        budgets,
        router,
        executor,
        checkpoints,
        idempotency,
        telemetry,
        clock,
        project_key=key,
        max_parallel_agents=settings.max_parallel,
        ready_env_keys=lambda: set(ready_env_keys),
    )
    status_builder = StatusBuilder(
        ProjectRepository(db),
        workflow,
        PhaseRepository(db),
        runs,
        budgets,
        ledger,
        project_key=key,
    )
    orchestrator = DefaultOrchestrator(
        scheduler,
        executor,
        recovery,
        status_builder,
        hooks,
        ledger,
        clock,
        project_key=key,
        kernel_instance=instance,
        poll_interval_s=settings.poll_interval_s,
    )

    async def wake_on_finish(run: AgentRun) -> None:
        del run
        await orchestrator.wake()

    executor.on_run_finished = wake_on_finish
    return KernelHandle(
        settings=settings,
        project_key=key,
        kernel_instance=instance,
        db=db,
        ledger=ledger,
        telemetry=telemetry,
        evidence=evidence,
        hooks=hooks,
        workflow=workflow,
        budgets=budgets,
        costs=costs,
        effort=effort,
        tools=tools,
        permissions=permissions,
        memory=memory,
        agents=agents,
        router=router,
        git=git,
        context=context,
        checkpoints=checkpoints,
        tool_invoker=tool_invoker,
        executor=executor,
        recovery=recovery,
        scheduler=scheduler,
        orchestrator=orchestrator,
        status_builder=status_builder,
        credentials=credentials,
        integrations=integrations,
    )


def open_integrations(
    repo: Path,
    *,
    runner: SubprocessRunner | None = None,
    keyring_backend: KeyringBackend | None = None,
    clock: Clock | None = None,
) -> DefaultIntegrationManager:
    """Wire the §26 preflight for ``repo`` (``walk doctor``); opens no database.

    Args:
        repo: Game repository root.
        runner: Runs the probes (the asyncio runner by default).
        keyring_backend: OS keyring behind the `CredentialStore` (the system keyring by default).
        clock: Stamps the manifest (the system clock by default).

    Raises:
        ConfigError: The packaged tool catalogue is invalid.
    """
    credentials = CredentialStore(os.environ, keyring_backend or SystemKeyringBackend())
    tools = DefaultToolRegistry(load_tool_specs([]))
    return _integrations(
        repo, runner or AsyncioSubprocessRunner(), credentials, tools, clock or SystemClock()
    )


def _integrations(
    repo: Path,
    runner: SubprocessRunner,
    credentials: CredentialStore,
    tools: DefaultToolRegistry,
    clock: Clock,
) -> DefaultIntegrationManager:
    """The preflight manager; skills join with E02-S05/S07, the Unity path with E03-S10."""
    return DefaultIntegrationManager(
        runner=runner,
        credentials=credentials,
        manifest_store=ManifestStore(repo / _AI_DIR, clock),
        tools=tools,
        clock=clock,
        machine_id=socket.gethostname(),
        unity_path=None,
        project_path=str(repo),
        required_skills=[],
        available_skills=[],
        sdk_option_probe=missing_sdk_options,
    )


def _agent_services(  # noqa: PLR0917 - private wiring step of build_kernel
    db: Database,
    ai_root: Path,
    ledger: DefaultLedgerManager,
    hooks: DefaultHookManager,
    ids: IdSequenceStore,
    clock: Clock,
    key: ProjectKey,
) -> tuple[DefaultToolRegistry, DefaultPermissionManager, DefaultAgentManager, TemplateRenderer]:
    """Tools, permissions, the agent manager and the prompt renderer (kernel + project files)."""
    tools = DefaultToolRegistry(load_tool_specs([]))
    constitutions = ConstitutionLoader(_AGENT_DEFAULTS, ai_root / "agents" / "roles")
    policies = PolicyLoader(_AGENT_DEFAULTS / "policies.yaml", ai_root / "agents" / "policies.yaml")
    permissions = DefaultPermissionManager(
        _constitution_rules(constitutions),
        [],
        ApprovalRepository(db),
        ledger,
        hooks,
        ids,
        clock,
        project_key=key,
    )
    renderer = TemplateRenderer(_AGENT_TEMPLATES, ai_root / "agents" / "templates")
    agents = DefaultAgentManager(constitutions, policies, permissions, tools, renderer)
    return tools, permissions, agents, renderer


def build_status_reader(repo: Path) -> StatusBuilder:
    """A `StatusBuilder` on a read-only connection; no adapter is constructed.

    Raises:
        ConfigError: The database does not exist, or holds no project or several.
    """
    db = open_database(repo, read_only=True)
    clock = SystemClock()
    key = _single_project(db).key
    ledger = DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), clock)
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, clock)
    workflow = DefaultWorkflowManager(
        db,
        WorkflowRepository(db),
        ProjectRepository(db),
        IdSequenceStore(db),
        ledger,
        hooks,
        clock,
        TABLES_DIR,
    )
    return StatusBuilder(
        ProjectRepository(db),
        workflow,
        PhaseRepository(db),
        AgentRunRepository(db, clock=clock),
        DefaultBudgetManager(db, BudgetRepository(db), ledger, hooks, clock),
        ledger,
        project_key=key,
    )


def _single_project(db: Database) -> Project:
    rows = db.connect().execute("SELECT json FROM projects ORDER BY key").fetchall()
    if not rows:
        raise ConfigError(_NO_PROJECT, detail={"db": str(db.path)})
    if len(rows) > 1:
        msg = f"expected exactly one project in .ai/kernel.db, found {len(rows)}"
        raise ConfigError(msg, detail={"db": str(db.path), "projects": len(rows)})
    return Project.model_validate_json(rows[0][0])


def _ready_env_keys() -> set[str]:
    return set(DEFAULT_READY_ENV_KEYS) if shutil.which(_GIT) else set()


def _constitution_rules(constitutions: ConstitutionLoader) -> list[PermissionRule]:
    """The kernel rule set until E02-S10: every role's constitution rules (ADR-0006 D-6)."""
    return [
        rule
        for role in constitutions.available_roles()
        for rule in constitutions.load(role).tool_permissions
    ]


def _model_router(
    ai_root: Path,
    overrides: KernelOverrides,
    clock: Clock,
    sleep: Callable[[float], Awaitable[None]],
    runner: SubprocessRunner,
) -> DefaultModelRouter:
    config = load_models_config(_DEFAULT_MODELS, ai_root / "agents" / "models.yaml")
    if overrides.adapters is not None:
        adapters = dict(overrides.adapters)
        extra = {
            descriptor.id: descriptor
            for adapter in adapters.values()
            for descriptor in adapter.descriptors()
            if descriptor.id not in config.models
        }
        config = config.model_copy(update={"models": {**config.models, **extra}})
    else:
        adapters = _real_adapters(config, ai_root, clock, sleep, runner)
    return DefaultModelRouter(_disable_unserved(config, adapters), adapters, clock)


def _real_adapters(
    config: ModelsConfig,
    ai_root: Path,
    clock: Clock,
    sleep: Callable[[float], Awaitable[None]],
    runner: SubprocessRunner,
) -> dict[str, ModelAdapter]:
    project_constitution = _project_constitution(ai_root)

    async def probe(argv: list[str]) -> tuple[int, str, str]:
        result = await runner.run(argv, timeout_s=_PROBE_TIMEOUT_S)
        return result.exit_code, result.stdout, result.stderr

    def system_prompt(agent_input: AgentInput) -> str:
        return render_constitution(agent_input.constitution, project_constitution)

    def user_message(agent_input: AgentInput) -> str:
        return agent_input.instructions_markdown + "\n\n" + render_input_sections(agent_input)

    def served(provider: str) -> list[ModelDescriptor]:
        return [d for d in config.models.values() if d.provider == provider]

    adapters: dict[str, ModelAdapter] = {
        "codex": CodexAdapter(
            AsyncioCodexProcessLauncher(),
            served("codex"),
            clock,
            system_prompt_builder=system_prompt,
            user_message_builder=user_message,
            sleep=sleep,
        )
    }
    if importlib.util.find_spec(_CLAUDE_SDK) is not None:
        adapters["claude"] = ClaudeAdapter(
            SdkClaudeClient(probe=probe),
            served("claude"),
            clock,
            system_prompt_builder=system_prompt,
            user_message_builder=user_message,
            sleep=sleep,
        )
    else:
        _LOG.warning("claude_agent_sdk is not installed; claude models are disabled")
    return adapters


def _disable_unserved(config: ModelsConfig, adapters: dict[str, ModelAdapter]) -> ModelsConfig:
    """Models whose provider has no adapter are disabled (and never selected)."""
    unserved = {
        model_id: descriptor.model_copy(update={"enabled": False})
        for model_id, descriptor in config.models.items()
        if descriptor.enabled and descriptor.provider not in adapters
    }
    if unserved:
        _LOG.warning("models without an adapter disabled", extra={"models": sorted(unserved)})
    return config.model_copy(update={"models": {**config.models, **unserved}})


def _project_constitution(ai_root: Path) -> str | None:
    path = ai_root / "project" / "constitution.md"
    if not path.is_file():
        return None
    _, sections = split_document(path, path.read_text(encoding="utf-8"))
    return "\n\n".join(f"## {name}\n\n{body}".rstrip() for name, body in sections.items())


async def _effort_approval(run_id: RunId, request: EffortRequest) -> bool:
    """Effort changes that need approval are refused until approvals are wired (E02-S11)."""
    _LOG.info(
        "effort change needs approval; refused", extra={"run_id": run_id, "target": request.target}
    )
    return False


async def _jittered_sleep(seconds: float) -> None:
    """`asyncio.sleep` with up to +10 % jitter (ARCHITECTURE §5.1 retry backoff)."""
    await asyncio.sleep(seconds * (1 + random.uniform(0, _JITTER)))  # noqa: S311 - jitter, not crypto


def open_database(repo: Path, *, read_only: bool = False) -> Database:
    """Open the project database ``<repo>/.ai/kernel.db``.

    Args:
        repo: Game repository root.
        read_only: Open without write access; the database must already exist.

    Returns:
        A connected `Database`. A writable database (and ``.ai/``) is created when missing.

    Raises:
        ConfigError: If a read-only database does not exist or cannot be opened.
    """
    db = Database(repo / _AI_DIR / _DB_FILE, read_only=read_only)
    db.connect()
    return db


def open_workflow(db: Database, *, clock: Clock | None = None) -> DefaultWorkflowManager:
    """Wire a `DefaultWorkflowManager` (with ledger and hook manager) on ``db``.

    Args:
        db: An open project database.
        clock: Time source; the system clock when ``None`` (tests inject a fake).

    Raises:
        ConfigError: If a packaged transition table is invalid.
    """
    time = clock or SystemClock()
    ids = IdSequenceStore(db)
    ledger = DefaultLedgerManager(db, LedgerRepository(db), ids, time)
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, time)
    return DefaultWorkflowManager(
        db,
        WorkflowRepository(db),
        ProjectRepository(db),
        ids,
        ledger,
        hooks,
        time,
        TABLES_DIR,
    )


def open_costs(db: Database, *, clock: Clock | None = None) -> DefaultCostManager:
    """Wire a `DefaultCostManager` (with its budget manager, ledger and hooks) on ``db``.

    Args:
        db: An open project database.
        clock: Time source; the system clock when ``None`` (tests inject a fake).
    """
    time = clock or SystemClock()
    ledger = DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), time)
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, time)
    budgets = DefaultBudgetManager(db, BudgetRepository(db), ledger, hooks, time)
    return DefaultCostManager(db, CostRepository(db), ledger, budgets, WorkflowRepository(db))


def open_memory(
    db: Database, repo: Path, *, project_key: ProjectKey, clock: Clock | None = None
) -> DefaultMemoryManager:
    """Wire a `DefaultMemoryManager` for ``<repo>/.ai`` (with ledger and hooks) on ``db``.

    Args:
        db: An open project database.
        repo: Game repository root.
        project_key: Project of the database (stamped on ledger events and hook contexts).
        clock: Time source; the system clock when ``None`` (tests inject a fake).
    """
    time = clock or SystemClock()
    ids = IdSequenceStore(db)
    ledger = DefaultLedgerManager(db, LedgerRepository(db), ids, time)
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, time)
    return DefaultMemoryManager(
        repo / _AI_DIR,
        MemoryIndexRepository(db),
        ledger,
        hooks,
        ids,
        time,
        project_key=project_key,
    )
