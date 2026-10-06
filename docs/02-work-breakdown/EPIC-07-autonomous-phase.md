# EPIC-07 — Autonomous Phase

**Roadmap stage:** §135 Stage 7
**Goal.** One approved phase executes autonomously inside its approved scope (§67) with parallel agents in isolated worktrees (§60, `max_parallel_agents` > 2), stops at the Phase Gate (§68), assembles the `PhaseEvidencePackage` (§69) and a metrics-only retrospective (§115), and lets the user decide GO / REWORK / CHANGE / STOP (§70–§72) — REWORK becoming structured work and CHANGE producing an impact analysis — while the phase survives a kernel crash (§89) and every decision is recorded (§137 Inv. 14). §134 passes.
**Requirements.** §56, §60, §66–§72, §89–§90, §93 (stop phase), §115 (skeleton), §134, §136, §137 (Inv. 7, 14), §140.
**Epic gate.** `tests/e2e/test_e07_gate.py` (§134): the E06 planned phase runs with `max_parallel_agents=3`, all stories complete through QC with one fix loop, `evidence-package.md` and `retrospective.md` are generated, phase enters `USER_GATE`; `walk phase gate --decision REWORK --feedback ...` creates rework work and returns to `ACTIVE`; `GO` completes the phase and starts the next.
**Branching.** Every story uses `story/<ID>-<slug>` + worktree (COMMIT-POLICY §4); merge `--no-ff` after E07-R01.
**Preconditions.** E06-R01 `DONE` with no `BLOCKER` bugfix stories; `main` green. E08 and E09 start only after E07-R01 (WBS §7.1).
**Refine first.** E07-X01 re-validates every Files table below against the `src/walk/` tree as it exists after E06-R01 — E01 (S18–S31), E03 (S06–S20), E05 and E06 stories were planned at index level only when this file was written; paths marked `(verify)` are the ones most likely to move.

## Story index

| ID | Title | Depends on | Effort |
|---|---|---|---|
| E07-X01 | Refine E07 against codebase | E06-R01 | LOW |
| E07-S01 | Scheduler: configurable parallelism and per-role limits | E07-X01, E03-S18 | MEDIUM |
| E07-S02 | Phase start: baseline snapshot and phase budgets | E07-X01, E02-S12 | MEDIUM |
| E07-S03 | `EvidencePackager` and `evidence-package.md` | E07-S02, E01-S06 | HIGH |
| E07-S04 | Phase review request, `walk phase review/evidence` | E07-S03 | MEDIUM |
| E07-S05 | `PhaseGate.decide_phase` GO/STOP and next-phase start | E07-S04 | MEDIUM |
| E07-S06 | REWORK intake | E07-S05, E05-S06 | HIGH |
| E07-S07 | CHANGE intake and `ChangeImpactAnalyzer` | E07-S05, E04-S11 | HIGH |
| E07-S08 | Phase retrospective skeleton | E07-S03, E04-S13 | MEDIUM |
| E07-S09 | Phase report and `ON_PHASE_COMPLETE` | E07-S05 | LOW |
| E07-S10 | Epic gate: §134 phase test (e2e) | E07-S01, E07-S06, E07-S07, E07-S08, E07-S09 | HIGH |
| E07-R01 | Review E07 | E07-S10 | MEDIUM |

## Reading order for implementers

1. `WBS.md` §2–§3 (binding conventions; §3.4 guard registry names and payload keys, §3.5 ledger write points, §3.6 fakes/e2e, §3.9 templates `ANALYSIS`/`RETRO`).
2. ADR-0009 D-4 (scheduler), D-5 (worktrees; containers deferred to Stage 7 — resolved in E07-S01), D-3 (CLI offline commands), ADR-0006 D-2/D-6 (`phase.*` user-only), ADR-0003 D-1/D-6 (`.ai/phases/`, reports), ADR-0002 (checkpoints, resume).
3. `INTERFACES.md` §1.1 (`Orchestrator.start_phase/request_phase_review/decide_phase/pause`, `KernelStatus`), §1.3 (`phase_event`, `gdd_coverage`), §1.6 (`BudgetManager.ensure`, `CostManager.cost_of`), §1.8 (`write`, `write_report`, `approve_artifact`), §1.14 (`EvidenceManager.for_phase`, `TelemetryManager.metrics`), §1.15 (`phase_retrospective`, `observe`), §2.6 (`CodeGraphProvider.impact`), §3.4 (`phase_workflow v1.0` — the authoritative transition table), §4 (PHASE rows of the routing table), §5.1 (scheduler tick), §5.6 (phase gate intake), §6 (`walk phase *`, `walk run --max-parallel`, `walk improvement retro`).
4. `DOMAIN-MODEL.md` §3 (`PhaseState`, `PhaseDecision`, `EvidenceKind`, `CostCategory`, `MemoryDocType.PHASE/EVIDENCE_PACKAGE/RETROSPECTIVE`, `ApprovedArtifactKind.PHASE_BASELINE`), §4.1 (`Phase`, `Project.current_phase_id`), §4.6 (`HookName`, `HookContext`), §4.12 (`RetrospectiveMetrics`), §4.14 (`Retrospective`), §4.15 (`PhaseEvidencePackage`), §6.2 (`phases`, `retrospectives`, `approved_artifacts`, `approval_requests`).
5. `ARCHITECTURE.md` §3.1 (offline `phase gate`), §3.2 (concurrency), §4.1 (`ON_PHASE_*` attachments), §4.3 (`orchestrator.PhaseGate` writes `PHASE_GATE_DECISION`, `USER_OVERRIDE`), §5.3–§5.4 (resume, `report.phase:{phase_id}:{gate_round}`, `schedule:` keys), §7 (Inv. 7, 14), §8 (`.ai/phases/PHASE-01/` layout).
6. `requirements/WAL_K_REQ.md` §66–§72, §89–§90, §93, §115, §134.
7. Existing files named in each story's Files table (E01-S11, E01-S29, E02-S08, E02-S12, E03-S18, E04-S13, E06-S04, E06-S07) and their tests.

Parallel sets (WBS.md §8): `{S01} ∥ {S02→S03→S04→S05}`; after S05: `{S06} ∥ {S07} ∥ {S08} ∥ {S09}` (S08 may start after S03); S10 last.

## `NEW NAME:` items introduced by this epic (to be added to WBS.md §6 by E07-X01)

| Item | Story | Why |
|---|---|---|
| `SchedulerLimits` (`walk.orchestrator.scheduler`), `Scheduler.running_by_role()` | S01 | ADR-0009 D-4 names the limits but no value object carries them |
| ADR-0009 D-5 status note: containers stay deferred after Stage 7 (worktrees sufficient; Unity-in-container re-evaluated in E08) | S01 | ADR text says "deferred to Stage 7"; the decision must be closed in the ADR |
| `policies.yaml` top-level key `phase_budget: {<BudgetDimension>: limit}`; `BuiltinHookDeps.phase_budget_limits`, `.workflow` | S02 | §20 PHASE-scope budgets need limits; `BudgetPolicy` is per role only |
| `PHASE_SECTIONS` (`walk.memory.sections`), `phase_doc_path`, `phase_evidence_dir` (`walk.memory.paths`); hook `builtin.phase_budget` | S02 | `.ai/phases/PHASE-NN.md` (`type: phase`) has no section list in DOMAIN-MODEL §4.7 |
| `EvidencePackager` Protocol placed in `walk.orchestrator.protocols`; `DefaultEvidencePackager` (`walk.orchestrator.evidence_packager`), `render_evidence_package`, `EVIDENCE_PACKAGE_SECTIONS`, `phase_evidence_package_path`; `BuiltinHookDeps.packager`, `.evidence`, `.costs_reader` | S03 | ARCHITECTURE §1.2 names `EvidencePackager` without a protocol or module |
| Payload keys consumed by the E01-S11 phase guards (`previous_phase_complete_or_first`, `scope_non_empty`, `kit_validated`, `all_scope_features_terminal`, `evidence_package_written`, `retrospective_written`, `feedback_non_empty`, `rework_work_items_created`, `impact_analysis_evidence_present`, `approval_user`): `previous_phase_state`, `scope_epic_ids`, `kit_validated`, `scope_feature_states`, `evidence_package_written`, `retrospective_written`, `feedback`, `rework_task_ids`, `change_plan_evidence_id`, `approval_state` — now produced by the kernel instead of test payloads (WBS §3.4 table extension) | S02, S04–S07 | E01-S11 registered the guards payload-based; the producers did not exist |
| `DefaultOrchestrator.auto_request_review()` called from `tick()`; `walk phase review --force` | S04 | §68 autonomous stop needs a kernel trigger; INTERFACES §3.4 "USER force" has no CLI flag |
| `CommandConsumer` command names `phase.review`, `phase.gate`, `phase.stop` | S04, S05 | ADR-0009 D-3 IPC has no command catalogue |
| `PhaseGate` Protocol (`walk.orchestrator.protocols`), `DefaultPhaseGate` (`walk.orchestrator.phase_gate`); `walk phase stop ID --reason TEXT`; hook `builtin.gate_decision_observe` | S05 | ARCHITECTURE §4.3 names `PhaseGate` as a write point without a contract; §93 Stop Phase has no CLI row in INTERFACES §6 |
| `REWORK_LABELS`, `DefaultPhaseGate.rework_intake()`, `DefaultPhaseGate.on_intake_completed()`; `PLAN.md.j2` block `rework_intake` | S06 | §71 categories as data; intake completion callback has no owner |
| `ChangeImpact` model, `ChangeImpactAnalyzer` concrete class (`walk.orchestrator.change_impact`); `ApprovalRequest.kind == "CHANGE_PLAN"`; change-plan evidence file `change-plan-<gate_round>.md` | S07 | ARCHITECTURE §1.2 names the analyzer; §72 list needs a typed result; INTERFACES §5.6 "ChangePlan evidence" has no shape |
| `RetrospectiveRepository`, `RETROSPECTIVE_SECTIONS`, `retrospective_path`; hook `builtin.phase_retrospective`; `DefaultImprovementManager.phase_retrospective` top-bottleneck/top-defect rules | S08 | §115 figures need deterministic definitions; `retrospectives` table has no repository |
| `render_phase_report`, `PHASE_REPORT_SECTIONS` (`walk.orchestrator.phase_report`); `DefaultMemoryManager.write_report` (basic form, extended by E09-S02); hook `builtin.phase_complete_report` | S09 | ARCHITECTURE §4.1 MUST attachment has no renderer before E09's `ReportQuery` |
| `e07_scenario` fixture, `E07Scenario` (`tests/e2e/conftest.py`) | S10 | Gate fixture reused by E08/E09 gates |

