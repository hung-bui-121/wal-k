# ADR-0020 — The Production Kit Bootstrapper Lives in `walk.orchestrator`

**Status:** Accepted
**Date:** 2026-10-07
**Deciders:** System architect (raised by the E02-S03 implementer)
**Related requirements:** §24, §25, §105, §123, §124; ADR-0002 D-1, ADR-0009 D-10, ADR-0016

## Context

E02-S03 planned `Bootstrapper` in `src/walk/integrations/bootstrap.py`. The class does the following:
- runs the preflight through `IntegrationManager`;
- writes the `project.md` and `constitution.md` skeletons (built by `walk.memory.skeletons`) through `MemoryManager.write`;
- inserts the `projects` row;
- from E02-S04 on, writes version pins from `walk.improvement`.

Later stories extend it further: E03-S10 installs `com.walk.ci` through `walk.integrations.unity`, E03-S11 adds `ci.yaml`, E04-S02 writes `project.md` through `project_context_to_document`, and E04-S11 adds `graphify-out/` to `.gitignore`.

`ARCHITECTURE.md` §2.2 forbids `integrations → memory` and `integrations → improvement`. `memory → integrations` (the `GitProvider` protocol) is allowed, so the first edge would also create a package cycle. Type-checking-only imports count as well (E01-B06). The planned constructor had two more problems: it took `WorkflowRepository` where the `projects` row needs `ProjectRepository`, and it gave no way to resolve the HEAD and branch that `MemoryManager.write(head=, branch=)` requires.

## Decision

**D-1 Placement.** `Bootstrapper`, `BootstrapOptions`, `BootstrapResult` and `NO_COMMIT_SHA` live in `src/walk/orchestrator/bootstrap.py` (L4) and are re-exported from `walk.orchestrator`. The §2.2 orchestrator row allows every lower package, so the import table does not change. As with `builtin_hooks` (ADR-0016), the module imports only `models`/`protocols`/`errors` of other packages, plus `walk.memory.skeletons` (pure document builders owned by `memory`) and `walk.persistence` (infrastructure).

**D-2 Construction.** Only the composition root constructs it, through `walk.cli.composition.open_bootstrapper`, after `cmd_bootstrap` has validated the options. The constructor takes protocol-typed services:

```python
class Bootstrapper:
    def __init__(
        self,
        *,
        integrations: IntegrationManager,
        memory: MemoryManager,
        git: GitProvider,
        database: Database,
        migrations: MigrationRunner,
        projects: ProjectRepository,
        clock: Clock,
        kit_version: str,
    ) -> None: ...
```

`git` is required: it supplies HEAD and branch for `MemoryManager.write`. A repository without commits gives `GitError`, and the bootstrapper then stamps `NO_COMMIT_SHA = "0000000"` and uses the project's default branch.

**D-3 Package data stays with its owner.** Templates of integration configuration (`work-provider.yaml`, `ai.gitignore`, `root.gitignore.fragment`, later `ci.yaml`) stay under `src/walk/integrations/defaults/` and are read as package resources. Document skeletons stay in `walk.memory.skeletons`. Files with an owning writer go through it: `ProjectionLock.write`, later `KernelVersionPins.write`. The kernel permission defaults are never copied into a project: bootstrap writes an empty narrowing `permissions.yaml` (E02-S03 Behavior 9).

**D-4 YAML confinement.** `ARCHITECTURE.md` §2.3 adds `walk/orchestrator/bootstrap.py` to the `yaml` row, for `production-kit.yaml` and the `work-provider.yaml` kind.

**D-5 Tests** move with the module: `tests/orchestrator/test_bootstrap.py`, and E04-S02's `tests/orchestrator/test_bootstrap_project_context.py`.

## Alternatives considered

- **`src/walk/cli/bootstrap.py`, beside the composition root.** Rejected. `cli` is wiring and I/O formatting (§1.3). The bootstrap sequence is kernel behaviour that E03/E04 stories extend, and it must be testable without typer. ADR-0016 rejected the same placement for hook callables.
- **Keep it in `integrations` and inject callables for document and pin writes.** Rejected. Four later stories would each add another untyped callable, and the class would become an orchestration script whose real dependencies are hidden.
- **Split it across packages** (`integrations` writes config, `memory` writes documents, `cli` sequences). Rejected. The §25 step order and the idempotency report (`created_paths`/`unchanged_paths`) need one owner.
- **An `integrations → memory` exception in §2.2.** Rejected. It makes a cycle with `memory → integrations` and breaks the "only columns to the left" rule.

## Consequences

- `ARCHITECTURE.md` §1.2 (orchestrator row) names the bootstrapper; §2.3 `yaml` row gains the module; §2.2 is unchanged.
- E02-S03's Files table, contract and test paths are updated. E02-S04, E03-S10, E03-S11, E04-S02 and E04-S11 modify `src/walk/orchestrator/bootstrap.py` instead of `src/walk/integrations/bootstrap.py`.
- E02-S04 creates `walk.improvement`. `tests/test_import_contracts.py` then treats it as an existing package, so E02-S04 adds its import-linter row contract. `orchestrator → improvement` is allowed.
- WBS.md §6 register gains a row for this placement.
