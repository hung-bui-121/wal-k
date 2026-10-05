# ADR-0005 — Work Provider Abstraction (Local + Jira)

**Status:** Proposed (owner confirmation required before Stage 1)
**Date:** 2026-10-05
**Deciders:** Project owner, system architect

## Context

§8/§55 make Jira (or equivalent) the source of work state; §56 prefers webhook-driven scheduling with polling as backup; §90 requires idempotent Jira creation/comments; §129 requires Jira in MVP integrations; §139 leaves the "exact Jira schema" open. ADR-0001 decided a `WorkProvider` protocol with `LocalWorkProvider` and `JiraWorkProvider`. Development and tests must not require a Jira tenant.

## Decision

**D-1 Protocol** `WorkProvider` (`INTERFACES.md` §2.2): `create, update, transition, assign, comment, link, get, query, changes_since, parse_webhook, status_map, health`, all mutating methods with `*, idempotency_key`. Kernel IDs are never provider IDs; `WorkItem.external_ref` stores the provider key.

**D-2 `LocalWorkProvider` `[MVP]`** stores items in the project SQLite tables `local_work_items` (added by migration `0002_local_work_provider.sql`: `external_ref PK, work_item_id, status, assignee_role, json, updated_at`) and writes a human-readable mirror `.walk/work/<external_ref>.md` (gitignored). External refs are `LOCAL-<n>`. `changes_since` returns rows updated after `since`; `parse_webhook` raises `NotSupported`. It is the default provider and the one used by all unit/integration tests.

**D-3 `JiraWorkProvider` `[Stage 3]`** uses Jira Cloud REST v3 via `httpx`, basic auth (email + API token from `CredentialStore`). Mapping (`.ai/project/work-provider.yaml`, defaults shown):

| Kernel | Jira (default) |
|---|---|
| Project | project key `jira.project_key` |
| Phase | `fixVersion` named `<PHASE-id> <name>` |
| Epic | issue type Epic |
| Feature | issue type Story, label `walk-feature`, parent = Epic |
| Story / Task | issue type Sub-task under the Feature (configurable to Story/Task + "parent" link) |
| Bug | issue type Bug, issue link "relates to" Feature, label `walk-bug` |
| kernel id | label `walk:<ID>` (lookup + reconciliation) |
| owner role | label `walk-role:<ROLE>` (+ optional `assignee_accounts: {ROLE: accountId}`) |
| priority P0..P3 | Highest / High / Medium / Low |
| state | `status_map` below |

Default `status_map` (WorkItemState → Jira status name; project may rename): IDEA→"Backlog", DISCOVERY→"Discovery", DESIGN→"Design", READY→"Ready", BLOCKED→"Blocked", IMPLEMENTING→"In Progress", READY_FOR_REVIEW→"Ready for Review", LEAD_DEV_REVIEW→"In Review", INTEGRATION→"Integration", QC→"QC", REWORK→"Rework", PHASE_REVIEW→"Phase Review", USER_GATE→"User Gate", COMPLETE→"Done", CANCELLED→"Cancelled". Bootstrap `--provider jira` validates that the workflow has these statuses and prints the missing ones; transitions use the transition id resolved from the target status name (cached).

**D-4 Inbound events.** Webhook `POST /webhooks/jira` on the kernel's optional HTTP listener (`walk run --webhook-port`), validated by a shared secret query parameter and optional JWT; deliveries deduplicated in `webhook_deliveries`. Polling fallback: JQL `project = <KEY> AND labels = walk AND updated >= "<last_sync - 2m>"` every `poll_interval_s` (60) and on startup reconcile. Both feed `IntegrationManager.ingest`.

**D-5 Authority split.** Kernel is authoritative for workflow *state*; Jira is authoritative for backlog order, priority, assignee, dependency links, blockers (§55). An external status change that fails a kernel guard is reverted in Jira with a comment ("kernel rejected: <reason>") and logged `EXTERNAL_REJECTED`. Priority/blocker changes from Jira are always accepted.

**D-6 Idempotency & reconciliation.** Keys per `ARCHITECTURE.md` §5.4. `create` searches `labels = walk:<ID>` before creating; `comment` embeds a hidden marker `<!-- walk:<ledger_seq> -->` and checks for it before posting; `transition` is a no-op when the current status equals the target.

**D-7 Parity tests.** A contract test suite `tests/integrations/work_provider_contract.py` runs the same scenarios against `LocalWorkProvider` (always) and `JiraWorkProvider` (when `WALK_TEST_JIRA=1`), guaranteeing behavioural parity.

## Alternatives

- **Jira as the workflow engine (Jira automations drive transitions):** rejected — workflow must be kernel-owned and explicit (§53); Jira workflows vary per tenant.
- **Store kernel IDs in a custom field:** rejected for default — custom fields need admin setup; labels work on every Jira project (custom field remains configurable).
- **Polling only:** rejected — §56 prefers events; polling kept as fallback.
- **GitHub Issues provider in MVP:** deferred — can be added as a plugin (`walk.providers` entry point) without kernel changes.

## Consequences

- Jira workflow setup is a bootstrap prerequisite; `walk doctor` reports status-map gaps.
- Sub-task depth limits (Jira allows one level) force Story/Task under Feature; deeper nesting is represented by kernel `parent_id` only.
- All tests run offline with `LocalWorkProvider`; Jira tests are opt-in.

## Related requirements

§6.3, §8, §55–§58, §90, §124, §129, §137 (Invariant 3), §139.