---

### E07-X01 — Refine E07 against codebase

**Status:** TODO
**Type:** docs
**Requirements:** §66–§72, §134, §135
**Depends on:** E06-R01
**Effort:** LOW   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
Every E07 story's Files table, interface references and dependencies are re-validated against the `src/walk/` tree and `INTERFACES.md` as they exist after E06-R01, and the corrected epic file is committed before any E07 story starts (WBS §1 `X` task, §2 rule 3).

#### Scope
- In: this file (E07-S01…S10, R01), WBS §5 rows for E07, WBS §6 register additions from the table above.
- Out: renaming, renumbering, adding or dropping stories (WBS §1: IDs are fixed); any source change.

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-07-autonomous-phase.md` | modify | — |
| `docs/02-work-breakdown/WBS.md` | modify | — (§5 status rows for E07, §6 register rows) |

#### Interface contract
No code. Procedure:
1. For every row of every Files table in this file: `create` paths must not exist; `modify` paths must exist (or be created by an earlier story in this file); every "Public symbols" entry on a `modify` row must already be defined in that file (grep) or be new in this story.
2. For every `INTERFACES.md §x.y` / `DOMAIN-MODEL.md §x.y` reference: the section exists and still defines the referenced names; in particular `phase_workflow v1.0` (§3.4) still has the 13 rows and guard names the E01-S11 story registered (`src/walk/workflow/tables/phase_workflow.yaml`).
3. Every `Depends on` ID is `DONE` in WBS §5 (E06-R01, E03-S18, E02-S12, E01-S06, E05-S06, E04-S11, E04-S13) or belongs to this epic.
4. Every `(verify)` marker is resolved (kept or path corrected) and removed. Known hotspots: `src/walk/orchestrator/{models,protocols,router,scheduler,service,commands}.py` (E01-S29/S30, E03-S07/S18), `src/walk/cli/cmd_phase.py` (E01-S11, E06-S04), `src/walk/hooks/builtins.py` (E02-S08 → E04 → E06), `src/walk/improvement/service.py` (E04-S13), `src/walk/agents/templates/{PLAN,ANALYSIS}.md.j2` (E01-S18, E03-S06, E04-S14), `tests/e2e/conftest.py` fixtures `e03_scenario`/`e04_scenario`/`e06_scenario`, `tests/fakes/fake_unity_provider.py` (E03-S10).
5. Reconcile the §3.9 note "E07 enriches `ANALYSIS`/`RETRO`": `ANALYSIS.md.j2` is enriched by E07-S07; `RETRO.md.j2` is left for E10-S07 (narrative) — record the split in WBS §3.9 if the architect agrees, otherwise set E07-S08 to also touch `RETRO.md.j2`.

#### Behavior
1. Corrections are made in place; no story text is removed, only paths, symbol names, references and `Notes` are corrected.
2. New public names discovered during refinement are added to the `NEW NAME:` table above and to WBS §6.
3. Where a dependency is not `DONE`, the dependent story is set `BLOCKED` with the reason (IMPLEMENTATION-PROTOCOL §1.2) instead of being rewritten.
4. The refine commit contains only the two documentation files.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given every Files table path in this file When checked against `src/walk/` and `tests/` Then each `modify` path exists and each `create` path does not exist or is created by an earlier E07 story | manual checklist recorded in this story's Evidence |
| 2 | Given every `INTERFACES.md`/`DOMAIN-MODEL.md` reference in this file When opened Then the section exists and defines the named symbols | manual checklist recorded in this story's Evidence |
| 3 | Given WBS §5 When E07 dependencies are read Then every dependency outside E07 is `DONE` or the dependent story is marked `BLOCKED` with a reason | manual checklist recorded in this story's Evidence |
| 4 | Given the corrected file When `py -3 scripts/validate_wbs.py` runs Then no error mentions an `E07-` ID | gate output in Evidence |

#### Evidence required
- Checklist per story (ID → paths checked → corrections made).
- `scripts/validate_wbs.py` output.

#### Notes
- WBS §2 rule 3; IMPLEMENTATION-PROTOCOL §1.2 (Definition of Ready).
- The E01-S11 guard list is authoritative for guard registry names; E07 stories only add payload producers (see `NEW NAME:` table).
- Commit subject: `docs: refine epic 07 stories (E07-X01)`.

#### Evidence (filled by implementer)
_pending_

---

### E07-S01 — Scheduler: configurable parallelism and per-role limits

**Status:** TODO
**Type:** feat
**Requirements:** §56, §60, §67, §89, §90, §137 (Inv. 4, 7)
**Depends on:** E07-X01, E03-S18
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The scheduler admits up to a configurable `max_parallel_agents` (> 2) concurrent runs, each in its own worktree, while honouring per-role `RuntimePolicy.max_parallel_runs`, `TaskRouter.can_run_parallel`, phase scope and the scheduling idempotency key — and the admission state is observable (`KernelStatus.active_runs`, `running_by_role`) and survives a kernel restart without double-scheduling.

#### Scope
- In: `SchedulerLimits`, limits wiring from `KernelSettings.max_parallel_agents` / `walk run --max-parallel`, per-role counting, admission order under contention, restart idempotency, ADR-0009 D-5 containers decision closed.
- Out: new routing rows (E07-S06/S07 add PHASE rows); budget allocation per phase (E07-S02); any container/sandbox technology change (none — see Notes).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/scheduler.py` | modify | `SchedulerLimits`, `Scheduler.limits`, `Scheduler.running_by_role` `(verify: created by E01-S29, extended by E03-S18)` |
| `src/walk/orchestrator/service.py` | modify | — (`DefaultOrchestrator.tick` passes `limits`; `status().active_runs` sorted by `id`) |
| `src/walk/orchestrator/__init__.py` | modify | re-export `SchedulerLimits` |
| `src/walk/cli/composition.py` | modify | — (`KernelSettings.max_parallel_agents` default 2, validated `1 ≤ n ≤ 16`; builds `SchedulerLimits`) |
| `src/walk/cli/cmd_run.py` | modify | — (`--max-parallel N` maps to `KernelSettings.max_parallel_agents`) `(verify: created by E01-S30)` |
| `docs/01-architecture/adr/ADR-0009-runtime-topology-and-open-questions.md` | modify | — (D-5 status note, see Notes) |
| `tests/orchestrator/test_scheduler_parallel.py` | create | — |
| `tests/orchestrator/test_scheduler_restart.py` | create | — |
| `tests/cli/test_cmd_run_max_parallel.py` | create | — |

#### Interface contract
```python
# src/walk/orchestrator/scheduler.py
class SchedulerLimits(FrozenModel):
    max_parallel_agents: int = Field(default=2, ge=1, le=16, description="ADR-0009 D-4 global cap; §60")
    per_role: dict[AgentRole, int] = Field(default_factory=dict, description="RuntimePolicy.max_parallel_runs per role; missing role → 1")

class Scheduler:  # existing (E01-S29/E03-S18); additions
    limits: SchedulerLimits
    def running_by_role(self) -> dict[AgentRole, int]:
        """Count of AgentExecutor.running() runs per role (RUNNING or PAUSED_FOR_APPROVAL)."""
```
Algorithm: INTERFACES §5.1 unchanged; step 4 uses `limits.max_parallel_agents`, step 6 uses `limits.per_role.get(role, 1)` and `TaskRouter.can_run_parallel(item, each running item)`, step 7 the key `schedule:{item.id}:{item.state}:{item.state_version}` (ARCHITECTURE §5.4). `per_role` is built at composition from `AgentManager.load_runtime_policy(role).max_parallel_runs` for every `AgentManager.list_roles()`.

#### Behavior
1. With `max_parallel_agents = 3` and five ready stories on different features, one `tick()` starts exactly 3 runs; the next `tick()` after one completes starts 1 more; `len(executor.running()) ≤ 3` holds after every tick.
2. Each admitted run has its own worktree `<repo>/.walk/worktrees/<run_id>/` created by `SandboxManager.create` (E01-S25); no two running runs share a worktree path or a branch.
3. A role whose `per_role` limit is reached is skipped for that tick even when global capacity remains; other roles are still admitted in the same tick (no head-of-line blocking).
4. `can_run_parallel(a, b) == False` for a candidate against any running item (same feature with overlapping `relevant_files`, dependency edge, same branch) skips the candidate; the skip is counted via `TelemetryManager.counter("scheduler.skipped", reason=...)` with reasons `global_limit`, `role_limit`, `parallel_conflict`, `idempotent`, `budget`.
5. Scheduling order within a tick is the INTERFACES §4 order: BLOCKED-resolvable first, bugs by `Severity`, then `priority`, then `created_at`; ties broken by `id` so admission is deterministic.
6. Reviewer roles (`LEAD_DEV` REVIEW, `QC`) are never admitted on a work item whose implementer run is still running (Invariant 4; `ready_items` already excludes such states, re-asserted here).
7. After `Orchestrator.stop(drain=False)` and a restart (ARCHITECTURE §5.3), the first `tick()` does not start a second run for an item whose key `schedule:{id}:{state}:{state_version}` exists; the interrupted run is resumed instead (E01-S28 path).
8. Items outside `Phase.scope_epic_ids` of `project.current_phase_id` are never admitted while the phase is `ACTIVE` (guard `in_phase_scope`, E06-S07; Invariant 7) — asserted end-to-end through `ready_items(phase_id)`.
9. `KernelSettings.max_parallel_agents` outside `[1, 16]` → `ConfigError` at `build_kernel`; `walk run --max-parallel 0` exits 1.
10. `KernelStatus.active_runs` equals `executor.running()` sorted by `id` after every tick.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `max_parallel_agents=3` and 5 ready stories on 5 features When `tick()` Then 3 runs started, 3 distinct worktree paths exist | `tests/orchestrator/test_scheduler_parallel.py::test_admits_up_to_global_limit_with_distinct_worktrees` |
| 2 | Given 3 running When one completes and `tick()` Then exactly 1 new run and `running` is 3 | `tests/orchestrator/test_scheduler_parallel.py::test_refills_after_completion` |
| 3 | Given `per_role[SENIOR_DEV]=1`, 2 ready stories and 1 ready bug in `DISCOVERY` (LEAD_DEV TRIAGE) When `tick()` Then 1 SENIOR_DEV run + 1 LEAD_DEV run | `tests/orchestrator/test_scheduler_parallel.py::test_role_limit_does_not_block_other_roles` |
| 4 | Given two ready stories on the same feature with overlapping `relevant_files` When `tick()` Then one run and counter `scheduler.skipped{reason=parallel_conflict}` == 1 | `tests/orchestrator/test_scheduler_parallel.py::test_parallel_conflict_skipped` |
| 5 | Given items with mixed priority/created_at When `tick()` with capacity 2 Then the two admitted ids follow the §4 order deterministically across two fresh kernels | `tests/orchestrator/test_scheduler_parallel.py::test_admission_order_deterministic` |
| 6 | Given a story whose implementer run is RUNNING When `ready_items` is read Then the story is absent and no reviewer run is admitted | `tests/orchestrator/test_scheduler_parallel.py::test_reviewer_never_concurrent_with_implementer` |
| 7 | Given a story outside the active phase scope When `tick()` Then it is not admitted and `in_phase_scope` rejection is the reason | `tests/orchestrator/test_scheduler_parallel.py::test_out_of_scope_item_not_admitted` |
| 8 | Given 3 running runs When the kernel is stopped without drain and rebuilt Then the first `tick()` starts 0 new runs for those items and 3 `RECOVERY_RESUMED` events exist | `tests/orchestrator/test_scheduler_restart.py::test_restart_resumes_without_double_scheduling` |
| 9 | Given `max_parallel_agents=17` When `build_kernel` Then `ConfigError` | `tests/orchestrator/test_scheduler_restart.py::test_limits_out_of_range_rejected` |
| 10 | Given `walk run --max-parallel 3 --once` on a repo with 4 ready items Then exit 0 and `walk status --json` shows 3 `active_runs` | `tests/cli/test_cmd_run_max_parallel.py::test_run_once_respects_max_parallel` |
| 11 | Given `walk run --max-parallel 0` Then exit 1 | `tests/cli/test_cmd_run_max_parallel.py::test_run_rejects_zero_parallel` |

