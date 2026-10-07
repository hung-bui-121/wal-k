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
from typing import Final, cast

from pydantic import ConfigDict, Field, SkipValidation

import walk
import walk.agents
import walk.model_router
import walk.skills
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
from walk.common.roles import AgentRole
from walk.context import DefaultContextManager
from walk.effort import DefaultEffortManager, EffortRequest, StaticCostEstimator
from walk.hooks import DefaultHookManager, HookCallable, HookContext, HookExecutionRepository
from walk.improvement import PINS_PATH, BehaviorVersionCatalog, KernelVersionPins
from walk.integrations import (
    AsyncioSubprocessRunner,
    CredentialStore,
    DefaultIntegrationManager,
    GitCliProvider,
    GitProvider,
    IntegrationManager,
    ManifestStore,
    SubprocessRunner,
)
from walk.integrations.credentials import KeyringBackend, SystemKeyringBackend
from walk.memory import (
    DefaultMemoryManager,
    MemoryIndexRepository,
    contains_secret,
    split_document,
)
from walk.model_router import (
    DefaultModelRouter,
    ModelAdapter,
    ModelDescriptor,
    ModelsConfig,
    load_models_config,
)
from walk.model_router.adapters.claude import ClaudeAdapter
from walk.model_router.adapters.claude.client import SdkClaudeClient, missing_sdk_options
from walk.model_router.adapters.claude.projector import ClaudeSkillProjector
from walk.model_router.adapters.codex import CodexAdapter
from walk.model_router.adapters.codex.process import AsyncioCodexProcessLauncher
from walk.model_router.adapters.codex.projector import CodexSkillProjector
from walk.orchestrator import (
    DEFAULT_MAX_PARALLEL_AGENTS,
    DEFAULT_POLL_INTERVAL_S,
    BootstrapOptions,
    Bootstrapper,
    BuiltinHookDeps,
    DefaultOrchestrator,
    DefaultTaskRouter,
    Scheduler,
    StatusBuilder,
    register_builtins,
)
from walk.permissions import (
    ApprovalRepository,
    DefaultPermissionManager,
    PermissionsFile,
    load_defaults,
    load_project_rules,
    merge_narrowing,
)
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
    EventApprovalWaiter,
    HandoverRepository,
    RecoveryManager,
)
from walk.runtime.sandbox import WORKTREES_DIR, scrubbed_env
from walk.skills import DefaultSkillRegistry, DriftReport, HideTracked, SkillProjector
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
    Bug,
    DefaultWorkflowManager,
    PhaseRepository,
    Project,
    ProjectRepository,
    Story,
    Task,
    WorkflowRepository,
    WorkItem,
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
_PACKAGE_ROOT: Final = Path(walk.__file__).resolve().parent
_BUILTIN_SKILLS: Final = Path(walk.skills.__file__).resolve().parent / "builtin"
_ACTORS: Final = frozenset({AgentRole.USER, AgentRole.KERNEL})  # never instantiated as agents
_CLAUDE_SDK: Final = "claude_agent_sdk"
_GIT: Final = "git"
_JITTER: Final = 0.1  # ARCHITECTURE §5.1 retry backoff jitter: up to +10 %
_NO_PROJECT: Final = "no project in .ai/kernel.db; run 'walk bootstrap'"
_NO_DATABASE: Final = "no .ai/kernel.db; run 'walk bootstrap'"
_GIT_EXCLUDE: Final = "info/exclude"
PROJECTIONS_DIR: Final = Path(".walk") / "projections"
"""Repo-level projection folder per provider (`walk skills sync`, startup drift check)."""
_PROBE_TIMEOUT_S: Final = 30  # `claude --version` health probe
_PROJECT_HOOKS: Final = Path("agents") / "hooks.yaml"
_PERMISSIONS: Final = Path("agents") / "permissions.yaml"


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
    strict: bool = Field(
        default=False, description="Startup fails on skill projection drift (E02-S07)."
    )
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
    runner = o.subprocess_runner or AsyncioSubprocessRunner()
    hooks = DefaultHookManager(
        HookExecutionRepository(db),
        ledger,
        clock,
        command_runner=runner,
        cwd=str(repo),
        base_env=scrubbed_env(os.environ),  # project commands never see secrets (E02-S09)
    )
    items = WorkflowRepository(db)
    workflow = DefaultWorkflowManager(
        db, items, ProjectRepository(db), ids, ledger, hooks, clock, TABLES_DIR
    )
    budgets = DefaultBudgetManager(db, BudgetRepository(db), ledger, hooks, clock)
    costs = DefaultCostManager(db, CostRepository(db), ledger, budgets, items)
    effort = DefaultEffortManager(
        StaticCostEstimator(), ledger, hooks, clock, _effort_approval, project_key=key
    )
    git = o.git or GitCliProvider(repo, runner, ledger, idempotency, clock, project_key=key)
    tools, permissions, agents, renderer, skills, policies = _agent_services(
        db, ai_root, ledger, hooks, ids, clock, key, git
    )
    memory = DefaultMemoryManager(
        ai_root,
        MemoryIndexRepository(db),
        ledger,
        hooks,
        ids,
        clock,
        project_key=key,
        git=git,
        may_approve=_may_approve(ai_root),
    )
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
        repo,
        git,
        list(project.protected_branches),
        default_branch=project.default_branch,
        project_skills=_skill_projection(router, skills),
    )
    waiter = _approval_waiter(db, clock, permissions)
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
        approvals=ApprovalRepository(db),
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
        DefaultBoundaryAuditor(secret_scan=contains_secret),  # E02-S14: one secret scanner
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
        startup_checks=_startup_checks(
            _version_pin_check(ai_root, clock),
            _drift_check(skills, router, repo, strict=settings.strict),
            _approved_check(memory),
        ),
        expire_approvals=lambda: permissions.expire_due(clock.now()),
        projects=ProjectRepository(db),
        workflow=workflow,
        policies_path=ai_root / "agents" / "policies.yaml",
        model_known=_model_known(ai_root, router),
        on_policy_changed=policies.clear_cache,
    )

    async def wake_on_finish(run: AgentRun) -> None:
        del run
        await orchestrator.wake()

    executor.on_run_finished = wake_on_finish
    _wire_hooks(
        hooks,
        BuiltinHookDeps(
            hooks=hooks,
            checkpoints=checkpoints,
            memory=memory,
            git=git,
            executor=executor,
            permissions=permissions,
            telemetry=telemetry,
            workflow=workflow,
            runs=runs,
            default_branch=project.default_branch,
        ),
        _kernel_actions(memory, skills, telemetry, repo),
        ai_root / _PROJECT_HOOKS,
    )
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


