# EPIC-09 — Production Intelligence

**Roadmap stage:** §135 Stage 9
**Goal.** Reports, cost accounting completeness, dashboard data contract and provenance queries derived solely from the ledger (§83: never agent-reconstructed), so that §82/§88 questions are answerable by SQL alone and future dashboards (ADR-0009 D-14) have a fixed data contract.
**Requirements.** §81–§88, §116 (metrics completeness), §137 (Inv. 9), §6.11, §27 (multi-machine groundwork remains deferred, ADR-0009 D-12 — no story in this epic).
**Epic gate.** `tests/e2e/test_e09_gate.py`: after the E07 phase run, `walk report phase PHASE-01 --write`, `walk report cost PHASE-01`, `walk status --json` and the `v_*` SQLite views return consistent numbers equal to direct ledger aggregation.
**Branching.** Every story uses `story/<ID>-<slug>` + worktree (COMMIT-POLICY §4); merge `--no-ff` after E09-R01.
**Preconditions.** E07-R01 `DONE` with no `BLOCKER` bugfix stories; `main` green. E09 runs in parallel with E08 (WBS §7.1); E09 stories never touch E08 files.
**Refine first.** E09-X01 re-validates every Files table below against the `src/walk/` tree as it exists after E07 — several E01 (S18–S31), E03 (S06–S20) and E07 stories were planned at index level only when this file was written; paths marked `(verify)` are the ones most likely to move.

## Story index

| ID | Title | Depends on | Effort |
|---|---|---|---|
| E09-X01 | Refine E09 against codebase | E07-R01 | LOW |
| E09-S01 | `ReportQuery` and task/feature reports | E09-X01 | MEDIUM |
| E09-S02 | Phase/project/cost/improvement reports, `walk report --write`, `write_report` | E09-S01 | MEDIUM |
| E09-S03 | Cost accounting completeness: CI/compute/time records, roll-ups | E09-X01, E03-S11 | MEDIUM |
| E09-S04 | Dashboard views (`0003_dashboard_views.sql`), `walk status --json`, `/status` | E09-S03 | MEDIUM |
| E09-S05 | Provenance queries and `behavior_versions` on events | E09-S01, E02-S04 | MEDIUM |
| E09-S06 | Metrics completeness and log rotation | E09-S03 | LOW |
| E09-S07 | Epic gate: reports and dashboards consistent with ledger (e2e) | E09-S02, E09-S04, E09-S05, E09-S06 | MEDIUM |
| E09-R01 | Review E09 | E09-S07 | MEDIUM |

## Reading order for implementers

1. `WBS.md` §2–§3 (binding conventions, especially §3.5 ledger write points and §3.6 fakes/e2e).
2. ADR-0002 D-3 (append-only tables), ADR-0009 D-3 (`/status`), D-12 (multi-machine deferred), D-14 (dashboard contract), D-16 (logging).
3. `INTERFACES.md` §1.1 (`KernelStatus`), §1.6 (`CostManager`), §1.14 (`LedgerManager.report`, `Report`, `TelemetryManager`), §1.15 (`pinned_versions`), §6 (`walk report`, `walk cost`, `walk status`, `walk ledger`).
4. `DOMAIN-MODEL.md` §3 (`LedgerEventKind`, `CostCategory`, `BudgetDimension`), §4.4 (`CostRecord`), §4.12 (`LedgerEvent.behavior_versions`, `RetrospectiveMetrics`), §6.2 (`ledger_events`, `cost_records`, `agent_runs`, `budgets`, `approval_requests`, `decisions`).
5. `ARCHITECTURE.md` §3.1 (CLI reads SQLite directly for `status`/`ledger`/`report`), §4.3 (write points; "Reports are `ReportQuery` objects over `ledger_events` + `cost_records`"), §7 (Inv. 9), §8 (`.ai/reports/` layout).
6. Existing files named in each story's Files table (E01-S05/S06/S12, E02-S04, E03-S05, E04-S13) and their tests.

Parallel sets (WBS.md §8): `{S01→S02} ∥ {S03→S04} ∥ {S06}`; S05 after S01; S07 last.

## `NEW NAME:` items introduced by this epic (to be added to WBS.md §6 by E09-X01)

| Item | Story | Why |
|---|---|---|
| module `walk.telemetry.reports`: `ReportSection`, `ReportQuery` (Protocol), `TaskReportQuery`, `FeatureReportQuery`, `PhaseReportQuery`, `ProjectReportQuery`, `CostReportQuery`, `ImprovementReportQuery`, `REPORT_QUERIES`, `render_report_markdown` | S01, S02 | ARCHITECTURE §4.3 names `ReportQuery` without a module or concrete classes |
| `walk report` command group module `walk.cli.cmd_report` (`report_app`) | S01 | WBS §3.7 lists the group; no story created it |
| `DefaultMemoryManager.write_report` writes without front matter and without `memory_index` row | S02 | INTERFACES §1.8 defines the method; its document shape was open |
| `KernelSettings.compute_usd_per_hour`, `KernelSettings.time_usd_per_hour` | S03 | §84 compute/time cost need a rate; none defined |
| `BuiltinHookDeps.costs: CostManager`; hook callables `build_result_record_compute_cost`, `agent_end_record_time_cost` | S03 | New default attachments on `ON_BUILD_*` / `ON_AGENT_END` |
| `CostManager.breakdown(...)`, `walk cost --by` | S03 | §85 roll-ups by provider/model/role not covered by `cost_of` |
| module `walk.orchestrator.status`: `KernelStatusQuery`; `DefaultOrchestrator.refresh_status` | S04 | `Orchestrator.status()` is synchronous; the CLI needs the same snapshot without a daemon |
| migration `0003_dashboard_views.sql` views `v_phase_progress`, `v_model_usage`, `v_budget_usage`, `v_pending_decisions` (names from ADR-0009 D-14; columns fixed here) | S04 | ADR names the views, not their columns |
| `DefaultLedgerManager` constructor parameter `behavior_versions: Callable[[], dict[str, str]] \| None` | S05 | telemetry may not import improvement; versions injected as a callable |
| module `walk.telemetry.provenance`: `ProvenanceQuery`, `ProvenanceChain`, `ProvenanceLink`; `walk ledger why` | S05 | §88 questions need a chain query and a CLI entry |
| `DECISION_RECORDED` payload keys `evidence_ids`, `proposed_by_role`, `related_work_items`, `source_requirements` | S05 | Additive payload enrichment for §88 |
| `OBSERVABILITY_MAP` (`walk.telemetry.metrics`), `lint_observability_coverage` (`walk.cli.lints`) | S06 | §86 completeness check as data |
| `configure_logging(..., max_bytes, backup_count)` rotation parameters | S06 | ADR-0009 D-16 rotation figures |

---

### E09-X01 — Refine E09 against codebase

**Status:** TODO
**Type:** docs
**Requirements:** §81, §83, §87, §135, §5 (non-goals: refine rejects stories that drift into out-of-scope work)
**Depends on:** E07-R01
**Effort:** LOW   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
Every E09 story's Files table, interface references and dependencies are re-validated against the `src/walk/` tree and `INTERFACES.md` as they exist after E07-R01, and the corrected epic file is committed before any E09 story starts (WBS §1 `X` task, §2 rule 3).