#### Evidence required
- Quality gate output (ruff ok, mypy ok, N passed, coverage %).
- Demo: `walk run --max-parallel 3 --once` on the E06 gate fixture repo, then `walk status --json` → `active_runs` has 3 entries; `ls .walk/worktrees/` → three run directories.

#### Notes
- ADR-0009 D-4 (limits), D-5 (worktrees). This story closes the D-5 deferral: append to ADR-0009 D-5 a status note "Stage 7 (E07-S01): containers not adopted; worktree + provider sandbox + `BoundaryAuditor` remain the isolation mechanism up to 16 parallel agents; Unity-in-container re-evaluated with E08-S08". No new ADR is needed because no mechanism changes.
- Fakes only (`FakeModelAdapter` scripted to run until released by the test); no wall clock — use `FakeClock`.
- `NEW NAME:` `SchedulerLimits`, `Scheduler.running_by_role`, counter `scheduler.skipped`, ADR-0009 D-5 status note.
- Commit subject: `feat: add configurable scheduler parallelism and per-role limits (E07-S01)`.

#### Evidence (filled by implementer)
_pending_

---

### E07-S02 — Phase start: baseline snapshot and phase budgets

**Status:** TODO
**Type:** feat
**Requirements:** §66, §67, §68, §20, §33 (phase baseline), §90, §137 (Inv. 7, 10)
**Depends on:** E07-X01, E02-S12
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
`Orchestrator.start_phase` is a complete kernel step: the `PLANNED → ACTIVE` transition is guarded with real payload (previous phase complete, non-empty scope, kit validated), the `ON_PHASE_START` MUST hook writes a full `PHASE_BASELINE` approved artifact (scope ids, HEAD, GDD coverage, approved-artifact ids), the default hook allocates PHASE-scope budgets, `.ai/phases/PHASE-NN.md` exists as a `type: phase` document, and `projects.current_phase_id` points at the active phase.

#### Scope
- In: `start_phase` payload production, baseline content, `builtin.phase_budget`, `PHASE_SECTIONS` + phase document, `Phase.started_at/baseline_artifact_id/budget_id` persistence, `walk phase start` completing the step offline.
- Out: evidence package (E07-S03); review request (E07-S04); gate decisions and next-phase chaining (E07-S05); `walk phase plan` (E06-S04).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/service.py` | modify | `DefaultOrchestrator.start_phase` |
| `src/walk/workflow/service.py` | modify | `DefaultWorkflowManager.update_phase` `(verify: E01-S11 may expose `PhaseRepository.save` instead)` |
| `src/walk/workflow/repository.py` | modify | `PhaseRepository.save` `(verify)` |
| `src/walk/hooks/builtins.py` | modify | `phase_baseline` (content completed), `phase_budget_allocate`; `BuiltinHookDeps.workflow`, `BuiltinHookDeps.phase_budget_limits` |
| `src/walk/agents/policy_file.py` | modify | `PoliciesFile.phase_budget` `(verify: E01-S17 policies loader module name)` |
| `src/walk/agents/defaults/policies.yaml` | modify | — (`phase_budget: {COST_USD: 200.0, EXECUTION_TIME_S: 86400}`) |
| `src/walk/memory/sections.py` | modify | `PHASE_SECTIONS` |
| `src/walk/memory/paths.py` | modify | `phase_doc_path`, `phase_evidence_dir` |
| `src/walk/memory/skeletons.py` | modify | `phase_skeleton` |
| `src/walk/cli/cmd_phase.py` | modify | — (`start` calls `Orchestrator.start_phase` in-process when no daemon; via `CommandClient` otherwise) |
| `src/walk/cli/composition.py` | modify | — (`phase_budget_limits` from policies into `BuiltinHookDeps`) |
| `tests/orchestrator/test_start_phase.py` | create | — |
| `tests/hooks/test_builtins_phase_start.py` | create | — |
| `tests/memory/test_phase_document.py` | create | — |

#### Interface contract
```python
# DefaultOrchestrator (INTERFACES §1.1)
async def start_phase(self, phase_id: PhaseId) -> Phase:
    """PLANNED → ACTIVE via WorkflowManager.phase_event(phase_id, "start", ctx) with ctx.payload =
    {"previous_phase_state": <state of phase ordinal-1 or None>, "scope_epic_ids": phase.scope_epic_ids,
     "kit_validated": <EnvironmentManifest from .ai/project/environment.yaml has no MISSING required component>};
    after commit: Phase.started_at = clock.now(); projects.current_phase_id = phase_id; MemoryManager.write(phase document);
    returns the persisted Phase (baseline_artifact_id and budget_id set by the hooks below)."""

# src/walk/hooks/builtins.py
# ON_PHASE_START  builtin.phase_baseline   prio 10  required=True   (exists since E02-S08; content completed here)
#   payload manifest written as the APR payload file `baseline.yaml`:
#     {phase_id, gate_round, head: <repo HEAD sha>, scope_epic_ids, scope_work_item_ids (all descendants of scope epics),
#      gdd_coverage: WorkflowManager.gdd_coverage(project_key), approved_artifact_ids: <all APPROVED artifacts>, created_at}
#   → MemoryManager.approve_artifact(ApprovedArtifact(kind=PHASE_BASELINE, scope=phase_id, title=f"Baseline {phase_id} r{gate_round}",
#       supersedes=<previous baseline of the phase if any>), actor=Actor(role=KERNEL)); Phase.baseline_artifact_id updated.
# ON_PHASE_START  builtin.phase_budget     prio 60  required=False
#   → BudgetManager.ensure(BudgetScope.PHASE, phase_id, policy=None, limits=deps.phase_budget_limits); Phase.budget_id = first Budget.id

class BuiltinHookDeps(WalkModel):   # additions
    workflow: WorkflowManager
    phase_budget_limits: dict[BudgetDimension, float]

