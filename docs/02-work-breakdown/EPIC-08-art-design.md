# EPIC-08 — Art / Design

**Roadmap stage:** §135 Stage 8
**Goal.** Design Leader and Art Director take part in the feature workflow; generated assets come from pluggable `AssetProvider`s (Meshy, OpenArt) through one kernel-executed `asset.generate` path that is idempotent, metered as `EXTERNAL_CREDITS`/`ASSETS` cost, validated against §79 rules held as data, recorded with §80 provenance and visual evidence (screenshots), reviewed by the Art Director (who may reject a technically valid asset, §10.5), and registered as `ApprovedArtifact(kind=ASSET)` (§33); Unity MCP becomes an optional `ToolKind.MCP` provider (ADR-0009 D-6).
**Requirements.** §10.4–§10.5, §33 (art kinds, change workflow), §78–§80, §6.5 (`ART_COMPLETE`, `DESIGN_VALIDATED`), §84 (Assets cost branch), §90 (idempotency), §30–§31 (tool kinds, permissions), §137 (Inv. 7, 9, 10).
**Epic gate.** `tests/e2e/test_e08_gate.py`: a feature requiring an asset triggers `asset.generate` via a fake `AssetProvider`, the asset is validated by `FakeUnityProvider.validate_assets`, provenance file + evidence recorded, fake ART_DIRECTOR rejects then approves, `ART_COMPLETE` dimension set, asset registered as `ApprovedArtifact(kind=ASSET)`.
**Branching.** Every story uses `story/<ID>-<slug>` + worktree (COMMIT-POLICY §4); merge `--no-ff` after E08-R01.
**Preconditions.** E07-R01 `DONE` with no `BLOCKER` bugfix stories; `main` green. E08 runs in parallel with E09 (WBS §7.1); E08 stories never touch E09 files (`src/walk/telemetry/reports.py`, `src/walk/telemetry/provenance.py`, `0003_dashboard_views.sql`, `src/walk/cli/cmd_report.py`, `src/walk/cli/cmd_status.py`).
**Refine first.** E08-X01 re-validates every Files table below against the `src/walk/` tree as it exists after E07-R01 — E01 (S27–S31), E03 (S09–S20), E05 (S04–S10) and E07 (S07–S10) were planned at index level only when this file was written; paths marked `(verify)` are the ones most likely to move.

## Story index

| ID | Title | Depends on | Effort |
|---|---|---|---|
| E08-X01 | Refine E08 against codebase | E07-R01 | LOW |
| E08-S01 | ART_DIRECTOR constitution and design/art routing | E08-X01, E05-S06 | MEDIUM |
| E08-S02 | `AssetProvider` implementation: Meshy | E08-X01, E02-S01 | HIGH |
| E08-S03 | `AssetProvider` implementation: OpenArt | E08-S02 | MEDIUM |
| E08-S04 | `asset.generate` kernel tool, idempotency, `EXTERNAL_CREDITS` cost | E08-S02, E01-S26 | MEDIUM |
| E08-S05 | `AssetProvenance` files and evidence | E08-S04 | MEDIUM |
| E08-S06 | Asset validation via `UnityProvider.validate_assets` and `com.walk.ci` | E08-S04, E03-S10 | MEDIUM |
| E08-S07 | Art Director review flow and ART/DESIGN done dimensions | E08-S01, E08-S06, E03-S17 | MEDIUM |
| E08-S08 | Unity MCP provider (`ToolKind.MCP`) | E08-X01, E01-S14 | HIGH |
| E08-S09 | Epic gate: asset generation → validation → approval (e2e) | E08-S05, E08-S07 | MEDIUM |
| E08-R01 | Review E08 | E08-S09 | MEDIUM |

Title note: WBS §4 names E08-S06 "Asset validation via `UnityProvider.validate_assets` and `com.walk.ci`"; the WBS §5 row omits "and `com.walk.ci`". Same story; E08-X01 aligns the §5 title.

## Reading order for implementers

1. `WBS.md` §2–§3 (binding conventions; §3.1 `Default*` naming, §3.2 integrations model placement, §3.5 ledger write points, §3.6 fakes and `tests/e2e/`).
2. ADR-0006 D-2 (side effects — including "Unity builds and asset generation" — are executed by the kernel), D-3/D-4 (decisions, approvals); ADR-0009 D-6 (Unity batchmode first, MCP deferred to Stage 8), D-8 (`MESHY_API_KEY`, `OPENART_API_KEY`), D-11 (provider plugins), D-13 (asset review automation deferred to Stage 8); ADR-0013 (constitution schema; D-7 remaining roles added in Stage 8); ADR-0003 D-4/D-5 (approved artifacts; `.ai/` written only via `MemoryManager.write`).
3. `INTERFACES.md` §1.3 (`set_done_dimension`, `check_definition_of_ready`), §1.8 (`approve_artifact`, `verify_approved_artifacts`), §1.12 (`IntegrationManager.assets`, `with_idempotency`), §1.13 (`ToolInvoker`), §1.14 (`EvidenceManager.record`), §2.4 (`UnityProvider.validate_assets`, `JobResult(job_kind="asset_validation")`), §2.5 (`AssetRequest`, `AssetJob`, `AssetProvenance`, `AssetProvider`), §3.1/§3.2 (feature/story tables), §4 (routing table).
4. `DOMAIN-MODEL.md` §3 (`AgentRole.DESIGN_LEADER/ART_DIRECTOR`, `DoneDimension`, `ApprovedArtifactKind`, `ToolKind.MCP`, `BudgetDimension.EXTERNAL_CREDITS`, `CostCategory.ASSETS`, `EvidenceKind.SCREENSHOT/LOG/PROJECT_DATA`, `DecisionCategory.ART`), §4.1 (`StoryContract`, `Feature.applicable_dimensions/done_dimensions`), §4.4 (`CostRecord`), §4.6 (`ToolSpec`), §4.7 (`ApprovedArtifact`), §4.12 (`Evidence`, `EvidenceDraft`), §4.13 (`EnvironmentManifest.providers`).
5. `ARCHITECTURE.md` §2.2 (import table: `integrations` may import `telemetry`, `workflow`, `budgets`, `tools`, never `memory`/`runtime`), §2.3 (SDK confinement: Meshy/OpenArt only under `walk/integrations/assets/<provider>/`; `httpx` and PyYAML also allowed in `walk/integrations/assets/`; Unity MCP process/client only under `walk/integrations/unity_mcp/`), §4.2 (KERNEL tools incl. `asset.*` enforced in `ToolInvoker.invoke`), §4.4 (idempotency key `asset.generate:{work_item_id}:{request_hash}`), §8 (`.ai/` layout).
6. `requirements/WAL_K_REQ.md` §6.5, §10.4, §10.5, §33, §78, §79, §80, §84.

Parallel sets (WBS §8): `{S01} ∥ {S02→S03} ∥ {S08}`; `{S05} ∥ {S06}` after S04; S07 after S01 and S06; S09 last. Accepted exceptions to Files-table disjointness (wiring or one-line config edits only; parallel branches rebase before merge, E08-X01 confirms): `src/walk/cli/composition.py` (S02, S03, S04, S05, S06, S07, S08), `src/walk/integrations/service.py` (S02, S08), `pyproject.toml` (S02, S05, S06).

## Planning decisions fixed for this epic

Autonomy Level 0 for the planner unless marked `NEW NAME:` (WBS §3):

- **Who generates.** An asset is the deliverable of a TASK whose `StoryContract.asset_request` is set (an "asset task"). Asset tasks are created by the ART_DIRECTOR's DESIGN run as `new_tasks` (§78: the Art Director defines requirements); generation is a **kernel step** (`AssetPipelineStep`, ADR-0006 D-2), not an agent run, so the Art Director reviews output it did not produce (`reviewer_role_differs` holds with implementer `KERNEL`). Agents whose policy allows the `asset.generate` tool may also call it directly through `ToolInvoker.invoke`; both paths share `DefaultAssetGenerator` and the same idempotency keys.
- **Pipeline order.** generate → poll → download into `<worktree>/Assets/Generated/<work_item_id>/<job_id>/` → post-processors (S05 provenance, S06 validation) → kernel commit → `submit`. A failing post-processor verdict triggers regeneration up to `MAX_ASSET_ATTEMPTS` (2), then the task is `BLOCKED` with the violations as reason.
- **Approval.** On ART_DIRECTOR `APPROVED` the kernel calls `MemoryManager.approve_artifact(kind=ASSET)` with actor ART_DIRECTOR (`may_approve: [ASSET]`). `ART_DIRECTION` artifacts are never approvable by an agent — a change is an L3 escalation to USER and lands through `walk artifacts approve --supersedes` (§33 change workflow, E02-S12 write guard).
- **Provenance "approved by".** The `<asset>.provenance.yaml` written at generation has `approved_by: null`; the authoritative approval is the `ApprovedArtifact` whose payload includes that file. `walk assets show` answers the four §80 questions by joining both (E08-S05), so S07 never rewrites provenance files and does not need S05 code.
- **Dimensions.** `ART_COMPLETE` becomes applicable to a feature once it has an asset task, and is set by the kernel when every asset task under it is `COMPLETE` with an `APPROVED` `ASSET` artifact; `DESIGN_VALIDATED` is applicable when DESIGN_LEADER is enabled and is set by an `APPROVED` DESIGN_LEADER review at feature `QC` (§6.5).
- **No new enum members.** Existing `LedgerEventKind`s cover everything (`TOOL_INVOKED`, `COST_RECORDED`, `EVIDENCE_RECORDED`, `ARTIFACT_APPROVED`, `WORK_ITEM_TRANSITION`); no new `HookName`.

## `NEW NAME:` items introduced by this epic (to be added to WBS.md §6 by E08-X01)

| Item | Story | Why |
|---|---|---|
| `src/walk/agents/defaults/art_director.md`; `policies.yaml` ART_DIRECTOR entry (`enabled: false`) | S01 | ADR-0013 D-7 adds remaining roles in Stage 8; no file named |
| KERNEL tools `art.approve`, `art.reject` (`tools.yaml`, `permissions/defaults.yaml`) | S01 | `review.approve` is LEAD_DEV-only (ADR-0006 D-2 example); the Art Director needs its own review authority |
| builtin skill `art-direction-review` | S01 | WBS §3.10 lists no art skill |
| routing rows: FEATURE `DESIGN` → ART_DIRECTOR (before LEAD_DEV, when enabled and art applicable); asset TASK `READY`/`REWORK` → kernel step `asset_pipeline`; FEATURE `QC` → DESIGN_LEADER (REVIEW, when `DESIGN_VALIDATED` pending) | S01, S04, S07 | INTERFACES §4 has no art/design rows |
| `walk.integrations.assets` package: `request_hash`, `download_to`, `raise_for_asset_status`; `MeshyAssetProvider`, `MESHY_BASE_URL`, `MESHY_STATUS_MAP`; `OpenArtAssetProvider`, `OPENART_BASE_URL`, `OPENART_STATUS_MAP`; `AssetJobFailed` | S02, S03 | ARCHITECTURE §2.3 names the folder, not the classes |
| `detect_asset_providers` (`walk.integrations.preflight`); `KernelOverrides.asset_providers`; `KernelSettings.asset_credits_per_job`, `KernelSettings.asset_usd_per_credit` | S02, S04 | §26 provider readiness; §84 credits → USD rate |
| `tests/fakes/fake_asset_provider.py::FakeAssetProvider` | S02 | WBS §3.6 fake list has no asset fake |
| `StoryContract.asset_request: JsonDict \| None` | S04 | `workflow` may not import `integrations.models.AssetRequest`; validated into `AssetRequest` by the kernel |
| `walk.integrations.assets.pipeline`: `AssetProcessingContext`, `AssetProcessingVerdict`, `AssetPostProcessor` | S04 | Extension point so S05 and S06 stay file-disjoint |
| `walk.runtime.asset_tools`: `ASSET_GENERATE_TOOL`, `DefaultAssetGenerator`, `AssetGenerateToolHandler`, `ASSET_OUTPUT_ROOT`, `ASSET_POLL_INTERVAL_S`, `ASSET_POLL_TIMEOUT_S`; `walk.runtime.models.AssetGenerationResult` | S04 | Handler for the `asset.generate` KERNEL tool (ARCHITECTURE §4.2) |
| idempotency key `asset.job:{work_item_id}:{request_hash}` (submitted job id, stored before the final `asset.generate:` key) | S04 | Prevents double credit spend when the kernel dies between submit and download (ARCHITECTURE §4.4 table addition) |
| `walk.orchestrator.asset_step`: `AssetPipelineStep`, `MAX_ASSET_ATTEMPTS` | S04 | Non-agent kernel step (precedent: E03-S12 integration step) |
| `walk.integrations.assets.provenance`: `PROVENANCE_SUFFIX`, `provenance_path_for`, `write_provenance`, `read_provenance`, `ProvenanceRecorder`; `walk.orchestrator.asset_provenance`: `AssetProvenanceQuery`, `AssetProvenanceAnswer`; `walk assets show/list` (`walk.cli.cmd_assets.assets_app`) | S05 | §80 questions need a file format and a query entry point |
| `RELOCATE:` PyYAML allowed in `walk/integrations/assets/` (provenance files, asset rules) | S05, S06 | ARCHITECTURE §2.3 yaml row did not list `integrations` — applied to ARCHITECTURE §2.3 by the architect 2026-10-06 |
| `walk.integrations.assets.rules`: `AssetRuleSet`, `AssetKindRules`, `AssetRuleViolation`, `load_asset_rules`, `evaluate_asset_metrics`, `ASSET_RULES_DEFAULT_PATH`; kernel defaults `asset_rules.yaml`; project override `.ai/project/asset-rules.yaml`; `AssetValidationProcessor`; `walk.integrations.unity.asset_metrics`: `AssetMetrics`, `parse_asset_validation_result`; C# `WalK.CI.ValidateAssets` arguments `-walkAssets`, `-walkResult`, `-walkPreviewDir` | S06 | §79 rules as data; ADR-0009 D-6 names the method only |
| `DefaultWorkflowManager.update_contract`, `DefaultWorkflowManager.set_applicable_dimensions`; `walk.orchestrator.art_dimensions`: `ArtDimensionTracker`, `applicable_dimensions_for`; `BuiltinHookDeps.art_dimensions`; `ASSET_TASK_REQUIRED_EVIDENCE` | S07 | §6.5 applicability is decided at runtime; INTERFACES §1.3 only has `set_done_dimension` |
| `ART_LABEL` (`"art"`), `ART_BRIEF_DONE_LABEL` (`"art-brief-done"`) feature labels | S01 | Keep `TaskRouter.route` a pure function of the work item |
| `RELOCATE:` `httpx` allowed in `walk/integrations/assets/` (shared download helper); `MAX_DOWNLOAD_BYTES`, `MESHY_LICENSE_NOTE`, `OPENART_LICENSE_NOTE`, `OPENART_GENERATE_PATH`, `OPENART_JOB_PATH` | S02, S03 | ARCHITECTURE §2.3 listed httpx only for Jira — applied to ARCHITECTURE §2.3 by the architect 2026-10-06 |
| commit key variant `git.commit:{work_item_id}:asset:{request_hash}` | S04 | Kernel-step commit has no run id (ARCHITECTURE §4.4 key is per run) |
| `SECRET_LIKE` pattern in `walk.integrations.assets.provenance` | S05 | `integrations` may not import `walk.memory.secrets` |
| `TextureMetrics`; C# `WalK.AssetMetricsCollector`; `FakeUnityProvider.asset_metrics`, `FakeUnityProvider.validate_calls` | S06 | Metrics schema and fake scripting |
| `REVIEW_TOOLS_BY_ROLE`, `DESIGN_REVIEW_HOLD_LABEL`, `art_dimensions_on_transition`; asset-request keys `constraints.base_prompt`, `constraints.revision_notes` | S07 | Review authority per reviewer role; revision loop data |
| `MCP_PROTOCOL_VERSION`; manifest key `tools["unity_mcp"]`; ARCHITECTURE §2.3 row "Unity MCP server process → `walk/integrations/unity_mcp/`" | S08 | MCP handshake and confinement — §2.3 row applied to ARCHITECTURE §2.3 by the architect 2026-10-06 |
| ADR-0015 (Unity MCP provider and MCP client; written as `Proposed` 2026-10-06); `walk.integrations.unity_mcp`: `McpTransport`, `StdioMcpTransport`, `McpClient`, `McpToolResult`, `UnityMcpProvider`, `UNITY_MCP_TOOLS`; `McpProtocolError`; `walk.runtime.mcp_tools.McpToolHandler`; MCP tools `unity_mcp.screenshot`, `unity_mcp.console`, `unity_mcp.inspect_asset` (`tools_mcp.yaml`); `permissions/defaults_unity_mcp.yaml`; `KernelSettings.unity_mcp_command`, `KernelSettings.unity_mcp_tool_map`; `detect_unity_mcp`; `tests/fakes/fake_mcp_transport.py::FakeMcpTransport` | S08 | ADR-0009 D-6 defers MCP to Stage 8 without a design |

---

### E08-X01 — Refine E08 against codebase

**Status:** TODO
**Type:** docs
**Requirements:** §78, §79, §80, §33, §135, §5 (non-goals: refine rejects stories that drift into out-of-scope work)
**Depends on:** E07-R01
**Effort:** LOW   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
Every E08 story's Files table, interface references and dependencies are re-validated against the `src/walk/` tree and `INTERFACES.md` as they exist after E07-R01, the open questions marked `BLOCKING` are resolved with the architect, and the corrected epic file is committed before any E08 story starts (WBS §1 `X` task, §2 rule 3).

