# EPIC-11 — Release

**Roadmap stage:** §135 Stage 11
**Goal.** RC lifecycle, UA/Release role, store metadata and publishing behind protected actions: a release candidate is built for every target, passes final QC (rejections re-enter the bug loop and produce the next RC), store metadata is generated and approved as an artifact, and publishing runs only after explicit user approval recorded in the ledger.
**Requirements.** §10.9, §75–§77, §92 (`store.publish`), §62 (release builds), §63–§64 (final QC and rejection bugs), §33 (store metadata as approved artifacts), §136 / §1 flow (`RELEASE CANDIDATE → FINAL QC → STORE / RELEASE`), §137 (Inv. 7, 9, 10, 14).
**Epic gate.** `tests/e2e/test_e11_gate.py`: RC1 is built (fake Unity), QC rejects creating a BLOCKER bug, bug fixed, RC2 passes, `release` requires `walk approve`, `RELEASED` with `RC_TRANSITION` ledger trail.
**Branching.** Every story uses `story/<ID>-<slug>` + worktree (COMMIT-POLICY §4); merge `--no-ff` after E11-R01.
**Preconditions.** E08-R01 and E09-R01 `DONE` with no `BLOCKER` bugfix stories; `main` green; E11-X01 committed before any `E11-S*` story starts (WBS §2 rule 3).

## Story index

| ID | Title | Depends on | Effort |
|---|---|---|---|
| E11-X01 | Refine E11 against codebase | E08-R01, E09-R01 | LOW |
| E11-S01 | UA_RELEASE constitution and routing | E11-X01 | MEDIUM |
| E11-S02 | RC lifecycle service and `walk rc create/list/show` | E11-X01, E01-S11 | HIGH |
| E11-S03 | RC build pipeline for all targets | E11-S02, E03-S11 | MEDIUM |
| E11-S04 | Final QC on RC and rejection bugs | E11-S03, E03-S15 | MEDIUM |
| E11-S05 | Store metadata as approved artifacts | E11-S01, E02-S12 | MEDIUM |
| E11-S06 | Publishing integrations behind `store.publish` | E11-S05, E02-S11 | HIGH |
| E11-S07 | Polish phase template | E11-X01, E07-S05 | LOW |
| E11-S08 | Epic gate: RC1 reject → RC2 release (e2e) | E11-S04, E11-S06, E11-S07 | MEDIUM |
| E11-R01 | Review E11 | E11-S08 | MEDIUM |

## Reading order for implementers

1. `WBS.md` §2–§3 (especially §3.4 payload keys, §3.5 ledger vs hooks, §3.6 fakes, §3.7 CLI layout — `rc` command group).
2. `INTERFACES.md` §3.6 (`rc_workflow`), §3.2 (`story_workflow`, extended here by one row), §4 (routing table, extended here), §1.3 (`WorkflowManager.rc_event`), §1.10 (`PermissionManager`), §1.8 (`approve_artifact`, `write_report`), §2.4 (`UnityProvider.build`, `CiProvider.run_pipeline`), §6 (CLI).
3. `DOMAIN-MODEL.md` §3 (`ReleaseCandidateState`, `ApprovedArtifactKind`, `EvidenceKind`), §4.1 (`ReleaseCandidate`, `Phase`), §4.5 (`ProtectedAction`, `ApprovalRequest`), §4.7 (`ApprovedArtifact`), §6.2 (`release_candidates`).
4. `ARCHITECTURE.md` §4.2 (enforcement point), §4.3 (`RC_TRANSITION` write point), §6 (protected actions, `store.publish`), §7 (Inv. 7, 9, 10, 14), §8 (`.ai/reports/`, `.ai/approved/`).
5. ADR-0006 (D-2 kernel executes side effects, D-3 protected actions cannot be downgraded, D-4 approval pauses the run), ADR-0009 (D-6 Unity batchmode, D-8 credentials), ADR-0013 (constitution schema).
6. `requirements/WAL_K_REQ.md` §10.9, §75, §76, §77, §92; the §1 flow lines 51–61.

Parallel sets (WBS §8): `{S01→S05} ∥ {S02→S03→S04} ∥ {S07}`; S06 after S05 and S02; S08 after S04, S06, S07.

**Carrier-task mechanism (binding for S01, S04, S05, S06).** Release-candidate work has no work item of its own, but every agent run needs one (`AgentExecutor.start(agent, item, purpose)`). Each RC step that needs an agent is therefore represented by a `TASK` work item created by `ReleaseManager` with labels `walk-release:<RC-id>` and `walk-release-step:<qc|ua-review|publish>`. The `TaskRouter` routes such tasks by step (S01), the carrier completes `READY → COMPLETE` through one new `story_workflow` row `release_step_done` (S01), and `ReleaseManager.on_run_completed` maps the applied `AgentOutput` onto `rc_event(...)` (S04–S06). Carrier tasks never enter `IMPLEMENTING`; they are scheduled like any `READY` task.

---

### E11-X01 — Refine E11 against codebase

**Status:** TODO
**Type:** docs
**Requirements:** §135 (Stage 11), §58, §76, §77
**Depends on:** E08-R01, E09-R01
**Effort:** LOW   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
Every E11 story's Files table, interface reference and dependency is re-validated against the `src/walk/` tree and `INTERFACES.md` as they exist after E10, and the corrected epic file plus WBS rows are committed before E11-S01 starts.

#### Scope
- In: path/symbol verification for all E11 stories; resolution of the assumptions listed under Behavior; WBS §3.4 payload-key rows and §6 `NEW NAME:` rows for E11; story `BLOCKED` marks where an assumption fails.
- Out: any source change; re-scoping stories (a story that cannot be made ready is marked `BLOCKED` with the reason, never rewritten into something else).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-11-release.md` | modify | — (corrected Files tables, interface references, Notes) |
| `docs/02-work-breakdown/WBS.md` | modify | — (§3.4 rows for RC payload keys, §6 register rows for E11 `NEW NAME:` items, §5 status of E11-X01) |

#### Interface contract
Refine protocol (WBS §1 `Exx-Xyy`, §2 rule 3): read `src/walk/` and `INTERFACES.md`, then for each story S01–S08: every `modify` path exists; every `create` path does not exist; every referenced symbol in a `modify` row exists with the signature the story assumes; every `INTERFACES.md §x.y` reference resolves; every dependency is `DONE` in WBS §5.

#### Behavior
Assumptions made at planning time (E03-S06…S20, E05–E10 stories were not yet written) that this task must confirm or correct in the epic file:
1. `TaskRouter` implementation lives in `src/walk/orchestrator/router.py` (E03-S07) and `route()` can be extended by label-based rows (S01).
2. `OutputApplier` (`src/walk/runtime/output_applier.py`, E03-S08) chooses the implied workflow event from `(kind, state, output.status)`; S01 adds the `release_step_done` mapping there.
3. `LocalCiProvider` lives in `src/walk/integrations/ci.py` (E03-S11) and job names are strings; S03 assumes the form `build:<BuildTarget>` with `development=False` — confirm or rename.
4. `UnityBatchProvider` is `src/walk/integrations/unity/provider.py` and the editor package file is `unity/com.walk.ci/Editor/WalkCI.cs` (E03-S10); `tests/fakes/fake_unity_provider.py` exists (WBS §3.6).
5. `DefaultOrchestrator` has a single run-completion path where QC output is handled (E03-S14; ARCHITECTURE §4.3 `QC_RESULT`) — S04 hooks `ReleaseManager.on_run_completed` there.
6. `KernelStatus.build_status` is unset by E09-S04 and may be filled by S02.
7. `BehaviorVersionCatalog` (`src/walk/improvement/catalog.py`, E10-S05) derives workflow/template versions from file front matter; if versions are hard-coded, S01/S04/S05 must list the catalog file as `modify`.
8. `walk.persistence.atomic_write` (E01-S04) exists for non-`.ai/` file writes (S05 writes `.walk/release/<rc>/store-metadata.json`).
9. `EvidenceManager.for_phase(phase_id)` has no `kinds` filter (INTERFACES §1.14); S03/S05 filter in code.
10. `ToolInvoker.invoke` dispatches `KERNEL` tools to `IntegrationManager` through a name → handler map (E01-S26); S06 registers `store.validate` / `store.publish` handlers in that map — confirm the registration mechanism.
11. Phase creation: confirm whether E06-S04/E07 added a `walk phase create` command; if yes, S07 modifies it instead of creating one.
12. ADR-0011 D-3 model-policy defaults: confirm which row S01 copies for `UA_RELEASE` (planned: the `PRODUCT_OWNER` row).
13. Record in WBS §3.4 the payload keys defined in E11-S02 and in WBS §6 every `NEW NAME:` item of E11 (listed in each story's Notes).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given every E11 story Files table When each path is checked against `src/walk/` and `tests/` Then every `modify` path exists and every `create` path is absent, or the row is corrected | manual checklist (story → path → OK/corrected) recorded in this task's Evidence |
| 2 | Given every `INTERFACES.md §x.y` / `DOMAIN-MODEL.md §x.y` reference in E11 When opened Then the section exists and names the referenced symbol | manual checklist recorded in Evidence |
| 3 | Given every `Depends on` id of E11 stories When looked up in WBS §5 Then status is `DONE` (or the depending story is marked `BLOCKED` with the id) | manual checklist recorded in Evidence |
| 4 | Given Behavior items 1–13 When each is confirmed or corrected Then the epic file reflects the real path/symbol and WBS §3.4/§6 contain the E11 rows | diff of the refine commit recorded in Evidence |

#### Evidence required
- Checklist table (story → files verified → interface refs verified → deps verified → corrections made).
- `git show --stat` of the refine commit.

#### Notes
- No production code; no test files. A story that depends on a missing symbol is set `BLOCKED` with `pending <symbol> (<story that should create it>)`.
- Commit subject: `docs: refine epic 11 stories (E11-X01)`.

#### Evidence (filled by implementer)
_pending_

---

### E11-S01 — UA_RELEASE constitution and routing

**Status:** TODO
**Type:** feat
**Requirements:** §10.9, §9, §12, §31, §127, §137 (Inv. 1, 7)
**Depends on:** E11-X01
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The `UA_RELEASE` role exists as a kernel-default constitution, runtime policy and permission rule set, and release carrier tasks (`walk-release-step:*`) are routed to the right role and purpose and complete through one data-declared `story_workflow` transition.

#### Scope
- In: `ua_release.md` constitution; `policies.yaml` and `permissions/defaults.yaml` rows for `UA_RELEASE`; `walk.workflow.release` label helpers; `TaskRouter` release rows; `story_workflow.yaml` row `release_step_done` + guards; `OutputApplier` implied-event mapping for carrier tasks.
- Out: `ReleaseManager` and carrier-task creation (E11-S02/S04/S05/S06); `store.*` tool specs and handlers (E11-S06); market-feedback participation before release (§10.9 "MAY", not planned).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/agents/defaults/ua_release.md` | create | — |
| `src/walk/agents/defaults/policies.yaml` | modify | — (`UA_RELEASE` role entry) |
| `src/walk/permissions/defaults.yaml` | modify | — (`UA_RELEASE` rows, table below) |
| `src/walk/workflow/release.py` | create | `ReleaseStep`, `RELEASE_LABEL_PREFIX`, `RELEASE_STEP_LABEL_PREFIX`, `release_labels`, `rc_id_of`, `release_step_of` |
| `src/walk/workflow/guards.py` | modify | `is_release_step`, `output_status_is_verdict` |
| `src/walk/workflow/tables/story_workflow.yaml` | modify | — (row `release_step_done`; `version: "1.1"`) |
| `src/walk/workflow/__init__.py` | modify | re-export `ReleaseStep`, `release_step_of`, `rc_id_of` |
| `src/walk/orchestrator/router.py` | modify | `DefaultTaskRouter.route` (release rows), `RELEASE_ROUTES` |
| `src/walk/runtime/output_applier.py` | modify | — (`release_step_done` implied event for carrier tasks) |
| `src/walk/improvement/catalog.py` | modify | — (only if `WORKFLOW/story_workflow` version is hard-coded; E11-X01 item 7) |
| `tests/agents/test_defaults_ua_release.py` | create | — |
| `tests/permissions/test_defaults_ua_release.py` | create | — |
| `tests/workflow/test_release_labels.py` | create | — |
| `tests/workflow/test_tables.py` | modify | — (story table row count + version) |
| `tests/orchestrator/test_router_release.py` | create | — |
| `tests/runtime/test_applier_release.py` | create | — |

#### Interface contract
```python
# src/walk/workflow/release.py
class ReleaseStep(StrEnum):
    QC = "qc"                 # final QC run (E11-S04)
    UA_REVIEW = "ua-review"   # store metadata review (E11-S05)
    PUBLISH = "publish"       # approval-gated publish run (E11-S06)

RELEASE_LABEL_PREFIX = "walk-release:"            # + ReleaseCandidateId
RELEASE_STEP_LABEL_PREFIX = "walk-release-step:"  # + ReleaseStep value

def release_labels(rc_id: ReleaseCandidateId, step: ReleaseStep) -> list[str]: ...
def rc_id_of(item: WorkItem) -> ReleaseCandidateId | None: ...
def release_step_of(item: WorkItem) -> ReleaseStep | None: ...

# src/walk/orchestrator/router.py
RELEASE_ROUTES: dict[ReleaseStep, tuple[AgentRole, str]] = {
    ReleaseStep.QC: (AgentRole.QC, "QC"),
    ReleaseStep.UA_REVIEW: (AgentRole.UA_RELEASE, "REVIEW"),
    ReleaseStep.PUBLISH: (AgentRole.UA_RELEASE, "IMPLEMENT"),
}
```
`story_workflow.yaml` new row (INTERFACES §3.2 addition, table version `1.1`): `READY | release_step_done | is_release_step, output_status_is_verdict, required_evidence_present | COMPLETE | ON_TASK_COMPLETE | KERNEL`.

