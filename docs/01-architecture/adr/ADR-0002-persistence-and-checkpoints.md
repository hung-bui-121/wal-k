# ADR-0002 — Workflow Persistence & Checkpoint Model

**Status:** Proposed (owner confirmation required before Stage 1)
**Date:** 2026-10-05
**Deciders:** Project owner, system architect

## Context

§54 requires workflow state to survive process, model, provider, machine and agent failures; §89 requires resumption from the last durable checkpoint; §90 requires idempotent critical operations; §132 mandates a failover test where Codex is interrupted mid-implementation and Claude continues. ADR-0001 fixed SQLite as the durable store but left table design, checkpoint granularity and the handling of in-progress code changes open (§139 "whether kernel requires a database").

Constraints: single kernel process per project; human-readable knowledge must stay in `.ai/` (ADR-0003); in-progress code must survive a machine restart (§27 reproducibility across machines).

## Decision

**D-1 Storage split.** Durable *kernel state* (workflow, runs, checkpoints, ledger, budgets, cost, approvals, idempotency) lives in `<repo>/.ai/kernel.db` (SQLite, WAL). Durable *knowledge* lives in `.ai/**/*.md` (git). The two never duplicate authority: `work_items.state` is the only source of workflow state; Markdown docs are the only source of narrative knowledge; `memory_index` is a rebuildable cache.

**D-2 Table pattern: aggregate JSON + indexed projection columns.** Each persisted pydantic aggregate is stored as `json TEXT` (`model_dump_json()`) plus the columns needed for querying and uniqueness (see `DOMAIN-MODEL.md` §6.2). Rationale: schema stability across model evolution, while keeping indexes for hot queries (`state`, `external_ref`, `run_id`, `kind/at`).

**D-3 Append-only tables.** `ledger_events`, `checkpoints`, `cost_records`, `evidence`, `work_item_transitions` have `BEFORE UPDATE`/`BEFORE DELETE` triggers that abort (Invariant 9).

**D-4 Checkpoint granularity and WIP commits.** A `Checkpoint` row is written at run `START`, every `checkpoint_every_tool_calls` (default 10) tool calls (`PERIODIC`), on adapter `CHECKPOINT_HINT` (`AGENT_REQUESTED`), before any handoff/fallback (`HANDOFF`), on pause (`PAUSE`) and at run `END`. Every checkpoint first makes a **WIP commit** on the work branch (`wip(<work_item>): checkpoint <seq>`, trailer `Walk-Work-Item`) so that uncommitted code is durable and portable (§27, §132); WIP commits are squashed by the kernel (`GitProvider.squash_wip`) before a PR is opened. A checkpoint stores: identity (run, item, role, model, effort, workflow state), `head_sha`, dirty files, tool-call counter, budget consumption, provider session ref (for native resume), `handover_id`, and a `ContextBundleRef` manifest. It never stores model transcripts or chain-of-thought (§22).

**D-5 Handover is a first-class document.** `Handover` (§22 fields) is persisted in `handovers` and written to `.ai/handovers/HO-NNNN.md` at `HANDOFF`, `PAUSE`, `PARTIAL` and `FALLBACK`. Resume feeds the latest open handover into `AgentInput.handover`.

**D-6 Resume algorithm** is the one in `ARCHITECTURE.md` §5.3: orphaned runs (`kernel_instance != current`) → `INTERRUPTED` → latest checkpoint → native provider resume if healthy and resumable, else new run on the routed model with the handover (§132 path).

**D-7 Idempotency store.** `idempotency_keys(key PK, operation, result_ref, created_at)`; key formats in `ARCHITECTURE.md` §5.4. Keys are inserted in the same transaction as the local state change. Providers additionally reconcile by label `walk:<WorkItemId>` for creates.

**D-8 Migrations.** Numbered SQL files (`persistence/migrations/{project,kernel}/NNNN_name.sql`, optional paired `.py`) applied at startup inside one transaction; `schema_migrations` + `PRAGMA user_version`; backup before Python-step migrations.

**D-9 Transactions.** `UnitOfWork` wraps one SQLite transaction (`BEGIN IMMEDIATE`); a workflow transition, its ledger event, its idempotency key and its transition row commit atomically. Hooks fire *after* commit.

## Alternatives

- **Event-sourcing everything (rebuild state from ledger):** rejected — more code, slower queries, and the ledger would carry mutable-state semantics; we keep the ledger as audit log with explicit state tables.
- **Checkpoint only at run end:** rejected — fails §132 (interrupt mid-run) and §89.
- **Keep WIP in a stash / patch files instead of commits:** rejected — not portable across machines, invisible to git tooling, harder to audit.
- **One SQLite DB per entity group:** rejected — cross-table transactions are needed (transition + ledger + idempotency).
- **Postgres:** deferred (ADR-0001); revisit with multi-machine execution.

## Consequences

- Branch history contains `wip(...)` commits until squash; `GitProvider.squash_wip` is mandatory before PR; protected branches never receive WIP commits.
- Every external write site must pass an idempotency key — enforced by signature (`*, idempotency_key: str`) on all `WorkProvider`/`GitProvider`/`CiProvider` mutating methods.
- Checkpoint frequency is a budgeted cost (git commit ≈ 100 ms); default 10 tool calls is tunable per role in `RuntimePolicy.checkpoint_every_tool_calls`.
- Tests: §132 failover test = kill kernel during Codex run → restart → assert Claude run with `handover_in_id` set and same branch HEAD.

## Related requirements

§22, §27, §41, §54, §81, §89, §90, §132, §137 (Invariants 9, 12), §139.
