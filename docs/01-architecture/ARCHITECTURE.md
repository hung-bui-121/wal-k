# WAL-K Kernel Architecture

**Status:** Draft v1 (architecture stage) — companion to `requirements/WAL_K_REQ.md` (cited as `§NN`) and ADR-0001 (tech stack, decided).
**Audience:** any implementing model or engineer. Everything named here (packages, classes, enums, tables, file paths, CLI commands) is referenced by `DOMAIN-MODEL.md`, `INTERFACES.md`, the ADRs and the work-breakdown stories. Names are stable; do not rename without an ADR.
**Scope markers:** `[MVP]` = Stages 1–4 of §135 as refined by §127–§134; `[Stage N]` = later roadmap stage. Unmarked = structural and present from Stage 1.

---

## 0. Reading map

| Question | Where |
|---|---|
| What packages exist, what may import what | §1, §2 of this doc |
| How the process runs, how agents execute, how Jira feeds the loop | §3 |
| Hooks, permission enforcement, ledger write points | §4 |
| Crash recovery, checkpoints, idempotency | §5 |
| Security model | §6 |
| Which mechanism enforces each §137 invariant | §7 |
| Game repo `.ai/` layout and front matter | §8 |
| Kernel-side `.improvement/` | §9 |
| Entities, enums, SQLite schema | `DOMAIN-MODEL.md` |
| Service protocols, state tables, algorithms, CLI | `INTERFACES.md` |
| Decisions the spec left open | `adr/` |

---

## 1. Layered architecture → Python packages

### 1.1 Overview

WAL-K is a single long-running Python 3.12 `asyncio` process per game project (ADR-0001, ADR-0009). It is a **production orchestration kernel** (§2): it owns workflow state, routes work to role-specialised agents, drives interchangeable model providers behind adapters, persists project knowledge into the game repository, and records every significant event in an execution ledger (§8). Game-specific logic stays out of the kernel (§8).

The §7 supporting layers map to packages under `src/walk/` as follows. The package list is exactly §122 plus one leaf package `common` (ADR-0009 §D-1: `common` holds only IDs, clock, errors, the `Actor` value object and four cross-cutting enums — `AgentRole`, `Effort`, `LearningScope`, `ImprovementScope` — because they are referenced by nearly every package and would otherwise create import cycles).

```text
 §7 layer                              src/walk/ package(s)              Layer #
 ─────────────────────────────────────  ───────────────────────────────  ───────
 Production Orchestrator                orchestrator                     L4
 Continuous Improvement                 improvement                      L3b
 Agent Runtime                          runtime                          L3
 Workflow / State Engine                workflow                         L2
 Model Router / Effort / Budget         model_router, effort, budgets    L2
 Context / Memory / Knowledge           context, memory                  L2
 Debate / Decision / Authority          debate, decisions, permissions   L2
 Skill / Tool / Hook Runtime            skills, tools, hooks             L2
 Jira / Git / Unity / Provider APIs     integrations, model_router/adapters L2 (edge)
 Execution Ledger / Telemetry           telemetry                        L1
 (durable storage)                      persistence                      L1
 (shared primitives)                    common                           L0
 (entry point)                          cli                              L5
 (role definitions)                     agents                           L2
```

```text
                 ┌──────────────────────────────────────────────┐
  L5             │                    cli                       │  typer commands, composition root
                 └───────────────────────┬──────────────────────┘
                 ┌───────────────────────▼──────────────────────┐
  L4             │                 orchestrator                 │  Orchestrator, TaskRouter, Scheduler,
                 │                                              │  PhaseGate, EvidencePackager
                 └──────┬─────────────────────────────┬─────────┘
                 ┌──────▼──────┐               ┌──────▼─────────┐
  L3 / L3b       │   runtime   │               │  improvement   │  AgentExecutor, ToolInvoker,
                 │             │               │                │  CheckpointManager / ImprovementManager
                 └──────┬──────┘               └──────┬─────────┘
   ┌────────────────────┼───────────────────────────────┼─────────────────────────────┐
   │  L2 domain packages (may import L1/L0 and the L2 packages listed in §2.2 only)  │
   │  workflow  agents  model_router  effort  budgets  context  memory  decisions     │
   │  debate  skills  tools  hooks  integrations  permissions                         │
   └─────────────────────────────────┬────────────────────────────────────────────────┘
                 ┌───────────────────▼──────────────────┐
  L1             │        telemetry      persistence     │  LedgerManager, EvidenceManager,
                 └───────────────────┬──────────────────┘  TelemetryManager / SQLite, migrations
                 ┌───────────────────▼──────────────────┐
  L0             │                 common                │  ids, clock, errors, AgentRole
                 └──────────────────────────────────────┘
```

**Architectural style:** layered kernel with explicit state machine; hexagonal at the edges (all provider SDKs behind `Protocol`s in `model_router/adapters/*` and `integrations/*`); event-sourced audit trail (ledger is append-only; reports are derived from it, §83); DI by constructor injection assembled in one composition root (`walk.cli.composition.build_kernel()`).

### 1.2 Package catalogue

Each row: responsibility, §125 kernel service(s) hosted, key public classes (defined in `INTERFACES.md`/`DOMAIN-MODEL.md`), MVP marker.

