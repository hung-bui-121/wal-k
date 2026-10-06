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
**Requirements:** §66–§72, §134, §135, §5 (non-goals: refine rejects stories that drift into out-of-scope work)
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
4. Every `(verify)` marker is resolved (kept or path corrected) and removed. Known hotspots: `src/walk/orchestrator/{models,protocols,router,scheduler,service,commands}.py` (E01-S29/S30, E03-S07/S18), `src/walk/cli/cmd_phase.py` (E01-S11, E06-S04), `src/walk/orchestrator/builtin_hooks.py` (E02-S08 → E04 → E06; moved from `hooks/builtins.py` by ADR-0016), `src/walk/improvement/service.py` (E04-S13), `src/walk/agents/templates/{PLAN,ANALYSIS}.md.j2` (E01-S18, E03-S06, E04-S14), `tests/e2e/conftest.py` fixtures `e03_scenario`/`e04_scenario`/`e06_scenario`, `tests/fakes/fake_unity_provider.py` (E03-S10).
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
| `src/walk/orchestrator/builtin_hooks.py` | modify | `phase_baseline` (content completed), `phase_budget_allocate`; `BuiltinHookDeps.workflow`, `BuiltinHookDeps.phase_budget_limits` |
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

# src/walk/orchestrator/builtin_hooks.py  (ADR-0016)
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
- Builtin callables live in `walk.orchestrator.builtin_hooks` (ADR-0016; L4, may import every lower package's protocols/models), so importing `walk.workflow.protocols` is allowed; `BudgetDimension` comes through `BuiltinHookDeps` as data, following the E02-S08 precedent for `budgets`.
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
| `src/walk/orchestrator/builtin_hooks.py` | modify | `phase_review_build_package`; `BuiltinHookDeps.packager`, `BuiltinHookDeps.evidence` |
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
| `src/walk/orchestrator/builtin_hooks.py` | modify | `gate_decision_observe`; `BuiltinHookDeps.improvement` |
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
| `src/walk/runtime/output_applier.py` | modify | — (`new_tasks` from an intake run inherit `phase_id`, `labels += ["rework:<category>"]`, parent = the feature named in the draft or the intake task) `(verify)` |
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
        acceptance_criteria=["new_tasks cover every feedback category", "all new_tasks inside phase scope"]), labels=["phase-intake", "rework", "analysis-only"]),
        actor=KERNEL, phase_id=phase.id) → state READY (raise_event "ready" by KERNEL); idempotency key f"phase.rework:{phase.id}:{phase.gate_round}"."""
    async def on_intake_completed(self, task: Task, output: AgentOutput, created: list[WorkItemId]) -> Phase | None:
        """Called once the intake task reaches COMPLETE through `analysis_done` (INTERFACES §3.2 row, E06-S02 label `analysis-only`): phase_event(task.phase_id, "rework_planned", ctx(KERNEL, payload={"rework_task_ids": created}))
        → ACTIVE (ON_PHASE_START fires again: new baseline r+1, budgets ensured). Returns the Phase, or None if task is not an intake task."""
```
Routing (INTERFACES §4): `PHASE | REWORK | PRODUCT_OWNER (if enabled) else ORCHESTRATOR | PLAN` — realised as the intake TASK being the schedulable item (phases themselves are not scheduled). "Enabled" = `AgentManager.list_roles()` contains `PRODUCT_OWNER` (E05-S06 constitution present).
Template `PLAN.md.j2` receives `rework: {feedback, categories: REWORK_LABELS, scope: [{epic_id, feature_ids, titles}]}` when `item.labels` contains `phase-intake`.

#### Behavior
1. `decide(REWORK, feedback)` (E07-S05) now ends by calling `rework_intake`; the created task has `phase_id == phase.id`, `labels ⊇ {"phase-intake", "rework", "analysis-only"}`, `contract.owner_role` per the enabled-role rule, state `READY`, and is the only item the scheduler admits while the phase is `REWORK` (E07-S04 rule 2 refinement).
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
| 1 | Given USER_GATE and PRODUCT_OWNER enabled When `decide(REWORK, "Shotgun feels weak")` Then phase `REWORK` and one TASK `READY` with `owner_role == PRODUCT_OWNER`, labels `phase-intake`, `rework`, `analysis-only`, `phase_id` set | `tests/orchestrator/test_rework_intake.py::test_rework_creates_intake_task_for_po` |
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
- Completion path (architect decision 2026-10-06): the intake task carries label `analysis-only`, so a `COMPLETED` intake output moves it `IMPLEMENTING → COMPLETE` via `analysis_done` (INTERFACES §3.2, E06-S02) — no commit, no review; no new transition row. `on_intake_completed` runs after that transition; with zero `new_tasks` the kernel raises the Behavior 4 rejection before `analysis_done`. `RunCompletionHandler` already holds `(TASK, "PLAN", "analysis_done")` (E06-S04): the intake consumer is a `phase-intake` label branch of that entry (E06-S02 Notes), not a second registration.
- The fake PO adapter script lives in the test (scripted `FINAL_OUTPUT` with three drafts); no template content is asserted beyond the three facts in AC 12.
- `NEW NAME:` `REWORK_LABELS`, `rework_intake`, `on_intake_completed`, label `phase-intake`, idempotency key `phase.rework:{phase_id}:{gate_round}`, `GuardRejected` reasons `rework_scope_kind`, `WORK_ITEM_CREATED` payload keys `source/gate_round/feedback_excerpt`, template block `rework_intake`.
- Commit subject: `feat: add rework intake turning gate feedback into phase work (E07-S06)`.

#### Evidence (filled by implementer)
_pending_

---

### E07-S07 — CHANGE intake and `ChangeImpactAnalyzer`

**Status:** TODO
**Type:** feat
**Requirements:** §72, §70, §43, §73, §92, §137 (Inv. 7, 14), §138 (Over-Engineering)
**Depends on:** E07-S05, E04-S11
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A `CHANGE` decision becomes a §72 impact analysis that the user approves before anything changes: the kernel creates a change-analysis TASK run by `LEAD_DEV` (then `PRODUCT_OWNER` when enabled) with purpose `ANALYSIS`, `ChangeImpactAnalyzer` merges the agents' declared impact with kernel facts (`CodeGraphProvider.impact`, scope work items, tests, future phases) into a `ChangeImpact` covering all eight §72 categories plus a migration plan, records it as change-plan evidence, and raises an `ApprovalRequest(USER)`; approval moves the phase `CHANGE_ANALYSIS → PLANNED` and re-plans it, denial returns it to `USER_GATE`.

#### Scope
- In: `DefaultPhaseGate.change_intake`, `on_change_analysis_completed`, `apply_change_decision`; `ChangeImpact` model; `ChangeImpactAnalyzer` (kernel fact expansion, rendering, evidence recording); routing of the change-analysis task (LEAD_DEV → PRODUCT_OWNER, purpose `ANALYSIS`); admission of that task in `CHANGE_ANALYSIS`; `ApprovalRequest.kind == "CHANGE_PLAN"`; payload producers `change_plan_evidence_id` and `approval_state`; `change_plan_approved` / `change_rejected` transitions; `plan_phase` re-run after approval; `ANALYSIS.md.j2` block `change_analysis`.
- Out: executing the migration plan (the re-planned phase is started by the user with `walk phase start`, E07-S02); gate decision recording (E07-S05); REWORK intake (E07-S06); GDD compiler internals (E06-S04 `plan_phase`); asset-provider impact (E08 — assets are agent-declared here).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/models.py` | modify | `ChangeImpact` |
| `src/walk/orchestrator/change_impact.py` | create | `ChangeImpactAnalyzer`, `CHANGE_PLAN_SECTIONS`, `CHANGE_FINDING_PREFIXES`, `render_change_plan` |
| `src/walk/orchestrator/phase_gate.py` | modify | `DefaultPhaseGate.change_intake`, `DefaultPhaseGate.on_change_analysis_completed`, `DefaultPhaseGate.apply_change_decision` |
| `src/walk/orchestrator/router.py` | modify | — (row `PHASE / CHANGE_ANALYSIS`: change-analysis task → `LEAD_DEV` then `PRODUCT_OWNER` if enabled, purpose `ANALYSIS`) `(verify: E03-S07 full table module)` |
| `src/walk/orchestrator/scheduler.py` | modify | — (in `CHANGE_ANALYSIS`, only items labelled `phase-intake` + `change` are admissible) |
| `src/walk/orchestrator/service.py` | modify | — (`decide` CHANGE → `change_intake`; after `OutputApplier.apply` on a change-analysis task → `on_change_analysis_completed`; `tick` step 0 → `apply_change_decision` for decided `CHANGE_PLAN` approvals) |
| `src/walk/orchestrator/__init__.py` | modify | re-exports `ChangeImpact`, `ChangeImpactAnalyzer` |
| `src/walk/permissions/models.py` | modify | `ApprovalRequest.kind` gains `"CHANGE_PLAN"` |
| `src/walk/workflow/guards.py` | modify | — (`impact_analysis_evidence_present` reads `change_plan_evidence_id`; `approval_user` reads `approval_state`) |
| `src/walk/memory/paths.py` | modify | `change_plan_path` |
| `src/walk/agents/templates/ANALYSIS.md.j2` | modify | — (block `change_analysis`: feedback, §72 category list, `CHANGE_FINDING_PREFIXES`, scope list, kernel seed impact, "migration plan in `result`", "no `new_tasks`") |
| `src/walk/cli/cmd_approvals.py` | modify | — (offline `walk approve/deny` of a `CHANGE_PLAN` request calls `apply_change_decision` in-process) `(verify: E02-S11)` |
| `src/walk/cli/composition.py` | modify | — (constructs `ChangeImpactAnalyzer` with `IntegrationManager.code_graph` or `None`) |
| `docs/01-architecture/DOMAIN-MODEL.md` | modify | — (`ApprovalRequest.kind` literal, `ChangeImpact` in §4.15) |
| `tests/orchestrator/test_change_impact.py` | create | — |
| `tests/orchestrator/test_change_intake.py` | create | — |
| `tests/orchestrator/test_change_approval.py` | create | — |
| `tests/cli/test_cmd_approvals_change.py` | create | — |
| `tests/agents/test_templates_change.py` | create | — |

#### Interface contract
```python
# src/walk/orchestrator/models.py
class ChangeImpact(WalkModel):
    """§72 impact analysis result; rendered to .ai/phases/<PHASE-id>/evidence/change-plan-<gate_round>.md."""
    phase_id: PhaseId
    gate_round: int
    feedback: str
    affected_gdd: list[GddRef]                 # Affected GDD
    affected_specs: list[str]                  # Affected Specs (doc ids / .ai paths)
    affected_work_items: list[WorkItemId]      # Affected Jira Work (kernel ids; provider keys rendered alongside)
    affected_code: list[str]                   # Affected Code (repo paths; declared ∪ CodeGraphProvider.impact)
    affected_assets: list[str]                 # Affected Assets
    affected_save_data: list[str]              # Affected Save Data
    affected_tests: list[str]                  # Affected Tests (paths + AUTOMATED_TEST evidence ids)
    affected_future_phases: list[PhaseId]      # Affected Future Phases
    migration_plan: str                        # §72 SHOULD: migration/change plan (markdown)
    graph_available: bool
    analysis_run_ids: list[RunId]
    generated_at: datetime

# src/walk/orchestrator/change_impact.py
CHANGE_PLAN_SECTIONS = ("Feedback", "Affected GDD", "Affected Specs", "Affected Jira Work", "Affected Code", "Affected Assets",
                        "Affected Save Data", "Affected Tests", "Affected Future Phases", "Migration Plan")   # §72 order + plan
CHANGE_FINDING_PREFIXES: dict[str, str] = {"GDD:": "affected_gdd", "SPEC:": "affected_specs", "WORK:": "affected_work_items",
    "CODE:": "affected_code", "ASSET:": "affected_assets", "SAVE:": "affected_save_data", "TEST:": "affected_tests",
    "PHASE:": "affected_future_phases"}   # Finding.summary prefix → field; values come from Finding.affected_files

class ChangeImpactAnalyzer:
    def __init__(self, workflow: WorkflowManager, memory: MemoryManager, evidence: EvidenceManager,
                 code_graph: CodeGraphProvider | None, repo_path: str, clock: Clock) -> None: ...
    async def seed(self, phase: Phase, feedback: str) -> ChangeImpact:
        """Kernel facts before any agent run: affected_future_phases = phases with ordinal > phase.ordinal not COMPLETE/STOPPED;
        affected_work_items = []; all other lists empty; migration_plan = ''. Passed to the ANALYSIS template."""
    async def analyze(self, phase: Phase, feedback: str, outputs: list[tuple[RunId, AgentOutput]]) -> ChangeImpact:
        """Merge declared findings (CHANGE_FINDING_PREFIXES) of every output, then expand:
        affected_code ∪= [n.path for n in code_graph.impact(repo_path, declared_code) if n.path];
        affected_tests ∪= impacted paths matching tests globs + AUTOMATED_TEST evidence ids of affected work items;
        affected_work_items ∪= scope descendants whose FeatureContext.relevant_files ∩ affected_code ≠ ∅ or whose gdd_refs ∩ affected_gdd ≠ ∅;
        affected_future_phases ∪= seed facts; migration_plan = LEAD_DEV output.result (+ PO output.result under '### Product');
        all lists de-duplicated and sorted."""
    async def record(self, impact: ChangeImpact, *, actor: Actor) -> Evidence:
        """render_change_plan → file at change_plan_path(phase_id, gate_round) → EvidenceManager.record(
        EvidenceDraft(kind=PROJECT_DATA, path_or_uri=<file>, description=f"Change plan {phase_id} r{gate_round}",
        metrics=impact.model_dump(mode="json")), actor=actor, work_item_id=None, phase_id=phase_id, commit=HEAD)."""

def render_change_plan(impact: ChangeImpact, titles: dict[WorkItemId, str]) -> str:
    """One '## <section>' per CHANGE_PLAN_SECTIONS in order; empty list → '_none identified_';
    Affected Code adds '_code graph unavailable — agent-declared paths only_' when graph_available is False."""

# src/walk/memory/paths.py
def change_plan_path(phase_id: PhaseId, gate_round: int) -> str: ...   # "phases/<PHASE-id>/evidence/change-plan-<gate_round>.md"

# src/walk/orchestrator/phase_gate.py — DefaultPhaseGate additions (constructor gains analyzer, permissions, plan_phase)
async def change_intake(self, phase: Phase, feedback: str, actor: Actor) -> Task:
    """INTERFACES §5.6 CHANGE line. WorkflowManager.create(WorkItemDraft(kind=TASK, title=f"Change analysis: {phase.id} r{phase.gate_round}",
    description=feedback, contract=StoryContract(goal=feedback, owner_role=LEAD_DEV,
    reviewer_role=PRODUCT_OWNER if enabled else LEAD_DEV, acceptance_criteria=["every §72 category answered", "migration plan in result"]),
    labels=["phase-intake", "change", "analysis-only"]), actor=KERNEL, phase_id=phase.id) → READY; idempotency key f"phase.change:{phase.id}:{phase.gate_round}"."""
async def on_change_analysis_completed(self, task: Task, output: AgentOutput, run_id: RunId) -> ApprovalRequest | None:
    """Called after the task reached COMPLETE via `analysis_done` (INTERFACES §3.2, label `analysis-only`).
    LEAD_DEV task done and PRODUCT_OWNER enabled → create the follow-up change-analysis TASK (same title suffix " (PO)",
    owner_role=PRODUCT_OWNER, labels ["phase-intake", "change", "analysis-only", "change:po"], parent_id=task.id) → READY;
    idempotency key f"phase.change_po:{phase.id}:{phase.gate_round}"; return None.
    Last task done → analyzer.analyze(outputs of all change-analysis tasks of this gate round) → analyzer.record →
    PermissionManager.request_approval({"phase_id", "gate_round", "evidence_id", "path"}, kind="CHANGE_PLAN",
    approver=USER, requested_by=LEAD_DEV, run_id=run_id, work_item_id=task.id)."""
async def apply_change_decision(self, approval_id: ApprovalRequestId) -> Phase:
    """Approval kind CHANGE_PLAN, state APPROVED → phase_event("change_plan_approved", ctx(Actor(USER, name=decided_by),
    payload={"change_plan_evidence_id": payload.evidence_id, "approval_state": "APPROVED"})) → PLANNED → plan_phase(phase_id);
    DENIED/EXPIRED → phase_event("change_rejected") → USER_GATE. Idempotency key f"phase.change_decided:{approval_id}"."""
```
Routing (INTERFACES §4 `PHASE | CHANGE_ANALYSIS | LEAD_DEV + PRODUCT_OWNER | ANALYSIS`), realised on the change-analysis TASKs: labels ⊇ {`phase-intake`, `change`} and no `change:po` → `LEAD_DEV`/`ANALYSIS`; with `change:po` (follow-up task) → `PRODUCT_OWNER`/`ANALYSIS`. "Enabled" = `AgentManager.list_roles()` contains `PRODUCT_OWNER` (same rule as E07-S06).
Guards (E01-S11 names): `impact_analysis_evidence_present` passes iff payload `change_plan_evidence_id` is a non-empty `EvidenceId`; `approval_user` passes iff payload `approval_state == "APPROVED"` and `ctx.actor.role == USER`.

#### Behavior
1. `decide(CHANGE, feedback)` (E07-S05) now ends by calling `change_intake`; the task has `phase_id == phase.id`, labels `phase-intake`, `change`, `analysis-only`, `owner_role == LEAD_DEV`, state `READY`, and is the only admissible item while the phase is `CHANGE_ANALYSIS` (E07-S04 rule 2 refined; counter `scheduler.skipped{reason=phase_gate}` for the rest).
2. The `ANALYSIS.md.j2` `change_analysis` block renders the feedback, the eight §72 categories, `CHANGE_FINDING_PREFIXES` as the reporting format ("one `Finding` per affected item, `summary` starts with the prefix, paths in `affected_files`"), the phase scope list and the `seed()` impact; ordinary `ANALYSIS` items render byte-identically to before (snapshot).
3. A change-analysis run must not mutate production work: its `new_tasks`, `new_bugs` and `changes` are rejected by `OutputApplier` with `GuardRejected("change_analysis_read_only")`, the run ends `FAILED`, the task returns to `READY` for a retry (bounded by `max_fix_loops`, then `BLOCKED`) — Inv. 7, §138.
4. Output status `NEEDS_INPUT`/`BLOCKED` follows the normal escalation path (INTERFACES §1.1 `handle_escalation`); the phase stays `CHANGE_ANALYSIS`.
5. With `PRODUCT_OWNER` enabled there are two change-analysis tasks in order (LEAD_DEV, then the `change:po` follow-up for PRODUCT_OWNER, both `ANALYSIS`, each completing via `analysis_done`); without it, one LEAD_DEV task. The approval is requested only after the last task completes.
6. `analyze` treats a finding whose summary matches no prefix as context only (ignored for lists); a `WORK:` value that is not an existing work item id is dropped with a `TelemetryManager.log` warning; a `PHASE:` value that is not a later phase is dropped likewise.
7. When `code_graph is None` or `impact()` raises `TransientError`, `affected_code` is the declared set only, `graph_available=False`, and the rendered section carries the unavailability note; the analysis still completes (E04-S11 rule 7).
8. `record` writes the change plan under the phase evidence dir, `EVIDENCE_RECORDED` is emitted by `EvidenceManager`, and the `ApprovalRequest` payload points to that evidence id and repo-relative path; `walk approvals --pending` lists it with kind `CHANGE_PLAN`.
9. `walk approve APV-NNNN` (daemon: through `commands`; offline: in-process via `cmd_approvals`) → `apply_change_decision`: phase `PLANNED`, `PHASE_TRANSITION` with `event == "change_plan_approved"`, then `Orchestrator.plan_phase(phase_id)` (E06-S04) adds/updates scope work; completed stories stay `COMPLETE`; the phase is not started automatically — the user runs `walk phase start` (E07-S02; baseline `r<gate_round>` supersedes the previous one).
10. `walk deny APV-NNNN` or expiry (E02-S11 `expire_due`) → `change_rejected` → `USER_GATE` with `gate_round` unchanged and `last_decision == CHANGE`; the user decides again (E07-S05).
11. `change_plan_approved` raised without a recorded change plan or with a non-USER actor fails `impact_analysis_evidence_present` / `approval_user` (`GuardRejected`); nothing else reaches it (Inv. 14).
12. Idempotency: `change_intake` per `(phase_id, gate_round)` and `apply_change_decision` per approval id; a restart between approval and transition applies the decision once (§90).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given USER_GATE When `decide(CHANGE, "Replace energy system with stamina")` Then phase `CHANGE_ANALYSIS` and one TASK `READY` with labels `phase-intake`, `change`, `analysis-only`, `owner_role == LEAD_DEV`, `phase_id` set | `tests/orchestrator/test_change_intake.py::test_change_creates_analysis_task` |
| 2 | Given phase `CHANGE_ANALYSIS` with 3 other READY stories When `tick()` Then only the change-analysis task is admitted with role `LEAD_DEV` and purpose `ANALYSIS` | `tests/orchestrator/test_change_intake.py::test_only_analysis_task_admitted` |
| 3 | Given PRODUCT_OWNER enabled and a completed LEAD_DEV run When applied Then the LEAD_DEV task is `COMPLETE` via `analysis_done`, a follow-up TASK labelled `change:po` is `READY`, no approval; next `tick()` admits PRODUCT_OWNER with purpose `ANALYSIS` on it | `tests/orchestrator/test_change_intake.py::test_po_run_follows_lead_dev` |
| 4 | Given an analysis output with `new_tasks` When applied Then `GuardRejected("change_analysis_read_only")`, zero tasks created, run `FAILED`, task `READY` | `tests/orchestrator/test_change_intake.py::test_analysis_run_is_read_only` |
| 5 | Given `decide(CHANGE)` then a simulated crash before task creation and a restart Then exactly one change-analysis task | `tests/orchestrator/test_change_intake.py::test_change_intake_idempotent_across_restart` |
| 6 | Given findings `CODE: Assets/Scripts/Energy.cs` and a fake graph where `Hud.cs`, `Tests/EnergyTests.cs` depend on it When `analyze` Then `affected_code` contains all three, `affected_tests` contains the test path, `graph_available` True | `tests/orchestrator/test_change_impact.py::test_analyze_expands_code_via_graph` |
| 7 | Given a scope story whose feature context lists `Assets/Scripts/Hud.cs` in relevant files When `analyze` Then the story id is in `affected_work_items` | `tests/orchestrator/test_change_impact.py::test_analyze_maps_code_to_work_items` |
| 8 | Given PHASE-01 and PLANNED PHASE-02, PHASE-03 When `seed` Then `affected_future_phases == [PHASE-02, PHASE-03]`; a `PHASE: PHASE-01` finding is dropped | `tests/orchestrator/test_change_impact.py::test_future_phases_from_kernel_facts` |
| 9 | Given `code_graph=None` When `analyze` Then `affected_code` equals the declared paths, `graph_available` False | `tests/orchestrator/test_change_impact.py::test_analyze_without_graph_degrades` |
| 10 | Given the same outputs and frozen clock When `analyze` twice Then equal `model_dump()` with sorted lists | `tests/orchestrator/test_change_impact.py::test_analyze_deterministic` |
| 11 | Given an impact with empty assets When `render_change_plan` Then exactly 10 `## ` headings equal to `CHANGE_PLAN_SECTIONS` in order and `Affected Assets` reads `_none identified_` | `tests/orchestrator/test_change_impact.py::test_render_change_plan_sections` |
| 12 | Given the last analysis run completes When applied Then `change-plan-1.md` exists under the phase evidence dir, one `EVIDENCE_RECORDED`, task `COMPLETE`, one PENDING `ApprovalRequest` with `kind == "CHANGE_PLAN"`, `approver == USER`, payload `evidence_id` | `tests/orchestrator/test_change_approval.py::test_completion_records_plan_and_requests_approval` |
| 13 | Given the pending approval When approved by USER and `apply_change_decision` Then phase `PLANNED`, `plan_phase` called once, COMPLETE stories unchanged | `tests/orchestrator/test_change_approval.py::test_approved_change_replans_phase` |
| 14 | Given the pending approval When denied (or expired) Then phase `USER_GATE`, `gate_round` unchanged, `last_decision == CHANGE` | `tests/orchestrator/test_change_approval.py::test_denied_change_returns_to_gate` |
| 15 | Given `phase_event("change_plan_approved")` with no `change_plan_evidence_id` or actor ORCHESTRATOR Then `GuardRejected` naming `impact_analysis_evidence_present` / `approval_user` | `tests/orchestrator/test_change_approval.py::test_change_plan_approved_guards` |
| 16 | Given `apply_change_decision(APV-0001)` called twice Then one `PHASE_TRANSITION` | `tests/orchestrator/test_change_approval.py::test_apply_change_decision_idempotent` |
| 17 | Given offline `walk approve APV-0001 --note ok` on a `CHANGE_PLAN` request Then exit 0 and output `PHASE-01 PLANNED (change plan approved)` | `tests/cli/test_cmd_approvals_change.py::test_offline_approve_applies_change_decision` |
| 18 | Given a change-analysis item When `render_instructions(purpose="ANALYSIS")` Then output contains the feedback, all eight §72 categories and every prefix; given an ordinary ANALYSIS item Then output equals the prior snapshot | `tests/agents/test_templates_change.py::test_analysis_template_change_block_and_snapshot` |

#### Evidence required
- Quality gate output.
- Demo on the fixture repo at `USER_GATE` (fake LEAD_DEV/PO adapters, `FakeCodeGraphProvider`): `walk phase gate PHASE-01 --decision CHANGE --feedback "Replace energy with stamina"` → `PHASE-01 CHANGE_ANALYSIS intake=TASK-00NN`; `walk run --once` twice; `walk approvals --pending` → `APV-NNNN CHANGE_PLAN USER`; `cat .ai/phases/PHASE-01/evidence/change-plan-1.md | head -40`; `walk approve APV-NNNN --note ok`; `walk phase list` → `PHASE-01 PLANNED`.

#### Notes
- INTERFACES §5.6 CHANGE line, §3.4 rows 9–10, §4 `PHASE / CHANGE_ANALYSIS` row, §2.6 `impact` ("used by §72 CHANGE analysis"); ARCHITECTURE §1.2 lists `ChangeImpactAnalyzer` `[Stage 6+]` in `walk.orchestrator` without a contract — this story gives it one as a concrete class (no protocol: single implementation, orchestrator-internal).
- Completion path (architect decision 2026-10-06): every change-analysis task carries label `analysis-only` and completes via `analysis_done` (INTERFACES §3.2, E06-S02); one task per analysis run because `analysis_done` ends the task, so the PRODUCT_OWNER step is a follow-up task, not a second run on the same task. `RunCompletionHandler` already holds `(TASK, "ANALYSIS", "analysis_done")` (E06-S02): the change consumer is a `phase-intake` + `change` label branch of that entry, not a second registration.
- Findings-as-impact (`CHANGE_FINDING_PREFIXES`) keeps `AgentOutput` unchanged (§126); the analyzer, not the agent, decides the final lists, so a hallucinated work item or phase id is dropped (Behavior 6).
- `ApprovalRequest.kind` literal extension must be mirrored in DOMAIN-MODEL §4.5 in the same commit; the `approval_requests.kind` column is free text, so no migration is needed.
- `plan_phase` is E06-S04's GDD compiler entry; this story only calls it. If E06-S04's signature differs, X01 corrects the call site.
- `NEW NAME:` `ChangeImpact`, `ChangeImpactAnalyzer` (concrete, `walk.orchestrator.change_impact`), `CHANGE_PLAN_SECTIONS`, `CHANGE_FINDING_PREFIXES`, `render_change_plan`, `change_plan_path`, `change_intake`, `on_change_analysis_completed`, `apply_change_decision`, `ApprovalRequest.kind "CHANGE_PLAN"`, labels `change`, `change:po`, idempotency keys `phase.change:{phase_id}:{gate_round}`, `phase.change_po:{phase_id}:{gate_round}` and `phase.change_decided:{approval_id}`, `GuardRejected` reason `change_analysis_read_only`, template block `change_analysis`.
- Commit subject: `feat: add change intake with impact analysis and approval (E07-S07)`.

#### Evidence (filled by implementer)
_pending_

---

### E07-S08 — Phase retrospective skeleton

**Status:** TODO
**Type:** feat
**Requirements:** §115, §114, §116, §83, §90, §136 (retrospective skeleton), §137 (Inv. 9)
**Depends on:** E07-S03, E04-S13
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every phase review produces a metrics-only §115 retrospective without any agent run: `ImprovementManager.phase_retrospective(phase_id, with_narrative=False)` computes `RetrospectiveMetrics` from the ledger plus a deterministic top bottleneck and top defect, persists a `Retrospective` row and writes `.ai/phases/PHASE-NN/retrospective.md` from the `ON_PHASE_REVIEW_START` default hook, so the `retrospective_written` guard (E07-S04) is satisfied and the evidence package links it.

#### Scope
- In: `phase_retrospective` (was `NotSupported("E07-S08")` since E04-S13), `RetrospectiveRepository`, bottleneck/defect rules, `RETROSPECTIVE_SECTIONS` + document, default hook `builtin.phase_retrospective`, `PhaseEvidencePackage.retrospective_id`, `walk improvement retro PHASE_ID` (`[MVP skeleton]`), `request_phase_review` resuming a phase stuck in `EVIDENCE_REVIEW`.
- Out: narrative / `PROCESS_ARCHITECT` `RETRO` run, `RETRO.md.j2` content and the `.ai/improvements/RETRO-PHASE-NN.md` copy (E10-S07); improvement candidates (E10-S04 — `candidate_ids` stays empty); TASK/FEATURE/PROJECT retrospective levels (E10).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/improvement/service.py` | modify | `DefaultImprovementManager.phase_retrospective` |
| `src/walk/improvement/repository.py` | modify | `RetrospectiveRepository` |
| `src/walk/improvement/retrospective.py` | create | `top_bottleneck`, `top_defect`, `render_retrospective` |
| `src/walk/improvement/__init__.py` | modify | re-exports `RetrospectiveRepository` |
| `src/walk/memory/sections.py` | modify | `RETROSPECTIVE_SECTIONS` |
| `src/walk/orchestrator/builtin_hooks.py` | modify | `phase_retrospective` (hook `builtin.phase_retrospective`) |
| `src/walk/orchestrator/evidence_packager.py` | modify | — (`build` sets `retrospective_id` when the phase retrospective exists) |
| `src/walk/orchestrator/service.py` | modify | — (`request_phase_review` on a phase already in `EVIDENCE_REVIEW` re-fires `ON_PHASE_REVIEW_START` hooks and retries `package_ready` only) |
| `src/walk/cli/cmd_improvement.py` | modify | `retro` |
| `src/walk/cli/composition.py` | modify | — (`DefaultImprovementManager` gains `telemetry`, `retrospectives`) |
| `tests/improvement/test_phase_retrospective.py` | create | — |
| `tests/improvement/test_retrospective_rules.py` | create | — |
| `tests/hooks/test_builtins_phase_retrospective.py` | create | — |
| `tests/orchestrator/test_request_phase_review_resume.py` | create | — |
| `tests/cli/test_cmd_improvement_retro.py` | create | — |

#### Interface contract
Protocol: INTERFACES §1.15 `ImprovementManager.phase_retrospective(phase_id, *, with_narrative) -> Retrospective`; model DOMAIN-MODEL §4.14 `Retrospective`, §4.12 `RetrospectiveMetrics`; table DOMAIN-MODEL §6.2 `retrospectives`.
```python
# src/walk/improvement/repository.py
class RetrospectiveRepository:
    def __init__(self, db: Database) -> None: ...
    async def upsert(self, retro: Retrospective) -> None: ...                 # PK id; json = model_dump_json()
    async def get(self, retro_id: RetrospectiveId) -> Retrospective | None: ...

# src/walk/improvement/retrospective.py — pure functions over ledger events (§83)
def top_bottleneck(transitions: list[LedgerEvent], now: datetime) -> str:
    """Sum dwell time per WorkItemState over WORK_ITEM_TRANSITION events of STORY/TASK/BUG items (state entered → next transition,
    open intervals closed at `now`), excluding COMPLETE and CANCELLED. Max sum wins; tie → state name ascending.
    Returns f"{state}: {hours:.1f} h over {n} items (worst {item_id})" or "none"."""
def top_defect(bug_events: list[LedgerEvent]) -> str:
    """Group BUG_CREATED by payload.parent_id (feature or story). Max count wins; tie → highest payload.severity, then id ascending.
    Returns f"{count} bugs under {parent_id} (max severity {severity}; first {bug_id})" or "none"."""
def render_retrospective(retro: Retrospective, phase_id: PhaseId, gate_round: int) -> str:
    """One '## <section>' per RETROSPECTIVE_SECTIONS. Metrics = '| metric | value |' table in §115 order
    (Stories, First-pass success %, Reworked stories, QC Bugs, Escaped Bugs, Context stale incidents, Fallbacks, Failed handoffs,
    Build failures) followed by Debate rounds, User escalations, Total cost USD, Total tokens, Mean task duration s."""

# src/walk/memory/sections.py
RETROSPECTIVE_SECTIONS = ("Metrics", "Top Bottleneck", "Top Defect", "Candidates", "Narrative")

# DefaultImprovementManager — constructor gains telemetry: TelemetryManager, retrospectives: RetrospectiveRepository
async def phase_retrospective(self, phase_id: PhaseId, *, with_narrative: bool) -> Retrospective:
    """with_narrative=True → NotSupported("E10-S07"). Else: metrics = telemetry.metrics(phase_id=phase_id);
    top_bottleneck/top_defect from ledger.query(phase_id=phase_id, kinds=[...]); Retrospective(id=f"RETRO-{phase_id}", level="PHASE",
    subject_id=phase_id, candidate_ids=[], narrative_markdown=""); repository upsert; MemoryManager.write(doc type=retrospective,
    id=f"RETRO-{phase_id}") at retrospective_path(phase_id) (E07-S04). Returns the Retrospective."""

# ON_PHASE_REVIEW_START  builtin.phase_retrospective  prio 5  required=False  (default attachment, ARCHITECTURE §4.1)
#   improvement.phase_retrospective(phase_id, with_narrative=False); ctx.payload["retrospective_written"] = True
```
CLI: `walk improvement retro PHASE_ID [--json]` — regenerates the retrospective (same call as the hook) and prints the document (`--json` → `Retrospective.model_dump(mode="json")`).

#### Behavior
1. Metrics come only from `TelemetryManager.metrics(phase_id=…)` (E01 `METRIC_QUERIES`); the retrospective reads no agent output and starts no run (§83, Inv. 9 — ledger is the source).
2. `top_bottleneck` and `top_defect` are pure and deterministic for a given event list and `now` (injected `Clock`); an empty phase yields `"none"` for both and all-zero metrics.
3. The hook runs at priority 5, before `builtin.phase_review_build_package` (priority 10), so `DefaultEvidencePackager.build` finds the retrospective and sets `PhaseEvidencePackage.retrospective_id = "RETRO-<phase>"`; when absent it stays `None`.
4. The document has front matter `type: retrospective`, `id: RETRO-<phase>`, `related.work_items` = scope stories, the five `RETROSPECTIVE_SECTIONS` in order; `Candidates` reads `_none — candidate generation is E10-S04_`, `Narrative` reads `_not generated (with_narrative=False)_`.
5. A later gate round overwrites the same document (version bump, `MemoryManager.write`) and upserts the same row; the previous round remains in git history only.
6. Hook failure is `LOG_AND_CONTINUE` (default attachment): the phase stays `EVIDENCE_REVIEW` because `retrospective_written` is false (E07-S04 rule 5). `walk phase review ID` on a phase in `EVIDENCE_REVIEW` re-fires `ON_PHASE_REVIEW_START` and retries `package_ready` without a second `request_review` transition — the same path a restarted kernel uses after a crash during review (§90).
7. `with_narrative=True` raises `NotSupported("E10-S07")`; the hook never passes `True`.
8. `walk improvement retro PHASE-01` on a phase with no ledger events still writes a valid document and exits 0; an unknown phase id exits 1.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a seeded phase ledger (4 stories COMPLETE, 1 with a QC rejection, 2 bugs, 1 fallback, 1 build failure) When `phase_retrospective(PHASE-01, with_narrative=False)` Then `metrics == telemetry.metrics(phase_id=PHASE-01)`, `level == "PHASE"`, `candidate_ids == []`, `narrative_markdown == ""` | `tests/improvement/test_phase_retrospective.py::test_phase_retrospective_metrics_from_ledger` |
| 2 | Given the call When done Then a `retrospectives` row `RETRO-PHASE-01` and `.ai/phases/PHASE-01/retrospective.md` with `type: retrospective` and five sections in order | `tests/improvement/test_phase_retrospective.py::test_phase_retrospective_persists_row_and_document` |
| 3 | Given two calls on different gate rounds Then one row, one file, document `version == 2` | `tests/improvement/test_phase_retrospective.py::test_second_round_overwrites` |
| 4 | Given `with_narrative=True` Then `NotSupported` naming `E10-S07` | `tests/improvement/test_phase_retrospective.py::test_narrative_not_supported` |
| 5 | Given transitions where items spend 10 h in `LEAD_DEV_REVIEW` and 4 h in `IMPLEMENTING` When `top_bottleneck` Then it starts with `LEAD_DEV_REVIEW: 10.0 h` | `tests/improvement/test_retrospective_rules.py::test_top_bottleneck_largest_dwell` |
| 6 | Given equal dwell in two states Then the alphabetically first state wins; given no events Then `"none"` | `tests/improvement/test_retrospective_rules.py::test_top_bottleneck_tie_and_empty` |
| 7 | Given 3 bugs under FEAT-0002 and 3 under FEAT-0001 with a higher max severity on FEAT-0002 When `top_defect` Then it names FEAT-0002 | `tests/improvement/test_retrospective_rules.py::test_top_defect_count_then_severity` |
| 8 | Given a retrospective When `render_retrospective` Then the Metrics table lists the §115 figures first and in order | `tests/improvement/test_retrospective_rules.py::test_render_metrics_order` |
| 9 | Given `ON_PHASE_REVIEW_START` fired Then the retrospective file exists, `ctx.payload["retrospective_written"] is True`, and the package built after it has `retrospective_id == "RETRO-PHASE-01"` | `tests/hooks/test_builtins_phase_retrospective.py::test_hook_writes_retro_before_package` |
| 10 | Given `phase_retrospective` raising When the hook fires Then hook `FAILED`, no exception propagates, `retrospective_written` absent | `tests/hooks/test_builtins_phase_retrospective.py::test_hook_failure_is_tolerated` |
| 11 | Given a phase stuck in `EVIDENCE_REVIEW` (retrospective hook failed once) When `request_phase_review` is called again with the hook healthy Then `USER_GATE`, exactly one `request_review` and one `package_ready` transition in the ledger | `tests/orchestrator/test_request_phase_review_resume.py::test_review_resumes_from_evidence_review` |
| 12 | Given `walk improvement retro PHASE-01 --json` Then exit 0 and JSON validates as `Retrospective`; given `PHASE-99` Then exit 1 | `tests/cli/test_cmd_improvement_retro.py::test_retro_cli_json_and_unknown_phase` |
| 13 | Given any test in this story Then no `AGENT_RUN_STARTED` event is written | `tests/improvement/test_phase_retrospective.py::test_no_agent_run_started` |

#### Evidence required
- Quality gate output.
- Demo on the fixture repo after a review: `cat .ai/phases/PHASE-01/retrospective.md` (Metrics table + Top Bottleneck + Top Defect); `walk improvement retro PHASE-01 --json | head -20`; `walk phase evidence PHASE-01 --json` showing `retrospective_id`.

#### Notes
- INTERFACES §1.15, §6 (`walk improvement retro` `[MVP skeleton]`); ARCHITECTURE §4.1 `ON_PHASE_REVIEW_START` default attachment, §8 layout (`phases/PHASE-01/retrospective.md`); §115 example fixes the display order.
- WBS §3.9 reconciliation (E07-X01 step 5): `RETRO.md.j2` stays untouched here; E10-S07 owns narrative and the `.ai/improvements/RETRO-PHASE-NN.md` copy shown in ARCHITECTURE §8.
- Bottleneck and defect definitions are planner choices (no requirement fixes them); they live in one module so E10 can replace them under a `BehaviorVersion`.
- `BUG_CREATED.payload.parent_id` and `.severity` are a normative payload contract (DOMAIN-MODEL §4.12 "Ledger payload contracts", written by E03-S14 `BugIntake`): `parent_id = bug.parent_id or bug.related_feature_id` (may be `null` → grouped under `"none"`), `severity` = severity at creation. This story never reads the `work_items` table for them.
- `NEW NAME:` `RetrospectiveRepository`, `RETROSPECTIVE_SECTIONS`, `top_bottleneck`, `top_defect`, `render_retrospective` (`walk.improvement.retrospective`), hook `builtin.phase_retrospective`, retrospective id convention `RETRO-<PHASE-id>`.
- Commit subject: `feat: add metrics-only phase retrospective (E07-S08)`.

#### Evidence (filled by implementer)
_pending_

---

### E07-S09 — Phase report and `ON_PHASE_COMPLETE`

**Status:** TODO
**Type:** feat
**Requirements:** §83, §70, §90, §84, §137 (Inv. 9, 14)
**Depends on:** E07-S05
**Effort:** LOW   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
When a phase reaches `COMPLETE` the `ON_PHASE_COMPLETE` MUST attachment writes `.ai/reports/phases/PHASE-NN.md` — a derived report of gate history, delivered scope, open issues, cost and links to the final evidence package and retrospective — through a basic `MemoryManager.write_report`, updates the phase document's `Status`/`Gate History`, and a kernel restart repairs a completed phase whose report is missing.

#### Scope
- In: `render_phase_report` + `PHASE_REPORT_SECTIONS`, `DefaultMemoryManager.write_report` (kind `phase` only), MUST hook `builtin.phase_complete_report`, phase document `Status`/`Gate History` update, startup repair `repair_phase_reports`.
- Out: `ReportQuery`/`PhaseReportQuery`, other report kinds, secret refusal and `walk report --write` (E09-S01/S02 — they replace this renderer and extend `write_report`); any learning promotion (the former `MemoryManager.promote_phase_learnings()` default attachment was removed from ARCHITECTURE §4.1, see Notes).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/phase_report.py` | create | `render_phase_report`, `PHASE_REPORT_SECTIONS` |
| `src/walk/orchestrator/service.py` | modify | `DefaultOrchestrator.repair_phase_reports` (called from the startup sequence after recovery) |
| `src/walk/orchestrator/__init__.py` | modify | re-exports `render_phase_report`, `PHASE_REPORT_SECTIONS` |
| `src/walk/memory/service.py` | modify | `DefaultMemoryManager.write_report` |
| `src/walk/memory/paths.py` | modify | `report_path` |
| `src/walk/orchestrator/builtin_hooks.py` | modify | `phase_complete_report` (hook `builtin.phase_complete_report`); `BuiltinHookDeps.retrospectives` |
| `src/walk/cli/composition.py` | modify | — (hook deps wiring) |
| `tests/orchestrator/test_phase_report.py` | create | — |
| `tests/orchestrator/test_phase_report_recovery.py` | create | — |
| `tests/memory/test_write_report_basic.py` | create | — |
| `tests/hooks/test_builtins_phase_complete.py` | create | — |

#### Interface contract
`MemoryManager.write_report(kind, subject_id, markdown) -> str` per INTERFACES §1.8.
```python
# src/walk/orchestrator/phase_report.py
PHASE_REPORT_SECTIONS = ("Summary", "Gate History", "Scope Delivered", "Open Issues", "Production Cost", "Retrospective", "Evidence Package")

def render_phase_report(phase: Phase, decisions: list[LedgerEvent], package: PhaseEvidencePackage | None,
                        retrospective: Retrospective | None, cost: dict[CostCategory, float], generated_at: datetime) -> str:
    """'# Phase report <id> — <name>' then one '## <section>' per PHASE_REPORT_SECTIONS.
    Summary: state, started_at, completed_at, gate rounds, last decision. Gate History: table round | decision | at | feedback excerpt (≤ 120 chars)
    from PHASE_GATE_DECISION events. Scope Delivered / Open Issues: from package (stories_completed, stories_open, open_issues).
    Production Cost: category | usd + total. Retrospective: §115 figures + top bottleneck/defect, or '_none_'.
    Evidence Package: repo-relative link to phase_evidence_package_path(phase.id) and its gate_round, or '_none_'."""

# src/walk/memory/paths.py
def report_path(kind: str, subject_id: str) -> str: ...   # kind "phase" → "reports/phases/<subject_id>.md"

# DefaultMemoryManager
async def write_report(self, kind: str, subject_id: str, markdown: str) -> str:
    """kind == "phase" only, else NotSupported("E09-S02"). Atomic overwrite at report_path; no front matter, no memory_index row,
    no CONTEXT_UPDATED (derived artefact, E09-S02 contract). Returns repo-relative path."""

# ON_PHASE_COMPLETE  builtin.phase_complete_report  prio 10  required=True  (MUST, ARCHITECTURE §4.1)
#   decisions = ledger.query(kinds=[PHASE_GATE_DECISION], phase_id=…); package = read back from evidence-package.md (E07-S04 reader);
#   retrospective = deps.retrospectives.get(f"RETRO-{phase_id}"); cost = deps.costs_reader.cost_of(phase_id=phase_id)
#   → MemoryManager.write_report("phase", phase_id, render_phase_report(...))
#   → MemoryManager.apply_updates([ContextUpdate(doc=phase_doc_path, section="Status", REPLACE, f"COMPLETE at {iso}"),
#                                  ContextUpdate(doc=phase_doc_path, section="Gate History", REPLACE, <gate history table>)], actor=KERNEL)

# DefaultOrchestrator
async def repair_phase_reports(self) -> list[PhaseId]:
    """Startup (ARCHITECTURE §3.4, after recovery): for every COMPLETE phase of the project whose report_path("phase", id) is missing,
    re-fire ON_PHASE_COMPLETE hooks (no transition). Returns repaired ids."""
```

#### Behavior
1. The report is derived from persisted facts only (ledger, `phases`, evidence-package document, `retrospectives`, `cost_records`); no agent run, no provider call (§83, Inv. 9).
2. `render_phase_report` is deterministic for equal inputs; sections appear in `PHASE_REPORT_SECTIONS` order; empty inputs render `_none_`.
3. Gate History lists every gate decision of the phase across all rounds (e.g. `1 REWORK`, `2 GO`), oldest first.
4. Hook failure is `FAIL_CLOSED`: `decide(GO)` raises `HookFailed` after the decision and the `COMPLETE` transition are committed, the successor is not started (E07-S05 rule 4 ordering), and the CLI exits 2 naming the hook; the user may `walk phase start` the successor; the next kernel start repairs the missing report.
5. `write_report` overwrites the same file on every call; a second `ON_PHASE_COMPLETE` (repair) produces byte-identical output when inputs are unchanged.
6. The phase document `Status` becomes `COMPLETE at <iso>` and `Gate History` is replaced with the same table as the report; other sections are untouched (section-level update, E04 `apply_updates`).
7. `repair_phase_reports` re-fires hooks only; it writes no `PHASE_TRANSITION` and no `PHASE_GATE_DECISION`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a phase with decisions REWORK (round 1) and GO (round 2), a package and a retrospective When `render_phase_report` Then 7 `## ` headings in order, Gate History rows `1 REWORK` then `2 GO`, Retrospective shows `First-pass success` | `tests/orchestrator/test_phase_report.py::test_render_sections_and_gate_history` |
| 2 | Given no package and no retrospective When `render_phase_report` Then those sections read `_none_` | `tests/orchestrator/test_phase_report.py::test_render_missing_inputs` |
| 3 | Given equal inputs When rendered twice Then identical strings | `tests/orchestrator/test_phase_report.py::test_render_deterministic` |
| 4 | Given `write_report("phase", "PHASE-01", md)` twice Then one file `.ai/reports/phases/PHASE-01.md` without front matter, no `memory_index` row, no `CONTEXT_UPDATED` | `tests/memory/test_write_report_basic.py::test_write_report_phase_overwrite_plain` |
| 5 | Given `write_report("cost", …)` Then `NotSupported` naming `E09-S02` | `tests/memory/test_write_report_basic.py::test_write_report_other_kinds_not_supported` |
| 6 | Given PHASE-01 at USER_GATE When `decide(GO)` Then `.ai/reports/phases/PHASE-01.md` exists and the phase document `Status` starts with `COMPLETE at` | `tests/hooks/test_builtins_phase_complete.py::test_go_writes_phase_report_and_updates_doc` |
| 7 | Given the report hook raising When `decide(GO)` Then `HookFailed`, PHASE-01 `COMPLETE`, PHASE-02 still `PLANNED` | `tests/hooks/test_builtins_phase_complete.py::test_report_failure_fails_closed` |
| 8 | Given a COMPLETE phase without report file When the kernel starts Then `repair_phase_reports() == [PHASE-01]`, the file exists, and no new `PHASE_TRANSITION` | `tests/orchestrator/test_phase_report_recovery.py::test_startup_repairs_missing_report` |
| 9 | Given a COMPLETE phase with its report When the kernel starts Then `repair_phase_reports() == []` | `tests/orchestrator/test_phase_report_recovery.py::test_startup_skips_existing_report` |

#### Evidence required
- Quality gate output.
- Demo on the fixture repo at `USER_GATE`: `walk phase gate PHASE-01 --decision GO`; `cat .ai/reports/phases/PHASE-01.md`; `head -30 .ai/phases/PHASE-01.md` showing `Status` and `Gate History`.

#### Notes
- ARCHITECTURE §4.1 `ON_PHASE_COMPLETE` row, §8 `reports/phases/`; INTERFACES §1.8 `write_report`. WBS §3.5: no ledger event is written by this hook (it is not a §4.3 write point); `HOOK_EXECUTED` comes from `HookManager`.
- E09-S02 replaces the hook body with `LedgerManager.report("phase", id)` + `write_report` and adds kind validation/secret refusal; keep `write_report`'s observable contract (plain overwrite, no index) identical to E09-S02 AC 7 so that story only extends it.
- `promote_phase_learnings()` is dropped (architect decision 2026-10-06): phase learnings are captured by the `ON_PHASE_REVIEW_START` retrospective (E07-S08) and reach kernel scope only through explicit `walk improvement promote` (E10-S06, ADR-0008 D-2 — no automatic promotion). ARCHITECTURE §4.1 `ON_PHASE_COMPLETE` no longer lists it; nothing to implement.
- `NEW NAME:` `render_phase_report`, `PHASE_REPORT_SECTIONS` (`walk.orchestrator.phase_report`), `report_path`, `DefaultOrchestrator.repair_phase_reports`, hook `builtin.phase_complete_report`, `BuiltinHookDeps.retrospectives`; basic `DefaultMemoryManager.write_report` (extended by E09-S02).
- Commit subject: `feat: add phase report on phase completion (E07-S09)`.

#### Evidence (filled by implementer)
_pending_

---

### E07-S10 — Epic gate: §134 phase test (e2e)

**Status:** TODO
**Type:** feat
**Requirements:** §134, §136, §56, §60, §66–§72, §89, §90, §93, §115, §137 (Inv. 7, 14), §140
**Depends on:** E07-S01, E07-S06, E07-S07, E07-S08, E07-S09
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** QC   **Reviewer role:** LeadDev

#### Goal
The §134 MVP Phase Test passes end-to-end with fakes: a small GDD compiled into one phase (E06) runs autonomously with `max_parallel_agents=3`, its stories go through review and QC with one fix loop, the kernel survives a crash mid-phase, the phase stops itself at the gate with `evidence-package.md` and `retrospective.md`, and the user exercises REWORK, CHANGE (denied), GO (report + next phase started) and STOP — every decision recorded and user-only.

#### Scope
- In: `tests/e2e/test_e07_gate.py`, `e07_scenario` fixture and `E07Scenario`, fake-adapter scripts for PO rework intake and LEAD_DEV/PO change analysis.
- Out: production code changes (any defect found → `bugfix` story `E07-Bxx`); real providers, network, real Unity (CI and Unity are `tests/fakes`).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `tests/e2e/test_e07_gate.py` | create | — |
| `tests/e2e/conftest.py` | modify | `e07_scenario` fixture, `E07Scenario` `(verify: builds on e06_scenario from E06-S08)` |
| `tests/fakes/fake_model_adapter.py` | modify | — (script helpers `rework_intake_output(drafts)`, `change_analysis_output(findings, plan)`; per-run artificial latency on `FakeClock` to make concurrency observable) |

#### Interface contract
Fixture `e07_scenario(e06_scenario) -> E07Scenario` (`WalkModel` in conftest): `handle: KernelHandle`, `project_key: ProjectKey`, `phase_ids: list[PhaseId]` (`PHASE-01`, `PHASE-02` from the E06 small GDD), `story_ids: list[WorkItemId]` (PHASE-01 scope, ≥ 4 stories over ≥ 2 features), `qc_reject_story_id: WorkItemId`, `repo_path: Path`. Settings: `KernelSettings(max_parallel=3, …)`; overrides: `FakeModelAdapter` providers `fake-codex/sim` (SENIOR_DEV), `fake-claude/sim` (LEAD_DEV, QC, PRODUCT_OWNER), `FakeUnityProvider`, `LocalCiProvider` with scripted green jobs, `FakeCodeGraphProvider` (fixture graph), `LocalWorkProvider`, `FakeClock`, `SequentialIdFactory`; real temp git repo (`tests/conftest.py::tmp_game_repo`). Each step below is one test, executed in order on the fixture's cached state (E04-S15 pattern).

#### Behavior
Scenario steps:
1. **Start.** `walk phase start PHASE-01` (offline) → `ACTIVE`, `PHASE_BASELINE` artifact, PHASE budgets (E07-S02).
2. **Parallel execution.** `walk run` ticks until 3 runs are simultaneously `RUNNING`; peak concurrency == 3, never > 3; runs of one role never exceed its `max_parallel_runs`; concurrent runs use distinct worktrees and branches; no two dependent stories run together (E07-S01, §60).
3. **QC fix loop.** QC rejects `qc_reject_story_id` once (`BUG` created, `fix_loops == 1`), the fix passes review and QC; every story reaches `COMPLETE`.
4. **Crash and recovery.** Mid-step 2, the kernel is stopped with `Orchestrator.stop(drain=False)` while ≥ 2 runs are `RUNNING`; a new kernel instance starts; recovery resumes from checkpoints (`RECOVERY_RESUMED` per interrupted run), no item is scheduled twice (`schedule:` keys), the phase is still `ACTIVE` with the same `baseline_artifact_id` (§89–§90).
5. **Autonomous stop at the gate.** When all scope features are terminal the tick requests the review: phase `USER_GATE`, `gate_round == 1`, `.ai/phases/PHASE-01/evidence-package.md` (14 sections) and `retrospective.md` (5 sections, `stories` equals completed stories) exist, `PhaseEvidencePackage.retrospective_id == "RETRO-PHASE-01"`; further ticks admit nothing (§68).
6. **REWORK.** `walk phase gate PHASE-01 --decision REWORK --feedback "Shotgun feels weak"` → `REWORK`, intake task for PRODUCT_OWNER; the scripted PO output creates 2 tasks (`rework:design`, `rework:vfx`) inside scope; phase `ACTIVE`; the tasks complete; the gate is reached again with `gate_round == 2` and a new evidence package (`id` ends `EP2`).
7. **CHANGE denied.** `walk phase gate PHASE-01 --decision CHANGE --feedback "Replace energy with stamina"` → `CHANGE_ANALYSIS`; LEAD_DEV then PO analysis runs; `change-plan-2.md` lists all ten `CHANGE_PLAN_SECTIONS` with graph-expanded `Affected Code`; `walk deny APV-NNNN` → `USER_GATE`, `gate_round == 2`.
8. **GO.** `walk phase gate PHASE-01 --decision GO` → PHASE-01 `COMPLETE`, `.ai/reports/phases/PHASE-01.md` with Gate History `1 REWORK`, `2 CHANGE`, `2 GO`; PHASE-02 `ACTIVE` with its own baseline; `walk status --json` shows `current_phase.id == "PHASE-02"`.
9. **STOP.** `walk phase stop PHASE-02 --reason "end of gate test"` → `STOPPED`, project paused, one `USER_OVERRIDE`.
10. **Audit.** Ledger `PHASE_GATE_DECISION` events are exactly REWORK, CHANGE, GO in that order, each with actor role `USER`; no `PHASE_GATE_DECISION` or `phase_event("decide:*")` by a non-USER actor; every `WORK_ITEM_CREATED` during the phase is a descendant of PHASE-01 scope or a phase-intake task (Inv. 7); `walk ledger query --phase PHASE-01 --kind PHASE_TRANSITION` lists `start, request_review, package_ready, decide:REWORK, rework_planned, request_review, package_ready, decide:CHANGE, change_rejected, decide:GO`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the E06 planned phase When `walk phase start PHASE-01` Then `ACTIVE` with baseline and PHASE budget | `tests/e2e/test_e07_gate.py::test_phase_starts_with_baseline_and_budget` |
| 2 | Given the running kernel Then peak concurrent runs == 3, per-role limits respected, distinct worktrees, no dependent pair concurrent | `tests/e2e/test_e07_gate.py::test_parallel_execution_respects_limits` |
| 3 | Given the QC-rejected story Then one bug, `fix_loops == 1`, story finally `COMPLETE`; all scope stories `COMPLETE` | `tests/e2e/test_e07_gate.py::test_qc_fix_loop_and_all_stories_complete` |
| 4 | Given a crash with ≥ 2 running runs When the kernel restarts Then each interrupted run has `RECOVERY_RESUMED`, no duplicate scheduling, phase `ACTIVE` with unchanged baseline | `tests/e2e/test_e07_gate.py::test_phase_survives_kernel_crash` |
| 5 | Given all features terminal Then phase `USER_GATE` round 1, both documents exist with the expected sections, `retrospective_id` set, and a further tick admits 0 | `tests/e2e/test_e07_gate.py::test_autonomous_stop_with_evidence_and_retrospective` |
| 6 | Given REWORK feedback Then 2 in-scope rework tasks are created, completed, and the phase returns to `USER_GATE` round 2 with package `EP2` | `tests/e2e/test_e07_gate.py::test_rework_round_trip` |
| 7 | Given CHANGE feedback Then a change plan with 10 sections and graph-expanded code is recorded, a `CHANGE_PLAN` approval is pending, and denying it returns to `USER_GATE` round 2 | `tests/e2e/test_e07_gate.py::test_change_analysis_and_denial` |
| 8 | Given GO Then PHASE-01 `COMPLETE`, phase report Gate History has 3 rows, PHASE-02 `ACTIVE`, `status.current_phase.id == "PHASE-02"` | `tests/e2e/test_e07_gate.py::test_go_completes_reports_and_starts_next` |
| 9 | Given `walk phase stop PHASE-02` Then `STOPPED`, `paused == true`, one `USER_OVERRIDE` | `tests/e2e/test_e07_gate.py::test_stop_phase_pauses_project` |
| 10 | Given the ledger Then gate decisions REWORK, CHANGE, GO in order, all by USER, and the PHASE-01 transition sequence equals Behavior 10 | `tests/e2e/test_e07_gate.py::test_gate_decisions_user_only_and_ordered` |
| 11 | Given all `WORK_ITEM_CREATED` events of the scenario Then each item is in PHASE-01 scope or a `phase-intake` task | `tests/e2e/test_e07_gate.py::test_no_work_outside_phase_scope` |

#### Evidence required
- Quality gate output including `tests/e2e/test_e07_gate.py` (11 passed).
- Demo transcript on the fixture repo after the test: `walk phase list`, `walk phase evidence PHASE-01 | head -40`, `cat .ai/phases/PHASE-01/retrospective.md`, `cat .ai/reports/phases/PHASE-01.md`, `walk ledger query --phase PHASE-01 --kind PHASE_GATE_DECISION`, `walk status --json`.

#### Notes
- WBS §4 E07 epic gate and §9 row "Phase completes · Evidence package · Retrospective · GO/REWORK/CHANGE/STOP"; §134 flow (Small GDD → One Phase → Multiple Stories → Autonomous Execution → QC → Evidence → Phase Gate).
- The crash step (4) proves the epic goal "phase survives a kernel crash" (§89–§90) with E01/E02 recovery; no E07 story adds recovery code beyond idempotency keys and E07-S08/S09 resume paths.
- Gate uses only `tests/fakes` adapters and a real temp git repo with `LocalWorkProvider`; no network, no wall clock (`FakeClock`). Any production change needed to pass is a separate `bugfix` story; this commit touches tests only.
- `e07_scenario` is reused by the E08/E09 gates (E09-S07 `e09_scenario(e07_scenario)`); keep its fields stable.
- `NEW NAME:` `e07_scenario`, `E07Scenario`, fake script helpers `rework_intake_output`, `change_analysis_output`.
- Commit subject: `feat: add epic 07 gate autonomous phase test (E07-S10)`.

#### Evidence (filled by implementer)
_pending_

---

### E07-R01 — Review E07

**Status:** TODO
**Type:** docs
**Requirements:** §137 (Inv. 7, 14), §134, §69, §72, §83, §115
**Depends on:** E07-S10
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
An independent agent instance (different model than the E07 implementer where possible, §23) verifies every E07 story against the Definition of Done and Invariants 7 and 14, confirms the phase guard payload producers and derived-document rules hold in code, and records defects as `bugfix` stories before E08/E09 start.

#### Scope
- In: stories E07-X01, E07-S01…S10 and their commits; `INTERFACES.md`/`DOMAIN-MODEL.md`/ADR-0009 deltas (D-5 container note, `ApprovalRequest.kind`, `ChangeImpact`, `PhaseEvidencePackage.known_limitations_sources`); WBS §6 register entries from this epic; `story/<ID>` branch merges (`--no-ff`).
- Out: fixing defects (each becomes `E07-Bxx`).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-07-autonomous-phase.md` | modify | — (review record appended; `E07-Bxx` stories appended if any) |
| `docs/02-work-breakdown/WBS.md` | modify | — (status rows, §6 register) |
| `docs/01-architecture/INTERFACES.md`, `docs/01-architecture/DOMAIN-MODEL.md`, `docs/01-architecture/adr/ADR-0009-runtime-topology-and-open-questions.md` | modify (only if drift found) | — |
| `tests/architecture/test_phase_decision_user_only.py` | create | — |
| `tests/architecture/test_phase_guard_payloads.py` | create | — |
| `tests/architecture/test_phase_documents_derived.py` | create | — |

#### Interface contract
Reviewer protocol, IMPLEMENTATION-PROTOCOL.md "Reviewer protocol" steps 1–5.

#### Behavior
1. For each story: `git show <sha>`; Files table == changed files (extra files need commit-body justification); every acceptance-criterion test exists and passes; coverage ≥ 90 % for touched modules.
2. Invariant 14: `phase_event(…, "decide:…")`, `"change_plan_approved"`, `"change_rejected"`, `"reopen"` and `"stop"` are raised only from `src/walk/orchestrator/phase_gate.py` (and `service.py` delegation), always with a USER actor resolved from the CLI/approval; `AgentOutput` has no field that can carry a `PhaseDecision`.
3. Invariant 7: every work item created by a phase-intake run is inside `Phase.scope_epic_ids` or is itself the intake task; change-analysis runs create nothing (E07-S07 rule 3).
4. Every guard of `phase_workflow v1.0` (INTERFACES §3.4, `src/walk/workflow/tables/phase_workflow.yaml`) reads a payload key that some non-test module under `src/walk/` writes (header `NEW NAME:` table of this epic).
5. Derived documents: `evidence_packager.py`, `change_impact.py` (render part), `phase_report.py` and `improvement/retrospective.py` import nothing from `walk.agents`, `walk.runtime`, `walk.model_router` and start no agent run.
6. ADR-0009 D-5 states the container decision taken in E07-S01; WBS §3.9 records the `ANALYSIS`/`RETRO` template split (E07-X01 step 5).
7. `NEW NAME:` items of E07 (epic header table and story Notes) are present in WBS §6 or listed in the review note for the architect; `promote_phase_learnings` is dropped (E07-S09 Notes), not a pending item.
8. All `story/E07-*` branches are merged `--no-ff` into `main` after this review and the gate passes on `main`.
9. Defects → `E07-Bxx` stories using the template; commit `docs: review epic 07 stories E07-S01..S10 (E07-R01)`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given each E07 story When the DoD checklist is applied Then every box is checked or an `E07-Bxx` story exists | manual checklist recorded in this story's Evidence |
| 2 | Given `src/walk` When parsing calls that raise phase events `decide:*`, `change_plan_approved`, `change_rejected`, `reopen`, `stop` Then the only callers are in `walk/orchestrator/phase_gate.py` or `walk/orchestrator/service.py` | `tests/architecture/test_phase_decision_user_only.py::test_phase_decisions_raised_only_by_phase_gate` |
| 3 | Given `phase_workflow.yaml` guards and the WBS §3.4 payload-key map When `src/walk` is scanned Then every key read by a phase guard is written by a non-test module | `tests/architecture/test_phase_guard_payloads.py::test_every_phase_guard_payload_key_produced` |
| 4 | Given the four derived-document modules When their imports are parsed Then none imports `walk.agents`, `walk.runtime` or `walk.model_router` | `tests/architecture/test_phase_documents_derived.py::test_phase_document_builders_do_not_import_agents` |
| 5 | Given the quality gate on `main` after the merges Then green with overall coverage ≥ 85 % and `tests/e2e/test_e07_gate.py` passing | gate output in Evidence |

#### Evidence required
- Checklist per story (ID → DoD items → OK/defect id), including Inv. 7/14 findings.
- Quality gate output on `main` after the review commit and merges; `walk phase list` on the gate fixture repo as a sanity demo.
- List of `E07-Bxx` stories created (or "none") and the architect note listing open `NEW NAME:` items.

#### Notes
- Tests 2–4 are architecture tests created by the reviewer (review tasks may add tests, never production code).
- E08-X01 and E09-X01 depend on this review (WBS §5); a `BLOCKER` bugfix story stops both until fixed (WBS §2 rule 2).
- Commit subject: `docs: review epic 07 stories E07-S01..S10 (E07-R01)`.

#### Evidence (filled by implementer)
_pending_

---