#### Scope
- In: this file (E09-S01…S07, R01), WBS §5 rows for E09, WBS §6 register additions from the table above.
- Out: renaming, renumbering, adding or dropping stories (WBS §1: IDs are fixed); any source change.

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-09-production-intelligence.md` | modify | — |
| `docs/02-work-breakdown/WBS.md` | modify | — (§5 status rows for E09, §6 register rows) |

#### Interface contract
No code. Procedure:
1. For every row of every Files table in this file: `create` paths must not exist; `modify` paths must exist (or be created by an earlier story in this file); every "Public symbols" entry marked `modify` must already be defined in that file (grep) or be new in this story.
2. For every `INTERFACES.md §x.y` / `DOMAIN-MODEL.md §x.y` reference: the section exists and still defines the referenced names.
3. Every `Depends on` ID is `DONE` in WBS §5 (E07-R01, E03-S11, E02-S04, E04-S13) or belongs to this epic.
4. Migration number: `0003_dashboard_views.sql` must be the next free number under `src/walk/persistence/migrations/project/`; renumber in E09-S04 and E09-S07 if E05–E08 added migrations.
5. Every `(verify)` marker is resolved (kept or path corrected) and removed.

#### Behavior
1. Corrections are made in place; no story text is removed, only paths, symbol names, references and `Notes` are corrected.
2. New public names discovered during refinement are added to the `NEW NAME:` table above and to WBS §6.
3. Where a dependency is not `DONE`, the story is set `BLOCKED` with the reason (IMPLEMENTATION-PROTOCOL §1.2) instead of being rewritten.
4. The refine commit contains only the two documentation files.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given every Files table path in this file When checked against `src/walk/` and `tests/` Then each `modify` path exists and each `create` path does not exist or is created by an earlier E09 story | manual checklist recorded in this story's Evidence |
| 2 | Given every `INTERFACES.md`/`DOMAIN-MODEL.md` reference in this file When opened Then the section exists and defines the named symbols | manual checklist recorded in this story's Evidence |
| 3 | Given WBS §5 When E09 dependencies are read Then every dependency outside E09 is `DONE` or the dependent story is marked `BLOCKED` with a reason | manual checklist recorded in this story's Evidence |
| 4 | Given the corrected file When `py -3 scripts/validate_wbs.py` runs Then no error mentions an `E09-` ID | gate output in Evidence |

#### Evidence required
- Checklist per story (ID → paths checked → corrections made).
- `scripts/validate_wbs.py` output.

#### Notes
- WBS §2 rule 3; IMPLEMENTATION-PROTOCOL §1.2 (Definition of Ready).
- Known hotspots: `src/walk/cli/cmd_status.py` and `src/walk/cli/cmd_run.py` (E01-S30), `src/walk/model_router/costing.py` (E01-S20), `src/walk/runtime/executor.py` (E01-S27), `src/walk/integrations/ci.py` (E03-S11), phase report hook and `EvidencePackager` module (E07-S03/S09), `tests/e2e/conftest.py` fixture `e07_scenario` (E07-S10).
- Commit subject: `docs: refine epic 09 stories (E09-X01)`.

#### Evidence (filled by implementer)
_pending_

---

### E09-S01 — `ReportQuery` and task/feature reports

**Status:** TODO
**Type:** feat
**Requirements:** §83, §82, §81, §6.11, §137 (Inv. 9)
**Depends on:** E09-X01
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Task and Feature reports (§83) are rendered deterministically from `ledger_events` and `cost_records` only — never from `.ai/` narrative or agent output — through `ReportQuery` objects, and are available from `walk report task|feature`.

#### Scope
- In: `walk.telemetry.reports` module, `TaskReportQuery`, `FeatureReportQuery`, `DefaultLedgerManager.report` dispatch, `walk report task|feature SUBJECT_ID [--json]`.
- Out: phase/project/cost/improvement queries and `--write` (E09-S02); provenance chains (E09-S05).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/telemetry/reports.py` | create | `ReportSection`, `ReportQuery`, `TaskReportQuery`, `FeatureReportQuery`, `REPORT_QUERIES`, `render_report_markdown` |
| `src/walk/telemetry/service.py` | modify | `DefaultLedgerManager.report` (dispatch to `REPORT_QUERIES`) |
| `src/walk/telemetry/__init__.py` | modify | re-exports |
| `src/walk/cli/cmd_report.py` | create | `report_app` |
| `src/walk/cli/app.py` | modify | — (register `report_app`) |
| `tests/telemetry/test_reports_task.py` | create | — |
| `tests/telemetry/test_reports_feature.py` | create | — |
| `tests/cli/test_cmd_report.py` | create | — |

#### Interface contract
```python
# src/walk/telemetry/reports.py
class ReportSection(FrozenModel):
    title: str
    rows: list[JsonDict]  # machine-readable rows (also placed in Report.data[title])
    markdown: str  # rendered table / list for this section


class ReportQuery(Protocol):
    kind: ClassVar[str]  # one of "task", "feature", "phase", "project", "cost", "improvement"

    async def run(self, subject_id: str) -> Report: ...


class TaskReportQuery:  # kind = "task"; subject = STORY/TASK/BUG id
    def __init__(self, db: Database, clock: Clock) -> None: ...


class FeatureReportQuery:  # kind = "feature"; subject = FEAT id
    def __init__(self, db: Database, clock: Clock) -> None: ...


REPORT_QUERIES: dict[
    str, type[ReportQuery]
]  # filled by S01 (task, feature) and S02 (the other four)


def render_report_markdown(
    kind: str, subject_id: str, generated_at: datetime, sections: list[ReportSection]
) -> str:
    """'# <Kind> report — <subject>' + 'Generated: <iso>' + one '## <title>' per section, in order."""


# DefaultLedgerManager
async def report(
    self,
    kind: Literal["task", "feature", "phase", "project", "cost", "improvement"],
    subject_id: str,
) -> Report:
    """REPORT_QUERIES[kind](self._db, self._clock).run(subject_id); unknown kind → ConfigError."""
```
`Report` is INTERFACES §1.14 (`kind, subject_id, generated_at, markdown, data`). CLI: `walk report (task|feature) SUBJECT_ID [--json]` prints `markdown` or `Report.model_dump(mode="json")`.

#### Behavior
1. Queries read only `ledger_events`, `cost_records` and the projection columns `work_items(id, parent_id, kind, title, state)`; they never open `.ai/` files, never read `agent_runs.json`/`output`, never call providers (§83 "from recorded events").
2. `TaskReportQuery.run(id)` sections in order: `Summary` (id, title, kind, current state, first event `at`, last event `at`, duration), `Timeline` (every `WORK_ITEM_TRANSITION` for the item: at, from, to, event, actor), `Runs` (one row per `run_id` seen in `AGENT_RUN_STARTED`: role, model_id, effort, outcome of `AGENT_RUN_ENDED`, duration, `behavior_versions` of the start event, cost_usd summed from `cost_records.run_id`), `Tools` (`TOOL_INVOKED` count per `tool`, `TOOL_DENIED` count), `Failures` (`ERROR`, `RETRY`, `MODEL_FALLBACK`, `HANDOVER_CREATED` rows), `Decisions` (`DECISION_RECORDED` rows), `Evidence` (`EVIDENCE_RECORDED` rows), `Cost` (sum `cost_usd` per `CostCategory` for the item).
3. `FeatureReportQuery.run(id)` = feature + descendants (`work_items.parent_id` transitively, plus BUG rows whose `json` has `related_feature_id == id`): sections `Summary`, `Stories` (one row per child: id, kind, title, state, runs, cost_usd), `Timeline` (feature-level transitions only), `Quality` (`QC_RESULT` outcomes, `BUG_CREATED` count, `BUILD_RESULT` pass/fail counts across descendants), `Decisions`, `Cost` (per category, descendants included).
4. Unknown subject (no `work_items` row and no ledger event) → `ConfigError("no events for <id>")`; a subject with a row but no events renders sections with `_none_`.
5. `Report.data` = `{section.title: section.rows}` plus `"subject_id"`, `"kind"`, `"generated_at"`; `generated_at` from the injected `Clock`.
6. Determinism: two runs on the same DB with the same clock value produce byte-identical `markdown`; rows are ordered by `seq` (ledger) or `id` (items), never by dict order.
7. Numbers in markdown use two decimals for USD, integers for counts, ISO-8601 for timestamps.
8. CLI exit 1 on `ConfigError`; the CLI opens the DB read-only (ARCHITECTURE §3.1) and never requires the daemon.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a seeded ledger for STORY-0001 (3 transitions, 2 runs, 1 fallback, 4 cost records) When `TaskReportQuery.run` Then `Summary.state`, `Timeline` 3 rows, `Runs` 2 rows with per-run cost, `Failures` 1 row | `tests/telemetry/test_reports_task.py::test_task_report_sections_from_ledger` |
| 2 | Given the same DB When run twice Then identical `markdown` | `tests/telemetry/test_reports_task.py::test_task_report_deterministic` |
| 3 | Given an item id with no row and no events When run Then `ConfigError` | `tests/telemetry/test_reports_task.py::test_task_report_unknown_subject_raises` |
| 4 | Given a `.ai/features/FEAT-0001.md` whose text contains `SENTINEL` and an agent output containing `SENTINEL` When any report runs Then `SENTINEL` is absent from `markdown` and `data` | `tests/telemetry/test_reports_task.py::test_report_never_reads_memory_or_output` |
| 5 | Given FEAT-0001 with 2 stories and 1 bug (`related_feature_id`) When `FeatureReportQuery.run` Then `Stories` has 3 rows and `Cost` equals the sum of all descendants' cost records | `tests/telemetry/test_reports_feature.py::test_feature_report_rolls_up_descendants` |
| 6 | Given QC_RESULT rejected once then passed and 1 BUG_CREATED When run Then `Quality` rows report `rejected=1, passed=1, bugs=1` | `tests/telemetry/test_reports_feature.py::test_feature_report_quality_counts` |
| 7 | Given `report("phase", …)` before E09-S02 When called Then `ConfigError("unknown report kind")` | `tests/telemetry/test_reports_task.py::test_report_unknown_kind_raises` |
| 8 | Given `walk report task STORY-0001` Then exit 0 and output starts with `# Task report — STORY-0001` | `tests/cli/test_cmd_report.py::test_report_task_markdown` |
| 9 | Given `walk report feature FEAT-0001 --json` Then JSON with keys `kind, subject_id, generated_at, markdown, data` | `tests/cli/test_cmd_report.py::test_report_feature_json` |
| 10 | Given `walk report task NOPE-0001` Then exit 1 | `tests/cli/test_cmd_report.py::test_report_unknown_subject_exits_1` |

