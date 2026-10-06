# EPIC-10 — Continuous Improvement

**Roadmap stage:** §135 Stage 10
**Goal.** Production evidence turns into controlled, versioned behaviour change: observations (agent-made and ledger-detected) become hypotheses and candidates, candidates are reviewed by the §104 authority tier, approved candidates become `BehaviorVersion`s that roll out through `rollout_workflow` (DRAFT → EXPERIMENTAL → LIMITED → DEFAULT → DEPRECATED, with rollback), projects pin the versions they run, experiments (A/B by work-item hash, shadow evaluation) and §116 metrics measure the outcome, and every step is a ledger event — while project learning stays in `.ai/improvements/` and kernel learning in `$WALK_HOME/.improvement/` (promotion is explicit).
**Requirements.** §94–§121 (all of Continuous Improvement), §6.11, §32 (hook attachments `ON_IMPROVEMENT_OBSERVATION`, `ON_PHASE_REVIEW_START`, `ON_PHASE_GATE_DECISION`, `ON_AGENT_START`), §82/§105 (`behavior_versions` on events, pins), §137 (Inv. 13; Inv. 5 for PROCESS decisions), §138 (Workflow Drift), §139 (experiment methodology → ADR-0008 addendum).
**Epic gate.** `tests/e2e/test_e10_gate.py`: a repeated-fallback signal produces an observation, `walk improvement promote` copies it to kernel scope, a MEDIUM candidate is approved by PO, `register_version` creates `feature_workflow 1.1` at `LIMITED` with a changelog entry, the project pins it, ledger events carry `behavior_versions`, and `rollback` returns to `DRAFT`.
**Branching.** Every story uses `story/<ID>-<slug>` + worktree (COMMIT-POLICY §4); merge `--no-ff` after E10-R01.
**Preconditions.** E09-R01 `DONE` with no `BLOCKER` bugfix stories; `main` green. E10 runs in parallel with E11 (WBS §7.1): E10 stories never touch `walk.workflow.release`, `walk.orchestrator.release*`, `walk.integrations.store*` or `cmd_rc.py`; the one shared file is `src/walk/workflow/tables/story_workflow.yaml` (see E10-S07 Notes).
**Refine first.** E10-X01 re-validates every Files table below against the `src/walk/` tree as it exists after E09 — E01 (S18–S31), E03 (S06–S20), E05–E09 stories were planned at index level when this file was written; paths and symbols marked `(verify)` are the ones most likely to differ.

## Story index

| ID | Title | Depends on | Effort |
|---|---|---|---|
| E10-X01 | Refine E10 against codebase | E09-R01 | LOW |
| E10-S01 | Observations full: `observe`, `.ai/improvements/`, `walk improvement observations` | E10-X01, E04-S13 | MEDIUM |
| E10-S02 | `detect_signals` from ledger | E10-S01 | MEDIUM |
| E10-S03 | Kernel store `$WALK_HOME/.improvement/` and kernel DB migrations | E10-X01 | MEDIUM |
| E10-S04 | Candidates and risk-tier review, `walk improvement candidates` | E10-S03, E05-S01 | HIGH |
| E10-S05 | `BehaviorVersion` registry, `rollout_workflow`, pins, changelog | E10-S04, E02-S04 | HIGH |
| E10-S06 | Promotion and pattern/anti-pattern registries | E10-S03 | MEDIUM |
| E10-S07 | Retrospectives with narrative and PROCESS_ARCHITECT constitution | E10-S01, E07-S08 | MEDIUM |
| E10-S08 | Experiments: A/B by work-item hash and shadow evaluation | E10-S05 | HIGH |
| E10-S09 | Improvement metrics and report | E10-S02, E09-S02 | MEDIUM |
| E10-S10 | Epic gate: observation → versioned rollout (e2e) | E10-S06, E10-S07, E10-S08, E10-S09 | MEDIUM |
| E10-R01 | Review E10 | E10-S10 | MEDIUM |

## Reading order for implementers