| Package | Responsibility | §125 services | Key public classes | Notes |
|---|---|---|---|---|
| `walk.common` | Typed IDs and ID allocation contract, UTC clock, kernel exception hierarchy, `Actor`, cross-cutting enums `AgentRole` (§10), `Effort` (§17), `LearningScope` (§110), `ImprovementScope` (§100). No I/O. | — | `AgentRole`, `Effort`, `LearningScope`, `ImprovementScope`, `Actor`, `WorkItemId`, `RunId`, `IdFactory` (Protocol), `Clock`, `WalkError`, `TransientError`, `PermanentError` | L0 |
| `walk.persistence` | SQLite engine: connection, WAL mode, numbered migrations applied at startup, generic `Repository[T]` base, `UnitOfWork`, `IdSequenceStore` (implements `IdFactory`), `IdempotencyStore`. Knows no domain semantics beyond table names. | — | `Database`, `MigrationRunner`, `UnitOfWork`, `Repository`, `IdSequenceStore`, `IdempotencyStore` | ADR-0002 |
| `walk.telemetry` | Append-only execution ledger (§81, §86), evidence records (§6.6, §47), structured JSON logging, metrics (§116). Reports (§83) are **queries** over the ledger. | `LedgerManager`, `EvidenceManager`, `TelemetryManager` | `LedgerEvent`, `LedgerEventKind`, `Evidence`, `EvidenceDraft`, `EvidenceKind`, `RetrospectiveMetrics`, `Report` | L1 |
| `walk.workflow` | Work-item hierarchy (§52), `WorkItemState` enum (§53/§61), transition tables with guards (§53), phase lifecycle (§66–§72), RC lifecycle (§76), Definition of Ready checks (§58), GDD traceability links (§73–§74), work-item drafts (§126). Pure domain + repositories; no provider calls. | `WorkflowManager` | `WorkItem` family, `WorkItemDraft`, `BugDraft`, `Phase`, `ReleaseCandidate`, `StateMachine`, `TransitionTable`, `Transition`, `Guard`, `WorkflowManager` | |
| `walk.agents` | Role definitions: `Constitution` (§12) loading from Markdown+YAML, `RuntimePolicy` (§13) composition, `AgentInstance` assembly (§9), `AgentInput`/`AgentOutput` contract (§126), `Handover` (§22) + its document conversion. Does not run agents. | `AgentManager` | `Constitution`, `RuntimePolicy`, `AgentInstance`, `AgentInput`, `AgentOutput`, `Handover`, `Finding`, `AgentManager`, `ConstitutionLoader` | |
| `walk.effort` | Effective-effort resolution (§18) over the `Effort` enum (§17, in `common`), dynamic up/downgrade requests (§19). | `EffortManager` | `EffortPolicy`, `EffortRequest`, `EffortResolution`, `EffortManager` | |
| `walk.budgets` | Budget definitions at Global/Project/Phase/Role/Task scopes (§20), consumption tracking, soft/hard thresholds, cost records and cost metrics (§84–§85). | `BudgetManager`, `CostManager` | `Budget`, `BudgetScope`, `BudgetDimension`, `BudgetSubject`, `CostRecord`, `BudgetManager`, `CostManager` | |
| `walk.permissions` | Permission rules (`allow` / `deny` / `conditional`, §31), protected actions (§92), approval requests, decision evaluation. Enforcement *point* is in `runtime` and adapters; *policy* lives here. | `PermissionManager` | `PermissionRule`, `PermissionEffect`, `PermissionDecision`, `ProtectedAction`, `ApprovalRequest`, `PermissionManager` | ADR-0006 |
| `walk.skills` | Canonical skill registry (§28–§29): `SKILL.md` + front matter, required-skill matching, projection orchestration and drift detection (hash lock file). Provider-specific projection *formats* are implemented by adapters via `SkillProjector`. | `SkillRegistry` | `Skill`, `SkillProjection`, `SkillProjector` (Protocol), `SkillRegistry`, `DriftReport` | ADR-0007 |
| `walk.tools` | Tool registry (§30): `ToolSpec` catalogue (kind, command patterns, provider, cost dimension), tool availability resolution per environment. Does not execute tools. | `ToolRegistry` | `ToolSpec`, `ToolKind`, `ToolRegistry` | |
| `walk.hooks` | Deterministic lifecycle hooks (§32): `HookName` enum, registry (kernel built-ins + project `hooks.yaml`), ordered synchronous dispatch, failure policy, hook execution records. Registry and dispatcher only — built-in hook *callables* live in `walk.orchestrator.builtin_hooks` (ADR-0016). | `HookManager` | `HookName`, `Hook`, `HookContext`, `HookResult`, `HookCallable`, `HookManager` | ADR-0016 |
| `walk.memory` | `.ai/` project memory (§34–§39): reading/writing Markdown+YAML documents, front-matter schemas per document type, section-level `ContextUpdate`s (§41), freshness stamping and classification (§42), handover documents as files (§22), approved artifacts (§33), memory index table. | `MemoryManager` | `MemoryDocument`, `FrontMatter`, `Freshness`, `FreshnessStatus`, `ContextUpdate`, `ProjectContext`, `FeatureContext`, `BugContext`, `ApprovedArtifact`, `MemoryManager` | ADR-0003 |
| `walk.decisions` | Decision records (§44), decision categories, **authority** (§12 Authority, escalation rules), autonomy levels (§51), proposals vs accepted decisions (Invariant 5), escalation routing (§50), evidence ranking usage (§47). | `DecisionManager` | `Decision`, `DecisionProposal`, `Authority`, `EscalationRule`, `EscalationRequest`, `Escalation`, `DecisionCategory`, `DecisionStatus`, `AutonomyLevel`, `DecisionManager` | `[Stage 5]` full; `[MVP]` persistence + manual decisions (§133) |
| `walk.debate` | Structured debate lifecycle (§45–§46): rounds, positions, consensus check, escalation to PO then user, round/budget limits (§138). | `DebateManager` | `Debate`, `DebateState`, `DebatePosition`, `DebateManager` | `[Stage 5]`; `[MVP]` minimal path for §133 |
| `walk.integrations` | Provider boundary protocols and implementations: `WorkProvider` (Local, Jira §55), `GitProvider` (git CLI, worktrees §59–§60), `UnityProvider` (batchmode CLI §62), `CodeGraphProvider` (Graphify §43), `AssetProvider` (§78) `[Stage 8]`, `CiProvider` (§62). Idempotency keys for all external writes (§90). | `IntegrationManager` | protocols above, `LocalWorkProvider`, `JiraWorkProvider`, `GitCliProvider`, `UnityBatchProvider`, `GraphifyProvider`, `IntegrationManager`, `WebhookReceiver`, `WorkPoller` | ADR-0005 |
| `walk.model_router` | `ModelAdapter` protocol (§6.1, §22), `ModelDescriptor` + `CapabilityRegistry` (§16), routing (preferred → capability check → fallback, §14, §21), handover construction trigger (§22), cross-model review preference (§23). `adapters/claude`, `adapters/codex` are the only places that import provider SDKs / spawn provider CLIs. | `ModelRouter` | `ModelAdapter`, `ModelDescriptor`, `Capability`, `CapabilityRegistry`, `FallbackTrigger`, `RoutingDecision`, `ModelRouter`, `ClaudeAdapter`, `CodexAdapter`, `AgentEvent` | ADR-0004 |
| `walk.context` | Context-first retrieval (§6.8, §40): builds the `ContextBundle` for an `AgentInput` from memory, decisions, approved artifacts, workflow state, code graph and selected source, within a token budget, with freshness-aware ranking (§42, ADR-0012). | `ContextManager` | `ContextBundle`, `ContextBundleRef`, `ContextItem`, `ContextRequest`, `ContextRanker`, `ContextManager` | |
| `walk.runtime` | Agent execution engine: `AgentExecutor` runs one `AgentRun` as an asyncio task around a `ModelAdapter`, consumes the event stream, enforces permissions at the tool boundary (`ToolInvoker`, `can_use_tool` callback), meters budget, creates checkpoints, performs fallback + handover, validates `AgentOutput`, applies output effects via `OutputApplier`. Also hosts the WIP commit strategy and worktree sandbox. | `CheckpointManager` | `AgentExecutor`, `AgentRun`, `AgentRunState`, `ToolInvoker`, `Checkpoint`, `CheckpointManager`, `OutputApplier`, `SandboxManager`, `BoundaryAuditor` | ADR-0002, ADR-0006 |
| `walk.improvement` | Continuous improvement (§94–§121): observations, retrospectives (derived from ledger), candidates, patterns/anti-patterns, behavior versions and rollout stages, kernel changelog; project vs kernel storage separation (§110, §119). | `ImprovementManager` | `ImprovementObservation`, `ImprovementCandidate`, `Pattern`, `AntiPattern`, `Retrospective`, `BehaviorVersion`, `RolloutStage`, `ImprovementManager` | `[Stage 10]` full; `[MVP]` observations + phase retrospective skeleton (§136) |
| `walk.orchestrator` | Production orchestration: event loop/scheduler (§56, §60), `TaskRouter` (role assignment, §10.1), phase execution and Phase Gate (§67–§72), phase evidence packaging (§69), REWORK/CHANGE intake (§71–§72), GDD compiler entry points (§48–§49) `[Stage 6]`, human override commands (§93), built-in hook callables for the §4.1 MUST/default attachments (`builtin_hooks`, ADR-0016). | `Orchestrator`, `TaskRouter` | `Orchestrator`, `TaskRouter`, `RouteDecision`, `KernelStatus`, `Scheduler`, `PhaseGate`, `EvidencePackager`, `PhaseEvidencePackage`, `ChangeImpactAnalyzer` `[Stage 6+]`, `GddCompiler` `[Stage 6]`, `BuiltinHookDeps` | ADR-0016 |
| `walk.cli` | `walk` typer application; composition root; JSON output mode for dashboards (§87). | — | `app`, `build_kernel()`, `KernelHandle` | |

### 1.3 Standard module layout inside every package

```text
src/walk/<package>/
├── __init__.py        # re-exports the public names listed above; nothing else
├── models.py          # pydantic v2 models + enums owned by this package (ADR-0001)
├── protocols.py       # typing.Protocol / ABC for the package's service(s)   (when the package hosts a §125 service)
├── service.py         # default implementation(s) of protocols.py
├── repository.py      # SQLite repository for this package's aggregates      (when persisted)
├── errors.py          # package-specific exceptions deriving from walk.common.errors
└── <feature>.py       # further modules as needed; no sub-packages except model_router/adapters, integrations/<provider>, persistence/migrations
```

Implementations are injected, never imported across packages: package A imports `walk.b.protocols` and `walk.b.models`, never `walk.b.service`. The composition root is the only module that imports `service.py` files from multiple packages.

---

## 2. Dependency rules