# src/walk/memory/sections.py
PHASE_SECTIONS = ("Goal", "Scope", "Exit Criteria", "Status", "Gate History", "Known Limitations", "Risks")
# src/walk/memory/paths.py
def phase_doc_path(phase_id: PhaseId) -> str: ...        # "phases/<PHASE-id>.md"
def phase_evidence_dir(phase_id: PhaseId) -> str: ...    # "phases/<PHASE-id>/evidence"
```
`policies.yaml` gains a top-level `phase_budget` mapping (`BudgetDimension` → limit) next to `roles:`; absent → kernel default above.

#### Behavior
1. `start_phase` on a phase whose predecessor (ordinal − 1) is not `COMPLETE` raises `GuardRejected` (`previous_phase_complete_or_first`); the first phase (ordinal 1) passes with `previous_phase_state=None`.
2. Empty `scope_epic_ids` → `GuardRejected` (`scope_non_empty`); a missing or `MISSING`-component `environment.yaml` → `GuardRejected` (`kit_validated`).
3. On success exactly one `PHASE_TRANSITION` ledger event (write point `StateMachine.commit`, WBS §3.5) and one `ARTIFACT_APPROVED` event exist; the baseline payload hash verifies via `MemoryManager.verify_approved_artifacts()` (Invariant 10).
4. The baseline manifest lists every work item below the scope epics at start time; re-entering `ACTIVE` from `REWORK` (E07-S06) fires `ON_PHASE_START` again and produces a new baseline with `supersedes` = previous id and `gate_round` from the phase.
5. `builtin.phase_budget` is idempotent (`BudgetManager.ensure` creates missing rows only); a second `ON_PHASE_START` for the same phase does not create duplicate budgets; the Budget rows carry `scope=PHASE, scope_id=phase_id` and are returned by `BudgetManager.applicable(subject with phase_id)` for every run in the phase.
6. The phase document `.ai/phases/PHASE-NN.md` has `type: phase`, `id == phase_id`, the seven `PHASE_SECTIONS` in order; `Goal`/`Scope`/`Exit Criteria` filled from `Phase`; `Status` = `ACTIVE since <iso>`; written via `MemoryManager.write` (ADR-0003 D-4) so `memory_index` has the row.
7. `projects.current_phase_id` is updated in the same transaction as the transition; `KernelStatus.current_phase` reflects it on the next `status()`.
8. `walk phase start PHASE-01` without a daemon performs the full step in-process (ARCHITECTURE §3.1 offline list) and prints `PHASE-01 ACTIVE baseline=APR-NNNN budget=BUD-…`; with a daemon it goes through `CommandClient` (`phase.start`, already present `(verify)`); guard rejection exits 2.
9. `phase_budget` hook failures are `LOG_AND_CONTINUE` (default attachment). `phase_baseline` is `FAIL_CLOSED`: hooks fire after the transition commits (INTERFACES §1.3 `raise_event`), so on baseline failure the phase row is already `ACTIVE`, `start_phase` raises `HookFailed`, and a retry of `start_phase` returns the phase with `baseline_artifact_id` still `None` and re-fires only the hooks (no second `PHASE_TRANSITION`).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given PHASE-01 PLANNED with 2 scope epics and a READY manifest When `start_phase` Then state `ACTIVE`, `started_at` set, `current_phase_id == PHASE-01` | `tests/orchestrator/test_start_phase.py::test_start_first_phase_activates` |
| 2 | Given PHASE-02 PLANNED and PHASE-01 ACTIVE When `start_phase(PHASE-02)` Then `GuardRejected` naming `previous_phase_complete_or_first` | `tests/orchestrator/test_start_phase.py::test_start_requires_previous_complete` |
| 3 | Given a phase with empty scope When `start_phase` Then `GuardRejected` naming `scope_non_empty` | `tests/orchestrator/test_start_phase.py::test_start_requires_scope` |
| 4 | Given `environment.yaml` with a MISSING required component When `start_phase` Then `GuardRejected` naming `kit_validated` | `tests/orchestrator/test_start_phase.py::test_start_requires_validated_kit` |
| 5 | Given a successful start Then `.ai/phases/PHASE-01.md` exists with `type: phase` and `PHASE_SECTIONS` in order and a `memory_index` row | `tests/memory/test_phase_document.py::test_phase_document_written_with_sections` |
| 6 | Given a successful start Then one `ARTIFACT_APPROVED` event, artifact kind `PHASE_BASELINE`, `baseline.yaml` lists all scope descendants and `gdd_coverage`, and `verify_approved_artifacts()` returns `[]` | `tests/hooks/test_builtins_phase_start.py::test_phase_baseline_manifest_complete_and_verified` |
| 7 | Given `ON_PHASE_START` fired twice for the same phase Then two baseline artifacts, second `supersedes` the first | `tests/hooks/test_builtins_phase_start.py::test_second_baseline_supersedes_first` |
| 8 | Given `phase_budget_limits={COST_USD: 200}` When `ON_PHASE_START` fires twice Then exactly one PHASE budget row with limit 200 and `Phase.budget_id` set | `tests/hooks/test_builtins_phase_start.py::test_phase_budget_allocated_once` |
| 9 | Given a run in the phase When `BudgetManager.applicable(subject)` Then the PHASE budget is included | `tests/hooks/test_builtins_phase_start.py::test_phase_budget_applies_to_runs` |
| 10 | Given `BudgetManager.ensure` raising When `ON_PHASE_START` fires Then hook result `FAILED`, phase stays `ACTIVE`, baseline still written | `tests/hooks/test_builtins_phase_start.py::test_phase_budget_failure_logged_and_continues` |
| 11 | Given `walk phase start PHASE-01` without daemon Then exit 0 and output contains `ACTIVE` and `baseline=APR-` | `tests/orchestrator/test_start_phase.py::test_cli_phase_start_offline` |
| 12 | Given `walk phase start PHASE-02` while PHASE-01 is ACTIVE Then exit 2 | `tests/orchestrator/test_start_phase.py::test_cli_phase_start_guard_exit_2` |
| 13 | Given `approve_artifact` raising on the first attempt When `start_phase` Then `HookFailed`, phase `ACTIVE`, one `PHASE_TRANSITION`; a second `start_phase` re-fires the hooks, sets `baseline_artifact_id`, still one `PHASE_TRANSITION` | `tests/orchestrator/test_start_phase.py::test_baseline_failure_raises_and_retry_refires_hooks` |

#### Evidence required
- Quality gate output.
- Demo: on the E06 gate fixture repo `walk phase start PHASE-01` → `PHASE-01 ACTIVE baseline=APR-0001 budget=…`; `walk artifacts list` shows the `PHASE_BASELINE`; `cat .ai/phases/PHASE-01.md | head -20`.

#### Notes
- ARCHITECTURE §4.1 `ON_PHASE_START` row; ADR-0003 D-1 (`phases/`), D-5 (approved payload hashing); E02-S08 created `builtin.phase_baseline` with a minimal manifest — this story completes it in place (same hook id, same priority).
- `hooks` importing `walk.workflow.protocols` is allowed (ARCHITECTURE §2.2 row `hooks`); `BudgetDimension` comes through `BuiltinHookDeps` as data, following the E02-S08 precedent for `budgets`.
- Behavior 9: the transition commits before hooks (INTERFACES §1.3 `raise_event`); do not try to roll back the phase row on hook failure — surface `HookFailed`.
- `NEW NAME:` `policies.yaml` `phase_budget`, `BuiltinHookDeps.workflow/phase_budget_limits`, hook `builtin.phase_budget`, `PHASE_SECTIONS`, `phase_doc_path`, `phase_evidence_dir`, `phase_skeleton`, `DefaultWorkflowManager.update_phase`.
- Commit subject: `feat: complete phase start with baseline snapshot and phase budgets (E07-S02)`.

#### Evidence (filled by implementer)
_pending_

---

### E07-S03 — `EvidencePackager` and `evidence-package.md`

**Status:** TODO
**Type:** feat
**Requirements:** §69, §68, §6.6, §47, §74, §84, §83, §137 (Inv. 9, 14)
**Depends on:** E07-S02, E01-S06
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The §69 Phase Evidence Package is assembled deterministically from persisted facts only (work items, `evidence`, `cost_records`, ledger, GDD coverage, feature contexts) into a `PhaseEvidencePackage` and rendered to `.ai/phases/PHASE-NN/evidence-package.md` by the `ON_PHASE_REVIEW_START` MUST hook, so the user can judge the phase from one document (Inv. 14).

#### Scope
- In: `EvidencePackager` protocol + `DefaultEvidencePackager`, 14-section renderer, `evidence_package` document type, MUST hook, payload key `evidence_package_written`.
- Out: the review-request transition and CLI (E07-S04); retrospective (E07-S08); phase report after GO (E07-S09); §83 report queries (E09).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/models.py` | modify | `PhaseEvidencePackage` (DOMAIN-MODEL §4.15, add `known_limitations_sources: list[str]`) `(verify: created by E01-S29)` |
| `src/walk/orchestrator/protocols.py` | modify | `EvidencePackager` `(verify)` |
| `src/walk/orchestrator/evidence_packager.py` | create | `DefaultEvidencePackager`, `render_evidence_package`, `EVIDENCE_PACKAGE_SECTIONS` |
| `src/walk/orchestrator/__init__.py` | modify | re-exports |
| `src/walk/memory/sections.py` | modify | `EVIDENCE_PACKAGE_SECTIONS` re-exported for `MemoryDocType.EVIDENCE_PACKAGE` section validation |
| `src/walk/memory/paths.py` | modify | `phase_evidence_package_path` |
| `src/walk/hooks/builtins.py` | modify | `phase_review_build_package`; `BuiltinHookDeps.packager`, `BuiltinHookDeps.evidence` |
| `src/walk/cli/composition.py` | modify | — (constructs `DefaultEvidencePackager`, wires deps) |
| `tests/orchestrator/test_evidence_packager.py` | create | — |
| `tests/orchestrator/test_evidence_package_render.py` | create | — |
| `tests/hooks/test_builtins_phase_review.py` | create | — |

#### Interface contract
```python
# src/walk/orchestrator/protocols.py
class EvidencePackager(Protocol):
    """§69. Hosted by walk.orchestrator; called by the ON_PHASE_REVIEW_START MUST hook."""
    async def build(self, phase_id: PhaseId) -> PhaseEvidencePackage:
        """Assemble from persisted state only (no agent run, no .ai narrative except feature-context sections named below)."""
    async def write(self, package: PhaseEvidencePackage, *, actor: Actor, head: Sha, branch: str) -> str:
        """Render + MemoryManager.write(MemoryDocument type=evidence_package, id=f"{phase_id}-EP{gate_round}") at
        phase_evidence_package_path(phase_id). Returns repo-relative path."""

# src/walk/orchestrator/evidence_packager.py
class DefaultEvidencePackager:
    def __init__(self, workflow: WorkflowManager, evidence: EvidenceManager, costs: CostManager, ledger: LedgerManager,
                 memory: MemoryManager, clock: Clock) -> None: ...

EVIDENCE_PACKAGE_SECTIONS = ("GDD Coverage", "Stories Completed", "Open Issues", "Known Limitations", "QC Status", "Automated Tests",
                             "Performance Metrics", "Playable Build", "Gameplay Recording", "Screenshots", "Design Review",
                             "Technical Review", "Risk Summary", "Production Cost")   # §69 order, verbatim

def render_evidence_package(package: PhaseEvidencePackage, titles: dict[WorkItemId, str], evidence: dict[EvidenceId, Evidence]) -> str:
    """One '## <section>' per EVIDENCE_PACKAGE_SECTIONS entry, in order; empty section body = '_none_'."""

# src/walk/memory/paths.py
def phase_evidence_package_path(phase_id: PhaseId) -> str: ...   # "phases/<PHASE-id>/evidence-package.md"

# ON_PHASE_REVIEW_START  builtin.phase_review_build_package  prio 10  required=True
#   package = packager.build(phase_id); path = packager.write(package, actor=KERNEL, head=repo HEAD, branch=default_branch)
#   ctx.payload["evidence_package_written"] = True; ctx.payload["evidence_package_path"] = path
```

