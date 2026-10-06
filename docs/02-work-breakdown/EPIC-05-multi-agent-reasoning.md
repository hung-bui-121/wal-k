# EPIC-05 — Multi-Agent Reasoning

**Roadmap stage:** §135 Stage 5
**Goal.** Constitutions with professional bias drive debates, authority and escalation; the PO resolves what agents cannot; every accepted decision is persisted and the §133 debate test passes with fake adapters producing scripted positions.
**Requirements.** §6.7, §6.9, §10.2, §10.4, §12 (full), §44–§47, §50–§51, §93 (decisions override), §127 (optional roles), §133, §137 (Inv. 5, 7), §138 (Infinite Debate, Over-Engineering).
**Epic gate.** `tests/e2e/test_e05_gate.py` (§133): a feature requirement is challenged by fake LEAD_DEV (`REJECTED` with `debate_position`); a `Debate` opens with LEAD_DEV + DESIGN_LEADER (or ORCHESTRATOR), two rounds without consensus escalate to PO, PO resolves, `Decision` is `ACCEPTED`, persisted in SQLite and `.ai/decisions/DEC-NNNN.md`, linked to the feature context.
**Branching.** `story/<ID>-<slug>` + worktree per story (COMMIT-POLICY §4); merge `--no-ff` after E05-R01.
**Preconditions.** E01-R01…E04-R01 `DONE` with no `BLOCKER` bugfix stories; `main` green; E05-X01 committed before any E05 story starts (WBS §2 rule 3).

## Story index

| ID | Title | Depends on | Effort |
|---|---|---|---|
| E05-X01 | Refine E05 against codebase | E04-R01 | LOW |
| E05-S01 | `DecisionManager.propose/classify_autonomy/escalate/override` | E05-X01, E04-S05 | HIGH |
| E05-S02 | `Orchestrator.handle_escalation` routing (L1 debate, L2 PO run, L3 user approval) | E05-S01, E02-S11 | MEDIUM |
| E05-S03 | `DebateManager` and `debate_workflow` table | E05-S01 | HIGH |
| E05-S04 | Debate runs and `DebatePosition` output (incl. `agrees_with_role`) | E05-S03, E03-S07 | HIGH |
| E05-S05 | Debate escalation PO → USER, round and budget limits | E05-S04, E05-S02 | MEDIUM |
| E05-S06 | PRODUCT_OWNER and DESIGN_LEADER constitutions and policies | E05-X01, E03-S06 | MEDIUM |
| E05-S07 | Constitution schema enforcement: narrowing merge, provider-name lint, section rendering | E05-S06 | MEDIUM |
| E05-S08 | Conflict detection → debate opening from review/design disagreement | E05-S04, E03-S13 | MEDIUM |
| E05-S09 | `walk debates list/show`, `walk decisions override` | E05-S03, E05-S01 | LOW |
| E05-S10 | Epic gate: §133 debate test (e2e) | E05-S05, E05-S07, E05-S08, E05-S09 | MEDIUM |
| E05-R01 | Review E05 | E05-S10 | MEDIUM |

## Reading order for implementers

1. `WBS.md` §2–§3 (rules; §3.4 payload keys, §3.5 ledger vs hooks, §3.6 fakes, §3.9 templates).
2. ADR-0013 (constitution schema, D-3 rendering, D-4 narrowing, D-5 lint), ADR-0006 (authority in `OutputApplier`, D-4 approvals), ADR-0010 D-3/D-4 (`DebateState`, `debate_workflow` as data), ADR-0003 (decision documents).
3. `INTERFACES.md` §1.1 `Orchestrator.handle_escalation`, §1.2, §1.9 (`DecisionManager`, `DebateManager`), §1.10, §3.5 (`debate_workflow v1.0`), §4 (DEBATE rows), §5.1.
4. `DOMAIN-MODEL.md` §3 (`DecisionCategory`, `DecisionStatus`, `AutonomyLevel`, `DebateState`), §4.2 (`Constitution`, `AgentOutput.decisions/escalations/debate_position`), §4.8, §6.2 (`decisions`, `debates`, `debate_positions`, `escalations`).
5. `ARCHITECTURE.md` §4.1 rows `ON_DEBATE_*`, `ON_DECISION_RECORDED`, `ON_ESCALATION`; §4.3 write points `debate.DebateManager`, `decisions.DecisionManager`; §5.5 (debate circuit breaker); §7 Inv. 5, 7.
6. Existing E04-S05 `walk.decisions` service (the `NotSupported("E05-S01")`/`("E05-S03")` stubs this epic replaces).