#### Scope
- In: this file (E08-S01…S09, R01), WBS §5 rows for E08 (including the S06 title alignment), WBS §6 register additions from the `NEW NAME:` table above, resolution record for the `BLOCKING` notes in E08-S03 and E08-S08.
- Out: renaming, renumbering, adding or dropping stories (WBS §1: IDs are fixed); any source change; architecture-doc edits (the architect applies the `NEW NAME:`/`RELOCATE:` register; this task only records the outcome).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-08-art-design.md` | modify | — |
| `docs/02-work-breakdown/WBS.md` | modify | — (§5 status rows and S06 title for E08, §6 register rows) |

#### Interface contract
No code. Procedure:
1. For every row of every Files table in this file: `create` paths must not exist; `modify` paths must exist (or be created by an earlier story in this file); every symbol listed against a `modify` row must already be defined in that file (grep) or be new in this story.
2. For every `INTERFACES.md §x.y` / `DOMAIN-MODEL.md §x.y` / `ARCHITECTURE.md §x.y` / ADR reference: the section exists and still defines the referenced names (`AssetProvider`, `AssetRequest`, `AssetJob`, `AssetProvenance`, `UnityProvider.validate_assets`, `ToolKind.MCP`, `ApprovedArtifactKind.ASSET`, `DoneDimension.ART_COMPLETE`, `BudgetDimension.EXTERNAL_CREDITS`, `CostCategory.ASSETS`).
3. Every `Depends on` ID is `DONE` in WBS §5 (E07-R01, E05-S06, E02-S01, E01-S26, E03-S10, E03-S17, E01-S14) or belongs to this epic.
4. Every `(verify)` marker is resolved (kept or path corrected) and removed. Known hotspots: `src/walk/orchestrator/router.py` and its routing data (E01-S29, E03-S07), the E03-S12 integration-step module and its worktree helper (reused by `AssetPipelineStep`), `src/walk/runtime/output_applier.py` (E01-S27, E03-S08), `src/walk/runtime/models.py` (E01-S25), `src/walk/workflow/tables/story_workflow.yaml` allowed roles for `start`/`submit` (E01-S09), `src/walk/orchestrator/builtin_hooks.py` (`BuiltinHookDeps`, E02-S08 → E07-S09; moved from `orchestrator/builtin_hooks.py` by ADR-0016), `src/walk/agents/defaults/design_leader.md` and `RuntimePolicy.enabled` (E05-S06), `src/walk/integrations/unity/provider.py` and `unity/com.walk.ci/Editor/WalkCI.cs` (E03-S10), `tests/fakes/fake_unity_provider.py` (E03-S10), `tests/e2e/conftest.py` fixture `e07_scenario` (E07-S10).
5. ADR number: ADR-0015 (E08-S08) must be the next free number under `docs/01-architecture/adr/`; renumber in E08-S08 and the `NEW NAME:` table if E05–E07 added ADRs.
6. `BLOCKING` items: (a) E08-S03 OpenArt API contract (endpoint, auth header, job/status shape) confirmed by the owner with a reference URL, or S03 re-scoped by the owner; (b) E08-S08 ADR-0015 (exists as `Proposed` with the architect's recommendations, 2026-10-06) accepted by the owner after its acceptance checklist (server version pinned, `tools/list` bindings confirmed). Each outcome is recorded in the story's Notes and the `BLOCKING` marker removed, or the story is set `BLOCKED`.
7. Shared-file exceptions (header "Parallel sets"): confirm that the edits to `src/walk/cli/composition.py`, `src/walk/integrations/service.py` and `pyproject.toml` are wiring/one-line config only, or sequence the stories (S08 after S02; S06 after S05) instead of running them in parallel.
8. Dependency note: S07 deliberately does not use S05 code (see header "Provenance approved by"); if refinement finds S07 needs S05, add `E08-S05` to S07's `Depends on` here (a dependency correction, not a new story).

#### Behavior
1. Corrections are made in place; no story text is removed, only paths, symbol names, references, dependencies and `Notes` are corrected.
2. New public names discovered during refinement are added to the `NEW NAME:` table above and to WBS §6.
3. Where a dependency is not `DONE`, the story is set `BLOCKED` with the reason (IMPLEMENTATION-PROTOCOL §1.2) instead of being rewritten.
4. The refine commit contains only the two documentation files.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given every Files table path in this file When checked against `src/walk/`, `tests/`, `unity/` and `docs/` Then each `modify` path exists and each `create` path does not exist or is created by an earlier E08 story | manual checklist recorded in Evidence |
| 2 | Given every `INTERFACES.md`/`DOMAIN-MODEL.md`/`ARCHITECTURE.md`/ADR reference in this file When opened Then the section exists and defines the named symbols | manual checklist recorded in Evidence |
| 3 | Given WBS §5 When E08 dependencies are read Then every dependency outside E08 is `DONE` or the dependent story is marked `BLOCKED` with a reason | manual checklist recorded in Evidence |
| 4 | Given the `BLOCKING` notes in E08-S03 and E08-S08 When refinement ends Then each is resolved (decision recorded) or the story is `BLOCKED` | manual checklist recorded in Evidence |
| 5 | Given the corrected file When `py -3 scripts/validate_wbs.py` runs Then no error mentions an `E08-` ID | manual checklist recorded in Evidence |

#### Evidence required
- Checklist per story (ID → paths checked → corrections made).
- Resolution record for the two `BLOCKING` items.
- `scripts/validate_wbs.py` output.
- Demo: `walk --version` and `walk doctor` on a scratch repo still succeed (no source change expected).

#### Notes
- WBS §2 rule 3; IMPLEMENTATION-PROTOCOL §1.2 (Definition of Ready).
- E08 and E09 run in parallel; if E09-X01 renumbers migrations or touches `walk.telemetry`, re-check that no E08 story lists those files.
- Commit subject: `docs: refine epic 08 stories (E08-X01)`.

#### Evidence (filled by implementer)
_pending_

---

### E08-S01 — ART_DIRECTOR constitution and design/art routing

**Status:** TODO
**Type:** feat
**Requirements:** §10.4, §10.5, §12, §33, §78, §6.7, §31, §127, §137 (Inv. 7, 10)
**Depends on:** E08-X01, E05-S06
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The ART_DIRECTOR role exists as a kernel-default constitution and runtime policy (optional, disabled by default), has its own review authority (`art.approve`/`art.reject`, `may_approve: [ASSET]`) but cannot approve or silently change `ART_DIRECTION`, and a feature labelled `art` is routed in `DESIGN` to the Art Director (art brief, asset task drafts) before the Lead Developer's technical design, alongside the existing DESIGN_LEADER discovery routing.

#### Scope
- In: `art_director.md` constitution (ADR-0013 D-2/D-3 schema), ART_DIRECTOR entry in kernel `policies.yaml` (`enabled: false`), builtin skill `art-direction-review`, KERNEL tools `art.approve`/`art.reject`, ART_DIRECTOR permission defaults, router rule for FEATURE `DESIGN`, `OutputApplier` rule that an ART_DIRECTOR DESIGN output adds label `art-brief-done` and raises no workflow event, escalation rule for art-direction changes (L3, USER), INTERFACES §4 rows.
- Out: `StoryContract.asset_request` and the asset kernel step (E08-S04); asset-task normalisation, Art Director REVIEW handling, `approve_artifact(kind=ASSET)` and dimensions (E08-S07); DESIGN_LEADER constitution content (E05-S06, unchanged here); Unity MCP tools for the role (E08-S08).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/agents/defaults/art_director.md` | create | — (constitution `id: ART_DIRECTOR`, `version: "1.0"`) |
| `src/walk/agents/defaults/policies.yaml` | modify | — (`ART_DIRECTOR` entry: `enabled: false`, `allowed_tools`, `default_skills`, `execution_strategy: review_only`) |
| `src/walk/skills/builtin/art-direction-review/SKILL.md` | create | — (skill `art-direction-review` v1.0, `scope: KERNEL`) |
| `src/walk/tools/builtin/tools.yaml` | modify | — (rows `art.approve`, `art.reject`: kind KERNEL, provider `kernel`) |
| `src/walk/permissions/defaults.yaml` | modify | — (ART_DIRECTOR rows, see Behavior 4) |
| `src/walk/orchestrator/router.py` | modify `(verify: created by E01-S29, extended by E03-S07)` | `DefaultTaskRouter.route` (FEATURE `DESIGN` art rule), `ART_LABEL`, `ART_BRIEF_DONE_LABEL` |
| `src/walk/runtime/output_applier.py` | modify `(verify: E01-S27/E03-S08)` | `DefaultOutputApplier.apply` (ART_DIRECTOR DESIGN branch) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§4 routing row FEATURE `DESIGN` → ART_DIRECTOR) |
| `tests/agents/test_defaults_art_director.py` | create | — |
| `tests/skills/test_builtin_skills.py` | modify | — |
| `tests/tools/test_builtin_tools.py` | modify | — |
| `tests/permissions/test_defaults_art_director.py` | create | — |
| `tests/orchestrator/test_router_art.py` | create | — |
| `tests/runtime/test_output_applier_art_design.py` | create | — |

#### Interface contract
Constitution schema: ADR-0013 D-2 front matter, D-3 body sections; model DOMAIN-MODEL §4.2 `Constitution`. Front matter of `art_director.md` (structured fields are binding; prose may be reworded):
```yaml
id: ART_DIRECTOR
type: constitution
title: Art Director
version: "1.0"
role: ART_DIRECTOR
identity: Art Director
mission: Protect visual coherence and presentation quality.          # §10.5
responsibilities: [visual language, silhouette, readability, animation, VFX, UI visual quality, consistency, generated asset quality]
authority:
  decision_scope: [ART]
  max_autonomy_level: 1
  may_approve: [ASSET, art.approve]
  may_reject: [art.reject]
  may_create_work: [TASK]
professional_bias: Visual coherence over feature speed; a technically valid asset may still be rejected.
core_beliefs: ["Functional does not mean finished.", "Every asset follows the approved art direction."]
decision_principles: ["Judge against the approved ART_DIRECTION artifact, not taste.", "Reject with actionable revision notes."]
risk_tolerance: LOW
preferred_evidence: [SCREENSHOT, GAMEPLAY_RECORDING, PLAYTEST]
conflict_behavior: Challenge implementation that breaks visual language; concede to approved art direction.
escalation_rules:
  - {condition: "art direction change", to_level: 3, category: ART}
  - {condition: "asset budget exceeds phase credits", to_level: 2, category: PRODUCT}
tool_permissions:
  - {tool: art.approve, effect: ALLOW}
  - {tool: art.reject, effect: ALLOW}
  - {tool: asset.generate, effect: ALLOW}
forbidden_actions: ["approve or edit an ART_DIRECTION artifact", "approve an asset without screenshot evidence", "write files in the repository"]
```
`policies.yaml` ART_DIRECTOR entry:
```yaml
ART_DIRECTOR:
  version: "1.0"
  enabled: false                       # RuntimePolicy.enabled (E05 NEW NAME); projects enable it in .ai/agents/policies.yaml
  model_policy: {preferred: [claude/opus], fallback: [codex/default], required_capabilities: [VISUAL_REASONING, DESIGN_REASONING]}
  default_skills: [walk-output-contract, art-direction-review]
  allowed_tools: [read, glob, grep, asset.generate, art.approve, art.reject]
  execution_strategy: review_only
```
Router rule (pure, INTERFACES §1.1 `TaskRouter.route`):
```python
ART_LABEL = "art"                      # feature needs art (set by planner or `walk feature add --label art`)
ART_BRIEF_DONE_LABEL = "art-brief-done"
# FEATURE in DESIGN:
#   ART_DIRECTOR enabled and ART_LABEL in item.labels and ART_BRIEF_DONE_LABEL not in item.labels
#       -> RouteDecision(role=ART_DIRECTOR, purpose="DESIGN")
#   otherwise -> existing row (LEAD_DEV, DESIGN)
```

