# ADR-0018 — `walk.hooks` Precedes the Other L2 Packages in the Import Order

**Status:** Accepted (implementer, autonomy level 0; owner review requested)
**Date:** 2026-10-06
**Deciders:** Implementer of E01-S08
**Related requirements:** §32, §53; ADR-0009 D-7, D-10; ADR-0016

## Context

`ARCHITECTURE.md` §2.2 put `hooks` seventh in the L2 order (`workflow, effort, budgets,
permissions, tools, skills, hooks, …`). So `hooks` could import `workflow`, and of the L2
packages only `runtime`, `improvement`, `orchestrator` and `cli` could import `hooks`.

The planned stories need the reverse direction. These services take a `HookManager` in their
constructor and fire hooks:

| Package | Stories |
|---|---|
| `workflow` | E01-S08 (`DefaultWorkflowManager(..., hooks)`); `Transition.hooks: tuple[HookName, ...]` (INTERFACES §1.3); E01-S09 and E01-S11 |
| `budgets` | E01-S12 |
| `effort` | E01-S13 |
| `permissions` | E01-S15 |
| `memory` | E01-S16 |
| `context` | E01-S24 |
| `decisions` | E04-S05 |
| `debate` | E05-S03 |

The composition order of E01-S30 (`persistence → telemetry → hooks → workflow → …`) and the
dependencies of E01-S09 and E01-S12 on E01-S07 assume the same thing. No planned module of
`walk.hooks` imports `walk.workflow` (E01-S07, E02-S09). The implemented package imports only
`common`, `persistence` and `telemetry`.

## Decision

**D-1** `hooks` is the first L2 package in the topological order:
`hooks, workflow, effort, budgets, permissions, tools, skills, integrations, memory, decisions,
debate, context, agents, model_router`.

**D-2** `hooks` may import only `common`, `persistence` and `telemetry`. Every package after it
may import `walk.hooks` (`models`, `protocols`, `errors`), the same way they import
`telemetry`.

**D-3** ADR-0016 still holds. `walk.hooks` is the registry and dispatcher, and the built-in
callables live in `walk.orchestrator.builtin_hooks`.

## Alternatives considered

- **Keep the order and pass callbacks instead of `HookManager`.** Rejected. Ten stories would
  change their constructor contracts, and `Transition.hooks` still needs `HookName`.
- **Use `HookNameStr` from `walk.common` and keep the manager untyped.** Rejected. It loses the
  `HookName` enum validation of transition tables (E01-S09 Behavior 1) and typed injection.
- **Import `walk.hooks` under `TYPE_CHECKING` only.** Rejected. It hides a real dependency
  from import-linter (ADR-0009 D-10).

## Consequences

- The import-linter contracts generated in E01-S31 must use the new order.
- `walk.hooks` can never use workflow types. Hook payloads carry plain JSON (`HookContext.payload`).
- No cycle is introduced, because `hooks` imports only L0/L1 packages.