Parallel sets (WBS §8): `{S01→S02} ∥ {S06→S07}`; `{S03→S04→S05} ∥ {S09}`.

Planning decisions fixed for this epic (Autonomy Level 0 unless marked `NEW NAME:`):
- Debate budgets use `BudgetScope.TASK` with `scope_id = <DebateId>` (dimensions `REVIEW_LOOPS` = `max_rounds`, `COST_USD` = `DebatePolicy.cost_usd`); no new `BudgetScope` member.
- Debate guards are registered through `walk.workflow.guards.register_guard` from `walk.debate.guards` (debate may import workflow); the `debate_workflow.yaml` table lives with the other tables under `src/walk/workflow/tables/` and is loaded by the E01-S11 generic engine with `DebateState`.
- Debate runs are scheduled against the debate's `work_item_id`; a debate without a work item is never auto-scheduled (only resolvable by USER via approval).
- `record()` accepts `by.role == KERNEL` only when `decision.debate_id` is set (debate resolution path); any other KERNEL record is `AuthorityViolation`.
- Optional roles are "enabled" when `RuntimePolicy.enabled` is true (`NEW NAME:` field, default `True`; kernel defaults ship PO and DESIGN_LEADER with `enabled: false`); `AgentManager.list_roles()` returns enabled roles with a constitution.

---

### E05-X01 — Refine E05 against codebase

**Status:** TODO
**Type:** docs
**Requirements:** §135 (Stage 5), §58 (Definition of Ready applied to stories)
**Depends on:** E04-R01
**Effort:** LOW   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
Every E05 story's Files table, interface references and dependencies are re-validated against the `src/walk/` tree and `INTERFACES.md` as they exist after E04-R01, and the corrected epic file is committed before any E05 story starts.