def open_bootstrapper(
    repo: Path,
    options: BootstrapOptions,
    *,
    runner: SubprocessRunner | None = None,
    keyring_backend: KeyringBackend | None = None,
    clock: Clock | None = None,
) -> Bootstrapper:
    """Wire the Default* services for one bootstrap (the only place that constructs `Bootstrapper`).

    Called by `cmd_bootstrap` after its checks (confirmation, project key, Jira credentials)
    passed; opening the database creates `.ai/` and `.ai/kernel.db` (migrated by the run).

    Args:
        repo: Game repository root.
        options: The validated bootstrap options (key, provider, Unity path).
        runner: Runs the preflight probes and git (the asyncio runner by default).
        keyring_backend: OS keyring behind the `CredentialStore` (the system keyring by default).
        clock: Time source (the system clock by default).

    Raises:
        ConfigError: The database cannot be opened or the packaged tool catalogue is invalid.
    """
    time = clock or SystemClock()
    run = runner or AsyncioSubprocessRunner()
    db = open_database(repo)
    ledger = DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), time)
    key = options.project_key
    git = GitCliProvider(repo, run, ledger, IdempotencyStore(db, time), time, project_key=key)
    credentials = CredentialStore(os.environ, keyring_backend or SystemKeyringBackend())
    tools = DefaultToolRegistry(load_tool_specs([]))
    return Bootstrapper(
        # The bootstrapper calls only `preflight`; DefaultIntegrationManager gains the protocol's
        # provider attributes in E03-S03, and strict mypy then reports this cast as redundant.
        integrations=cast(
            "IntegrationManager",
            _integrations(repo, run, credentials, tools, time, unity_path=options.unity_path),
        ),
        memory=open_memory(db, repo, project_key=key, clock=time),
        git=git,
        database=db,
        migrations=MigrationRunner(db, "project"),
        projects=ProjectRepository(db),
        clock=time,
        kit_version=walk.__version__,
    )