### 2.1 Layer rule

A package may import only from packages in a **lower** layer, plus the same-layer exceptions explicitly listed in §2.2. `cli` imports `orchestrator` and the composition root; nothing imports `cli`. Enforced by `import-linter` contracts in CI (ADR-0009 §D-10) and by `ruff` banned-import rules for SDKs.

### 2.2 Import-dependency table

Legend: `✔` = may import (`models`, `protocols`, `errors` only, unless the cell names more modules) · `·` = forbidden. Rows import columns. `common` and `persistence` are infrastructure: every module of theirs may be imported. `orchestrator` (the engine host) and `cli` (the composition root) may import any module of the packages they may import; only `cli/composition.py` wires `service.py` implementations of several packages (§1.3). The package-level cells are enforced on direct imports by import-linter contracts in `pyproject.toml` (`uv run lint-imports`, part of the quality gate; E01-S31); nothing imports `cli` (§2.1).

Rows and columns are listed in **topological order**; a package may import only packages that appear *before* it. Within L2 the order is: `hooks, workflow, budgets, effort, permissions, tools, skills, integrations, memory, decisions, debate, context, agents, model_router` (`hooks` first: ADR-0018; `budgets` before `effort`: ADR-0019).

| importer ↓ / imported → | common | persistence | telemetry | hooks | workflow | budgets | effort | permissions | tools | skills | integrations | memory | decisions | debate | context | agents | model_router | runtime | improvement | orchestrator |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **common** | – | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| **persistence** | ✔ | – | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| **telemetry** | ✔ | ✔ | – | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| **hooks** | ✔ | ✔ | ✔ | – | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| **workflow** | ✔ | ✔ | ✔ | ✔ | – | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| **budgets** | ✔ | ✔ | ✔ | ✔ | ✔ (+ `repository`) | – | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| **effort** | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | – | · | · | · | · | · | · | · | · | · | · | · | · | · |
| **permissions** | ✔ | ✔ | ✔ | ✔ | ✔ | · | · | – | ✔ | · | · | · | · | · | · | · | · | · | · | · |
| **tools** | ✔ | ✔ | ✔ | ✔ | · | ✔ | · | · | – | · | · | · | · | · | · | · | · | · | · | · |
| **skills** | ✔ | ✔ | ✔ | ✔ | · | · | · | · | ✔ | – | · | · | · | · | · | · | · | · | · | · |
| **integrations** | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | · | · | ✔ | · | – | · | · | · | · | · | · | · | · | · |
| **memory** | ✔ | ✔ | ✔ | ✔ | ✔ | · | · | · | · | · | ✔ (GitProvider protocol only) | – | · | · | · | · | · | · | · | · |
| **decisions** | ✔ | ✔ | ✔ | ✔ | ✔ | · | · | · | · | · | · | ✔ | – | · | · | · | · | · | · | · |
| **debate** | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | · | · | · | · | · | · | ✔ | – | · | · | · | · | · | · |
| **context** | ✔ | ✔ | ✔ | ✔ | ✔ (+ `repository`) | · | ✔ | · | · | · | ✔ (CodeGraphProvider protocol only) | ✔ (+ `frontmatter`) | ✔ | · | – | · | · | · | · | · |
| **agents** | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | · | ✔ (+ `frontmatter`, `paths`) | ✔ | ✔ | ✔ | – | · | · | · | · |
| **model_router** | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | · | · | · | · | ✔ | ✔ | – | · | · | · |
| **runtime** | ✔ | ✔ | ✔ | ✔ | ✔ (+ `repository`: work items are read through it, never by raw SQL) | ✔ | ✔ | ✔ (+ `repository`) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ (+ `handover`) | ✔ (+ `costing`, `output`) | – | · | · |
| **improvement** | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | · | · | ✔ | · | ✔ | ✔ | ✔ | · | ✔ | ✔ | · | – | · |
| **orchestrator** | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | – |
| **cli** | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |

Cycle check: every ✔ lies strictly left of the row's own diagonal, so the relation is a strict partial order — no cycles. Model placements that this forces (see `DOMAIN-MODEL.md`): `Authority`/`EscalationRule`/`DecisionProposal`/`EscalationRequest` live in `decisions`; `WorkItemDraft`/`BugDraft` in `workflow`; `EvidenceDraft`/`RetrospectiveMetrics` in `telemetry`; `ContextUpdate` in `memory`; `Handover` in `agents` (memory only sees it as a `MemoryDocument`); `PhaseEvidencePackage` in `orchestrator`; token→USD conversion in `model_router.costing`.

### 2.3 Third-party / SDK confinement (Invariant 1, 11; ADR-0001)

| Dependency | Allowed only in |
|---|---|
| `claude_agent_sdk` | `walk/model_router/adapters/claude/` |
| `codex` CLI subprocess (`codex exec`) | `walk/model_router/adapters/codex/` |
| `httpx` (Jira REST; asset-provider HTTP APIs and asset downloads `[Stage 8]`; MCP OAuth transport `[Stage 8]`) | `walk/integrations/jira/`, `walk/integrations/assets/` (shared download helper and `<provider>/` subpackages), `walk/integrations/mcp/` (ADR-0017) |
| `git` subprocess | `walk/integrations/git/` |
| Unity executable subprocess | `walk/integrations/unity/` |
| Graphify CLI / library | `walk/integrations/graphify/` |
| Meshy / OpenArt / Blender | `walk/integrations/assets/<provider>/` `[Stage 8]` |
| `mcp` (official MCP Python SDK: streamable HTTP client, OAuth client provider) | `walk/integrations/mcp/` (generic client, OAuth token storage, server registry) and `walk/integrations/assets/openart/` (adapter) `[Stage 8]` (ADR-0017) |
| `sqlite3` | `walk/persistence/` (repositories in other packages receive a `Database` handle; they write SQL, they do not open connections) |
| `typer` | `walk/cli/` |
| `keyring` | `walk/integrations/credentials.py` (the `CredentialStore`) |
| `yaml` (PyYAML) | `walk/memory/`, `walk/agents/`, `walk/skills/`, `walk/hooks/`, `walk/permissions/`, `walk/workflow/` (transition tables, ADR-0010 D-4), `walk/orchestrator/router.py` (routing rows of `scheduled_states.yaml`, E01-S29), `walk/cli/` (configuration loaders only); `walk/integrations/manifest.py` and `walk/integrations/service.py` (`environment.yaml`, `work-provider.yaml` kind; E02-S02); `walk/integrations/assets/` (provenance files and asset rules `[Stage 8]`) |

A ruff `banned-api` / `import-linter` configuration encodes this table.

---

## 3. Runtime topology

### 3.1 Process model

One kernel process per game project (ADR-0009 §D-3: **local daemon, not a server**). The process is started by `walk run` in the game repository root (or with `--repo PATH`). It owns:

- the SQLite database `<repo>/.ai/kernel.db` (WAL mode; gitignored),
- the `.ai/` memory tree (git-tracked),
- an `asyncio` event loop hosting the `Scheduler`, agent run tasks, the optional webhook HTTP listener, the polling fallback and the hook dispatcher,
- an exclusive OS-level lock file `<repo>/.ai/kernel.lock` (fail-fast if a second kernel targets the same repo).