#### Evidence required
- Quality gate output (ruff ok, mypy ok, N passed, coverage %).
- Demo: `walk report task STORY-0001` on the E03 gate fixture DB → `## Runs` table with two rows; `walk report feature FEAT-0001 --json | head -c 300`.

#### Notes
- ARCHITECTURE §4.3 last paragraph (reports are queries); E01-S05 `report()` is extended, not replaced — the `data["events"]` list of E01-S05 is kept under `data["events"]` for backward compatibility.
- telemetry is L1 and may import only `common` and `persistence`: all hierarchy lookups are raw read-only SQL on projection columns; no `walk.workflow` import.
- `NEW NAME:` module `walk.telemetry.reports` and its classes; `walk.cli.cmd_report`.
- Commit subject: `feat: add report queries for task and feature reports (E09-S01)`.

#### Evidence (filled by implementer)
_pending_

---

### E09-S02 — Phase/project/cost/improvement reports, `walk report --write`, `write_report`

**Status:** TODO
**Type:** feat
**Requirements:** §83, §85, §82, §69, §115, §6.11
**Depends on:** E09-S01
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
All six §83 report kinds exist as `ReportQuery` objects, `walk report --write` persists them under `.ai/reports/<kind>/`, `MemoryManager.write_report` is implemented, and the `ON_PHASE_COMPLETE` phase report is produced by the same query instead of ad-hoc rendering.

#### Scope
- In: `PhaseReportQuery`, `ProjectReportQuery`, `CostReportQuery`, `ImprovementReportQuery`, `REPORT_QUERIES` complete, `write_report`, `--write`, phase-complete hook delegation.
- Out: improvement metrics section of the improvement report (E10-S09 extends `ImprovementReportQuery`); cost record completeness (E09-S03 — cost report shows whatever categories exist).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/telemetry/reports.py` | modify | `PhaseReportQuery`, `ProjectReportQuery`, `CostReportQuery`, `ImprovementReportQuery` |
| `src/walk/memory/service.py` | modify | `DefaultMemoryManager.write_report` |
| `src/walk/memory/paths.py` | modify | `report_path_for` |
| `src/walk/orchestrator/builtin_hooks.py` | modify | — (`ON_PHASE_COMPLETE` MUST attachment from E07-S09 now calls `LedgerManager.report("phase", id)` then `MemoryManager.write_report`) `(verify)` |
| `src/walk/cli/cmd_report.py` | modify | `report_app` (`phase`, `project`, `cost`, `improvement`, `--write`) |
| `tests/telemetry/test_reports_phase.py` | create | — |
| `tests/telemetry/test_reports_project_cost.py` | create | — |
| `tests/telemetry/test_reports_improvement.py` | create | — |
| `tests/memory/test_service_write_report.py` | create | — |
| `tests/cli/test_cmd_report_write.py` | create | — |

#### Interface contract
```python
class PhaseReportQuery:        # kind="phase"; subject = PHASE id
class ProjectReportQuery:      # kind="project"; subject = project key
class CostReportQuery:         # kind="cost"; subject = PHASE id | work item id | project key (prefix-detected)
class ImprovementReportQuery:  # kind="improvement"; subject = project key
# all: __init__(self, db: Database, clock: Clock); async def run(self, subject_id: str) -> Report

# src/walk/memory/paths.py
REPORT_FOLDERS: dict[str, str] = {"task": "tasks", "feature": "features", "phase": "phases", "project": "project", "cost": "cost", "improvement": "improvement"}
def report_path_for(kind: str, subject_id: str) -> str: ...     # "reports/<folder>/<subject_id>.md" relative to .ai/

# DefaultMemoryManager (INTERFACES §1.8)
async def write_report(self, kind: str, subject_id: str, markdown: str) -> str:
    """Atomic write (tmp + rename) of plain Markdown (no front matter) to report_path_for(); overwrites; no memory_index row,
    no CONTEXT_UPDATED event, no freshness stamp (derived artefact). Secret scan still applies. Returns repo-relative path."""
```
CLI: `walk report (task|feature|phase|project|cost|improvement) SUBJECT_ID [--write] [--json]`; `--write` prints the written path on its own last line.

#### Behavior
1. `PhaseReportQuery` sections: `Summary` (phase id, state from last `PHASE_TRANSITION`, started/ended, gate rounds = count `PHASE_GATE_DECISION`), `Gate decisions` (rows: at, decision, actor), `Work` (counts of descendants per final state; first-pass = COMPLETE items whose `WORK_ITEM_TRANSITION` payload `fix_loops == 0`), `Runs` (per role: runs, failures, fallbacks, mean duration), `Quality` (`QC_RESULT` pass/reject, `BUG_CREATED`, `BUILD_RESULT` pass/fail, `TEST_RESULT` pass/fail), `Decisions` (`DECISION_RECORDED` in phase), `Debates` (`DEBATE_OPENED`/`DEBATE_RESOLVED` counts, rounds), `Cost` (per category; per role), `Retrospective metrics` (`RetrospectiveMetrics` via the E01-S06 `METRIC_QUERIES` scoped to the phase, rendered as a two-column table).
2. `ProjectReportQuery` = `Phases` (one row per phase: state, stories complete/total, cost), `Features` (state counts), `Models` (per `model_id`: runs, tokens, cost), `Totals` (events, runs, cost per category), `Improvements` (observations, candidates, version changes counts).
3. `CostReportQuery` detects the subject by prefix (`PHASE-` → `phase_id`; `EPIC-|FEAT-|STORY-|TASK-|BUG-` → item + descendants; otherwise project key) and renders `By category`, `By provider`, `By model`, `By role`, `By phase` (project only), `Top 10 items by cost`; totals equal `SUM(cost_usd)` of the selected `cost_records` rows exactly (no rounding before summation).
4. `ImprovementReportQuery` sections: `Observations by signal` (`IMPROVEMENT_OBSERVATION` payload `source_signal`), `Candidates by state and risk` (`IMPROVEMENT_CANDIDATE` latest state per id), `Behavior version changes` (`BEHAVIOR_VERSION_CHANGED` rows), `User overrides by command` (`USER_OVERRIDE` payload `command`, §118).
5. `write_report` refuses `kind` not in `REPORT_FOLDERS` (`ConfigError`) and refuses markdown containing a secret pattern (`SecretDetected`, E01-S16 `find_secrets`).
6. `--write` calls `report()` then `write_report()`; the file is overwritten on every call; `.ai/reports/` is created on demand.
7. The `ON_PHASE_COMPLETE` MUST hook writes `.ai/reports/phases/<PHASE-id>.md` through `report("phase")` + `write_report`; it no longer contains rendering code of its own `(verify against E07-S09)`.
8. All four new queries obey E09-S01 rules 1, 5–7 (ledger + cost_records + projection columns only; deterministic ordering).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a seeded phase with 4 stories (3 COMPLETE, 1 first-pass failure), 1 REWORK gate decision When `PhaseReportQuery.run` Then `Work` reports `complete=3`, `first_pass=2`; `Gate decisions` 1 row | `tests/telemetry/test_reports_phase.py::test_phase_report_work_and_gates` |
| 2 | Given the seeded phase When run Then `Retrospective metrics` rows equal `compute_metrics(phase_id)` field by field | `tests/telemetry/test_reports_phase.py::test_phase_report_metrics_match_telemetry` |
| 3 | Given two phases When `ProjectReportQuery.run("DEMO")` Then `Phases` has 2 rows and `Totals.cost_usd` equals `SUM(cost_records.cost_usd)` | `tests/telemetry/test_reports_project_cost.py::test_project_report_totals` |
| 4 | Given cost records across 2 providers, 2 models, 3 roles When `CostReportQuery.run("PHASE-01")` Then each `By …` section sums to the same total | `tests/telemetry/test_reports_project_cost.py::test_cost_report_sections_sum_equal` |
| 5 | Given `CostReportQuery.run("FEAT-0001")` Then only the feature's descendants' records are counted | `tests/telemetry/test_reports_project_cost.py::test_cost_report_item_subject_rolls_up` |
| 6 | Given 3 observations (2 signals), 2 candidates, 1 version change, 2 overrides When `ImprovementReportQuery.run("DEMO")` Then the four sections have the matching counts | `tests/telemetry/test_reports_improvement.py::test_improvement_report_counts` |
| 7 | Given `write_report("phase", "PHASE-01", md)` When called twice Then one file at `.ai/reports/phases/PHASE-01.md`, no front matter, no `memory_index` row, no `CONTEXT_UPDATED` event | `tests/memory/test_service_write_report.py::test_write_report_plain_overwrite_no_index` |
| 8 | Given markdown with an API-key pattern When `write_report` Then `SecretDetected` and no file | `tests/memory/test_service_write_report.py::test_write_report_rejects_secret` |
| 9 | Given `write_report("bogus", …)` Then `ConfigError` | `tests/memory/test_service_write_report.py::test_write_report_unknown_kind` |
| 10 | Given `walk report cost PHASE-01 --write` Then exit 0, last line is `.ai/reports/cost/PHASE-01.md`, file exists | `tests/cli/test_cmd_report_write.py::test_report_write_creates_file` |
| 11 | Given a phase reaching COMPLETE in a fake scenario When `ON_PHASE_COMPLETE` fires Then `.ai/reports/phases/PHASE-01.md` content equals `report("phase","PHASE-01").markdown` | `tests/cli/test_cmd_report_write.py::test_phase_complete_hook_uses_report_query` |

#### Evidence required
- Quality gate output.
- Demo: `walk report phase PHASE-01 --write` → path line; `walk report cost DEMO` → `By category` table with `LLM`, `COMPUTE`, `TIME` rows (zeros allowed before E09-S03).

#### Notes
- ARCHITECTURE §8 `reports/` layout; ADR-0003 (only `MemoryManager` writes under `.ai/`; `write_report` is inside it).
- `write_report` deliberately bypasses `write()` semantics (no version bump, no index, no ledger): reports are derived, reproducible artefacts. Record this in INTERFACES §1.8 docstring in the same commit.
- `NEW NAME:` `REPORT_FOLDERS`, `report_path_for`.
- Commit subject: `feat: add phase, project, cost and improvement reports with write (E09-S02)`.

#### Evidence (filled by implementer)
_pending_

---

### E09-S03 — Cost accounting completeness: CI/compute/time records, roll-ups

**Status:** TODO
**Type:** feat
**Requirements:** §84, §85, §86, §20
**Depends on:** E09-X01, E03-S11
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every §84 cost dimension produces `CostRecord`s — LLM (existing), Assets (E08-S04, existing), Compute (CI/build jobs) and Time (agent execution wall clock) — and §85 roll-ups can be broken down by provider, model and role from the CLI.

#### Scope
- In: `COMPUTE` records from `ON_BUILD_SUCCESS`/`ON_BUILD_FAILURE`, `TIME` records from `ON_AGENT_END`, rates in `KernelSettings`, `CostManager.breakdown`, `walk cost --by`.
- Out: asset credits (E08-S04); token→USD (E01-S20); cost report rendering (E09-S02).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/budgets/protocols.py` | modify | `CostManager.breakdown` |
| `src/walk/budgets/service.py` | modify | `DefaultCostManager.breakdown` |
| `src/walk/budgets/repository.py` | modify | `CostRepository.aggregate` |
| `src/walk/orchestrator/builtin_hooks.py` | modify | `build_result_record_compute_cost`, `agent_end_record_time_cost`; `BuiltinHookDeps.costs` |
| `src/walk/cli/composition.py` | modify | `KernelSettings.compute_usd_per_hour`, `KernelSettings.time_usd_per_hour` |
| `src/walk/cli/cmd_cost.py` | modify | `cost_app` (`--by`) |
| `tests/budgets/test_cost_breakdown.py` | create | — |
| `tests/hooks/test_builtins_cost.py` | create | — |
| `tests/cli/test_cmd_cost_by.py` | create | — |

