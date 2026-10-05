# ADR-0008 — Kernel vs Project Learning Separation and Behavior Versioning

**Status:** Proposed (owner confirmation required before Stage 10; data model fixed now)
**Date:** 2026-10-05
**Deciders:** Project owner, system architect

## Context

§94–§121 define continuous improvement: observations → hypothesis → candidate → review/experiment → approved, versioned, measurable, reversible change (§121); no uncontrolled self-modification (§103, Invariant 13); project learning must not automatically become kernel behaviour (§110) and promotion is explicit (§111); behaviour must be versioned and projects must know which versions they run (§105); storage split between `GameProject/.ai/improvements/` and kernel `.improvement/` (§119); §139 leaves "experiment methodology" open.

## Decision

**D-1 Two learning scopes, two stores.** `LearningScope.PROJECT` artefacts live in `<repo>/.ai/improvements/` + project `kernel.db`; `LearningScope.KERNEL` artefacts live in `$WALK_HOME/.improvement/` + `$WALK_HOME/kernel.db` (`ARCHITECTURE.md` §9). The same pydantic models are used with `scope` set; IDs differ (`OBS-` vs `OBS-K-`).

**D-2 Promotion is a human/authority action.** `walk improvement promote OBS-0001` (or `ImprovementManager.promote`) copies with `origin_project` and sets `promoted_to`; automatic detection (`detect_signals`) only ever creates PROJECT-scoped observations. Cross-project patterns (§111) are created by the `PROCESS_ARCHITECT` role or the user from ≥ 2 projects' observations.

**D-3 Versioned behaviour artefacts.** Every behaviour that can be improved (§100) is a `BehaviorVersion(kind: ImprovementScope, name, version, stage, content_sha256, source_path)`: transition tables (`WORKFLOW`), constitutions (`CONSTITUTION`), skills (`SKILL`), prompt templates (`PROMPT`), memory section schemas (`CONTEXT_FORMAT`), story templates (`STORY_TEMPLATE`), routing/effort policies (`MODEL_ROUTING`, `EFFORT_POLICY`), tool rules (`TOOL_USAGE`), hooks (`HOOK`), guards (`QUALITY_GATE`). Versions are `MAJOR.MINOR`; a MAJOR bump means projects must opt in.

**D-4 Project pinning.** `.ai/project/kernel-versions.yaml` maps `<kind>/<name> → version`. The kernel loads exactly the pinned version (built-ins ship all `DEFAULT` and `DEPRECATED`-but-supported versions). Every `LedgerEvent.behavior_versions` records the versions in effect (§82, §105). Changing a pin is itself an improvement decision (MEDIUM risk; HIGH for workflow/autonomy/permissions, §104).

**D-5 Rollout stages** (§109) with gates per `INTERFACES.md` §3.7: DRAFT → EXPERIMENTAL → LIMITED → DEFAULT → DEPRECATED; `rollback` to DRAFT from EXPERIMENTAL/LIMITED. New projects get `DEFAULT` versions; `LIMITED` versions are opt-in per project pin.

**D-6 Authority tiers** (§104): `ImprovementRisk.LOW` auto-approvable by ORCHESTRATOR (logging, metadata, template clarification); `MEDIUM` by PRODUCT_OWNER/maintainer (skills, routing, workflow step, DoR); `HIGH` by USER (autonomy boundary, agent authority, major workflow, phase gate, destructive permissions). `review_candidate` enforces the tier.

**D-7 Agents cannot write behaviour artefacts.** `BoundaryAuditor` forbids agent diffs under `.ai/agents/**` and kernel package paths; `ImprovementCandidate.proposed_change` is text + optional patch file under `.improvement/candidates/IMP-NN/`, applied only by `register_version` after approval (§103 Observe → Propose → Review → Approve → Version → Rollout).

**D-8 Changelog.** `register_version` to `LIMITED`/`DEFAULT` requires a `kernel_changelog` entry (`version, changed, reason=IMP-id, evidence`) (§120).

**D-9 Experiment methodology `[Stage 10]`.** Two methods: (a) `AB_BY_WORK_ITEM_HASH` — work items are assigned control/treatment by `sha1(work_item_id) % 2` within opted-in projects, compared on §107 metrics (duration, rework, QC defects, tokens, cost, escalations) with minimum sample `n ≥ 20` items per arm; (b) `SHADOW` — the treatment version computes its decision (routing/effort/context) and the kernel records `would_have = …` in the ledger payload without acting (§108). Statistical details (significance threshold) are deferred to Stage 10 and will be an addendum to this ADR.

## Alternatives

- **Single global store with project tags:** rejected — §110 demands separation; a shared file store across machines/projects would also conflate authority.
- **Git-based versioning only (no explicit version strings):** rejected — projects need a stable name to pin and ledger events need a compact version tag.
- **Allow agents to edit their own constitution behind a review PR:** rejected — still "agent edits constitution" (§103); proposals must be data, not edits.

## Consequences

- All built-in behaviour files carry `version:` front matter from Stage 1 even though improvement tooling arrives in Stage 10.
- `BehaviorVersion` loading adds a resolution step at startup; mismatched pins fail fast with guidance (`walk version`).
- Experiments need ≥ 2 projects or long phases to reach sample sizes; shadow mode is the practical default for high-risk changes.

## Related requirements

§94–§121, §137 (Invariant 13), §138 "Workflow Drift", §139 "experiment methodology".
