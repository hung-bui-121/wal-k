# WAL-K Architecture Documentation

Source of truth for requirements: `requirements/WAL_K_REQ.md` (cited as `§NN`). These documents translate it into an implementable blueprint; names defined here are stable and referenced by the work breakdown.

| Document | One line |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Layered packages under `src/walk/`, import-dependency table, runtime topology, hooks, permission enforcement, ledger write points, recovery, security, invariant enforcement, `.ai/` and `.improvement/` layouts. |
| [DOMAIN-MODEL.md](DOMAIN-MODEL.md) | All pydantic v2 entities and enums, ID conventions, entity relationships, SQLite schema and migration approach. |
| [INTERFACES.md](INTERFACES.md) | `Protocol` definitions for every §125 service and provider boundary, workflow transition tables (feature/story/bug/phase/debate/RC/rollout), routing table, scheduler/effort/fallback/context/freshness algorithms, CLI surface. |
| [adr/ADR-0001-tech-stack.md](adr/ADR-0001-tech-stack.md) | Python 3.12 + pydantic v2 + SQLite + Markdown/YAML `.ai/` + in-house state machine + typer + Claude Agent SDK / `codex exec` (decided). |
| [adr/ADR-0002-persistence-and-checkpoints.md](adr/ADR-0002-persistence-and-checkpoints.md) | SQLite aggregate-JSON tables, append-only ledger, checkpoint granularity with WIP commits, resume algorithm, idempotency keys, migrations. |
| [adr/ADR-0003-ai-project-memory-format.md](adr/ADR-0003-ai-project-memory-format.md) | `.ai/` layout, file naming, front-matter schema, freshness = commit SHA + timestamp, single write path, approved-artifact hashing. |
| [adr/ADR-0004-model-adapter-boundary-and-handover.md](adr/ADR-0004-model-adapter-boundary-and-handover.md) | `ModelAdapter` protocol, normalised event stream, structured `AgentOutput` channel, handover built from kernel facts (never chain-of-thought), Claude/Codex specifics. |
| [adr/ADR-0005-work-provider-abstraction.md](adr/ADR-0005-work-provider-abstraction.md) | `WorkProvider` protocol, `LocalWorkProvider` for MVP/tests, Jira issue-type/status/label mapping, webhook + polling, authority split, parity tests. |
| [adr/ADR-0006-permission-enforcement-at-tool-boundary.md](adr/ADR-0006-permission-enforcement-at-tool-boundary.md) | Kernel-enforced allow/deny/require-approval at the tool boundary, kernel-executed side effects, protected actions, Codex compensating controls, default rule set. |
| [adr/ADR-0007-canonical-skill-registry-and-projections.md](adr/ADR-0007-canonical-skill-registry-and-projections.md) | Canonical `SKILL.md` source, adapter-generated worktree projections, hash-based drift detection. |
| [adr/ADR-0008-learning-separation-and-behavior-versioning.md](adr/ADR-0008-learning-separation-and-behavior-versioning.md) | Project vs kernel learning stores, explicit promotion, `BehaviorVersion` pinning, rollout stages, authority tiers, experiment methodology. |
| [adr/ADR-0009-runtime-topology-and-open-questions.md](adr/ADR-0009-runtime-topology-and-open-questions.md) | Local daemon + SQLite IPC, scheduler, worktree sandbox, Unity batchmode package, credentials, Graphify, plugin entry points, and explicit deferrals (multi-machine, asset review, dashboard). |
| [adr/ADR-0010-unified-work-item-state-enum.md](adr/ADR-0010-unified-work-item-state-enum.md) | One `WorkItemState` enum for all work-item kinds (bug loop mapped onto it), separate enums for phase/RC/debate/rollout, data-driven transition tables. |
| [adr/ADR-0011-effort-mapping-per-provider.md](adr/ADR-0011-effort-mapping-per-provider.md) | `LOW..VERY_HIGH` → Claude `effort` / Codex `model_reasoning_effort` via configurable model families, role defaults, degradation and re-queue semantics. |
| [adr/ADR-0012-context-ranking-algorithm.md](adr/ADR-0012-context-ranking-algorithm.md) | Mandatory + ranked context tiers, deterministic relevance × freshness × role-weight scoring, token budget by effort, source slicing. |
| [adr/ADR-0013-agent-constitution-schema.md](adr/ADR-0013-agent-constitution-schema.md) | Markdown + front-matter constitution schema for the §12 fields, narrowing-only project overrides, model-independence lint. |
| [adr/ADR-0015-unity-mcp-provider.md](adr/ADR-0015-unity-mcp-provider.md) | *Proposed.* Unity MCP as an optional `ToolKind.MCP` provider: in-house stdio client, protocol versions, tool bindings with fixed arguments, scrubbed server env. |
| [adr/ADR-0016-builtin-hook-placement.md](adr/ADR-0016-builtin-hook-placement.md) | Built-in hook callables live in `walk.orchestrator.builtin_hooks`; `walk.hooks` stays registry + dispatcher; composition root registers them once. |

Reading order for implementers: ADR-0001 → ARCHITECTURE → DOMAIN-MODEL → INTERFACES → remaining ADRs as referenced.