#### Interface contract
```python
# CostManager (INTERFACES §1.6 addition)
async def breakdown(
    self,
    *,
    work_item_id: WorkItemId | None = None,
    phase_id: PhaseId | None = None,
    project_key: ProjectKey | None = None,
    by: Literal["category", "provider", "model", "role"],
) -> dict[str, float]:
    """Σ cost_usd of the selected cost_records grouped by the chosen column; item subjects include descendants (as cost_of)."""


# CostRepository
async def aggregate(
    self,
    *,
    ids: list[WorkItemId] | None,
    phase_id: PhaseId | None,
    project_key: ProjectKey | None,
    column: str,
) -> dict[str, float]: ...


# KernelSettings
compute_usd_per_hour: float = 0.0  # §84 Compute: CI / build infrastructure
time_usd_per_hour: float = 0.0  # §84 Time: agent execution wall clock

# Hook payloads consumed
# ON_BUILD_SUCCESS / ON_BUILD_FAILURE: {"job": str, "provider": "unity"|"ci", "duration_ms": int, "work_item_id", "run_id", "phase_id"}
# ON_AGENT_END: run available on HookContext (started_at, ended_at, role, work_item_id, phase_id, run_id)
```
`CostRecord` fields (DOMAIN-MODEL §4.4): COMPUTE → `category=COMPUTE, provider=payload.provider, dimension=EXECUTION_TIME_S, quantity=duration_ms/1000, unit="seconds", cost_usd=quantity/3600*compute_usd_per_hour`; TIME → `category=TIME, provider="wallclock", dimension=EXECUTION_TIME_S, quantity=(ended_at-started_at).total_seconds(), unit="seconds", cost_usd=quantity/3600*time_usd_per_hour`, `role=run.role`.
CLI: `walk cost (--item ID | --phase ID | --project) [--by category|provider|model|role] [--json]`.

#### Behavior
1. `build_result_record_compute_cost` (default attachment, priority 100, `required=False`, on both `ON_BUILD_SUCCESS` and `ON_BUILD_FAILURE`): one `CostManager.record` per job; `id` = `COST-<ulid>` via `IdFactory`; idempotent per `(run_id|work_item_id, job, at)` — a hook re-fire with the same payload does not create a second record (checked through `CostRepository` lookup on `json.job_key`).
2. `agent_end_record_time_cost` (default, priority 100, on `ON_AGENT_END`): one `TIME` record per run; runs without `started_at` are skipped with a telemetry counter `cost.time.skipped`.
3. `CostManager.record` (E01-S12 rule 6) meters `COST_USD` only when `cost_usd > 0`, and `TOKENS` only for `dimension == TOKENS`; it never meters `EXECUTION_TIME_S` from cost records (the executor already meters run time) — rule documented in the service docstring.
4. `breakdown(by="model")` keys are `model_id` strings, `None` grouped under `"-"`; `by="role"` likewise.
5. `breakdown` and `cost_of` agree: `sum(breakdown(by="category").values()) == sum(cost_of(...).values())` for every subject.
6. Default rates are `0.0`, so COMPUTE/TIME records exist with `cost_usd == 0.0` out of the box (quantities still reported); rates are read once at composition.
7. `walk cost --by provider` prints `provider | usd` rows sorted by usd desc, then a `total` line; `--json` → `{"by": "provider", "rows": {...}, "total_usd": x}`.
8. Both hooks are `LOG_AND_CONTINUE`: a `CostManager` failure never fails a build or a run.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `ON_BUILD_SUCCESS` payload `duration_ms=90000, provider=unity` and `compute_usd_per_hour=3.6` When fired Then a `COMPUTE` record with `quantity=90.0`, `cost_usd=0.09`, `COST_RECORDED` ledger event | `tests/hooks/test_builtins_cost.py::test_build_success_records_compute_cost` |
| 2 | Given `ON_BUILD_FAILURE` When fired Then a `COMPUTE` record is also written | `tests/hooks/test_builtins_cost.py::test_build_failure_records_compute_cost` |
| 3 | Given the same build payload fired twice When counted Then one record | `tests/hooks/test_builtins_cost.py::test_build_cost_idempotent` |
| 4 | Given a run of 120 s and `time_usd_per_hour=0` When `ON_AGENT_END` fires Then a `TIME` record `quantity=120.0, cost_usd=0.0, role=run.role` | `tests/hooks/test_builtins_cost.py::test_agent_end_records_time_cost` |
| 5 | Given a run without `started_at` When fired Then no record and counter `cost.time.skipped` incremented | `tests/hooks/test_builtins_cost.py::test_agent_end_without_start_skipped` |
| 6 | Given `CostManager.record` raising When the hook fires Then hook result `FAILED` and the triggering operation continues | `tests/hooks/test_builtins_cost.py::test_cost_hooks_log_and_continue` |
| 7 | Given a `TIME` record with `cost_usd=0` When recorded Then no budget is metered; given an LLM record with `cost_usd>0` Then `COST_USD` metered once | `tests/budgets/test_cost_breakdown.py::test_record_meters_only_positive_usd` |
| 8 | Given records for 2 providers / 2 models / 2 roles on FEAT-0001's stories When `breakdown(work_item_id=FEAT-0001, by=…)` for each `by` Then each result sums to `sum(cost_of(FEAT-0001))` | `tests/budgets/test_cost_breakdown.py::test_breakdown_sums_match_cost_of` |
| 9 | Given a record with `model_id=None` When `breakdown(by="model")` Then key `"-"` present | `tests/budgets/test_cost_breakdown.py::test_breakdown_groups_none_as_dash` |
| 10 | Given `walk cost --phase PHASE-01 --by role --json` Then JSON `by == "role"` and `total_usd` equals the SQL sum | `tests/cli/test_cmd_cost_by.py::test_cost_by_role_json` |
| 11 | Given `walk cost --project --by bogus` Then exit 1 | `tests/cli/test_cmd_cost_by.py::test_cost_by_invalid_exits_1` |

#### Evidence required
- Quality gate output.
- Demo: after the E03 gate scenario, `walk cost --project --by category` → rows `LLM`, `COMPUTE`, `TIME` (ASSETS when E08 ran) and `total`.