Constitution front matter (ADR-0013 D-2): `id: UA_RELEASE`, `role: UA_RELEASE`, `version: "1.0"`, `identity: UA / Release Manager`, `mission: Protect market readiness and release quality.` (§10.9), `responsibilities: [positioning, store listing, ASO, screenshots, creatives, release notes, publishing, release validation]`, `authority: {decision_scope: [RELEASE], max_autonomy_level: 1, may_approve: [STORE_METADATA], may_reject: [review.reject], may_create_work: [TASK]}`, `risk_tolerance: VERY_LOW`, `preferred_evidence: [BUILD_ARTIFACT, QC_REPORT, SCREENSHOT, PLAYTEST]`, `escalation_rules: [{condition: "publishing a store build", to_level: 3, category: RELEASE}, {condition: "release date, pricing or monetization change", to_level: 3, category: PRODUCT}]`, `tool_permissions: [{tool: store.validate, effect: ALLOW}, {tool: store.publish, effect: REQUIRE_APPROVAL, approver: USER}, {tool: Edit, effect: DENY}, {tool: Write, effect: DENY}]`, `forbidden_actions: ["publish without user approval", "edit game code or assets", "change approved store metadata"]`. Body sections per ADR-0013 D-3 with one paragraph each derived from §10.9.

`permissions/defaults.yaml` rows added:

| role | tool | effect | notes |
|---|---|---|---|
| UA_RELEASE | `Read`,`Glob`,`Grep`,`decision.propose`,`store.validate` | ALLOW | |
| UA_RELEASE | `Edit`,`Write`,`bash`,`git.*`,`jira.*` | DENY | |
| UA_RELEASE | `store.publish` | REQUIRE_APPROVAL | approver USER (already covered by the `*` protected-action row; restated for the role) |

`policies.yaml` `UA_RELEASE` entry: `model_policy` families copied from the `PRODUCT_OWNER` row of ADR-0011 D-3 with `required_capabilities: [PLANNING, LONG_CONTEXT_REASONING]`, `cross_model_review: false`; `effort_policy.default: MEDIUM`; `budget_policy` kernel default; `allowed_tools: [Read, Glob, Grep, store.validate, store.publish]`; `allowed_paths: []`; `execution_strategy: single_run`; `max_parallel_runs: 1`.

#### Behavior
1. `ConstitutionLoader.load(UA_RELEASE)` succeeds; `list_roles()` includes `UA_RELEASE`; the provider-name lint (E01-S17 rule 3) passes on the new file.
2. `release_labels(rc, step)` returns exactly `[f"walk-release:{rc}", f"walk-release-step:{step}"]`; `rc_id_of`/`release_step_of` return `None` for items without the labels and raise `ConfigError` when exactly one of the two labels is present.
3. `DefaultTaskRouter.route(item, state)`: when `item.kind == TASK`, `state in {READY, REWORK}` and `release_step_of(item)` is set → `RouteDecision(role, purpose)` from `RELEASE_ROUTES`, `cross_model_review=False`; otherwise the E03-S07 table applies unchanged. A release task whose `contract.owner_role` differs from the routed role raises `ConfigError`.
4. `is_release_step(item, ctx)` is true iff `release_step_of(item)` is not `None`; `output_status_is_verdict` is true iff `ctx.payload["output_status"] ∈ {APPROVED, REJECTED, COMPLETED}`.
5. `DefaultOutputApplier` raises `release_step_done` (instead of the regular `(kind, state, status)` mapping) when `release_step_of(run item)` is set; the payload carries `output_status` and `evidence_kinds_present` (WBS §3.4) so `required_evidence_present` checks `contract.required_evidence`.
6. The `story_workflow` table loads as version `1.1` with exactly one more row than `1.0`; `TransitionTable` validation (E01-S09) still passes; non-release tasks cannot take `release_step_done` (guard `is_release_step` rejects).
7. `PermissionManager.decide` for `UA_RELEASE` + `store.publish` → `REQUIRE_APPROVAL(approver=USER)`; for `Edit` → `DENY`; for `store.validate` → `ALLOW`; a project `permissions.yaml` granting `UA_RELEASE Edit ALLOW` → `ConfigError` (E02-S10 narrowing).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the shipped defaults When `ConstitutionLoader.load(UA_RELEASE)` Then `authority.decision_scope == [RELEASE]`, `may_approve == ["STORE_METADATA"]`, `max_autonomy_level == 1`, `version == "1.0"` | `tests/agents/test_defaults_ua_release.py::test_ua_release_constitution_loads_with_adr_authority` |
| 2 | Given `policies.yaml` When loaded for `UA_RELEASE` Then `allowed_paths == []` and `allowed_tools` contains `store.publish` | `tests/agents/test_defaults_ua_release.py::test_ua_release_policy_defaults` |
| 3 | Given `UA_RELEASE` When `decide(store.publish)` Then `REQUIRE_APPROVAL` approver USER; `decide(Edit)` DENY; `decide(store.validate)` ALLOW | `tests/permissions/test_defaults_ua_release.py::test_ua_release_rule_effects` |
| 4 | Given a project rule `UA_RELEASE Edit ALLOW` When merged Then `ConfigError` | `tests/permissions/test_defaults_ua_release.py::test_ua_release_cannot_be_widened` |
| 5 | Given labels from `release_labels("RC-01", QC)` on a TASK When parsed Then `rc_id_of == "RC-01"`, `release_step_of == QC`; given only one label Then `ConfigError` | `tests/workflow/test_release_labels.py::test_release_labels_roundtrip_and_partial_rejected` |
| 6 | Given `story_workflow.yaml` When loaded Then version `1.1`, contains `READY --release_step_done--> COMPLETE` with the three guards, and all `1.0` rows unchanged | `tests/workflow/test_tables.py::test_story_workflow_release_row` |
| 7 | Given a TASK with step `qc` in READY When `route` Then `(QC, "QC")`; step `ua-review` → `(UA_RELEASE, "REVIEW")`; step `publish` → `(UA_RELEASE, "IMPLEMENT")`; all with `cross_model_review False` | `tests/orchestrator/test_router_release.py::test_release_steps_route_by_label` |
| 8 | Given a plain TASK in READY When `route` Then the E03-S07 result is unchanged | `tests/orchestrator/test_router_release.py::test_non_release_task_routing_unchanged` |
| 9 | Given a release task whose `contract.owner_role` is SENIOR_DEV When `route` Then `ConfigError` | `tests/orchestrator/test_router_release.py::test_release_task_owner_mismatch_rejected` |
| 10 | Given a fake QC run on a `qc` carrier task returning `REJECTED` with `QC_REPORT` evidence When output applied Then the task is `COMPLETE` via `release_step_done` and `WORK_ITEM_TRANSITION` names that event | `tests/runtime/test_applier_release.py::test_carrier_task_completes_via_release_step_done` |
| 11 | Given a carrier task whose output lacks the contract's required evidence When applied Then `GuardRejected` and the task stays `READY` | `tests/runtime/test_applier_release.py::test_carrier_task_missing_required_evidence_rejected` |
| 12 | Given a non-release TASK When `raise_event(release_step_done)` Then `GuardRejected` from `is_release_step` | `tests/workflow/test_release_labels.py::test_release_step_done_rejected_for_plain_task` |

#### Evidence required
- Quality gate output.
- Demo: `walk doctor --strict` on the demo repo → `lints: none` (new constitution passes the provider-name lint); `uv run python -c "from walk.workflow import ReleaseStep; print(list(ReleaseStep))"`.

#### Notes
- ADR-0013 D-1–D-5, D-7 (optional roles use the same schema); ADR-0006 D-3/D-6 (role row pattern); Invariant 7 (`store.publish` remains USER-approved regardless of role rows).
- `story_workflow` `1.0 → 1.1` is a `BehaviorVersion kind=WORKFLOW` MINOR bump (§105); the version string lives in the YAML `version` field.
- `NEW NAME:` module `walk.workflow.release` (`ReleaseStep`, `RELEASE_LABEL_PREFIX`, `RELEASE_STEP_LABEL_PREFIX`, `release_labels`, `rc_id_of`, `release_step_of`); guards `is_release_step`, `output_status_is_verdict`; `story_workflow` event `release_step_done` (INTERFACES §3.2 row); routing rows keyed by release step (INTERFACES §4 rows); `RELEASE_ROUTES`; kernel default constitution `ua_release.md`; `ApprovedArtifactKind.STORE_METADATA` is referenced here and introduced by E11-S05 (the `may_approve` string is validated only when used).
- Commit subject: `feat: add ua release role and release task routing (E11-S01)`.

#### Evidence (filled by implementer)
_pending_

---

### E11-S02 — RC lifecycle service and `walk rc create/list/show`

**Status:** TODO
**Type:** feat
**Requirements:** §76, §136 (§1 flow `RELEASE CANDIDATE → FINAL QC → STORE / RELEASE`), §87, §137 (Inv. 9, 14)
**Depends on:** E11-X01, E01-S11
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Release candidates are created, inspected and advanced through one kernel service: `ReleaseManager` creates `RC-NN` in `BUILDING` from a commit and a project release configuration, computes the `rc_workflow` guard payload from evidence, bugs and approvals, enforces one active release line per project, and is exposed by the new `walk rc create/list/show` command group and in `walk status`.

#### Scope
- In: `ReleaseManager` protocol + `DefaultReleaseManager` (create, get, list, current, event, next); `ReleaseConfig` (`.ai/project/release.yaml`); `DefaultWorkflowManager.create_rc/get_rc/list_rcs`; RC payload keys and the guards that read them; daemon command `rc.create`; `walk rc create/list/show`; `KernelStatus.build_status`.
- Out: running builds (E11-S03); final QC and rejection bugs (E11-S04); carrier-task creation and `on_run_completed` (E11-S04–S06 add the step handlers); store metadata and publishing (E11-S05/S06); the `release` event execution (E11-S06 — this story only computes `approval_user` from an approval id).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/protocols.py` | modify | `ReleaseManager` |
| `src/walk/orchestrator/release.py` | create | `DefaultReleaseManager`, `ReleaseConfig`, `RELEASE_CONFIG_PATH`, `rc_payload` |
| `src/walk/orchestrator/__init__.py` | modify | re-exports `ReleaseManager`, `DefaultReleaseManager`, `ReleaseConfig` |
| `src/walk/workflow/service.py` | modify | `DefaultWorkflowManager.create_rc`, `.get_rc`, `.list_rcs`, `.rc_event` (`rc_fields` payload) |
| `src/walk/workflow/guards.py` | modify | — (`build_evidence_present`, `qc_report_evidence`, `rejection_bugs_created`, `rejection_bugs_complete`, `approval_user` read the payload keys below) `(verify E01-S11 implementation)` |
| `src/walk/orchestrator/commands.py` | modify | — (command `rc.create`) `(verify)` |
| `src/walk/orchestrator/status.py` | modify | — (`KernelStatus.build_status` = latest RC id and state) `(verify E09-S04)` |
| `src/walk/cli/cmd_rc.py` | create | `rc_app` (`create`, `list`, `show`) |
| `src/walk/cli/app.py` | modify | — (registers `rc_app`) |
| `src/walk/cli/composition.py` | modify | — (constructs `DefaultReleaseManager`; `KernelHandle.release`) |
| `docs/01-architecture/INTERFACES.md` | modify | — (new `ReleaseManager` block under §1.1; §1.3 `create_rc/get_rc/list_rcs`; §6 `walk rc …` rows) |
| `tests/orchestrator/test_release_manager.py` | create | — |
| `tests/orchestrator/test_release_payload.py` | create | — |
| `tests/workflow/test_service_rc.py` | create | — |
| `tests/cli/test_cmd_rc.py` | create | — |

#### Interface contract
`ReleaseCandidate`, `ReleaseCandidateState` per DOMAIN-MODEL §4.1/§3; `rc_workflow` per INTERFACES §3.6; `BuildTarget` per INTERFACES §2.4.
```python
# src/walk/orchestrator/release.py
RELEASE_CONFIG_PATH: str = "project/release.yaml"          # relative to .ai/

class ReleaseConfig(WalkModel):
    targets: list[BuildTarget] = Field(min_length=1, description="§62/§77 targets every RC must build, e.g. [Android, iOS]")
    release_branch: str = Field(default="main", description="branch whose HEAD is the default RC commit")
    output_dir: str = Field(default=".walk/release", description="build/output root, gitignored")

async def rc_payload(rc: ReleaseCandidate, *, config: ReleaseConfig, evidence: EvidenceManager, workflow: WorkflowManager,
                     permissions: PermissionManager) -> JsonDict: ...