#### Behavior
1. Field sources (all read-only queries): `gdd_coverage` ← `WorkflowManager.gdd_coverage(project_key)`; `stories_completed`/`stories_open` ← STORY/TASK descendants of `Phase.scope_epic_ids` split by `state == COMPLETE`; `open_issues` ← BUG items in the phase not in `COMPLETE/CANCELLED`, ordered by `Severity` then id; `qc_status` ← `"passed=<n> rejected=<m> open_bugs=<k>"` from `QC_RESULT` ledger outcomes and open bugs; `automated_tests`/`performance_metrics`/`gameplay_recordings`/`screenshots` ← `EvidenceManager.for_phase(phase_id)` plus `for_item` of every scope descendant, filtered by `EvidenceKind` (`AUTOMATED_TEST`; `PERFORMANCE_METRICS|PROFILER_RESULT|REPRODUCIBLE_BENCHMARK`; `GAMEPLAY_RECORDING`; `SCREENSHOT`); `playable_build` ← `EvidenceManager.strongest` over `BUILD_ARTIFACT`; `design_review`/`technical_review` ← strongest `QC_REPORT` evidence produced by `DESIGN_LEADER` / `LEAD_DEV` respectively (None when absent); `known_limitations` ← the `Known Risks` section lines of every scope feature's `FeatureContext` (ADR-0003 fixed H2) with `known_limitations_sources` listing the feature ids; `risk_summary` ← one line per open item with `risk ∈ {HIGH, CRITICAL}` plus `"<n> open blocker bugs"`; `production_cost` ← `CostManager.cost_of(phase_id=phase_id)`.
2. `gate_round` = `Phase.gate_round + 1` (the round the package is for); `generated_at` = injected `Clock`.
3. `build()` is deterministic: two calls on a frozen DB and clock produce equal `model_dump()`; lists are sorted by id, never by dict order.
4. `build()` never starts an agent run, never reads `agent_runs.json`/`output`, never calls a provider; the only `.ai/` reads are feature contexts via `MemoryManager.read_feature_context` (rule 1).
5. `write()` produces a document with front matter `type: evidence_package`, `id: <PHASE-id>-EP<round>`, `related.work_items` = completed + open stories, `related.evidence` = every evidence id referenced, and the 14 sections in order; written via `MemoryManager.write` (atomic, indexed, `CONTEXT_UPDATED`); overwriting `evidence-package.md` on a later round bumps `version` and keeps the previous round's content retrievable from git only.
6. Rendering: `Stories Completed`/`Open Issues` are tables `id | title | state`; evidence sections are tables `id | kind | uri | produced_at`; `GDD Coverage` is `area | %` (two decimals); `Production Cost` is `category | usd` plus `total`; empty → `_none_`.
7. The MUST hook fails closed on any exception; `package_ready` (E07-S04) cannot pass without `evidence_package_written` in the payload.
8. A phase with no evidence at all still yields a valid package (all evidence lists empty, `playable_build=None`, `qc_status="passed=0 rejected=0 open_bugs=0"`).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a seeded phase (2 epics, 3 features, 6 stories: 5 COMPLETE, 1 IMPLEMENTING; 1 open BUG severity HIGH) When `build` Then `stories_completed` has 5, `stories_open` 1, `open_issues` 1, `qc_status` counts match ledger `QC_RESULT`s | `tests/orchestrator/test_evidence_packager.py::test_build_collects_work_and_qc_status` |
| 2 | Given evidence of kinds AUTOMATED_TEST ×2, SCREENSHOT ×1, BUILD_ARTIFACT ×2 (different `produced_at`), PROFILER_RESULT ×1 When `build` Then the four lists are filled by kind and `playable_build` is the newest BUILD_ARTIFACT | `tests/orchestrator/test_evidence_packager.py::test_build_sorts_evidence_by_kind_and_picks_strongest_build` |
| 3 | Given a `QC_REPORT` evidence produced by LEAD_DEV and none by DESIGN_LEADER When `build` Then `technical_review` set and `design_review is None` | `tests/orchestrator/test_evidence_packager.py::test_build_reviews_by_producer_role` |
| 4 | Given feature contexts with `Known Risks` lines When `build` Then `known_limitations` equals their union and `known_limitations_sources` lists the feature ids | `tests/orchestrator/test_evidence_packager.py::test_build_known_limitations_from_feature_contexts` |
| 5 | Given cost records in the phase When `build` Then `production_cost == CostManager.cost_of(phase_id)` | `tests/orchestrator/test_evidence_packager.py::test_build_production_cost_matches_cost_manager` |
| 6 | Given the same DB and frozen clock When `build` twice Then equal `model_dump()` | `tests/orchestrator/test_evidence_packager.py::test_build_deterministic` |
| 7 | Given an `.ai/features/FEAT-0001.md` with `SENTINEL` outside `Known Risks` and an agent output containing `SENTINEL` When `build` + render Then `SENTINEL` absent | `tests/orchestrator/test_evidence_packager.py::test_build_reads_only_known_risks_section` |
| 8 | Given a phase with no evidence and no bugs When `build` Then a valid package with empty lists and `qc_status == "passed=0 rejected=0 open_bugs=0"` | `tests/orchestrator/test_evidence_packager.py::test_build_empty_phase_valid` |
| 9 | Given a package When `render_evidence_package` Then exactly 14 `## ` headings equal to `EVIDENCE_PACKAGE_SECTIONS` in order and empty sections render `_none_` | `tests/orchestrator/test_evidence_package_render.py::test_render_fourteen_sections_in_order` |
| 10 | Given a package When `write` Then `.ai/phases/PHASE-01/evidence-package.md` has `type: evidence_package`, `id: PHASE-01-EP1`, `related.evidence` complete, and a `memory_index` row | `tests/orchestrator/test_evidence_package_render.py::test_write_document_front_matter_and_index` |
| 11 | Given `write` called for round 1 then round 2 Then one file, `version == 2`, `id` ends `EP2` | `tests/orchestrator/test_evidence_package_render.py::test_write_second_round_bumps_version` |
| 12 | Given `ON_PHASE_REVIEW_START` fired Then the file exists and `ctx.payload["evidence_package_written"] is True` | `tests/hooks/test_builtins_phase_review.py::test_review_start_hook_writes_package` |
| 13 | Given `packager.build` raising When the hook fires Then `HookFailed` and no file | `tests/hooks/test_builtins_phase_review.py::test_review_start_hook_fails_closed` |

#### Evidence required
- Quality gate output.
- Demo: on a fixture DB after the E03 gate scenario, a small script or `walk phase evidence PHASE-01` (available after E07-S04) printing the rendered package; until then, the test transcript of AC 9–10 plus `cat .ai/phases/PHASE-01/evidence-package.md | head -40`.

#### Notes
- DOMAIN-MODEL §4.15 fixes the field list; the only addition is `known_limitations_sources` (record in DOMAIN-MODEL in the same commit). ARCHITECTURE §2.2: orchestrator may import every package, so reading `memory`, `telemetry`, `budgets` protocols here is allowed.
- §83 spirit: the package is a derived document; the kernel, not an agent, writes it. Narrative ("Design Review" prose) is deliberately absent — reviews are evidence references.
- `NEW NAME:` `EvidencePackager` placement, `DefaultEvidencePackager`, `render_evidence_package`, `EVIDENCE_PACKAGE_SECTIONS`, `phase_evidence_package_path`, `PhaseEvidencePackage.known_limitations_sources`, hook `builtin.phase_review_build_package`, `BuiltinHookDeps.packager/evidence`, payload keys `evidence_package_written`, `evidence_package_path`.
- Commit subject: `feat: add evidence packager and phase evidence package document (E07-S03)`.

#### Evidence (filled by implementer)
_pending_

---

### E07-S04 — Phase review request, `walk phase review/evidence`

**Status:** TODO
**Type:** feat
**Requirements:** §68, §69, §67, §93, §90, §137 (Inv. 7, 14)
**Depends on:** E07-S03
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The kernel stops at the phase boundary by itself (§68): when every scope feature is terminal the scheduler requests the phase review, the phase moves `ACTIVE → EVIDENCE_REVIEW → USER_GATE` (`gate_round += 1`) with the evidence package and retrospective guards satisfied, no further work is admitted, and the user can trigger or inspect the review with `walk phase review` / `walk phase evidence`.