#### Notes
- ARCHITECTURE §4.3: `COST_RECORDED` stays a `budgets.CostManager` write point — the hooks call `record`, they do not append to the ledger themselves (WBS §3.5).
- `BuiltinHookDeps` is a pydantic model with `arbitrary_types_allowed` (E02-S08); adding `costs` is additive. Composition root wiring only.
- `NEW NAME:` `CostManager.breakdown`, `CostRepository.aggregate`, `KernelSettings.compute_usd_per_hour`, `KernelSettings.time_usd_per_hour`, hook callables above, `walk cost --by`.
- Commit subject: `feat: add compute and time cost records with cost breakdowns (E09-S03)`.

#### Evidence (filled by implementer)
_pending_

---

### E09-S04 — Dashboard views (`0003_dashboard_views.sql`), `walk status --json`, `/status`

**Status:** TODO
**Type:** feat
**Requirements:** §87, §85, §86, §20, §74
**Depends on:** E09-S03
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The §87 dashboard data contract is fixed and served three ways from one query — `walk status --json`, `GET /status` and read-only SQLite views — so every `KernelStatus` field is populated from persisted state and the three outputs agree.

#### Scope
- In: migration with the four ADR-0009 D-14 views, `KernelStatusQuery`, full `KernelStatus` population, `walk status --json/--watch`, `/status` using the same query.
- Out: any UI (ADR-0009 D-14 stack deferred); multi-machine aggregation (D-12).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/persistence/migrations/project/0003_dashboard_views.sql` | create | — `(verify number)` |
| `src/walk/orchestrator/status.py` | create | `KernelStatusQuery` |
| `src/walk/orchestrator/service.py` | modify | `DefaultOrchestrator.status`, `DefaultOrchestrator.refresh_status` |
| `src/walk/orchestrator/__init__.py` | modify | re-export `KernelStatusQuery` |
| `src/walk/cli/cmd_status.py` | modify | `status` (`--json`, `--watch`) `(verify: created by E01-S30)` |
| `src/walk/cli/composition.py` | modify | — (`KernelHandle.status_query`; `/status` `status_provider` wired to the query snapshot) |
| `tests/persistence/test_migration_0003_views.py` | create | — |
| `tests/orchestrator/test_status_query.py` | create | — |
| `tests/cli/test_cmd_status_json.py` | create | — |

#### Interface contract
```sql
-- 0003_dashboard_views.sql (read-only views; no tables, no triggers)
CREATE VIEW v_phase_progress AS      -- phase_id, state, items           : count of work_items per (phase_id, state), kinds STORY/TASK/BUG
CREATE VIEW v_model_usage AS         -- model_id, runs, input_tokens, output_tokens, cache_read_tokens, cost_usd, duration_s, tool_calls
                                     --   from cost_records (category LLM) joined to agent_runs (duration) and ledger_events TOOL_INVOKED (by run_id)
CREATE VIEW v_budget_usage AS        -- id, scope, scope_id, dimension, "limit", consumed, ratio (consumed/limit, 0 when limit=0)
CREATE VIEW v_pending_decisions AS   -- id, source ('APPROVAL'|'DECISION'), category, approver, work_item_id, requested_at
                                     --   UNION of approval_requests(state='PENDING') and decisions(status='PROPOSED')
```
```python
# src/walk/orchestrator/status.py
class KernelStatusQuery:
    def __init__(self, db: Database, workflow: WorkflowManager, clock: Clock, project_key: ProjectKey) -> None: ...
    async def snapshot(self, *, active_runs: list[AgentRun] | None = None) -> KernelStatus:
        """KernelStatus (INTERFACES §1.1) from SQLite: current_phase (projects.current_phase_id), phase_progress (v_phase_progress for that
        phase), gdd_coverage (WorkflowManager.gdd_coverage), active_runs (given, else agent_runs state RUNNING), blocked_items
        (work_items state BLOCKED), pending_approvals (approval_requests PENDING), open_debates (debates not RESOLVED/ABANDONED),
        model_usage (v_model_usage → UsageReport), qc_status ({'passed','rejected','open_bugs'} from QC_RESULT outcomes and BUG rows
        not COMPLETE/CANCELLED), build_status (outcome of latest BUILD_RESULT or None), budgets (budgets table rows),
        open_improvement_candidates (improvement_candidates state not in APPROVED/REJECTED), paused (projects.paused)."""

# DefaultOrchestrator
def status(self) -> KernelStatus: ...            # returns the last snapshot (never None after start())
async def refresh_status(self) -> KernelStatus:  # snapshot(active_runs=executor.running()); called at the end of every tick
```
CLI: `walk status [--json] [--watch]` — no daemon required; `--watch` re-queries every 2 s (injected sleep) until Ctrl-C. `/status` (E03-S05 `WebhookReceiver.status_provider`) returns `DefaultOrchestrator.status()`.

#### Behavior
1. The migration contains only `CREATE VIEW` statements; `schema_migrations` gains version 3 `(verify)`; the kernel DB is untouched.
2. `v_model_usage.cost_usd` equals `SUM(cost_usd)` of `cost_records WHERE category='LLM'` per model; `runs` = `COUNT(DISTINCT run_id)`; `duration_s` = Σ `(julianday(ended_at)-julianday(started_at))*86400` of those runs; `tool_calls` = count of `TOOL_INVOKED` events with those `run_id`s.
3. `v_pending_decisions` orders by `requested_at`; `decisions` rows use `decided_at` as `requested_at` and `approver = owner_role`.
4. `snapshot()` is read-only (opens no transaction with writes) and deterministic for a frozen DB and clock.
5. `KernelStatus.model_usage` maps a view row to `UsageReport(input_tokens, output_tokens, cache_read_tokens, cost_usd, turns=runs, tool_calls, duration_s)`.
6. `walk status` without a daemon runs `KernelStatusQuery.snapshot()` against a read-only connection (`active_runs` = `agent_runs` RUNNING rows, which may be stale orphans — printed with a `(unverified)` marker in table mode, unchanged in JSON).
7. `walk status --json` output parses back into `KernelStatus` (`model_validate_json`) and contains every field of `KernelStatus.model_fields` — the dashboard contract.
8. `/status` and `walk status --json` on the same DB and tick produce equal JSON except `active_runs` ordering (sorted by `id` in both to make them equal).
9. `refresh_status` failures are logged and keep the previous snapshot (status never breaks the tick).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a migrated project DB When `sqlite_master` is read Then the four views exist and `schema_migrations` contains `0003_dashboard_views` | `tests/persistence/test_migration_0003_views.py::test_views_created` |
| 2 | Given 3 stories (2 IMPLEMENTING, 1 COMPLETE) in PHASE-01 When `v_phase_progress` is read Then rows `(PHASE-01, IMPLEMENTING, 2)`, `(PHASE-01, COMPLETE, 1)` | `tests/persistence/test_migration_0003_views.py::test_phase_progress_counts` |
| 3 | Given LLM cost records for 2 models and 3 runs When `v_model_usage` is read Then `cost_usd` per model equals direct `SUM` and `runs` counts distinct runs | `tests/persistence/test_migration_0003_views.py::test_model_usage_matches_sum` |
| 4 | Given a budget `limit=10, consumed=8` When `v_budget_usage` is read Then `ratio == 0.8`; a `limit=0` budget yields `ratio == 0` | `tests/persistence/test_migration_0003_views.py::test_budget_usage_ratio` |
| 5 | Given 1 PENDING approval and 1 PROPOSED decision When `v_pending_decisions` is read Then 2 rows with sources `APPROVAL`, `DECISION` | `tests/persistence/test_migration_0003_views.py::test_pending_decisions_union` |
| 6 | Given a seeded DB When `snapshot()` Then every `KernelStatus` field is populated (no default-empty field where seed data exists) and `phase_progress` equals `v_phase_progress` for the current phase | `tests/orchestrator/test_status_query.py::test_snapshot_populates_all_fields` |
| 7 | Given QC_RESULT passed ×2, rejected ×1 and 1 open bug When `snapshot()` Then `qc_status == {"passed": 2, "rejected": 1, "open_bugs": 1}` | `tests/orchestrator/test_status_query.py::test_snapshot_qc_status` |
| 8 | Given latest BUILD_RESULT outcome FAILED When `snapshot()` Then `build_status == "FAILED"`; with no builds Then `None` | `tests/orchestrator/test_status_query.py::test_snapshot_build_status` |
| 9 | Given the same DB When `snapshot()` twice Then equal `model_dump()` | `tests/orchestrator/test_status_query.py::test_snapshot_deterministic` |
| 10 | Given `refresh_status` with a DB error injected When tick ends Then previous snapshot retained and a log line written | `tests/orchestrator/test_status_query.py::test_refresh_status_keeps_previous_on_error` |
| 11 | Given `walk status --json` without daemon Then exit 0 and output validates as `KernelStatus` with all `model_fields` keys present | `tests/cli/test_cmd_status_json.py::test_status_json_contract` |
| 12 | Given a kernel with webhook port When `GET /status` and `walk status --json` are compared Then equal JSON | `tests/cli/test_cmd_status_json.py::test_status_endpoint_equals_cli` |
| 13 | Given `walk status --watch` with injected sleep When 3 iterations pass Then 3 snapshots printed | `tests/cli/test_cmd_status_json.py::test_status_watch_repeats` |

#### Evidence required
- Quality gate output.
- Demo: `walk status --json | python -m json.tool | head -40`; `sqlite3 .ai/kernel.db "select * from v_model_usage"`; `curl -s localhost:8765/status | head -c 200`.

#### Notes
- ADR-0009 D-3 (`/status` is the only read endpoint), D-14 (view names fixed by ADR; columns fixed here — update ADR-0009 D-14 with the column list in the same commit).
- `KernelStatus.gdd_coverage` uses `WorkflowManager.gdd_coverage` (E06-S06); orchestrator may import workflow.
- `NEW NAME:` `KernelStatusQuery`, `DefaultOrchestrator.refresh_status`, view columns, `walk status --json/--watch` options (INTERFACES §6 lists `--watch` only; `--json` is the global flag).
- Commit subject: `feat: add dashboard views and full kernel status snapshot (E09-S04)`.

#### Evidence (filled by implementer)
_pending_

---

### E09-S05 — Provenance queries and `behavior_versions` on events

**Status:** TODO
**Type:** feat
**Requirements:** §82, §88, §105, §6.11, §137 (Inv. 9)
**Depends on:** E09-S01, E02-S04
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every ledger event records the behavior versions in effect (§82 "with which version"), and the §88 questions about a decision or a work item are answered by one chain query over ledger events exposed as `walk ledger why`.

#### Scope
- In: `behavior_versions` stamping in `DefaultLedgerManager.append`, `DECISION_RECORDED` payload enrichment, `ProvenanceQuery.decision_chain/item_chain`, `walk ledger why`.
- Out: version registry and rollout (E10-S05); report rendering of chains (reports link to `walk ledger why`).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/telemetry/service.py` | modify | `DefaultLedgerManager.__init__` (`behavior_versions` parameter), `append` |
| `src/walk/telemetry/provenance.py` | create | `ProvenanceLink`, `ProvenanceChain`, `ProvenanceQuery` |
| `src/walk/telemetry/__init__.py` | modify | re-exports |
| `src/walk/decisions/service.py` | modify | — (`DECISION_RECORDED` payload gains `evidence_ids`, `proposed_by_role`, `related_work_items`, `source_requirements`) |
| `src/walk/cli/cmd_ledger.py` | modify | `why` command |
| `src/walk/cli/composition.py` | modify | — (passes `lambda: pins.pins` from `KernelVersionPins.load` to `DefaultLedgerManager`) |
| `tests/telemetry/test_ledger_versions.py` | create | — |
| `tests/telemetry/test_provenance.py` | create | — |
| `tests/decisions/test_service_payload.py` | create | — |
| `tests/cli/test_cmd_ledger_why.py` | create | — |