# src/walk/orchestrator/protocols.py
class ReleaseManager(Protocol):
    """§76. Hosted by walk.orchestrator. Owns RC creation and RC events; WorkflowManager.rc_event stays the only state change."""
    async def create(self, *, commit: Sha | None, targets: list[BuildTarget] | None, actor: Actor) -> ReleaseCandidate: ...
    async def get(self, rc_id: ReleaseCandidateId) -> ReleaseCandidate: ...
    async def list(self) -> list[ReleaseCandidate]: ...
    async def current(self) -> ReleaseCandidate | None: ...           # latest RC not RELEASED
    async def event(self, rc_id: ReleaseCandidateId, event: str, *, actor: Actor, extra: JsonDict | None = None) -> ReleaseCandidate: ...
    def config(self) -> ReleaseConfig: ...

# src/walk/workflow/service.py — DefaultWorkflowManager additions
async def create_rc(self, project_key: ProjectKey, number: int, commit: Sha) -> ReleaseCandidate: ...   # RC-NN, BUILDING, ledger RC_TRANSITION{event: "create"}
async def get_rc(self, rc_id: ReleaseCandidateId) -> ReleaseCandidate: ...
async def list_rcs(self) -> list[ReleaseCandidate]: ...
# rc_event(): when ctx.payload contains "rc_fields" (keys ⊆ {build_evidence_ids, qc_report_evidence_id, rejection_bug_ids}),
# those fields are set on the RC in the same transaction as the state change; any other key → ConfigError.
```
RC payload keys (recorded in WBS §3.4 by E11-X01):

| Payload key | Type | Written by | Read by guard |
|---|---|---|---|
| `rc_targets_required` | list[`BuildTarget`] | `rc_payload` (from `ReleaseConfig.targets`) | `build_evidence_present` |
| `rc_targets_built` | list[`BuildTarget`] | `rc_payload` (from `BUILD_ARTIFACT` evidence ids on the RC, E11-S03) | `build_evidence_present` |
| `qc_report_evidence_id` | `EvidenceId \| None` | `rc_payload` | `qc_report_evidence` |
| `open_blocker_bug_count` | int | `rc_payload` (existing key, WBS §3.4) | `no_open_blocker_bugs` |
| `rejection_bug_ids` | list[`BugId`] | `rc_payload` | `rejection_bugs_created` |
| `rejection_bug_states` | dict[`BugId`, `WorkItemState`] | `rc_payload` | `rejection_bugs_complete` |
| `release_approval_state` | `ApprovalState \| None` | `rc_payload` (from `extra["approval_id"]`) | `approval_user` |

CLI: `walk rc create [--target T...] [--commit SHA] [--json]`; `walk rc list [--json]`; `walk rc show RC_ID [--json]` (RC fields, transitions from `RC_TRANSITION` events, evidence ids, rejection bugs with states).

#### Behavior
1. `create`: refuses (`ConfigError`) when an RC in `BUILDING`, `QC`, `PASSED` or `REJECTED` exists (`REJECTED` continues with `next_rc`, §76); `targets` default to `ReleaseConfig.targets` (missing `release.yaml` and no `--target` → `ConfigError` naming `RELEASE_CONFIG_PATH`); `commit` defaults to `GitProvider` HEAD of `release_branch`; `number` = 1 for a new release line; `WorkflowManager.create_rc` allocates `RC-NN` (project `id_sequences`, width 2) and writes `RC_TRANSITION{event: "create", from_state: null, to_state: BUILDING, commit, targets}` (ARCHITECTURE §4.3 write point `StateMachine.commit`).
2. `event(rc_id, event, actor, extra)` computes `rc_payload`, copies `extra["rc_fields"]` into the context payload and calls `WorkflowManager.rc_event`; guard rejections surface as `GuardRejected` naming the guard; the RC is never mutated outside `rc_event` (fields and state change commit together, or neither).
3. `rc_payload`: `rc_targets_built` = targets of `BUILD_ARTIFACT` evidence listed in `extra["rc_fields"]["build_evidence_ids"]` when given, else in `rc.build_evidence_ids` (target read from the evidence `metadata.target` `(verify EvidenceDraft field, E01-S06)`); `open_blocker_bug_count` = open `BLOCKER` bugs in the project (the §76 "PASS" condition); `rejection_bug_states` = current state of each `rc.rejection_bug_ids`; `release_approval_state` = state of `extra["approval_id"]` via `PermissionManager.pending`/repository lookup, `None` when absent.
4. Guards (E01-S11 names, `(verify)` existing semantics): `build_evidence_present` ⇔ `set(required) ⊆ set(built)`; `qc_report_evidence` ⇔ id not `None`; `no_open_blocker_bugs` ⇔ count == 0; `rejection_bugs_created` ⇔ list non-empty; `rejection_bugs_complete` ⇔ every state ∈ {`COMPLETE`, `CANCELLED`}; `approval_user` ⇔ state == `APPROVED`.
5. `next_rc` from `REJECTED` (via `event(rc, "next_rc")`) yields the successor created by E01-S11 (`number + 1`, `BUILDING`, same targets, `commit` = current HEAD of `release_branch`); `current()` then returns the successor.
6. `walk rc create`: with a running daemon the CLI sends command `rc.create` (ADR-0009 D-3); otherwise runs in-process under `KernelLock`; prints `RC-01 BUILDING <commit> <targets>`. `walk rc list`/`show` read SQLite directly (ARCHITECTURE §3.1); unknown id → exit 1.
7. `KernelStatus.build_status` = `"<RC id> <state>"` of `current()` or `None`; `walk status --json` shows it.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `release.yaml` with `[Android, iOS]` When `create(commit=None)` Then `RC-01`, number 1, `BUILDING`, commit = HEAD of `main`, and one `RC_TRANSITION` with `event == "create"` | `tests/orchestrator/test_release_manager.py::test_create_first_rc` |
| 2 | Given an RC in `QC` When `create` Then `ConfigError` | `tests/orchestrator/test_release_manager.py::test_create_refused_with_active_rc` |
| 3 | Given no `release.yaml` and no targets When `create` Then `ConfigError` naming `project/release.yaml` | `tests/orchestrator/test_release_manager.py::test_create_requires_targets` |
| 4 | Given RC-01 `REJECTED` with both rejection bugs `COMPLETE` When `event("next_rc")` Then `RC-02` number 2 `BUILDING` and `current() == RC-02` | `tests/orchestrator/test_release_manager.py::test_next_rc_successor` |
| 5 | Given build evidence for Android only and required `[Android, iOS]` When `event("build_ok")` Then `GuardRejected` naming `build_evidence_present` | `tests/orchestrator/test_release_payload.py::test_build_ok_requires_all_targets` |
| 6 | Given one open BLOCKER bug When `event("qc_pass")` with a QC report Then `GuardRejected` naming `no_open_blocker_bugs` | `tests/orchestrator/test_release_payload.py::test_qc_pass_blocked_by_open_blocker` |
| 7 | Given a REJECTED RC with one rejection bug in `IMPLEMENTING` When `next_rc` Then `GuardRejected` naming `rejection_bugs_complete` | `tests/orchestrator/test_release_payload.py::test_next_rc_requires_bugs_complete` |
| 8 | Given a PASSED RC and a PENDING approval id When `event("release", extra={"approval_id": …})` Then `GuardRejected` naming `approval_user`; after approval Then `RELEASED` | `tests/orchestrator/test_release_payload.py::test_release_requires_user_approval_state` |
| 9 | Given `create_rc` twice for different lines When ids are read Then `RC-01`, `RC-02` matching `ReleaseCandidateId` | `tests/workflow/test_service_rc.py::test_create_rc_ids_and_ledger` |
| 10 | Given `walk rc create --target Android` (no daemon) then `walk rc list --json` Then exit 0 and one RC in `BUILDING` | `tests/cli/test_cmd_rc.py::test_rc_create_and_list_offline` |
| 11 | Given `walk rc show RC-01 --json` Then the RC, its transitions and targets; `walk rc show RC-99` Then exit 1 | `tests/cli/test_cmd_rc.py::test_rc_show_and_unknown` |
| 12 | Given a running fake daemon When `walk rc create` Then a `commands` row `rc.create` is written and its result printed | `tests/cli/test_cmd_rc.py::test_rc_create_via_daemon` |
| 13 | Given RC-01 `BUILDING` When `walk status --json` Then `build_status == "RC-01 BUILDING"` | `tests/cli/test_cmd_rc.py::test_status_shows_build_status` |
| 14 | Given `rc_event("build_ok")` with `rc_fields.build_evidence_ids` for all targets Then state `QC` and the ids stored; with key `state` in `rc_fields` Then `ConfigError` and nothing changed | `tests/workflow/test_service_rc.py::test_rc_fields_applied_atomically` |

#### Evidence required
- Quality gate output.
- Demo on the fixture repo: `cat .ai/project/release.yaml`, `walk rc create`, `walk rc list`, `walk rc show RC-01`, `walk ledger query --kind RC_TRANSITION`, `walk status --json | grep build_status`.

#### Notes
- INTERFACES §3.6 (table unchanged); ARCHITECTURE §4.3 (`RC_TRANSITION` only from `StateMachine.commit`); ADR-0009 D-3 (IPC); WBS §3.7 (`rc` command group).
- `src/walk/workflow/guards.py` is also modified by E11-S01 (parallel set): rebase rather than merge-overwrite; the two edits touch different guard functions.
- `NEW NAME:` `ReleaseManager` (protocol), `DefaultReleaseManager`, `ReleaseConfig`, `RELEASE_CONFIG_PATH` (`.ai/project/release.yaml`), `rc_payload`, the RC payload keys above and payload key `rc_fields`, `DefaultWorkflowManager.create_rc/get_rc/list_rcs`, `CommandConsumer` command `rc.create`, `KernelHandle.release`, `walk rc create/list/show` (already in WBS §6).
- Commit subject: `feat: add release candidate service and walk rc commands (E11-S02)`.

#### Evidence (filled by implementer)
_pending_

---

### E11-S03 — RC build pipeline for all targets

**Status:** TODO
**Type:** feat
**Requirements:** §62, §76, §77 (AAB), §84, §90, §137 (Inv. 9)
**Depends on:** E11-S02, E03-S11
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
An RC in `BUILDING` is built non-development for every configured target from its exact commit in an isolated worktree through `CiProvider`, every artifact is recorded as `BUILD_ARTIFACT` evidence, and the RC moves to `QC` (`build_ok`) only when all targets succeeded or to `REJECTED` (`build_failed`) otherwise — idempotently across kernel restarts.

#### Scope
- In: `ReleaseManager.build` and `resume_builds`; `release_jobs`; `release-build:<BuildTarget>` jobs in `LocalCiProvider`; Android App Bundle output for release builds (`UnityBatchProvider` + `com.walk.ci`); daemon command `rc.build` and build start after `rc.create`; startup resume of interrupted RC builds; `walk rc build`; fake Unity provider release artifacts.
- Out: iOS `.ipa` export (Unity produces an Xcode project; archiving/signing with `xcodebuild` is not planned — the iOS artifact is the zipped Xcode project and E11-S06 documents the limitation); final QC (E11-S04); compute cost records (already produced by the E09-S03 `ON_BUILD_*` attachments).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/protocols.py` | modify | `ReleaseManager.build`, `ReleaseManager.resume_builds` |
| `src/walk/orchestrator/release.py` | modify | `DefaultReleaseManager.build`, `.resume_builds`, `release_jobs`, `RELEASE_JOB_PREFIX` |
| `src/walk/integrations/ci.py` | modify | — (`LocalCiProvider` runs `release-build:<BuildTarget>` as `UnityProvider.build(..., development=False)`) `(verify E03-S11 job dispatch)` |
| `src/walk/integrations/unity/provider.py` | modify | — (`build(..., development=False)` for `ANDROID` passes `-walkAppBundle`) `(verify E03-S10)` |
| `unity/com.walk.ci/Editor/WalkCI.cs` | modify | — (`-walkAppBundle` sets `EditorUserBuildSettings.buildAppBundle = true`) `(verify E03-S10)` |
| `src/walk/orchestrator/service.py` | modify | — (startup calls `release.resume_builds()`; RC build tasks tracked like runs and cancelled on `stop`) `(verify)` |
| `src/walk/orchestrator/commands.py` | modify | — (command `rc.build`; `rc.create` schedules `build`) |
| `src/walk/cli/cmd_rc.py` | modify | `rc_app` (`build`) |
| `tests/fakes/fake_unity_provider.py` | modify | — (release builds write `<target>.aab` / `<target>.zip` artifacts; scripted per-target failure) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§2.4 `CiProvider` job name `release-build:<BuildTarget>`; `ReleaseManager.build/resume_builds`; §6 `walk rc build`) |
| `tests/orchestrator/test_release_build.py` | create | — |
| `tests/integrations/test_ci_release_jobs.py` | create | — |
| `tests/integrations/test_unity_release_build.py` | create | — |
| `tests/cli/test_cmd_rc_build.py` | create | — |

