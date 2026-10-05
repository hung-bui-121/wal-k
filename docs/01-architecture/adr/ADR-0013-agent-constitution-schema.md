# ADR-0013 — Agent Constitution Schema

**Status:** Proposed (owner confirmation required before Stage 1; full use in Stage 5)
**Date:** 2026-10-05
**Deciders:** Project owner, system architect

## Context

§12 requires every role to support a common constitution with the conceptual fields Identity, Mission, Responsibilities, Authority, Professional Bias, Core Beliefs, Decision Principles, Risk Tolerance, Preferred Evidence, Conflict Behavior, Escalation Rules, Tool Permissions, Forbidden Actions — and states the detailed schema is deferred (§139). Constitutions must be model-independent (§12, Invariant 1), versioned (§105), and not editable by agents (§103).

## Decision

**D-1 Format.** A constitution is a Markdown document with YAML front matter, `type: constitution`, one per role: kernel defaults at `src/walk/agents/defaults/<role>.md`, project overrides at `.ai/agents/roles/<role>.md`. Parsed into `walk.agents.models.Constitution`.

**D-2 Front matter fields (structured, validated):**

```yaml
---
id: LEAD_DEV
type: constitution
title: Lead Developer
version: "1.0"                      # BehaviorVersion kind=CONSTITUTION
role: LEAD_DEV
identity: Lead Developer
mission: Protect long-term technical integrity.             # §10.6
responsibilities: [architecture, scalability, maintainability, performance, testability, consistency, technical debt, integration]
authority:
  decision_scope: [TECH]
  max_autonomy_level: 1
  may_approve: [review.approve, ARCHITECTURE_DIRECTION]
  may_reject: [review.reject]
  may_create_work: [TASK, BUG]
professional_bias: Technical integrity over speed; guard against over-engineering.
core_beliefs: ["Functional does not mean finished.", "Evidence beats assertion."]
decision_principles: ["Prefer reversible changes.", "Measure before optimising."]
risk_tolerance: LOW
preferred_evidence: [AUTOMATED_TEST, REPRODUCIBLE_BENCHMARK, PROFILER_RESULT]
conflict_behavior: Challenge design when technical risk is unaddressed; concede on evidence.
escalation_rules:
  - {condition: "core architecture migration", to_level: 3, category: TECH}
  - {condition: "cross-team scope increase", to_level: 2, category: PRODUCT}
tool_permissions:                   # PermissionRule list (ADR-0006), role implied
  - {tool: review.approve, effect: ALLOW}
  - {tool: git.merge_protected, effect: REQUIRE_APPROVAL, approver: USER}
forbidden_actions: ["approve own implementation", "close a feature without QC acceptance"]
---
```

**D-3 Body sections (free text rendered into the system prompt, in this order):** `## Identity`, `## Mission`, `## Responsibilities`, `## Authority`, `## Professional Bias`, `## Core Beliefs`, `## Decision Principles`, `## Risk Tolerance`, `## Preferred Evidence`, `## Conflict Behavior`, `## Escalation Rules`, `## Forbidden Actions`, `## Working Guidance` (optional, role know-how that is not a skill). Front matter is authoritative for structured fields; body elaborates.

**D-4 Merge rules for project overrides.** Scalars and lists in the override replace the default's **except** `authority`, `tool_permissions`, `forbidden_actions`, which may only be *narrowed* (override may remove permissions/lower autonomy, never add or raise) — widening requires a HIGH-risk improvement approval (§104). Body sections in the override replace same-named sections; new sections append.

**D-5 Model independence.** No field may mention a provider or model; a lint (`walk doctor --strict`) rejects constitutions containing provider names.

**D-6 Immutability at runtime.** `BoundaryAuditor` forbids agent writes under `.ai/agents/roles/`; changes flow through `ImprovementCandidate` (ADR-0008).

**D-7 MVP roles shipped:** ORCHESTRATOR, LEAD_DEV, SENIOR_DEV, QC (full), PRODUCT_OWNER and DESIGN_LEADER (optional, minimal), per §127. Remaining roles are added in Stages 5/8/11 using the same schema.

## Alternatives

- **Pure YAML constitutions:** rejected — long guidance text is better in Markdown and reviewable in PRs.
- **Constitution as code (Python classes):** rejected — not editable by non-developers, not versionable as data, blurs §103.
- **Free-form Markdown only:** rejected — kernel needs structured `authority`, `escalation_rules`, `tool_permissions` for enforcement (§31, §51).

## Consequences

- `Constitution.tool_permissions` and `.ai/agents/permissions.yaml` are merged by `PermissionManager.rules_for` (project file wins on exact duplicates, narrowing only).
- Prompt rendering is deterministic; constitution version appears in `LedgerEvent.behavior_versions`.

## Related requirements

§6.7, §9–§12, §31, §51, §103–§105, §127, §137 (Invariants 1, 7, 13), §139.