def _integrations(
    repo: Path,
    runner: SubprocessRunner,
    credentials: CredentialStore,
    tools: DefaultToolRegistry,
    clock: Clock,
    *,
    unity_path: str | None = None,
) -> DefaultIntegrationManager:
    """The preflight manager; ``unity_path`` comes from `walk bootstrap --unity-path`.

    Skills join with E02-S05/S07; the configured Unity path of other commands with E03-S10.
    """
    return DefaultIntegrationManager(
        runner=runner,
        credentials=credentials,
        manifest_store=ManifestStore(repo / _AI_DIR, clock),
        tools=tools,
        clock=clock,
        machine_id=socket.gethostname(),
        unity_path=unity_path,
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
    git: GitProvider,
) -> tuple[
    DefaultToolRegistry,
    DefaultPermissionManager,
    DefaultAgentManager,
    TemplateRenderer,
    DefaultSkillRegistry,
    PolicyLoader,
]:
    """Tools, permissions, agents, renderer, skills and the policy loader (E02-S13 clears it)."""
    tools = DefaultToolRegistry(load_tool_specs([]))
    constitutions = ConstitutionLoader(_AGENT_DEFAULTS, ai_root / "agents" / "roles")
    policies = PolicyLoader(_AGENT_DEFAULTS / "policies.yaml", ai_root / "agents" / "policies.yaml")
    kernel_rules = _permission_rules(ai_root)
    permissions = DefaultPermissionManager(
        kernel_rules.rules,
        kernel_rules.protected_actions,
        ApprovalRepository(db),
        ledger,
        hooks,
        ids,
        clock,
        project_key=key,
    )
    renderer = TemplateRenderer(_AGENT_TEMPLATES, ai_root / "agents" / "templates")
    skills = _skills(ai_root, policies, db, git, ledger=ledger, clock=clock, key=key)
    agents = DefaultAgentManager(
        constitutions, policies, permissions, tools, renderer, skills=skills
    )
    return tools, permissions, agents, renderer, skills, policies


def _skills(
    ai_root: Path,
    policies: PolicyLoader,
    db: Database,
    git: GitProvider,
    *,
    ledger: DefaultLedgerManager,
    clock: Clock,
    key: ProjectKey,
) -> DefaultSkillRegistry:
    """Kernel built-ins plus `.ai/agents/skills`; role defaults from the runtime policies.

    Projections are recorded in ``db`` and the lock under ``ai_root``; worktree exclude files
    are resolved through ``git`` (E02-S06).
    """
    defaults = {
        role: policies.load(role).default_skills for role in AgentRole if role not in _ACTORS
    }

    async def exclude_path(worktree: str) -> str:
        return await git.git_path(worktree, _GIT_EXCLUDE)

    return DefaultSkillRegistry(
        _BUILTIN_SKILLS,
        ai_root / "agents" / "skills",
        defaults,
        db=db,
        ai_root=ai_root,
        exclude_path=exclude_path,
        ledger=ledger,
        clock=clock,
        project_key=key,
        hide_tracked=tracked_projection_guard(ai_root.parent, git),
    )


def _inside(path: str, root: Path) -> bool:
    return Path(path).resolve().is_relative_to(root)


def tracked_projection_guard(repo: Path, git: GitProvider) -> HideTracked:
    """The skill projection's ``hide_tracked`` step (E02-S14 Behavior 9-10).

    In a run worktree (`<repo>/.walk/worktrees/`) the tracked targets (e.g. the repository's
    own ``AGENTS.md``) get ``skip-worktree`` in that worktree's index, so the projection never
    shows as a change. Anywhere else a tracked target refuses the projection: the user's
    checkout never gets a hidden index flag.
    """
    runs = (repo / WORKTREES_DIR).resolve()

    async def hide(worktree: str, targets: list[str]) -> list[str]:
        if _inside(worktree, runs):
            return await git.hide_local_changes(worktree, targets)
        tracked = await git.hide_local_changes(worktree, targets, mark=False)
        if tracked:
            msg = f"{tracked[0]} is tracked; skills are projected into run worktrees only"
            raise ConfigError(msg, detail={"worktree": worktree, "tracked": tracked})
        return []

    return hide


def _approval_waiter(
    db: Database, clock: Clock, permissions: DefaultPermissionManager
) -> EventApprovalWaiter:
    """The run-side approval waiter, woken by every decision and expiry (E02-S11)."""
    waiter = EventApprovalWaiter(ApprovalRepository(db), clock, permissions=permissions)
    permissions.on_decided = lambda approval: waiter.resolve(approval.id, approval.state)
    return waiter


def _wire_hooks(
    hooks: DefaultHookManager,
    deps: BuiltinHookDeps,
    actions: dict[str, HookCallable],
    project_hooks: Path,
) -> None:
    """Builtins first (ADR-0016 D-3), then the project hooks, which cannot replace them."""
    register_builtins(hooks, deps)
    hooks.set_kernel_actions(actions)
    hooks.load_project_hooks(str(project_hooks))