```text
   walk CLI (typer, separate short-lived process)      ────── IPC: SQLite tables `commands` + `command_results` (ADR-0009 §D-3)
        │  writes a Command row, polls result
        ▼
 ┌─────────────────────────────────── kernel process (asyncio) ────────────────────────────────────┐
 │                                                                                                  │
 │  Scheduler.tick()  ◄── wake-ups: timer (5 s) │ webhook event │ poll result │ agent run finished │ command │
 │       │                                                                                          │
 │       ├─ WorkflowManager.ready_items()  → TaskRouter.route(item) → AgentManager.instantiate(role)│
 │       │                                                                                          │
 │       └─ AgentExecutor.start(agent, item) ──► asyncio.Task  ──► ModelAdapter.run(...) ──► stream │
 │                                                    │                                             │
 │                                                    ├─ ToolInvoker / can_use_tool  (permissions)  │
 │                                                    ├─ BudgetManager.meter(...)                   │
 │                                                    ├─ CheckpointManager.checkpoint(...)          │
 │                                                    ├─ HookManager.fire(...)                      │
 │                                                    └─ LedgerManager.append(...)                  │
 │                                                                                                  │
 │  WebhookReceiver (HTTP, optional)  ──► IntegrationManager.ingest(event) ──► WorkflowManager      │
 │  WorkPoller (every 60 s, fallback) ──► IntegrationManager.reconcile()  ──► WorkflowManager      │
 └──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

CLI ⇄ kernel IPC: the CLI never calls provider APIs. Query commands (`status`, `ledger`, `report`) read SQLite directly (read-only connection). Mutating commands (`phase gate`, `pause`, `approve`, `work transition`) insert a `Command` row; the kernel's `CommandConsumer` executes it and writes `command_results`; the CLI prints the result. If no kernel is running, mutating commands that are safe offline (`bootstrap`, `doctor`, `phase gate`, `approve`, `work transition`) run in-process against the DB (the CLI acquires the lock); commands needing agents (`run`, `feature add --execute`) require the daemon.

### 3.2 Agent execution

An **agent run** (`AgentRun`) is one asyncio task wrapping one `ModelAdapter` session for one `(work item, role, workflow state)` triple.

1. `TaskRouter` picks the role from the work item kind + state (`INTERFACES.md` §5 routing table) and `AgentManager.instantiate(role, work_item)` assembles an `AgentInstance` (§9): constitution + runtime policy + permissions + skills + tools.
2. `ModelRouter.select(role, task_profile)` returns a `RoutingDecision` (model, adapter, effort) after capability check (§16) and budget check (§20).
3. `ContextManager.build(ContextRequest)` produces the `ContextBundle` (§40).
4. `AgentExecutor` composes `AgentInput` (§126), creates a sandbox worktree (`SandboxManager`), fires `ON_AGENT_START`, writes `AGENT_RUN_STARTED` + `MODEL_SELECTED` + `EFFORT_SET` ledger events, and calls `adapter.run(input, session)`.
5. The adapter yields `AgentEvent`s. The executor:
   - routes `TOOL_CALL_REQUESTED` events through `PermissionManager` (ADR-0006) — for Claude via the SDK `can_use_tool` callback, for kernel tools via `ToolInvoker`;
   - meters `USAGE` events into `BudgetManager`/`CostManager`;
   - creates a checkpoint every `checkpoint_every_tool_calls` (default 10) tool calls and on `CHECKPOINT_HINT`;
   - on `ERROR` classified as a `FallbackTrigger` (§21) runs the fallback algorithm (`INTERFACES.md` §5.3);
   - on `FINAL_OUTPUT` validates `AgentOutput` (pydantic), with one repair turn on validation failure.
6. `OutputApplier` applies the structured output: context updates → `MemoryManager`; evidence → `EvidenceManager`; decisions → `DecisionManager`; new tasks/bugs → `WorkflowManager` + `WorkProvider`; escalations → `Orchestrator`; code changes → `GitProvider.commit` (the **kernel** commits, not the agent — ADR-0006 §D-2). Then the workflow event implied by `AgentOutput.status` is raised on the `StateMachine`.
7. `ON_AGENT_END` fires; `AGENT_RUN_ENDED` is written; the scheduler is woken.

Concurrency: `Scheduler` admits up to `max_parallel_agents` (default 2 `[MVP]`; raised in `[Stage 7]`) runs; at most one run per work item; one worktree per run (§60). Roles that review (`LEAD_DEV`, `QC`) never run on the same work item concurrently with the implementer (Invariant 4).

### 3.3 Work-provider event flow (§55–§56)

```text
 Jira Cloud ──webhook──► WebhookReceiver (POST /webhooks/jira, HMAC/secret check)
                               │ parse → WorkProviderEvent(kind, external_ref, fields, at)
                               ▼
                    IntegrationManager.ingest(event)
                               │ map external_ref → WorkItemId (work_items.external_ref index)
                               │ map Jira status → WorkItemState via status map (ADR-0005)
                               ▼
                    WorkflowManager.apply_external_transition(item, state, source=EXTERNAL)
                               │ guards may reject (→ kernel re-syncs Jira to kernel state)
                               ▼
                    Scheduler.wake()

 WorkPoller (fallback, every poll_interval_s=60): JQL `project = KEY AND updated >= -2m`
   → same ingest path; also used on startup recovery to reconcile everything changed since `last_sync_at`.