#### Scope
- In: this file (`EPIC-05-multi-agent-reasoning.md`), `WBS.md` §5 rows for E05, `WBS.md` §6 register entries introduced by E05.
- Out: changing story IDs, titles, dependencies or effort (fixed by WBS §4); writing code.

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-05-multi-agent-reasoning.md` | modify | — |
| `docs/02-work-breakdown/WBS.md` | modify | — (§5 status row E05-X01; §6 register additions) |

#### Interface contract
Checklist applied to every story E05-S01…S10 and E05-R01:
1. Every path in the Files table marked `modify` exists in `src/walk/` or `tests/`; every path marked `create` does not exist and is not created by an earlier story.
2. Every `INTERFACES.md §x.y` / `DOMAIN-MODEL.md §x.y` reference resolves to a section that still defines the named symbol with the signature quoted in the story.
3. Every `Depends on` ID is `DONE` in `WBS.md` §5 (or belongs to E05 and precedes the story).
4. Every symbol the story calls (`DefaultDecisionManager`, `AuthorityResolver`, `AuthorityViolation`, `DECISION_SECTIONS`, `DefaultOutputApplier`, `DefaultOrchestrator`, `Scheduler`, `TaskRouter`, `BuiltinHookDeps`, `ApprovalWaiter`, `ConstitutionLoader`, `PolicyLoader`, `TableLoader`, generic `StateMachine`, `tests/fakes/fake_model_adapter.py::FakeModelAdapter`, `tests/e2e/conftest.py` fixtures) exists under the name used here; otherwise the story is corrected to the real name.
5. Specifically verify (these were planned from WBS §3 and architecture docs because `EPIC-01` S18–S31 and `EPIC-03` S06–S20 story bodies were not yet written at planning time): `src/walk/debate/models.py` + `__init__.py` exist (created by E01-S18 for `AgentInput.debate`); `src/walk/agents/templates/DEBATE.md.j2` exists (E01-S18); `src/walk/orchestrator/{service,scheduler,router,commands}.py` module names (E01-S29/S30); `src/walk/runtime/applier.py` (E01-S27); the E01-S11 generic state-machine constructor signature used for `DebateState`.

#### Behavior
1. For each checklist failure the planner edits the story in place (path, symbol or reference) and records the change in a `Refinement log` list appended to this story's Evidence section (`<story id>: <old> → <new>`).
2. A story that cannot be made ready without an architecture change is marked `BLOCKED` with a `BLOCKING:` note naming the missing name/decision, and the corresponding `NEW NAME:` line is added to `WBS.md` §6.
3. Nothing outside `docs/02-work-breakdown/` is modified.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given every E05 story When the Files tables are checked Then every `modify` path exists in the repo and every `create` path is absent | manual check recorded in Evidence (no automated test; docs task) |
| 2 | Given every E05 story When each `INTERFACES.md`/`DOMAIN-MODEL.md` reference is opened Then the referenced symbol and signature exist | manual check recorded in Evidence |
| 3 | Given every E05 story When its `Depends on` list is compared with `WBS.md` §5 Then every dependency outside E05 is `DONE` | manual check recorded in Evidence |
| 4 | Given the refined file When `grep -c "^### E05-"` Then 12 headings (X01, S01…S10, R01) and no ID renamed | manual check recorded in Evidence |

#### Evidence required
- Refinement log (list of corrections, or "no corrections").
- `git diff --stat` of the commit (only `docs/02-work-breakdown/` files).

#### Notes
- WBS §1 (`Exx-Xyy` refine task), §2 rule 3.
- Commit subject: `docs: refine epic 05 stories (E05-X01)`.

#### Evidence (filled by implementer)
_pending_

---

### E05-S01 — `DecisionManager.propose/classify_autonomy/escalate/override`

**Status:** TODO
**Type:** feat
**Requirements:** §44, §50, §51, §6.9, §6.10, §93, §137 (Inv. 5, 7)
**Depends on:** E05-X01, E04-S05
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Agent decision proposals are classified into §51 autonomy levels bounded by the proposer's authority and the project's `autonomy_level_max`; Level 0 proposals become ACCEPTED decisions, higher levels become persisted `Escalation`s, and the user can override any accepted decision — replacing the E04-S05 `NotSupported` stubs.

#### Scope
- In: `classify_autonomy`, `propose`, `escalate`, `override`, `EscalationRepository`, `LEVEL3_CONDITIONS`, `OutputApplier` wiring of `AgentOutput.decisions` and `AgentOutput.escalations`.
- Out: routing of escalations (E05-S02); `record()` for debate-sourced decisions (E05-S03); CLI (E05-S09).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/decisions/service.py` | modify | `DefaultDecisionManager.propose`, `.classify_autonomy`, `.escalate`, `.override` |
| `src/walk/decisions/repository.py` | modify | `EscalationRepository`, `DecisionRepository.by_status`, `DecisionRepository.latest_version` |
| `src/walk/decisions/autonomy.py` | create | `LEVEL3_CONDITIONS`, `classify`, `matches_condition` |
| `src/walk/decisions/protocols.py` | modify | `EscalationSink` |
| `src/walk/decisions/__init__.py` | modify | re-exports |
| `src/walk/runtime/applier.py` | modify | — (`DefaultOutputApplier` calls `propose` per `output.decisions`, `escalate` per `output.escalations`; fills `AppliedEffects.decision_ids/escalation_ids`) |
| `src/walk/cli/composition.py` | modify | — (injects `project_autonomy_max` resolver and `EscalationSink` into `DefaultDecisionManager`) |
| `tests/decisions/test_autonomy.py` | create | — |
| `tests/decisions/test_service_propose.py` | create | — |
| `tests/decisions/test_service_override.py` | create | — |
| `tests/runtime/test_applier_decisions.py` | create | — |

#### Interface contract
Protocol methods: `INTERFACES.md §1.9 DecisionManager.propose/escalate/override/classify_autonomy` verbatim. Deltas:
```python
# src/walk/decisions/autonomy.py
LEVEL3_CONDITIONS: tuple[str, ...] = ("core gameplay change", "monetization", "major feature removal", "large scope increase",
                                      "major art direction change", "major schedule impact", "phase gate")      # §51 Level 3 list
def matches_condition(condition: str, *texts: str) -> bool:
    """True when every word of `condition` (lower-cased, len >= 3) occurs in the concatenation of `texts` (lower-cased)."""
def classify(proposal: DecisionProposal, authority: Authority, rules: list[EscalationRule], project_max: AutonomyLevel) -> AutonomyLevel:
    """level = proposal.autonomy_level;
    for rule in rules: if (rule.category is None or rule.category == proposal.category) and matches_condition(rule.condition, topic, position): level = max(level, rule.to_level)
    if any(matches_condition(c, topic, position) for c in LEVEL3_CONDITIONS): level = USER
    if proposal.category not in authority.decision_scope: level = max(level, MULTI_AGENT)
    if level > authority.max_autonomy_level and level == LOCAL: level = MULTI_AGENT        # cannot self-resolve
    if level > project_max and level < USER: level = USER                                   # Project.autonomy_level_max (§140)
    return level"""

# src/walk/decisions/protocols.py
class EscalationSink(Protocol):
    """Implemented by walk.orchestrator (handle_escalation); injected so decisions stays below orchestrator."""
    async def __call__(self, escalation: Escalation) -> None: ...

# src/walk/decisions/repository.py
class EscalationRepository(Repository[Escalation]):     # table escalations
    async def open_for_item(self, work_item_id: WorkItemId) -> list[Escalation]: ...   # resolved_decision_id IS NULL
    async def set_approval(self, escalation_id: str, approval_request_id: ApprovalRequestId) -> None: ...
    async def resolve(self, escalation_id: str, decision_id: DecisionId) -> None: ...

# src/walk/decisions/service.py
class DefaultDecisionManager:
    def __init__(self, repo: DecisionRepository, escalations: EscalationRepository, memory: MemoryManager, ledger: LedgerManager,
                 hooks: HookManager, ids: IdFactory, clock: Clock, authority_for: AuthorityResolver, workflow: WorkflowManager,
                 project_autonomy_max: Callable[[], AutonomyLevel], sink: EscalationSink | None) -> None: ...
```

