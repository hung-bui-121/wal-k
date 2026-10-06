# ADR-0019 — `walk.budgets` Precedes `walk.effort` in the Import Order

**Status:** Accepted (implementer, autonomy level 0; owner review requested)
**Date:** 2026-10-06
**Deciders:** Implementer of E01-S13
**Related requirements:** §18–§20; ADR-0009 D-10; ADR-0011 D-5; amends ADR-0018 D-1

## Context

`ARCHITECTURE.md` §2.2 ordered L2 as `hooks, workflow, effort, budgets, …`, so `effort` could
not import `budgets`. The effort contract needs it. Both methods of `EffortManager`
(INTERFACES §1.5) take budget headroom as `dict[BudgetDimension, float]`, and resolution step 7
(INTERFACES §5.2) reads `headroom[COST_USD]`. `BudgetDimension` lives in `walk.budgets.models`.

The reverse edge is not needed. `walk.budgets` (E01-S12) imports only `common`, `persistence`,
`telemetry`, `hooks` and `workflow`. `BudgetPolicy` was moved into `budgets` (WBS §3.2) so
that `budgets` would not import `agents`, not `effort`. Every package that imports `effort`
or `budgets` (`tools`, `integrations`, `debate`, `context`, `agents`, `model_router`, `runtime`,
`improvement`, `orchestrator`, `cli`) comes after both of them.

## Decision

**D-1** `budgets` comes before `effort` in the L2 order:
`hooks, workflow, budgets, effort, permissions, tools, skills, integrations, memory, decisions,
debate, context, agents, model_router`.

**D-2** `effort` may import `walk.budgets` (`models`, `protocols`, `errors`). `budgets` still may
not import `effort`. No other cell of the table changes. The table only swaps the two rows and
columns.

## Alternatives considered

- **Move `BudgetDimension` to `walk.common.enums`.** Rejected. It moves a budgets-owned enum
  and touches every importer of `BudgetDimension` in order to remove one edge.
- **Type headroom as `dict[str, float]` in `effort`.** Rejected. It changes the INTERFACES §1.5
  signatures, and dict keys are invariant, so typed callers (`BudgetManager.headroom`) would
  no longer type-check.

## Consequences

- The import-linter contracts generated in E01-S31 must use this order.
- No cycle is introduced. `budgets` imports nothing that comes after `workflow`.