#### Scope
- In: `Orchestrator.request_phase_review`, `auto_request_review` in the tick, payload producers for `all_scope_features_terminal`, `evidence_package_written`, `retrospective_written`, `package_ready` event, admission freeze in `USER_GATE`, IPC commands `phase.review`, CLI `review [--force]` / `evidence [--open]`.
- Out: gate decisions (E07-S05); retrospective producer (E07-S08 — this story reads the file's existence only); evidence package content (E07-S03).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/service.py` | modify | `DefaultOrchestrator.request_phase_review`, `DefaultOrchestrator.auto_request_review` |
| `src/walk/orchestrator/scheduler.py` | modify | — (`tick` step 1a: no admission while `phase.state ∉ {ACTIVE}`; calls `auto_request_review` when all scope features terminal) |
| `src/walk/orchestrator/commands.py` | modify | — (command `phase.review` → `request_phase_review`) `(verify: E01-S30 CommandConsumer)` |
| `src/walk/memory/paths.py` | modify | `retrospective_path` |
| `src/walk/cli/cmd_phase.py` | modify | `phase_app` (`review ID [--force]`, `evidence ID [--open] [--json]`) |
| `src/walk/cli/ipc.py` | modify | — (`CommandClient` sends `phase.review`) `(verify)` |
| `tests/orchestrator/test_request_phase_review.py` | create | — |
| `tests/orchestrator/test_scheduler_phase_boundary.py` | create | — |
| `tests/cli/test_cmd_phase_review.py` | create | — |

#### Interface contract
```python
# DefaultOrchestrator (INTERFACES §1.1)
async def request_phase_review(self, phase_id: PhaseId, *, force: bool = False, actor: AgentRole = AgentRole.KERNEL) -> PhaseEvidencePackage:
    """1) phase_event(phase_id, "request_review", ctx(actor, payload={"scope_feature_states": {feature_id: state}, "force": force}))
          → EVIDENCE_REVIEW; ON_PHASE_REVIEW_START fires (E07-S03 MUST package; E07-S08 default retrospective).
       2) phase_event(phase_id, "package_ready", ctx(KERNEL, payload={"evidence_package_written": <file exists>,
          "retrospective_written": <retrospective_path(phase_id) exists>})) → USER_GATE, gate_round += 1.
       3) returns the package built in step 1 (read back from the document)."""

async def auto_request_review(self) -> bool:
    """Called at the end of every tick: if project.current_phase is ACTIVE, running() is empty for the phase, and every FEATURE under
    Phase.scope_epic_ids is in COMPLETE ∪ CANCELLED ∪ BLOCKED → request_phase_review(phase_id); returns True when it did."""

# src/walk/memory/paths.py
def retrospective_path(phase_id: PhaseId) -> str: ...     # "phases/<PHASE-id>/retrospective.md"
```
Guards (E01-S11 names): `all_scope_features_terminal` reads `scope_feature_states` (passes when all values ∈ {COMPLETE, CANCELLED, BLOCKED} or `force` is True **and** `actor_role == USER`); `evidence_package_written`, `retrospective_written` read the same-named boolean payload keys.
CLI: `walk phase review ID [--force]` (USER actor; `--force` is the INTERFACES §3.4 "USER force"); `walk phase evidence ID [--open] [--json]` prints the evidence-package document (`--json` → `PhaseEvidencePackage.model_dump(mode="json")` reconstructed from the document's front matter + sections; `--open` launches the OS default viewer via `SubprocessRunner`).

#### Behavior
1. `auto_request_review` fires at most once per `(phase_id, gate_round)` — idempotency key `phase.review:{phase_id}:{gate_round}` through `IdempotencyStore` (§90, ARCHITECTURE §5.4 style); a tick that finds the key skips.
2. While the current phase is in `EVIDENCE_REVIEW`, `USER_GATE`, `CHANGE_ANALYSIS` or `STOPPED`, `tick()` admits nothing (returns 0) and increments counter `scheduler.skipped{reason=phase_gate}`; runs already running are allowed to finish (they are drained, not cancelled). In `REWORK` only the rework-intake task (E07-S06) is admissible — this story encodes the rule as "states in which admission is allowed: `ACTIVE`, `REWORK`".
3. A `BLOCKED` feature counts as terminal for `all_scope_features_terminal` (INTERFACES §3.4) and is listed under `Open Issues`/`Risk Summary` by the package.
4. `request_phase_review` without `force` on a phase with a non-terminal feature raises `GuardRejected`; with `force=True` and `actor=USER` it proceeds; `force=True` with a non-USER actor raises `PermissionDenied` (Inv. 14).
5. If the retrospective file does not exist after `ON_PHASE_REVIEW_START` (E07-S08 absent or disabled), `package_ready` fails `retrospective_written` and the phase stays in `EVIDENCE_REVIEW`; `request_phase_review` raises `GuardRejected` naming the guard — the CLI prints the guard name and exits 2.
6. Exactly two `PHASE_TRANSITION` events are written per successful review request (`request_review`, `package_ready`); `gate_round` is incremented by the `package_ready` transition (INTERFACES §3.4) and persisted on `phases.gate_round`.
7. `walk phase review PHASE-01` with a daemon goes through `CommandClient` (`phase.review`) and prints the returned package path; without a daemon it runs in-process (ARCHITECTURE §3.1 offline list — `phase review` is added to that list because it needs no agent).
8. `walk phase evidence PHASE-01` on a phase that never reached review exits 1 with `no evidence package for PHASE-01`.
9. `KernelStatus.current_phase.state` reflects `USER_GATE` on the next `status()`; `phase_progress` is unchanged by the review.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given ACTIVE phase with all 3 scope features COMPLETE and no running runs When `tick()` Then `auto_request_review` returns True, phase `USER_GATE`, `gate_round == 1`, package file exists | `tests/orchestrator/test_request_phase_review.py::test_auto_review_when_all_features_terminal` |
| 2 | Given the same phase When a second `tick()` runs Then no second review (idempotency key present) and still one pair of transitions | `tests/orchestrator/test_request_phase_review.py::test_auto_review_idempotent_per_round` |
| 3 | Given one feature IMPLEMENTING When `request_phase_review(force=False)` Then `GuardRejected` naming `all_scope_features_terminal` | `tests/orchestrator/test_request_phase_review.py::test_review_rejected_when_feature_open` |
| 4 | Given one feature IMPLEMENTING When `request_phase_review(force=True, actor=USER)` Then `USER_GATE`; with `actor=ORCHESTRATOR` Then `PermissionDenied` | `tests/orchestrator/test_request_phase_review.py::test_force_review_user_only` |
| 5 | Given a BLOCKED feature and the rest COMPLETE When `tick()` Then review requested and the blocked feature appears in `Open Issues` or `Risk Summary` of the package | `tests/orchestrator/test_request_phase_review.py::test_blocked_feature_is_terminal` |
| 6 | Given the retrospective hook disabled When `request_phase_review` Then `GuardRejected` naming `retrospective_written` and phase `EVIDENCE_REVIEW` | `tests/orchestrator/test_request_phase_review.py::test_package_ready_requires_retrospective` |
| 7 | Given phase `USER_GATE` and 3 ready stories When `tick()` Then 0 admitted and counter `scheduler.skipped{reason=phase_gate}` == 3 | `tests/orchestrator/test_scheduler_phase_boundary.py::test_no_admission_in_user_gate` |
| 8 | Given phase `EVIDENCE_REVIEW` with 1 running run When `tick()` Then the run keeps running (not cancelled) and nothing new is admitted | `tests/orchestrator/test_scheduler_phase_boundary.py::test_running_runs_drain_at_boundary` |
| 9 | Given `walk phase review PHASE-01` (offline, all terminal) Then exit 0 and output ends with `.ai/phases/PHASE-01/evidence-package.md` | `tests/cli/test_cmd_phase_review.py::test_phase_review_offline` |
| 10 | Given `walk phase review PHASE-01` with an open feature Then exit 2 and output names `all_scope_features_terminal`; with `--force` Then exit 0 | `tests/cli/test_cmd_phase_review.py::test_phase_review_guard_and_force` |
| 11 | Given a reviewed phase When `walk phase evidence PHASE-01 --json` Then JSON validates as `PhaseEvidencePackage` | `tests/cli/test_cmd_phase_review.py::test_phase_evidence_json` |
| 12 | Given a never-reviewed phase When `walk phase evidence PHASE-01` Then exit 1 | `tests/cli/test_cmd_phase_review.py::test_phase_evidence_missing_exits_1` |

#### Evidence required
- Quality gate output.
- Demo: on the E06 fixture repo after fake runs complete, `walk run --once` → log line `phase review requested PHASE-01 round 1`; `walk phase evidence PHASE-01 | head -30`; `walk status --json` → `current_phase.state == "USER_GATE"`.

#### Notes
- INTERFACES §3.4 rows 2–3; §5.1 (tick) gains the boundary check; ARCHITECTURE §3.1 offline command list is extended with `phase review` (document in ARCHITECTURE §3.1 in the same commit).
- `retrospective_written` is satisfied by the file written in E07-S08; until E07-S08 lands, this story's tests pre-create `retrospective.md` through a fixture (never through production code).
- `NEW NAME:` `DefaultOrchestrator.auto_request_review`, `request_phase_review(force, actor)` keyword parameters, idempotency key `phase.review:{phase_id}:{gate_round}`, counter reason `phase_gate`, `retrospective_path`, `walk phase review --force`, `walk phase evidence --json`, command `phase.review`, payload keys `scope_feature_states`, `force`, `retrospective_written`.
- Commit subject: `feat: add phase review request and phase boundary stop (E07-S04)`.

#### Evidence (filled by implementer)
_pending_

---

### E07-S05 — `PhaseGate.decide_phase` GO/STOP and next-phase start

**Status:** TODO
**Type:** feat
**Requirements:** §70, §68, §93 (Stop Phase), §118, §6.12, §137 (Inv. 7, 14), §90
**Depends on:** E07-S04
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The user — and only the user — decides a phase at `USER_GATE`: `PhaseGate.decide_phase` records `PHASE_GATE_DECISION`, applies the INTERFACES §5.6 intake for `GO` (phase `COMPLETE`, next phase `start`ed) and `STOP` (phase `STOPPED`, project paused), performs the state transition for `REWORK`/`CHANGE` (intake work in E07-S06/S07), and `walk phase gate` / `walk phase stop` expose it offline and through the daemon.

#### Scope
- In: `PhaseGate` protocol + `DefaultPhaseGate`, `Orchestrator.decide_phase` delegation, GO chaining, STOP + pause, `stop` event from any state (§93), `USER_OVERRIDE` for stop, default hook `builtin.gate_decision_observe`, CLI `gate` (full) and `stop`, IPC `phase.gate`/`phase.stop`.
- Out: REWORK intake task and `rework_planned` (E07-S06); CHANGE analysis task, approval and `change_plan_approved` (E07-S07); phase report on `ON_PHASE_COMPLETE` (E07-S09).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/protocols.py` | modify | `PhaseGate` |
| `src/walk/orchestrator/phase_gate.py` | create | `DefaultPhaseGate` |
| `src/walk/orchestrator/service.py` | modify | `DefaultOrchestrator.decide_phase`, `DefaultOrchestrator.stop_phase` |
| `src/walk/orchestrator/commands.py` | modify | — (commands `phase.gate`, `phase.stop`) `(verify)` |
| `src/walk/orchestrator/__init__.py` | modify | re-exports `PhaseGate`, `DefaultPhaseGate` |
| `src/walk/hooks/builtins.py` | modify | `gate_decision_observe`; `BuiltinHookDeps.improvement` |
| `src/walk/cli/cmd_phase.py` | modify | `phase_app` (`gate ID --decision … [--feedback FILE|TEXT]`, `stop ID --reason TEXT`) |
| `src/walk/cli/ipc.py` | modify | — (`phase.gate`, `phase.stop`) `(verify)` |
| `src/walk/cli/composition.py` | modify | — (constructs `DefaultPhaseGate`; `BuiltinHookDeps.improvement`) |
| `tests/orchestrator/test_phase_gate_go_stop.py` | create | — |
| `tests/orchestrator/test_phase_gate_authority.py` | create | — |
| `tests/hooks/test_builtins_gate_decision.py` | create | — |
| `tests/cli/test_cmd_phase_gate.py` | create | — |

#### Interface contract
```python
# src/walk/orchestrator/protocols.py
class PhaseGate(Protocol):
    """§70–§72 intake; ARCHITECTURE §4.3 write point for PHASE_GATE_DECISION and USER_OVERRIDE. Hosted by walk.orchestrator."""
    async def decide(self, phase_id: PhaseId, decision: PhaseDecision, feedback: str | None, actor: Actor) -> Phase:
        """actor.role must be USER else PermissionDenied (Inv. 14). Requires phase.state == USER_GATE else GuardRejected.
        1) ledger PHASE_GATE_DECISION {decision, feedback, gate_round}; 2) phase_event(f"decide:{decision}", ctx(USER, payload={"feedback": feedback}));
        3) fire ON_PHASE_GATE_DECISION; 4) intake: GO → complete_and_chain(); STOP → stop(); REWORK/CHANGE → return (E07-S06/S07 add intake)."""
    async def stop(self, phase_id: PhaseId, reason: str, actor: Actor) -> Phase:
        """§93 Stop Phase from ANY state: phase_event("stop") → STOPPED; Orchestrator.pause() (checkpoint all, project.paused=True);
        ledger USER_OVERRIDE {command: "phase stop", reason}; USER only."""

# src/walk/orchestrator/phase_gate.py
class DefaultPhaseGate:
    def __init__(self, workflow: WorkflowManager, ledger: LedgerManager, hooks: HookManager, orchestrator_pause: Callable[[], Awaitable[None]],
                 phases: Callable[[ProjectKey], Awaitable[list[Phase]]], start_phase: Callable[[PhaseId], Awaitable[Phase]],
                 clock: Clock, ids: IdFactory) -> None: ...
    async def complete_and_chain(self, phase: Phase) -> Phase:
        """GO: Phase.completed_at = now; Phase.last_decision = GO; next = phase with ordinal+1 in PLANNED → start_phase(next.id)
        (E07-S02 guards apply); no next → projects.current_phase_id = None. ON_PHASE_COMPLETE fires via the decide:GO transition hooks."""

# DefaultOrchestrator
async def decide_phase(self, phase_id, decision, feedback, actor: str) -> Phase:   # INTERFACES §1.1; actor "USER" → Actor(role=USER, name=actor)
async def stop_phase(self, phase_id: PhaseId, reason: str) -> Phase: ...

# ON_PHASE_GATE_DECISION  builtin.gate_decision_observe  prio 60  required=False
#   → improvement.observe(ObservationDraft(observed=f"user gate {decision}", ...), actor=USER, work_item_id=None, run_id=None,
#       source_signal=f"user_gate_{decision.lower()}")   (§118; INTERFACES §5.6 last line)
```
CLI: `walk phase gate ID --decision GO|REWORK|CHANGE|STOP [--feedback FILE|TEXT]` (REWORK/CHANGE require `--feedback`; a value naming an existing file is read, otherwise used verbatim); `walk phase stop ID --reason TEXT`. Both run offline when no daemon (ARCHITECTURE §3.1), otherwise via `CommandClient`.

#### Behavior
1. `decide` with a non-USER actor raises `PermissionDenied` before any write; `AgentOutput` can never carry a phase decision (no field exists — asserted by a schema test).
2. `decide` on a phase not in `USER_GATE` raises `GuardRejected("phase not at gate")` and writes nothing.
3. Ledger order per decision: `PHASE_GATE_DECISION` (payload `decision`, `feedback`, `gate_round`, `actor`) then `PHASE_TRANSITION`; `Phase.last_decision` is updated; the `MUST: ledger PHASE_GATE_DECISION` attachment of ARCHITECTURE §4.1 is satisfied by this write point (WBS §3.5) — the hook writes no duplicate.
4. GO with a `PLANNED` successor: successor becomes `ACTIVE` through `start_phase` (baseline + budgets, E07-S02) in the same `decide` call; `projects.current_phase_id` = successor; `ON_PHASE_COMPLETE` fires for the completed phase before the successor starts.
5. GO without a successor: phase `COMPLETE`, `current_phase_id = None`, `KernelStatus.current_phase is None`; the scheduler admits nothing until a new phase is started.
6. GO whose successor fails its start guards (e.g. empty scope): the completed phase stays `COMPLETE`, the error is re-raised after the decision is recorded, and `walk phase gate` exits 2 printing both facts.
7. STOP via the gate and `stop` via `walk phase stop` both end in `STOPPED` with `project.paused = True`, all running runs checkpointed (`PAUSE`) through `Orchestrator.pause()`, and exactly one `USER_OVERRIDE` event (`command: "phase stop"`); `walk resume` (E02-S13) un-pauses the project but the phase stays `STOPPED` until `reopen` (`STOPPED → PLANNED` row) followed by `walk phase start`; `reopen` is raised through `walk phase transition ID reopen`, a thin USER-only passthrough added by this story (mirrors `walk work transition`), never through a gate decision.
8. REWORK/CHANGE without feedback → `GuardRejected` (`feedback_non_empty`); with feedback the phase moves to `REWORK` / `CHANGE_ANALYSIS` and `decide` returns — no intake yet (E07-S06/S07).
9. `gate_decision_observe` is `LOG_AND_CONTINUE`; one observation per decision with `source_signal == "user_gate_<decision>"`.
10. Decisions are idempotent per gate round: a second `decide` for the same `(phase_id, gate_round)` after the phase left `USER_GATE` fails rule 2; the CLI prints the current state.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given PHASE-01 USER_GATE and PHASE-02 PLANNED with scope When `decide(GO, actor=USER)` Then PHASE-01 `COMPLETE` with `completed_at`, PHASE-02 `ACTIVE`, `current_phase_id == PHASE-02`, events in order `PHASE_GATE_DECISION`, `PHASE_TRANSITION`(COMPLETE), `PHASE_TRANSITION`(ACTIVE) | `tests/orchestrator/test_phase_gate_go_stop.py::test_go_completes_and_starts_next` |
| 2 | Given PHASE-01 USER_GATE and no successor When `decide(GO)` Then `COMPLETE`, `current_phase_id is None`, next `tick()` admits 0 | `tests/orchestrator/test_phase_gate_go_stop.py::test_go_without_successor` |
| 3 | Given a successor with empty scope When `decide(GO)` Then PHASE-01 `COMPLETE`, `GuardRejected` re-raised, decision event present | `tests/orchestrator/test_phase_gate_go_stop.py::test_go_with_unstartable_successor` |
| 4 | Given USER_GATE and 2 running runs When `decide(STOP)` Then `STOPPED`, `project.paused`, 2 `PAUSE` checkpoints, one `USER_OVERRIDE{command="phase stop"}` | `tests/orchestrator/test_phase_gate_go_stop.py::test_stop_pauses_project_and_checkpoints` |
| 5 | Given ACTIVE phase When `stop(reason)` Then `STOPPED` and `USER_OVERRIDE`; then `phase_event("reopen")` by USER → `PLANNED` | `tests/orchestrator/test_phase_gate_go_stop.py::test_stop_from_active_and_reopen` |
| 6 | Given USER_GATE When `decide(REWORK, feedback="Shotgun feels weak")` Then `REWORK`, `last_decision == REWORK`; `decide(CHANGE, feedback=None)` on another gate Then `GuardRejected` naming `feedback_non_empty` | `tests/orchestrator/test_phase_gate_go_stop.py::test_rework_and_change_transitions` |
| 7 | Given `actor.role == ORCHESTRATOR` When `decide(GO)` Then `PermissionDenied` and no ledger event | `tests/orchestrator/test_phase_gate_authority.py::test_non_user_cannot_decide` |
| 8 | Given `AgentOutput.model_fields` Then no field accepts a `PhaseDecision` | `tests/orchestrator/test_phase_gate_authority.py::test_agent_output_has_no_phase_decision_channel` |
| 9 | Given phase ACTIVE When `decide(GO)` Then `GuardRejected("phase not at gate")` | `tests/orchestrator/test_phase_gate_authority.py::test_decide_requires_user_gate` |
| 10 | Given `ON_PHASE_GATE_DECISION` fired with `decision=REWORK` Then one observation with `source_signal == "user_gate_rework"`; given `observe` raising Then hook `FAILED` and the decision stands | `tests/hooks/test_builtins_gate_decision.py::test_gate_decision_observed_and_tolerant` |
| 11 | Given `walk phase gate PHASE-01 --decision GO` offline Then exit 0 and output `PHASE-01 COMPLETE → PHASE-02 ACTIVE` | `tests/cli/test_cmd_phase_gate.py::test_gate_go_offline` |
| 12 | Given `walk phase gate PHASE-01 --decision REWORK --feedback notes.txt` with the file present Then feedback equals file content; without `--feedback` Then exit 2 | `tests/cli/test_cmd_phase_gate.py::test_gate_feedback_from_file_and_required` |
| 13 | Given `walk phase stop PHASE-01 --reason "budget"` Then exit 0, phase `STOPPED`, `walk status --json` shows `paused: true` | `tests/cli/test_cmd_phase_gate.py::test_phase_stop_cli` |
| 14 | Given a running daemon When `walk phase gate … GO` Then the command goes through `commands`/`command_results` and the result equals the offline output shape | `tests/cli/test_cmd_phase_gate.py::test_gate_via_daemon_ipc` |

#### Evidence required
- Quality gate output.
- Demo: on the fixture repo at `USER_GATE`, `walk phase gate PHASE-01 --decision GO` → `PHASE-01 COMPLETE → PHASE-02 ACTIVE`; `walk ledger query --kind PHASE_GATE_DECISION --json`; `walk phase stop PHASE-02 --reason demo` then `walk status` → `paused`.

#### Notes
- INTERFACES §5.6 (GO/STOP lines), §3.4 rows 4, 7, 11, 12; ARCHITECTURE §4.3 (`orchestrator.PhaseGate` write point), §6 (`walk phase stop` in the §93 list), §7 Inv. 14. E01-S11's minimal `walk phase gate` ("records a decision only") is replaced by this full path; keep its tests green by extending them.
- Behavior 7 settles `reopen`: exposed as `walk phase transition ID EVENT` (USER-only passthrough mirroring `walk work transition`), not as a gate decision. `NEW NAME:` `walk phase transition`.
- `NEW NAME:` `PhaseGate` protocol, `DefaultPhaseGate`, `complete_and_chain`, `DefaultOrchestrator.stop_phase`, `walk phase stop`, `walk phase transition`, commands `phase.gate`/`phase.stop`, hook `builtin.gate_decision_observe`, `BuiltinHookDeps.improvement`, `USER_OVERRIDE` payload `command: "phase stop"`.
- Commit subject: `feat: add phase gate decisions with go chaining and phase stop (E07-S05)`.

#### Evidence (filled by implementer)
_pending_

---

### E07-S06 — REWORK intake

**Status:** TODO
**Type:** feat
**Requirements:** §71, §70, §67, §10.2, §137 (Inv. 7, 14), §138 (Over-Engineering)
**Depends on:** E07-S05, E05-S06
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
User feedback given with `REWORK` becomes structured production work (§71): the kernel creates a rework-intake PLAN task owned by `PRODUCT_OWNER` (or `ORCHESTRATOR` when PO is disabled), the agent decomposes the feedback into categorised `new_tasks` strictly inside the phase scope, and when the intake completes the phase returns to `ACTIVE` (`rework_planned`) so the new work is scheduled and the phase is revalidated at the next gate round.

#### Scope
- In: `DefaultPhaseGate.rework_intake`, routing row `PHASE/REWORK`, `PLAN.md.j2` rework block, `REWORK_LABELS`, scope guard on created tasks, `on_intake_completed` → `rework_planned`, payload `rework_task_ids`, admission of the intake task in `REWORK` state.
- Out: CHANGE analysis (E07-S07); gate decision recording (E07-S05); the §71 "phase is revalidated" round itself (E07-S04 handles the next review).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/phase_gate.py` | modify | `DefaultPhaseGate.rework_intake`, `DefaultPhaseGate.on_intake_completed`, `REWORK_LABELS` |
| `src/walk/orchestrator/router.py` | modify | — (row `PHASE / REWORK → PRODUCT_OWNER if enabled else ORCHESTRATOR, purpose PLAN`) `(verify: E03-S07 full table module)` |
| `src/walk/orchestrator/service.py` | modify | — (after `OutputApplier.apply` of a run on an intake task: `phase_gate.on_intake_completed(item, output)`) |
| `src/walk/orchestrator/scheduler.py` | modify | — (in `REWORK`, only items labelled `phase-intake` are admissible) |
| `src/walk/runtime/applier.py` | modify | — (`new_tasks` from an intake run inherit `phase_id`, `labels += ["rework:<category>"]`, parent = the feature named in the draft or the intake task) `(verify)` |
| `src/walk/workflow/guards.py` | modify | — (`rework_work_items_created` reads `rework_task_ids` non-empty; `in_phase_scope` unchanged) |
| `src/walk/agents/templates/PLAN.md.j2` | modify | — (block `rework_intake`: feedback text, §71 category list, scope epics/features list, instruction "one task per category, `phase_id` set, no scope expansion") |
| `tests/orchestrator/test_rework_intake.py` | create | — |
| `tests/orchestrator/test_rework_intake_scope.py` | create | — |
| `tests/agents/test_templates_rework.py` | create | — |

#### Interface contract
```python
# src/walk/orchestrator/phase_gate.py
REWORK_LABELS: tuple[str, ...] = ("rework:design", "rework:vfx", "rework:animation", "rework:gameplay", "rework:audio", "rework:qc", "rework:other")   # §71 categories

class DefaultPhaseGate:   # additions
    async def rework_intake(self, phase: Phase, feedback: str, actor: Actor) -> Task:
        """INTERFACES §5.6 REWORK line: WorkflowManager.create(WorkItemDraft(kind=TASK, title=f"Rework intake: {phase.id} r{phase.gate_round}",
        description=feedback, contract=StoryContract(goal=feedback, owner_role=PRODUCT_OWNER if enabled else ORCHESTRATOR,
        acceptance_criteria=["new_tasks cover every feedback category", "all new_tasks inside phase scope"]), labels=["phase-intake", "rework"]),
        actor=KERNEL, phase_id=phase.id) → state READY (raise_event "ready" by KERNEL); idempotency key f"phase.rework:{phase.id}:{phase.gate_round}"."""
    async def on_intake_completed(self, task: Task, output: AgentOutput, created: list[WorkItemId]) -> Phase | None:
        """Called once the intake task reaches COMPLETE: phase_event(task.phase_id, "rework_planned", ctx(KERNEL, payload={"rework_task_ids": created}))
        → ACTIVE (ON_PHASE_START fires again: new baseline r+1, budgets ensured). Returns the Phase, or None if task is not an intake task."""
```
Routing (INTERFACES §4): `PHASE | REWORK | PRODUCT_OWNER (if enabled) else ORCHESTRATOR | PLAN` — realised as the intake TASK being the schedulable item (phases themselves are not scheduled). "Enabled" = `AgentManager.list_roles()` contains `PRODUCT_OWNER` (E05-S06 constitution present).
Template `PLAN.md.j2` receives `rework: {feedback, categories: REWORK_LABELS, scope: [{epic_id, feature_ids, titles}]}` when `item.labels` contains `phase-intake`.

#### Behavior
1. `decide(REWORK, feedback)` (E07-S05) now ends by calling `rework_intake`; the created task has `phase_id == phase.id`, `labels ⊇ {"phase-intake", "rework"}`, `contract.owner_role` per the enabled-role rule, state `READY`, and is the only item the scheduler admits while the phase is `REWORK` (E07-S04 rule 2 refinement).
2. The intake run's `AgentOutput.new_tasks` are applied by `OutputApplier` (E03-S08) with: `phase_id` forced to the phase, `parent_id` = the feature the draft names (must be a descendant of `Phase.scope_epic_ids`) else the intake task, `labels` gaining exactly one `rework:<category>` from `REWORK_LABELS` (draft label outside the list → `rework:other`), `source_requirements` copied from the parent feature's `gdd_refs`.
3. A draft naming a parent outside the phase scope is rejected: the whole output application fails with `GuardRejected("in_phase_scope")`, no task is created, the run ends `FAILED` with an `EscalationRequest` Level 2 (`PRODUCT`) raised by the kernel (Inv. 7; INTERFACES §1.1 `handle_escalation` routes it).
4. An intake output with `status == COMPLETED` and zero `new_tasks` leaves the phase in `REWORK` and raises `GuardRejected("rework_work_items_created")`; the kernel sets the intake task `BLOCKED` with that reason so the user sees it in `walk status`.
5. On success `rework_planned` → `ACTIVE`; `ON_PHASE_START` produces baseline `r<gate_round>` superseding the previous (E07-S02 rule 4); the new tasks are `READY` and admitted on the next tick; the previous round's completed stories are untouched.
6. Every created task is linked to the phase decision: ledger `WORK_ITEM_CREATED` payload carries `source: "rework"`, `gate_round`, `feedback_excerpt` (first 200 chars).
7. `rework_intake` is idempotent per `(phase_id, gate_round)` (key above): a crash between the decision and task creation followed by a restart creates no duplicate intake task (E07-S05 rule 10 + this key).
8. `PLAN.md.j2` renders the rework block only for intake items; ordinary PLAN runs (E03-S09) render byte-identically to before (snapshot test).
9. §138 Over-Engineering: the template instructs "no new features or epics" and the applier rejects `new_tasks` drafts with `kind ∈ {EPIC, FEATURE}` from an intake run (`GuardRejected("rework_scope_kind")`).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given USER_GATE and PRODUCT_OWNER enabled When `decide(REWORK, "Shotgun feels weak")` Then phase `REWORK` and one TASK `READY` with `owner_role == PRODUCT_OWNER`, labels `phase-intake`, `rework`, `phase_id` set | `tests/orchestrator/test_rework_intake.py::test_rework_creates_intake_task_for_po` |
| 2 | Given PRODUCT_OWNER not in `list_roles()` When `decide(REWORK, …)` Then `owner_role == ORCHESTRATOR` | `tests/orchestrator/test_rework_intake.py::test_rework_falls_back_to_orchestrator` |
| 3 | Given phase `REWORK` with 3 other READY stories When `tick()` Then only the intake task is admitted | `tests/orchestrator/test_rework_intake.py::test_only_intake_admitted_in_rework` |
| 4 | Given a fake PO run returning 3 `new_tasks` (design, vfx, qc) under in-scope features When applied Then 3 tasks with labels `rework:design|vfx|qc`, `phase_id`, `source_requirements` from the parents, and phase `ACTIVE` with `gate_round` unchanged and a new baseline | `tests/orchestrator/test_rework_intake.py::test_intake_output_creates_tasks_and_reactivates` |
| 5 | Given the reactivated phase When `tick()` Then the 3 new tasks are admitted (capacity permitting) | `tests/orchestrator/test_rework_intake.py::test_new_rework_tasks_scheduled` |
| 6 | Given a `new_tasks` draft with an unknown category label When applied Then label `rework:other` | `tests/orchestrator/test_rework_intake.py::test_unknown_category_maps_to_other` |
| 7 | Given `decide(REWORK)` then a simulated crash before task creation and a restart When `decide` path resumes via the idempotency key Then exactly one intake task | `tests/orchestrator/test_rework_intake.py::test_intake_idempotent_across_restart` |
| 8 | Given a draft whose parent feature is outside scope When applied Then `GuardRejected("in_phase_scope")`, zero tasks, run `FAILED`, one Level-2 `ESCALATION_RAISED` | `tests/orchestrator/test_rework_intake_scope.py::test_out_of_scope_task_rejected_and_escalated` |
| 9 | Given an intake output with zero `new_tasks` When applied Then phase stays `REWORK`, intake task `BLOCKED` with reason `rework_work_items_created` | `tests/orchestrator/test_rework_intake_scope.py::test_empty_intake_blocks_task` |
| 10 | Given a draft with `kind=FEATURE` from an intake run When applied Then `GuardRejected("rework_scope_kind")` | `tests/orchestrator/test_rework_intake_scope.py::test_intake_cannot_create_features` |
| 11 | Given `WORK_ITEM_CREATED` events of the new tasks Then payload has `source == "rework"`, `gate_round`, `feedback_excerpt` | `tests/orchestrator/test_rework_intake_scope.py::test_created_tasks_linked_to_feedback` |
| 12 | Given an intake item When `render_instructions(purpose="PLAN")` Then the output contains the feedback, all seven categories and the scope list; given an ordinary feature PLAN item Then output equals the E03-S09 snapshot | `tests/agents/test_templates_rework.py::test_plan_template_rework_block_and_snapshot` |

#### Evidence required
- Quality gate output.
- Demo: fixture repo at `USER_GATE`: `walk phase gate PHASE-01 --decision REWORK --feedback "Shotgun feels weak"` → `PHASE-01 REWORK intake=TASK-00NN`; `walk run --once` (fake PO) → `walk work list --phase PHASE-01 --state READY` shows `rework:*` tasks; `walk phase list` shows `ACTIVE`.

#### Notes
- INTERFACES §5.6 REWORK line and §3.4 row 8; §71 example categories → `REWORK_LABELS`. ADR-0006 D-2: the kernel creates the work items from `new_tasks` intents; the PO agent never calls `jira.*` itself.
- `in_phase_scope` real implementation comes from E06-S07; this story only supplies the parent check at application time.
- The fake PO adapter script lives in the test (scripted `FINAL_OUTPUT` with three drafts); no template content is asserted beyond the three facts in AC 12.
- `NEW NAME:` `REWORK_LABELS`, `rework_intake`, `on_intake_completed`, label `phase-intake`, idempotency key `phase.rework:{phase_id}:{gate_round}`, `GuardRejected` reasons `rework_scope_kind`, `WORK_ITEM_CREATED` payload keys `source/gate_round/feedback_excerpt`, template block `rework_intake`.
- Commit subject: `feat: add rework intake turning gate feedback into phase work (E07-S06)`.

#### Evidence (filled by implementer)
_pending_

---

