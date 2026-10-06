# ADR-0016 — Built-in Hook Implementations Live in `walk.orchestrator`

**Status:** Accepted
**Date:** 2026-10-06
**Deciders:** System architect (raised by the E02/E03/E07/E08 story planners)
**Related requirements:** §32, §41, §22, §137 (Inv. 1); ADR-0009 D-7, D-10, D-11

## Context

`ARCHITECTURE.md` §2.2 places `walk.hooks` in L2 directly after `skills`: it may import only `common`, `persistence`, `telemetry` and `workflow`. The MUST attachments of `ARCHITECTURE.md` §4.1, however, call services far above that line:

| Attachment (story) | Needs |
|---|---|
| pause / handoff / final checkpoint, budget block, cancel cleanup (E02-S08) | `runtime.CheckpointManager`, `runtime.AgentExecutor` |
| `ensure_branch`, work-provider sync, bug create, build/test evidence (E02-S08, E03-S08, E03-S11, E03-S14) | `integrations` (`GitProvider`, `WorkProvider`, `IntegrationManager`) |
| freshness check, index update, phase baseline (E02-S08, E07-S02) | `memory` |
| fix-loop escalation, phase review package, retrospective, gate observation (E03-S16, E07-S03/S05/S08) | `orchestrator`, `improvement`, `permissions`, `budgets` |

E02-S08 planned these callables in `src/walk/hooks/builtins.py`, which would make `walk.hooks` import `runtime`, `integrations`, `memory`, `improvement` and `orchestrator` — a layering violation that `import-linter` (ADR-0009 D-10) rejects and that creates cycles (`runtime` imports `hooks` to fire hooks). E01-S29 additionally calls `HookManager.register_builtins()` from `Orchestrator.start()`, while E02-S08 calls it from the composition root; a second call raises `ConfigError`, so the two stories also disagree on the call site.

## Decision

**D-1 Split registry from implementations.** `walk.hooks` (L2) is the registry and dispatcher only: `HookName`, `Hook`, `HookContext`, `HookResult`, `HookCallable`, `HookManager.register(hook, fn)`, `fire`, `hooks_for`, `load_project_hooks`. It never imports a built-in callable.

**D-2 Built-in callables live in `walk.orchestrator.builtin_hooks`** (`src/walk/orchestrator/builtin_hooks.py`, L4). It owns `BuiltinHookDeps`, `builtin_hooks(deps)` and `register_builtins(manager, deps)`. L4 may import every lower package; the module still imports only `protocols`/`models` of other packages (`ARCHITECTURE.md` §1.3), so `BuiltinHookDeps` stays protocol-typed.

```python
# src/walk/orchestrator/builtin_hooks.py
class BuiltinHookDeps(WalkModel):
    """Protocol-typed service handles (arbitrary_types_allowed); stories add fields additively."""

    hooks: HookManager
    checkpoints: CheckpointManager
    memory: MemoryManager
    git: GitProvider
    executor: AgentExecutor
    budgets: BudgetManager
    permissions: PermissionManager
    telemetry: TelemetryManager


def builtin_hooks(deps: BuiltinHookDeps) -> list[tuple[Hook, HookCallable]]: ...
def register_builtins(manager: HookManager, deps: BuiltinHookDeps) -> None: ...
```

**D-3 One call site: the composition root.** `walk.cli.composition.build_kernel()` calls `register_builtins(hook_manager, deps)` exactly once, after every service exists and before `.ai/agents/hooks.yaml` is loaded (so the "project hook may not replace a required builtin" check of E01-S07 sees the builtins). `build_kernel()` runs before `Orchestrator.start()`, so builtins are registered before recovery (`ARCHITECTURE.md` §3.4 step 4). `HookManager.register_builtins()` is removed from the `HookManager` protocol; `Orchestrator.start()` does not register hooks. A second `register_builtins` call fails through `register`'s duplicate-id check (`ConfigError`).

**D-4 Plugins.** ADR-0009 D-11 `walk.hooks` entry points yield `(Hook, HookCallable)` pairs and are registered by the composition root through the same `HookManager.register` call, after the kernel builtins.

**D-5 Tests stay where they are.** Test modules (`tests/hooks/test_builtins*.py`) keep their paths and node ids; tests are not subject to the import table.

## Alternatives considered

- **Declare `hooks/builtins.py` a composition-level exception** — rejected: it breaks the "row may import only columns to its left" rule that makes §2.2 cycle-free by construction, needs an `import-linter` ignore list, and `runtime → hooks → runtime` remains a real import cycle.
- **Each package registers its own hooks (distributed registration)** — rejected: most MUST attachments span two or more packages (e.g. `ON_BUDGET_EXHAUSTED` needs checkpoints, executor and permissions), the §4.1 table would be scattered across a dozen modules, and the E02-R01 "every row accounted for" check gets harder.
- **Put the callables in `walk.cli.composition`** — rejected: `cli` is wiring only; hook behaviour would become untestable without importing the CLI.
- **Inject a builtin provider into `DefaultHookManager` and keep `register_builtins()` on the protocol** — rejected: adds an indirection whose only purpose is to keep an old method name; the composition root already owns construction order.

## Consequences

- `ARCHITECTURE.md` §2.2 is unchanged (no exception needed); §1.2 (`walk.hooks`, `walk.orchestrator` rows), §3.4 step 4 and §4.1 name the new module.
- `INTERFACES.md` §1.11: `HookManager.register(hook, fn=None)`; `register_builtins()` removed.
- Stories: every Files-table row `src/walk/hooks/builtins.py` becomes `src/walk/orchestrator/builtin_hooks.py` (E02-S08 creates it; E03-S07, S08, S09, S11, S14, S16; E04-S04, S05, S07, S12, S13; E07-S02, S03, S05, S08, S09; E08-S07; E09-S02, S03; E10-X01, S01, S02, S07, S08 modify or name it). E01-S07 drops the `register_builtins` no-op; E01-S29 drops the `hooks.register_builtins()` call from `start()`.
- `BuiltinHookDeps` grows with each story (additive fields); the composition root is the only place that constructs it.
