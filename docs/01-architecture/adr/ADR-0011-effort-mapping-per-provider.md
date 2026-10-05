# ADR-0011 — Effort Mapping per Provider

**Status:** Proposed (owner confirmation required before Stage 1; model IDs are configuration and may be changed without re-opening this ADR)
**Date:** 2026-10-05
**Deciders:** Project owner, system architect

## Context

§17 requires provider-independent effort levels `LOW, MEDIUM, HIGH, VERY_HIGH` translated by adapters; §18–§19 define effective effort and dynamic changes; §139 leaves "effort mapping per provider" open. Current provider controls (as of 2026-10): Claude models expose an `effort` parameter (`low | medium | high | xhigh | max`) with adaptive thinking; the Claude Agent SDK forwards model and effort settings. Codex CLI exposes `model_reasoning_effort` (`low | medium | high | xhigh`) and a model selection.

## Decision

**D-1 Effort selects a (model, provider params) pair per `ModelId` "family".** Policies reference families (`claude/opus`, `claude/sonnet`, `codex/default`); `models.yaml` resolves each family to concrete model IDs and per-effort parameters so model generations can change without code or ADR changes.

**D-2 Default mapping (kernel `walk/model_router/defaults/models.yaml`, overridable in `.ai/agents/models.yaml`):**

| Effort | `claude/opus` family | `claude/sonnet` family | `codex/default` family |
|---|---|---|---|
| LOW | model `claude-opus-5-5`, `effort: low`, `max_turns: 40` | `claude-sonnet-5-5`, `effort: low`, `max_turns: 40` | `gpt-5-codex`, `model_reasoning_effort: low` |
| MEDIUM | `claude-opus-5-5`, `effort: medium`, `max_turns: 80` | `claude-sonnet-5-5`, `effort: medium`, `max_turns: 80` | `gpt-5-codex`, `model_reasoning_effort: medium` |
| HIGH | `claude-opus-5-5`, `effort: high`, `max_turns: 150` | `claude-sonnet-5-5`, `effort: high`, `max_turns: 150` | `gpt-5-codex`, `model_reasoning_effort: high` |
| VERY_HIGH | `claude-opus-5-5`, `effort: xhigh`, `max_turns: 300` | escalates to `claude/opus` row | `gpt-5-codex`, `model_reasoning_effort: xhigh` |

Thinking is left adaptive (never a fixed token budget). `max_turns` and the per-effort `EXECUTION_TIME_S` budget (LOW 10 min, MEDIUM 25 min, HIGH 45 min, VERY_HIGH 90 min) are part of the mapping because effort also bounds wall-clock (§20).

**D-3 Role → family defaults** (§15, configurable in `policies.yaml`): ORCHESTRATOR, PRODUCT_OWNER, DESIGN_LEADER, ART_DIRECTOR, UA_RELEASE → preferred `claude/opus`, fallback `codex/default`; SCRUM_MASTER → `claude/sonnet`, fallback `claude/opus`; LEAD_DEV → `claude/opus`, fallback `codex/default`; SENIOR_DEV → `codex/default`, fallback `claude/opus`; QC → `claude/sonnet`, fallback `codex/default` (with `cross_model_review=true` so QC/review differ from the implementer, §23).

**D-4 Degradation rule.** If a family lacks a level (`ModelDescriptor.supports_effort_levels`), `map_effort` picks the nearest lower supported level and sets `ProviderEffortConfig.params["degraded_from"]`; `EFFORT_SET` ledger payload records it.

**D-5 Cost estimate table** for effort resolution step 7 (`INTERFACES.md` §5.2) is seeded with static USD values `{LOW: 1, MEDIUM: 3, HIGH: 8, VERY_HIGH: 20}` and replaced by rolling per-role/per-effort means from `cost_records` once ≥ 10 samples exist.

**D-6 Mid-run changes are not applied to the running session** (§19 request semantics): the change is recorded and takes effect on the next run of the work item; agents that need more effort immediately return `PARTIAL` with `effort_request`, and the scheduler re-queues at once with `escalation_bump`.

## Alternatives

- **Map effort to thinking token budgets:** rejected — fixed budgets are deprecated on current Claude models; `effort` is the supported control.
- **Hard-code model IDs in adapters:** rejected — model generations change quarterly; configuration keeps ADR-0001/0004 stable.
- **Reconfigure the live session on effort upgrade:** rejected — neither provider supports it cleanly within a run; re-queue is deterministic and checkpointed.

## Consequences

- `ModelDescriptor` must carry `supports_effort_levels` and prices for every configured model; `walk doctor` validates `models.yaml`.
- Costs per effort level become measurable and feed §116 metrics.
- Family indirection adds one lookup; `RoutingDecision.model_id` is always the concrete model for the ledger (§82).

## Related requirements

§14–§20, §23, §82, §84, §116, §139.