```

Rule (§6.3): the kernel is the authority on *workflow* state; Jira is the authority on *backlog, priority, assignment, dependencies, blockers* (§55). A conflicting external transition that fails a guard is written back (kernel → Jira) and logged as `WORK_ITEM_TRANSITION` with `source=EXTERNAL_REJECTED`. `LocalWorkProvider` `[MVP]` has no webhooks; its "events" come from the CLI.

### 3.4 Startup sequence (`walk run`)

1. Acquire `.ai/kernel.lock`; open DB; `MigrationRunner.apply_pending()`.
2. `EnvironmentManifest` preflight (§26) — fail fast on missing required tools/providers unless `--skip-preflight`.
3. Load Production Kit (§24): constitutions, policies, permissions, hooks, skills; verify `kernel-versions.yaml` compatibility (§105); run skill drift check (ADR-0007).
4. Built-in hooks registered (table in §4.1): `walk.orchestrator.builtin_hooks.register_builtins(hook_manager, deps)` is called once by the composition root `build_kernel()` after all services exist, then project hooks from `.ai/agents/hooks.yaml` are loaded (ADR-0016). `build_kernel()` runs before `Orchestrator.start()`, so this precedes step 5.
5. **Recovery** (§5.2 of this doc): mark orphaned `RUNNING` agent runs `INTERRUPTED`; enqueue resumes.
6. Fire `ON_PROJECT_START`; start `Scheduler`, `WebhookReceiver` (if configured), `WorkPoller`, `CommandConsumer`.

---

## 4. Cross-cutting mechanisms

### 4.1 Lifecycle hooks (§32)

Hooks are **kernel-side, deterministic and synchronous** (ADR-0009 §D-7): `HookManager.fire(name, ctx)` awaits every registered hook in priority order before the triggering operation continues. A hook never runs inside a model prompt. Two hook kinds: `builtin` (Python callables in `walk.orchestrator.builtin_hooks`, registered once by the composition root — ADR-0016; `walk.hooks` itself never imports them) and `project` (declared in `.ai/agents/hooks.yaml`: a shell command or a kernel action name, with `fail_policy`). Every execution is recorded (`hook_executions` table + `HOOK_EXECUTED`/`HOOK_FAILED` ledger events).

`HookName` enum (`walk.hooks.models`) — every value, when it fires, and what is attached by default (`MUST` = built-in, non-removable; `default` = registered by default, project may disable):

| HookName | Fires when | Default attachments |
|---|---|---|
| `ON_PROJECT_START` | kernel started for project (after recovery) | default: `MemoryManager.rebuild_index()` (ledger `PROJECT_STARTED` is written by `Orchestrator.start` before the hook fires, §4.3) |
| `ON_PROJECT_PAUSE` / `ON_PROJECT_RESUME` | user `walk pause` / `walk resume` | MUST: checkpoint all running agents (pause); ledger `USER_OVERRIDE` |
| `ON_PHASE_START` | phase → `ACTIVE` | MUST: snapshot phase baseline (`ApprovedArtifact kind=PHASE_BASELINE`); default: budget allocation for phase |
| `ON_PHASE_REVIEW_START` | phase → `EVIDENCE_REVIEW` | MUST: `EvidencePackager.build()`; default: `ImprovementManager.phase_retrospective()` |
| `ON_PHASE_COMPLETE` | phase → `COMPLETE` | MUST: write phase report to `.ai/reports/phases/` (no learning promotion: phase learnings are captured by the `ON_PHASE_REVIEW_START` retrospective and reach kernel scope only through explicit `walk improvement promote`, ADR-0008 D-2) |
| `ON_PHASE_GATE_DECISION` | user GO/REWORK/CHANGE/STOP recorded | MUST: ledger `PHASE_GATE_DECISION`; default: `ImprovementManager.observe_user_feedback()` (§118) |
| `ON_TASK_START` | work item → `IMPLEMENTING` (or bug → fixing) | MUST: Definition-of-Ready guard already passed; create branch via `GitProvider.ensure_branch` (idempotent) |
| `ON_TASK_COMPLETE` | work item → `COMPLETE` | MUST: feature/bug context `remaining_work` cleared check; ledger `TASK_COMPLETED` |
| `ON_TASK_BLOCKED` | work item → `BLOCKED` | MUST: `WorkProvider.transition` + comment with blocker reason |
| `ON_TASK_FAILED` | agent run `FAILED` and retries exhausted | MUST: escalation to Orchestrator role; ledger `ERROR` |
| `ON_TASK_CANCELLED` | user `walk work cancel` | MUST: cancel run, remove worktree, ledger `USER_OVERRIDE` |
| `ON_STATE_TRANSITION` | every committed `StateMachine` transition | MUST: ledger `WORK_ITEM_TRANSITION`; `WorkProvider.transition` (idempotent) |
| `ON_AGENT_START` | before `adapter.run` | MUST: ledger `AGENT_RUN_STARTED`; `ContextManager` freshness check → may fire `ON_CONTEXT_STALE` |
| `ON_AGENT_CHECKPOINT` | `CheckpointManager.checkpoint()` | MUST: WIP commit on work branch (ADR-0002 §D-4); ledger `CHECKPOINT_CREATED` |
| `ON_AGENT_END` | after output applied | MUST: final checkpoint — **no-op when the payload carries `checkpoint_id`** (the executor already wrote the `END` checkpoint); ledger `AGENT_RUN_ENDED`; cost roll-up |
| `ON_AGENT_HANDOFF` | run about to be continued by another run (fallback, pause, re-assignment) | **MUST: `CheckpointManager.checkpoint()` + `MemoryManager.write_handover()`** (§32 example) — no-op when the payload carries both `checkpoint_id` and `handover_id` (the caller already checkpointed and wrote the handover) |
| `ON_MODEL_FALLBACK` | executor (or recovery) switched a run to a different model | MUST: `ON_AGENT_HANDOFF` chain, forwarding the payload (`checkpoint_id`, `handover_id` present → the handoff attachment is a no-op, so observers still see every handoff without a duplicate checkpoint); ledger `MODEL_FALLBACK` is written by `runtime.AgentExecutor` before the hook fires; default: improvement observation `REPEATED_FALLBACK` counter |
| `ON_EFFORT_CHANGE` | `EffortManager` approved an up/downgrade | MUST: ledger `EFFORT_CHANGED` |
| `ON_BUDGET_THRESHOLD` | consumption crosses `soft_threshold` | MUST: ledger `BUDGET_EVENT`; default: effort downgrade request |
| `ON_BUDGET_EXHAUSTED` | hard limit reached | MUST: checkpoint + run state `BLOCKED_BUDGET` + escalation |
| `ON_TOOL_BEFORE` | permission decision ALLOW for a tool call | MUST: ledger `TOOL_INVOKED` (pre) |
| `ON_TOOL_AFTER` | tool returned | MUST: ledger `TOOL_INVOKED` (post, duration, status); default: `ON_CODE_CHANGED` if write tool |
| `ON_TOOL_DENIED` | permission decision DENY | MUST: ledger `TOOL_DENIED`; counter for anti-pattern detection |
| `ON_PROTECTED_ACTION_REQUESTED` | decision `REQUIRE_APPROVAL` | MUST: `ApprovalRequest` persisted; ledger `APPROVAL_REQUESTED`; run paused |
| `ON_CODE_CHANGED` | files in worktree changed (post tool or at checkpoint diff) | default: `CodeGraphProvider.mark_dirty(paths)`; freshness invalidation of memory docs listing those files |
| `ON_COMMIT` | kernel committed on work branch | MUST: ledger `COMMIT` with work item ref; default: `WorkProvider.add_comment` summary |
| `ON_PR_OPENED` / `ON_MERGED` | PR created / merged | MUST: ledger `PR_OPENED` / `MERGED`; feature context `relevant_files` refresh |
| `ON_BUILD_START` / `ON_BUILD_SUCCESS` / `ON_BUILD_FAILURE` | `CiProvider`/`UnityProvider` job | MUST: ledger `BUILD_RESULT` + evidence record; failure → workflow event `ci_failed` |
| `ON_TEST_RESULT` | test run finished | MUST: evidence record `AUTOMATED_TEST` |
| `ON_CONTEXT_STALE` | freshness `POSSIBLY_STALE`/`INVALID` detected for an item in the bundle | MUST: mark bundle item `requires_verification=True`; ledger `CONTEXT_FRESHNESS`; default: observation counter |
| `ON_CONTEXT_UPDATED` | memory doc written | MUST: freshness stamp (commit + timestamp); memory index update; ledger `CONTEXT_UPDATED` |
| `ON_READY_FOR_QC` | work item → `QC` | MUST: QC run scheduled with a model different from implementer when `cross_model_review=true` (§23) |
| `ON_QC_RESULT` | QC output applied | MUST: ledger `QC_RESULT`; evidence record |
| `ON_BUG_CREATED` | bug work item persisted | MUST: `WorkProvider.create` (idempotent); ledger `BUG_CREATED`; bug context skeleton |
| `ON_DEBATE_OPENED` / `ON_DEBATE_ROUND_COMPLETE` / `ON_DEBATE_RESOLVED` | debate lifecycle | MUST: ledger events; resolved → `DecisionManager.record()` |
| `ON_DECISION_RECORDED` | decision persisted | MUST: write `.ai/decisions/DEC-NNNN.md`; link to affected feature contexts |
| `ON_ESCALATION` | escalation created (any autonomy level ≥ 2) | MUST: ledger `ESCALATION_RAISED`; Level 3 → `ApprovalRequest` for user |
| `ON_RECOVERY_RESUME` | interrupted run resumed at startup | MUST: ledger `RECOVERY_RESUMED`; handover loaded into input |
| `ON_IMPROVEMENT_OBSERVATION` | observation created | MUST: write to `.ai/improvements/OBS-NNNN.md`; ledger |

Failure policy: `MUST` hooks are `fail_closed` (the triggering operation aborts and the run is marked `FAILED_HOOK`); `default`/project hooks are `log_and_continue` unless `fail_policy: fail_closed` in `hooks.yaml`.

### 4.2 Permission enforcement point (§31; ADR-0006)

Policy lives in `walk.permissions`; **enforcement happens in the kernel at the tool-invocation boundary**, never only in prompts:

| Tool kind (`ToolKind`) | Where enforced | Mechanism |
|---|---|---|
| `KERNEL` (jira.*, git.* protected ops, unity.*, graph.*, asset.*) | `runtime.ToolInvoker.invoke()` | `PermissionManager.decide(ToolCallRequest)` → ALLOW / DENY / REQUIRE_APPROVAL before dispatch to `IntegrationManager` |
| `PROVIDER_NATIVE` for Claude (Read/Edit/Write/Bash/Glob/Grep) | `ClaudeAdapter` `can_use_tool` callback → `ToolInvoker.authorize()` | same `decide()`; Bash commands matched against `command_patterns`; paths matched against repo boundary |
| `PROVIDER_NATIVE` for Codex (shell) | pre-run `CodexAdapter.configure_sandbox()` + post-run `runtime.BoundaryAuditor` | sandbox `workspace-write` scoped to the worktree, network off; after the run the diff is audited: writes outside allowed paths or to forbidden files → output rejected, run `FAILED_BOUNDARY` |
| `CLI` (graphify, dotnet, unity on PATH) | as `PROVIDER_NATIVE` shell | command patterns |
| Git protected branches | `GitProvider.install_guard_hooks()` installs `pre-commit`/`pre-push` guards in every worktree | defence in depth: blocks direct commits/pushes to protected branches regardless of provider |

Agents never hold credentials for Jira/Git remotes/stores (§91). All such operations are executed by the kernel from structured `AgentOutput` intents (`new_bugs`, `changes`, `decisions`), so a provider-native tool cannot perform them.

### 4.3 Ledger write points (§81, §86)

`LedgerManager.append(LedgerEvent)` is called from exactly these places (anything else writing to the ledger is a defect):

| Write point | Event kinds |
|---|---|
| `workflow.StateMachine.commit()` | `WORK_ITEM_CREATED`, `WORK_ITEM_TRANSITION`, `PHASE_TRANSITION`, `RC_TRANSITION` |
| `orchestrator.Orchestrator.start()` (`DefaultOrchestrator.start`, E01-S29) | `PROJECT_STARTED` |
| `runtime.AgentExecutor` (and `runtime.RecoveryManager` on its behalf, same package) | `AGENT_ASSIGNED`, `AGENT_RUN_STARTED`, `AGENT_RUN_ENDED`, `MODEL_SELECTED`, `EFFORT_SET`, `EFFORT_CHANGED`, `MODEL_FALLBACK`, `HANDOVER_CREATED`, `CHECKPOINT_CREATED`, `RETRY`, `ERROR`, `RECOVERY_RESUMED` |
| `runtime.ToolInvoker` / adapters' `can_use_tool` | `TOOL_INVOKED`, `TOOL_DENIED`, `APPROVAL_REQUESTED` |
| `permissions.PermissionManager.decide_approval()` | `APPROVAL_DECIDED` |
| `budgets.BudgetManager` / `CostManager` | `BUDGET_EVENT`, `COST_RECORDED` |
| `integrations.GitCliProvider` | `COMMIT`, `PR_OPENED`, `MERGED` |
| `integrations.UnityBatchProvider` / `CiProvider` | `BUILD_RESULT`, `TEST_RESULT` |
| `orchestrator.PhaseGate` | `PHASE_GATE_DECISION`, `USER_OVERRIDE` |
| `orchestrator.Orchestrator` (QC output applied) | `QC_RESULT`, `BUG_CREATED` |
| `debate.DebateManager` | `DEBATE_OPENED`, `DEBATE_POSITION`, `DEBATE_RESOLVED` |
| `decisions.DecisionManager` | `DECISION_RECORDED`, `ESCALATION_RAISED` |
| `memory.MemoryManager` | `CONTEXT_UPDATED`, `CONTEXT_FRESHNESS`, `ARTIFACT_APPROVED` |
| `skills.SkillRegistry` (`DefaultSkillRegistry.regenerate`, E02-S07) | `CONTEXT_UPDATED` (payload `skills_drift`) |
| `telemetry.EvidenceManager` | `EVIDENCE_RECORDED` |
| `hooks.HookManager` | `HOOK_EXECUTED`, `HOOK_FAILED` |
| `improvement.ImprovementManager` | `IMPROVEMENT_OBSERVATION`, `IMPROVEMENT_CANDIDATE`, `BEHAVIOR_VERSION_CHANGED` |

Every event carries `project_key`, `at`, optional `work_item_id`, `run_id`, `role`, `model_id`, `phase_id`, `cost_usd` so §82/§88 questions are answerable by SQL alone. Reports (§83) are implemented as `ReportQuery` objects over `ledger_events` + `cost_records`; agents never reconstruct history from memory.

---

## 5. Error handling & recovery (§89–§90)

### 5.1 Error taxonomy

`walk.common.errors`:

```text
WalkError
├── TransientError          # retry with backoff; may become FallbackTrigger
│   ├── ProviderUnavailable, RateLimited, Timeout, QuotaExhausted, ToolCrashed
├── PermanentError          # no retry; fail the run / operation
│   ├── PermissionDenied, GuardRejected, OutputInvalid, BoundaryViolation, ConfigError
└── RecoverableInterruption # process died / cancelled; resume from checkpoint
```

Retry policy: `TransientError` → exponential backoff (1 s, 2 s, 4 s … max 5 attempts, jitter) recorded as `RETRY`; after attempts exhausted the error is mapped to a `FallbackTrigger` (§21) if applicable, else the run fails (`ON_TASK_FAILED`).

### 5.2 Checkpoint granularity (ADR-0002)

A `Checkpoint` is created at: run start (`kind=START`), every `checkpoint_every_tool_calls` (10) tool calls (`PERIODIC`), adapter `CHECKPOINT_HINT` (`AGENT_REQUESTED`), before handoff/fallback (`HANDOFF`), on pause (`PAUSE`), at run end (`END`). Contents: run/work-item identity, role, model, effort, provider session reference (Claude `session_id`, Codex thread id) for native resume, worktree `head_sha` after the WIP commit, dirty-file list, budget consumed, tool-call counter, the latest structured `Handover` (§22 fields), and the `ContextBundle` manifest (ids + freshness stamps, not contents). Never chain-of-thought (§22).

### 5.3 Resume algorithm (startup and on demand)

```text
 1. rows = agent_runs WHERE state IN (RUNNING, PAUSED_FOR_APPROVAL) AND kernel_instance != current
 2. for each run: set state = INTERRUPTED; ledger ERROR(kind=INTERRUPTED)
 3. ckpt = latest checkpoint for run (ORDER BY seq DESC LIMIT 1); if none → treat as never started: requeue work item
 4. git: ensure worktree exists for run.work_item; checkout ckpt.head_sha on the work branch (WIP commits make it durable)
 5. adapter = ModelRouter.adapter_for(ckpt.model_id); if adapter.health().ok and ckpt.provider_session_ref is resumable:
        new_run = AgentExecutor.resume_native(ckpt)        # same model, provider-side session resume (NotResumable → else-branch)
    else:
        handover = CheckpointManager.latest_open_handover(item) or build_handover(run, "RECOVERY") checkpointed as HANDOFF on run
        decision = ModelRouter.select(role, policy, profile, ckpt.effort, exclude=[ckpt.model_id] if provider unhealthy else [])
        if decision.model_id != ckpt.model_id:
            ledger MODEL_FALLBACK{trigger: PROVIDER_OUTAGE, from: ckpt.model_id, to: decision.model_id}; fire ON_MODEL_FALLBACK
        new_run = AgentExecutor.start(agent, item, handover=handover, parent_run_id=run.id, routing=decision)   # §132 path
        run.state = HANDED_OVER; close_handover(handover.id, new_run.id)
 6. new_run.parent_run_id = run.id; ledger RECOVERY_RESUMED{from_run_id, mode: native|handover, checkpoint_seq, handover_id}; fire ON_RECOVERY_RESUME
 7. after all runs: IntegrationManager.reconcile(since=last_sync_at)  # Jira/Git drift during downtime