#### Behavior
1. `classify_autonomy(proposal, authority, rules)` delegates to `autonomy.classify(..., project_autonomy_max())`; it is pure apart from that resolver.
2. `propose(proposal, by, work_item_id)`: allocates `DEC-NNNN`, persists `Decision(status=PROPOSED, owner=by.role, autonomy_level=<classified>, participants=[by.role], positions=[DecisionPosition(role=by.role, model_id=by.model_id, position=proposal.position, confidence=1.0)], related_work_items=[work_item_id] if given)`; writes no `.ai/` document for PROPOSED decisions (only ACCEPTED ones are documents, Inv. 8).
3. If the classified level is `LOCAL` → `record(decision, by=by)` in the same call; the returned decision is `ACCEPTED`.
4. Otherwise `escalate(EscalationRequest(to_level=level, category, question=f"{topic}: {position}", options=[position, *alternatives], recommendation=position, evidence_ids), from_role=by.role, work_item_id, run_id=by.run_id)` is called and the PROPOSED decision is returned; the escalation's ledger payload carries `proposal_decision_id`.
5. `escalate(request, from_role, work_item_id, run_id)`: id `ESC-<ULID>` (`new_ulid`), row in `escalations`, ledger `ESCALATION_RAISED{to_level, category, question, proposal_decision_id?}` (write point `decisions.DecisionManager`), fires `ON_ESCALATION` with payload `{"escalation_id", "to_level", "category", "work_item_id"}`, then awaits `sink(escalation)` when a sink is configured (E05-S02 supplies it; `None` in unit tests).
6. `override(decision_id, outcome, rationale)`: the target must be `ACCEPTED` (else `PermanentError("only accepted decisions can be overridden")`); in one `UnitOfWork`: target `status=OVERRIDDEN`, `overridden_by_user_at=now`; new `Decision` with new id, `version = target.version + 1`, `supersedes = target.id`, `owner=USER`, `outcome`, `rationale`, same category/topic/participants/positions/affected_systems/related_work_items, `autonomy_level=USER` → `record(new, by=Actor(role=USER))`; ledger `USER_OVERRIDE{command: "decisions.override", decision_id, new_decision_id}`; the superseded document is rewritten with `status: OVERRIDDEN` through `MemoryManager.write`.
7. `relevant_for` (E04-S05) now also excludes `OVERRIDDEN` decisions.
8. `DefaultOutputApplier.apply`: for each `output.decisions` → `propose(p, by=Actor(run.role, run.model_id, run.id), work_item_id=run.work_item_id)`; for each `output.escalations` → `escalate(...)`; ids collected into `AppliedEffects`; a `AuthorityViolation` from `propose` is converted into a `Finding(severity="RISK")` on the run and does not fail the run.
9. A proposal from a role without a constitution-backed authority (`authority_for` raises `ConstitutionError`) is treated as `Authority()` (empty scope, `max_autonomy_level=LOCAL`) → escalates at Level 1.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given LEAD_DEV authority (`scope=[TECH]`, max 1) and a TECH proposal at level 0 with no matching rule When classified Then `LOCAL` | `tests/decisions/test_autonomy.py::test_in_scope_level0_stays_local` |
| 2 | Given the same authority and a DESIGN proposal When classified Then `MULTI_AGENT` | `tests/decisions/test_autonomy.py::test_out_of_scope_raises_to_multi_agent` |
| 3 | Given rule `{condition: "core architecture migration", to_level: 3}` and topic "core architecture migration to ECS" When classified Then `USER` | `tests/decisions/test_autonomy.py::test_escalation_rule_matches_condition_words` |
| 4 | Given topic containing "monetization" When classified Then `USER` regardless of authority | `tests/decisions/test_autonomy.py::test_level3_list_forces_user` |
| 5 | Given `project_max=MULTI_AGENT` and classified `PO` When classified Then `USER` | `tests/decisions/test_autonomy.py::test_project_autonomy_max_caps_to_user` |
| 6 | Given `matches_condition("major art direction change", "Minor tweak")` Then False; with "major change to art direction" Then True | `tests/decisions/test_autonomy.py::test_matches_condition_word_based` |
| 7 | Given LEAD_DEV proposing an in-scope TECH decision When `propose` Then returned decision `ACCEPTED`, `DEC-0001.md` exists, `DECISION_RECORDED` written, no escalation row | `tests/decisions/test_service_propose.py::test_propose_level0_records_immediately` |
| 8 | Given SENIOR_DEV proposing a TECH decision When `propose` Then decision `PROPOSED`, one `escalations` row with `to_level=1`, `ESCALATION_RAISED` payload has `proposal_decision_id`, `ON_ESCALATION` fired once, no `.ai/decisions/` file | `tests/decisions/test_service_propose.py::test_propose_escalates_and_keeps_proposed` |
| 9 | Given a sink When `escalate` Then the sink receives the persisted `Escalation` after the ledger event | `tests/decisions/test_service_propose.py::test_escalate_calls_sink_after_persist` |
| 10 | Given `authority_for` raising `ConstitutionError` When `propose` Then escalated at level 1 | `tests/decisions/test_service_propose.py::test_unknown_authority_escalates` |
| 11 | Given ACCEPTED `DEC-0001` When `override("DEC-0001", "Use addressables", "cost")` Then `DEC-0001` OVERRIDDEN with timestamp, `DEC-0002` ACCEPTED version 2 `supersedes=DEC-0001` owner USER, `USER_OVERRIDE` ledger, both documents on disk with matching statuses | `tests/decisions/test_service_override.py::test_override_supersedes_and_logs` |
| 12 | Given a PROPOSED decision When `override` Then `PermanentError` and nothing written | `tests/decisions/test_service_override.py::test_override_requires_accepted` |
| 13 | Given OVERRIDDEN and ACCEPTED decisions on FEAT-0001 When `relevant_for` Then only the ACCEPTED one | `tests/decisions/test_service_override.py::test_relevant_for_excludes_overridden` |
| 14 | Given a fake LEAD_DEV output with 1 Level-0 decision and 1 escalation When applied Then `AppliedEffects.decision_ids == ["DEC-0001"]`, `escalation_ids` has one id | `tests/runtime/test_applier_decisions.py::test_applier_proposes_and_escalates` |
| 15 | Given a fake QC output proposing a TECH decision (out of scope) When applied Then run not failed, decision PROPOSED, escalation created | `tests/runtime/test_applier_decisions.py::test_applier_out_of_scope_proposal_escalates_not_fails` |

#### Evidence required
- Quality gate output.
- Demo: `walk decisions list --json` after a test run showing one `ACCEPTED` and one `PROPOSED` row; `walk ledger query --kind ESCALATION_RAISED --json` showing `payload.to_level == 1`.

#### Notes
- Invariant 5: `AgentOutput.decisions` never reach `ACCEPTED` without passing `classify` → `record`; Invariant 7: `Project.autonomy_level_max` is consulted on every classification.
- `NEW NAME:` `walk.decisions.autonomy` (`LEVEL3_CONDITIONS`, `classify`, `matches_condition`), `EscalationSink`, `EscalationRepository`, `DecisionRepository.by_status/latest_version`, escalation id format `ESC-<ULID>` (DOMAIN-MODEL §2 has no row for `Escalation.id`), `USER_OVERRIDE` write point extended to `decisions.DecisionManager.override` (ARCHITECTURE §4.3 lists `orchestrator.PhaseGate` only).
- Pitfall: `propose` must allocate the id before `classify` so the ledger payload can reference it even when the decision stays PROPOSED.
- Commit subject: `feat: add decision proposals, autonomy classification and override (E05-S01)`.

#### Evidence (filled by implementer)
_pending_

---
