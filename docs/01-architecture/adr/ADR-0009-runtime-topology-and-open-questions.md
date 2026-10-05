# ADR-0009 — Runtime Topology, Scheduler, Sandbox, and Resolution of Remaining §139 Open Questions

**Status:** Proposed (owner confirmation required before Stage 1)
**Date:** 2026-10-05
**Deciders:** Project owner, system architect

## Context

§139 lists open design questions. ADR-0001–0008 and ADR-0010–0013 resolve: `.ai` format (0003), database (0001/0002), workflow engine (0001/0010), Jira schema (0005), model adapter API (0004), effort mapping (0011), context ranking (0012), constitution schema (0013), experiment methodology (0008, partially), sandbox (0006 partially). This ADR records the rest in one place so every §139 item is either decided or explicitly deferred with a stage, and fixes structural choices the other docs rely on.

## Decision

| # | Question | Decision | Status |
|---|---|---|---|
| D-1 | Package list vs shared primitives | Packages = §122 list + `walk.common` (typed ids, clock, errors, `Actor`, and the cross-cutting enums `AgentRole`, `Effort`, `LearningScope`, `ImprovementScope`). `common` has zero I/O and zero third-party imports beyond pydantic. Anything else cross-cutting must be placed in the lowest package that owns the concept (see `ARCHITECTURE.md` §2.2 cycle check). | Decided |
| D-2 | Repository layout | `src/walk/` src-layout (ADR-0001). Package name `walk`, CLI `walk`. §122's `model-router` becomes `model_router`. | Decided |
| D-3 | Local daemon vs server | **Local daemon per project** (`walk run`), single process, `asyncio`. CLI ⇄ daemon IPC through SQLite `commands`/`command_results` tables (polling 250 ms) — no sockets, works on Windows/macOS/Linux, auditable. Optional HTTP listener only for Jira webhooks and a read-only `/status` JSON endpoint (§87). Not multi-tenant. | Decided |
| D-4 | Scheduler design | Tick-based admission (`INTERFACES.md` §5.1): wake-ups from timer (5 s), webhook, poll, run completion, commands. Readiness derived from workflow state + dependencies + phase scope; ordering = blockers, bug severity, priority, age; limits `max_parallel_agents` (2 `[MVP]`, configurable `[Stage 7]`), per-role `max_parallel_runs`, `TaskRouter.can_run_parallel` (§60). Scheduling idempotency key per `(item, state, state_version)`. | Decided |
| D-5 | Sandbox technology | **Git worktrees** under `<repo>/.walk/worktrees/<run_id>` (one per run) + provider sandbox modes (Claude `can_use_tool` path checks; Codex `--sandbox workspace-write`, network off) + `BoundaryAuditor` + git guard hooks. No containers in MVP. Containers (Docker) deferred to `[Stage 7]` when parallel agents increase and Unity-in-container is validated. | Decided for MVP; containers deferred (Stage 7) |
| D-6 | Unity Editor automation method | **Unity batchmode CLI** through a small editor package `com.walk.ci` (installed into the game project by bootstrap as a local package under `Packages/com.walk.ci/`) exposing static methods `WalK.CI.Compile`, `WalK.CI.RunTests(mode)`, `WalK.CI.Build(target)`, `WalK.CI.ValidateAssets` and writing JSON result files the `UnityBatchProvider` parses. Unity MCP deferred to `[Stage 8]` (Art/Design) as an additional `ToolKind.MCP` provider. | Decided for MVP; MCP deferred (Stage 8) |
| D-7 | Hooks execution model | Kernel-side, synchronous, priority-ordered, with `fail_closed` for required hooks (ARCHITECTURE.md §4.1). Project hooks are shell commands or kernel actions declared in `hooks.yaml`; they never run inside model prompts. | Decided |
| D-8 | Provider credential model | `CredentialStore` resolves, in order: environment variable → OS keyring (`keyring` service `walk`, username = credential name) → absent. Names: `ANTHROPIC_API_KEY` (optional; Claude SDK may also use its own login), `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `WALK_WEBHOOK_SECRET`, `MESHY_API_KEY` `[Stage 8]`, `OPENART_API_KEY` `[Stage 8]`. Codex uses its own `codex login` state; no key passes through the kernel. `.ai/` never stores secrets (write-time scan); `walk doctor` reports presence only. Agent subprocess env is an allowlist. | Decided |
| D-9 | Graphify integration | `GraphifyProvider` implements `CodeGraphProvider` by invoking the `graphify` CLI (`graphify .`, `graphify query`, and reading `graphify-out/graph.json` for neighbourhoods/impact). Index built at bootstrap and refreshed incrementally at `ON_MERGED` and on `mark_dirty` batches; `graphify-out/` gitignored. Graphify is **recommended, not required** (§129): when absent, `ContextManager` skips CODE_GRAPH items and widens SOURCE_FILE heuristics. | Decided |
| D-10 | Dependency-rule enforcement | `import-linter` contracts generated from the table in `ARCHITECTURE.md` §2.2 + ruff `banned-api` for SDK confinement; run in CI and `walk doctor --strict` (dev mode). | Decided |
| D-11 | Kernel plugin packaging | Python entry points: `walk.adapters` (→ `ModelAdapter` factory), `walk.providers` (→ `WorkProvider`/`GitProvider`/`AssetProvider`/`CodeGraphProvider` factories), `walk.tools` (→ `ToolSpec` lists), `walk.hooks` (→ builtin `Hook`s), `walk.skills` (→ skill directories). Discovered via `importlib.metadata.entry_points(group=...)` at startup; plugin versions recorded in `EnvironmentManifest.tools`. | Decided |
| D-12 | Multi-machine execution | **Deferred to Stage 9.** Preconditions already in place: `.ai/` + WIP commits in git, per-machine `kernel.db`, `machine_id` in manifests, idempotency keys. Design sketch for later: a lease table on a shared store (or Jira assignee as lease) and ledger merge by ULID. Until then, one machine runs the kernel for a project at a time (lock file). | Deferred (Stage 9) |
| D-13 | Asset review automation | **Deferred to Stage 8.** Data model fixed now (`AssetProvider`, `AssetProvenance`, `EvidenceKind` entries, §79 validation as `UnityProvider.validate_assets`). | Deferred (Stage 8) |
| D-14 | Dashboard stack | **Deferred to Stage 9.** Data contract fixed now: `walk status --json` (`KernelStatus`), `/status` endpoint, read-only SQLite views `v_phase_progress`, `v_model_usage`, `v_budget_usage`, `v_pending_decisions` (added in migration `0003_dashboard_views.sql`). | Deferred (Stage 9) |
| D-15 | Experiment methodology | A/B by work-item hash and shadow evaluation (ADR-0008 D-9); statistical thresholds deferred. | Partially decided; addendum Stage 10 |
| D-16 | Logging | stdlib `logging` → JSON lines in `<repo>/.walk/logs/kernel.jsonl` with rotation (10 × 20 MB); never the source of truth (ADR-0001). | Decided |
| D-17 | Time & IDs | All timestamps UTC ISO-8601; ULIDs generated in-process (`python-ulid`), sequences from `id_sequences`. | Decided |

## Alternatives

- **Long-running HTTP server with REST API for CLI:** rejected for MVP — an extra network surface and auth story; SQLite IPC is enough for one user per project. Can be added later without changing `Orchestrator`.
- **Celery/Redis/Temporal scheduler:** rejected — operational burden for a single-process kernel (ADR-0001).
- **Unity MCP first:** rejected — batchmode is deterministic, CI-friendly and needed anyway for builds/tests (§62).
- **Store credentials in `.ai/project/secrets.yaml` (gitignored):** rejected — too easy to commit by accident; keyring/env are standard.
- **Hooks as model-visible instructions:** rejected — §32 requires deterministic enforcement.

## Consequences

- Windows is a first-class platform (owner environment): no Unix sockets, path handling via `pathlib`, git hooks as `sh` scripts (Git for Windows ships `sh`).
- `com.walk.ci` becomes a small C# artefact maintained alongside the kernel (`unity/com.walk.ci/`), versioned as part of the Production Kit.
- Plugins can extend providers and adapters without forking; the import-linter table must list plugin packages as "edge" (SDK imports allowed).

## Related requirements

§7, §8, §26–§27, §32, §43, §56, §60, §62, §87, §91, §122, §129, §135, §139.