#### Interface contract
`CiProvider.run_pipeline`, `UnityProvider.build`, `JobResult`, `BuildTarget` per INTERFACES §2.4; `IntegrationManager.with_idempotency` per §1.12; RC payload per E11-S02.
```python
# src/walk/orchestrator/release.py
RELEASE_JOB_PREFIX: str = "release-build:"
def release_jobs(targets: list[BuildTarget]) -> list[str]: ...      # ["release-build:Android", "release-build:iOS"] in config order

# ReleaseManager additions (src/walk/orchestrator/protocols.py)
async def build(self, rc_id: ReleaseCandidateId) -> ReleaseCandidate: ...
    """BUILDING only. Worktree at rc.commit; CiProvider.run_pipeline(worktree, rc.commit, release_jobs(targets),
    idempotency_key=f"rc:{rc_id}:build"); all ok → event build_ok with rc_fields.build_evidence_ids; else build_failed."""
async def resume_builds(self) -> list[ReleaseCandidateId]: ...
    """Startup: every RC still BUILDING is built again (idempotent per job); returns the ids resumed."""
```
Artifact layout: `<repo>/<ReleaseConfig.output_dir>/<RC-id>/<BuildTarget>/` (gitignored `.walk/release/…` by default). CLI: `walk rc build RC_ID [--json]`.

#### Behavior
1. `build` refuses an RC not in `BUILDING` (`GuardRejected`); creates (or reuses) a detached worktree at `rc.commit` under `.walk/worktrees/rc-<RC-id>/` through `GitProvider` `(verify worktree API, E01-S23)`; the worktree is removed after the pipeline.
2. Jobs are `release_jobs(targets)`; `LocalCiProvider` maps `release-build:<T>` to `UnityProvider.build(worktree, T, <output>/<RC-id>/<T>/, development=False)`; any other job prefix keeps its E03-S11 behaviour.
3. Android release builds produce an `.aab` (`-walkAppBundle`); other targets produce Unity's default player output, zipped into one artifact file per target by the provider.
4. Each `JobResult` is recorded by `CiProvider` as `BUILD_RESULT` + `BUILD_ARTIFACT` evidence with `metadata.target = <BuildTarget>` and `metadata.rc_id` (E03-S11 recording, extended with the two metadata keys); `build` collects the evidence ids.
5. All jobs ok → `event(rc, "build_ok", extra={"rc_fields": {"build_evidence_ids": [...]}})` → `QC` (guard `build_evidence_present`); any job failed → `event(rc, "build_failed", extra={"rc_fields": {"build_evidence_ids": [...]}})` → `REJECTED` (no rejection bugs: a failed build is not a QC rejection; the next RC is created with `walk rc create` after the fix lands, since `next_rc` requires rejection bugs).
6. Idempotency (§90): the pipeline runs inside `IntegrationManager.with_idempotency(f"rc:{rc_id}:build:<target>", …)` per job, so a resumed build re-runs only targets without a stored result; `resume_builds` at startup resumes every RC still in `BUILDING`.
7. The `ON_BUILD_SUCCESS`/`ON_BUILD_FAILURE` hooks fired by the RC transition (INTERFACES §3.6) carry `payload.rc_id` and no job result; attachments that need a job result skip such contexts, so no duplicate `BUILD_RESULT` or evidence is written (WBS §3.5) `(verify E03-S11 attachments)`.
8. With a daemon, `rc.create` schedules `build` as a tracked background task and returns immediately; `rc.build` re-triggers it; offline `walk rc build` runs synchronously under `KernelLock` and prints one line per target (`Android ok RC-01/Android/game.aab`) and the final RC state.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given targets `[Android, iOS]` When `release_jobs` Then `["release-build:Android", "release-build:iOS"]` | `tests/orchestrator/test_release_build.py::test_release_jobs_from_targets` |
| 2 | Given RC-01 BUILDING and a fake Unity succeeding for both targets When `build` Then 2 `BUILD_ARTIFACT` evidence rows with `metadata.target`, RC `QC`, `build_evidence_ids` of length 2, one `RC_TRANSITION` with event `build_ok` | `tests/orchestrator/test_release_build.py::test_build_all_targets_ok_moves_to_qc` |
| 3 | Given iOS failing When `build` Then RC `REJECTED` via `build_failed`, Android evidence still recorded | `tests/orchestrator/test_release_build.py::test_build_failure_rejects_rc` |
| 4 | Given RC in `QC` When `build` Then `GuardRejected` | `tests/orchestrator/test_release_build.py::test_build_requires_building_state` |
| 5 | Given a build interrupted after Android succeeded When `resume_builds` Then only iOS is built again and the RC reaches `QC` | `tests/orchestrator/test_release_build.py::test_resume_builds_idempotent_per_target` |
| 6 | Given a completed build When the ledger is queried Then exactly one `BUILD_RESULT` per target (no duplicates from the RC-level hook) | `tests/orchestrator/test_release_build.py::test_no_duplicate_build_results` |
| 7 | Given job `release-build:Android` When `LocalCiProvider.run_pipeline` Then `UnityProvider.build` called with `development=False` and target `Android` | `tests/integrations/test_ci_release_jobs.py::test_release_build_job_dispatch` |
| 8 | Given an Android release build When `UnityBatchProvider.build(development=False)` Then the batchmode arguments include `-walkAppBundle`; a development build Then not | `tests/integrations/test_unity_release_build.py::test_app_bundle_flag_for_android_release` |
| 9 | Given `walk rc build RC-01` offline with a fake Unity Then exit 0, one line per target, last line `RC-01 QC` | `tests/cli/test_cmd_rc_build.py::test_rc_build_offline` |

#### Evidence required
- Quality gate output.
- Demo on the fixture repo with the fake Unity provider: `walk rc create`, `walk rc build RC-01`, `ls .walk/release/RC-01/*`, `walk rc show RC-01`, `walk cost --phase <id>` showing COMPUTE cost for the builds.
- Optional (`@pytest.mark.integration`, skipped by default): real Unity Android release build transcript.

#### Notes
- §62 "builds" as `BUILD_ARTIFACT` evidence; ADR-0009 D-6 (Unity batchmode, `com.walk.ci`); E11-X01 item 3 confirms the job naming (`release-build:` was chosen over `build:` + flag because `CiProvider.run_pipeline` has no development parameter).
- `NEW NAME:` `ReleaseManager.build/resume_builds`, `release_jobs`, `RELEASE_JOB_PREFIX`, job name `release-build:<BuildTarget>`, batchmode argument `-walkAppBundle`, evidence metadata keys `target`/`rc_id`, `CommandConsumer` command `rc.build`, `walk rc build`.
- Commit subject: `feat: build release candidates for all targets (E11-S03)`.

#### Evidence (filled by implementer)
_pending_

---

### E11-S04 — Final QC on RC and rejection bugs

**Status:** TODO
**Type:** feat
**Requirements:** §76, §63, §64, §23, §136 (`FINAL QC`), §137 (Inv. 4, 9)
**Depends on:** E11-S03, E03-S15
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A built RC gets an independent final QC run through a `qc` carrier task; an approving QC report moves it to `PASSED`, a rejection moves it to `REJECTED` with the bugs QC created linked as rejection bugs, those bugs flow through the normal bug loop, and when the last one completes the kernel itself raises `next_rc` so the next RC is built — the §76 RC1 → QC → REJECT → RC2 → QC → PASS cycle.

#### Scope
- In: `RELEASE_STEP_CONTRACTS`, `release_step_brief`, `ReleaseManager.open_step`; opening the QC carrier after `build_ok`; `ReleaseManager.on_run_completed` for the `qc` step; QC-output path writing `QC_RESULT` with `rc_id` for carriers; rejection-bug linking; hook callable `release_bug_complete_next_rc` (`ON_TASK_COMPLETE`); automatic build of the successor RC; daemon command `rc.qc` and `walk rc qc`.
- Out: carrier routing and the `release_step_done` transition (E11-S01); the bug loop itself (E03-S15, unchanged); `ua-review` and `publish` steps (E11-S05/S06); QC on physical devices (QC uses the fake/real tools its policy allows; no device farm integration is planned).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/protocols.py` | modify | `ReleaseManager.open_step`, `.on_run_completed`, `.on_bug_completed` |
| `src/walk/orchestrator/release.py` | modify | `RELEASE_STEP_CONTRACTS`, `release_step_brief`, `release_bug_complete_next_rc`, `DefaultReleaseManager.open_step/on_run_completed/on_bug_completed`; `build` opens the QC step after `build_ok` |
| `src/walk/orchestrator/service.py` | modify | — (run-completion path calls `release.on_run_completed` for items with `release_step_of(item) == QC`; QC_RESULT payload gains `rc_id` for carriers) `(verify E03-S14 completion path)` |
| `src/walk/orchestrator/commands.py` | modify | — (command `rc.qc`) |
| `src/walk/cli/cmd_rc.py` | modify | `rc_app` (`qc`) |
| `src/walk/cli/composition.py` | modify | — (registers `release_bug_complete_next_rc` on `ON_TASK_COMPLETE`, priority 150, `log_and_continue`) |
| `docs/01-architecture/INTERFACES.md` | modify | — (`ReleaseManager` methods; §6 `walk rc qc`) |
| `tests/orchestrator/test_release_qc.py` | create | — |
| `tests/orchestrator/test_release_rejection_loop.py` | create | — |
| `tests/cli/test_cmd_rc_qc.py` | create | — |

#### Interface contract
Carrier-task mechanism: this file's header; `ReleaseStep`, `release_labels`, `release_step_of`, `rc_id_of` from E11-S01; `rc_workflow` per INTERFACES §3.6; RC payload per E11-S02; `BugDraft` per DOMAIN-MODEL §4.1.
```python
# src/walk/orchestrator/release.py
RELEASE_STEP_CONTRACTS: dict[ReleaseStep, tuple[AgentRole, list[EvidenceKind]]] = {
    ReleaseStep.QC: (AgentRole.QC, [EvidenceKind.QC_REPORT]),
    ReleaseStep.UA_REVIEW: (AgentRole.UA_RELEASE, []),
    ReleaseStep.PUBLISH: (AgentRole.UA_RELEASE, []),
}   # (contract.owner_role, contract.required_evidence)

def release_step_brief(rc: ReleaseCandidate, step: ReleaseStep, *, artifacts: list[Evidence], open_bugs: list[Bug]) -> str: ...
    # carrier description: RC id, commit, targets, artifact paths, open bugs, verdict rules of the step

async def release_bug_complete_next_rc(ctx: HookContext) -> HookResult: ...   # ON_TASK_COMPLETE → ReleaseManager.on_bug_completed

# ReleaseManager additions
async def open_step(self, rc_id: ReleaseCandidateId, step: ReleaseStep) -> WorkItem: ...
    """Creates (or returns the existing non-terminal) carrier TASK: labels release_labels(rc_id, step), state READY,
    contract.owner_role/required_evidence from RELEASE_STEP_CONTRACTS, description release_step_brief(...)."""