def _kernel_actions(
    memory: DefaultMemoryManager,
    skills: DefaultSkillRegistry,
    telemetry: DefaultTelemetryManager,
    repo: Path,
) -> dict[str, HookCallable]:
    """The `KERNEL_ACTIONS` project hooks may name (E02-S09 Behavior 7)."""

    async def rebuild_index(ctx: HookContext) -> None:
        del ctx
        await memory.rebuild_index()

    async def sync_skills(ctx: HookContext) -> None:
        del ctx
        chosen = skills.load()
        for projector in skill_projectors():  # as `walk skills sync` without --worktree
            target = repo / PROJECTIONS_DIR / projector.provider
            target.mkdir(parents=True, exist_ok=True)
            await skills.project_all([projector], str(target), chosen)

    async def count(ctx: HookContext) -> None:
        telemetry.counter(f"hook.{ctx.payload['hook_id']}")

    return {
        "memory.rebuild_index": rebuild_index,
        "skills.sync": sync_skills,
        "telemetry.counter": count,
    }


def _skill_projection(
    router: DefaultModelRouter, skills: DefaultSkillRegistry
) -> Callable[[AgentRun, WorkItem, str], Awaitable[None]]:
    """The sandbox step projecting the run's skills for the run's provider (E02-S06)."""

    async def project(run: AgentRun, item: WorkItem, worktree: str) -> None:
        contract = item.contract if isinstance(item, Story | Task | Bug) else None
        required = list(contract.required_skills) if contract is not None else []
        chosen = skills.for_role(run.role, required)
        projector = router.adapter_for(run.model_id).skill_projector()
        await skills.project_all([projector], worktree, chosen)

    return project


def skill_projectors(clock: Clock | None = None) -> list[SkillProjector]:
    """The projectors of the kernel's providers (claude, codex), independent of SDK presence."""
    time = clock or SystemClock()
    return [ClaudeSkillProjector(clock=time), CodexSkillProjector(clock=time)]


def open_skill_registry(
    repo: Path, *, clock: Clock | None = None
) -> tuple[DefaultSkillRegistry, Database]:
    """The skill registry of ``repo`` with projection support, and its open database.

    Raises:
        ConfigError: ``repo`` has no `.ai/kernel.db` (not bootstrapped), or the database holds
            no project or several.
    """
    if not (repo / _AI_DIR / _DB_FILE).is_file():
        raise ConfigError(_NO_DATABASE, detail={"repo": str(repo)})
    time = clock or SystemClock()
    db = open_database(repo)
    MigrationRunner(db, "project").apply_pending()
    key = _single_project(db).key
    ids = IdSequenceStore(db)
    ledger = DefaultLedgerManager(db, LedgerRepository(db), ids, time)
    runner = AsyncioSubprocessRunner()
    git = GitCliProvider(repo, runner, ledger, IdempotencyStore(db, time), time, project_key=key)
    ai_root = repo / _AI_DIR
    policies = PolicyLoader(_AGENT_DEFAULTS / "policies.yaml", ai_root / "agents" / "policies.yaml")
    return _skills(ai_root, policies, db, git, ledger=ledger, clock=time, key=key), db


def skill_drift_reports(repo: Path) -> dict[str, DriftReport]:
    """Drift of each kernel provider's projection under `PROJECTIONS_DIR` (no database).

    Raises:
        ConfigError: A skill file or the projection lock is invalid.
    """
    ai_root = repo / _AI_DIR
    registry = DefaultSkillRegistry(
        _BUILTIN_SKILLS, ai_root / "agents" / "skills", {}, ai_root=ai_root
    )
    reports: dict[str, DriftReport] = {}
    for projector in skill_projectors():
        worktree = repo / PROJECTIONS_DIR / projector.provider
        reports[projector.provider] = asyncio.run(registry.check_drift([projector], str(worktree)))
    return reports


def _startup_checks(*checks: Callable[[], Awaitable[None]]) -> Callable[[], Awaitable[None]]:
    """ARCHITECTURE §3.4 step 3 checks, awaited in order; the first failure aborts startup."""

    async def run_all() -> None:
        for check in checks:
            await check()

    return run_all