```

Partial external operations: every external write is wrapped `IdempotencyStore.run(key, op)`; on resume, operations whose key exists are skipped (result replayed). For Jira creates the provider also searches by label `walk:<WorkItemId>` to reconcile a create that succeeded before the key was recorded.

### 5.4 Idempotency keys (§90)

| Operation | Key format |
|---|---|
| Jira / Local create work item | `work.create:{work_item_id}` |
| Work item transition | `work.transition:{work_item_id}:{transition_seq}` (`transition_seq` = row id in `work_item_transitions`) |
| Work item comment | `work.comment:{work_item_id}:{ledger_seq}` |
| Branch creation | `git.branch:{work_item_id}` |
| WIP / final commit | `git.commit:{run_id}:{checkpoint_seq}` |
| PR open | `git.pr:{work_item_id}:{head_sha}` |
| Merge | `git.merge:{work_item_id}:{pr_ref}` |
| Build / test job | `ci.job:{work_item_id}:{head_sha}:{job_kind}` |
| Phase report | `report.phase:{phase_id}:{gate_round}` |
| Scheduling an agent run | `schedule:{work_item_id}:{state}:{state_version}` |
| Handover document | `handover:{run_id}:{checkpoint_seq}` |
| Asset generation `[Stage 8]` | `asset.generate:{work_item_id}:{request_hash}` |

Keys are stored in `idempotency_keys(key PRIMARY KEY, operation, result_ref, created_at)` and inserted **in the same SQLite transaction** as the local state change they belong to.

### 5.5 Circuit breakers (§138 "Infinite Fix Loop", "Infinite Debate")

- QC fix loop: `max_fix_loops` per story (default 3) → `ON_TASK_FAILED` with escalation `ROOT_CAUSE_REVIEW` to Lead Dev, then user.
- Debate: `max_rounds` (default 3) then PO, then user (§46).
- Fallback: `max_fallbacks_per_run` (default 2); then run `BLOCKED_PROVIDER` + escalation.
- Repair turns for invalid `AgentOutput`: 1.
- Agent run wall-clock: `BudgetDimension.EXECUTION_TIME` per role (default 45 min) — hard stop + checkpoint.

---

## 6. Security model (§91–§93)

| Principle (§91) | Mechanism |
|---|---|
| Tool allowlist | `ToolRegistry` is the closed set of tools; `AgentInput.allowed_tools` ⊆ role's allowed set ∩ environment-available set; adapters receive only that list (Claude `allowed_tools`; Codex: shell only, kernel tools unavailable) |
| Repository boundary | Every run executes in a dedicated git worktree under `<repo>/.walk/worktrees/<run_id>/` (gitignored). File tools are constrained to the worktree (Claude: `can_use_tool` path check; Codex: sandbox `workspace-write` cwd). `BoundaryAuditor` rejects diffs touching paths outside `allowed_paths` or matching `forbidden_paths` (`.ai/kernel.db`, `.walk/`, `ProjectSettings/*Secrets*`, `**/*.env`) |
| Protected branches | `GitProvider` refuses pushes/merges to `protected_branches` unless `ApprovalRequest` approved; guard hooks installed in worktrees |
| Secret isolation | Credentials are read by `CredentialStore` from environment variables, then OS keyring (`keyring` service `walk`), never from `.ai/` (ADR-0009 §D-8). `.ai/` is scanned by a secret-pattern check on every write (`MemoryManager.write` refuses content matching key patterns). Subprocess environments for agents are scrubbed to an allowlist (`PATH`, `HOME`, `TMP`, Unity vars); provider keys are not passed — Codex uses its own login, Claude SDK runs inside the kernel process |
| Credential abstraction | `CredentialStore.get(name) -> SecretStr`; providers are constructed with it; nothing else reads env vars for secrets |
| Command restrictions | `PermissionRule.command_patterns` (glob/regex on shell commands) with default deny for `rm -rf /`, `git push --force`, `git merge` to protected, `curl|wget` external, package managers unless role allows |
| Audit log | ledger + `hook_executions` + `approval_requests`; `TOOL_DENIED` events are first-class |

Protected actions (§92) are a configurable list (`.ai/agents/permissions.yaml: protected_actions`) defaulting to: `git.merge_protected`, `git.delete_branch_protected`, `repo.delete_data`, `store.publish`, `credentials.change`, `monetization.change`, `jira.delete`, `permissions.alter`. Each maps to `PermissionEffect.REQUIRE_APPROVAL` with `approver=USER`; the run pauses (`PAUSED_FOR_APPROVAL`) until `walk approve <id>` / `walk deny <id>`.

Human override (§93): CLI commands `walk pause [--agent RUN]`, `walk resume`, `walk work cancel <id>`, `walk phase stop <id>`, `walk decisions override <id>`, `walk work priority <id> <n>`, `walk policy set-model <role> ...`, `walk policy set-autonomy <level>`, `walk work force-review <id>` — all recorded as `USER_OVERRIDE` ledger events and usable as improvement evidence (§118).

---

## 7. Invariants (§137) → enforcing mechanism

| # | Invariant | Concrete mechanism |
|---|---|---|
| 1 | Role ≠ Model | `AgentInstance` holds `role` + `constitution` independently of `RoutingDecision.model_id`; `ModelAdapter`s are stateless w.r.t. role; provider SDK imports confined to `model_router/adapters/*` (import-linter); §132 failover test in CI |
| 2 | Project Knowledge ≠ Model Context | Durable knowledge only via `MemoryManager` writes to `.ai/` (git) and SQLite; `AgentOutput.context_updates` is the only channel from model to memory; adapters drop thinking blocks; `ON_AGENT_END` MUST hook requires context update or explicit `no_context_change_reason` |
| 3 | Work State ≠ Project Knowledge | `WorkProvider` writes only work-item fields/status/comments; `MemoryManager` never writes to Jira; `workflow` and `memory` packages are siblings with no mutual import |
| 4 | Implementation ≠ Verification | Transition table: `IMPLEMENTING → … → COMPLETE` requires `LEAD_DEV_REVIEW` event by `LEAD_DEV` and `qc_passed` by `QC` (role checked in `Guard`); `TaskRouter` never assigns reviewer role to the run that implemented; `cross_model_review` prefers a different model (§23) |
| 5 | Opinion ≠ Decision | `DebatePosition` and `AgentOutput.decisions` are *proposals* (`DecisionStatus.PROPOSED`); only `DecisionManager.record()` invoked by an authority with matching `Constitution.authority.decision_scope` (or user) sets `ACCEPTED` |
| 6 | Feature Complete ≠ Code Complete | `Feature.done_dimensions: dict[DoneDimension, bool]` (§6.5); guard `all_applicable_dimensions_done` on `QC → COMPLETE` for features |
| 7 | Autonomy always has boundaries | `AutonomyLevel` on every decision/escalation; `Constitution.authority.max_autonomy_level`; Level 3 items always create `ApprovalRequest(approver=USER)`; phase scope guard: work items outside `Phase.scope` cannot leave `IDEA` while the phase is `ACTIVE` |
| 8 | Important decisions are recoverable | `Decision` persisted in SQLite and `.ai/decisions/DEC-NNNN.md` with topic, participants, positions, evidence ids, alternatives, owner, rationale, version (§44) |
| 9 | Important actions are auditable | Ledger write points (§4.3); `LedgerEvent` immutable (no UPDATE/DELETE statements exist in `telemetry/repository.py`; trigger `ledger_events_no_update` in SQLite) |
| 10 | Approved artifacts cannot silently drift | `ApprovedArtifact` carries `content_sha256`; `MemoryManager.write` to `.ai/approved/` requires `ChangeRequest` + approver; `BoundaryAuditor` forbids agent writes under `.ai/approved/`; startup check compares hashes and raises `ON_CONTEXT_STALE(INVALID)` on mismatch |
| 11 | Skills are model-independent | Single source `.ai/agents/skills/<name>/SKILL.md` (+ kernel built-ins); projections generated by adapters; `projections.lock.yaml` hashes; `walk skills check-drift` in `doctor` and at startup (ADR-0007) |
| 12 | Agent continuity does not depend on session continuity | Checkpoints + WIP commits + `Handover` documents; resume algorithm (§5.3); §132 failover test |
| 13 | Workflow improvement cannot silently modify production behavior | Versioned behavior artifacts (`BehaviorVersion`), project pins in `.ai/project/kernel-versions.yaml`, `RolloutStage` gates, candidate approval by risk tier (§104); `BoundaryAuditor` forbids agent writes to `.ai/agents/**` and kernel config; changelog entries required (§120) |
| 14 | User retains final product authority | `PhaseDecision` only via CLI (user), never via `AgentOutput`; `ApprovalRequest(approver=USER)` for Level 3; override commands (§93) always available and bypass agent authority |

---

## 8. Game repository layout: `.ai/` (§35, §123, §130; ADR-0003)

```text
GameProject/
├── Assets/  Packages/  ProjectSettings/  GDD/            # game + GDD (§123)
├── .walk/                                                 # gitignored kernel scratch: worktrees/, cache/, logs/
└── .ai/
    ├── kernel.db  kernel.db-wal  kernel.db-shm  kernel.lock   # gitignored (ADR-0001)
    ├── .gitignore                                         # generated by bootstrap
    ├── project/                                           # [MVP]
    │   ├── project.md                 # ProjectContext (§36)            type: project
    │   ├── constitution.md            # Project constitution & constraints (§24)  type: project_constitution
    │   ├── environment.yaml           # EnvironmentManifest (§26)
    │   ├── kernel-versions.yaml       # BehaviorVersion pins (§105)
    │   ├── work-provider.yaml         # provider kind + Jira mapping (ADR-0005)
    │   ├── gdd-coverage.md            # generated (§74)                   type: report
    │   └── traceability.yaml          # GDD requirement → spec → work item links (§73) [Stage 6]
    ├── phases/
    │   ├── PHASE-01.md                # Phase plan & status               type: phase
    │   └── PHASE-01/
    │       ├── evidence/              # PhaseEvidencePackage files (§69)
    │       ├── evidence-package.md    # generated                         type: evidence_package
    │       └── retrospective.md       # generated (§115)                  type: retrospective
    ├── features/                                          # [MVP]
    │   ├── FEAT-0012.md               # FeatureContext (§37)              type: feature
    │   └── FEAT-0012/evidence/        # screenshots, recordings, profiler exports
    ├── bugs/                                              # [MVP]
    │   └── BUG-0031.md                # BugContext (§38)                  type: bug
    ├── decisions/                                         # [MVP]
    │   └── DEC-0007.md                # Decision (§44)                    type: decision
    ├── approved/                                          # [Stage 2]
    │   ├── APR-0003.md                # ApprovedArtifact metadata (§33)   type: approved
    │   └── APR-0003/                  # payload (concept art, spec, baseline manifest)
    ├── reports/                                           # generated from ledger (§83)
    │   ├── tasks/   features/   phases/   project/   cost/   improvement/
    ├── handovers/                                         # [MVP]
    │   └── HO-0005.md                 # Handover (§22)                    type: handover
    ├── improvements/                                      # project-level learning (§110, §119)
    │   ├── OBS-0001.md                type: observation
    │   ├── IMP-0004.md                type: improvement_candidate
    │   ├── PATTERN-001.md             type: pattern     (project-scoped)
    │   └── RETRO-PHASE-01.md          type: retrospective
    └── agents/                                            # Production Kit (§24) [Stage 2]; MVP ships kernel defaults
        ├── roles/<role>.md            # per-project Constitution overrides (§12)   type: constitution
        ├── policies.yaml              # RuntimePolicy per role (§13–§20)
        ├── models.yaml                # ModelDescriptor overrides / disabled models (§16)
        ├── permissions.yaml           # PermissionRule set + protected_actions (§31, §92)
        ├── hooks.yaml                 # project hooks (§32)
        ├── skills/<skill-name>/SKILL.md   # canonical skills (§28)
        └── projections.lock.yaml      # skill projection hashes (drift detection)
```

### 8.1 File naming convention

`<PREFIX>-<zero-padded seq>.md` using the ID conventions in `DOMAIN-MODEL.md` §2 (`FEAT-0012`, `BUG-0031`, `DEC-0007`, `HO-0005`, `APR-0003`, `OBS-0001`, `IMP-0004`, `PHASE-01`). Sub-folders with the same stem hold binary payloads. Role files use `snake_case` role names (`lead_dev.md`). Skills use kebab-case directory names (`unity-debugging/SKILL.md`).

### 8.2 Front matter schema (common header)

Every `.ai/**/*.md` begins with a YAML front matter block validated by `walk.memory.models.FrontMatter`:

```yaml
---
id: FEAT-0012                 # required; equals file stem
type: feature                 # required; MemoryDocType enum
title: Save System            # required
status: IMPLEMENTING          # type-specific enum as string
version: 3                    # monotonically increasing per write
schema_version: 1             # front-matter schema version (migration)
created_at: 2026-10-05T09:12:00Z
updated_at: 2026-10-07T14:03:11Z
updated_by:                   # who last wrote it
  role: SENIOR_DEV
  model_id: codex/gpt-5-codex
  run_id: RUN-01J9...
