# ADR-0010 — Unified `WorkItemState` Enum and Per-Kind Transition Tables

**Status:** Proposed (owner confirmation required before Stage 1)
**Date:** 2026-10-05
**Deciders:** Project owner, system architect

## Context

§53 lists possible workflow states (IDEA … COMPLETE) including a coarse `REVIEW`; §61 refines review into `READY_FOR_REVIEW → LEAD_DEV_REVIEW → INTEGRATION`; §58 introduces `BLOCKED`; §64 describes a bug loop (Triage → Assign → Fix → Review → Re-test → Close/Reopen) in different vocabulary; §93 allows cancelling tasks; §66–§72 define a phase lifecycle; §76 an RC lifecycle; §109 a rollout lifecycle. The engine is an in-house explicit state machine (ADR-0001). A decision is needed on how many enums exist and how bugs map.

## Decision

**D-1 One `WorkItemState` enum for Epic/Feature/Story/Task/Bug**, values: `IDEA, DISCOVERY, DESIGN, READY, BLOCKED, IMPLEMENTING, READY_FOR_REVIEW, LEAD_DEV_REVIEW, INTEGRATION, QC, REWORK, PHASE_REVIEW, USER_GATE, COMPLETE, CANCELLED`. §53's `REVIEW` is represented by the §61 pair and is not a separate value.

**D-2 Bug lifecycle maps onto the same enum** (§64): Triage = `DISCOVERY`, Assigned = `READY`, Fix = `IMPLEMENTING`, Review = `READY_FOR_REVIEW`/`LEAD_DEV_REVIEW`, (integration) = `INTEGRATION`, Re-test = `QC`, Close = `COMPLETE`, Reopen = `REWORK`, Won't-fix = `CANCELLED` (requires a QUALITY decision, §10.8). Bug-specific data (`severity`, `reopen_count`, `reproduction`, …) lives on the `Bug` model, not in states.

**D-3 Separate enums for other lifecycles:** `PhaseState` (§66–§72), `ReleaseCandidateState` (§76), `DebateState` (§46), `RolloutStage` (§109), `AgentRunState` (runtime). They are different aggregates with different authorities (user vs QC vs kernel).

**D-4 One `StateMachine` engine, several `TransitionTable`s.** Tables `feature_workflow`, `story_workflow`, `bug_workflow`, `phase_workflow`, `debate_workflow`, `rc_workflow`, `rollout_workflow` (`INTERFACES.md` §3) are data (`BehaviorVersion kind=WORKFLOW`) loaded from `walk/workflow/tables/<name>.yaml`; guards are named Python callables registered in `walk.workflow.guards`. Adding or changing a transition is a workflow improvement (§104 MEDIUM/HIGH), never a code edit inside an agent run.

**D-5 `BLOCKED` remembers the previous state** in the transition payload (`resume_state`), and `unblock` returns there.

**D-6 Phase-level projection states** (`PHASE_REVIEW`, `USER_GATE`) exist on features only as projections of the phase's state for dashboards; authority is `Phase.state`.

## Alternatives

- **Separate `BugState` enum:** rejected — duplicates review/QC/rework semantics, doubles guards and provider status maps; the single enum keeps Jira mapping one table.
- **Keep §53 `REVIEW` as an alias state:** rejected — an unreachable enum member is a trap for implementers and dashboards.
- **Hard-code transitions in Python:** rejected — §105/§109 require versioned, data-driven workflows.

## Consequences

- Jira status map (ADR-0005) has 15 entries covering all kinds.
- `work_items.state` is indexable uniformly; §87 progress charts group by one enum.
- Guards carry kind-specific logic (e.g. `root_cause_section_present` only in `bug_workflow`).

## Related requirements

§53, §58, §61, §64, §66–§72, §76, §93, §105, §109, §131, §139 "exact workflow engine technology".