#### Interface contract
```python
# DefaultLedgerManager
def __init__(
    self,
    db: Database,
    repo: LedgerRepository,
    ids: IdFactory,
    clock: Clock,
    behavior_versions: Callable[[], dict[str, str]] | None = None,
) -> None: ...


# append(): if event.behavior_versions == {} and behavior_versions is not None → event = event.model_copy(update={"behavior_versions": behavior_versions()})


# src/walk/telemetry/provenance.py
class ProvenanceLink(FrozenModel):
    question: Literal[
        "WHY",
        "WHICH_ROLE",
        "WHICH_MODEL",
        "WHICH_VERSION",
        "WHAT_EVIDENCE",
        "WHAT_CODE",
        "WHICH_REQUIREMENT",
        "WHAT_COST",
        "WHAT_OUTCOME",
    ]
    answer: str  # human-readable
    event_seqs: list[int]  # ledger rows supporting the answer


class ProvenanceChain(FrozenModel):
    subject_id: str
    links: list[ProvenanceLink]  # fixed order of the Literal above
    events: list[LedgerEvent]  # all events in the chain, seq ascending


class ProvenanceQuery:
    def __init__(self, db: Database) -> None: ...
    async def decision_chain(self, decision_id: DecisionId) -> ProvenanceChain: ...
    async def item_chain(self, work_item_id: WorkItemId) -> ProvenanceChain: ...
```
CLI: `walk ledger why (DEC_ID | ITEM_ID) [--json]` — one line per link `question: answer (seq a, b, c)`.

#### Behavior
1. `append` stamps `behavior_versions` only when the caller left it empty; explicit values (e.g. E04-S08 `CONTEXT_FORMAT/context_ranking`) are preserved and merged over the pins (`{**pins, **event.behavior_versions}`).
2. The callable is evaluated per append (cheap dict copy); when `None` (tests, E01 fixtures) events keep `{}`.
3. `DECISION_RECORDED` payload (E04-S05) additionally carries `evidence_ids` (from `decision.evidence`), `proposed_by_role` (`decision.positions[0].role` when present, else `owner`), `related_work_items`, `source_requirements` (union of `contract.source_requirements` / `gdd_refs` of related items, as `path#anchor` strings). Existing keys unchanged.
4. `decision_chain(DEC)`: anchor = the `DECISION_RECORDED` event with `payload.id == DEC` (or `payload.decision_id`); `WHY` = `payload.topic` + `payload.rationale` when present + preceding `ESCALATION_RAISED`/`DEBATE_RESOLVED` events on the same `work_item_id` within the anchor's run or the 200 events before it; `WHICH_ROLE` = `proposed_by_role`/`owner`; `WHICH_MODEL` = `model_id` of `AGENT_RUN_STARTED`/`MODEL_SELECTED` for the anchor's `run_id`; `WHICH_VERSION` = anchor `behavior_versions`; `WHAT_EVIDENCE` = `EVIDENCE_RECORDED` events whose `payload.id ∈ evidence_ids`; `WHAT_CODE` = `COMMIT`/`MERGED` events on `related_work_items` after the anchor; `WHICH_REQUIREMENT` = `source_requirements`; `WHAT_COST` = Σ `COST_RECORDED.cost_usd` for the anchor's `run_id`; `WHAT_OUTCOME` = last `WORK_ITEM_TRANSITION` on the related items.
5. `item_chain(ITEM)`: `WHY` = `WORK_ITEM_CREATED` payload (title, parent, source requirements); `WHICH_ROLE/MODEL/VERSION` from every `AGENT_RUN_STARTED` of the item (one answer line per run); `WHAT_EVIDENCE`, `WHAT_CODE`, `WHAT_COST`, `WHAT_OUTCOME` as above over the item's events.
6. Missing anchors → `ConfigError("no provenance for <id>")`; missing links are rendered `unknown` with empty `event_seqs`, never omitted (fixed link order).
7. Chains are built from ledger rows only (plus `work_items.json` keys `contract.source_requirements`/`gdd_refs` for rule 3 at write time — read in `decisions.service`, not in telemetry).
8. `walk ledger why` opens the DB read-only; exit 1 on `ConfigError`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given pins `{"WORKFLOW/story_workflow": "1.0"}` injected When `append(event)` with empty versions Then stored event has those versions | `tests/telemetry/test_ledger_versions.py::test_append_stamps_pinned_versions` |
| 2 | Given an event with `behavior_versions={"CONTEXT_FORMAT/context_ranking": "1.0"}` When appended Then both the explicit key and the pins are present | `tests/telemetry/test_ledger_versions.py::test_append_merges_explicit_versions` |
| 3 | Given `behavior_versions=None` When appended Then `{}` | `tests/telemetry/test_ledger_versions.py::test_append_without_provider_keeps_empty` |
| 4 | Given a decision with 2 evidence ids related to STORY-0001 (contract source `GDD/save.md#autosave`) When recorded Then `DECISION_RECORDED.payload` has `evidence_ids` (2), `related_work_items`, `source_requirements == ["GDD/save.md#autosave"]` | `tests/decisions/test_service_payload.py::test_decision_recorded_payload_enriched` |
| 5 | Given the E04-S05 tests When run Then they still pass (existing keys unchanged) | `tests/decisions/test_service_payload.py::test_decision_recorded_payload_backward_compatible` |
| 6 | Given a seeded chain (run started with model `fake-claude/sim`, evidence recorded, decision recorded, commit, transition) When `decision_chain(DEC-0001)` Then `WHICH_MODEL == "fake-claude/sim"`, `WHAT_EVIDENCE` lists the evidence seq, `WHAT_CODE` lists the commit seq, `WHAT_OUTCOME` names the final state | `tests/telemetry/test_provenance.py::test_decision_chain_answers_all_questions` |
| 7 | Given a decision with no evidence When chained Then `WHAT_EVIDENCE.answer == "unknown"` and all 9 links present in order | `tests/telemetry/test_provenance.py::test_chain_links_fixed_order_with_unknowns` |
| 8 | Given STORY-0001 with 2 runs When `item_chain` Then `WHICH_MODEL` has 2 answer lines and `WHAT_COST` equals the SQL sum of the item's `COST_RECORDED` | `tests/telemetry/test_provenance.py::test_item_chain_runs_and_cost` |
| 9 | Given `decision_chain("DEC-9999")` Then `ConfigError` | `tests/telemetry/test_provenance.py::test_chain_unknown_subject_raises` |
| 10 | Given `walk ledger why DEC-0001` Then exit 0 and 9 lines starting with the question names | `tests/cli/test_cmd_ledger_why.py::test_ledger_why_decision` |
| 11 | Given `walk ledger why STORY-0001 --json` Then JSON validates as `ProvenanceChain` | `tests/cli/test_cmd_ledger_why.py::test_ledger_why_item_json` |