freshness:                    # §42; written by ON_CONTEXT_UPDATED
  commit: 3f9c2e1             # HEAD of the work branch at write time
  branch: feat/FEAT-0012-save-system
  pr: 42                      # optional
  build: 2026.10.07.3         # optional
  timestamp: 2026-10-07T14:03:11Z
related:                      # typed links; ids must resolve
  work_items: [STORY-0412, STORY-0413]
  decisions: [DEC-0007]
  approved: [APR-0003]
  gdd: ["GDD/combat.md#shotgun"]
relevant_files:               # used by freshness classification
  - Assets/Scripts/Save/SaveManager.cs
---
```

Type-specific sections (Markdown H2 headings, fixed names, in this order) are defined per `MemoryDocType` in `DOMAIN-MODEL.md` §4 (e.g. feature: Intent, Design Goal, Relevant GDD, Current Status, Architecture, Affected Systems, Dependencies, Relevant Files, Important Decisions, Implementation Notes, Known Risks, QC Notes, Evidence, Remaining Work — §37 verbatim). `MemoryManager` parses H2 sections into the pydantic context models; unknown sections are preserved verbatim.

---

## 9. Kernel-side improvement storage `.improvement/` (§119; ADR-0008)

Project learning stays in `<repo>/.ai/improvements/`. **Kernel** (cross-project) learning lives outside any game repo at `$WALK_HOME/.improvement/` (default `WALK_HOME=~/.walk`; may itself be a git repository for sharing across machines):

```text
$WALK_HOME/
├── kernel.db                       # cross-project SQLite: observations index, candidates, experiments, behavior_versions, changelog
├── config.yaml                     # global defaults (providers, global budget §20, telemetry)
└── .improvement/
    ├── observations/OBS-K-0001.md      # promoted from projects (§111); type: observation, scope: kernel
    ├── candidates/IMP-0031.md          # ImprovementCandidate (§98)
    ├── experiments/EXP-0003.md         # Experiment design + results (§107–§108) [Stage 10]
    ├── patterns/PATTERN-021.md         # §112
    ├── anti-patterns/ANTI-017.md       # §113
    ├── retrospectives/<project>-PHASE-03.md   # copies of project retrospectives (§115)
    └── changelog/0.8.2.md              # §120 entries, keyed by kernel behavior release