#### Behavior
1. `ConstitutionLoader` loads `art_director.md` without error; the provider-name lint (E05-S07, ADR-0013 D-5) passes; body contains every D-3 section in order plus `## Working Guidance` describing the art brief: one asset task draft per asset with `contract.asset_request` (`kind`, `prompt`, `reference_artifact_ids` = approved `ART_DIRECTION`/`REFERENCE_MATERIAL` ids from context, `constraints` with triangle/texture budgets and style tags, §79) and `reviewer_role: ART_DIRECTOR`.
2. With kernel defaults only, `AgentManager.list_roles()` does not return ART_DIRECTOR; with a project `policies.yaml` setting `ART_DIRECTOR.enabled: true` it does.
3. `art.approve` and `art.reject` are KERNEL tools (`provider: kernel`, no `requires_env`); neither is a protected action.
4. Permission defaults: ART_DIRECTOR — ALLOW `read`, `glob`, `grep`, `asset.generate`, `art.approve`, `art.reject`; DENY `write`, `edit`, `bash`, `review.approve`, `qc.approve`, `git.*`, `jira.*` (ADR-0006 role table row "PRODUCT_OWNER / DESIGN_LEADER / ART_DIRECTOR"). Every other role: DENY `art.approve`, `art.reject` (default deny already covers it; an explicit test asserts LEAD_DEV is denied).
5. `approve_artifact(kind=ART_DIRECTION, actor=ART_DIRECTOR)` raises `ApprovalNotAuthorized` (E02-S12 authority check against `may_approve`); `approve_artifact(kind=ASSET, actor=ART_DIRECTOR)` passes the authority check.
6. An ART_DIRECTOR `DecisionProposal(category=ART)` whose topic matches "art direction change" is classified at autonomy level 3 by the constitution's escalation rule and routed to USER approval (E05-S01/S02 machinery; no new code — the test asserts the classification only).
7. Router: FEATURE `DESIGN` routes to ART_DIRECTOR only when ART_DIRECTOR is enabled, the feature has label `art` and lacks `art-brief-done`; otherwise to LEAD_DEV exactly as before. FEATURE `DISCOVERY` routing (DESIGN_LEADER if enabled else ORCHESTRATOR) is unchanged and asserted by a regression test.
8. `OutputApplier`: for a run with `role == ART_DIRECTOR` and `purpose == "DESIGN"` and status `COMPLETED`, effects are applied in the normal order (context updates, evidence, decisions, `new_tasks`), then label `art-brief-done` is added to the feature through `WorkflowManager` (labels update, ledger `WORK_ITEM_TRANSITION` is **not** written because the state does not change) and **no** workflow event is raised (the Lead Developer's DESIGN run still raises `design_approved`). Any other status follows the existing mapping.
9. `skills/builtin/art-direction-review/SKILL.md` lists the §10.5 review dimensions and the §79 validation fields as a checklist and states that a reject must contain actionable revision notes in `findings`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given kernel defaults When `ConstitutionLoader` loads ART_DIRECTOR Then `authority.may_approve == ["ASSET", "art.approve"]`, `decision_scope == [ART]` and all ADR-0013 D-3 sections are present in order | `tests/agents/test_defaults_art_director.py::test_art_director_constitution_loads_with_schema` |
| 2 | Given kernel defaults only When `list_roles()` Then ART_DIRECTOR absent; Given project policy `enabled: true` Then present | `tests/agents/test_defaults_art_director.py::test_art_director_disabled_by_default` |
| 3 | Given the ART_DIRECTOR policy When loaded Then `allowed_tools` and `default_skills` equal the contract lists | `tests/agents/test_defaults_art_director.py::test_art_director_policy_tools_and_skills` |
| 4 | Given the builtin skills When loaded Then `art-direction-review` v1.0 scope KERNEL exists | `tests/skills/test_builtin_skills.py::test_art_direction_review_skill_present` |
| 5 | Given `tools.yaml` When loaded Then `art.approve` and `art.reject` are KERNEL tools without `protected_action` | `tests/tools/test_builtin_tools.py::test_art_review_tools_registered` |
| 6 | Given default permissions When ART_DIRECTOR requests `art.approve` / `edit` Then ALLOW / DENY | `tests/permissions/test_defaults_art_director.py::test_art_director_allow_and_deny_rows` |
| 7 | Given default permissions When LEAD_DEV requests `art.approve` Then DENY | `tests/permissions/test_defaults_art_director.py::test_other_roles_cannot_art_approve` |
| 8 | Given ART_DIRECTOR actor When `approve_artifact(kind=ART_DIRECTION)` Then `ApprovalNotAuthorized`; `kind=ASSET` passes the authority check | `tests/agents/test_defaults_art_director.py::test_art_director_cannot_approve_art_direction` |
| 9 | Given an ART proposal "art direction change" from ART_DIRECTOR When classified Then autonomy level 3 | `tests/agents/test_defaults_art_director.py::test_art_direction_change_escalates_to_user` |
| 10 | Given FEATURE in DESIGN with label `art`, ART_DIRECTOR enabled When `route` Then ART_DIRECTOR/DESIGN | `tests/orchestrator/test_router_art.py::test_design_routes_to_art_director_first` |
| 11 | Given the same feature with `art-brief-done` When `route` Then LEAD_DEV/DESIGN | `tests/orchestrator/test_router_art.py::test_design_routes_to_lead_dev_after_brief` |
| 12 | Given ART_DIRECTOR disabled or no `art` label When `route` Then LEAD_DEV/DESIGN; DISCOVERY still routes to DESIGN_LEADER when enabled | `tests/orchestrator/test_router_art.py::test_routing_unchanged_without_art` |
| 13 | Given an ART_DIRECTOR DESIGN output with two `new_tasks` When applied Then two TASKs created, feature gains `art-brief-done`, no workflow event raised, feature state still DESIGN | `tests/runtime/test_output_applier_art_design.py::test_art_design_output_labels_without_event` |

#### Evidence required
- Quality gate output (ruff ok, mypy ok, N passed, coverage %).
- Demo: with `.ai/agents/policies.yaml` enabling ART_DIRECTOR on a scratch repo, `walk doctor` lists ART_DIRECTOR among roles and the constitution lint passes; `walk skills list` shows `art-direction-review`.

#### Notes
- ADR-0013 D-7 (remaining roles in Stage 8), D-4 (project overrides may only narrow); ADR-0006 D-2 role table; §10.5 "Technically valid asset MAY still be rejected by Art Director".
- `may_approve` mixes artifact kinds and review tool names by design (DOMAIN-MODEL §4.8 `Authority.may_approve` description).
- Labels are used so the router stays a pure function of the work item (INTERFACES §1.1); no ledger query from the router.
- `NEW NAME:` `art_director.md`, ART_DIRECTOR policy entry, `art.approve`, `art.reject`, skill `art-direction-review`, `ART_LABEL`, `ART_BRIEF_DONE_LABEL`, routing row FEATURE `DESIGN` → ART_DIRECTOR.
- Commit subject: `feat: add art director role and design routing (E08-S01)`.

#### Evidence (filled by implementer)
_pending_

---

### E08-S02 — `AssetProvider` implementation: Meshy

**Status:** TODO
**Type:** feat
**Requirements:** §78, §80, §84, §26, §91, §137 (Inv. 1, 11)
**Depends on:** E08-X01, E02-S01
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A `MeshyAssetProvider` implements the INTERFACES §2.5 `AssetProvider` protocol for 3D models (Meshy text-to-3D) behind an injectable `httpx.AsyncClient`, reads `MESHY_API_KEY` only through `CredentialStore`, reports readiness in the environment manifest, and ships with shared asset helpers and a protocol-conformant `FakeAssetProvider` that every later E08 test uses.

#### Scope
- In: `walk.integrations.assets` package skeleton and shared helpers (`request_hash`, `download_to`, `raise_for_asset_status`); `MeshyAssetProvider` (`health`, `generate`, `poll`, `download`, `provenance`) for `kind="model3d"`; HTTP error → kernel error mapping; `AssetJobFailed`; `detect_asset_providers` and `IntegrationManager.assets` wiring; `FakeAssetProvider`; recorded-fixture unit tests and one `@pytest.mark.integration` live test.
- Out: OpenArt (E08-S03); the `asset.generate` tool, idempotency keys, cost records and download location policy (E08-S04); provenance files (E08-S05); validation (E08-S06); Meshy texture/rigging/animation endpoints (not in Stage 8 scope — `NotSupported`).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/integrations/assets/__init__.py` | create | re-exports `request_hash`, `download_to`, `raise_for_asset_status`, `MAX_DOWNLOAD_BYTES`, `MeshyAssetProvider` |
| `src/walk/integrations/assets/common.py` | create | `request_hash`, `download_to`, `raise_for_asset_status`, `MAX_DOWNLOAD_BYTES` |
| `src/walk/integrations/assets/meshy/__init__.py` | create | `MeshyAssetProvider` |
| `src/walk/integrations/assets/meshy/provider.py` | create | `MeshyAssetProvider`, `MESHY_BASE_URL`, `MESHY_STATUS_MAP`, `MESHY_LICENSE_NOTE` |
| `src/walk/integrations/errors.py` | modify | `AssetJobFailed` |
| `src/walk/integrations/preflight.py` | modify | `detect_asset_providers` |
| `src/walk/integrations/service.py` | modify | `DefaultIntegrationManager.__init__` (`assets` parameter), `DefaultIntegrationManager.preflight` (asset providers) |
| `src/walk/integrations/__init__.py` | modify | re-exports `AssetJobFailed`, `detect_asset_providers` |
| `src/walk/cli/composition.py` | modify | `KernelOverrides.asset_providers`, `KernelSettings.asset_credits_per_job` |
| `pyproject.toml` | modify | — (import-linter / ruff `banned-api`: `httpx` also allowed under `walk.integrations.assets`) |
| `tests/fakes/fake_asset_provider.py` | create | `FakeAssetProvider` |
| `tests/integrations/assets/__init__.py` | create | — |
| `tests/integrations/assets/test_common.py` | create | — |
| `tests/integrations/assets/test_fake_asset_provider.py` | create | — |
| `tests/integrations/assets/meshy/__init__.py` | create | — |
| `tests/integrations/assets/meshy/fixtures/create_task.json`, `task_pending.json`, `task_succeeded.json`, `task_failed.json`, `balance.json` | create | — |
| `tests/integrations/assets/meshy/test_provider.py` | create | — |
| `tests/integrations/assets/meshy/test_meshy_live.py` | create | — (`@pytest.mark.integration`) |
| `tests/integrations/test_preflight_assets.py` | create | — |

#### Interface contract
Protocol and models: INTERFACES §2.5 (`AssetRequest`, `AssetJob`, `AssetProvenance`, `AssetProvider`), defined in `walk.integrations.models`/`protocols` by E01-S23. Deltas:
```python
# src/walk/integrations/assets/common.py
MAX_DOWNLOAD_BYTES: Final = 200 * 1024 * 1024
def request_hash(request: AssetRequest) -> str:
    """First 16 hex chars of sha256 over canonical JSON {kind, prompt, sorted reference_artifact_ids, constraints (sorted keys), work_item_id}."""
async def download_to(client: httpx.AsyncClient, files: Mapping[str, str], target_dir: Path) -> list[str]:
    """files = {file_name: url}; streams each to <target_dir>/<file_name>.tmp then os.replace; returns POSIX paths in input order.
    file_name containing '/', '\\' or '..' -> BoundaryViolation; body > MAX_DOWNLOAD_BYTES -> OutputInvalid (partial file removed)."""
def raise_for_asset_status(response: httpx.Response, provider: str) -> None:
    """2xx -> None; 401/403 -> ConfigError; 402 -> QuotaExhausted; 429 -> RateLimited; 404 -> AssetJobFailed; 5xx -> ProviderUnavailable."""

# src/walk/integrations/errors.py
class AssetJobFailed(PermanentError): ...          # provider reported FAILED/CANCELED/EXPIRED, or job unknown

# src/walk/integrations/assets/meshy/provider.py
MESHY_BASE_URL: Final = "https://api.meshy.ai"
MESHY_STATUS_MAP: Final[dict[str, Literal["QUEUED", "RUNNING", "DONE", "FAILED"]]] = {
    "PENDING": "QUEUED", "IN_PROGRESS": "RUNNING", "SUCCEEDED": "DONE", "FAILED": "FAILED", "CANCELED": "FAILED", "EXPIRED": "FAILED"}
MESHY_LICENSE_NOTE: Final = "Generated with Meshy API; subject to Meshy terms of service"
class MeshyAssetProvider:                          # implements AssetProvider; provider = "meshy"
    def __init__(self, credentials: CredentialStore, *, client: httpx.AsyncClient | None = None,
                 base_url: str = MESHY_BASE_URL, credits_per_job: Mapping[str, float] | None = None) -> None: ...

# src/walk/integrations/preflight.py
async def detect_asset_providers(providers: Mapping[str, AssetProvider]) -> dict[str, ComponentStatus]: ...

# tests/fakes/fake_asset_provider.py
class FakeAssetProvider:                           # implements AssetProvider
    def __init__(self, provider: str = "fake-assets", *, polls_until_done: int = 1, credits: float | None = 10.0,
                 files: tuple[str, ...] = ("model.fbx", "thumbnail.png"), fail_job_numbers: tuple[int, ...] = (),
                 supported_kinds: tuple[str, ...] = ("model3d", "texture", "image")) -> None: ...
    generate_calls: list[tuple[AssetRequest, str]]  # (request, idempotency_key)
    poll_calls: int
    download_calls: int
```
HTTP contract used by `MeshyAssetProvider` (all requests carry `Authorization: Bearer <MESHY_API_KEY>` and `Idempotency-Key: <idempotency_key>` on create):

| Method | Path | Used by | Response fields read |
|---|---|---|---|
| GET | `/openapi/v1/balance` | `health` | `balance` |
| POST | `/openapi/v2/text-to-3d` body `{mode: "preview", prompt, art_style, negative_prompt?, target_polycount?}` | `generate` | `result` (task id) |
| GET | `/openapi/v2/text-to-3d/{id}` | `poll`, `download` | `status`, `progress`, `model_urls.fbx`, `model_urls.glb`, `thumbnail_url`, `task_error.message` |

`KernelSettings.asset_credits_per_job: dict[str, dict[str, float]]` (provider → kind → credits; default `{}`); `KernelOverrides.asset_providers: dict[str, AssetProvider] | None` replaces every real provider (tests, e2e).

#### Behavior
1. `generate(request, idempotency_key)`: `request.kind != "model3d"` → `NotSupported("meshy: <kind>")` before any HTTP call. Body: `prompt` (≤ 600 chars, longer → `OutputInvalid`), `art_style = constraints.get("style", "realistic")`, `negative_prompt = constraints.get("negative_prompt")` when present, `target_polycount = constraints.get("triangle_budget")` when present. Returns `AssetJob(provider="meshy", job_id=<result>, state="QUEUED", cost_credits=credits_per_job.get("model3d"))`.
2. `poll(job_id)`: maps `status` through `MESHY_STATUS_MAP`; unknown status → `OutputInvalid`; keeps `cost_credits` from `credits_per_job` (Meshy responses carry no credit figure — Notes).
3. `download(job_id, target_dir)`: re-reads the task; state ≠ `DONE` → `AssetJobFailed(task_error.message or status)`; downloads `model.fbx` (`model_urls.fbx`, falling back to `model.glb` from `model_urls.glb` when fbx is absent) and `thumbnail.png` (`thumbnail_url`, when present) via `download_to`; returns paths with the model first.
4. `provenance(job, request, paths, actor)` → `AssetProvenance(asset_path=paths[0], provider="meshy", prompt=request.prompt, reference_concept=request.reference_artifact_ids[0] if any else None, generated_by=actor, approved_by=None, version=1, related_feature_id=None, license_or_source=MESHY_LICENSE_NOTE, job_id=job.job_id)`; pure, no I/O (S05 fills `version`/`related_feature_id`).
5. `health()`: credential absent → `ComponentStatus(state=MISSING, detail="MESHY_API_KEY not set")` without HTTP; balance 200 → `READY` with `detail="balance=<n>"`; 401/403 → `MISCONFIGURED`; transport error/timeout → `UNKNOWN` (never raises).
6. Every HTTP response passes `raise_for_asset_status`; `httpx.TimeoutException` → `Timeout`, `httpx.TransportError` → `ProviderUnavailable` (both `TransientError`, retried by callers, not here).
7. The API key is read per request from `CredentialStore.get("MESHY_API_KEY")`; it never appears in exceptions, logs, `AssetJob` or `AssetProvenance` (test asserts on `caplog` and `repr`).
8. `detect_asset_providers` awaits `health()` of each provider concurrently and returns `{name: status}`; `DefaultIntegrationManager.preflight` stores them under `EnvironmentManifest.providers[<name>]`, so `ToolRegistry.available` sees `meshy` as a ready key when `READY` (E01-S14 `requires_env: meshy|openart`).
9. Composition constructs `MeshyAssetProvider` unconditionally (health reports `MISSING` without a key) and registers it as `IntegrationManager.assets["meshy"]`; `KernelOverrides.asset_providers`, when given, replaces the whole dict.
10. `FakeAssetProvider` is deterministic: job ids `fake-job-0001`, …; `poll` returns `RUNNING` until called `polls_until_done` times for that job, then `DONE` (or `FAILED` when the job number is in `fail_job_numbers`); `download` writes files whose bytes are `b"<provider>:<job_id>:<file>"`; unsupported kind → `NotSupported`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given two equal requests with constraint keys in different order When `request_hash` Then equal; a changed prompt Then different | `tests/integrations/assets/test_common.py::test_request_hash_canonical_and_sensitive` |
| 2 | Given a file name `../x.fbx` When `download_to` Then `BoundaryViolation` and nothing written | `tests/integrations/assets/test_common.py::test_download_rejects_path_traversal` |
| 3 | Given a body larger than the cap When `download_to` Then `OutputInvalid` and no partial file remains | `tests/integrations/assets/test_common.py::test_download_enforces_size_cap` |
| 4 | Given responses 401, 402, 429, 503 When `raise_for_asset_status` Then `ConfigError`, `QuotaExhausted`, `RateLimited`, `ProviderUnavailable` | `tests/integrations/assets/test_common.py::test_status_mapping_to_kernel_errors` |
| 5 | Given a mock transport returning `create_task.json` When `generate(model3d request)` Then POST body has `mode=preview`, `target_polycount` from `triangle_budget`, header `Idempotency-Key`, and job state `QUEUED` | `tests/integrations/assets/meshy/test_provider.py::test_generate_posts_text_to_3d` |
| 6 | Given `kind="audio"` When `generate` Then `NotSupported` and no HTTP request made | `tests/integrations/assets/meshy/test_provider.py::test_generate_unsupported_kind` |
| 7 | Given pending then succeeded fixtures When `poll` twice Then `QUEUED` then `DONE` | `tests/integrations/assets/meshy/test_provider.py::test_poll_maps_status` |
| 8 | Given a succeeded task When `download` Then `model.fbx` and `thumbnail.png` written, model path first | `tests/integrations/assets/meshy/test_provider.py::test_download_writes_model_and_thumbnail` |
| 9 | Given a failed task When `download` Then `AssetJobFailed` carrying `task_error.message` | `tests/integrations/assets/meshy/test_provider.py::test_download_failed_task_raises` |
| 10 | Given no credential / 200 balance / 401 When `health` Then `MISSING` (no HTTP) / `READY` / `MISCONFIGURED` | `tests/integrations/assets/meshy/test_provider.py::test_health_states` |
| 11 | Given a key `sk-secret` When any call fails Then the key appears in no exception text, log record or model repr | `tests/integrations/assets/meshy/test_provider.py::test_api_key_never_leaks` |
| 12 | Given a job and request When `provenance` Then fields match Behavior 4 | `tests/integrations/assets/meshy/test_provider.py::test_provenance_fields` |
| 13 | Given `FakeAssetProvider(polls_until_done=2)` When generate/poll/poll/download Then `RUNNING`, `DONE`, deterministic bytes, call counters 1/2/1 | `tests/integrations/assets/test_fake_asset_provider.py::test_fake_provider_lifecycle` |
| 14 | Given providers meshy (READY) and openart (MISSING) When preflight Then manifest `providers` holds both states and `meshy` is a ready env key | `tests/integrations/test_preflight_assets.py::test_preflight_records_asset_providers` |
| 15 | Given `MESHY_API_KEY` in the environment When the live test runs Then `health()` is `READY` | `tests/integrations/assets/meshy/test_meshy_live.py::test_meshy_live_health` |

#### Evidence required
- Quality gate output (ruff ok, mypy ok, N passed, coverage %); live test listed as skipped.
- Demo: `walk doctor` on a scratch repo without `MESHY_API_KEY` → `meshy: missing (MESHY_API_KEY not set)`; with a key (owner machine) → `meshy: ready (balance=…)`. Optional owner-run transcript of `uv run pytest -m integration tests/integrations/assets/meshy`.

#### Notes
- ADR-0009 D-8 (credential names), D-11 (provider plugins — composition wires directly in Stage 8; entry-point packaging is not required by any gate); ARCHITECTURE §2.3 (Meshy only under `walk/integrations/assets/meshy/`).
- Endpoint paths and field names in the HTTP table follow Meshy's public API documentation (v2 text-to-3D, v1 balance). The implementer confirms them against the current docs, records the doc URL and date here, and on mismatch changes only the constants/field names (no contract change). Fixtures are hand-written from that documentation, never captured from a real account.
- Meshy responses do not report credits per task, so `cost_credits` comes from `KernelSettings.asset_credits_per_job` (empty → `None`, which S04 records as quantity 0 with a WARNING).
- The live test never calls `generate` (it spends credits); a manual generate run is an owner decision.
- `RELOCATE:` `httpx` allowed under `walk/integrations/assets/` for the shared download helper (applied to ARCHITECTURE §2.3 by the architect 2026-10-06).
- `NEW NAME:` `request_hash`, `download_to`, `raise_for_asset_status`, `MAX_DOWNLOAD_BYTES`, `MeshyAssetProvider`, `MESHY_BASE_URL`, `MESHY_STATUS_MAP`, `MESHY_LICENSE_NOTE`, `AssetJobFailed`, `detect_asset_providers`, `KernelOverrides.asset_providers`, `KernelSettings.asset_credits_per_job`, `FakeAssetProvider`.
- Commit subject: `feat: add meshy asset provider and asset fakes (E08-S02)`.

#### Evidence (filled by implementer)
_pending_

---

### E08-S03 — `AssetProvider` implementation: OpenArt

**Status:** BLOCKED — OpenArt public API contract unconfirmed (owner must supply an API reference URL; see Notes)
**Type:** feat
**Requirements:** §78, §80, §84, §26, §91
**Depends on:** E08-S02
**Effort:** MEDIUM   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
An `OpenArtAssetProvider` implements the `AssetProvider` protocol for 2D images and textures (concept art, UI art, tileable textures) with the same shape, error mapping and credential handling as the Meshy adapter, so the kernel has two interchangeable asset providers (§78).

#### Scope
- In: `OpenArtAssetProvider` (`health`, `generate`, `poll`, `download`, `provenance`) for `kind in {"image", "texture"}`; endpoint/field constants isolated in one module; composition registration as `IntegrationManager.assets["openart"]`; recorded-fixture unit tests; one `@pytest.mark.integration` live test.
- Out: shared helpers and fakes (E08-S02, reused unchanged); provider selection policy and cost records (E08-S04); 3D, animation and audio kinds (`NotSupported`); Blender (§78 lists it; no Stage 8 gate needs it — not planned in E08).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/integrations/assets/openart/__init__.py` | create | `OpenArtAssetProvider` |
| `src/walk/integrations/assets/openart/provider.py` | create | `OpenArtAssetProvider`, `OPENART_BASE_URL`, `OPENART_STATUS_MAP`, `OPENART_LICENSE_NOTE`, `OPENART_GENERATE_PATH`, `OPENART_JOB_PATH` |
| `src/walk/integrations/assets/__init__.py` | modify | re-export `OpenArtAssetProvider` |
| `src/walk/cli/composition.py` | modify | — (registers `assets["openart"]`) |
| `tests/integrations/assets/openart/__init__.py` | create | — |
| `tests/integrations/assets/openart/fixtures/create_job.json`, `job_running.json`, `job_succeeded.json`, `job_failed.json` | create | — |
| `tests/integrations/assets/openart/test_provider.py` | create | — |
| `tests/integrations/assets/openart/test_openart_live.py` | create | — (`@pytest.mark.integration`) |
| `tests/integrations/assets/test_provider_conformance.py` | create | — |

#### Interface contract
Protocol: INTERFACES §2.5 `AssetProvider`; helpers and errors from E08-S02 (`request_hash`, `download_to`, `raise_for_asset_status`, `AssetJobFailed`).
```python
# src/walk/integrations/assets/openart/provider.py
OPENART_BASE_URL: Final[str]              # confirmed by E08-X01 (BLOCKING note)
OPENART_GENERATE_PATH: Final[str]         # POST, returns a job id
OPENART_JOB_PATH: Final[str]              # GET, "{job_id}" placeholder, returns status + image URLs
OPENART_STATUS_MAP: Final[dict[str, Literal["QUEUED", "RUNNING", "DONE", "FAILED"]]]
OPENART_LICENSE_NOTE: Final = "Generated with OpenArt API; subject to OpenArt terms of service"
class OpenArtAssetProvider:               # implements AssetProvider; provider = "openart"
    def __init__(self, credentials: CredentialStore, *, client: httpx.AsyncClient | None = None,
                 base_url: str = OPENART_BASE_URL, credits_per_job: Mapping[str, float] | None = None) -> None: ...
```
Request mapping (fields named by the confirmed API; semantic contract fixed here):

| `AssetRequest` | OpenArt request field | Rule |
|---|---|---|
| `prompt` | prompt | required, ≤ 1000 chars else `OutputInvalid` |
| `constraints["negative_prompt"]` | negative prompt | optional |
| `constraints["texture_size"]` | width = height | default 1024; `kind="texture"` additionally requests a tileable/seamless output when the API supports it, else adds "seamless tileable texture" to the prompt |
| `constraints["aspect"]` | width/height | `image` only, e.g. `"16:9"`; ignored for `texture` |
| `constraints["style"]` | style/model preset | optional; unknown preset passed through |

Auth: credential `OPENART_API_KEY` (ADR-0009 D-8) via `CredentialStore`, sent in the header the confirmed API requires.

#### Behavior
1. `generate`: kind not in `{"image", "texture"}` → `NotSupported("openart: <kind>")` before any HTTP call; otherwise POST and return `AssetJob(provider="openart", job_id, state="QUEUED", cost_credits=credits_per_job.get(kind) or the credit figure from the response when the API returns one)`.
2. `poll`: status mapped through `OPENART_STATUS_MAP`; unknown status → `OutputInvalid`.
3. `download`: state ≠ `DONE` → `AssetJobFailed`; downloads the first image as `image.png` (`texture.png` for `kind="texture"` — the kind is read from the job response or, if absent, from a per-job record kept only for the provider's lifetime) via `download_to`; returns `[path]`.
4. `provenance`: as E08-S02 Behavior 4 with `provider="openart"` and `OPENART_LICENSE_NOTE`.
5. `health`: credential absent → `MISSING` without HTTP; if the confirmed API has an authenticated read endpoint it is used (200 → `READY`, 401/403 → `MISCONFIGURED`), otherwise `READY` with `detail="credential present (unverified)"`; transport errors → `UNKNOWN`.
6. Error mapping and key secrecy identical to E08-S02 Behaviors 6–7.
7. Conformance: both real providers and `FakeAssetProvider` satisfy `isinstance(x, AssetProvider)` (runtime-checkable protocol) and the same scripted lifecycle (generate → poll until DONE → download → provenance) against mock transports.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given an `image` request with `aspect="16:9"` When `generate` Then the POST body carries prompt and 16:9 dimensions and the job is `QUEUED` | `tests/integrations/assets/openart/test_provider.py::test_generate_image_request_mapping` |
| 2 | Given a `texture` request with `texture_size=512` When `generate` Then 512×512 and a seamless/tileable request (flag or prompt suffix) | `tests/integrations/assets/openart/test_provider.py::test_generate_texture_is_square_and_tileable` |
| 3 | Given `kind="model3d"` When `generate` Then `NotSupported` and no HTTP request | `tests/integrations/assets/openart/test_provider.py::test_generate_unsupported_kind` |
| 4 | Given running then succeeded fixtures When `poll` twice Then `RUNNING` then `DONE` | `tests/integrations/assets/openart/test_provider.py::test_poll_maps_status` |
| 5 | Given a succeeded texture job When `download` Then a single `texture.png` path | `tests/integrations/assets/openart/test_provider.py::test_download_texture_file` |
| 6 | Given a failed job When `download` Then `AssetJobFailed` | `tests/integrations/assets/openart/test_provider.py::test_download_failed_job_raises` |
| 7 | Given no credential When `health` Then `MISSING` with no HTTP call | `tests/integrations/assets/openart/test_provider.py::test_health_missing_credential` |
| 8 | Given a key `oa-secret` and a 500 response When `generate` Then `ProviderUnavailable` and the key appears in no exception text or log record | `tests/integrations/assets/openart/test_provider.py::test_errors_mapped_and_key_never_leaks` |
| 9 | Given Meshy, OpenArt and the fake When the scripted lifecycle runs on mock transports Then each is an `AssetProvider` and returns provenance with its own provider name | `tests/integrations/assets/test_provider_conformance.py::test_all_providers_conform` |
| 10 | Given `OPENART_API_KEY` in the environment When the live test runs Then `health()` is not `MISSING` | `tests/integrations/assets/openart/test_openart_live.py::test_openart_live_health` |

#### Evidence required
- Quality gate output; live test listed as skipped.
- Demo: `walk doctor` on a scratch repo → `openart: missing (OPENART_API_KEY not set)`; owner-run `uv run pytest -m integration tests/integrations/assets/openart` transcript when a key is available.

#### Notes
- **BLOCKED** pending owner confirmation of an OpenArt API reference URL (architect, 2026-10-06). The public generation API contract — base URL, generate and job-status endpoints, auth header, status values, image URL field, credit reporting — is unknown and must not be invented: the endpoint constants in Interface contract stay unset and the request-mapping table names semantic fields only. Unblock condition: the owner records the reference URL and the confirmed contract in this Notes section (E08-X01), then sets `TODO`. If OpenArt offers no public generation API, the owner either names an OpenArt-compatible HTTP contract or sets the story `DROPPED` in WBS §5 (IDs are never reused).
- Nothing depends on this story: no `Depends on` in E08–E11 names E08-S03, the E08 gate (E08-S09) uses `FakeAssetProvider`, and E08-S04…S09 use only the `AssetProvider` protocol and E08-S02. Its absence only removes `assets["openart"]` from composition.
- All uncertainty is confined to the six constants and the field names in `provider.py`; tests read the same constants, so a later API change touches one module.
- `NEW NAME:` `OpenArtAssetProvider`, `OPENART_BASE_URL`, `OPENART_STATUS_MAP`, `OPENART_LICENSE_NOTE`, `OPENART_GENERATE_PATH`, `OPENART_JOB_PATH`.
- Commit subject: `feat: add openart asset provider (E08-S03)`.

#### Evidence (filled by implementer)
_pending_

---

### E08-S04 — `asset.generate` kernel tool, idempotency, `EXTERNAL_CREDITS` cost

**Status:** TODO
**Type:** feat
**Requirements:** §78, §84, §85, §90, §30, §31, §20, §6.5, §137 (Inv. 7, 9)
**Depends on:** E08-S02, E01-S26
**Effort:** MEDIUM   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Assets are produced only by the kernel: one `DefaultAssetGenerator` (generate → poll → download → post-processors) is exposed as the `asset.generate` KERNEL tool handler and driven by `AssetPipelineStep` for asset tasks; it never spends provider credits twice for the same request (two-stage idempotency keys), refuses to start when the `EXTERNAL_CREDITS` budget has no headroom, and records every job as an `ASSETS` cost line metered in `EXTERNAL_CREDITS` and USD.

#### Scope
- In: `StoryContract.asset_request`; post-processor extension point (`walk.integrations.assets.pipeline`); `DefaultAssetGenerator`; `AssetGenerateToolHandler` registered on `DefaultToolInvoker`; `AssetPipelineStep` (READY/REWORK → IMPLEMENTING → READY_FOR_REVIEW, regeneration up to `MAX_ASSET_ATTEMPTS`, BLOCKED on exhaustion); scheduler dispatch of asset tasks to the step; `tools.yaml` cost attribution for `asset.generate`; `KernelSettings.asset_usd_per_credit`; INTERFACES §4 / DOMAIN-MODEL §4.1 doc rows.
- Out: provenance files and their evidence (E08-S05, a post-processor); validation and screenshots (E08-S06, a post-processor); asset-task normalisation at creation, review and approval (E08-S07); OpenArt (E08-S03 — the generator is provider-agnostic); report roll-ups (E09-S03).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/workflow/models.py` | modify | `StoryContract.asset_request` |
| `src/walk/workflow/tables/story_workflow.yaml` | modify `(verify: KERNEL already allowed on start/submit/block?)` | — (`KERNEL` in `allowed_roles` of `start`, `submit`, `block`) |
| `src/walk/integrations/assets/pipeline.py` | create | `AssetProcessingContext`, `AssetProcessingVerdict`, `AssetPostProcessor` |
| `src/walk/integrations/assets/__init__.py` | modify | re-exports pipeline symbols |
| `src/walk/runtime/models.py` | modify `(verify: created by E01-S25)` | `AssetGenerationResult` |
| `src/walk/runtime/asset_tools.py` | create | `ASSET_GENERATE_TOOL`, `ASSET_OUTPUT_ROOT`, `ASSET_POLL_INTERVAL_S`, `ASSET_POLL_TIMEOUT_S`, `DefaultAssetGenerator`, `AssetGenerateToolHandler` |
| `src/walk/runtime/__init__.py` | modify | re-exports |
| `src/walk/orchestrator/asset_step.py` | create | `AssetPipelineStep`, `MAX_ASSET_ATTEMPTS` |
| `src/walk/orchestrator/scheduler.py` | modify `(verify: E01-S29/E07-S01)` | `Scheduler.tick` (dispatch asset tasks to `AssetPipelineStep`) |
| `src/walk/tools/builtin/tools.yaml` | modify | — (`asset.generate`: `cost_category: ASSETS`, `cost_dimension: EXTERNAL_CREDITS`) |
| `src/walk/cli/composition.py` | modify | `KernelSettings.asset_usd_per_credit` (wires generator, handler, step) |
| `docs/01-architecture/DOMAIN-MODEL.md` | modify | — (§4.1 `StoryContract.asset_request`) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§4 row: TASK with `asset_request`, READY/REWORK → kernel step) |
| `tests/workflow/test_contract_asset_request.py` | create | — |
| `tests/integrations/assets/test_pipeline_models.py` | create | — |
| `tests/runtime/test_asset_generator.py` | create | — |
| `tests/runtime/test_asset_tool_handler.py` | create | — |
| `tests/orchestrator/test_asset_step.py` | create | — |
| `tests/orchestrator/test_scheduler_asset_dispatch.py` | create | — |
| `tests/tools/test_builtin_tools.py` | modify | — |

#### Interface contract
```python
# src/walk/workflow/models.py
class StoryContract(WalkModel):
    ...
    asset_request: JsonDict | None = Field(default=None, description="AssetRequest fields minus work_item_id (§78); set only on asset tasks")

# src/walk/integrations/assets/pipeline.py
class AssetProcessingContext(FrozenModel):
    request: AssetRequest
    job: AssetJob
    paths: list[str]                    # repo-relative POSIX paths inside worktree_path
    worktree_path: str
    feature_id: FeatureId | None
    phase_id: PhaseId | None
    actor: Actor
    attempt: int

class AssetProcessingVerdict(FrozenModel):
    processor: str
    ok: bool
    reasons: list[str] = []
    evidence_ids: list[EvidenceId] = []
    evidence_kinds: list[EvidenceKind] = []
    extra_paths: list[str] = []         # files the processor wrote that must be committed with the asset

@runtime_checkable
class AssetPostProcessor(Protocol):
    name: str
    async def process(self, ctx: AssetProcessingContext) -> AssetProcessingVerdict: ...

# src/walk/runtime/models.py
class AssetGenerationResult(FrozenModel):
    ok: bool
    provider: str
    job_id: str
    request_hash: str
    paths: list[str]
    cost_credits: float | None
    attempt: int
    verdicts: list[AssetProcessingVerdict]
    reused: bool                        # True when served from the idempotency store

# src/walk/runtime/asset_tools.py
ASSET_GENERATE_TOOL: Final = "asset.generate"
ASSET_OUTPUT_ROOT: Final = "Assets/Generated"
ASSET_POLL_INTERVAL_S: Final = 5.0
ASSET_POLL_TIMEOUT_S: Final = 900.0
class DefaultAssetGenerator:
    def __init__(self, integrations: IntegrationManager, costs: CostManager, budgets: BudgetManager, *,
                 sleep: Callable[[float], Awaitable[None]], post_processors: Sequence[AssetPostProcessor] = (),
                 usd_per_credit: Mapping[str, float], project_key: ProjectKey,
                 poll_interval_s: float = ASSET_POLL_INTERVAL_S, poll_timeout_s: float = ASSET_POLL_TIMEOUT_S) -> None: ...
    def add_post_processor(self, processor: AssetPostProcessor) -> None: ...      # duplicate name -> ConfigError
    async def generate(self, request: AssetRequest, *, actor: Actor, worktree_path: str, feature_id: FeatureId | None,
                       phase_id: PhaseId | None, provider: str | None = None, attempt: int = 1) -> AssetGenerationResult: ...
class AssetGenerateToolHandler:          # a KernelToolHandler (E01-S26)
    def __init__(self, generator: DefaultAssetGenerator, runs: AgentRunRepository, workflow: WorkflowManager) -> None: ...
    async def __call__(self, request: ToolCallRequest) -> JsonDict: ...
    # arguments: {kind, prompt, reference_artifact_ids?, constraints?, provider?}; returns AssetGenerationResult.model_dump(mode="json")

# src/walk/orchestrator/asset_step.py
MAX_ASSET_ATTEMPTS: Final = 2
class AssetPipelineStep:
    def __init__(self, workflow: WorkflowManager, generator: DefaultAssetGenerator, git: GitProvider, clock: Clock, *,
                 worktrees: "<E03-S12 worktree helper> (verify)", max_attempts: int = MAX_ASSET_ATTEMPTS) -> None: ...
    def handles(self, item: WorkItem) -> bool: ...          # TASK with contract.asset_request and state in {READY, REWORK}
    async def run(self, task: Task) -> WorkItemTransition: ...
```
Idempotency keys (ARCHITECTURE §4.4; second one `NEW NAME:`):

| Key | Stored value | Written |
|---|---|---|
| `asset.job:{work_item_id}:{request_hash}` | provider job id | right after `AssetProvider.generate` returns |
| `asset.generate:{work_item_id}:{request_hash}` | `AssetGenerationResult` JSON | after post-processors, same transaction as the cost record |
| `git.commit:{work_item_id}:asset:{request_hash}` | commit sha | `AssetPipelineStep` commit (`NEW NAME:` variant of the §4.4 commit key; no run exists) |

#### Behavior
1. `generate`: `h = request_hash(request)`. If `asset.generate:{wi}:{h}` exists → return the stored result with `reused=True`; no provider call, no cost, no post-processor.
2. Budget: `headroom(BudgetSubject(project_key, phase_id, role=actor.role, work_item_id=request.work_item_id, run_id=actor.run_id))[EXTERNAL_CREDITS] <= 0` → `BudgetExhausted` before any provider call (a missing dimension means unlimited).
3. Provider choice: explicit `provider` argument, else `request.constraints.get("provider")`, else each provider in `IntegrationManager.assets` insertion order, skipping those raising `NotSupported`; none left → `NotSupported("no asset provider for <kind>")`. An unknown explicit provider → `ConfigError`.
4. Job submission goes through `with_idempotency("asset.job:…", …)`: a stored job id is reused (kernel restarted after submit), so `AssetProvider.generate` is called at most once per `(work item, request hash)`.
5. Polling: `poll(job_id)` every `poll_interval_s` via the injected `sleep`; `FAILED` → `AssetJobFailed`; elapsed > `poll_timeout_s` → `Timeout` (job key kept, so a later call resumes polling).
6. Download target: `<worktree_path>/Assets/Generated/<work_item_id>/<job_id>/`; returned paths are repo-relative POSIX.
7. Cost: one `CostRecord(category=ASSETS, provider, dimension=EXTERNAL_CREDITS, quantity=cost_credits or 0, unit="credits", cost_usd=quantity * usd_per_credit.get(provider, 0.0), run_id=actor.run_id, work_item_id, phase_id, role=actor.role)` via `CostManager.record` (ledger `COST_RECORDED`), then `BudgetManager.meter(subject, EXTERNAL_CREDITS, quantity)`; `cost_credits is None` → quantity 0 and one WARNING log. A soft/hard verdict after the job does not undo it (the credits are spent).
8. Post-processors run in registration order on an `AssetProcessingContext`; `ok = all(v.ok)`; a processor exception is converted to a failing verdict (`reasons=[<type>: <message>]`) and logged — never propagated.
9. `AssetGenerateToolHandler` (agent path, behind `ToolInvoker.invoke` which already authorised and metered `TOOL_CALLS`): resolves the run → `work_item_id`, feature (walking `parent_id` to the FEATURE) and phase; builds `AssetRequest` from arguments (`OutputInvalid` on validation error); `actor = Actor(role=run.role, model_id=run.model_id, run_id=run.id)`; `worktree_path = request.worktree_path`.
10. `AssetPipelineStep.run(task)` (kernel path, actor `KERNEL`): (a) build `AssetRequest` from `contract.asset_request` + `work_item_id`; invalid → raise `block` with reason `invalid asset_request: …` and return; (b) raise `start` with payload `budget_ok`, `branch_available` computed as for agent runs; (c) obtain the task-branch worktree through the E03-S12 helper; (d) for `attempt` in `1..max_attempts`: `constraints["attempt"] = attempt`, `constraints["revision"] =` number of prior `REWORK` entries of the task; `generate(...)`; stop at the first `ok`; (e) all attempts failed → `block` with reason `asset rejected by post-processors: <reasons of last attempt>`; (f) success → commit `paths + extra_paths` on the task branch (`wip`-free message `asset(<task id>): <kind> <job_id>`, key `git.commit:{wi}:asset:{h}`) and raise `submit` with payload `has_commit=True`, `evidence_kinds_present` = union of verdict `evidence_kinds`, `implementer_role=KERNEL`, `implementer_model_id=None`.
11. `TransientError` from the generator inside the step → `block` with reason `asset provider unavailable: <error>` (`resume_state` IMPLEMENTING per ADR-0010 D-5); `PermanentError` → `block` with the error text. The step never leaves the task in `IMPLEMENTING` without a recorded reason.
12. Scheduler: on each tick, items for which `AssetPipelineStep.handles(item)` is true are dispatched to the step as a tracked asyncio task (at most one per work item, not counted against `max_parallel_agents`) instead of `TaskRouter.route`; `READY_FOR_REVIEW` asset tasks route normally (reviewer from `contract.reviewer_role`).
13. `asset.generate` in `tools.yaml` declares `cost_category: ASSETS`, `cost_dimension: EXTERNAL_CREDITS`; `requires_env: meshy|openart` is unchanged.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a `StoryContract` with `asset_request` When round-tripped through `model_dump`/`model_validate` Then equal; default is `None` | `tests/workflow/test_contract_asset_request.py::test_asset_request_field_roundtrip` |
| 2 | Given `AssetPostProcessor` When a class with `name` and `process` is checked Then `isinstance` is True; verdict defaults are empty lists | `tests/integrations/assets/test_pipeline_models.py::test_post_processor_protocol_and_verdict_defaults` |
| 3 | Given `FakeAssetProvider(polls_until_done=2)` When `generate` Then files under `Assets/Generated/<wi>/<job>/`, two sleeps, `ok=True`, `reused=False` | `tests/runtime/test_asset_generator.py::test_generate_polls_downloads_and_returns_paths` |
| 4 | Given a completed generation When `generate` is called again with the same request Then `reused=True`, provider `generate_calls` still 1, one cost record | `tests/runtime/test_asset_generator.py::test_generate_idempotent_on_request_hash` |
| 5 | Given the job key stored but no result key (crash after submit) When `generate` Then no new provider `generate` call and polling resumes on the stored job id | `tests/runtime/test_asset_generator.py::test_generate_resumes_submitted_job` |
| 6 | Given `credits=10` and `usd_per_credit={"fake-assets": 0.02}` When `generate` Then one `CostRecord(category=ASSETS, dimension=EXTERNAL_CREDITS, quantity=10, cost_usd=0.2)` and `EXTERNAL_CREDITS` metered by 10 | `tests/runtime/test_asset_generator.py::test_generate_records_assets_cost_and_meters_credits` |
| 7 | Given `EXTERNAL_CREDITS` headroom 0 When `generate` Then `BudgetExhausted` and no provider call | `tests/runtime/test_asset_generator.py::test_generate_refuses_without_credit_headroom` |
| 8 | Given a job that ends `FAILED` / never finishes When `generate` Then `AssetJobFailed` / `Timeout` | `tests/runtime/test_asset_generator.py::test_generate_failed_and_timeout` |
| 9 | Given providers `[unsupported, fake]` and no explicit provider When `generate` Then the second is used; an unknown explicit provider Then `ConfigError` | `tests/runtime/test_asset_generator.py::test_provider_selection_order` |
| 10 | Given one processor returning `ok=False` and one raising When `generate` Then result `ok=False` with two failing verdicts and no exception | `tests/runtime/test_asset_generator.py::test_post_processor_failures_become_verdicts` |
| 11 | Given an ART_DIRECTOR run on TASK-0003 When the handler is called with tool arguments Then `AssetRequest.work_item_id == TASK-0003`, actor carries run id/model, result JSON returned | `tests/runtime/test_asset_tool_handler.py::test_handler_builds_request_from_run` |
| 12 | Given invalid arguments (missing prompt) When the handler is called Then `OutputInvalid` | `tests/runtime/test_asset_tool_handler.py::test_handler_rejects_invalid_arguments` |
| 13 | Given an asset task READY and a passing generator When `AssetPipelineStep.run` Then transitions READY→IMPLEMENTING→READY_FOR_REVIEW by KERNEL, one commit containing the asset files, submit payload `has_commit=True` | `tests/orchestrator/test_asset_step.py::test_step_generates_commits_and_submits` |
| 14 | Given a processor failing on attempt 1 and passing on attempt 2 When `run` Then two provider jobs (different request hashes) and READY_FOR_REVIEW | `tests/orchestrator/test_asset_step.py::test_step_regenerates_until_ok` |
| 15 | Given a processor failing on every attempt When `run` Then BLOCKED with reason containing the last reasons; no commit | `tests/orchestrator/test_asset_step.py::test_step_blocks_after_max_attempts` |
| 16 | Given an invalid `asset_request` / a `ProviderUnavailable` When `run` Then BLOCKED with `invalid asset_request` / `asset provider unavailable` | `tests/orchestrator/test_asset_step.py::test_step_blocks_on_invalid_request_or_transient_error` |
| 17 | Given a ready asset task and a ready normal story When `Scheduler.tick` Then the asset task goes to the step, the story to an agent run, and the step does not consume a parallel-agent slot | `tests/orchestrator/test_scheduler_asset_dispatch.py::test_tick_dispatches_asset_tasks_to_step` |
| 18 | Given `tools.yaml` When loaded Then `asset.generate` has `cost_category=ASSETS`, `cost_dimension=EXTERNAL_CREDITS` | `tests/tools/test_builtin_tools.py::test_asset_generate_cost_attribution` |

#### Evidence required
- Quality gate output (ruff ok, mypy ok, N passed, coverage %).
- Demo: `walk work show TASK-0003` after a fake-provider step run (fixture repo) showing `READY_FOR_REVIEW`; `walk cost --work-item TASK-0003` showing an `ASSETS` line in credits and USD; `walk ledger query --work-item TASK-0003` listing `COST_RECORDED` and the two transitions.

#### Notes
- ADR-0006 D-2 (kernel executes asset generation); ARCHITECTURE §4.2 (`asset.*` enforced in `ToolInvoker.invoke`), §4.4 (keys); E01-S26 (`KernelToolHandler`, `register_handler`); E03-S12 integration step is the precedent for a non-agent step and its worktree helper (`(verify)` the helper's name at E08-X01).
- Agent-path downloads land in the agent's worktree and become part of its diff: `BoundaryAuditor` allowed paths for roles allowed `asset.generate` must include `Assets/Generated/**` (`(verify)` where E01-S25/E02-S14 define allowed paths; adjust there by data, not code, at E08-X01).
- `constraints["attempt"]` and `constraints["revision"]` are part of the request hash on purpose: a regeneration is a new request, a replay is not.
- Risk HIGH: real money (credits). Mitigations are AC 4, 5, 7.
- `NEW NAME:` `StoryContract.asset_request`, `AssetProcessingContext`, `AssetProcessingVerdict`, `AssetPostProcessor`, `AssetGenerationResult`, `ASSET_GENERATE_TOOL`, `ASSET_OUTPUT_ROOT`, `ASSET_POLL_INTERVAL_S`, `ASSET_POLL_TIMEOUT_S`, `DefaultAssetGenerator`, `AssetGenerateToolHandler`, `AssetPipelineStep`, `MAX_ASSET_ATTEMPTS`, `KernelSettings.asset_usd_per_credit`, keys `asset.job:{work_item_id}:{request_hash}` and `git.commit:{work_item_id}:asset:{request_hash}`, INTERFACES §4 kernel-step row.
- Commit subject: `feat: add asset.generate kernel tool and asset pipeline step (E08-S04)`.

#### Evidence (filled by implementer)
_pending_

---

### E08-S05 — `AssetProvenance` files and evidence

**Status:** TODO
**Type:** feat
**Requirements:** §80, §6.6, §33, §82, §88, §137 (Inv. 9)
**Depends on:** E08-S04
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every generated asset carries a `<asset>.provenance.yaml` (INTERFACES §2.5 `AssetProvenance`) committed next to it and recorded as evidence, and `walk assets show <path>` answers the four §80 questions — where it came from, which concept it followed, who approved it, which prompt/provider generated it — by joining the provenance file with the approved-artifact registry and evidence records.

#### Scope
- In: provenance file format and atomic writer/reader; `ProvenanceRecorder` post-processor (registered on `DefaultAssetGenerator`); `PROJECT_DATA` evidence per provenance file; `AssetProvenanceQuery` (read-only); `walk assets show|list`; INTERFACES §6 CLI rows.
- Out: validation evidence and screenshots (E08-S06); writing `approved_by` (never — approval lives in `ApprovedArtifact`, header decision "Provenance approved by"); ledger-wide provenance chains for decisions (E09-S05, parallel epic — no shared files).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/integrations/assets/provenance.py` | create | `PROVENANCE_SUFFIX`, `provenance_path_for`, `write_provenance`, `read_provenance`, `ProvenanceRecorder` |
| `src/walk/integrations/assets/__init__.py` | modify | re-exports provenance symbols |
| `src/walk/orchestrator/asset_provenance.py` | create | `AssetProvenanceAnswer`, `AssetProvenanceQuery` |
| `src/walk/orchestrator/__init__.py` | modify | re-exports |
| `src/walk/cli/cmd_assets.py` | create | `assets_app` (`show`, `list`) |
| `src/walk/cli/app.py` | modify | — (registers `assets_app`) |
| `src/walk/cli/composition.py` | modify | — (`generator.add_post_processor(ProvenanceRecorder(...))`) |
| `pyproject.toml` | modify | — (import-linter / ruff `banned-api`: `yaml` allowed under `walk.integrations.assets`) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§6 `walk assets show/list` rows) |
| `tests/integrations/assets/test_provenance.py` | create | — |
| `tests/integrations/assets/test_provenance_recorder.py` | create | — |
| `tests/orchestrator/test_asset_provenance.py` | create | — |
| `tests/cli/test_cmd_assets.py` | create | — |

#### Interface contract
```python
# src/walk/integrations/assets/provenance.py
PROVENANCE_SUFFIX: Final = ".provenance.yaml"
def provenance_path_for(asset_path: str) -> str:
    """'Assets/Generated/TASK-0003/job/model.fbx' -> 'Assets/Generated/TASK-0003/job/model.fbx.provenance.yaml'."""
def write_provenance(provenance: AssetProvenance, worktree_path: Path) -> str:
    """yaml.safe_dump(provenance.model_dump(mode="json"), sort_keys=True) to <worktree>/<provenance_path_for(asset_path)> via tmp + os.replace; returns repo-relative path."""
def read_provenance(path: Path) -> AssetProvenance:
    """Parse + validate; malformed -> OutputInvalid naming the file."""
class ProvenanceRecorder:                   # AssetPostProcessor, name = "provenance"
    def __init__(self, providers: Mapping[str, AssetProvider], evidence: EvidenceManager) -> None: ...
    async def process(self, ctx: AssetProcessingContext) -> AssetProcessingVerdict: ...

# src/walk/orchestrator/asset_provenance.py
class AssetProvenanceAnswer(FrozenModel):
    asset_path: str
    provenance_path: str
    provider: str
    job_id: str
    prompt: str
    license_or_source: str
    reference_concept: ApprovedArtifactId | None
    generated_by: Actor
    version: int
    related_feature_id: FeatureId | None
    approved_artifact_id: ApprovedArtifactId | None
    approved_by: Actor | None
    evidence_ids: list[EvidenceId]
    def to_markdown(self) -> str: ...       # four §80 questions as H3 headings, answers below, in §80 order

class AssetProvenanceQuery:
    def __init__(self, db: Database, repo_root: Path) -> None: ...      # read-only SQL on approved_artifacts, evidence
    def describe(self, asset_path: str) -> AssetProvenanceAnswer: ...
    def list(self, *, work_item_id: WorkItemId | None = None) -> list[AssetProvenanceAnswer]: ...
```
CLI: `walk assets show PATH [--json]` (exit 0; unknown path → exit 1 with message); `walk assets list [--work-item ID] [--json]` (one line per asset: path, provider, version, approved id or `-`).

#### Behavior
1. `ProvenanceRecorder.process(ctx)`: `p = providers[ctx.job.provider].provenance(ctx.job, ctx.request, ctx.paths, ctx.actor)`; then `version = 1 +` number of existing `*.provenance.yaml` files under `<worktree>/Assets/Generated/<work_item_id>/`, `related_feature_id = ctx.feature_id`; written with `write_provenance` next to `ctx.paths[0]` (the primary asset).
2. Evidence: `EvidenceManager.record(EvidenceDraft(kind=PROJECT_DATA, path_or_uri=<abs provenance path>, description="asset provenance <asset_path>", metrics={"provider", "job_id", "version", "asset_path", "prompt_sha256"}), actor=ctx.actor, work_item_id=ctx.request.work_item_id, phase_id=ctx.phase_id, commit=None)`.
3. Verdict: `ok=True`, `evidence_ids=[id]`, `evidence_kinds=[PROJECT_DATA]`, `extra_paths=[provenance path]` (so `AssetPipelineStep` commits it with the asset). An unknown provider name → failing verdict (`reasons=["no provider <name>"]`), not an exception.
4. The provenance file never contains credentials: the writer refuses (failing verdict) any field value matching the kernel secret patterns supplied as a constructor-free module constant copy (`SECRET_LIKE = r"(sk-|api[_-]?key|Bearer )"`), keeping `integrations` free of a `memory` import.
5. `approved_by` in the file is always `null`; `AssetProvenanceQuery.describe` fills `approved_artifact_id`/`approved_by` from the newest `APPROVED` `approved_artifacts` row of kind `ASSET` whose `payload_paths` contains the asset path or any path under the same `Assets/Generated/<wi>/<job_id>/` directory; none → both `None` ("not approved").
6. `describe` resolves `asset_path` relative to `repo_root`; accepts either the asset or its provenance path; missing provenance file → `ConfigError("no provenance for <path>")`. `evidence_ids` = evidence rows whose `metrics.job_id` equals the provenance `job_id`, ordered by `produced_at`.
7. `to_markdown()` renders: "Where did this asset come from?" (provider, job id, license/source, generated by role/model/run), "Which concept did it follow?" (`reference_concept` or "none recorded"), "Who approved it?" (role/model/run and APR id, or "not approved"), "Which prompt/model generated it?" (prompt verbatim, provider). Deterministic.
8. `list(work_item_id)` scans `Assets/Generated/**/*.provenance.yaml` (only that subtree), sorted by path.
9. The CLI opens the DB read-only and never needs the daemon (ARCHITECTURE §3.1).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given an `AssetProvenance` When written and read back Then equal, file next to the asset with `.provenance.yaml` suffix, keys sorted | `tests/integrations/assets/test_provenance.py::test_write_read_roundtrip_next_to_asset` |
| 2 | Given a malformed provenance file When `read_provenance` Then `OutputInvalid` naming the file | `tests/integrations/assets/test_provenance.py::test_read_malformed_raises` |
| 3 | Given a context from `FakeAssetProvider` When `ProvenanceRecorder.process` Then file written with `related_feature_id` from the context, `approved_by` null, verdict ok with `extra_paths` = [provenance path] | `tests/integrations/assets/test_provenance_recorder.py::test_recorder_writes_file_and_verdict` |
| 4 | Given the same context When processed Then one `PROJECT_DATA` evidence with metrics `provider`, `job_id`, `version` | `tests/integrations/assets/test_provenance_recorder.py::test_recorder_records_project_data_evidence` |
| 5 | Given an existing provenance file for the task When a second generation is processed Then `version == 2` | `tests/integrations/assets/test_provenance_recorder.py::test_recorder_increments_version` |
| 6 | Given a prompt containing `sk-abc123` When processed Then failing verdict and no file written | `tests/integrations/assets/test_provenance_recorder.py::test_recorder_refuses_secret_like_values` |
| 7 | Given a provenance file and an APPROVED ASSET artifact whose payload includes the asset When `describe` Then `approved_artifact_id` and `approved_by` set; without the artifact Then both `None` | `tests/orchestrator/test_asset_provenance.py::test_describe_joins_approval` |
| 8 | Given `describe` on the provenance path itself Then same answer as on the asset path; unknown path Then `ConfigError` | `tests/orchestrator/test_asset_provenance.py::test_describe_accepts_either_path_and_rejects_unknown` |
| 9 | Given an answer When `to_markdown` Then the four §80 questions appear in order with the prompt verbatim | `tests/orchestrator/test_asset_provenance.py::test_markdown_answers_four_questions` |
| 10 | Given two generated assets for TASK-0003 and one for TASK-0004 When `list(work_item_id="TASK-0003")` Then two answers sorted by path | `tests/orchestrator/test_asset_provenance.py::test_list_filters_by_work_item` |
| 11 | Given `walk assets show Assets/Generated/TASK-0003/fake-job-0001/model.fbx` Then exit 0 and output contains `Who approved it?` | `tests/cli/test_cmd_assets.py::test_assets_show_markdown` |
| 12 | Given `walk assets list --json` Then a JSON list of answers; `walk assets show nope.fbx` Then exit 1 | `tests/cli/test_cmd_assets.py::test_assets_list_json_and_show_unknown` |

#### Evidence required
- Quality gate output (ruff ok, mypy ok, N passed, coverage %).
- Demo: after a fake-provider step run on the fixture repo, `cat Assets/Generated/TASK-0003/fake-job-0001/model.fbx.provenance.yaml`; `walk assets show Assets/Generated/TASK-0003/fake-job-0001/model.fbx` showing the four answers; `walk assets list`.

#### Notes
- INTERFACES §2.5 docstring: provenance is stored "next to the asset as `<asset>.provenance.yaml` and as Evidence"; files live in the game tree (`Assets/`), not under `.ai/`, so the `MemoryManager.write` rule (ADR-0003 D-4) does not apply; evidence copies under `.ai/` are made by `EvidenceManager` as for every other evidence.
- `AssetProvenanceQuery` uses read-only SQL on `approved_artifacts` and `evidence` (orchestrator may import `persistence`), not `ApprovedArtifactRepository`, to respect "import protocols/models only" (ARCHITECTURE §1.3).
- Unity creates `.meta` files for the YAML on import; they are committed by the integration step like any other `.meta`.
- `RELOCATE:` PyYAML under `walk/integrations/assets/` (ARCHITECTURE §2.3 yaml row — applied to ARCHITECTURE §2.3 by the architect 2026-10-06).
- `NEW NAME:` `PROVENANCE_SUFFIX`, `provenance_path_for`, `write_provenance`, `read_provenance`, `ProvenanceRecorder`, `SECRET_LIKE`, `AssetProvenanceAnswer`, `AssetProvenanceQuery`, `walk assets show/list` (`assets_app`).
- Commit subject: `feat: add asset provenance files, evidence and assets command (E08-S05)`.

#### Evidence (filled by implementer)
_pending_

---

### E08-S06 — Asset validation via `UnityProvider.validate_assets` and `com.walk.ci`

**Status:** TODO
**Type:** feat
**Requirements:** §79, §62, §6.6, §47, §10.5, ADR-0009 D-6, D-13
**Depends on:** E08-S04, E03-S10
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every generated asset is imported and measured by Unity through `com.walk.ci` (`WalK.CI.ValidateAssets`), the metrics are checked against §79 rules held as data (kernel defaults + project override + per-request constraints), and the result is recorded as `LOG` evidence plus `SCREENSHOT` evidence (Unity preview render, falling back to the provider thumbnail or the image itself) so that the Art Director reviews pictures, not assertions.

#### Scope
- In: C# `WalK.CI.ValidateAssets` and metrics collector; `UnityBatchProvider.validate_assets`; `AssetMetrics` parsing; rule model, kernel default rules file, project override loader, evaluator; `AssetValidationProcessor` post-processor; `FakeUnityProvider.validate_assets` scripting; one `@pytest.mark.integration` test against a real Unity install.
- Out: provenance (E08-S05); Art Director judgement (E08-S07 — a passing validation is necessary, not sufficient, §10.5); Unity MCP screenshots (E08-S08, optional alternative source); performance budgets at scene level (Stage 9+ perf work).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `unity/com.walk.ci/Editor/WalkCI.cs` | modify `(verify: created by E03-S10)` | `WalK.CI.ValidateAssets` (C#) |
| `unity/com.walk.ci/Editor/AssetMetricsCollector.cs` | create | `WalK.AssetMetricsCollector` (C#) |
| `unity/com.walk.ci/Tests/Editor/AssetMetricsCollectorTests.cs` | create | — (Unity EditMode tests, run by the owner) |
| `src/walk/integrations/unity/asset_metrics.py` | create | `AssetMetrics`, `TextureMetrics`, `parse_asset_validation_result` |
| `src/walk/integrations/unity/provider.py` | modify `(verify: created by E03-S10)` | `UnityBatchProvider.validate_assets` |
| `src/walk/integrations/assets/rules.py` | create | `AssetKindRules`, `AssetRuleSet`, `AssetRuleViolation`, `ASSET_RULES_DEFAULT_PATH`, `load_asset_rules`, `evaluate_asset_metrics` |
| `src/walk/integrations/assets/asset_rules.yaml` | create | — (kernel default rules, `version: "1.0"`) |
| `src/walk/integrations/assets/validation.py` | create | `AssetValidationProcessor` |
| `src/walk/cli/composition.py` | modify | — (loads rules, `generator.add_post_processor(AssetValidationProcessor(...))`) |
| `pyproject.toml` | modify | — (same `yaml` allowance under `walk.integrations.assets` as E08-S05; whichever story merges second drops the duplicate line) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§2.4 `validate_assets` docstring: `JobResult.metrics["assets"]` schema) |
| `tests/fakes/fake_unity_provider.py` | modify | `FakeUnityProvider.validate_assets`, `FakeUnityProvider.asset_metrics` |
| `tests/integrations/unity/fixtures/asset_validation_result.json` | create | — |
| `tests/integrations/unity/test_asset_metrics.py` | create | — |
| `tests/integrations/unity/test_provider_validate_assets.py` | create | — |
| `tests/integrations/unity/test_validate_assets_live.py` | create | — (`@pytest.mark.integration`) |
| `tests/integrations/assets/test_rules.py` | create | — |
| `tests/integrations/assets/test_validation_processor.py` | create | — |

#### Interface contract
Protocol: INTERFACES §2.4 `UnityProvider.validate_assets(project_path, paths) -> JobResult` with `job_kind="asset_validation"`. Unity invocation (ADR-0009 D-6):
```
<unity> -batchmode -quit -projectPath <worktree> -executeMethod WalK.CI.ValidateAssets
        -walkAssets <comma-separated repo-relative paths> -walkResult <.walk/cache/unity/asset-validation-<n>.json>
        -walkPreviewDir <.walk/cache/asset-previews/<work_item_id>/> -logFile <.walk/logs/unity-asset-validation-<n>.log>
```
Result JSON (written by C#, parsed by `parse_asset_validation_result`):
```json
{"ok": true, "assets": [{"path": "Assets/Generated/TASK-0003/job/model.fbx", "type": "model",
  "import_ok": true, "import_errors": [], "triangles": 1840, "vertices": 1200, "materials": 2, "bones": 0,
  "textures": [{"path": "...", "width": 1024, "height": 1024}], "bounds_size": [0.9, 1.8, 0.6],
  "pivot_offset": [0.0, 0.0, 0.0], "animation_clips": [], "platform_issues": {"Android": []},
  "preview": ".walk/cache/asset-previews/TASK-0003/model.png"}]}
```
```python
# src/walk/integrations/unity/asset_metrics.py
class TextureMetrics(FrozenModel):
    path: str
    width: int
    height: int
class AssetMetrics(FrozenModel):
    path: str
    type: Literal["model", "texture", "other"]
    import_ok: bool
    import_errors: list[str]
    triangles: int | None
    vertices: int | None
    materials: int | None
    bones: int | None
    textures: list[TextureMetrics]
    bounds_size: tuple[float, float, float] | None
    pivot_offset: tuple[float, float, float] | None     # pivot minus bottom-centre of bounds, metres
    animation_clips: list[str]
    platform_issues: dict[str, list[str]]
    preview: str | None
def parse_asset_validation_result(path: Path) -> list[AssetMetrics]: ...   # malformed -> OutputInvalid

# src/walk/integrations/assets/rules.py
class AssetKindRules(FrozenModel):
    max_triangles: int | None = None
    max_materials: int | None = None
    max_bones: int | None = None
    max_texture_px: int | None = None
    require_power_of_two: bool = False
    scale_m: tuple[float, float] | None = None          # allowed range of the largest bounds dimension
    pivot: Literal["bottom_center", "center", "any"] = "any"
    pivot_tolerance_m: float = 0.05
    required_clips: list[str] = []
    require_import_ok: bool = True
    platforms: list[str] = []                           # BuildTarget values whose platform_issues must be empty
class AssetRuleSet(FrozenModel):
    version: str
    kinds: dict[str, AssetKindRules]                    # keys = AssetRequest.kind
class AssetRuleViolation(FrozenModel):
    asset_path: str
    rule: str
    expected: str
    actual: str
    def __str__(self) -> str: ...                       # "<asset_path>: <rule> expected <expected>, got <actual>"
ASSET_RULES_DEFAULT_PATH: Final[Path]                   # package data asset_rules.yaml
def load_asset_rules(default_path: Path, project_path: Path | None) -> AssetRuleSet: ...
def evaluate_asset_metrics(kind: str, metrics: list[AssetMetrics], rules: AssetRuleSet, constraints: JsonDict) -> list[AssetRuleViolation]: ...

# src/walk/integrations/assets/validation.py
class AssetValidationProcessor:                         # AssetPostProcessor, name = "validation"
    def __init__(self, unity: UnityProvider | None, evidence: EvidenceManager, rules: AssetRuleSet) -> None: ...
    async def process(self, ctx: AssetProcessingContext) -> AssetProcessingVerdict: ...
```
Project override file: `.ai/project/asset-rules.yaml` (same schema; read-only for the kernel; per-kind fields replace kernel defaults field by field).

#### Behavior
1. C# `ValidateAssets` imports each listed path (`AssetDatabase.ImportAsset`, forced synchronous), captures importer errors through a log handler, computes the metrics above (triangles/vertices summed over `MeshFilter`/`SkinnedMeshRenderer` shared meshes, distinct `sharedMaterials`, distinct skinned bones, combined renderer bounds, `AnimationClip`s at the path, referenced `Texture2D` sizes, per-target `platform_issues` from `TextureImporter` platform settings — non-power-of-two textures where the target's compression needs it, size above the platform max), renders a 512×512 PNG preview of models with a temporary camera when a graphics device exists (`preview: null` otherwise), writes the JSON, and exits 0 even when assets fail (failure is data); exceptions exit 1.
2. `UnityBatchProvider.validate_assets` runs the command through `SubprocessRunner`; `ok = exit_code == 0 and all(a.import_ok)`; `metrics = {"assets": [m.model_dump(mode="json") ...]}`; `artifact_paths = [result json] + previews`; `summary = "<n> assets, <k> import failures"`; Unity missing → `JobResult(ok=False, summary="unity unavailable")` (never raises for a missing editor).
3. `evaluate_asset_metrics`: rules for `kind` (unknown kind → no rules, no violations); per-request overrides: `constraints["triangle_budget"]` → `max_triangles`, `constraints["texture_size"]` → `max_texture_px`, `constraints["required_clips"]` → `required_clips`; each failed check yields one violation with `rule` ∈ {`import_ok`, `max_triangles`, `max_materials`, `max_bones`, `max_texture_px`, `power_of_two`, `scale_m`, `pivot`, `required_clips`, `platform:<target>`}; checks on `None` metrics are skipped (e.g. textures have no triangles).
4. `load_asset_rules`: kernel defaults then project file; unknown keys or wrong types → `ConfigError` naming the file and key; missing project file → defaults.
5. `AssetValidationProcessor.process(ctx)`: (a) `unity is None` → no Unity evidence, `reasons=["validation skipped: unity unavailable"]`, `ok=True` only if the request kind is `image`/`texture` (no import-level checks possible otherwise `ok=False`); (b) otherwise call `validate_assets(ctx.worktree_path, ctx.paths)`, record `LOG` evidence for the result JSON with metrics `{assets, violations}`; (c) violations from `evaluate_asset_metrics`; (d) `SCREENSHOT` evidence per asset from the first available source: Unity `preview` → provider `thumbnail.png` in `ctx.paths` → the image file itself for `image`/`texture`; (e) verdict `ok = job.ok and not violations`, `reasons = [str(v) ...]` (plus the job summary when `job.ok` is false), `evidence_kinds` = kinds actually recorded.
6. A model asset that passes every rule but has no screenshot source yields `ok=True` with reason `no screenshot available` — the review story requires `SCREENSHOT` evidence through `required_evidence` (E08-S07), so this surfaces at `submit` as a guard rejection rather than silently.
7. `FakeUnityProvider.validate_assets` returns metrics from `asset_metrics[path]` when scripted, otherwise passing defaults (`import_ok=True`, `triangles=1000`, `materials=1`, `preview` = a 1×1 PNG written under the given worktree's `.walk/cache/asset-previews/`), and records calls in `validate_calls`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the fixture result JSON When parsed Then two `AssetMetrics` with the fixture values; a truncated file Then `OutputInvalid` | `tests/integrations/unity/test_asset_metrics.py::test_parse_result_and_reject_malformed` |
| 2 | Given a `FakeSubprocessRunner` exiting 0 and writing the fixture When `validate_assets` Then the command contains `-executeMethod WalK.CI.ValidateAssets` and `-walkAssets`, `job_kind=="asset_validation"`, `metrics["assets"]` has two entries | `tests/integrations/unity/test_provider_validate_assets.py::test_validate_assets_builds_command_and_parses` |
| 3 | Given a fixture with one `import_ok=false` When `validate_assets` Then `ok=False` and summary counts one import failure | `tests/integrations/unity/test_provider_validate_assets.py::test_validate_assets_import_failure_not_ok` |
| 4 | Given no Unity executable When `validate_assets` Then `ok=False`, summary `unity unavailable`, no exception | `tests/integrations/unity/test_provider_validate_assets.py::test_validate_assets_without_unity` |
| 5 | Given kernel defaults and a project file overriding `model3d.max_triangles` When `load_asset_rules` Then that field replaced, others kept; unknown key Then `ConfigError` | `tests/integrations/assets/test_rules.py::test_load_rules_project_override_and_validation` |
| 6 | Given metrics with 25 000 triangles and `triangle_budget=20000` When evaluated Then one `max_triangles` violation mentioning both numbers | `tests/integrations/assets/test_rules.py::test_triangle_budget_from_constraints` |
| 7 | Given metrics violating texture size, power-of-two, pivot, scale, required clip and an Android platform issue When evaluated Then one violation per rule, in rule order | `tests/integrations/assets/test_rules.py::test_each_rule_reports_violation` |
| 8 | Given texture metrics (no triangles) When evaluated with model rules present Then triangle checks skipped | `tests/integrations/assets/test_rules.py::test_none_metrics_are_skipped` |
| 9 | Given a passing fake Unity result with a preview When the processor runs Then verdict ok, `LOG` and `SCREENSHOT` evidence recorded, `evidence_kinds == [LOG, SCREENSHOT]` | `tests/integrations/assets/test_validation_processor.py::test_processor_records_log_and_screenshot` |
| 10 | Given a result violating `max_triangles` When the processor runs Then verdict not ok with the violation text as reason | `tests/integrations/assets/test_validation_processor.py::test_processor_fails_on_violation` |
| 11 | Given no preview but a provider `thumbnail.png` in paths When processed Then the thumbnail is the `SCREENSHOT` evidence | `tests/integrations/assets/test_validation_processor.py::test_screenshot_falls_back_to_thumbnail` |
| 12 | Given `unity=None` and kind `image` / kind `model3d` When processed Then ok with skip reason / not ok | `tests/integrations/assets/test_validation_processor.py::test_processor_without_unity_by_kind` |
| 13 | Given `WALK_UNITY_PATH` and the sample project When the live test validates a bundled cube FBX Then `import_ok` and `triangles == 12` | `tests/integrations/unity/test_validate_assets_live.py::test_validate_cube_with_real_unity` |

#### Evidence required
- Quality gate output; live test listed as skipped.
- Owner-run transcript: Unity EditMode tests `AssetMetricsCollectorTests` green in the sample project; `uv run pytest -m integration tests/integrations/unity/test_validate_assets_live.py`.
- Demo: on the fixture repo with `FakeUnityProvider`, `walk ledger query --work-item TASK-0003 --kind EVIDENCE_RECORDED` lists `LOG` and `SCREENSHOT` evidence for the generated asset.

#### Notes
- ADR-0009 D-6 names `WalK.CI.ValidateAssets`; D-13 fixes the data model now and the automation in Stage 8; §79 lists the checks ("MAY include"), all of which are rules here with the defaults in `asset_rules.yaml` (values are starting points the project tunes in `.ai/project/asset-rules.yaml`).
- Preview rendering needs a graphics device: Unity must not be started with `-nographics` for previews; CI machines without a GPU get `preview: null` and fall back to provider thumbnails (Behavior 5d).
- `integrations` may not import `memory` (ARCHITECTURE §2.2): the project override is read as a plain YAML file, not through `MemoryManager` (read-only access to `.ai/` is allowed; writes are not made).
- `NEW NAME:` `AssetMetrics`, `TextureMetrics`, `parse_asset_validation_result`, `AssetKindRules`, `AssetRuleSet`, `AssetRuleViolation`, `ASSET_RULES_DEFAULT_PATH`, `load_asset_rules`, `evaluate_asset_metrics`, `asset_rules.yaml`, `.ai/project/asset-rules.yaml`, `AssetValidationProcessor`, `WalK.AssetMetricsCollector`, Unity arguments `-walkAssets`/`-walkResult`/`-walkPreviewDir`, `FakeUnityProvider.asset_metrics`/`validate_calls`.
- Commit subject: `feat: add unity asset validation rules and evidence (E08-S06)`.

#### Evidence (filled by implementer)
_pending_

---

### E08-S07 — Art Director review flow and ART/DESIGN done dimensions

**Status:** TODO
**Type:** feat
**Requirements:** §10.4, §10.5, §6.5, §33, §78, §61, §31, §137 (Inv. 4, 7, 10)
**Depends on:** E08-S01, E08-S06, E03-S17
**Effort:** MEDIUM   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Asset tasks are created in a normalised shape (implementer `KERNEL`, reviewer ART_DIRECTOR, screenshot + validation evidence required), the Art Director's review either registers the asset as `ApprovedArtifact(kind=ASSET)` or sends it back with revision notes that change the next generation request, and features get `ART_COMPLETE` (all asset tasks approved and complete) and `DESIGN_VALIDATED` (DESIGN_LEADER review at feature QC) as applicable done dimensions, so `all_applicable_dimensions_done` (E03-S17) enforces §6.5 for art and design.

#### Scope
- In: `OutputApplier` normalisation of asset task drafts; ART_DIRECTOR REVIEW handling on asset tasks (`art.approve`/`art.reject` authorisation, `approve_artifact(kind=ASSET)`, revision notes via `update_contract`); DESIGN_LEADER feature-level REVIEW handling (`DESIGN_VALIDATED`, hold label on reject); `WorkflowManager.update_contract` / `set_applicable_dimensions`; `ArtDimensionTracker` and its builtin hook attachment; router rule FEATURE `QC` → DESIGN_LEADER; REVIEW template art/design blocks.
- Out: the generation step and regeneration loop (E08-S04); provenance files (E08-S05 — not used here, header decision); validation rules (E08-S06); ART_DIRECTION change approval (USER via `walk artifacts approve --supersedes`, E02-S12; escalation classification E08-S01); `UX_COMPLETE` and `PERFORMANCE_ACCEPTABLE` dimensions (no Stage 8 owner).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/runtime/output_applier.py` | modify `(verify: E01-S27/E03-S08/E03-S13)` | `DefaultOutputApplier.apply` (asset drafts, ART_DIRECTOR review, DESIGN_LEADER feature review), `ASSET_TASK_REQUIRED_EVIDENCE`, `REVIEW_TOOLS_BY_ROLE` |
| `src/walk/workflow/protocols.py` | modify | `WorkflowManager.update_contract`, `WorkflowManager.set_applicable_dimensions` |
| `src/walk/workflow/service.py` | modify | `DefaultWorkflowManager.update_contract`, `DefaultWorkflowManager.set_applicable_dimensions` |
| `src/walk/orchestrator/art_dimensions.py` | create | `applicable_dimensions_for`, `ArtDimensionTracker`, `DESIGN_REVIEW_HOLD_LABEL` |
| `src/walk/orchestrator/router.py` | modify `(verify)` | `DefaultTaskRouter.route` (FEATURE `QC` → DESIGN_LEADER rule) |
| `src/walk/orchestrator/__init__.py` | modify | re-exports |
| `src/walk/orchestrator/builtin_hooks.py` | modify `(verify: BuiltinHookDeps from E02-S08/E07-S03; ADR-0016 path)` | `art_dimensions_on_transition`, `BuiltinHookDeps.art_dimensions` |
| `src/walk/agents/templates/REVIEW.md.j2` | modify | — (ART_DIRECTOR asset-review block; DESIGN_LEADER feature-review block) |
| `src/walk/cli/composition.py` | modify | — (constructs `ArtDimensionTracker`, passes it to hooks and applier) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§1.3 two methods; §4 row FEATURE `QC` → DESIGN_LEADER) |
| `tests/runtime/test_output_applier_asset_tasks.py` | create | — |
| `tests/runtime/test_output_applier_art_review.py` | create | — |
| `tests/runtime/test_output_applier_design_review.py` | create | — |
| `tests/workflow/test_service_contract_dimensions.py` | create | — |
| `tests/orchestrator/test_art_dimensions.py` | create | — |
| `tests/orchestrator/test_router_design_review.py` | create | — |
| `tests/hooks/test_builtins_art_dimensions.py` | create | — |
| `tests/agents/test_templates_e08.py` | create | — |

#### Interface contract
```python
# src/walk/workflow/protocols.py (WorkflowManager additions; implemented in DefaultWorkflowManager)
async def update_contract(self, work_item_id: WorkItemId, contract: StoryContract, *, actor: AgentRole) -> WorkItem:
    """Replace the contract of a STORY/TASK/BUG in work_items (state and state_version unchanged). No ledger event of its own:
    the triggering run's AGENT_RUN_ENDED carries the findings; actor == USER additionally writes USER_OVERRIDE (§93).
    Raises ConfigError for kinds without a contract."""
async def set_applicable_dimensions(self, feature_id: FeatureId, dimensions: list[DoneDimension]) -> Feature:
    """Replace Feature.applicable_dimensions (deduplicated, enum order); existing done_dimensions entries are kept."""

# src/walk/runtime/output_applier.py
ASSET_TASK_REQUIRED_EVIDENCE: Final = (EvidenceKind.LOG, EvidenceKind.SCREENSHOT)
REVIEW_TOOLS_BY_ROLE: Final[dict[AgentRole, tuple[ToolName, ToolName]]] = {
    AgentRole.LEAD_DEV: ("review.approve", "review.reject"),
    AgentRole.ART_DIRECTOR: ("art.approve", "art.reject"),
    AgentRole.DESIGN_LEADER: ("review.approve", "review.reject"),   # see Notes
}

# src/walk/orchestrator/art_dimensions.py
DESIGN_REVIEW_HOLD_LABEL: Final = "design-review-hold"
def applicable_dimensions_for(feature: Feature, *, design_leader_enabled: bool, art_director_enabled: bool,
                              has_asset_children: bool) -> list[DoneDimension]:
    """feature.applicable_dimensions ∪ {DESIGN_VALIDATED if design_leader_enabled} ∪ {ART_COMPLETE if art_director_enabled and
    (has_asset_children or ART_LABEL in feature.labels)}; pure."""
class ArtDimensionTracker:
    def __init__(self, workflow: WorkflowManager, evidence: EvidenceManager, db: Database,
                 enabled_roles: Callable[[], list[AgentRole]]) -> None: ...
    async def refresh_applicability(self, feature_id: FeatureId) -> Feature: ...
    async def on_transition(self, item: WorkItem, to_state: WorkItemState) -> None: ...   # called by the builtin hook
```
`ApprovedArtifact` for an approved asset (DOMAIN-MODEL §4.7): `id="APR-0000"` (allocated), `kind=ASSET`, `title=task.title`, `status=APPROVED`, `scope=<parent FEAT id>`, `version` per E02-S12, `approved_by=Actor(ART_DIRECTOR, model_id, run_id)`, `related_requirements=contract.source_requirements`, `payload_paths` = files of the newest `asset(<task id>):` commit on the task branch, `supersedes` = the task's previous APPROVED ASSET artifact if any.

#### Behavior
1. Asset drafts: a `new_tasks` draft whose `contract.asset_request` is set is normalised before `WorkflowManager.create`: `kind=TASK`, `owner_role=KERNEL`, `reviewer_role=ART_DIRECTOR`, `required_evidence ⊇ ASSET_TASK_REQUIRED_EVIDENCE`, `asset_request["constraints"]["base_prompt"] = asset_request["prompt"]` when absent; `asset_request` must validate as `AssetRequest` (with the parent id as placeholder `work_item_id`) else `OutputInvalid` (one repair turn, E01-S27). Only roles whose `authority.may_create_work` contains TASK may create them (existing check). After creation the parent feature's applicability is refreshed (`ArtDimensionTracker.refresh_applicability`).
2. ART_DIRECTOR REVIEW on an asset task, status `APPROVED`: authorise `art.approve` through `ToolInvoker.authorize` for the run (DENY → `PermissionDenied`, nothing applied); require at least one `SCREENSHOT` evidence on the task (else treat as `OutputInvalid`: "approval without screenshot evidence"); call `MemoryManager.approve_artifact(...)` as specified above with `actor = Actor(ART_DIRECTOR, model_id, run_id)` (ledger `ARTIFACT_APPROVED` by memory); then raise the story_workflow review-approve event (E03-S13 name) with payload `approved_artifact_ids=[APR id]`.
3. ART_DIRECTOR REVIEW, status `REJECTED`: authorise `art.reject`; findings with severity `WARNING`/`RISK` (or all findings when none are) become revision notes: `constraints["revision_notes"]` gets one entry `"r<n>: <summary> — <detail>"` per finding and `prompt = base_prompt + "\n\nRevision notes:\n- " + "\n- ".join(all notes)`; written with `update_contract(actor=ART_DIRECTOR)`; then the review-reject event is raised (→ REWORK, where E08-S04's step regenerates with the new request hash). A reject with no findings is `OutputInvalid` ("reject requires actionable revision notes", §10.5 skill rule).
4. A technically valid asset (all validation verdicts ok) may be rejected — no guard prevents it (§10.5); the test asserts the REWORK transition happens with passing validation evidence present.
5. DESIGN_LEADER REVIEW at FEATURE `QC`: `APPROVED` → record `EvidenceDraft(kind=EXPERT_REASONING, path_or_uri=<review summary written by the kernel under the feature evidence folder via EvidenceManager>, description="design validation")`, `set_done_dimension(feature, DESIGN_VALIDATED, True, evidence_id)`, no workflow event; `REJECTED` → `new_tasks` from the output are created (design rework), label `design-review-hold` added, no workflow event.
6. Router at FEATURE `QC`: if `DESIGN_VALIDATED ∈ applicable_dimensions`, not done, and DESIGN_LEADER enabled → DESIGN_LEADER/REVIEW unless the feature has `design-review-hold` (→ no route this tick); otherwise the existing QC/QC row. Asset tasks in `READY_FOR_REVIEW` keep routing through `contract.reviewer_role` (ART_DIRECTOR).
7. `ArtDimensionTracker.on_transition(item, to_state)` (builtin `ON_STATE_TRANSITION` attachment, `log_and_continue`): (a) asset task → `COMPLETE`: if every asset task under the same feature is `COMPLETE` and each has an `APPROVED` `ASSET` artifact whose `payload_paths` lie under `Assets/Generated/<task id>/` (read-only SQL on `approved_artifacts`), record `PROJECT_DATA` evidence listing the APR ids and `set_done_dimension(feature, ART_COMPLETE, True, evidence_id)`; (b) any child of a feature with `design-review-hold` reaches `COMPLETE`/`CANCELLED` and no open children remain → remove the label.
8. `refresh_applicability` computes `applicable_dimensions_for(...)` and calls `set_applicable_dimensions` only when the set changed; it never removes a dimension already marked done.
9. `REVIEW.md.j2`: when `role == ART_DIRECTOR` renders an "Asset review" block listing the task's `SCREENSHOT` and `LOG` evidence (paths and validation metrics), the referenced approved artifacts (`reference_artifact_ids`), the §10.5 checklist from the `art-direction-review` skill, and the rule "reject requires revision notes in findings"; when `role == DESIGN_LEADER` and the subject is a FEATURE renders a "Design validation" block (§10.4 list). Other roles render exactly as before (snapshot test).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given an ART_DIRECTOR DESIGN output with an asset draft (owner SENIOR_DEV, no evidence) When applied Then the TASK has owner KERNEL, reviewer ART_DIRECTOR, required evidence ⊇ LOG+SCREENSHOT and `base_prompt` set | `tests/runtime/test_output_applier_asset_tasks.py::test_asset_draft_normalised` |
| 2 | Given an asset draft whose `asset_request.kind` is invalid When applied Then `OutputInvalid` and no task created | `tests/runtime/test_output_applier_asset_tasks.py::test_invalid_asset_request_rejected` |
| 3 | Given a feature with ART_DIRECTOR enabled When its first asset task is created Then `ART_COMPLETE` becomes applicable | `tests/runtime/test_output_applier_asset_tasks.py::test_asset_task_makes_art_complete_applicable` |
| 4 | Given an asset task in review with screenshot evidence When ART_DIRECTOR outputs `APPROVED` Then an `APPROVED` `ASSET` artifact scoped to the feature exists with `approved_by.role == ART_DIRECTOR`, payload = files of the newest asset commit, and the review-approve event was raised | `tests/runtime/test_output_applier_art_review.py::test_art_approve_registers_asset_artifact` |
| 5 | Given no screenshot evidence When ART_DIRECTOR outputs `APPROVED` Then `OutputInvalid` and no artifact | `tests/runtime/test_output_applier_art_review.py::test_art_approve_requires_screenshot` |
| 6 | Given permissions denying `art.approve` for the run When applied Then `PermissionDenied` and state unchanged | `tests/runtime/test_output_applier_art_review.py::test_art_approve_requires_permission` |
| 7 | Given passing validation evidence When ART_DIRECTOR outputs `REJECTED` with one RISK finding Then task REWORK, `revision_notes` has one entry, prompt = base prompt + notes | `tests/runtime/test_output_applier_art_review.py::test_art_reject_valid_asset_adds_revision_notes` |
| 8 | Given `REJECTED` with no findings When applied Then `OutputInvalid` | `tests/runtime/test_output_applier_art_review.py::test_art_reject_requires_findings` |
| 9 | Given a second approval for the same task When applied Then the new artifact `supersedes` the first and the first is `SUPERSEDED` | `tests/runtime/test_output_applier_art_review.py::test_reapproval_supersedes_previous_asset` |
| 10 | Given `update_contract` on a TASK / on a FEATURE Then contract replaced / `ConfigError`; `set_applicable_dimensions` deduplicates and keeps done entries | `tests/workflow/test_service_contract_dimensions.py::test_update_contract_and_set_applicable_dimensions` |
| 11 | Given a feature with label `art`, ART_DIRECTOR and DESIGN_LEADER enabled When `applicable_dimensions_for` Then defaults + DESIGN_VALIDATED + ART_COMPLETE; disabled roles Then defaults only | `tests/orchestrator/test_art_dimensions.py::test_applicable_dimensions_rules` |
| 12 | Given two asset tasks, one COMPLETE+approved When the second becomes COMPLETE with an approved artifact Then `ART_COMPLETE` true with PROJECT_DATA evidence; if one lacks approval Then not set | `tests/orchestrator/test_art_dimensions.py::test_art_complete_set_when_all_assets_approved` |
| 13 | Given a held feature whose last open child completes When `on_transition` Then the hold label is removed | `tests/orchestrator/test_art_dimensions.py::test_hold_label_cleared_when_children_settle` |
| 14 | Given FEATURE QC with DESIGN_VALIDATED pending / with hold label / already done When `route` Then DESIGN_LEADER REVIEW / no route / QC | `tests/orchestrator/test_router_design_review.py::test_feature_qc_routing_for_design_validation` |
| 15 | Given DESIGN_LEADER outputs `APPROVED` at feature QC Then `DESIGN_VALIDATED` true with EXPERT_REASONING evidence and feature still QC; `REJECTED` with one new task Then task created and hold label set | `tests/runtime/test_output_applier_design_review.py::test_design_leader_feature_review_outcomes` |
| 16 | Given the builtin hooks When `ON_STATE_TRANSITION` fires for an asset task to COMPLETE Then the tracker is called; tracker errors are logged and do not fail the transition | `tests/hooks/test_builtins_art_dimensions.py::test_hook_calls_tracker_log_and_continue` |
| 17 | Given an ART_DIRECTOR REVIEW input When rendered Then the "Asset review" block lists screenshots and validation metrics; a LEAD_DEV REVIEW render equals the pre-E08 snapshot | `tests/agents/test_templates_e08.py::test_review_template_art_block_and_unchanged_default` |

#### Evidence required
- Quality gate output (ruff ok, mypy ok, N passed, coverage %).
- Demo on the fixture repo with fake adapters: `walk work show TASK-0003` (REWORK after reject, then INTEGRATION after approve), `walk artifacts list` showing the `ASSET` artifact with `approved_by ART_DIRECTOR`, `walk work show FEAT-0001` showing `ART_COMPLETE: true` once the task completes.

#### Notes
- E03-S13 (Lead Dev review flow: event names, cross-model guard), E03-S17 (`all_applicable_dimensions_done`), E02-S12 (`approve_artifact` authority, `supersedes`, write guard), ADR-0006 D-2 (review authority evaluated against the acting role inside `OutputApplier`).
- DESIGN_LEADER reuses `review.approve`/`review.reject` for feature-level design validation only if E02-S10 defaults allow it for DESIGN_LEADER; otherwise E08-X01 decides between adding DESIGN_LEADER rows to `permissions/defaults.yaml` (this story then lists that file) or new tools `design.approve`/`design.reject` (`NEW NAME:`). `(verify)`.
- Invariant 4: the Art Director never reviews its own output because the implementer of an asset task is `KERNEL`; Invariant 10: assets become approved artifacts only through `approve_artifact`.
- Effort is fixed by WBS at MEDIUM; Behaviors 5–7 (design validation) are the part to keep minimal. Risk HIGH because it touches `OutputApplier` and the feature-completion path.
- `NEW NAME:` `WorkflowManager.update_contract`, `WorkflowManager.set_applicable_dimensions`, `ASSET_TASK_REQUIRED_EVIDENCE`, `REVIEW_TOOLS_BY_ROLE`, `applicable_dimensions_for`, `ArtDimensionTracker`, `DESIGN_REVIEW_HOLD_LABEL`, `art_dimensions_on_transition`, `BuiltinHookDeps.art_dimensions`, routing row FEATURE `QC` → DESIGN_LEADER, asset-request keys `base_prompt`/`revision_notes`.
- Commit subject: `feat: add art director review flow and art design dimensions (E08-S07)`.

#### Evidence (filled by implementer)
_pending_

---

### E08-S08 — Unity MCP provider (`ToolKind.MCP`)

**Status:** TODO
**Type:** feat
**Requirements:** §30, §31, §62, §6.6, §79 (visual checks), §91, §129, ADR-0009 D-6 (deferred item), §137 (Inv. 7, 11)
**Depends on:** E08-X01, E01-S14
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The kernel can talk to a running Unity Editor through an MCP server as an optional provider: MCP tools are declared in the tool registry as `ToolKind.MCP`, authorised and metered at the same `ToolInvoker` enforcement point as KERNEL tools, executed by a kernel-side MCP client (agents never connect to the server), and image results become `SCREENSHOT` evidence — giving agents read-only visual inspection (screenshots, console, asset inspection) without changing the batchmode-first CI path.

#### Scope
- In: ADR-0015 (decision record); minimal MCP client over stdio (JSON-RPC 2.0: `initialize`, `notifications/initialized`, `tools/list`, `tools/call`); `UnityMcpProvider` with a configurable kernel-tool → server-tool map; three read-only MCP tools; `ToolInvoker.invoke` accepting `ToolKind.MCP`; `McpToolHandler` (evidence for images); permission defaults for the MCP tools; preflight readiness; fake transport; one `@pytest.mark.integration` test against a real server.
- Out: scene-mutating MCP tools (create/modify GameObjects, play mode) — not in Stage 8; MCP servers other than Unity; exposing kernel tools to agents through an MCP server (ADR-0006 alternative, still deferred); replacing `UnityBatchProvider` for CI (ADR-0009 D-6 keeps batchmode); wiring MCP screenshots into the asset pipeline (E08-S06 uses batchmode previews; agents may call `unity_mcp.screenshot` during review).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/01-architecture/adr/ADR-0015-unity-mcp-provider.md` | modify | — (exists as `Proposed`, 2026-10-06; record the acceptance-checklist results and set `Accepted`) |
| `src/walk/integrations/unity_mcp/__init__.py` | create | re-exports |
| `src/walk/integrations/unity_mcp/client.py` | create | `McpTransport`, `StdioMcpTransport`, `McpClient`, `McpToolResult`, `MCP_PROTOCOL_VERSION` |
| `src/walk/integrations/unity_mcp/provider.py` | create | `UnityMcpProvider`, `UNITY_MCP_TOOLS` |
| `src/walk/integrations/errors.py` | modify | `McpProtocolError` |
| `src/walk/integrations/service.py` | modify | `DefaultIntegrationManager.__init__` (`unity_mcp` parameter), `DefaultIntegrationManager.preflight` (`tools["unity_mcp"]`) |
| `src/walk/tools/builtin/tools_mcp.yaml` | create | — (3 MCP tool rows) |
| `src/walk/permissions/defaults_unity_mcp.yaml` | create | — |
| `src/walk/permissions/loader.py` | modify | `load_defaults` (accepts additional default files) |
| `src/walk/runtime/tool_invoker.py` | modify | `DefaultToolInvoker.invoke` (`ToolKind.MCP` dispatch) |
| `src/walk/runtime/mcp_tools.py` | create | `McpToolHandler` |
| `src/walk/runtime/__init__.py` | modify | re-exports |
| `src/walk/cli/composition.py` | modify | `KernelSettings.unity_mcp_command`, `KernelSettings.unity_mcp_tool_map` (loads `tools_mcp.yaml`, the MCP permission file, registers handlers) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§1.13 `ToolInvoker.invoke` docstring: KERNEL or MCP; §2.4 note on optional Unity MCP provider) |
| `tests/fakes/fake_mcp_transport.py` | create | `FakeMcpTransport` |
| `tests/integrations/unity_mcp/__init__.py` | create | — |
| `tests/integrations/unity_mcp/test_client.py` | create | — |
| `tests/integrations/unity_mcp/test_provider.py` | create | — |
| `tests/integrations/unity_mcp/test_unity_mcp_live.py` | create | — (`@pytest.mark.integration`) |
| `tests/integrations/test_preflight_unity_mcp.py` | create | — |
| `tests/tools/test_builtin_tools_mcp.py` | create | — |
| `tests/permissions/test_defaults_unity_mcp.py` | create | — |
| `tests/runtime/test_tool_invoker_mcp.py` | create | — |
| `tests/runtime/test_mcp_tools.py` | create | — |

#### Interface contract
```python
# src/walk/integrations/unity_mcp/client.py
MCP_PROTOCOL_VERSION: Final = "2025-06-18"          # confirmed in ADR-0015
class McpTransport(Protocol):
    async def send(self, message: JsonDict) -> None: ...
    async def receive(self) -> JsonDict: ...
    async def close(self) -> None: ...
class StdioMcpTransport:                            # newline-delimited JSON over a child process' stdin/stdout
    def __init__(self, command: list[str], *, cwd: str, env: Mapping[str, str]) -> None: ...
class McpToolResult(FrozenModel):
    is_error: bool
    text: list[str]
    images: list[JsonDict]                          # {"mime_type": str, "data_b64": str}
class McpClient:
    def __init__(self, transport: McpTransport, *, request_timeout_s: float = 30.0) -> None: ...
    async def initialize(self) -> JsonDict: ...     # returns serverInfo + capabilities
    async def list_tools(self) -> list[JsonDict]: ...
    async def call_tool(self, name: str, arguments: JsonDict) -> McpToolResult: ...
    async def close(self) -> None: ...

# src/walk/integrations/unity_mcp/provider.py
UNITY_MCP_TOOLS: Final = ("unity_mcp.screenshot", "unity_mcp.console", "unity_mcp.inspect_asset")
class UnityMcpProvider:
    provider: str = "unity_mcp"
    def __init__(self, client_factory: Callable[[], Awaitable[McpClient]], tool_map: Mapping[str, str]) -> None: ...
    async def health(self) -> ComponentStatus: ...
    async def call(self, tool: ToolName, arguments: JsonDict) -> McpToolResult: ...
    async def close(self) -> None: ...

# src/walk/integrations/errors.py
class McpProtocolError(PermanentError): ...         # JSON-RPC error object, malformed message, version mismatch

# src/walk/runtime/mcp_tools.py
class McpToolHandler:                               # a KernelToolHandler registered for each UNITY_MCP_TOOLS name
    def __init__(self, provider: UnityMcpProvider, evidence: EvidenceManager, runs: AgentRunRepository, cache_dir: Path) -> None: ...
    async def __call__(self, request: ToolCallRequest) -> JsonDict: ...   # {"ok", "text", "evidence_ids"}
```
`tools_mcp.yaml` rows: `name | kind=MCP | provider=unity_mcp | requires_env=[unity_mcp] | cost_dimension=TOOL_CALLS | cost_category=COMPUTE`. `KernelSettings.unity_mcp_command: list[str] | None` (None = provider disabled), `KernelSettings.unity_mcp_tool_map: dict[str, str]` (kernel tool → server tool name; defaults fixed by ADR-0015 for the chosen server).

#### Behavior
1. `McpClient.initialize` sends `initialize` (`protocolVersion`, `capabilities: {}`, `clientInfo: {name: "walk", version}`), awaits the response, sends `notifications/initialized`; a server `protocolVersion` the client does not accept → `McpProtocolError`. Request ids are sequential integers; responses are matched by id; notifications from the server are logged and skipped; no response within `request_timeout_s` → `Timeout`.
2. `call_tool` sends `tools/call {name, arguments}`; JSON-RPC `error` → `McpProtocolError(code, message)`; `result.isError == true` → `McpToolResult(is_error=True, …)` (not an exception); `content` items of type `text` → `text`, type `image` → `images`; other types are ignored with a DEBUG log.
3. `StdioMcpTransport` starts the process with `asyncio.create_subprocess_exec` (cwd = game repo, env = the scrubbed agent env allowlist from E02-S01 plus the variables named in ADR-0015), writes one JSON object per line, reads stdout line by line; process exit → `ProviderUnavailable` on the next receive; `close` terminates the process (kill after 5 s).
4. `UnityMcpProvider.call(tool, arguments)`: `tool` not in `UNITY_MCP_TOOLS` or not in `tool_map` → `NotSupported`; connects lazily (one client per provider, re-created after `ProviderUnavailable`), maps the name, delegates to `call_tool`.
5. `health()`: command not configured → `MISSING`; initialize + `tools/list` succeed and every mapped server tool is listed → `READY` (`version` = server version); some mapped tools absent → `MISCONFIGURED` with the missing names; connection failure → `UNKNOWN`; never raises.
6. Preflight writes `EnvironmentManifest.tools["unity_mcp"]`; `unity_mcp` is a ready env key only when `READY`, so `ToolRegistry.available` hides the MCP tools otherwise (E01-S14 `requires_env`).
7. `ToolInvoker.invoke` accepts `kind in {KERNEL, MCP}` with identical authorise → meter `TOOL_CALLS` → dispatch → `TOOL_INVOKED(phase=post)` → `ON_TOOL_AFTER` semantics (E01-S26 Behavior 2); `PROVIDER_NATIVE`/`CLI` still → `ConfigError`.
8. `McpToolHandler`: calls the provider; each image is decoded and written to `<cache_dir>/<run_id>/<seq>.png` (only `image/png` and `image/jpeg` accepted; other MIME types skipped with a WARNING) and recorded as `EvidenceDraft(kind=SCREENSHOT, description="unity_mcp <tool>", metrics={"tool", "server_tool"})` on the run's work item; returns `{"ok": not is_error, "text": "\n".join(text), "evidence_ids": [...]}`.
9. Permission defaults (`defaults_unity_mcp.yaml`, loaded after the main defaults): ALLOW the three MCP tools for ART_DIRECTOR, DESIGN_LEADER, LEAD_DEV, QC; all other roles fall to default deny. All three tools are read-only; none is a protected action.
10. With `unity_mcp_command = None` nothing is started, no handler is registered, and the kernel behaves exactly as before (regression test via the composition root).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a `FakeMcpTransport` scripted with an initialize response When `initialize` Then requests `initialize` then `notifications/initialized` in order and server info returned | `tests/integrations/unity_mcp/test_client.py::test_initialize_handshake_order` |
| 2 | Given a server answering an unsupported protocol version When `initialize` Then `McpProtocolError` | `tests/integrations/unity_mcp/test_client.py::test_initialize_rejects_unsupported_version` |
| 3 | Given a `tools/call` result with text and a PNG image When `call_tool` Then `McpToolResult` with one text and one image | `tests/integrations/unity_mcp/test_client.py::test_call_tool_parses_content` |
| 4 | Given a JSON-RPC error / `isError: true` When `call_tool` Then `McpProtocolError` / `is_error=True` without exception | `tests/integrations/unity_mcp/test_client.py::test_call_tool_errors` |
| 5 | Given an interleaved server notification and no reply within the timeout When calling Then notification skipped and `Timeout` raised | `tests/integrations/unity_mcp/test_client.py::test_notifications_skipped_and_timeout` |
| 6 | Given a tool map for two of three tools When `call("unity_mcp.console")` unmapped Then `NotSupported`; mapped Then delegated with the server tool name | `tests/integrations/unity_mcp/test_provider.py::test_call_maps_tool_names` |
| 7 | Given no command / all mapped tools listed / one missing When `health` Then `MISSING` / `READY` / `MISCONFIGURED` naming it | `tests/integrations/unity_mcp/test_provider.py::test_health_states` |
| 8 | Given the transport raising `ProviderUnavailable` once When `call` twice Then the second call uses a new client | `tests/integrations/unity_mcp/test_provider.py::test_reconnects_after_unavailable` |
| 9 | Given a READY Unity MCP provider When preflight runs Then `tools["unity_mcp"]` is READY and the MCP tools become available | `tests/integrations/test_preflight_unity_mcp.py::test_preflight_marks_unity_mcp_ready` |
| 10 | Given `tools_mcp.yaml` When loaded with the builtin catalogue Then three MCP tools with provider `unity_mcp` and `requires_env == ["unity_mcp"]` | `tests/tools/test_builtin_tools_mcp.py::test_mcp_tools_declared` |
| 11 | Given default permissions When ART_DIRECTOR / SENIOR_DEV requests `unity_mcp.screenshot` Then ALLOW / DENY | `tests/permissions/test_defaults_unity_mcp.py::test_mcp_tool_permissions_by_role` |
| 12 | Given an MCP tool request and a registered handler When `invoke` Then authorised, `TOOL_CALLS` metered, `TOOL_INVOKED(phase=post)` written; a PROVIDER_NATIVE request still `ConfigError` | `tests/runtime/test_tool_invoker_mcp.py::test_invoke_dispatches_mcp_kind` |
| 13 | Given a screenshot result with one PNG When the handler runs Then the file is written under the cache dir and one `SCREENSHOT` evidence recorded on the run's work item | `tests/runtime/test_mcp_tools.py::test_handler_records_screenshot_evidence` |
| 14 | Given an image with MIME `image/gif` When the handler runs Then skipped with a warning and no evidence | `tests/runtime/test_mcp_tools.py::test_handler_skips_unsupported_mime` |
| 15 | Given `WALK_UNITY_MCP_COMMAND` and a running editor When the live test runs Then `health()` is `READY` and `unity_mcp.console` returns text | `tests/integrations/unity_mcp/test_unity_mcp_live.py::test_unity_mcp_live_console` |

#### Evidence required
- Quality gate output; live test listed as skipped.
- ADR-0015 committed with status `Accepted` (or the story stays `BLOCKED`).
- Owner-run transcript with a real editor: `walk doctor` → `unity_mcp: ready (<server> <version>)`; `uv run pytest -m integration tests/integrations/unity_mcp`.
- Demo without a server: `walk doctor` → `unity_mcp: missing` and `walk run --once` unaffected.

#### Notes
- ADR-0015 exists as `Proposed` (architect, 2026-10-06) with recommendations: in-house stdio client (no new dependency); accepted protocol versions `MCP_ACCEPTED_PROTOCOL_VERSIONS`; no compiled-in server, reference server MCP for Unity pinned at acceptance; kernel tool → `McpToolBinding(tool, fixed_arguments)` so read-only is enforced by fixed operation arguments; server env = scrubbed allowlist only; server `ping` answered, other server requests → `-32601`. On acceptance its Consequences section lists the contract deltas to apply here (`unity_mcp_tool_map: dict[str, McpToolBinding]` replaces `dict[str, str]`). Still `BLOCKING` until the owner accepts it: ADR-0015 decides (a) in-house minimal stdio client (this story's contract; no new dependency) versus the `mcp` Python SDK (new dependency → ADR-0001 amendment, and `client.py` becomes a thin wrapper with the same public names); (b) the default Unity MCP server and its tool names for `unity_mcp_tool_map`; (c) `MCP_PROTOCOL_VERSION` accepted range; (d) the environment variables passed to the server process. Implementation starts only with ADR-0015 `Accepted`.
- ADR-0009 D-6 (MCP deferred to Stage 8 "as an additional `ToolKind.MCP` provider"); ADR-0006 D-1 (single enforcement point) and D-2 (kernel performs side effects — agents never get the MCP connection); ADR-0001 (Unity MCP later).
- ARCHITECTURE §2.3 row "Unity MCP server process and MCP client → `walk/integrations/unity_mcp/`" — applied to ARCHITECTURE §2.3 by the architect 2026-10-06.
- Shared files with E08-S02 (parallel set): `src/walk/integrations/service.py` and `src/walk/cli/composition.py` — wiring-only edits; E08-X01 sequences S08 after S02 if a rebase is undesirable.
- `NEW NAME:` ADR-0015, `McpTransport`, `StdioMcpTransport`, `McpClient`, `McpToolResult`, `MCP_PROTOCOL_VERSION`, `UnityMcpProvider`, `UNITY_MCP_TOOLS`, `McpProtocolError`, `McpToolHandler`, tools `unity_mcp.screenshot`/`unity_mcp.console`/`unity_mcp.inspect_asset`, `tools_mcp.yaml`, `defaults_unity_mcp.yaml`, `load_defaults` extra files, `KernelSettings.unity_mcp_command`/`unity_mcp_tool_map`, `FakeMcpTransport`, manifest key `tools["unity_mcp"]`.
- Commit subject: `feat: add unity mcp provider as mcp tool kind (E08-S08)`.

#### Evidence (filled by implementer)
_pending_

---

### E08-S09 — Epic gate: asset generation → validation → approval (e2e)

**Status:** TODO
**Type:** feat
**Requirements:** §10.4, §10.5, §33, §78, §79, §80, §84, §6.5, §90, §136, §137 (Inv. 4, 9, 10)
**Depends on:** E08-S05, E08-S07
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** QC   **Reviewer role:** LeadDev

#### Goal
One end-to-end scenario with fakes proves Stage 8: a feature that needs art gets an Art Director brief, the kernel generates an asset through `asset.generate` with a fake `AssetProvider`, `FakeUnityProvider.validate_assets` validates it, provenance and evidence are recorded, the fake ART_DIRECTOR rejects then approves, the asset becomes `ApprovedArtifact(kind=ASSET)`, and the feature completes only after `ART_COMPLETE` and `DESIGN_VALIDATED` are set.

#### Scope
- In: `tests/e2e/test_e08_gate.py`; `e08_scenario` fixture and its scripted fake outputs; a small concept image used as the approved `ART_DIRECTION` payload.
- Out: production code (defects → `E08-Bxx` bugfix stories); OpenArt (E08-S03) and Unity MCP (E08-S08) — not on the gate path; real providers and Unity (integration tests of S02/S03/S06/S08).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `tests/e2e/test_e08_gate.py` | create | — |
| `tests/e2e/conftest.py` | modify | `e08_scenario` fixture, `E08Scenario` `(verify: fixture style of e03_scenario/e07_scenario)` |
| `tests/e2e/data/e08/concept.png` | create | — (64×64 PNG, ART_DIRECTION payload) |
| `tests/e2e/data/e08/outputs.yaml` | create | — (scripted `AgentOutput`s per role/run for the fake adapters) |

#### Interface contract
Fixture `e08_scenario(tmp_game_repo) -> E08Scenario` (`WalkModel` in conftest): `handle: KernelHandle`, `feature_id: FeatureId`, `asset_task_id: WorkItemId`, `art_direction_id: ApprovedArtifactId`, `asset_provider: FakeAssetProvider`, `unity: FakeUnityProvider`, `repo: Path`. Built with `build_kernel(settings, overrides=KernelOverrides(model_adapters=[fake-claude/sim, fake-codex/sim], asset_providers={"fake-assets": FakeAssetProvider(credits=10.0)}, unity=FakeUnityProvider(), clock=FakeClock, id_factory=SequentialIdFactory))`; `LocalWorkProvider`; real temporary git repo; `.ai/agents/policies.yaml` enabling `DESIGN_LEADER` and `ART_DIRECTOR`; `KernelSettings.asset_usd_per_credit={"fake-assets": 0.02}`; a PROJECT budget `EXTERNAL_CREDITS=100`; `APR-0001` (`ART_DIRECTION`, payload `concept.png`) approved by USER during setup through `walk artifacts approve`.

#### Behavior
Scenario steps (each a test, executed in order on the fixture's cached state):
1. FEAT-0001 "Zombie brute enemy" is created with label `art`; its `applicable_dimensions` include `ART_COMPLETE` and `DESIGN_VALIDATED` once refreshed.
2. Planning and DISCOVERY run (fake ORCHESTRATOR, fake DESIGN_LEADER); in `DESIGN` the first routed run is ART_DIRECTOR (DESIGN), whose output creates one asset TASK (`model3d`, `reference_artifact_ids=[APR-0001]`, `triangle_budget=20000`) normalised to owner KERNEL / reviewer ART_DIRECTOR; then LEAD_DEV DESIGN raises `design_approved`.
3. The asset task is dispatched to `AssetPipelineStep`: `FakeAssetProvider.generate_calls == 1`, `FakeUnityProvider.validate_calls == 1`, files under `Assets/Generated/<task>/fake-job-0001/` plus `model.fbx.provenance.yaml` committed on the task branch, evidence `PROJECT_DATA`, `LOG`, `SCREENSHOT` recorded, task `READY_FOR_REVIEW`.
4. Fake ART_DIRECTOR review #1 returns `REJECTED` with one RISK finding although validation passed → task `REWORK`; `asset_request.prompt` ends with the revision note.
5. The step regenerates: `generate_calls == 2` with a different request hash; provenance `version == 2`; task `READY_FOR_REVIEW` again.
6. Fake ART_DIRECTOR review #2 returns `APPROVED` → `APR-0002` (`kind=ASSET`, `scope=FEAT-0001`, `approved_by.role=ART_DIRECTOR`, payload = second job's files); `ARTIFACT_APPROVED` once for APR-0002.
7. Integration and QC (fakes) complete the asset task → `ART_COMPLETE` true on FEAT-0001 with `PROJECT_DATA` evidence naming APR-0002.
8. The gameplay story completes; at feature `QC` the first routed run is DESIGN_LEADER REVIEW (`APPROVED`) → `DESIGN_VALIDATED` true; then QC passes and FEAT-0001 is `COMPLETE` (it could not complete before steps 7–8: asserted by attempting `qc_passed` earlier and observing the guard rejection).
9. Cost: exactly two `ASSETS` cost records (`EXTERNAL_CREDITS` quantity 10 each, `cost_usd` 0.2 each); `EXTERNAL_CREDITS` consumed 20 on the PROJECT budget.
10. Replaying `DefaultAssetGenerator.generate` with the approved request returns `reused=True` and `generate_calls` stays 2.
11. `walk assets show Assets/Generated/<task>/fake-job-0002/model.fbx` answers: provider `fake-assets`, concept `APR-0001`, approved by `ART_DIRECTOR` in `APR-0002`, prompt including the revision note.
12. `walk artifacts verify` exits 0; no file under `.ai/approved/` was written outside `approve_artifact` (all `.ai/approved/*.md` have a matching `ARTIFACT_APPROVED` ledger event).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given FEAT-0001 labelled `art` with both optional roles enabled Then `ART_COMPLETE` and `DESIGN_VALIDATED` are applicable | `tests/e2e/test_e08_gate.py::test_art_feature_has_art_and_design_dimensions` |
| 2 | Given the feature in DESIGN Then ART_DIRECTOR runs before LEAD_DEV and creates one normalised asset task referencing APR-0001 | `tests/e2e/test_e08_gate.py::test_art_director_brief_creates_asset_task` |
| 3 | Given the asset task READY Then one fake generation, one fake validation, provenance + three evidence kinds, task READY_FOR_REVIEW | `tests/e2e/test_e08_gate.py::test_asset_generated_validated_and_recorded` |
| 4 | Given review #1 REJECTED on a valid asset Then REWORK and the revision note is in the next prompt | `tests/e2e/test_e08_gate.py::test_art_director_rejects_valid_asset` |
| 5 | Given the rework Then a second generation with a new hash and provenance version 2 | `tests/e2e/test_e08_gate.py::test_rework_regenerates_with_new_request` |
| 6 | Given review #2 APPROVED Then APR-0002 is an APPROVED ASSET scoped to FEAT-0001 approved by ART_DIRECTOR | `tests/e2e/test_e08_gate.py::test_art_director_approval_registers_asset_artifact` |
| 7 | Given the asset task COMPLETE Then `ART_COMPLETE` is true with evidence naming APR-0002 | `tests/e2e/test_e08_gate.py::test_art_complete_dimension_set` |
| 8 | Given feature QC Then DESIGN_LEADER validates first, the feature cannot complete before both dimensions, then completes | `tests/e2e/test_e08_gate.py::test_feature_completes_only_with_art_and_design_dimensions` |
| 9 | Given the run Then two ASSETS cost records totalling 20 credits / 0.4 USD and the PROJECT `EXTERNAL_CREDITS` budget consumed 20 | `tests/e2e/test_e08_gate.py::test_asset_costs_recorded_in_credits_and_usd` |
| 10 | Given a replay of the approved request Then served from the idempotency store without a provider call | `tests/e2e/test_e08_gate.py::test_asset_generation_idempotent_replay` |
| 11 | Given `walk assets show` on the approved asset Then the four §80 answers match the scenario | `tests/e2e/test_e08_gate.py::test_provenance_answers_four_questions` |
| 12 | Given the final repo Then `walk artifacts verify` exits 0 and every approved document has its `ARTIFACT_APPROVED` event | `tests/e2e/test_e08_gate.py::test_approved_registry_consistent` |

#### Evidence required
- Quality gate output including `tests/e2e/test_e08_gate.py` (12 passed).
- Demo transcript on the fixture repo: `walk work show FEAT-0001` (dimensions), `walk artifacts list`, `walk assets show Assets/Generated/TASK-0003/fake-job-0002/model.fbx`, `walk cost --work-item TASK-0003`, `walk ledger query --work-item TASK-0003 --kind EVIDENCE_RECORDED`.

#### Notes
- Gate uses only fakes and a temp repo; no network (DoD). Any production change needed is a separate `bugfix` story; this commit touches tests only.
- Task ids in the demo (`TASK-0003`) depend on `SequentialIdFactory` ordering; the test reads ids from `E08Scenario`, never hard-codes them.
- WBS §4 E08 epic gate text is the authority for the scenario; steps 8–12 strengthen it with §6.5, §84, §90 and Inv. 10 checks.
- Commit subject: `feat: add epic 08 gate test for asset pipeline (E08-S09)`.

#### Evidence (filled by implementer)
_pending_

---

### E08-R01 — Review E08

**Status:** TODO
**Type:** docs
**Requirements:** §137 (Inv. 4, 7, 9, 10, 11), §33, §78–§80, §6.5
**Depends on:** E08-S09
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
An independent agent instance (different model than the E08 implementer where possible, §23) verifies every E08 story against the Definition of Done, the SDK-confinement and secret rules for asset providers, and Invariants 4, 7, 9, 10, recording defects as `bugfix` stories.

#### Scope
- In: stories E08-S01…S09 and their commits; `INTERFACES.md`/`DOMAIN-MODEL.md`/ADR-0015 deltas; WBS §6 register entries from this epic; architecture tests added by the reviewer.
- Out: fixing defects (each becomes `E08-Bxx`); E09 files (parallel epic, reviewed by E09-R01).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-08-art-design.md` | modify | — (review record appended; `E08-Bxx` stories appended if any) |
| `docs/02-work-breakdown/WBS.md` | modify | — (status rows, §6 register) |
| `docs/01-architecture/INTERFACES.md`, `docs/01-architecture/DOMAIN-MODEL.md`, `docs/01-architecture/adr/ADR-0015-unity-mcp-provider.md` | modify (only if drift found) | — |
| `tests/architecture/test_asset_sdk_confinement.py` | create | — |
| `tests/architecture/test_asset_secrets.py` | create | — |

#### Interface contract
Reviewer protocol, IMPLEMENTATION-PROTOCOL.md "Reviewer protocol" steps 1–5.

#### Behavior
1. For each story: `git show <sha>`; Files table == changed files (extra files need commit-body justification; the composition-root, `integrations/service.py` and `pyproject.toml` overlaps declared in this file are accepted); every acceptance-criterion test exists and passes; coverage ≥ 90 % for touched modules; integration tests are marked and skipped by default.
2. SDK confinement (ARCHITECTURE §2.3 as amended by the `RELOCATE:` rows): `httpx` imported only under `walk/integrations/jira/` and `walk/integrations/assets/`; MCP subprocess started only under `walk/integrations/unity_mcp/`; `yaml` under `walk/integrations/` only in `assets/`.
3. Secrets (§91, ADR-0009 D-8): `MESHY_API_KEY`/`OPENART_API_KEY` read only via `CredentialStore`; no provenance file, evidence, ledger payload or log fixture contains a value matching the kernel secret patterns.
4. Invariant 4: no asset task has `reviewer_role == implementer_role`; the gate's ledger shows `KERNEL` as implementer and `ART_DIRECTOR` as reviewer.
5. Invariant 7/§31: `asset.generate`, `art.*` and `unity_mcp.*` calls all pass through `ToolInvoker` (grep for direct handler invocation outside `asset_step.py` and tests).
6. Invariant 9: the asset code writes no SQL against `ledger_events`/`cost_records` other than through `LedgerManager`/`CostManager`.
7. Invariant 10: `.ai/approved/` is written only by `approve_artifact`; ART_DIRECTOR cannot approve `ART_DIRECTION` (E08-S01 test present and green).
8. `NEW NAME:`/`RELOCATE:` items of E08 are present in WBS §6 or listed in the review note for the architect; ADR-0015 status is `Accepted`.
9. Defects → `E08-Bxx` stories using the template; commit `docs: review epic 08 stories E08-S01..S09 (E08-R01)`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given each E08 story When the DoD checklist is applied Then every box is checked or an `E08-Bxx` story exists | manual checklist recorded in Evidence |
| 2 | Given `src/walk` When imports are parsed Then `httpx` appears only under `integrations/jira` and `integrations/assets`, and `yaml` under `integrations` only in `integrations/assets` | `tests/architecture/test_asset_sdk_confinement.py::test_httpx_and_yaml_confined` |
| 3 | Given `src/walk` When grepping for `MESHY_API_KEY`/`OPENART_API_KEY` Then only `integrations/credentials.py` and the two provider modules reference them, the providers only through `CredentialStore.get` | `tests/architecture/test_asset_secrets.py::test_asset_credentials_only_via_credential_store` |
| 4 | Given the gate scenario ledger When asset-task transitions are read Then implementer `KERNEL` and reviewer `ART_DIRECTOR` on every review | manual checklist recorded in Evidence |
| 5 | Given the quality gate on `main` Then green with overall coverage ≥ 85 % | manual checklist recorded in Evidence |

#### Evidence required
- Checklist per story (ID → DoD items → OK/defect id).
- Quality gate output on `main` after the review commit.
- List of `E08-Bxx` stories created (or "none").
- Demo: `walk doctor` on the gate fixture repo (asset providers, Unity MCP and ART_DIRECTOR lines) and `walk artifacts list`.

#### Notes
- Tests 2–3 are architecture tests created by the reviewer (review tasks may add tests, never production code).
- E08-R01 and E09-R01 may run concurrently (different epics, disjoint files); E11-X01 waits for both (WBS §5).
- Commit subject: `docs: review epic 08 stories E08-S01..S09 (E08-R01)`.

#### Evidence (filled by implementer)
_pending_

---