1. `WBS.md` §2–§3 (especially §3.4 payload-key pattern, §3.5 ledger write points, §3.6 fakes/e2e, §3.7 CLI layout — `improvement` command group).
2. ADR-0008 (D-1 two stores, D-2 explicit promotion, D-3 versioned artefacts, D-4 pins, D-5 rollout, D-6 authority tiers, D-7 agents cannot write behaviour, D-8 changelog, D-9 experiments), ADR-0006 (D-2 kernel executes side effects, D-3 rule semantics), ADR-0009 (D-3 IPC via `commands`, D-8 credentials, D-15), ADR-0013 (constitution schema, D-6 immutability).
3. `INTERFACES.md` §1.15 (`ImprovementManager`), §3.7 (`rollout_workflow`), §1.14 (`LedgerManager`, `EvidenceManager`, `TelemetryManager`), §1.9 (`DecisionManager.record`), §1.10 (`PermissionManager`), §1.13 (`ToolInvoker`, `OutputApplier`), §1.3 (`TransitionTable`, `Guard`), §4 (routing table), §6 (`walk improvement …`, `walk version`, `walk report improvement`).
4. `DOMAIN-MODEL.md` §2 (`OBS-`/`OBS-K-`/`IMP-`/`PATTERN-`/`ANTI-`/`EXP-`/`RETRO-` ids), §3 (`LearningScope`, `ImprovementScope`, `RolloutStage`, `ImprovementRisk`, `CandidateState`, `LedgerEventKind`, `DecisionCategory.PROCESS`, `ApprovalRequest.kind == "IMPROVEMENT"`), §4.14 (all improvement entities), §4.12 (`RetrospectiveMetrics`, `LedgerEvent.behavior_versions`), §6.2 (`improvement_*`, `patterns`, `retrospectives`, `behavior_versions`, `experiments`, `kernel_changelog`; table → DB mapping).
5. `ARCHITECTURE.md` §4.1 (hook rows named in item 1), §4.3 (`improvement.ImprovementManager` write point: `IMPROVEMENT_OBSERVATION`, `IMPROVEMENT_CANDIDATE`, `BEHAVIOR_VERSION_CHANGED`), §6 (`BoundaryAuditor` forbidden paths), §7 (Inv. 13), §8 (`improvements/` layout), §9 (`$WALK_HOME/.improvement/` layout), §2.2 (improvement may import `agents`, `model_router`, `memory`, `decisions`, `debate`, `skills`, `hooks`, `workflow`, `telemetry`; never `runtime`, `orchestrator`, `permissions`, `tools`, `integrations`).
6. `requirements/WAL_K_REQ.md` §94–§121, §6.11, §82, §105, §138 "Workflow Drift".
7. Existing files named in each story's Files table (E02-S04, E04-S13, E07-S05/S08, E09-S02/S05/S06) and their tests.

Parallel sets (WBS §8): `{S01→S02} ∥ {S03→S06}`; `{S07} ∥ {S08} ∥ {S09}` after their dependencies; S04 after S03 and E05-S01; S05 after S04; S10 last.

**Scope/store rule (binding for every story).** Every improvement entity carries `scope: LearningScope`. `PROJECT` rows live in the project DB and documents in `<repo>/.ai/improvements/` (written only through `MemoryManager.write`, ADR-0003 D-4); `KERNEL` rows live in `$WALK_HOME/kernel.db` and documents in `$WALK_HOME/.improvement/<folder>/` (written through `KernelImprovementStore`, E10-S03, using the same front-matter schema and `walk.persistence.atomic_write`). Ledger events are always written to the **project** ledger of the kernel instance performing the action (the kernel DB has no ledger). Nothing is written to `$WALK_HOME` by S01, S02, S07 or S09; nothing is promoted automatically (§110).

## `NEW NAME:` items introduced by this epic (to be added to WBS.md §6 by E10-X01)