async def on_run_completed(self, item: WorkItem, output: AgentOutput, effects: AppliedEffects) -> ReleaseCandidate | None: ...
async def on_bug_completed(self, bug_id: BugId) -> ReleaseCandidate | None: ...
```
CLI: `walk rc qc RC_ID` — (re)opens the QC step of an RC in `QC`.

#### Behavior
1. After `build_ok` (E11-S03) the RC is in `QC` and `build` calls `open_step(rc, QC)`; the carrier is routed to `(QC, "QC")` by E11-S01 and scheduled like any `READY` task; `cross_model_review` preference of §23 applies through the QC role policy, and the QC run never shares a run with an implementer of the release commit (Inv. 4 — a carrier is a separate work item with owner QC).
2. `open_step` is idempotent: an existing carrier with the same labels in a non-terminal state is returned; a second QC carrier for the same RC is created only after the previous one is `COMPLETE`.
3. `on_run_completed` (called only for `qc` carriers in this story): output `APPROVED` with a `QC_REPORT` evidence → `event(rc, "qc_pass", extra={"rc_fields": {"qc_report_evidence_id": <id>}})` → `PASSED` when guard `no_open_blocker_bugs` holds; output `REJECTED` → the bugs created from `output.new_bugs` by the applier (`effects.bug_ids`, E03-S14) become `rejection_bug_ids` in `event(rc, "qc_reject", extra={"rc_fields": {"qc_report_evidence_id": …, "rejection_bug_ids": […]}})` → `REJECTED`.
4. `qc_pass` rejected by `no_open_blocker_bugs` (a BLOCKER bug opened elsewhere) or a `REJECTED` output without new bugs (guard `rejection_bugs_created`): the RC stays in `QC`, an `ERROR` ledger event with `rc_id` and the guard name is written, and an escalation to `ORCHESTRATOR` is raised (`DecisionManager.escalate`, level 2); `walk rc qc RC_ID` re-opens the step after the cause is fixed.
5. Rejection bugs carry `against_commit = rc.commit` (set by `on_run_completed` before linking, through `WorkflowManager` update `(verify field update API)`) and follow the E03-S15 loop unchanged (triage, fix, review, re-test, reopen).
6. `QC_RESULT` for a carrier run is written once by the orchestrator QC-output path with payload `rc_id`, `verdict`, `bug_ids` (ARCHITECTURE §4.3 write point `orchestrator.Orchestrator`); the RC-level `ON_QC_RESULT`/`ON_BUG_CREATED` hooks fired by `rc_event` do not write a second one (WBS §3.5).
7. `on_bug_completed(bug_id)`: when the bug is a rejection bug of the current `REJECTED` RC and every rejection bug is `COMPLETE` or `CANCELLED`, raises `next_rc` (Who: KERNEL) → successor RC in `BUILDING` at the current `release_branch` HEAD, then schedules `build(successor)` (E11-S03); otherwise returns `None`. Idempotent: a second call after the successor exists does nothing.
8. `walk rc qc RC_ID` with an RC not in `QC` → exit 2 (guard semantics).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given RC-01 reaching `QC` via `build` When the carrier is inspected Then one TASK in `READY` with labels `walk-release:RC-01`, `walk-release-step:qc`, `owner_role == QC`, `required_evidence == [QC_REPORT]`, and the description lists every build artifact path | `tests/orchestrator/test_release_qc.py::test_qc_step_opened_after_build_ok` |
| 2 | Given `open_step(RC-01, QC)` called twice Then the same work item id | `tests/orchestrator/test_release_qc.py::test_open_step_idempotent` |
| 3 | Given a fake QC run returning `APPROVED` with a QC report When completed Then RC-01 `PASSED`, `qc_report_evidence_id` set, carrier `COMPLETE`, one `QC_RESULT` with `rc_id == "RC-01"` | `tests/orchestrator/test_release_qc.py::test_qc_pass_moves_rc_to_passed` |
| 4 | Given a fake QC run returning `REJECTED` with one BLOCKER `new_bugs` entry When completed Then a BUG exists with `against_commit == rc.commit`, RC-01 `REJECTED` with `rejection_bug_ids == [that bug]` | `tests/orchestrator/test_release_qc.py::test_qc_reject_links_rejection_bugs` |
| 5 | Given an open BLOCKER bug elsewhere and an approving QC run When completed Then RC stays `QC`, an `ERROR` event names `no_open_blocker_bugs`, an escalation to ORCHESTRATOR exists | `tests/orchestrator/test_release_qc.py::test_qc_pass_blocked_escalates` |
| 6 | Given a `REJECTED` QC output without bugs When completed Then RC stays `QC` and `ERROR` names `rejection_bugs_created` | `tests/orchestrator/test_release_qc.py::test_qc_reject_without_bugs_kept_in_qc` |
| 7 | Given RC-01 `REJECTED` with two rejection bugs When the first completes Then no successor; when the second completes Then RC-02 `BUILDING` and a build is scheduled | `tests/orchestrator/test_release_rejection_loop.py::test_last_rejection_bug_triggers_next_rc` |
| 8 | Given the successor exists When `on_bug_completed` is called again Then no third RC | `tests/orchestrator/test_release_rejection_loop.py::test_next_rc_idempotent` |
| 9 | Given a completed reject cycle When the ledger is queried Then `RC_TRANSITION` events `create, build_ok, qc_reject, next_rc` for RC-01/RC-02 in order and one `QC_RESULT` per QC run | `tests/orchestrator/test_release_rejection_loop.py::test_reject_cycle_ledger_trail` |
| 10 | Given RC-01 in `QC` When `walk rc qc RC-01` Then exit 0 and the carrier id printed; RC in `PASSED` Then exit 2 | `tests/cli/test_cmd_rc_qc.py::test_rc_qc_reopens_step` |

#### Evidence required
- Quality gate output.
- Demo on the fixture repo with scripted fake QC outputs: `walk rc build RC-01` → `walk run --once` (QC rejects) → `walk rc show RC-01` (REJECTED, bug id) → bug loop via fakes → `walk rc list` (RC-02 BUILDING) → `walk ledger query --kind RC_TRANSITION`.

#### Notes
- Carrier-task mechanism (header, binding); §63 QC authority (only QC creates the rejection bugs, through `AgentOutput.new_bugs`); §64 bug loop unchanged; ARCHITECTURE §4.3 `QC_RESULT`/`BUG_CREATED` write point; E11-X01 item 5 confirms the single run-completion path.
- Release instructions are given in the carrier description (`release_step_brief`), not in `QC.md.j2`, so no `PROMPT` behaviour version changes in this story.
- `NEW NAME:` `RELEASE_STEP_CONTRACTS`, `release_step_brief`, hook callable `release_bug_complete_next_rc`, `ReleaseManager.open_step/on_run_completed/on_bug_completed`, `QC_RESULT` payload key `rc_id`, `CommandConsumer` command `rc.qc`, `walk rc qc`.
- Commit subject: `feat: add final qc and rejection loop for release candidates (E11-S04)`.

#### Evidence (filled by implementer)
_pending_

---

### E11-S05 — Store metadata as approved artifacts

**Status:** TODO
**Type:** feat
**Requirements:** §77, §33, §10.9, §137 (Inv. 4, 10)
**Depends on:** E11-S01, E02-S12
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Store listing content (§77: title, descriptions, localized texts, release notes, keywords, screenshots, icons) lives as one typed `.ai/release/store-metadata.md` document, is validated against store field limits, is reviewed by the UA/Release role through a `ua-review` carrier task, and on approval becomes an `ApprovedArtifact` of the new kind `STORE_METADATA` whose hash protects it from silent drift (Inv. 10).

#### Scope
- In: `ApprovedArtifactKind.STORE_METADATA`; `MemoryDocType.STORE_METADATA`; models `StoreMetadata`, `LocalizedListing`; `STORE_METADATA_SECTIONS`; module `walk.memory.store_metadata` (path, document conversion, validation, `STORE_FIELD_LIMITS`); module `walk.orchestrator.store_metadata` (`StoreMetadataReview`: draft init, review request, review completion); run-completion dispatch for `ua-review` carriers; command group `walk store metadata init|show|review`.
- Out: exporting metadata to a store and publishing (E11-S06); generating screenshots or creatives (assets are provided files; E08 art pipeline may produce them); UA participation before release for market feedback (§10.9 "MAY", not planned); RC existence checks for the review subject (the RC id is validated by format here and by E11-S06 at publish time, because this story does not depend on E11-S02).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/memory/models.py` | modify | `ApprovedArtifactKind.STORE_METADATA`, `MemoryDocType.STORE_METADATA` |
| `src/walk/workflow/release.py` | modify | `StoreMetadata`, `LocalizedListing` |
| `src/walk/memory/sections.py` | modify | `STORE_METADATA_SECTIONS` |
| `src/walk/memory/store_metadata.py` | create | `STORE_METADATA_PATH`, `STORE_FIELD_LIMITS`, `store_metadata_document`, `store_metadata_from_document`, `validate_store_metadata` |
| `src/walk/memory/__init__.py` | modify | re-exports |
| `src/walk/orchestrator/store_metadata.py` | create | `StoreMetadataReview` |
| `src/walk/orchestrator/service.py` | modify | — (run-completion path calls `StoreMetadataReview.on_review_completed` for `release_step_of(item) == UA_REVIEW`) `(verify)` |
| `src/walk/cli/cmd_store.py` | create | `store_app` (`metadata init`, `metadata show`, `metadata review`) |
| `src/walk/cli/app.py` | modify | — (registers `store_app`) |
| `src/walk/cli/composition.py` | modify | — (constructs `StoreMetadataReview`) |
| `docs/01-architecture/DOMAIN-MODEL.md` | modify | — (§3 `ApprovedArtifactKind.STORE_METADATA`, `MemoryDocType.STORE_METADATA`; models) |
| `docs/01-architecture/ARCHITECTURE.md` | modify | — (§8 `.ai/release/store-metadata.md`) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§6 `walk store metadata …`) |
| `tests/memory/test_store_metadata.py` | create | — |
| `tests/orchestrator/test_store_metadata_review.py` | create | — |
| `tests/cli/test_cmd_store_metadata.py` | create | — |

#### Interface contract
`ApprovedArtifact`, `MemoryManager.approve_artifact` per DOMAIN-MODEL §4.7 / INTERFACES §1.8; carrier labels per E11-S01; front matter per ARCHITECTURE §8.2.
```python
# src/walk/workflow/release.py — additions
class LocalizedListing(WalkModel):
    title: str
    short_description: str
    full_description: str
    release_notes: str
    keywords: list[str] = Field(default_factory=list)

class StoreMetadata(WalkModel):
    """§77 store listing content. Paths are repo-relative and must exist."""
    default_locale: str = Field(description="BCP 47 tag, e.g. 'en-US'")
    listings: dict[str, LocalizedListing] = Field(description="locale → listing; must contain default_locale")
    screenshots: dict[str, list[str]] = Field(description="BuildTarget value or 'all' → image paths")
    icons: list[str]

# src/walk/memory/sections.py
STORE_METADATA_SECTIONS = ("App Title", "Short Description", "Full Description", "Release Notes", "Keywords",
                           "Screenshots", "Icons", "Review Notes")    # localized variants as '### <locale>' sub-sections

# src/walk/memory/store_metadata.py
STORE_METADATA_PATH: str = "release/store-metadata.md"      # relative to .ai/
STORE_FIELD_LIMITS: dict[str, int] = {"title": 30, "short_description": 80, "full_description": 4000,
                                      "release_notes": 500, "keywords": 100}   # characters; keywords = joined with ","
def store_metadata_document(meta: StoreMetadata, *, title: str) -> MemoryDocument: ...
def store_metadata_from_document(doc: MemoryDocument) -> StoreMetadata: ...
def validate_store_metadata(meta: StoreMetadata, repo_root: Path) -> list[str]: ...     # [] when valid

# src/walk/orchestrator/store_metadata.py
class StoreMetadataReview:
    def __init__(self, memory: MemoryManager, workflow: WorkflowManager, repo_root: Path, clock: Clock) -> None: ...
    async def init_draft(self, *, actor: Actor) -> MemoryDocument: ...          # skeleton from ProjectContext; refuses to overwrite
    async def request_review(self, rc_id: ReleaseCandidateId, *, actor: Actor) -> WorkItem: ...
    async def on_review_completed(self, item: WorkItem, output: AgentOutput) -> ApprovedArtifact | None: ...
```
CLI: `walk store metadata init`; `walk store metadata show [--json]` (parsed model + validation problems); `walk store metadata review RC_ID` (prints the carrier id).

#### Behavior
1. `init_draft` writes `.ai/release/store-metadata.md` (`type: store_metadata`, `status: DRAFT`) through `MemoryManager.write`, prefilled from `ProjectContext` (title → `App Title`, summary → `Full Description`), one locale (`en-US` unless the project context names one); an existing file → `ConfigError` (never overwritten).
2. `validate_store_metadata` reports: default locale missing from `listings`; any field over `STORE_FIELD_LIMITS` (per locale); empty title or descriptions; screenshot or icon path missing on disk; no icon. The validation lines name locale and field.
3. `request_review(rc_id)`: `rc_id` must match `ReleaseCandidateId`; the draft must validate (`ConfigError` listing all problems, no carrier); creates (or returns the existing non-terminal) TASK carrier with labels `release_labels(rc_id, UA_REVIEW)`, `contract.owner_role = UA_RELEASE`, `required_evidence = []`, description = the parsed metadata summary + review checklist (§10.9 positioning, store listing, ASO, screenshots, release notes); state `READY` (routed to `(UA_RELEASE, "REVIEW")` by E11-S01).
4. `on_review_completed`: output `APPROVED` and no `context_updates` targeting the metadata document → `MemoryManager.approve_artifact(ApprovedArtifact(kind=STORE_METADATA, title=f"Store metadata {rc_id}", scope=rc_id, payload_paths=[document, screenshots…, icons…], related_requirements=[]), actor=Actor(role=UA_RELEASE, run_id=…))`; the previous `STORE_METADATA` artifact, if any, is `SUPERSEDED` (E02-S12); the document status becomes `APPROVED`.
5. Output `APPROVED` together with `context_updates` to the metadata document → treated as not approved (Inv. 4: a run that changed the content cannot approve it); the changes are kept, the status stays `DRAFT`, `Review Notes` records "changed by review; needs another review".
6. Output `REJECTED` → findings are appended to `Review Notes`, status `CHANGE_REQUESTED`; no artifact.
7. After approval, any write to the approved payload goes through E02-S12 rules (`ApprovedArtifactDrift` / change decision required); `verify_approved_artifacts` flags manual edits as `INVALID` (Inv. 10).
8. Approval authority comes from the `UA_RELEASE` constitution `may_approve: [STORE_METADATA]` (E11-S01) or the user (`walk artifacts approve`, E02-S12); any other role → `ApprovalNotAuthorized`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a metadata model with 2 locales, screenshots for Android and `all`, 1 icon When converted to a document and back Then equal and sections equal `STORE_METADATA_SECTIONS` | `tests/memory/test_store_metadata.py::test_store_metadata_document_roundtrip` |
| 2 | Given a 31-character title in `vi-VN` and a missing icon file When validated Then two problems naming `vi-VN title` and the icon path | `tests/memory/test_store_metadata.py::test_validation_limits_and_paths` |
| 3 | Given no draft When `init_draft` Then `.ai/release/store-metadata.md` with status DRAFT; called again Then `ConfigError` | `tests/orchestrator/test_store_metadata_review.py::test_init_draft_once` |
| 4 | Given an invalid draft When `request_review("RC-01")` Then `ConfigError` listing the problems and no carrier | `tests/orchestrator/test_store_metadata_review.py::test_review_requires_valid_draft` |
| 5 | Given a valid draft When `request_review("RC-01")` twice Then one TASK with labels `walk-release:RC-01`, `walk-release-step:ua-review`, owner `UA_RELEASE`, `READY` | `tests/orchestrator/test_store_metadata_review.py::test_review_carrier_created_once` |
| 6 | Given a fake UA_RELEASE run returning `APPROVED` without changes When completed Then an `ApprovedArtifact` of kind `STORE_METADATA`, `approved_by.role == UA_RELEASE`, payload includes screenshots and icon, `ARTIFACT_APPROVED` in the ledger | `tests/orchestrator/test_store_metadata_review.py::test_ua_approval_creates_store_metadata_artifact` |
| 7 | Given a UA run returning `APPROVED` with a `context_updates` entry on the document When completed Then no artifact and status `DRAFT` with a review note | `tests/orchestrator/test_store_metadata_review.py::test_changed_content_cannot_be_approved_in_same_run` |
| 8 | Given a UA run returning `REJECTED` with 2 findings When completed Then status `CHANGE_REQUESTED` and both findings in `Review Notes` | `tests/orchestrator/test_store_metadata_review.py::test_ua_rejection_records_findings` |
| 9 | Given approved metadata When the screenshot file is edited and `verify_approved_artifacts` runs Then the artifact id is reported drifted | `tests/orchestrator/test_store_metadata_review.py::test_approved_metadata_drift_detected` |
| 10 | Given a QC actor When approving `STORE_METADATA` Then `ApprovalNotAuthorized` | `tests/orchestrator/test_store_metadata_review.py::test_only_ua_or_user_may_approve` |
| 11 | Given `walk store metadata init` then `walk store metadata show --json` Then exit 0 and a JSON object with `default_locale` and a `problems` list | `tests/cli/test_cmd_store_metadata.py::test_store_metadata_init_and_show` |