```

Promotion (§111) is explicit: `walk improvement promote OBS-0001` copies a project observation to kernel scope with `origin_project` recorded; nothing is promoted automatically (§110). Behavior artifacts carry versions (`BehaviorVersion`); the project's `kernel-versions.yaml` pins which versions it runs; changing a pin is a `MEDIUM`/`HIGH` risk change requiring approval per §104.

---

## 10. MVP boundary summary (§127–§134)

| Area | `[MVP]` | Later |
|---|---|---|
| Roles | Orchestrator, Lead Dev, Senior Dev, QC (PO, Design Leader optional) | Art Director, UA, Game Director `[Stage 8/11]` |
| Models | `ClaudeAdapter`, `CodexAdapter`; preferred/fallback/handover demonstrated (§128, §132) | further adapters via plugin entry points (ADR-0009 §D-11) |
| Work provider | `LocalWorkProvider` default; `JiraWorkProvider` required by §129 (Stage 3) | webhooks `[Stage 3]`, full status mapping config |
| Memory | `project/ features/ bugs/ decisions/ handovers/` (§130) | `approved/` `[Stage 2]`, `phases/` `[Stage 6–7]`, `improvements/` `[Stage 10]` |
| Workflow | feature lifecycle §131 incl. fix loop; phase lifecycle data model present, gate CLI minimal | autonomous phase scheduler `[Stage 7]`, RC `[Stage 11]` |
| Debate | minimal path for §133 (open → positions → decision) | PO/user escalation `[Stage 5]` |
| Improvement | observations + phase retrospective skeleton | candidates, experiments, versioning `[Stage 10]` |
| Unity | batchmode compile + EditMode/PlayMode tests (§62) | builds, asset validation, screenshot/console/asset inspection via batchmode CLI `[Stage 8]` (ADR-0015) |