| Item | Story | Why |
|---|---|---|
| `ObservationDraft.evidence_ids`, `ObservationDraft.ledger_seq_refs` (optional fields); `ObservationQuery`; `ObservationRepository.query/exists/mark_promoted`; `ImprovementManager.list_observations`; `walk improvement show <ID>`; `OBSERVATION_DEDUPE_WINDOW_S`; module `walk.improvement.documents` | S01 | §96 observations must link evidence and ledger rows; INTERFACES §1.15 has no query/listing method |
| module `walk.improvement.signals` (`SignalRule`, `SignalMatch`, `SignalDetector`, `load_signal_rules`) and data file `signals.yaml`; hook callable `phase_review_detect_signals`; `walk improvement detect`; `CommandConsumer` command `improvement.detect` | S02 | §99 sources are declared as data; INTERFACES §1.15 names `detect_signals` without rules or a CLI |
| module `walk.improvement.kernel_home` (`KernelHome`, `KernelConfig`, `WALK_HOME_ENV`, `DEFAULT_WALK_HOME`, `IMPROVEMENT_FOLDERS`); module `walk.improvement.store` (`KernelImprovementStore`, `ProjectImprovementStore`, `store_for`); repositories `CandidateRepository`, `PatternRepository`, `BehaviorVersionRepository`, `ExperimentRepository`, `ChangelogRepository`; kernel migration `0002_improvement_indexes.sql`; `KernelSettings.walk_home`; `KernelOverrides.kernel_home`; `walk doctor` section `improvement_home`; fixture `tmp_walk_home` | S03 | ARCHITECTURE §9 fixes the layout but no code owns `$WALK_HOME` |
| module `walk.improvement.candidates` (`CANDIDATE_TRANSITIONS`, `CandidateEvent`, `APPROVER_TIERS`, `can_approve`, `candidate_from_observations`); `CANDIDATE_SECTIONS` (`walk.memory.sections`); `ImprovementManager.candidate_event/list_candidates`; `CandidateQuery`; KERNEL tools `improvement.candidate`, `improvement.review` (provider `improvement`); `walk improvement candidates list/new/event/review` | S04 | §97 lifecycle and §104 tiers need data tables and an enforceable channel for agents (§103) |
| `rollout_workflow.yaml` under `walk/workflow/tables/`; module `walk.improvement.rollout` (`RolloutStateMachine`, `ROLLOUT_GUARDS`, `rollout_event_for`, payload keys `candidate_state`, `experiment_defined`, `shadow`, `experiment_evidence_count`, `approver_role`, `risk`, `projects_ran_phase`, `metrics_not_worse`, `changelog_entry_present`, `successor_default_exists`); module `walk.improvement.changelog` (`ChangelogEntry`, `render_changelog`, `changelog_path`); `ChangelogRequired` error; `$WALK_HOME/.improvement/versions/<KIND>/<name>/<version>.<ext>` folder; `BehaviorVersionCatalog.resolve/entries`; `ImprovementManager.rollback/list_versions/pin_version`; `PIN_RISK_BY_KIND`; `walk improvement versions/stage/pin/rollback` | S05 | INTERFACES §3.7 is a table without an engine; ARCHITECTURE §9 has no place for non-builtin artefact versions; INTERFACES §1.15 lacks rollback/pin methods |
| module `walk.improvement.patterns` (`pattern_document`, `anti_pattern_document`, `load_builtin_anti_patterns`, `BUILTIN_ANTI_PATTERNS_PATH`) and data file `defaults/anti_patterns.yaml`; `PATTERN_SECTIONS`, `ANTI_PATTERN_SECTIONS`; `ImprovementManager.register_pattern/register_anti_pattern/list_patterns`; `walk improvement patterns` | S06 | §112–§113 registries have models but no service methods, documents or seeds |
| kernel default constitution `process_architect.md`; module `walk.improvement.retrospectives` (`ANALYSIS_LABEL_PREFIX`, `ANALYSIS_STEP_LABEL_PREFIX`, `analysis_labels`, `analysis_step_of`, `narrative_from_output`); `story_workflow` row `analysis_done` + guard `is_analysis_task`; `ANALYSIS_ROUTES`; `ImprovementManager.retrospective(level, subject_id)`; `RETRO.md.j2` block `process_architect_duties`; `walk improvement retro --narrative` | S07 | §101 role exists only as an `AgentRole` member; a run needs a work item (`AgentExecutor.start`), and no phase-level run mechanism is confirmed |
| module `walk.improvement.experiments` (`ExperimentAssigner`, `arm_for`, `ExperimentResult`, `compare_arms`, `MIN_ARM_SIZE`, `IMPROVEMENT_THRESHOLD`, `REGRESSION_TOLERANCE`, `EXPERIMENT_METRICS`, `ShadowEvaluator`, `RoutingShadowEvaluator`, `EffortShadowEvaluator`); `LedgerEventKind.SHADOW_EVALUATION`; `KernelVersionPins.experiments`; `ImprovementManager.start_experiment/end_experiment/shadow_evaluate/experiment_versions_for`; `AgentExecutor` constructor parameter `versions_for_item`; hook callable `agent_start_shadow_evaluate`; `EXPERIMENT_SECTIONS`; `walk improvement experiments list/show/start/end`; ADR-0008 addendum | S08 | ADR-0008 D-9 fixes the two methods but defers thresholds and names no code; shadow results need a ledger kind |
| `ImprovementMetrics` (`walk.telemetry.models`), `IMPROVEMENT_METRIC_QUERIES`, `compute_improvement_metrics`, `AUTONOMY_QUALITY_FIELDS` (`walk.telemetry.metrics`); `TelemetryManager.improvement_metrics`; `VersionOutcome`, `ImprovementManager.measure_version`; `walk improvement metrics`; `walk report improvement --since` | S09 | §116 lists metrics that `RetrospectiveMetrics` does not cover (E09-S06 Notes) |
| `e10_scenario` fixture, `E10Scenario` (`tests/e2e/conftest.py`) | S10 | Gate fixture |

---

