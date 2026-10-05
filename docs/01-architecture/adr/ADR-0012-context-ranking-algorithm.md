# ADR-0012 — Context-First Retrieval and Ranking Algorithm

**Status:** Proposed (owner confirmation required before Stage 1)
**Date:** 2026-10-05
**Deciders:** Project owner, system architect

## Context

§6.8/§40 fix the order (work item → context → decisions → approved artifacts → workflow state → code graph → required source → execution); §42 requires freshness awareness; §43 splits roles of memory, code graph and source; §138 warns of context drift, hallucinated state and excessive context cost; §139 leaves the "context ranking algorithm" open. The algorithm must be deterministic (reproducible across implementing models) and cheap (no embedding service dependency in MVP).

## Decision

**D-1 Two tiers: mandatory and ranked.** Mandatory items (work item + contract, workflow state, open handover, feature/bug context, selected project-context sections, ACCEPTED relevant decisions, approved-artifact metadata) are always included in §40 order and never trimmed. Everything else (code-graph neighbourhoods, source files, evidence, proposed/superseded decisions, sibling contexts) is scored and admitted greedily within the token budget (`INTERFACES.md` §5.4).

**D-2 Score = relevance × freshness × role_weight** with the fixed constants in `INTERFACES.md` §5.4 (relevance: direct 1.0 / parent 0.8 / affected-systems 0.6 / graph `0.5/d` / keyword 0.3; freshness: CURRENT 1.0 / POSSIBLY_STALE 0.7 / INVALID 0 unless directly linked; role weights for source, evidence and graph). Ties break by `updated_at` desc then id. No embeddings, no LLM re-ranking in MVP.

**D-3 Token budget by effort** = `{LOW: 0.20, MEDIUM: 0.35, HIGH: 0.50, VERY_HIGH: 0.60} × context_window_tokens − reserved_output (max_output_tokens)`; estimate `tokens = chars / 3.5`.

**D-4 Stale handling.** POSSIBLY_STALE/INVALID items are flagged `requires_verification=True` in the bundle and the task template instructs the agent to verify against source before relying on them (§42 "stale context requires additional code verification"); `ON_CONTEXT_STALE` fires and counts towards §116 "context stale rate".

**D-5 Source slicing.** Source files are included as windows (≤ 400 lines centred on symbols referenced by the contract/feature context) rather than whole files; whole-repo reads are never pre-loaded (§6.8). Agents may still open more files via tools; that usage is metered and feeds the "excessive code reading" improvement signal (§99).

**D-6 Code graph optional.** Without `CodeGraphProvider`, CODE_GRAPH items are skipped and SOURCE_FILE candidates expand to the folders of `relevant_files` (depth 1).

**D-7 Determinism contract.** Given the same DB, `.ai/` tree, HEAD and request, `ContextManager.build` returns byte-identical bundles (tests assert this).

## Alternatives

- **Embedding-based semantic retrieval:** deferred to a Stage 4 experiment (ADR-0008 methodology) — adds a model dependency and non-determinism; structured links already cover most relevance.
- **Let the agent fetch all context itself with tools:** rejected — §6.8 and §138 (context cost, hallucination).
- **LLM re-ranker:** rejected for MVP — cost and non-determinism.

## Consequences

- Quality of retrieval depends on well-maintained `relevant_files`, `affected_systems` and links — enforced by `ON_AGENT_END` requiring context updates (Invariant 2).
- Ranking constants are a `BehaviorVersion kind=CONTEXT_FORMAT` (`context_ranking v1.0`) so they can be improved under §104 control.

## Related requirements

§6.8, §40–§43, §116, §138 ("Context Drift", "Hallucinated Project State", "Excessive Context Cost"), §139.