#### Evidence required
- Quality gate output.
- Demo on the fixture repo: `walk store metadata init`, edit the draft, `walk store metadata show`, `walk store metadata review RC-01`, `walk run --once` with a scripted fake UA output, `walk artifacts list` showing the `STORE_METADATA` artifact.

#### Notes
- §33 approved artifacts; ADR-0003 D-4 (all `.ai/` writes through `MemoryManager`); E02-S12 payload hashing and drift; ADR-0013 (`may_approve`).
- `StoreMetadata` lives in `walk.workflow.release` because both `walk.memory` and `walk.integrations` (E11-S06 publishers) must import it and `workflow` is the lowest package both may import (ARCHITECTURE §2.2).
- `STORE_FIELD_LIMITS` are conservative common limits of the two stores named in §77; a store-specific stricter limit is enforced by the publisher's `validate` (E11-S06).
- E11-X01 item 8 assumed this story writes `.walk/release/<rc>/store-metadata.json`; that export belongs to publishing and moves to E11-S06.
- `NEW NAME:` `ApprovedArtifactKind.STORE_METADATA`, `MemoryDocType.STORE_METADATA`, `StoreMetadata`, `LocalizedListing`, `STORE_METADATA_SECTIONS`, module `walk.memory.store_metadata` (`STORE_METADATA_PATH`, `STORE_FIELD_LIMITS`, `store_metadata_document`, `store_metadata_from_document`, `validate_store_metadata`), `.ai/release/` folder, `StoreMetadataReview` (`walk.orchestrator.store_metadata`), document statuses `DRAFT`/`CHANGE_REQUESTED`/`APPROVED`, command group `walk store` (`metadata init|show|review`).
- Commit subject: `feat: add store metadata review as approved artifact (E11-S05)`.

#### Evidence (filled by implementer)
_pending_

---

### E11-S06 — Publishing integrations behind `store.publish`

**Status:** TODO
**Type:** feat
**Requirements:** §77, §92, §91, §90, §10.9, §137 (Inv. 7, 9, 14)
**Depends on:** E11-S02, E11-S04, E11-S05, E02-S11
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A `PASSED` RC with approved store metadata is published to Google Play and/or App Store Connect only through the KERNEL tool `store.publish`, which is a protected action: the UA/Release run pauses until the user runs `walk approve`, the approval and the publish are in the ledger, the kernel (never the agent) holds the store credentials and performs the upload idempotently, and the RC becomes `RELEASED` through the approval-guarded `release` event.