def _version_pin_check(ai_root: Path, clock: Clock) -> Callable[[], Awaitable[None]]:
    """ARCHITECTURE §3.4 step 3: `kernel-versions.yaml` matches the installed kernel (§105).

    A repository without the pin file (not bootstrapped as a Production Kit) is not checked.
    """

    async def check() -> None:
        _validate_pins(ai_root, clock)

    return check


def _validate_pins(ai_root: Path, clock: Clock) -> None:
    if not (ai_root / PINS_PATH).is_file():
        _LOG.warning(
            "no kernel version pins; run 'walk bootstrap'", extra={"ai_root": str(ai_root)}
        )
        return
    catalog = BehaviorVersionCatalog(_PACKAGE_ROOT, clock).scan()
    KernelVersionPins.load(ai_root).validate(catalog)


def _approved_check(memory: DefaultMemoryManager) -> Callable[[], Awaitable[None]]:
    """ARCHITECTURE §3.4 step 3: approved artifact hashes (Invariant 10; E02-S12).

    Drift never aborts startup: the drifted documents are marked INVALID (``ON_CONTEXT_STALE``)
    and logged; `walk doctor` and `walk artifacts verify` report them.
    """

    async def check() -> None:
        drifted = await memory.verify_approved_artifacts()
        if drifted:
            _LOG.warning("approved artifact drift", extra={"artifact_ids": drifted})

    return check


def _model_known(ai_root: Path, router: DefaultModelRouter) -> Callable[[str], bool]:
    """Whether a model id, or every model of a family, is configured and enabled (§93)."""
    families = load_models_config(_DEFAULT_MODELS, ai_root / "agents" / "models.yaml").families

    def known(name: str) -> bool:
        enabled = {model for model, d in router.registry().models.items() if d.enabled}
        if name in families:
            return all(level.model in enabled for level in families[name].values())
        return name in enabled

    return known


def _may_approve(ai_root: Path) -> Callable[[AgentRole], frozenset[str]]:
    """The kinds a role's constitution may approve (``authority.may_approve``; §33)."""
    constitutions = ConstitutionLoader(_AGENT_DEFAULTS, ai_root / "agents" / "roles")

    def allowed(role: AgentRole) -> frozenset[str]:
        if role not in constitutions.available_roles():
            return frozenset()
        return frozenset(constitutions.load(role).authority.may_approve)

    return allowed


def _drift_check(
    skills: DefaultSkillRegistry, router: DefaultModelRouter, repo: Path, *, strict: bool
) -> Callable[[], Awaitable[None]]:
    """ARCHITECTURE §3.4 step 3: skill projection drift of every configured provider.

    Each provider's repo-level projection (`PROJECTIONS_DIR`) is checked; drift fails
    startup when ``strict``, otherwise it is regenerated (one ``CONTEXT_UPDATED`` each).
    """

    async def check() -> None:
        for projector in _configured_projectors(router):
            worktree = repo / PROJECTIONS_DIR / projector.provider
            worktree.mkdir(parents=True, exist_ok=True)
            report = await skills.check_drift([projector], str(worktree))
            if report.ok:
                continue
            if strict:
                msg = f"skill projections drift for {projector.provider} (strict startup)"
                raise ConfigError(
                    msg, detail={"provider": projector.provider, **report.model_dump()}
                )
            await skills.regenerate([projector], str(worktree), report)

    return check


def _configured_projectors(router: DefaultModelRouter) -> list[SkillProjector]:
    """One projector per provider that serves an enabled model."""
    projectors: dict[str, SkillProjector] = {}
    for descriptor in router.registry().models.values():
        if descriptor.enabled and descriptor.provider not in projectors:
            adapter = router.adapter_for(descriptor.id)
            projectors[descriptor.provider] = adapter.skill_projector()
    return list(projectors.values())


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


def _permission_rules(ai_root: Path) -> PermissionsFile:
    """Kernel defaults narrowed by `.ai/agents/permissions.yaml` (ADR-0006 D-6; E02-S10).

    Raises:
        ConfigError: A malformed default or project file, or a widening project rule.
    """
    return merge_narrowing(load_defaults(), load_project_rules(ai_root / _PERMISSIONS))


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
    git = GitCliProvider(
        repo,
        AsyncioSubprocessRunner(),
        ledger,
        IdempotencyStore(db, time),
        time,
        project_key=project_key,
    )
    return DefaultMemoryManager(
        repo / _AI_DIR,
        MemoryIndexRepository(db),
        ledger,
        hooks,
        ids,
        time,
        project_key=project_key,
        git=git,
        may_approve=_may_approve(repo / _AI_DIR),
    )