#### Evidence required
- Quality gate output.
- Demo: `walk ledger query --limit 1 --json` showing `behavior_versions` populated; `walk ledger why DEC-0001` → nine `question: answer` lines.

#### Notes
- ADR-0008 D-4 (every event records versions in effect); ARCHITECTURE §4.3 last paragraph (§82/§88 by SQL alone); INTERFACES §1.15 `pinned_versions` docstring says TelemetryManager uses it — implemented here via injection because telemetry may not import improvement.
- E04-S08 AC 14 asserted `CONTEXT_FORMAT/context_ranking` on `AGENT_RUN_STARTED` without a general stamping mechanism; this story makes it systematic and keeps that test green (rule 1).
- `NEW NAME:` `ProvenanceQuery`, `ProvenanceChain`, `ProvenanceLink`, `walk ledger why`, `DefaultLedgerManager(behavior_versions=…)`, `DECISION_RECORDED` payload keys.
- Commit subject: `feat: stamp behavior versions on events and add provenance chains (E09-S05)`.

#### Evidence (filled by implementer)
_pending_

---

### E09-S06 — Metrics completeness and log rotation

**Status:** TODO
**Type:** feat
**Requirements:** §86, §116, §81, §137 (Inv. 9)
**Depends on:** E09-S03
**Effort:** LOW   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The §86 "kernel MUST record" list is mapped as data to ledger event kinds and checked mechanically (unit test and `walk doctor --strict` lint), and the JSON log rotates per ADR-0009 D-16 (10 × 20 MB).

#### Scope
- In: `OBSERVABILITY_MAP`, coverage test over a real scenario DB, `lint_observability_coverage`, `configure_logging` rotation, `walk doctor --strict` section `observability`.
- Out: §116 improvement metrics beyond `RetrospectiveMetrics` (E10-S09).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/telemetry/metrics.py` | modify | `OBSERVABILITY_MAP`, `observability_coverage` |
| `src/walk/telemetry/logging.py` | modify | `configure_logging` (`max_bytes`, `backup_count`) |
| `src/walk/cli/lints.py` | modify | `lint_observability_coverage` |
| `src/walk/cli/cmd_doctor.py` | modify | — (`--strict` runs the lint; `DoctorReport.lints` lines prefixed `observability:`) |
| `src/walk/cli/composition.py` | modify | — (`KernelSettings.log_max_bytes = 20_000_000`, `log_backup_count = 10`) |
| `tests/telemetry/test_observability_map.py` | create | — |
| `tests/telemetry/test_logging_rotation.py` | create | — |
| `tests/cli/test_lints_observability.py` | create | — |

#### Interface contract
```python
# src/walk/telemetry/metrics.py
OBSERVABILITY_MAP: dict[str, tuple[LedgerEventKind, ...]] = {
    "executions": (AGENT_RUN_STARTED, AGENT_RUN_ENDED),
    "models": (MODEL_SELECTED,),
    "role": (AGENT_ASSIGNED, AGENT_RUN_STARTED),
    "effort": (EFFORT_SET, EFFORT_CHANGED),
    "tool calls": (TOOL_INVOKED, TOOL_DENIED),
    "workflow transitions": (WORK_ITEM_TRANSITION, PHASE_TRANSITION, RC_TRANSITION),
    "failures": (ERROR,),
    "retries": (RETRY,),
    "handovers": (HANDOVER_CREATED,),
    "decisions": (DECISION_RECORDED,),
    "debates": (DEBATE_OPENED, DEBATE_POSITION, DEBATE_RESOLVED),
    "tokens": (COST_RECORDED,),
    "cost": (COST_RECORDED,),
    "duration": (AGENT_RUN_ENDED, TOOL_INVOKED),
    "artifacts": (EVIDENCE_RECORDED, ARTIFACT_APPROVED, COMMIT, BUILD_RESULT),
}  # the 14 §86 bullets + "artifacts" column as written in §86


async def observability_coverage(db: Database) -> dict[str, bool]:
    """item → True iff at least one event of any mapped kind exists in ledger_events."""


# src/walk/telemetry/logging.py
def configure_logging(
    repo_root: Path, *, level: str = "INFO", max_bytes: int = 20_000_000, backup_count: int = 10
) -> None:
    """RotatingFileHandler on <repo>/.walk/logs/kernel.jsonl with JsonLineHandler formatting."""


# src/walk/cli/lints.py
async def lint_observability_coverage(db: Database) -> list[str]:
    """['observability: no events recorded for <item>' …] — only meaningful on a DB with runs; empty DB → ['observability: ledger empty (skipped)']."""