#### Scope
- In: `StoreProvider` protocol, `StoreValidation`, `StorePublishResult`; `GooglePlayProvider` (Play Developer Publishing API over `httpx`), `AppStoreConnectProvider` (App Store Connect API + Transporter upload through `SubprocessRunner`); `IntegrationManager.stores`; tool specs `store.validate` / `store.publish`; handlers registered with `ToolInvoker.register_handler`; publish carrier (`publish` step) and `ReleaseManager.request_publish`; store-metadata JSON export; `release` event after a successful publish; `walk rc release`; `FakeStoreProvider`; live tests marked `@pytest.mark.integration`.
- Out: producing an `.ipa` (E11-S03 Out — App Store publishing requires an `.ipa` `BUILD_ARTIFACT` provided outside the kernel; `store.validate` reports its absence); staged rollout percentages and review-status polling after submission (not planned); a direct USER publish path without the UA carrier (not planned; the protected-action approval is the user's control point).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/integrations/protocols.py` | modify | `StoreProvider`; `IntegrationManager.stores` |
| `src/walk/integrations/models.py` | modify | `StoreValidation`, `StorePublishResult` |
| `src/walk/integrations/store/__init__.py` | create | re-exports |
| `src/walk/integrations/store/google_play.py` | create | `GooglePlayProvider`, `GOOGLE_PLAY_CREDENTIAL` |
| `src/walk/integrations/store/app_store.py` | create | `AppStoreConnectProvider`, `APP_STORE_CREDENTIALS` |
| `src/walk/integrations/service.py` | modify | — (`DefaultIntegrationManager` holds `stores`) `(verify E03-S03)` |
| `src/walk/tools/defaults/tools.yaml` | modify | — (`store.validate`: KERNEL, provider `store`; `store.publish`: KERNEL, provider `store`, `protected_action: store.publish`) |
| `src/walk/orchestrator/protocols.py` | modify | `ReleaseManager.request_publish` |
| `src/walk/orchestrator/release.py` | modify | `store_tool_handlers`, `export_store_metadata`, `DefaultReleaseManager.request_publish`; `on_run_completed` handles the `publish` step |
| `src/walk/orchestrator/commands.py` | modify | — (command `rc.release`) |
| `src/walk/cli/cmd_rc.py` | modify | `rc_app` (`release`) |
| `src/walk/cli/composition.py` | modify | — (builds store providers from `CredentialStore`; registers `store_tool_handlers` with `ToolInvoker.register_handler`) |
| `tests/fakes/fake_store_provider.py` | create | `FakeStoreProvider` |
| `docs/01-architecture/INTERFACES.md` | modify | — (new §2.7 `StoreProvider`; §1.12 `stores`; `ReleaseManager.request_publish`; §6 `walk rc release`) |
| `docs/01-architecture/DOMAIN-MODEL.md` | modify | — (§4.13 `StoreValidation`, `StorePublishResult`) |
| `tests/integrations/test_store_google_play.py` | create | — |
| `tests/integrations/test_store_app_store.py` | create | — |
| `tests/integrations/test_store_live.py` | create | — |
| `tests/orchestrator/test_release_publish.py` | create | — |
| `tests/orchestrator/test_release_publish_approval.py` | create | — |
| `tests/cli/test_cmd_rc_release.py` | create | — |

#### Interface contract
Protected actions: ARCHITECTURE §6 (`store.publish` default, approver USER), ADR-0006 D-2/D-3/D-4; approvals: INTERFACES §1.10, E02-S11; `KernelToolHandler` / `register_handler`: E01-S26; credentials: ADR-0009 D-8; `StoreMetadata`: E11-S05.
```python
# src/walk/integrations/models.py
class StoreValidation(FrozenModel):
    store: str
    ok: bool
    problems: list[str]

class StorePublishResult(FrozenModel):
    store: str
    track: str
    remote_ref: str            # Play edit id / version code; App Store build id
    submitted_at: datetime
    artifact_path: str
    artifact_sha256: str

# src/walk/integrations/protocols.py
class StoreProvider(Protocol):
    """§77 store publishing. Kernel-side only; credentials from CredentialStore."""
    name: str                                                    # "google_play" | "app_store"
    targets: frozenset[BuildTarget]                              # {ANDROID} | {IOS}
    async def validate(self, artifact_path: str, metadata: StoreMetadata, *, track: str) -> StoreValidation: ...
    async def publish(self, artifact_path: str, metadata: StoreMetadata, *, track: str) -> StorePublishResult: ...

# src/walk/integrations/store/google_play.py
GOOGLE_PLAY_CREDENTIAL: str = "google_play_service_account_json"
class GooglePlayProvider:      # edits.insert → bundles.upload (.aab) → listings.update per locale → tracks.update → edits.commit
    def __init__(self, credentials: CredentialStore, package_name: str, http: httpx.AsyncClient, clock: Clock) -> None: ...

# src/walk/integrations/store/app_store.py
APP_STORE_CREDENTIALS: tuple[str, ...] = ("app_store_connect_key_id", "app_store_connect_issuer_id", "app_store_connect_private_key")
class AppStoreConnectProvider: # .ipa upload via Transporter (SubprocessRunner) + appStoreVersionLocalizations via API
    def __init__(self, credentials: CredentialStore, app_id: str, http: httpx.AsyncClient, runner: SubprocessRunner, clock: Clock) -> None: ...

# src/walk/orchestrator/release.py
def store_tool_handlers(release: ReleaseManager, integrations: IntegrationManager, memory: MemoryManager,
                        permissions: PermissionManager) -> dict[ToolName, KernelToolHandler]: ...
    # "store.validate" args {rc_id, store, track} → StoreValidation JSON
    # "store.publish"  args {rc_id, store, track} → StorePublishResult JSON (+ rc state)
def export_store_metadata(rc: ReleaseCandidate, metadata: StoreMetadata, output_dir: Path) -> Path: ...   # <output_dir>/<RC-id>/store-metadata.json (atomic_write)

# ReleaseManager addition
async def request_publish(self, rc_id: ReleaseCandidateId, *, stores: list[str], track: str, actor: Actor) -> WorkItem: ...
    """RC must be PASSED and an APPROVED, non-drifted STORE_METADATA artifact must exist; opens the publish carrier
    (open_step(PUBLISH), E11-S04) whose description names stores, track and artifacts."""
```
CLI: `walk rc release RC_ID --store google_play|app_store [--store …] [--track internal|alpha|beta|production|testflight]` — opens the publish step and prints the carrier id; the actual publish waits for `walk approve`.

#### Behavior
1. `request_publish`: RC state must be `PASSED` (`GuardRejected`); the latest `STORE_METADATA` artifact must be `APPROVED` and pass `verify_approved_artifacts` (`ConfigError` naming the artifact otherwise); each requested store must be configured in `IntegrationManager.stores` (`ConfigError`); opens the `publish` carrier (routed to `(UA_RELEASE, "IMPLEMENT")`, E11-S01).
2. `store.validate` (ALLOW for `UA_RELEASE`): resolves the artifact for the store's target from the RC `BUILD_ARTIFACT` evidence (`.aab` for Google Play; `.ipa` for App Store — absent → problem `ipa required`), loads the approved metadata (`store_metadata_from_document` of the approved payload), returns the provider's `StoreValidation`; no side effects.
3. `store.publish` is `PermissionEffect.REQUIRE_APPROVAL(approver=USER)` for every role (protected action, ADR-0006 D-3: cannot be downgraded by project or constitution rules); the UA run pauses (`PAUSED_FOR_APPROVAL`), `APPROVAL_REQUESTED` is in the ledger with payload `{tool: store.publish, rc_id, store, track}`; nothing is uploaded before `walk approve`; `walk deny` → the tool returns `PermissionDenied` to the run and the RC stays `PASSED`.
4. After approval the handler: re-checks rules 1–2 (state may have changed while paused); exports `store-metadata.json`; runs `provider.publish` inside `IntegrationManager.with_idempotency(f"store.publish:{rc_id}:{store}:{track}", …)` so a retried or resumed call returns the stored `remote_ref` without uploading again (§90); records the result as `PROJECT_DATA` evidence (`StorePublishResult` JSON); then, when every store requested by the carrier has a stored result, raises `ReleaseManager.event(rc, "release", actor=UA_RELEASE, extra={"approval_id": <approved request id>})` → guard `approval_user` → `RELEASED`.
5. The approved request id is found through the approvals repository by `(run_id, tool == "store.publish")` with state `APPROVED` (`ConfigError` if none — defence in depth: the handler never runs without an approved request).
6. Credentials are read only by the providers through `CredentialStore` (env var, then keyring); they never appear in tool arguments, results, the ledger, logs or `.ai/` (§91); provider HTTP errors become `ProviderUnavailable`/`PermanentError` with the store's message, the RC stays `PASSED`.
7. `on_run_completed` for the `publish` step: output `COMPLETED` with the RC `RELEASED` → carrier `COMPLETE`; output `COMPLETED` while the RC is not `RELEASED` → `ERROR` ledger event and escalation to the user (the agent claimed success without a publish).
8. `GooglePlayProvider` uses the documented edit flow (insert edit, upload bundle, update listings per locale, update track, commit) through an injected `httpx.AsyncClient`; `AppStoreConnectProvider` uploads with Transporter through `SubprocessRunner` and updates localizations through the API with a JWT signed from the key credentials. Unit tests use `httpx.MockTransport` and `FakeSubprocessRunner`; live calls exist only in `tests/integrations/test_store_live.py`, marked `@pytest.mark.integration` and skipped by default.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given an RC in `QC` When `request_publish` Then `GuardRejected`; given a `PASSED` RC without approved metadata Then `ConfigError` | `tests/orchestrator/test_release_publish.py::test_request_publish_preconditions` |
| 2 | Given a `PASSED` RC and approved metadata When `request_publish(stores=["google_play"], track="internal")` Then one `publish` carrier for `UA_RELEASE` in `READY` | `tests/orchestrator/test_release_publish.py::test_request_publish_opens_carrier` |
| 3 | Given the RC has only an iOS `.zip` artifact When `store.validate` for `app_store` Then `ok == False` with problem `ipa required` | `tests/orchestrator/test_release_publish.py::test_validate_reports_missing_ipa` |
| 4 | Given a fake UA run calling `store.publish` When the tool is invoked Then an `ApprovalRequest(kind="PROTECTED_ACTION", approver=USER)` is PENDING, the run is paused, and `FakeStoreProvider.publish_calls == 0` | `tests/orchestrator/test_release_publish_approval.py::test_publish_pauses_for_user_approval` |
| 5 | Given that pending request When `walk approve APV-… --note ok` Then the provider is called once, `store-metadata.json` exists, the RC is `RELEASED`, and the ledger holds `APPROVAL_REQUESTED`, `APPROVAL_DECIDED`, `TOOL_INVOKED(store.publish)`, `RC_TRANSITION(release)` in that order | `tests/orchestrator/test_release_publish_approval.py::test_approved_publish_releases_rc` |
| 6 | Given a pending request When `walk deny` Then the provider is not called, the run receives `PermissionDenied`, the RC stays `PASSED` | `tests/orchestrator/test_release_publish_approval.py::test_denied_publish_keeps_rc_passed` |
| 7 | Given a project `permissions.yaml` rule `UA_RELEASE store.publish ALLOW` When rules are merged Then `ConfigError` (protected action cannot be downgraded) | `tests/orchestrator/test_release_publish_approval.py::test_publish_approval_cannot_be_downgraded` |
| 8 | Given a publish interrupted after the provider returned When the handler runs again with the same arguments Then no second provider call and the same `remote_ref` | `tests/orchestrator/test_release_publish.py::test_publish_idempotent` |
| 9 | Given the handler invoked without an approved request for the run When executed Then `ConfigError` and no provider call | `tests/orchestrator/test_release_publish.py::test_handler_refuses_without_approved_request` |
| 10 | Given a UA output `COMPLETED` while the RC is still `PASSED` When the carrier completes Then an `ERROR` event and a user escalation | `tests/orchestrator/test_release_publish.py::test_publish_step_claim_without_release_escalates` |
| 11 | Given a `MockTransport` recording requests When `GooglePlayProvider.publish` Then the calls are edit insert, bundle upload, one listing update per locale, track update, commit — and no credential value appears in logs or the result | `tests/integrations/test_store_google_play.py::test_publish_edit_flow_and_secret_hygiene` |
| 12 | Given a Play API 403 When publishing Then `PermanentError` with the store message | `tests/integrations/test_store_google_play.py::test_publish_maps_http_errors` |
| 13 | Given `FakeSubprocessRunner` and `MockTransport` When `AppStoreConnectProvider.publish` with an `.ipa` Then Transporter is invoked with the ipa path and localizations are updated per locale | `tests/integrations/test_store_app_store.py::test_publish_uploads_ipa_and_localizations` |
| 14 | Given real credentials in the environment When the integration test runs Then a Play `internal` track upload succeeds (skipped by default) | `tests/integrations/test_store_live.py::test_google_play_internal_track_upload` |
| 15 | Given `walk rc release RC-02 --store google_play --track internal` Then exit 0 and the carrier id printed; for an RC in `QC` Then exit 2 | `tests/cli/test_cmd_rc_release.py::test_rc_release_opens_publish_step` |

#### Evidence required
- Quality gate output (integration tests skipped).
- Demo on the fixture repo with `FakeStoreProvider`: `walk rc release RC-02 --store google_play --track internal`, `walk run --once` (UA run pauses), `walk approvals --pending`, `walk approve APV-… --note "ship"`, `walk rc show RC-02` (`RELEASED`), `walk ledger query --kind APPROVAL_REQUESTED --kind APPROVAL_DECIDED --kind RC_TRANSITION`.

#### Notes
- §92 "publish store build" protected; Invariant 7 and 14 (the user retains final authority); ADR-0006 D-2 (kernel executes side effects), D-3, D-4 (approval pauses the run); ADR-0009 D-8 (credentials); ARCHITECTURE §4.2 (KERNEL tools enforced at `ToolInvoker`).
- Implementation-order note: this story uses `ReleaseManager` (E11-S02) and `open_step` (E11-S04), which WBS §5 does not list as dependencies of E11-S06 (only E11-S05, E02-S11); the header's parallel-set line also expects S06 after S02. E11-X01 must confirm E11-S02 and E11-S04 are merged first or add them as dependencies.
- Store metadata JSON export moved here from E11-S05 (E11-X01 item 8).
- `NEW NAME:` `StoreProvider` (INTERFACES §2.7), `StoreValidation`, `StorePublishResult`, package `walk.integrations.store` (`GooglePlayProvider`, `AppStoreConnectProvider`, `GOOGLE_PLAY_CREDENTIAL`, `APP_STORE_CREDENTIALS`), `IntegrationManager.stores`, tool specs `store.validate`/`store.publish` (provider `store`), `store_tool_handlers`, `export_store_metadata`, `.walk/release/<RC-id>/store-metadata.json`, `ReleaseManager.request_publish`, `CommandConsumer` command `rc.release`, `walk rc release`, `FakeStoreProvider`.
- Commit subject: `feat: publish release candidates behind approved store.publish (E11-S06)`.

#### Evidence (filled by implementer)
_pending_

---

### E11-S07 — Polish phase template

**Status:** TODO
**Type:** feat
**Requirements:** §75, §66, §74, §52, §137 (Inv. 7, 14)
**Depends on:** E11-X01, E07-S05
**Effort:** LOW   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
After functional GDD completion the user can create a dedicated polish phase from a data-declared template: `walk phase create --template polish` creates a `PLANNED` phase whose goal shifts from "Does it work?" to "Is it good?" and whose scope is one `Polish` epic with one `IDEA` feature per selected §75 focus area, ready for the normal phase start, planning and gate flow.

#### Scope
- In: phase-template data format and loader; `polish.yaml` with the twelve §75 areas; `instantiate_phase_template`; `walk phase create --template polish [--areas …]`; GDD-coverage warning (§74) when functional completion is not reached.
- Out: decomposition of polish features into stories (the existing ORCHESTRATOR `PLAN` route, INTERFACES §4); release candidates (E11-S02); other phase templates (only `polish` ships; the format allows more).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/workflow/phase_templates.py` | create | `PhaseTemplate`, `PhaseTemplateArea`, `load_phase_template`, `PHASE_TEMPLATES_DIR` |
| `src/walk/workflow/phase_templates/polish.yaml` | create | — (`version: "1.0"`, twelve areas, table below) |
| `src/walk/workflow/__init__.py` | modify | re-exports |
| `src/walk/orchestrator/phase_templates.py` | create | `instantiate_phase_template`, `PhaseTemplateResult` |
| `src/walk/cli/cmd_phase.py` | modify | `phase_app` (`create --template NAME [--areas A…] [--ordinal N] [--name TEXT]`) `(verify whether E06/E07 added phase creation; modify that command if so)` |
| `docs/01-architecture/INTERFACES.md` | modify | — (§6 `walk phase create --template`) |
| `tests/workflow/test_phase_templates.py` | create | — |
| `tests/orchestrator/test_phase_templates_instantiate.py` | create | — |
| `tests/cli/test_cmd_phase_create_template.py` | create | — |

#### Interface contract
`Phase`, `WorkItemDraft`, `StoryContract` per DOMAIN-MODEL §4.1; `WorkflowManager.create_phase` (E01-S11), `create`, `gdd_coverage` per INTERFACES §1.3.
```python
# src/walk/workflow/phase_templates.py
PHASE_TEMPLATES_DIR: str = "workflow/phase_templates"          # package-relative

class PhaseTemplateArea(WalkModel):
    key: str                      # snake_case, unique
    title: str
    intent: str                   # feature description seed
    acceptance_hints: list[str]   # become contract.acceptance_criteria seeds

class PhaseTemplate(WalkModel):
    name: str                     # "polish"
    version: str                  # "MAJOR.MINOR"
    phase_name: str               # "Polish"
    goal: str                     # §75 "Does it work?" → "Is it good?"
    epic_title: str
    areas: list[PhaseTemplateArea]
    requires_gdd_coverage: float = Field(ge=0.0, le=1.0, description="warn below this §74 coverage")

def load_phase_template(name: str, *, root: Path | None = None) -> PhaseTemplate: ...

# src/walk/orchestrator/phase_templates.py
class PhaseTemplateResult(FrozenModel):
    phase: Phase
    epic_id: EpicId
    feature_ids: list[FeatureId]
    warnings: list[str]

async def instantiate_phase_template(workflow: WorkflowManager, template: PhaseTemplate, *, project_key: ProjectKey,
                                     ordinal: int | None, areas: list[str] | None, name: str | None) -> PhaseTemplateResult: ...
```
`polish.yaml` areas (§75 verbatim order): `game_feel`, `vfx`, `animation`, `sound`, `ux`, `pacing`, `clarity`, `balance`, `performance`, `stability`, `device_compatibility`, `technical_debt`; `goal: "Shift from 'Does it work?' to 'Is it good?' (§75)"`; `requires_gdd_coverage: 1.0`.

CLI: `walk phase create --template polish [--areas game_feel,performance] [--ordinal N] [--name TEXT] [--json]`.

#### Behavior
1. `load_phase_template` validates: unique area keys; non-empty `areas`; `version` matches `^\d+\.\d+$`; unknown template name → `ConfigError` listing available names.
2. `instantiate_phase_template`: `areas` default to all template areas; an unknown key → `ConfigError` before anything is created; `ordinal` defaults to max existing ordinal + 1; creates the phase via `create_phase(name or template.phase_name, ordinal, goal=template.goal, scope_epic_ids=[epic])`, one `EPIC` (`template.epic_title`) and one `FEATURE` per area in `IDEA` (`title` = area title, `description` = intent, `contract.acceptance_criteria` = acceptance hints), all in one `UnitOfWork`; ledger `WORK_ITEM_CREATED` per item from the workflow write point.
3. Functional-completion check (§75 "after functional GDD completion"): when `gdd_coverage(project_key)` has any area below `requires_gdd_coverage`, the result carries a warning per area and the CLI prints them; creation is not blocked (§75 SHOULD; the user decides at the phase gate, Inv. 14).
4. The created phase is `PLANNED`; starting it uses the existing `walk phase start` guards (`previous_phase_complete_or_first`, `scope_non_empty`); features are decomposed by the ORCHESTRATOR `PLAN` route once the phase is `ACTIVE`.
5. Re-running with the same `ordinal` → `ConfigError` (unique ordinal, E01-S11 rule 1) and nothing created.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the shipped `polish.yaml` When loaded Then 12 areas in §75 order with non-empty intents | `tests/workflow/test_phase_templates.py::test_polish_template_matches_section_75` |
| 2 | Given a template with duplicate area keys When loaded Then `ConfigError`; given name `bogus` Then `ConfigError` listing `polish` | `tests/workflow/test_phase_templates.py::test_template_validation` |
| 3 | Given two completed phases When `instantiate_phase_template(polish)` Then phase `PHASE-03` `PLANNED` with the template goal, one EPIC and 12 FEATUREs in `IDEA` under it | `tests/orchestrator/test_phase_templates_instantiate.py::test_instantiate_all_areas` |
| 4 | Given `areas=["performance", "stability"]` When instantiated Then exactly 2 features with those titles and acceptance hints as criteria | `tests/orchestrator/test_phase_templates_instantiate.py::test_instantiate_selected_areas` |
| 5 | Given `areas=["bogus"]` When instantiated Then `ConfigError` and no phase or item created | `tests/orchestrator/test_phase_templates_instantiate.py::test_unknown_area_creates_nothing` |
| 6 | Given GDD coverage 0.8 for area `Combat` When instantiated Then one warning naming `Combat` and the phase still created | `tests/orchestrator/test_phase_templates_instantiate.py::test_gdd_coverage_warning_not_blocking` |
| 7 | Given `walk phase create --template polish --areas performance --json` Then exit 0 and JSON with `phase.id`, `epic_id`, one `feature_ids` entry; repeating with the same `--ordinal` Then exit 1 | `tests/cli/test_cmd_phase_create_template.py::test_phase_create_polish_cli` |

#### Evidence required
- Quality gate output.
- Demo on the E07 gate fixture repo: `walk phase create --template polish --areas performance,stability`, `walk phase list`, `walk work list --phase PHASE-0N`.

#### Notes
- §75 lists polish focus areas; the template only seeds work, it adds no workflow state or guard (data, CONVENTIONS §4).
- E11-X01 item 11 decides whether `walk phase create` already exists; this story then extends it with `--template` instead of adding a second command.
- `NEW NAME:` module `walk.workflow.phase_templates` (`PhaseTemplate`, `PhaseTemplateArea`, `load_phase_template`, `PHASE_TEMPLATES_DIR`), data file `workflow/phase_templates/polish.yaml`, module `walk.orchestrator.phase_templates` (`instantiate_phase_template`, `PhaseTemplateResult`), `walk phase create --template`.
- Commit subject: `feat: add polish phase template (E11-S07)`.

#### Evidence (filled by implementer)
_pending_

---

### E11-S08 — Epic gate: RC1 reject → RC2 release (e2e)

**Status:** TODO
**Type:** feat
**Requirements:** §75, §76, §77, §92, §136 (`RELEASE CANDIDATE → FINAL QC → STORE / RELEASE`), §137 (Inv. 4, 7, 9, 10, 14)
**Depends on:** E11-S04, E11-S06, E11-S07
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** QC   **Reviewer role:** LeadDev

#### Goal
One end-to-end scenario with fakes proves the release flow: a polish phase is created from the template, RC1 is built for all targets, final QC rejects it with a BLOCKER bug, the bug loop fixes it and the kernel creates and builds RC2, QC passes RC2, store metadata is approved by UA/Release, and publishing happens only after `walk approve` — ending `RELEASED` with a complete `RC_TRANSITION` and approval trail in the ledger.

#### Scope
- In: `tests/e2e/test_e11_gate.py`; fixture `e11_scenario` / model `E11Scenario`; scripted fake outputs for QC, SENIOR_DEV, LEAD_DEV and UA_RELEASE runs.
- Out: production code (defects → `E11-Bxx` bugfix stories); real Unity or store calls (covered by `@pytest.mark.integration` tests of E11-S03/S06, skipped by default).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `tests/e2e/test_e11_gate.py` | create | — |
| `tests/e2e/conftest.py` | modify | `e11_scenario` fixture, `E11Scenario` `(verify: builds on the E07 scenario helpers)` |

#### Interface contract
Fixture `e11_scenario(tmp_game_repo) -> E11Scenario` (`WalkModel` in conftest): `handle: KernelHandle`, `project_key: ProjectKey` (`"DEMO"`), `polish_phase_id: PhaseId`, `store: FakeStoreProvider`, `unity: FakeUnityProvider`, `release_config: ReleaseConfig` (`targets: [Android, iOS]`). Settings: `UA_RELEASE` enabled; `.ai/release/store-metadata.md` valid with one locale, two screenshots and one icon committed in the temp repo; `FakeModelAdapter` scripts: QC run on RC1 → `REJECTED` with one `BLOCKER` `new_bugs` entry and a `QC_REPORT` evidence; bug-loop runs (triage, fix with commit, review, re-test) → pass; QC run on RC2 → `APPROVED` with a `QC_REPORT`; UA_RELEASE `ua-review` → `APPROVED` with no changes; UA_RELEASE `publish` → tool calls `store.validate` then `store.publish` (`google_play`, track `internal`), then `COMPLETED`. All other adapters, providers and the clock are fakes (WBS §3.6); real temporary git repository; `LocalWorkProvider`.

#### Behavior
Scenario steps (each a test, executed in order via the fixture's cached state):
1. `walk phase create --template polish --areas performance,stability` creates a `PLANNED` polish phase with two `IDEA` features (E11-S07); it is not started in this scenario (release flow does not depend on it).
2. `walk rc create` → `RC-01` `BUILDING`; the build runs for Android and iOS through the fake Unity provider; two `BUILD_ARTIFACT` evidence rows; RC-01 → `QC`; a `qc` carrier exists.
3. The QC run rejects: one `BLOCKER` bug with `against_commit == RC-01.commit`; RC-01 → `REJECTED` with that bug as rejection bug; one `QC_RESULT` with `rc_id == "RC-01"`.
4. The bug loop (E03-S15) completes the bug; the kernel raises `next_rc`: `RC-02` `BUILDING` at the new `main` HEAD (contains the fix commit), built, → `QC`.
5. The QC run approves RC-02 → `PASSED` (`no_open_blocker_bugs` holds).
6. `walk store metadata review RC-02` → UA review approves → `ApprovedArtifact` of kind `STORE_METADATA`.
7. `walk rc release RC-02 --store google_play --track internal` → publish carrier → UA run calls `store.validate` (ok) then `store.publish` → run paused, one PENDING `PROTECTED_ACTION` approval for USER, `FakeStoreProvider.publish_calls == 0`.
8. `walk approve APV-… --note ship` → publish executed once with the `.aab` of RC-02 and the approved metadata; RC-02 → `RELEASED`; the carrier `COMPLETE`.
9. Ledger trail: `RC_TRANSITION` events in order `RC-01 create`, `RC-01 build_ok`, `RC-01 qc_reject`, `RC-01 next_rc` (successor RC-02 created in `BUILDING`), `RC-02 build_ok`, `RC-02 qc_pass`, `RC-02 release`; `APPROVAL_REQUESTED` before `APPROVAL_DECIDED` before `RC_TRANSITION(release)`; `ARTIFACT_APPROVED` for the store metadata before `APPROVAL_REQUESTED`.
10. Invariants: no agent run wrote under `.ai/approved/` or used store credentials (no credential value in the ledger, logs or `.ai/`); `RELEASED` is unreachable without the approved request (asserted by replaying step 8 with `walk deny` on a fresh fixture copy → RC stays `PASSED`).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the fixture When `walk phase create --template polish --areas performance,stability` Then a `PLANNED` phase with 2 `IDEA` features | `tests/e2e/test_e11_gate.py::test_polish_phase_created_from_template` |
| 2 | Given `walk rc create` When the build completes Then RC-01 `QC` with Android and iOS artifacts and a QC carrier | `tests/e2e/test_e11_gate.py::test_rc1_built_for_all_targets` |
| 3 | Given the scripted QC rejection When applied Then RC-01 `REJECTED` with one BLOCKER rejection bug against its commit | `tests/e2e/test_e11_gate.py::test_rc1_rejected_with_blocker_bug` |
| 4 | Given the bug loop completes the bug Then RC-02 is created automatically at the fix commit and reaches `QC` | `tests/e2e/test_e11_gate.py::test_rc2_created_after_bug_fixed` |
| 5 | Given the scripted QC approval Then RC-02 `PASSED` | `tests/e2e/test_e11_gate.py::test_rc2_passes_final_qc` |
| 6 | Given the UA review approval Then a `STORE_METADATA` approved artifact exists | `tests/e2e/test_e11_gate.py::test_store_metadata_approved_by_ua` |
| 7 | Given `walk rc release RC-02` and the UA publish run Then a PENDING user approval and no store call | `tests/e2e/test_e11_gate.py::test_publish_waits_for_walk_approve` |
| 8 | Given `walk approve` Then one store publish call and RC-02 `RELEASED` | `tests/e2e/test_e11_gate.py::test_release_after_approval` |
| 9 | Given the ledger Then the `RC_TRANSITION` and approval events appear in the order of Behavior 9 | `tests/e2e/test_e11_gate.py::test_rc_transition_trail` |
| 10 | Given a fresh copy denied at step 8 Then RC-02 stays `PASSED` and no store call; and no credential value appears in ledger, logs or `.ai/` | `tests/e2e/test_e11_gate.py::test_release_impossible_without_user_approval` |

#### Evidence required
- Quality gate output including `tests/e2e/test_e11_gate.py` (10 passed).
- Demo transcript on the fixture repo: `walk rc create`, `walk rc list` after each step, `walk rc show RC-01`, `walk approvals --pending`, `walk approve APV-…`, `walk rc show RC-02`, `walk ledger query --kind RC_TRANSITION`.

#### Notes
- WBS §9 maps "Release" of §136 to this story; the gate scenario is the WBS §4 E11 gate extended with the polish template and store-metadata approval so every E11 story is exercised.
- Any production change needed is a separate `bugfix` story; this commit touches tests only.
- `NEW NAME:` `e11_scenario` fixture, `E11Scenario` (`tests/e2e/conftest.py`).
- Commit subject: `feat: add epic 11 gate test for release flow (E11-S08)`.

#### Evidence (filled by implementer)
_pending_

---

### E11-R01 — Review E11

**Status:** TODO
**Type:** docs
**Requirements:** §137 (Inv. 4, 7, 9, 10, 14), §76, §77, §92
**Depends on:** E11-S08
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
An independent agent instance (a different model than the E11 implementer where possible, §23) verifies every E11 story against the Definition of Done and the release invariants — publishing only after explicit user approval, kernel-held credentials, RC state changed only through `rc_workflow` — recording defects as `E11-Bxx` bugfix stories.

#### Scope
- In: stories E11-S01…S08 and their commits; `INTERFACES.md` (`ReleaseManager`, §2.7 `StoreProvider`, §3.2 row, §4 rows, §6), `DOMAIN-MODEL.md`, `ARCHITECTURE.md` (§8 `.ai/release/`) deltas; WBS §3.4/§6 entries from this epic; the shared-file merge with E10-S07; architecture tests listed below.
- Out: fixing defects (each becomes `E11-Bxx`); production code.

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-11-release.md` | modify | — (review record appended; `E11-Bxx` stories appended if any) |
| `docs/02-work-breakdown/WBS.md` | modify | — (§5 status rows, §6 register) |
| `docs/01-architecture/INTERFACES.md`, `docs/01-architecture/DOMAIN-MODEL.md`, `docs/01-architecture/ARCHITECTURE.md` | modify (only if drift found) | — |
| `tests/architecture/test_release_boundaries.py` | create | — |

#### Interface contract
Reviewer protocol, IMPLEMENTATION-PROTOCOL.md "Reviewer protocol" steps 1–5, plus the checks under Behavior.

#### Behavior
1. For each story: `git show <sha>`; Files table equals changed files (extra files need commit-body justification); every acceptance-criterion test exists and passes; coverage ≥ 90 % for touched modules.
2. Invariant 7 / §92: `store.publish` has `protected_action: store.publish` in `tools.yaml`; no code path calls a `StoreProvider.publish` except the `store.publish` handler; the handler refuses to run without an `APPROVED` request for the run.
3. §91 / ADR-0009 D-8: store credentials are read only in `walk.integrations.store` through `CredentialStore`; no agent-facing tool argument or result contains a credential name's value; `walk.integrations.store` imports nothing from `walk.agents`, `walk.runtime`, `walk.orchestrator`.
4. RC state changes only through `WorkflowManager.rc_event` / `create_rc`: no `UPDATE release_candidates` outside `walk.workflow`.
5. Invariant 10: `STORE_METADATA` artifacts go through `MemoryManager.approve_artifact`; no module writes under `.ai/approved/` directly.
6. `story_workflow.yaml` contains both `release_step_done` (E11-S01) and `analysis_done` (E10-S07) when E10 is merged, with the version set by the merge-order rule (E10-S07 Notes).
7. `NEW NAME:` items of E11 (story Notes) are present in WBS §6 or listed in the review note for the architect; the dependency-order notes of E11-S06 are resolved in WBS §5.
8. Defects → `E11-Bxx` stories using the template.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given each E11 story When the DoD checklist is applied Then every box is checked or an `E11-Bxx` story exists | manual checklist recorded in this story's Evidence |
| 2 | Given `src/walk` When searching calls to `.publish(` on store providers Then only the `store.publish` handler in `walk.orchestrator.release` matches | `tests/architecture/test_release_boundaries.py::test_store_publish_single_call_site` |
| 3 | Given `src/walk/integrations/store` When its imports are parsed Then none of `walk.agents`, `walk.runtime`, `walk.orchestrator` | `tests/architecture/test_release_boundaries.py::test_store_package_imports` |
| 4 | Given `src/walk` When grepping `UPDATE release_candidates` Then matches only under `src/walk/workflow/` | `tests/architecture/test_release_boundaries.py::test_rc_state_changed_only_by_workflow` |
| 5 | Given `tools.yaml` When loaded Then `store.publish.protected_action == "store.publish"` and the default protected-action list contains it with approver USER | `tests/architecture/test_release_boundaries.py::test_store_publish_is_protected` |
| 6 | Given the quality gate on `main` Then green with overall coverage ≥ 85 % and `tests/e2e/test_e11_gate.py` passing | manual checklist recorded in this story's Evidence |

#### Evidence required
- Checklist per story (ID → DoD items → OK/defect id).
- Quality gate output on `main` after the review commit.
- List of `E11-Bxx` stories created (or "none").

#### Notes
- Tests 2–5 are architecture tests created by the reviewer (review tasks may add tests, never production code).
- Commit subject: `docs: review epic 11 stories E11-S01..S08 (E11-R01)`.

#### Evidence (filled by implementer)
_pending_

---