```

#### Behavior
1. `OBSERVABILITY_MAP` keys are exactly the §86 bullet texts (lower-case, as listed) — 14 entries; every value is non-empty and every kind exists in `LedgerEventKind`.
2. Every kind referenced in the map appears in the ARCHITECTURE §4.3 write-point table (test keeps a copy of that table's kinds as a frozen set and asserts subset).
3. `observability_coverage` is read-only SQL (`SELECT 1 FROM ledger_events WHERE kind IN (...) LIMIT 1` per item).
4. `configure_logging` is idempotent (second call replaces the handler instead of adding one); rotation renames `kernel.jsonl` → `kernel.jsonl.1` … `.10`; existing `JsonLineHandler` line format unchanged.
5. `walk doctor --strict` adds the lint output under `lints`; a non-empty finding list other than the `(skipped)` line makes the exit code 1 (E02-S15 rule).
6. The duration items are also asserted at the event level: every `AGENT_RUN_ENDED` and `TOOL_INVOKED` post event in a scenario DB has `duration_ms` set (coverage test over the E03 gate fixture).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `OBSERVABILITY_MAP` Then 14 keys equal the §86 list and every kind is a `LedgerEventKind` member | `tests/telemetry/test_observability_map.py::test_map_covers_section_86_items` |
| 2 | Given the map When compared to the §4.3 write-point kinds Then every mapped kind is written by some write point | `tests/telemetry/test_observability_map.py::test_map_kinds_have_write_points` |
| 3 | Given the DB produced by the E03 gate scenario (fixture) When `observability_coverage` Then every item is `True` | `tests/telemetry/test_observability_map.py::test_scenario_db_covers_all_items` |
| 4 | Given that DB When `AGENT_RUN_ENDED` and post `TOOL_INVOKED` events are read Then all have `duration_ms is not None` | `tests/telemetry/test_observability_map.py::test_duration_recorded_on_runs_and_tools` |
| 5 | Given `configure_logging(max_bytes=500, backup_count=2)` When 2 KB of lines are logged Then `kernel.jsonl`, `.1`, `.2` exist and no `.3` | `tests/telemetry/test_logging_rotation.py::test_log_rotates_with_backup_count` |
| 6 | Given `configure_logging` called twice Then one handler on the logger | `tests/telemetry/test_logging_rotation.py::test_configure_logging_idempotent` |
| 7 | Given an empty DB When `lint_observability_coverage` Then the single `(skipped)` line and `walk doctor --strict` exit code unaffected by it | `tests/cli/test_lints_observability.py::test_lint_skips_empty_ledger` |
| 8 | Given a DB with runs but no `DECISION_RECORDED` When lint Then one line naming `decisions` and `walk doctor --strict` exits 1 | `tests/cli/test_lints_observability.py::test_lint_reports_missing_item` |

#### Evidence required
- Quality gate output.
- Demo: `walk doctor --strict` → `observability: ok` (or the missing items); `ls .walk/logs/` after a long fake run showing rotated files (or the rotation test transcript).

#### Notes
- ADR-0009 D-16 (rotation 10 × 20 MB; logs never the source of truth); E01-S06 Notes deferred rotation here.
- `RetrospectiveMetrics` fields are fixed by DOMAIN-MODEL §4.12; the §116 metrics it does not cover are E10-S09's `ImprovementMetrics`.
- `NEW NAME:` `OBSERVABILITY_MAP`, `observability_coverage`, `lint_observability_coverage`, `KernelSettings.log_max_bytes/log_backup_count`, `configure_logging` keyword parameters.
- Commit subject: `feat: add observability coverage check and log rotation (E09-S06)`.

#### Evidence (filled by implementer)
_pending_

---

### E09-S07 — Epic gate: reports and dashboards consistent with ledger (e2e)

**Status:** TODO
**Type:** feat
**Requirements:** §83, §85, §87, §88, §82, §6.11, §137 (Inv. 9), §136
**Depends on:** E09-S02, E09-S04, E09-S05, E09-S06
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** QC   **Reviewer role:** LeadDev

#### Goal
After a full fake phase run (E07 gate scenario), every production-intelligence output — phase and cost reports, `walk status --json`, `/status`, the `v_*` views and provenance chains — agrees with direct SQL aggregation over `ledger_events` and `cost_records`.

#### Scope
- In: `tests/e2e/test_e09_gate.py`, `e09_scenario` fixture reusing the E07 scenario.
- Out: production code (defects → `E09-Bxx` bugfix stories).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `tests/e2e/test_e09_gate.py` | create | — |
| `tests/e2e/conftest.py` | modify | `e09_scenario` fixture `(verify: builds on e07_scenario from E07-S10)` |

#### Interface contract
Fixture `e09_scenario(e07_scenario) -> E09Scenario` (`WalkModel` in conftest): `handle: KernelHandle`, `phase_id: PhaseId`, `project_key`, `decision_id: DecisionId` (first ACCEPTED decision of the scenario), `db_path: Path`. Settings: `compute_usd_per_hour=3.6`, `time_usd_per_hour=0.0`, `webhook_port` chosen free. All adapters are `tests/fakes`; `LocalWorkProvider`; real temp git repo.

#### Behavior
Scenario steps (each a test, executed in order via the fixture's cached state):
1. The E07 phase scenario has completed (`PHASE-01` `COMPLETE`); the kernel is still running for `/status`.
2. `walk report phase PHASE-01 --write` writes `.ai/reports/phases/PHASE-01.md`; its `data["Cost"]` per category equals `SELECT category, SUM(cost_usd) FROM cost_records WHERE phase_id='PHASE-01' GROUP BY category`; `data["Work"]["complete"]` equals the count of descendants in `COMPLETE`.
3. `walk report cost PHASE-01 --json` `total_usd` equals the SQL sum; `By category` contains `LLM`, `COMPUTE` (> 0 because builds ran with the rate set) and `TIME` (quantity > 0, usd 0).
4. `walk status --json`: `phase_progress` equals `v_phase_progress` rows for `PHASE-01`; `model_usage[m].cost_usd` equals `v_model_usage` and equals SQL sum per model; `budgets` equal `v_budget_usage` rows; `pending_approvals` count equals `v_pending_decisions` `APPROVAL` rows.
5. `GET /status` JSON equals `walk status --json` JSON.
6. Every `ledger_events` row written after kernel start has non-empty `behavior_versions` containing `WORKFLOW/feature_workflow` and `WORKFLOW/story_workflow`.
7. `walk ledger why <decision_id>` yields 9 links; `WHICH_MODEL` is a fake descriptor id; `WHAT_OUTCOME` is a `COMPLETE` state line.
8. `observability_coverage(db)` is all `True`; `walk doctor --strict` has no `observability:` finding.
9. `walk report project DEMO --write` and `walk report improvement DEMO --write` succeed and the written files are re-generated byte-identically on a second call (clock frozen).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the completed phase When `walk report phase PHASE-01 --write` Then file exists and `Cost` section equals SQL sums per category | `tests/e2e/test_e09_gate.py::test_phase_report_matches_ledger_sums` |
| 2 | Given the phase report Then `Work.complete` equals the SQL count of COMPLETE descendants | `tests/e2e/test_e09_gate.py::test_phase_report_work_counts_match` |
| 3 | Given `walk report cost PHASE-01 --json` Then `total_usd` equals SQL and categories `LLM`, `COMPUTE`, `TIME` present | `tests/e2e/test_e09_gate.py::test_cost_report_complete_categories` |
| 4 | Given `walk status --json` Then `phase_progress` equals `v_phase_progress` and `model_usage` cost equals `v_model_usage` | `tests/e2e/test_e09_gate.py::test_status_matches_views` |
| 5 | Given `v_model_usage` Then its `cost_usd` per model equals direct `SUM` over `cost_records` | `tests/e2e/test_e09_gate.py::test_views_match_direct_aggregation` |
| 6 | Given `/status` and `walk status --json` Then equal | `tests/e2e/test_e09_gate.py::test_status_endpoint_equals_cli` |
| 7 | Given all events since kernel start Then each has `behavior_versions` with both workflow keys | `tests/e2e/test_e09_gate.py::test_all_events_carry_behavior_versions` |
| 8 | Given `walk ledger why DEC` Then 9 links, model and outcome answered | `tests/e2e/test_e09_gate.py::test_provenance_chain_for_decision` |
| 9 | Given the scenario DB Then observability coverage is complete | `tests/e2e/test_e09_gate.py::test_observability_coverage_complete` |
| 10 | Given project and improvement reports written twice Then byte-identical | `tests/e2e/test_e09_gate.py::test_reports_reproducible` |

#### Evidence required
- Quality gate output including `tests/e2e/test_e09_gate.py` (10 passed).
- Demo transcript on the fixture repo: `walk report phase PHASE-01 --write`, `walk report cost PHASE-01`, `walk status --json | head -c 400`, `sqlite3 .ai/kernel.db "select * from v_phase_progress"`, `walk ledger why DEC-0001`.

#### Notes
- Gate uses only fakes and a temp repo; no network. Any production change needed is a separate `bugfix` story; this commit touches tests only.
- WBS §9 maps "Reports/dashboards" of §136 to this story.
- Commit subject: `feat: add epic 09 gate test for reports and dashboards (E09-S07)`.

#### Evidence (filled by implementer)
_pending_

---

### E09-R01 — Review E09

**Status:** TODO
**Type:** docs
**Requirements:** §137 (Inv. 9), §83, §87, §88
**Depends on:** E09-S07
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
An independent agent instance (different model than the E09 implementer where possible, §23) verifies every E09 story against the Definition of Done and Invariant 9, recording defects as `bugfix` stories.

#### Scope
- In: stories E09-S01…S07 and their commits; `INTERFACES.md`/`DOMAIN-MODEL.md`/ADR-0009 deltas; WBS §6 register entries from this epic.
- Out: fixing defects (each becomes `E09-Bxx`).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-09-production-intelligence.md` | modify | — (review record appended; `E09-Bxx` stories appended if any) |
| `docs/02-work-breakdown/WBS.md` | modify | — (status rows, §6 register) |
| `docs/01-architecture/INTERFACES.md`, `docs/01-architecture/DOMAIN-MODEL.md`, `docs/01-architecture/adr/ADR-0009-runtime-topology-and-open-questions.md` | modify (only if drift found) | — |

#### Interface contract
Reviewer protocol, IMPLEMENTATION-PROTOCOL.md "Reviewer protocol" steps 1–5.

#### Behavior
1. For each story: `git show <sha>`; Files table == changed files (extra files need commit-body justification); every acceptance-criterion test exists and passes; coverage ≥ 90 % for touched modules.
2. Invariant 9: `src/walk/telemetry/` contains no `UPDATE`/`DELETE` SQL against `ledger_events` or `cost_records`; the `0003` migration contains only `CREATE VIEW`.
3. §83: `src/walk/telemetry/reports.py` and `provenance.py` import nothing from `walk.memory`, `walk.agents`, `walk.runtime` and open no file under `.ai/` (grep `open(`, `read_text`, `MemoryManager`).
4. Dashboard contract: `KernelStatus.model_fields` unchanged versus `INTERFACES.md` §1.1, or the doc updated in the same commit.
5. `NEW NAME:` items of E09 are present in WBS §6 or listed in the review note for the architect.
6. Defects → `E09-Bxx` stories using the template; commit `docs: review epic 09 stories E09-S01..S07 (E09-R01)`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given each E09 story When the DoD checklist is applied Then every box is checked or an `E09-Bxx` story exists | manual checklist recorded in this story's Evidence |
| 2 | Given `src/walk/telemetry` When grepping for `UPDATE ledger_events`, `DELETE FROM ledger_events`, `UPDATE cost_records`, `DELETE FROM cost_records` Then no match | `tests/architecture/test_ledger_append_only_code.py::test_no_mutating_sql_in_telemetry` |
| 3 | Given `src/walk/telemetry/reports.py` and `provenance.py` When their imports are parsed Then only `walk.common`, `walk.persistence`, `walk.telemetry` and stdlib/pydantic | `tests/architecture/test_reports_ledger_only.py::test_reports_import_only_ledger_layers` |
| 4 | Given the quality gate on `main` Then green with overall coverage ≥ 85 % | gate output in Evidence |

#### Evidence required
- Checklist per story (ID → DoD items → OK/defect id).
- Quality gate output on `main` after the review commit.
- List of `E09-Bxx` stories created (or "none").

#### Notes
- Tests 2–3 are architecture tests created by the reviewer (review tasks may add tests, never production code).
- Commit subject: `docs: review epic 09 stories E09-S01..S07 (E09-R01)`.

#### Evidence (filled by implementer)
_pending_
