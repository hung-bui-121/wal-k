# WAL-K Interfaces

**Status:** Draft v1. Companion to `ARCHITECTURE.md` and `DOMAIN-MODEL.md`. Spec citations `§NN` refer to `requirements/WAL_K_REQ.md`.

Every §125 service is a `typing.Protocol` in `src/walk/<package>/protocols.py`; the default implementation is `src/walk/<package>/service.py`. All I/O methods are `async`. Models referenced here are defined in `DOMAIN-MODEL.md` and are assumed imported. Signatures are normative; docstrings state contracts (pre/post-conditions, ledger events, hooks).

---

## 1. Kernel services (§125)

### 1.1 `walk.orchestrator.protocols`

```python
from typing import Protocol, AsyncIterator


class Orchestrator(Protocol):
    """§10.1, §56, §67–§72, §93. Owns the scheduling loop and phase gates. Hosted by walk.orchestrator."""

    async def start(self) -> None:
        """Run startup sequence (ARCHITECTURE.md §3.4) and enter the scheduling loop until `stop()`."""

    async def stop(self, *, drain: bool = True) -> None:
        """Checkpoint and pause all running agents (drain=True waits for a checkpoint boundary), release lock."""

    async def wake(self) -> None:
        """Signal the scheduler to run a tick now (called by webhook ingest, run completion, commands)."""

    async def tick(self) -> int:
        """One scheduling pass: admit ready work (INTERFACES §5.1), returns number of runs started."""

    async def submit_feature(self, title: str, description: str, gdd_refs: list[GddRef]) -> Feature:
        """§131 'User Feature' entry: creates Feature(IDEA) and a PLAN run for ORCHESTRATOR role."""

    async def plan_phase(self, phase_id: PhaseId) -> list[WorkItem]:
        """[Stage 6] GDD compiler output → epics/features/stories within phase scope (§48, §52)."""

    async def start_phase(self, phase_id: PhaseId) -> Phase:
        """PLANNED → ACTIVE. Requires user GO on previous phase or project start. Fires ON_PHASE_START."""

    async def request_phase_review(self, phase_id: PhaseId) -> PhaseEvidencePackage:
        """ACTIVE → EVIDENCE_REVIEW → USER_GATE. Builds evidence package (§69), retrospective (§115)."""

    async def decide_phase(
        self, phase_id: PhaseId, decision: PhaseDecision, feedback: str | None, actor: str
    ) -> Phase:
        """§70. USER only. GO→COMPLETE(+ next ACTIVE); REWORK→REWORK (feedback → work items §71);
        CHANGE→CHANGE_ANALYSIS (impact analysis §72); STOP→STOPPED + project paused. Ledger PHASE_GATE_DECISION."""

    async def handle_escalation(self, escalation: Escalation) -> None:
        """Route per AutonomyLevel: 1→DebateManager.open, 2→PO run, 3→ApprovalRequest(USER) (§50–§51)."""

    async def pause(self, run_id: RunId | None = None) -> None:
        """§93 Pause Project / Pause Agent. Checkpoint(PAUSE) then state PAUSED_BY_USER."""

    async def resume(self, run_id: RunId | None = None) -> None: ...

    async def cancel_work_item(self, work_item_id: WorkItemId, reason: str) -> None:
        """§93 Cancel Task: cancel run, state CANCELLED, remove worktree."""

    async def force_review(self, work_item_id: WorkItemId) -> None:
        """§93: raise event `force_review` → READY_FOR_REVIEW regardless of current implementer state."""

    def status(self) -> "KernelStatus":
        """§87 dashboard snapshot (current phase, active runs, blocked items, pending approvals, budgets)."""


class TaskRouter(Protocol):
    """§10.1 'assign role', §29 required skills. Hosted by walk.orchestrator."""

    def route(self, item: WorkItem, state: WorkItemState) -> "RouteDecision":
        """Pure function of (kind, state, contract.owner_role/reviewer_role) per table INTERFACES §5.2.
        Returns role + purpose + TaskProfile. Never returns the role of `item.assigned_run_id`'s implementer
        for REVIEW/QC purposes (Invariant 4)."""

    def can_run_parallel(self, a: WorkItem, b: WorkItem) -> bool:
        """§60: false if dependency edge, same feature with overlapping relevant_files, or same branch."""
```

```python
class RouteDecision(FrozenModel):
    role: AgentRole
    purpose: Literal[
        "IMPLEMENT", "DESIGN", "REVIEW", "QC", "TRIAGE", "DEBATE", "PLAN", "ANALYSIS", "RETRO"
    ]
    profile: TaskProfile
    cross_model_review: bool


class KernelStatus(FrozenModel):
    project_key: ProjectKey
    paused: bool
    current_phase: Phase | None
    phase_progress: dict[WorkItemState, int]
    gdd_coverage: dict[str, float]
    active_runs: list[AgentRun]
    blocked_items: list[WorkItemId]
    pending_approvals: list[ApprovalRequest]
    open_debates: list[DebateId]
    model_usage: dict[ModelId, UsageReport]
    qc_status: dict[str, int]
    build_status: str | None
    budgets: list[Budget]
    open_improvement_candidates: int
```

### 1.2 `walk.agents.protocols`

```python
class AgentManager(Protocol):
    """§8 role loading, constitution loading, agent lifecycle metadata. Hosted by walk.agents."""

    def load_constitution(self, role: AgentRole) -> Constitution:
        """Kernel default merged with `.ai/agents/roles/<role>.md` override (ADR-0013). Cached per process."""

    def load_runtime_policy(self, role: AgentRole) -> RuntimePolicy:
        """Kernel default merged with `.ai/agents/policies.yaml`."""

    async def instantiate(
        self,
        role: AgentRole,
        item: WorkItem,
        model_id: ModelId,
        effort: Effort,
        budget_ids: list[str],
        available_env_keys: set[str],
    ) -> AgentInstance:
        """§9 assembly (the caller passes RoutingDecision.model_id/effort so agents stays below model_router).
        Merges constitution.tool_permissions into PermissionManager.rules_for(role, extra=…). Validates required skills/tools
        available (§29) else raises ConfigError."""

    def render_instructions(self, agent: AgentInstance, item: WorkItem, purpose: str) -> str:
        """Render versioned task prompt template `walk/agents/templates/<purpose>.md.j2` (BehaviorVersion kind=PROMPT)."""

    def list_roles(self) -> list[AgentRole]: ...
```

### 1.3 `walk.workflow.protocols`

```python
type GuardSubject = WorkItem | Phase | ReleaseCandidate  # phase/RC tables share the guard registry


class Guard(Protocol):
    """Pure predicate used in TransitionTable rows."""

    def __call__(self, item: GuardSubject, ctx: "TransitionContext") -> "GuardResult": ...


class TransitionContext(FrozenModel):
    actor_role: AgentRole
    source: TransitionSource
    run_id: RunId | None = None
    payload: JsonDict = Field(default_factory=dict)
    phase: Phase | None = None


class GuardResult(FrozenModel):
    ok: bool
    reason: str = ""


class Transition[S: StrEnum](FrozenModel):  # S = WorkItemState | PhaseState | ReleaseCandidateState
    from_state: S | Literal["*"]  # "*" = any state not in excluded_states
    excluded_states: tuple[S, ...] = ()  # YAML "* except A,B"
    event: str
    to_state: S | Literal["PREVIOUS", "CHILDREN_READY_FOR_REVIEW"]  # PREVIOUS = payload resume_state
    # (unblock); CHILDREN_READY_FOR_REVIEW = state unchanged, effect force_children_review moves the children
    guards: tuple[str, ...]  # guard names (registered callables)
    allowed_roles: tuple[AgentRole, ...]  # USER may raise any event; guards still apply (§6)
    hooks: tuple[HookName, ...]  # fired after commit, in order
    effects: tuple[str, ...] = ()  # increment_fix_loops | increment_reopen_count | store_resume_state |
    # force_children_review | increment_gate_round | next_release_candidate

    def applies_to(self, state: S) -> bool: ...


class TransitionTable[S: StrEnum](FrozenModel):
    """BehaviorVersion kind=WORKFLOW, name in {'feature_workflow','story_workflow','bug_workflow','phase_workflow','rc_workflow'}."""

    name: str
    version: str
    kinds: tuple[WorkItemKind, ...] = ()  # work-item kinds the table governs (none for phase/RC)
    transitions: tuple[Transition[S], ...]


class WorkflowManager(Protocol):
    """§53–§54 explicit, persisted state machine. Hosted by walk.workflow."""

    def table_for(self, kind: WorkItemKind) -> TransitionTable[WorkItemState]: ...

    async def create(
        self, draft: WorkItemDraft | BugDraft, *, actor: AgentRole, phase_id: PhaseId | None
    ) -> WorkItem:
        """Allocates id (id_sequences), persists, ledger WORK_ITEM_CREATED; does NOT call WorkProvider (OutputApplier does)."""

    async def get(self, work_item_id: WorkItemId) -> WorkItem: ...

    async def query(
        self,
        *,
        states: list[WorkItemState] | None = None,
        kinds: list[WorkItemKind] | None = None,
        phase_id: PhaseId | None = None,
        parent_id: WorkItemId | None = None,
    ) -> list[WorkItem]: ...

    async def raise_event(
        self, work_item_id: WorkItemId, event: str, ctx: TransitionContext
    ) -> WorkItemTransition:
        """Finds the Transition for (item.state, event); evaluates guards; checks actor_role ∈ allowed_roles;
        in ONE transaction: update state + state_version, insert work_item_transitions row, ledger WORK_ITEM_TRANSITION;
        then fires ON_STATE_TRANSITION and the transition's hooks. Raises GuardRejected / PermissionDenied."""

    # Open (E03-S03): WorkProviderEvent is defined in walk.integrations, which walk.workflow may not
    # import (ARCHITECTURE §2.2); E03-S03 settles its placement and adds this method to the code protocol.
    async def apply_external_transition(
        self, external_ref: str, external_status: str, event: WorkProviderEvent
    ) -> WorkItemTransition | None:
        """ARCHITECTURE.md §3.3. Maps status → state → event via provider status map; rejected → EXTERNAL_REJECTED + resync."""

    async def ready_items(self, phase_id: PhaseId | None) -> list[WorkItem]:
        """Items whose state has a scheduled role (INTERFACES §5.2) and no unresolved dependencies, within phase scope."""

    def check_definition_of_ready(self, item: WorkItem) -> GuardResult:
        """§58 checks: contract.goal, acceptance_criteria non-empty, dependencies COMPLETE, design approved if DESIGN required,
        required assets available, constraints known. Failing → BLOCKED with reason."""

    async def set_done_dimension(
        self,
        feature_id: FeatureId,
        dimension: DoneDimension,
        done: bool,
        evidence_id: EvidenceId | None,
    ) -> Feature:
        """§6.5."""

    async def children_states(self, feature_id: FeatureId) -> dict[WorkItemId, WorkItemState]:
        """Child STORY/TASK items plus BUGs with related_feature_id == feature_id; CANCELLED items excluded.
        Producer of guard payload key `children_states` (feature_workflow §3.1). E03-S17."""

    async def open_blocker_bug_count(self, feature_id: FeatureId) -> int:
        """BUGs with related_feature_id == feature_id, severity BLOCKER, state not in {COMPLETE, CANCELLED}.
        Producer of guard payload key `open_blocker_bug_count` (`no_open_blocker_bugs`, §3.1). E03-S17."""

    # phases / RC
    async def phase_event(self, phase_id: PhaseId, event: str, ctx: TransitionContext) -> Phase: ...
    async def rc_event(
        self, rc_id: ReleaseCandidateId, event: str, ctx: TransitionContext
    ) -> ReleaseCandidate: ...
    async def gdd_coverage(self, project_key: ProjectKey) -> dict[str, float]:
        """§74: derived from traceability: COMPLETE stories with gdd_refs / all stories with gdd_refs, per GDD area."""
```

### 1.4 `walk.model_router.protocols`

```python
class ModelRouter(Protocol):
    """§14–§16, §21, §23. Hosted by walk.model_router."""

    def registry(self) -> CapabilityRegistry: ...

    def adapter_for(self, model_id: ModelId) -> "ModelAdapter": ...

    async def select(
        self,
        role: AgentRole,
        policy: ModelPolicy,
        profile: TaskProfile,
        effort: Effort,
        *,
        exclude: Sequence[ModelId] = (),  # Sequence: a tuple default (E01-S19)
        task_override: ModelId | None = None,
    ) -> RoutingDecision:
        """INTERFACES §5.3 steps 1–4: ordered candidates (override, preferred, fallback) minus restricted/disabled/excluded;
        reject on capability (§16), context window, effort support, health; first survivor wins. Ledger MODEL_SELECTED by caller."""

    async def fallback(self, request: FallbackRequest) -> RoutingDecision:
        """INTERFACES §5.3 steps 7–9 — the decision only: max-fallback check, exclusion (whole provider for
        PROVIDER_WIDE_TRIGGERS), CONTEXT_OVERFLOW / BUDGET_RESTRICTION re-ordering, then `select`. Returns is_fallback=True,
        trigger=request.trigger. No ledger writes, no checkpoint, no run start (model_router may not import runtime,
        ARCHITECTURE.md §2.2); the caller (runtime.AgentExecutor) owns steps 5, 6 and 10. Raises BlockedProvider. E01-S28."""

    def classify_error(self, exc: BaseException, adapter: "ModelAdapter") -> FallbackTrigger | None:
        """Maps adapter-specific exceptions/events to §21 triggers; None = not a fallback condition."""

    async def health_all(self) -> dict[ModelId, AdapterHealth]: ...
```

### 1.5 `walk.effort.protocols`

```python
class EffortManager(Protocol):
    """§17–§19. Hosted by walk.effort."""

    def resolve(
        self,
        policy: EffortPolicy,
        item: WorkItem,
        state: WorkItemState,
        escalation_bump: int,
        budget_headroom: dict[BudgetDimension, float],
    ) -> EffortResolution:
        """INTERFACES §5.2 algorithm. Pure."""

    async def request_change(
        self,
        run_id: RunId,
        current: Effort,
        request: EffortRequest,
        policy: EffortPolicy,
        headroom: dict[BudgetDimension, float],
    ) -> Effort:
        """§19: auto-approve if within [min,max] and budget headroom allows (upgrade) else ApprovalRequest(ORCHESTRATOR).
        Fires ON_EFFORT_CHANGE; ledger EFFORT_CHANGED. Returns effective effort for the *next* run (effort is fixed per run)."""
```

### 1.6 `walk.budgets.protocols`

```python
class BudgetManager(Protocol):
    """§20. Hosted by walk.budgets."""

    async def ensure(
        self,
        scope: BudgetScope,
        scope_id: str,
        policy: BudgetPolicy | None,
        limits: dict[BudgetDimension, float] | None,
    ) -> list[Budget]:
        """Create missing Budget rows for a scope (idempotent)."""

    async def applicable(self, subject: BudgetSubject) -> list[Budget]:
        """All budgets whose scope covers the subject: GLOBAL, PROJECT, PHASE(subject.phase_id), ROLE(subject.role), TASK(subject.work_item_id)."""

    async def meter(
        self, subject: BudgetSubject, dimension: BudgetDimension, quantity: float
    ) -> "BudgetVerdict":
        """Adds quantity to every applicable budget in one transaction. Returns verdict: OK | SOFT_THRESHOLD | EXHAUSTED(hard_action).
        Fires ON_BUDGET_THRESHOLD once per budget; ON_BUDGET_EXHAUSTED on hard limit. Ledger BUDGET_EVENT."""

    async def headroom(self, subject: BudgetSubject) -> dict[BudgetDimension, float]:
        """min over applicable budgets of (limit - consumed) per dimension."""

    async def can_afford(
        self, scope_ids: list[str], dimension: BudgetDimension, quantity: float
    ) -> bool: ...


class BudgetVerdict(FrozenModel):
    status: Literal["OK", "SOFT_THRESHOLD", "EXHAUSTED"]
    budget: Budget | None
    hard_action: BudgetHardAction | None


class CostManager(Protocol):
    """§84–§85. Hosted by walk.budgets."""

    async def record(self, record: CostRecord) -> None:
        """Insert cost_records + ledger COST_RECORDED; then BudgetManager.meter(subject from record) for COST_USD/TOKENS.
        Token→USD conversion happens in `walk.model_router.costing.usage_to_cost_record(usage, descriptor, subject)`
        (model_router may import budgets; not vice versa) and is called by runtime.AgentExecutor on USAGE events."""

    async def cost_of(
        self,
        *,
        work_item_id: WorkItemId | None = None,
        phase_id: PhaseId | None = None,
        project_key: ProjectKey | None = None,
    ) -> dict[CostCategory, float]:
        """§85 Cost per Task/Story/Feature (roll-up through parent_id)/Phase/Project."""
```

### 1.7 `walk.context.protocols`

```python
class ContextManager(Protocol):
    """§6.8, §40–§43. Hosted by walk.context."""

    async def build(self, request: ContextRequest) -> ContextBundle:
        """INTERFACES §5.4 algorithm. Fires ON_CONTEXT_STALE for any POSSIBLY_STALE/INVALID item included."""

    def token_budget_for(
        self, effort: Effort, context_window_tokens: int, max_output_tokens: int
    ) -> int:
        """LOW 20%, MEDIUM 35%, HIGH 50%, VERY_HIGH 60% of context_window_tokens minus max_output_tokens (ADR-0012).
        Caller passes the numbers from ModelDescriptor (context stays below model_router)."""
```

### 1.8 `walk.memory.protocols`

```python
class MemoryManager(Protocol):
    """§34–§42, §22, §33. Hosted by walk.memory. All writes go through `write()`."""

    def root(self) -> str:
        """Absolute path of `.ai/`."""

    async def read(self, doc_id: str) -> MemoryDocument: ...
    async def read_feature_context(self, feature_id: FeatureId) -> FeatureContext: ...
    async def read_bug_context(self, bug_id: BugId) -> BugContext: ...
    async def read_project_context(self) -> ProjectContext: ...
    async def read_handover(self, handover_id: HandoverId) -> MemoryDocument:
        """Raw document; `walk.agents.handover.from_document()` converts it to the typed Handover (agents is above memory)."""

    async def write(
        self, doc: MemoryDocument, *, actor: Actor, head: Sha, branch: str
    ) -> MemoryDocument:
        """Validates front matter, bumps version, stamps freshness (commit=head, timestamp=now), refuses secrets
        (ARCHITECTURE.md §6), refuses writes under approved/ without change authorisation (Invariant 10),
        writes atomically (tmp + rename), updates memory_index, fires ON_CONTEXT_UPDATED, ledger CONTEXT_UPDATED."""

    async def apply_updates(
        self, updates: list[ContextUpdate], *, actor: Actor, head: Sha, branch: str
    ) -> list[MemoryDocument]:
        """Section-level REPLACE/APPEND from AgentOutput.context_updates; creates FeatureContext/BugContext skeleton if missing."""

    async def write_handover(
        self, doc: MemoryDocument, *, actor: Actor, head: Sha, branch: str
    ) -> str:
        """Writes `.ai/handovers/HO-NNNN.md` (doc built by `walk.agents.handover.to_document(handover)`); ledger HANDOVER_CREATED.
        The `handovers` table row is written by runtime.CheckpointManager. Returns path."""

    async def assess_freshness(self, doc: MemoryDocument, head: Sha) -> FreshnessAssessment:
        """INTERFACES §5.5."""

    async def rebuild_index(self) -> int:
        """Scan `.ai/**/*.md`, parse front matter, upsert memory_index. Returns doc count."""

    async def approve_artifact(
        self, artifact: ApprovedArtifact, *, actor: Actor
    ) -> ApprovedArtifact:
        """§33. Requires actor role ∈ authority.may_approve[kind] or USER. Ledger ARTIFACT_APPROVED."""

    async def verify_approved_artifacts(self) -> list[ApprovedArtifactId]:
        """Hash check; returns drifted ids and fires ON_CONTEXT_STALE(INVALID) for each."""

    async def write_report(self, kind: str, subject_id: str, markdown: str) -> str:
        """`.ai/reports/<kind>/<subject_id>.md` (generated, overwritten)."""
```

### 1.9 `walk.decisions.protocols` / `walk.debate.protocols`

```python
class DecisionManager(Protocol):
    """§44, §50–§51, Invariant 5, 8. Hosted by walk.decisions."""

    async def propose(
        self, proposal: DecisionProposal, *, by: Actor, work_item_id: WorkItemId | None
    ) -> Decision:
        """Persist as PROPOSED. If proposal.autonomy_level <= proposer authority.max_autonomy_level and category ∈ decision_scope
        → immediately `record()` (Level 0). Else → `escalate()`."""

    async def record(self, decision: Decision, *, by: Actor) -> Decision:
        """Sets ACCEPTED; requires by.role ∈ authority(by.role).decision_scope for category, or USER, or a resolved Debate.
        Writes `.ai/decisions/DEC-NNNN.md`; fires ON_DECISION_RECORDED; ledger DECISION_RECORDED."""

    async def escalate(
        self,
        request: EscalationRequest,
        *,
        from_role: AgentRole,
        work_item_id: WorkItemId | None,
        run_id: RunId | None,
    ) -> Escalation:
        """Creates Escalation; fires ON_ESCALATION; Orchestrator.handle_escalation routes it."""

    async def override(self, decision_id: DecisionId, outcome: str, rationale: str) -> Decision:
        """§93 user override → status OVERRIDDEN + new ACCEPTED version owned by USER; ledger USER_OVERRIDE."""

    async def relevant_for(self, item: WorkItem, affected_systems: list[str]) -> list[Decision]:
        """ACCEPTED decisions linked to the item, its ancestors, or overlapping affected_systems (for context §40 step 3)."""

    def classify_autonomy(
        self,
        proposal: DecisionProposal,
        authority: Authority,
        escalation_rules: list[EscalationRule],
    ) -> AutonomyLevel:
        """§51 classification using the role's escalation_rules + the Level 3 list, bounded by authority.max_autonomy_level."""


class DebateManager(Protocol):
    """§45–§46, §133. Hosted by walk.debate."""

    async def open(
        self,
        topic: str,
        category: DecisionCategory,
        participants: list[AgentRole],
        *,
        opened_by: AgentRole,
        work_item_id: WorkItemId | None,
        max_rounds: int | None = None,
    ) -> Debate:
        """OPEN; allocates budget (REVIEW_LOOPS/COST) ; fires ON_DEBATE_OPENED."""

    async def submit_position(self, position: DebatePosition) -> Debate:
        """Validates role ∈ participants and round == debate.round; persists; ledger DEBATE_POSITION.
        When all participants submitted → `close_round()`."""

    async def close_round(self, debate_id: DebateId) -> Debate:
        """IN_ROUND → CONSENSUS_CHECK; agreement = share of positions whose `position` is marked agreeing with the leading one
        (adapter-structured field `agrees_with_role`); ≥ threshold → `resolve()`; else round+1 (≤ max_rounds) → IN_ROUND
        or → ESCALATED_PO (then ESCALATED_USER if no PO) (§46). Fires ON_DEBATE_ROUND_COMPLETE."""

    async def resolve(
        self, debate_id: DebateId, outcome: str, *, by: Actor, rationale: str
    ) -> Decision:
        """RESOLVED; builds Decision from final positions + evidence; DecisionManager.record; fires ON_DEBATE_RESOLVED."""

    async def abandon(self, debate_id: DebateId, reason: str) -> Debate: ...
```

### 1.10 `walk.permissions.protocols`

```python
class PermissionManager(Protocol):
    """§31, §92. Policy evaluation. Hosted by walk.permissions. Enforcement points: ADR-0006."""

    def rules_for(self, role: AgentRole, extra: Sequence[PermissionRule] = ()) -> list[PermissionRule]:
        """Kernel defaults + `.ai/agents/permissions.yaml` + `extra` (the constitution's tool_permissions, passed by AgentManager),
        de-duplicated; project/extra rules may only narrow (ADR-0013 D-4)."""

    def decide(self, request: ToolCallRequest) -> PermissionDecision:
        """Pure. Most-specific `tool` pattern wins; tie → DENY > REQUIRE_APPROVAL > ALLOW. Shell: command must match an ALLOW
        command_pattern and no DENY pattern. Paths outside worktree → DENY. Protected action → REQUIRE_APPROVAL(approver)."""

    async def request_approval(
        self,
        request: ToolCallRequest | WalkModel | JsonDict,  # Escalation is passed as a WalkModel (permissions may not import decisions)
        *,
        kind: str,
        approver: Approver,
        requested_by: AgentRole,
        run_id: RunId | None,
        work_item_id: WorkItemId | None,
    ) -> ApprovalRequest:
        """Persists PENDING; fires ON_PROTECTED_ACTION_REQUESTED; ledger APPROVAL_REQUESTED."""

    async def decide_approval(
        self,
        approval_id: ApprovalRequestId,
        approve: bool,
        *,
        by: str,
        note: str | None,
        expired: bool = False,
    ) -> ApprovalRequest:
        """CLI `walk approve|deny`. Ledger APPROVAL_DECIDED; wakes the paused run.
        `expired=True` (kernel wait timeout, E01-S26; `approve` must be False) records EXPIRED instead of DENIED."""

    async def pending(self, approver: Approver | None = None) -> list[ApprovalRequest]: ...
```

### 1.11 `walk.skills.protocols`, `walk.tools.protocols`, `walk.hooks.protocols`

```python
class SkillProjector(Protocol):
    """Implemented by each ModelAdapter (ADR-0007)."""

    provider: str

    def project(self, skill: Skill, worktree_path: str) -> SkillProjection:
        """Pure: compute target path + content for this provider (no write)."""

    def render(self, skills: list[Skill], worktree_path: str) -> dict[str, bytes]:
        """E02-S06: every file of the provider's projection (absolute path → bytes); may read, never writes.
        `SkillRegistry.project_all` writes them (atomic), appends each path once to the worktree's
        `info/exclude` (via GitProvider.git_path), upserts `skill_projections` and merges the lock
        (`.ai/agents/projections.lock.yaml`, worktree-relative targets; unchanged entries keep `generated_at`)."""

    def scan(self, worktree_path: str) -> dict[str, str]:
        """E02-S07: skills projected in the worktree → sha256 of their on-disk content (the content `project`
        hashes: a file, or a Codex `AGENTS.md` sub-section). `DefaultSkillRegistry.check_drift` keys it as
        `<target_path>#<skill>` for `walk.skills.drift.compute_drift`; `DefaultSkillRegistry.regenerate` re-projects
        drifted providers and appends one `CONTEXT_UPDATED` (`skills_drift`)."""


class SkillRegistry(Protocol):
    """§28–§29. Hosted by walk.skills."""

    def load(self) -> list[Skill]:
        """Kernel built-ins (`walk/skills/builtin/*/SKILL.md`) + project (`.ai/agents/skills/*/SKILL.md`); project wins on name clash."""

    def get(self, name: SkillName) -> Skill: ...
    def for_role(self, role: AgentRole, required: list[SkillName]) -> list[Skill]:
        """role defaults ∪ required; missing required → ConfigError (§29)."""

    async def project_all(
        self, projectors: list[SkillProjector], worktree_path: str, skills: list[Skill]
    ) -> list[SkillProjection]:
        """Writes projections into the worktree, records skill_projections rows and `.ai/agents/projections.lock.yaml`."""

    async def check_drift(
        self, projectors: list[SkillProjector], worktree_path: str
    ) -> DriftReport:
        """Compares on-disk projection hashes to lock; modified = someone edited a projection directly."""


class ToolRegistry(Protocol):
    """§30. Hosted by walk.tools."""

    def all(self) -> list[ToolSpec]: ...
    def get(self, name: ToolName) -> ToolSpec: ...
    def available(self, ready_env_keys: set[str]) -> list[ToolSpec]:
        """Tools whose requires_env ⊆ ready_env_keys (keys of EnvironmentManifest components in state READY; passed by caller)."""

    def for_role(
        self, allowed: list[ToolName], ready_env_keys: set[str], required: list[ToolName]
    ) -> list[ToolSpec]:
        """(allowed ∪ required) ∩ available; missing required → ConfigError (§29). `allowed` = RuntimePolicy.allowed_tools."""

    def identify(self, command: str) -> ToolSpec | None:
        """Match a shell command to a CLI ToolSpec by command_patterns (for permission + cost attribution)."""


class HookManager(Protocol):
    """§32. Hosted by walk.hooks — registry and dispatcher only. Built-in callables live in
    `walk.orchestrator.builtin_hooks` and are registered once by the composition root via
    `register_builtins(manager, deps)` (ADR-0016)."""

    def register(self, hook: Hook, fn: HookCallable | None = None) -> None:
        """`builtin` hooks need `fn`; project hooks pass None. Raises ConfigError on a duplicate (name, id) and if a project
        hook tries to disable/replace a `required` builtin."""

    def load_project_hooks(self, path: str) -> list[Hook]:
        """`.ai/agents/hooks.yaml`."""

    async def fire(self, name: HookName, ctx: HookContext) -> list[HookResult]:
        """Run hooks for `name` ordered by priority, sequentially, each with timeout. FAIL_CLOSED failure raises HookFailed
        after recording; LOG_AND_CONTINUE records and continues. Every execution → hook_executions + ledger HOOK_EXECUTED/HOOK_FAILED."""

    def hooks_for(self, name: HookName) -> list[Hook]: ...
```

### 1.12 `walk.integrations.protocols` (service)

```python
class IntegrationManager(Protocol):
    """§26–§27, §55–§56, §59. Facade over providers; owns idempotency and inbound event ingestion. Hosted by walk.integrations."""

    work: "WorkProvider"
    git: "GitProvider"
    unity: "UnityProvider | None"
    code_graph: "CodeGraphProvider | None"
    assets: dict[str, "AssetProvider"]
    ci: "CiProvider | None"

    async def preflight(self, required: list[str]) -> EnvironmentManifest:
        """§26 checks; writes `.ai/project/environment.yaml`; compares with previous manifest → drift (§27).
        E02-S02: `required` names `unity`, `work_provider`, a key of `tools`/`providers` (e.g. `git`, `codex`) or
        `<section>.<key>` (e.g. `credentials.JIRA_EMAIL`); an unknown name → ConfigError. The manifest is written
        first; any required component MISSING → ConfigError with `detail["missing_components"]` (`walk doctor` exit 4).
        Implemented by `walk.integrations.DefaultIntegrationManager`; `ingest`/`reconcile`/`with_idempotency` and the
        provider attributes arrive with E03-S03."""

    async def ingest(self, event: WorkProviderEvent) -> None:
        """Dedup by delivery_id (webhook_deliveries), then WorkflowManager.apply_external_transition; Orchestrator.wake()."""

    async def reconcile(self, since: datetime | None) -> int:
        """Poll `work.changes_since(since)` and ingest each; update work_provider_sync. Returns count."""

    async def with_idempotency(
        self, key: str, operation: str, fn: "Callable[[], Awaitable[str]]"
    ) -> str:
        """If key exists → return stored result_ref; else run fn, store (key, result_ref) in the caller's transaction."""
```

### 1.13 `walk.runtime.protocols`

```python
class CheckpointManager(Protocol):
    """§41, §54, §89; ADR-0002. Hosted by walk.runtime."""

    async def checkpoint(
        self,
        run: AgentRun,
        kind: CheckpointKind,
        *,
        handover: Handover | None = None,
        workflow_state: WorkItemState | None = None,
        budget_consumed: dict[BudgetDimension, float] | None = None,
        context_manifest: ContextBundleRef | None = None,
    ) -> Checkpoint:
        """1) WIP commit on run.branch (`wip(<work_item>): checkpoint <seq>`; skipped if clean) via GitProvider (idempotent key);
        2) insert checkpoints row; 3) if handover given → MemoryManager.write_handover; 4) fire ON_AGENT_CHECKPOINT; ledger CHECKPOINT_CREATED.
        E01-S25: `workflow_state` is required except for START and PAUSE (read from the work item); `budget_consumed` and
        `context_manifest` default to empty.
        E01-B05: a handover's `worktree_head` (and the sha in its `current_state`) is set to the HEAD after the WIP commit
        before the document and the row are written, so document, row and checkpoint `head_sha` agree. The continuing run
        receives the stored row. `DefaultCheckpointManager.close_handover(id, to_run_id)` closes the row and rewrites the
        document with `extra.to_run_id` through MemoryManager.write (version bump, CONTEXT_UPDATED; HANDOVER_CREATED stays
        once); a missing document is logged and the row stays closed."""

    async def latest(self, run_id: RunId) -> Checkpoint | None: ...
    async def latest_for_item(self, work_item_id: WorkItemId) -> Checkpoint | None: ...

    async def build_handover(
        self, run: AgentRun, reason: str, partial_output: AgentOutput | None
    ) -> Handover:
        """From run's accumulated findings/changes/decisions + git diff names; never from model transcript (§22)."""

    async def interrupted_runs(self, current_instance: str) -> list[AgentRun]: ...


class AgentExecutor(Protocol):
    """Runs AgentRun tasks. Hosted by walk.runtime (not a §125 service; the engine behind Orchestrator)."""

    async def start(
        self,
        agent: AgentInstance,
        item: WorkItem,
        purpose: str,
        *,
        handover: Handover | None = None,
        parent_run_id: RunId | None = None,
        debate: Debate | None = None,
        routing: RoutingDecision | None = None,
        effort_resolution: EffortResolution | None = None,
    ) -> AgentRun:
        """ARCHITECTURE.md §3.2 steps 3–7. Returns immediately with RUNNING run; completion wakes the orchestrator.
        E01-S27: `routing`/`effort_resolution` are the scheduler's decisions; the executor is their ledger write point
        (MODEL_SELECTED, EFFORT_SET). A preparation failure returns the run FAILED instead of raising.
        E01-B01 worktree lifecycle: a child run (`parent_run_id`) adopts its parent's worktree; a run without a parent
        adopts the newest worktree directory an ended run of the item left on disk (FAILED/BLOCKED_*/HANDED_OVER keep
        theirs for diagnosis), else `SandboxManager.create`. A COMPLETED run calls `SandboxManager.remove(keep_branch=True)`
        after AGENT_RUN_ENDED and ON_AGENT_END (a removal failure is logged; the run stays COMPLETED). `cancel` removes
        the worktree, `pause` keeps it."""

    async def resume_native(self, checkpoint: Checkpoint) -> AgentRun:
        """Same model, provider-side session resume (ModelAdapter.resume). E01-S28: raises NotResumable when the session
        is not resumable, the adapter is unhealthy or refuses the resume (the new run then ends FAILED `not_resumable`);
        the caller (runtime.RecoveryManager) continues with `start(handover=…)`."""

    async def cancel(self, run_id: RunId, reason: str) -> AgentRun: ...
    async def pause(self, run_id: RunId) -> AgentRun: ...
    def running(self) -> list[AgentRun]: ...


class ToolInvoker(Protocol):
    """Permission enforcement point for KERNEL tools and the authorizer for provider-native tools (ADR-0006)."""

    async def authorize(self, request: ToolCallRequest) -> PermissionDecision:
        """PermissionManager.decide; ALLOW → ON_TOOL_BEFORE; DENY → ON_TOOL_DENIED + ledger TOOL_DENIED;
        REQUIRE_APPROVAL → request_approval, pause run, await decision (timeout → DENY).
        E01-S27: an adapter that reports tool calls after they ran (Codex, `configure_sandbox`) gets the post-hoc
        authorizer `DefaultToolInvoker.authorizer_for(run, wait_for_approval=False)`: DENY/REQUIRE_APPROVAL are
        recorded (TOOL_DENIED) and returned unchanged, the run is never paused, and the executor fails the run
        FAILED_BOUNDARY instead of applying its effects (ADR-0006 D-5)."""

    async def invoke(self, request: ToolCallRequest) -> JsonDict:
        """authorize() then dispatch KERNEL tool to IntegrationManager; meter TOOL_CALLS; ON_TOOL_AFTER; ledger TOOL_INVOKED."""


class OutputApplier(Protocol):
    """Applies AgentOutput effects in a fixed order (ARCHITECTURE.md §3.2 step 6)."""

    async def apply(self, run: AgentRun, output: AgentOutput, *, start_head: Sha) -> "AppliedEffects":
        """E01-S27: `start_head` = worktree HEAD at run start; `commit_sha` is HEAD when it moved since."""


class AppliedEffects(FrozenModel):
    evidence_ids: list[EvidenceId]
    decision_ids: list[DecisionId]
    created_work_items: list[WorkItemId]
    escalation_ids: list[str]
    memory_docs: list[str]
    commit_sha: Sha | None
    workflow_event: str | None


class SandboxManager(Protocol):
    """§60 isolated worktrees; ADR-0009 §D-5."""

    async def create(self, run: AgentRun, item: WorkItem) -> str:
        """`git worktree add <repo>/.walk/worktrees/<run_id> <branch>` (branch = item.branch or feat/<id>-<slug>); installs guard hooks;
        writes projections; returns path. Fails while another worktree has the branch checked out: the executor adopts
        a leftover worktree instead (E01-B01)."""

    async def adopt(self, run: AgentRun, previous: AgentRun, item: WorkItem) -> str:
        """Child run (fallback / recovery / native resume) reuses previous.worktree_path unchanged; re-adds it on previous.branch
        with guard hooks when the directory is missing. Never `create` for a child run (one branch, one worktree). E01-S28.
        E01-B01: also used for a parentless run that takes over the worktree an ended run of the item left behind."""

    async def remove(self, run: AgentRun, *, keep_branch: bool = True) -> None:
        """`git worktree remove --force` + prune; the branch is deleted only when `keep_branch` is false and it is not
        protected. Called by the executor when a run is COMPLETED or CANCELLED (E01-B01)."""


class BoundaryAuditor(Protocol):
    def audit(
        self,
        worktree_path: str,
        changed_files: list[str],
        allowed_paths: list[str],
        forbidden_paths: list[str],
    ) -> list[str]:
        """Returns violations (paths). Non-empty → run FAILED_BOUNDARY, changes discarded (git checkout -- .)."""
```

### 1.14 `walk.telemetry.protocols`

```python
class LedgerManager(Protocol):
    """§81–§83, §86. Hosted by walk.telemetry."""

    async def append(self, event: LedgerEvent, *, uow: UnitOfWork | None = None) -> LedgerEvent:
        """Insert; returns event with seq. Participates in the caller's UnitOfWork when provided."""

    async def query(
        self,
        *,
        kinds: list[LedgerEventKind] | None = None,
        work_item_id: WorkItemId | None = None,
        run_id: RunId | None = None,
        phase_id: PhaseId | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 1000,
    ) -> list[LedgerEvent]: ...

    def tail(self, after_seq: int) -> AsyncIterator[LedgerEvent]:
        """Async generator in implementations (`async def` + `yield`); polls until cancelled."""

    async def report(
        self,
        kind: Literal["task", "feature", "phase", "project", "cost", "improvement"],
        subject_id: str,
    ) -> "Report":
        """§83 generated from events only."""


class Report(FrozenModel):
    kind: str
    subject_id: str
    generated_at: datetime
    markdown: str
    data: JsonDict


class EvidenceManager(Protocol):
    """§6.6, §47. Hosted by walk.telemetry."""

    async def record(
        self,
        draft: EvidenceDraft,
        *,
        actor: Actor,
        work_item_id: WorkItemId | None,
        phase_id: PhaseId | None,
        commit: Sha | None,
    ) -> Evidence:
        """Copies/links file under `.ai/<features|bugs|phases>/<id>/evidence/`, hashes it, mints EVD id, ledger EVIDENCE_RECORDED."""

    async def for_item(
        self, work_item_id: WorkItemId, kinds: list[EvidenceKind] | None = None
    ) -> list[Evidence]: ...
    async def for_phase(self, phase_id: PhaseId) -> list[Evidence]: ...
    def strongest(self, evidence: list[Evidence]) -> Evidence | None:
        """max by rank (§47), ties by produced_at desc."""

    def satisfies(
        self, required: list[EvidenceKind], present: list[Evidence]
    ) -> list[EvidenceKind]:
        """Returns missing kinds (guard `required_evidence_present`)."""


class TelemetryManager(Protocol):
    """§86 metrics + §116 improvement metrics. Hosted by walk.telemetry."""

    def counter(self, name: str, value: float = 1.0, **labels: str) -> None: ...
    def timer(self, name: str, seconds: float, **labels: str) -> None: ...
    async def metrics(
        self, *, phase_id: PhaseId | None = None, since: datetime | None = None
    ) -> RetrospectiveMetrics:
        """Computed from ledger (first-pass rate = items reaching COMPLETE with fix_loops == 0 / completed; etc.)."""

    def log(self, level: str, message: str, **fields: object) -> None:
        """JSON line to `.walk/logs/kernel.jsonl`; diagnostics only (ADR-0001)."""
```

### 1.15 `walk.improvement.protocols`

```python
class ImprovementManager(Protocol):
    """§94–§121. Hosted by walk.improvement."""

    async def observe(
        self,
        draft: ObservationDraft,
        *,
        actor: Actor,
        work_item_id: WorkItemId | None,
        run_id: RunId | None,
        source_signal: str,
    ) -> ImprovementObservation:
        """Project scope; writes `.ai/improvements/OBS-NNNN.md`; fires ON_IMPROVEMENT_OBSERVATION."""

    async def detect_signals(self, since: datetime) -> list[ImprovementObservation]:
        """§99 automatic sources from ledger: repeated fallback, stale context, fix loops, build failures, user overrides (§118)."""

    async def phase_retrospective(
        self, phase_id: PhaseId, *, with_narrative: bool
    ) -> Retrospective:
        """§115: TelemetryManager.metrics + top bottleneck/defect; optional PROCESS_ARCHITECT run for narrative."""

    async def promote(self, observation_id: ObservationId) -> ImprovementObservation:
        """§111 project → kernel scope (explicit; never automatic §110)."""

    async def create_candidate(self, candidate: ImprovementCandidate) -> ImprovementCandidate: ...
    async def review_candidate(
        self, candidate_id: ImprovementId, approve: bool, *, by: Actor, note: str
    ) -> ImprovementCandidate:
        """§104 tiers: LOW → ORCHESTRATOR may approve; MEDIUM → PRODUCT_OWNER/maintainer; HIGH → USER only."""

    async def register_version(self, version: BehaviorVersion) -> BehaviorVersion:
        """§105; ledger BEHAVIOR_VERSION_CHANGED; kernel_changelog entry required when stage ∈ {LIMITED, DEFAULT} (§120)."""

    async def set_stage(
        self, kind: ImprovementScope, name: str, version: str, stage: RolloutStage
    ) -> BehaviorVersion:
        """INTERFACES §6.5 rollout table."""

    def pinned_versions(self) -> dict[str, str]:
        """From `.ai/project/kernel-versions.yaml`; used by TelemetryManager for LedgerEvent.behavior_versions."""
```

---

## 2. Provider boundary protocols

### 2.1 `ModelAdapter` (`walk.model_router.protocols`; ADR-0004)

```python
class RunSession(FrozenModel):
    """Per-run adapter configuration supplied by the kernel."""

    run_id: RunId
    worktree_path: str
    allowed_tools: list[ToolSpec]
    permission_authorizer: "Callable[[ToolCallRequest], Awaitable[PermissionDecision]]"
    effort: Effort
    model_id: ModelId
    max_turns: int
    timeout_s: int
    env_allowlist: dict[str, str]
    output_path: str = Field(
        description="<worktree>/.walk/output.json — fallback channel for the structured AgentOutput"
    )


class ProviderEffortConfig(FrozenModel):
    """ADR-0011: what the adapter actually sets."""

    model_id: ModelId
    params: JsonDict


class ModelAdapter(Protocol):
    """One per provider. Stateless w.r.t. role (Invariant 1). Only module allowed to import the provider SDK / spawn its CLI."""

    provider: str

    def descriptors(self) -> list[ModelDescriptor]:
        """Capability descriptors for the models this adapter serves (defaults; overridable in models.yaml)."""

    async def health(self) -> AdapterHealth:
        """Cheap liveness/auth check (CLI present + logged in / API reachable). Cached ≤ 60 s."""

    def map_effort(self, effort: Effort, model_id: ModelId) -> ProviderEffortConfig:
        """§17 translate. Must be total over Effort for every supported model (degrade to nearest supported)."""

    def run(self, input: AgentInput, session: RunSession) -> AsyncIterator[AgentEvent]:
        """Start a fresh provider session; stream normalised AgentEvents; last event FINAL_OUTPUT(output=AgentOutput) or ERROR.
        MUST: drop thinking/reasoning blocks (§22); route every tool call through session.permission_authorizer before execution
        (Claude) or configure sandbox equivalently (Codex); emit USAGE at least at end; emit session ref in STARTED."""

    def resume(
        self, session_ref: ProviderSessionRef, instruction: str, session: RunSession
    ) -> AsyncIterator[AgentEvent]:
        """Continue provider-side session (Claude `resume=session_id`; Codex `exec resume <id>`). Raise NotResumable if unsupported."""

    async def cancel(self, run_id: RunId) -> None: ...

    def usage(self, run_id: RunId) -> UsageReport:
        """Cumulative usage of a run (also streamed as USAGE events)."""

    def skill_projector(self) -> SkillProjector: ...

    def parse_output(self, raw: str) -> AgentOutput:
        """Validate JSON against AgentOutput; raise OutputInvalid with field errors (used for the repair turn)."""
```

### 2.2 `WorkProvider` (`walk.integrations.protocols`; ADR-0005)

```python
class WorkItemRef(FrozenModel):
    external_ref: str
    url: str | None


class WorkProvider(Protocol):
    """§55 source of work state. Implementations: LocalWorkProvider [MVP], JiraWorkProvider [Stage 3]."""

    provider: str

    async def health(self) -> ComponentStatus: ...

    async def create(self, item: WorkItem, *, idempotency_key: str) -> WorkItemRef:
        """Create issue/record with label `walk:<item.id>`. Idempotent: existing key → return stored ref; else search by label before creating."""

    async def update(
        self, item: WorkItem, fields: dict[str, object], *, idempotency_key: str
    ) -> None:
        """Title/description/priority/labels/parent link."""

    async def transition(
        self, item: WorkItem, to_state: WorkItemState, *, idempotency_key: str
    ) -> None:
        """Map WorkItemState → provider status via status map; no-op if already there."""

    async def assign(self, item: WorkItem, role: AgentRole, *, idempotency_key: str) -> None:
        """Assignee = configured account per role (or label `walk-role:<role>`)."""

    async def comment(self, item: WorkItem, markdown: str, *, idempotency_key: str) -> None: ...

    async def link(
        self,
        from_item: WorkItem,
        to_item: WorkItem,
        kind: Literal["BLOCKS", "RELATES", "PARENT"],
        *,
        idempotency_key: str,
    ) -> None: ...

    async def get(self, external_ref: str) -> JsonDict: ...

    async def query(
        self,
        *,
        states: list[WorkItemState] | None = None,
        kinds: list[WorkItemKind] | None = None,
        limit: int = 200,
    ) -> list[JsonDict]: ...

    async def changes_since(self, since: datetime | None) -> list[WorkProviderEvent]:
        """Polling fallback (§56)."""

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> list[WorkProviderEvent]:
        """Verify signature/secret; normalise. LocalWorkProvider raises NotSupported."""

    def status_map(self) -> dict[WorkItemState, str]:
        """Kernel state → provider status name (configurable)."""
```

### 2.3 `GitProvider` (§59–§60)

```python
class CommitInfo(FrozenModel):
    sha: Sha
    message: str
    files: list[str]


class PullRequestRef(FrozenModel):
    number: int | None
    url: str | None
    head: Sha
    base: str


class GitProvider(Protocol):
    provider: str  # "git-cli"

    async def head(self, path: str) -> Sha: ...
    async def current_branch(self, path: str) -> str: ...
    async def git_path(self, path: str, name: str) -> str:
        """E02-S06: absolute `git rev-parse --git-path <name>` (e.g. `info/exclude`, shared by linked worktrees)."""
    async def ensure_branch(self, name: str, base: str, *, idempotency_key: str) -> str: ...
    async def add_worktree(self, path: str, branch: str) -> str: ...
    async def remove_worktree(self, path: str, *, force: bool = False) -> None: ...
    async def delete_branch(self, name: str, *, protected_branches: list[str]) -> None:
        """Local branch cleanup (SandboxManager.remove, E01-S25); PermissionDenied if `name` matches a protected glob —
        deleting a protected branch is the protected action `git.delete_branch_protected` (ToolInvoker)."""

    async def status(self, path: str) -> list[str]:
        """Dirty files (porcelain)."""

    async def diff_names(self, path: str, base: Sha | None = None) -> list[str]: ...
    async def discard_changes(self, path: str) -> None:
        """`git checkout -- .` + `git clean -fd` in the worktree at `path` only (boundary violation path, E01-S27)."""

    async def commit_all(
        self, path: str, message: str, *, trailer_work_item: WorkItemId, idempotency_key: str
    ) -> CommitInfo | None:
        """Stages everything except forbidden paths; message gets trailer `Walk-Work-Item: <id>` (§59 traceability). None if clean."""

    async def push(self, path: str, branch: str, *, protected_branches: list[str]) -> None:
        """Raises PermissionDenied if branch ∈ protected (protected ops go through ToolInvoker with approval)."""

    async def open_pr(
        self, branch: str, base: str, title: str, body: str, *, idempotency_key: str
    ) -> PullRequestRef:
        """Via `gh` CLI when available; else records a local PR stub (LocalWorkProvider dev mode)."""

    async def merge(
        self, pr: PullRequestRef, *, strategy: Literal["squash", "merge"], idempotency_key: str
    ) -> Sha:
        """Protected action — caller must hold an approved ApprovalRequest."""

    async def squash_wip(self, path: str, branch: str, base: Sha, message: str) -> Sha:
        """Collapse `wip(...)` checkpoint commits into one commit before PR (ADR-0002 §D-4)."""

    async def install_guard_hooks(self, path: str, protected_branches: list[str]) -> None: ...
    async def is_ancestor(self, ancestor: Sha, descendant: Sha, path: str) -> bool: ...
    async def merge_base(self, a: str, b: str, path: str) -> Sha:
        """`git merge-base a b`; refs or shas; no common ancestor → GitError. Squash base of the integration step (E03-S12)."""

    async def changed_between(
        self, a: Sha, b: Sha, path: str, *, paths: list[str] | None = None
    ) -> list[str]:
        """Used by freshness classification (§42)."""
```

### 2.4 `UnityProvider` and `CiProvider` (§62)

```python
class BuildTarget(StrEnum):
    ANDROID = "Android"
    IOS = "iOS"
    STANDALONE_WIN64 = "StandaloneWindows64"
    STANDALONE_OSX = "StandaloneOSX"
    WEBGL = "WebGL"


class JobResult(FrozenModel):
    ok: bool
    job_kind: Literal[
        "compile",
        "editmode_tests",
        "playmode_tests",
        "build",
        "asset_validation",
        "static_check",
        "perf_smoke",
    ]
    duration_s: float
    log_path: str
    artifact_paths: list[str]
    summary: str
    metrics: JsonDict


class UnityProvider(Protocol):
    """Unity batchmode CLI via a small editor package `com.walk.ci` installed by bootstrap (ADR-0009 §D-6)."""

    async def detect(self, project_path: str) -> ComponentStatus: ...
    async def compile(self, project_path: str) -> JobResult: ...
    async def run_tests(
        self, project_path: str, mode: Literal["EditMode", "PlayMode"], *, filter: str | None = None
    ) -> JobResult: ...
    async def build(
        self, project_path: str, target: BuildTarget, output_path: str, *, development: bool = True
    ) -> JobResult: ...
    async def validate_assets(self, project_path: str, paths: list[str]) -> JobResult:
        """§79 [Stage 8]."""


class CiProvider(Protocol):
    """§62 orchestration of jobs for a commit; default implementation runs UnityProvider locally."""

    async def run_pipeline(
        self,
        worktree_path: str,
        commit: Sha,
        jobs: list[str],
        *,
        idempotency_key: str,
        work_item_id: WorkItemId | None = None,
    ) -> list[JobResult]:
        """Fires ON_BUILD_START/SUCCESS/FAILURE and ON_TEST_RESULT; each result → EvidenceManager.record.
        `work_item_id` attributes hook contexts, evidence and BUILD_RESULT/TEST_RESULT ledger events to the item (E03-S11)."""
```

### 2.5 `AssetProvider` (§78–§80) `[Stage 8]`

```python
class AssetRequest(FrozenModel):
    kind: Literal["model3d", "texture", "image", "animation", "audio"]
    prompt: str
    reference_artifact_ids: list[ApprovedArtifactId]
    constraints: JsonDict  # triangle budget, texture size, style tags (§79)
    work_item_id: WorkItemId


class AssetJob(FrozenModel):
    provider: str
    job_id: str
    state: Literal["QUEUED", "RUNNING", "DONE", "FAILED"]
    cost_credits: float | None


class AssetProvenance(FrozenModel):
    """§80 metadata stored next to the asset as `<asset>.provenance.yaml` and as Evidence."""

    asset_path: str
    provider: str
    prompt: str
    reference_concept: ApprovedArtifactId | None
    generated_by: Actor
    approved_by: Actor | None
    version: int
    related_feature_id: FeatureId | None
    license_or_source: str
    job_id: str


class AssetProvider(Protocol):
    provider: str

    async def health(self) -> ComponentStatus: ...
    async def generate(self, request: AssetRequest, *, idempotency_key: str) -> AssetJob: ...
    async def poll(self, job_id: str) -> AssetJob: ...
    async def download(self, job_id: str, target_dir: str) -> list[str]: ...
    def provenance(
        self, job: AssetJob, request: AssetRequest, paths: list[str], actor: Actor
    ) -> AssetProvenance: ...
```

### 2.6 `CodeGraphProvider` (§43; ADR-0009 §D-9)

```python
class GraphNode(FrozenModel):
    id: str
    kind: Literal["file", "class", "method", "asset", "scene", "prefab", "community"]
    path: str | None
    name: str


class GraphEdge(FrozenModel):
    src: str
    dst: str
    kind: str  # imports / calls / references / depends_on


class GraphNeighborhood(FrozenModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    depth: int


class CodeGraphProvider(Protocol):
    provider: str  # "graphify"

    async def health(self, repo_path: str) -> ComponentStatus: ...
    async def build(self, repo_path: str, *, incremental: bool = True) -> str:
        """Returns graph version/sha. Output under `<repo>/graphify-out/` (gitignored)."""

    async def mark_dirty(self, paths: list[str]) -> None: ...
    async def neighbors(self, repo_path: str, seeds: list[str], depth: int) -> GraphNeighborhood:
        """seeds = file paths or symbol names (feature_context.relevant_files / affected_systems)."""

    async def impact(self, repo_path: str, changed_paths: list[str]) -> list[GraphNode]:
        """Reverse dependencies — used by §72 CHANGE analysis and Lead Dev review context."""

    async def query(self, repo_path: str, question: str) -> str:
        """Free-text graph query (graphify query) returned as markdown; used sparingly at HIGH+ effort."""
```

---

## 3. Workflow state machines

Conventions: *Event* names are the strings passed to `raise_event`. *Who* = `allowed_roles` (KERNEL = automatic). Guards are named callables registered in `walk.workflow.guards`. Hooks listed are fired after commit in addition to `ON_STATE_TRANSITION` (always).

### 3.1 Feature lifecycle `feature_workflow v1.0` (§53, §61, §131) `[MVP]`

| From | Event | Guard(s) | To | Hooks | Who |
|---|---|---|---|---|---|
| IDEA | `start_discovery` | `in_phase_scope` | DISCOVERY | — | ORCHESTRATOR, USER |
| DISCOVERY | `discovery_done` | `has_gdd_refs_or_user_feature` | DESIGN | — | ORCHESTRATOR, DESIGN_LEADER, PRODUCT_OWNER |
| DISCOVERY | `block` | — | BLOCKED | ON_TASK_BLOCKED | any agent role |
| DESIGN | `design_approved` | `technical_design_section_present`, `required_approved_artifacts_present` | READY | — | LEAD_DEV (technical design §131), DESIGN_LEADER |
| DESIGN | `block` | — | BLOCKED | ON_TASK_BLOCKED | any |
| READY | `start_implementation` | `definition_of_ready` (§58), `children_created` | IMPLEMENTING | ON_TASK_START | KERNEL (when first story starts) |
| IMPLEMENTING | `all_children_integrated` | `all_stories_in(INTEGRATION∪QC∪COMPLETE)` | INTEGRATION | — | KERNEL |
| IMPLEMENTING | `block` | — | BLOCKED | ON_TASK_BLOCKED | any |
| INTEGRATION | `integration_passed` | `ci_green_on_integration_branch`, `required_evidence_present` | QC | ON_READY_FOR_QC | KERNEL |
| INTEGRATION | `ci_failed` | — | REWORK | ON_BUILD_FAILURE | KERNEL |
| QC | `qc_passed` | `qc_output_status == APPROVED`, `all_applicable_dimensions_done` (§6.5), `no_open_blocker_bugs` | COMPLETE | ON_TASK_COMPLETE | QC |
| QC | `qc_rejected` | `fix_loops < max_fix_loops` | REWORK | ON_QC_RESULT, ON_BUG_CREATED (per bug) | QC |
| QC | `qc_rejected` | `fix_loops >= max_fix_loops` | BLOCKED | ON_TASK_FAILED (escalation ROOT_CAUSE_REVIEW) | QC |
| REWORK | `rework_planned` | `rework_children_created` | IMPLEMENTING | ON_TASK_START | ORCHESTRATOR, LEAD_DEV |
| BLOCKED | `unblock` | `blocker_resolved` | *previous state* (stored in payload) | — | ORCHESTRATOR, SCRUM_MASTER, USER |
| COMPLETE | `phase_review` | `phase.state == EVIDENCE_REVIEW` | PHASE_REVIEW | — | KERNEL |
| PHASE_REVIEW | `to_gate` | — | USER_GATE | — | KERNEL |
| USER_GATE | `gate_go` | — | COMPLETE (final) | — | USER |
| USER_GATE | `gate_rework` | — | REWORK | ON_PHASE_GATE_DECISION | USER |
| any except COMPLETE/CANCELLED | `cancel` | — | CANCELLED | ON_TASK_CANCELLED | USER |
| any | `force_review` | `has_children_in(IMPLEMENTING)` | *children → READY_FOR_REVIEW* | — | USER |

Note: PHASE_REVIEW/USER_GATE at feature level are projections of the phase state onto features in the phase (so dashboards §87 can show them); the authoritative gate is `Phase.state`.

### 3.2 Story / Task lifecycle `story_workflow v1.0` (§61, §131) `[MVP]`

| From | Event | Guard(s) | To | Hooks | Who |
|---|---|---|---|---|---|
| IDEA | `ready` | `definition_of_ready` | READY | — | ORCHESTRATOR, LEAD_DEV, SCRUM_MASTER |
| IDEA | `block` | — | BLOCKED | ON_TASK_BLOCKED | any |
| READY | `start_implementation` | `dependencies_complete`, `branch_available`, `budget_available` | IMPLEMENTING | ON_TASK_START | KERNEL (scheduler) |
| IMPLEMENTING | `submit_for_review` | `output_status == COMPLETED`, `has_commit`, `required_evidence_present(TESTED)` | READY_FOR_REVIEW | — | SENIOR_DEV |
| IMPLEMENTING | `analysis_done` | `output_status_is_completed`, `analysis_only_task` (label `analysis-only`) | COMPLETE | ON_TASK_COMPLETE | KERNEL |
| IMPLEMENTING | `partial` | `handover_present` | IMPLEMENTING (re-queue) | ON_AGENT_HANDOFF | SENIOR_DEV |
| IMPLEMENTING | `block` | `escalations_non_empty` | BLOCKED | ON_TASK_BLOCKED | SENIOR_DEV |
| READY_FOR_REVIEW | `start_review` | `reviewer_role != implementer_role`, `reviewer_run_model != implementer_model OR cross_model_review == false` | LEAD_DEV_REVIEW | — | KERNEL |
| LEAD_DEV_REVIEW | `review_approved` | `output_status == APPROVED` | INTEGRATION | — | LEAD_DEV |
| LEAD_DEV_REVIEW | `review_rejected` | — | REWORK | — | LEAD_DEV |
| INTEGRATION | `integration_passed` | `ci_green` | QC | ON_READY_FOR_QC | KERNEL |
| INTEGRATION | `ci_failed` | — | REWORK | ON_BUILD_FAILURE | KERNEL |
| QC | `qc_passed` | `output_status == APPROVED`, `required_evidence_present` | COMPLETE | ON_TASK_COMPLETE, ON_QC_RESULT | QC |
| QC | `qc_rejected` | `fix_loops < max_fix_loops` → `fix_loops += 1` | REWORK | ON_QC_RESULT, ON_BUG_CREATED | QC |
| QC | `qc_rejected` | `fix_loops >= max_fix_loops` | BLOCKED | ON_TASK_FAILED | QC |
| REWORK | `start_implementation` | `budget_available` | IMPLEMENTING | ON_TASK_START | KERNEL |
| BLOCKED | `unblock` | `blocker_resolved` | previous | — | ORCHESTRATOR, SCRUM_MASTER, USER |
| any except COMPLETE | `cancel` | — | CANCELLED | ON_TASK_CANCELLED | USER |
| IMPLEMENTING | `force_review` | — | READY_FOR_REVIEW | — | USER |

`analysis_done` is the single completion path for non-code work (no commit, no review): the `OutputApplier` raises it instead of the table-mapped event when the item carries label `analysis-only` and the output status is `COMPLETED` (E06-S02). GDD readiness (E06-S02), phase plan (E06-S04), REWORK intake (E07-S06) and CHANGE analysis (E07-S07) tasks use it; later analysis tasks reuse it rather than adding rows.

Integration for stories = squash WIP, push branch, open PR (kernel), run CI (§62); merge into the feature/integration branch is automatic for non-protected branches; merge to protected base is a protected action.

### 3.3 Bug lifecycle `bug_workflow v1.0` (§64; ADR-0010)

| From | Event | Guard(s) | To | Hooks | Who |
|---|---|---|---|---|---|
| IDEA (created) | `triage` | — | DISCOVERY | ON_BUG_CREATED | KERNEL (on creation) |
| DISCOVERY | `triaged` | `severity_set`, `owner_role_set` | READY | — | LEAD_DEV, ORCHESTRATOR, QC |
| DISCOVERY | `wont_fix` | `decision_recorded(category=QUALITY)` (§10.8 business decision) | CANCELLED | — | PRODUCT_OWNER, LEAD_DEV, USER |
| READY | `start_fix` | `dependencies_complete`, `budget_available` | IMPLEMENTING | ON_TASK_START | KERNEL |
| IMPLEMENTING | `submit_for_review` | `root_cause_section_present` (BugContext §38), `has_commit`, `regression_test_evidence` | READY_FOR_REVIEW | — | SENIOR_DEV |
| IMPLEMENTING | `block` | — | BLOCKED | ON_TASK_BLOCKED | SENIOR_DEV |
| READY_FOR_REVIEW | `start_review` | `reviewer != implementer` | LEAD_DEV_REVIEW | — | KERNEL |
| LEAD_DEV_REVIEW | `review_approved` | — | INTEGRATION | — | LEAD_DEV |
| LEAD_DEV_REVIEW | `review_rejected` | — | REWORK | — | LEAD_DEV |
| INTEGRATION | `integration_passed` | `ci_green` | QC (re-test) | ON_READY_FOR_QC | KERNEL |
| INTEGRATION | `ci_failed` | — | REWORK | — | KERNEL |
| QC | `verified` | `reproduction_no_longer_reproduces_evidence` | COMPLETE (closed) | ON_TASK_COMPLETE, ON_QC_RESULT | QC |
| QC | `reopen` | `reopen_count < max_reopen` → `reopen_count += 1` | REWORK | ON_QC_RESULT | QC |
| QC | `reopen` | `reopen_count >= max_reopen` | BLOCKED | ON_TASK_FAILED | QC |
| REWORK | `start_fix` | — | IMPLEMENTING | ON_TASK_START | KERNEL |
| COMPLETE | `regression_reopen` | — | DISCOVERY | ON_BUG_CREATED | QC |
| BLOCKED | `unblock` | — | previous | — | ORCHESTRATOR, USER |

### 3.4 Phase lifecycle `phase_workflow v1.0` (§66–§72)

| From | Event | Guard(s) | To | Hooks | Who |
|---|---|---|---|---|---|
| PLANNED | `start` | `previous_phase_complete_or_first`, `scope_non_empty`, `kit_validated` | ACTIVE | ON_PHASE_START | USER (`walk phase start`), KERNEL after GO |
| ACTIVE | `request_review` | `all_scope_features_in(COMPLETE∪CANCELLED∪BLOCKED)` or USER force | EVIDENCE_REVIEW | ON_PHASE_REVIEW_START | KERNEL, USER |
| EVIDENCE_REVIEW | `package_ready` | `evidence_package_written`, `retrospective_written` | USER_GATE (`gate_round += 1`) | — | KERNEL |
| USER_GATE | `decide:GO` | — | COMPLETE (+ next phase `start`) | ON_PHASE_GATE_DECISION, ON_PHASE_COMPLETE | USER |
| USER_GATE | `decide:REWORK` | `feedback_non_empty` | REWORK | ON_PHASE_GATE_DECISION | USER |
| USER_GATE | `decide:CHANGE` | `feedback_non_empty` | CHANGE_ANALYSIS | ON_PHASE_GATE_DECISION | USER |
| USER_GATE | `decide:STOP` | — | STOPPED (project paused) | ON_PHASE_GATE_DECISION | USER |
| REWORK | `rework_planned` | `rework_work_items_created` (§71 decomposition by ORCHESTRATOR/PO/DESIGN run) | ACTIVE | ON_PHASE_START | KERNEL |
| CHANGE_ANALYSIS | `change_plan_approved` | `impact_analysis_evidence_present` (§72 list), `approval(USER)` | PLANNED (re-plan) | — | USER |
| CHANGE_ANALYSIS | `change_rejected` | — | USER_GATE | — | USER |
| STOPPED | `reopen` | — | PLANNED | — | USER |
| any | `stop` | — | STOPPED | — | USER (§93 Stop Phase) |

### 3.5 Debate lifecycle `debate_workflow v1.0` (§46)

| From | Event | Guard(s) | To | Hooks | Who |
|---|---|---|---|---|---|
| OPEN | `start_round` | `participants >= 2`, `budget_available` | IN_ROUND (round=1) | ON_DEBATE_OPENED | KERNEL |
| IN_ROUND | `position_submitted` | `role ∈ participants`, `round matches` | IN_ROUND | — | participant roles |
| IN_ROUND | `all_positions_in` | — | CONSENSUS_CHECK | ON_DEBATE_ROUND_COMPLETE | KERNEL |
| CONSENSUS_CHECK | `consensus` | `agreement >= threshold` | RESOLVED | ON_DEBATE_RESOLVED, ON_DECISION_RECORDED | KERNEL |
| CONSENSUS_CHECK | `next_round` | `round < max_rounds` | IN_ROUND (round+1) | — | KERNEL |
| CONSENSUS_CHECK | `escalate` | `round >= max_rounds`, PO role configured | ESCALATED_PO | ON_ESCALATION | KERNEL |
| CONSENSUS_CHECK | `escalate` | `round >= max_rounds`, no PO | ESCALATED_USER | ON_ESCALATION | KERNEL |
| ESCALATED_PO | `po_resolved` | `output_status == COMPLETED with decision` | RESOLVED | ON_DEBATE_RESOLVED | PRODUCT_OWNER |
| ESCALATED_PO | `po_unresolved` | — | ESCALATED_USER | ON_ESCALATION | PRODUCT_OWNER |
| ESCALATED_USER | `user_resolved` | — | RESOLVED | ON_DEBATE_RESOLVED | USER |
| any non-terminal | `abandon` | `budget_exhausted OR user` | ABANDONED | — | KERNEL, USER |

### 3.6 RC lifecycle `rc_workflow v1.0` (§76) `[Stage 11]`

| From | Event | Guard(s) | To | Hooks | Who |
|---|---|---|---|---|---|
| BUILDING | `build_ok` | `build_evidence_present(all targets)` | QC | ON_BUILD_SUCCESS | KERNEL |
| BUILDING | `build_failed` | — | REJECTED | ON_BUILD_FAILURE | KERNEL |
| QC | `qc_pass` | `qc_report_evidence`, `no_open_blocker_bugs` | PASSED | ON_QC_RESULT | QC |
| QC | `qc_reject` | `rejection_bugs_created` | REJECTED | ON_QC_RESULT, ON_BUG_CREATED | QC |
| REJECTED | `next_rc` | `rejection_bugs_complete` | BUILDING (new RC, number+1) | — | KERNEL |
| PASSED | `release` | `approval(USER)` (§77 protected) | RELEASED | — | USER, UA_RELEASE (with approval) |

### 3.7 Improvement rollout lifecycle `rollout_workflow v1.0` (§109) `[Stage 10]`

| From | Event | Guard(s) | To | Who |
|---|---|---|---|---|
| DRAFT | `experiment` | `candidate.state == APPROVED`, `experiment defined` (§107) or shadow (§108) | EXPERIMENTAL | PROCESS_ARCHITECT |
| EXPERIMENTAL | `limited` | `experiment.result_evidence non-empty`, `approval per risk tier` (§104) | LIMITED (opt-in projects) | ORCHESTRATOR (LOW) / PRODUCT_OWNER (MEDIUM) / USER (HIGH) |
| LIMITED | `default` | `>= 1 project ran it through a phase`, `metrics not worse` (§116), changelog entry (§120) | DEFAULT | same tiers |
| DEFAULT | `deprecate` | `successor DEFAULT exists` | DEPRECATED | PROCESS_ARCHITECT |
| EXPERIMENTAL / LIMITED | `rollback` | — | DRAFT | any approver |

---

## 4. Routing table (TaskRouter)

| Work item kind | State | Role | Purpose | Notes |
|---|---|---|---|---|
| FEATURE | IDEA | ORCHESTRATOR | PLAN | §131 "Plan": decomposes to stories (`new_tasks`), creates Jira (kernel) |
| FEATURE | DISCOVERY | DESIGN_LEADER (if enabled) else ORCHESTRATOR | DESIGN | |
| FEATURE | DESIGN | LEAD_DEV | DESIGN | §131 technical design → FeatureContext.architecture |
| FEATURE | QC | QC | QC | feature-level acceptance |
| STORY/TASK | READY/REWORK | `contract.owner_role` (default SENIOR_DEV) | IMPLEMENT | |
| STORY/TASK | READY_FOR_REVIEW | `contract.reviewer_role` (default LEAD_DEV) | REVIEW | cross-model preferred (§23) |
| STORY/TASK | QC | QC | QC | |
| BUG | DISCOVERY | LEAD_DEV | TRIAGE | severity/owner; may propose `wont_fix` |
| BUG | READY/REWORK | `contract.owner_role` | IMPLEMENT | |
| BUG | READY_FOR_REVIEW | LEAD_DEV | REVIEW | |
| BUG | QC | QC | QC | re-test |
| PHASE | REWORK | PRODUCT_OWNER (if enabled) else ORCHESTRATOR | PLAN | §71 feedback → work |
| PHASE | CHANGE_ANALYSIS | LEAD_DEV + PRODUCT_OWNER | ANALYSIS | §72 |
| PHASE | EVIDENCE_REVIEW | PROCESS_ARCHITECT (if enabled) | RETRO | §115 narrative |
| DEBATE | IN_ROUND | each participant | DEBATE | one run per participant per round |
| DEBATE | ESCALATED_PO | PRODUCT_OWNER | DEBATE | |

Scheduling order: BLOCKED resolution first, then bugs by severity, then stories by `priority` then `created_at`; respects `max_parallel_agents`, `RuntimePolicy.max_parallel_runs` per role, `can_run_parallel`.

---

## 5. Algorithms

### 5.1 Scheduler tick

```text
 1. if project.paused → return 0
 2. items = WorkflowManager.ready_items(project.current_phase_id)      # has scheduled role per §4, deps complete, in scope
 3. sort items (BLOCKED-resolvable first, bug severity, priority, created_at)
 4. for item in items while running_count < max_parallel_agents:
 5.     route = TaskRouter.route(item, item.state)
 6.     if role busy (max_parallel_runs) or not can_run_parallel(item, each running) → continue
 7.     key = f"schedule:{item.id}:{item.state}:{item.state_version}"; if IdempotencyStore.has(key) → continue
 8.     budgets = BudgetManager.ensure(TASK, item.id, policy.budget_policy) + applicable ROLE/PHASE/PROJECT/GLOBAL
 9.     effort = EffortManager.resolve(policy.effort_policy, item, item.state, escalation_bump=0, headroom)
10.     routing = ModelRouter.select(route.role, policy.model_policy, route.profile, effort.effective)
11.     agent = AgentManager.instantiate(route.role, item, routing.model_id, routing.effort, [b.id for b in budgets], ready_env_keys)
12.     handover = latest Handover for item with to_run_id None (if any)
13.     run = AgentExecutor.start(agent, item, route.purpose, handover=handover); record key → run.id; started += 1
14. return started
```

### 5.2 Effort resolution (§18–§19) — `EffortManager.resolve`

```text
 Input: policy: EffortPolicy, item, state, escalation_bump: int, headroom: dict[BudgetDimension, float]
 ORDER = [LOW, MEDIUM, HIGH, VERY_HIGH]
 1. base = policy.complexity_map[item.contract.complexity] if item has contract else policy.default      # Task Complexity
 2. idx = max(ORDER.index(base), ORDER.index(policy.default))                                              # Role Default floor
 3. idx += policy.risk_bump[item.risk]                                                                      # Risk
 4. idx += policy.stage_bump.get(state, 0)                                                                  # Workflow Stage (REWORK +1)
 5. idx += escalation_bump                                                                                  # Agent Escalation (§19 upgrade carried into next run)
 6. idx = clamp(idx, ORDER.index(policy.min), ORDER.index(policy.max)); clamped_by_policy = (idx changed)
 7. while idx > 0 and estimated_cost(ORDER[idx]) > headroom[COST_USD]: idx -= 1; clamped_by_budget = True
      estimated_cost(e) = role historical mean cost at effort e (from cost_records) or static table {LOW:1, MEDIUM:3, HIGH:8, VERY_HIGH:20} USD
 8. return EffortResolution(role_default=policy.default, complexity_component=base, …, effective=ORDER[idx])

 Dynamic change (§19) — EffortManager.request_change(run, req):
 a. target = req.target; if not policy.min <= target <= policy.max → DENY (log) → return run.effort
 b. if req.direction == UPGRADE and not policy.auto_approve_upgrade_within_budget → ApprovalRequest(ORCHESTRATOR); await
 c. if UPGRADE and estimated_cost(target) - estimated_cost(run.effort) > headroom[COST_USD] → DENY (BUDGET) → observation
 d. persist run.effort_next = target; fire ON_EFFORT_CHANGE; ledger EFFORT_CHANGED; the change applies on the *next* run
    of this work item (current provider session keeps its effort; adapter sessions are not reconfigurable mid-run).
    If the agent returns PARTIAL, the scheduler immediately re-queues with escalation_bump so the upgrade takes effect.
```

### 5.3 Fallback (§21–§22) — `ModelRouter.select` / `fallback`, executor side effects, recovery

```text
 select(role, policy, profile, effort, exclude, task_override):
 1. candidates = [task_override] if task_override and policy.allow_task_override else []
    candidates += policy.preferred + policy.fallback           (ordered, de-duplicated)
 2. remove: policy.restricted, registry.enabled == False (→ MODEL_DISABLED), exclude
 3. for m in candidates:
      d = registry[m]
      if any(d.capabilities[c] < 3 for c in profile.required_capabilities ∪ policy.required_capabilities) → reject(m, "capability")   # §16
      if profile.estimated_context_tokens > 0.6 * d.context_window_tokens → reject(m, "context")
      if effort not in d.supports_effort_levels and map_effort cannot degrade → reject(m, "effort")
      if policy.cross_model_review and profile.implementer_model_id == m and another candidate survives → defer m to end   # §23
      if not adapter_for(m).health().ok → reject(m, "health")
      return RoutingDecision(m, effort, is_fallback = m not in policy.preferred, rejected)
 4. raise BlockedProvider(rejected)

 fallback — split between runtime.AgentExecutor (side effects) and ModelRouter.fallback(FallbackRequest) (decision); E01-S28:
 5. [executor] handover = build_handover(run, reason="FALLBACK", latest PARTIAL_OUTPUT or None)
               ckpt = CheckpointManager.checkpoint(run, HANDOFF, handover=handover)              # §22 before switching
 7. [router]   if request.fallbacks_so_far >= request.max_fallbacks → raise BlockedProvider([(current_model_id, "max_fallbacks")])
 8. [router]   exclude = [current_model_id] + every model of the same provider if trigger ∈ PROVIDER_WIDE_TRIGGERS
               (= {PROVIDER_OUTAGE, QUOTA_EXHAUSTED, RATE_LIMIT})
               CONTEXT_OVERFLOW: profile.estimated_context_tokens = measured_context_tokens; survivors by context window desc
               BUDGET_RESTRICTION: survivors by output_cost_per_mtok_usd asc
 9. [router]   decision = select(role, policy, profile, effort, exclude=exclude); decision.is_fallback = True; decision.trigger = trigger
               (pure: no ledger, no checkpoint, no run start)
 6. [executor] ledger MODEL_FALLBACK{trigger, from=run.model_id, to=decision.model_id, handover_id, checkpoint_id, rejected};
               fire ON_MODEL_FALLBACK with the same payload (chains ON_AGENT_HANDOFF; the handoff attachment is a no-op because
               checkpoint_id and handover_id are present — ARCHITECTURE.md §4.1)
10. [executor] one UnitOfWork: run.state = HANDED_OVER, item unassigned, ledger AGENT_RUN_ENDED{state: HANDED_OVER, trigger};
               new_run = AgentExecutor.start(agent with decision.model_id/effort, item, purpose, handover=handover,
                                             parent_run_id=run.id, routing=decision); new_run.fallbacks = run.fallbacks + 1
               close_handover(handover.id, new_run.id)       # §132 "Claude assumes SeniorDev role, reads handover, continues"
    BlockedProvider (step 7 or 9) → run.state = BLOCKED_PROVIDER; ledger ERROR{kind: BLOCKED_PROVIDER}; ApprovalRequest(ESCALATION, USER)
               (§21 level 3); item unassigned; ON_TASK_FAILED. The HANDOFF checkpoint and handover remain for a manual resume.

 Execution order is 5 → 7–9 → 6 → 10 (the ledger event names the target model, so it follows the decision).

 recovery path (ARCHITECTURE.md §5.3 step 5, runtime.RecoveryManager) — not a FallbackRequest:
    decision = select(role, policy, profile, ckpt.effort, exclude=[ckpt.model_id] if that adapter is unhealthy else [])
    if decision.model_id != ckpt.model_id → ledger MODEL_FALLBACK{trigger: PROVIDER_OUTAGE, from: ckpt.model_id, to: decision.model_id}
                                            and fire ON_MODEL_FALLBACK
    the interrupted run ends HANDED_OVER; the new run starts with the handover (reason RECOVERY) and parent_run_id = interrupted run
    E01-S28: after a native resume the interrupted run ends HANDED_OVER too (continued by another run); both paths write
    its AGENT_RUN_ENDED{state: HANDED_OVER, mode}
    E01-B02 step 4 (ensure worktree): when no open handover exists, SandboxManager.adopt(run, run, item) runs before
    build_handover and the HANDOFF checkpoint (an existing directory is kept, a deleted one is re-added on run.branch).
    E01-B02 failure path: any exception while recovering one run → in one UnitOfWork the run goes FAILED
    (failure_reason "recovery: <detail>"), the item is unassigned when assigned_run_id == run.id, and AGENT_RUN_ENDED
    {state: FAILED, failure_reason, mode: "recovery"} (outcome FAILED) is written; after commit ON_TASK_FAILED fires
    (a hook failure is logged). The run is reported in RecoveryReport.failed and the loop continues. A run already
    HANDED_OVER when the error is raised (its continuation started) keeps that state and its single AGENT_RUN_ENDED.

 E01-B04: every AGENT_RUN_ENDED payload (executor: COMPLETED, FAILED*, HANDED_OVER, BLOCKED_*, CANCELLED; recovery:
 HANDED_OVER and the failure path) carries handover_in_id = the ended run's handover_in_id (null for a run that did not
 start from a handover). TelemetryManager's failed_handoffs metric counts AGENT_RUN_ENDED with outcome FAILED and a
 non-null handover_in_id.
```

### 5.4 Context-first retrieval (§40, §42) — `ContextManager.build` (ADR-0012)

```text
 Input: ContextRequest(work_item_id, role, effort, token_budget, include_source, code_graph_depth)
 1. item = WorkflowManager.get(id); feature = item if FEATURE else ancestor FEATURE; head = GitProvider.head(worktree)
 2. MANDATORY (always included, in this order, never trimmed) :
      a. WORK_ITEM: item + contract (§40 step 1)
      b. WORKFLOW_STATE: state, transition history tail(5), fix_loops, blockers (§40 step 5)
      c. HANDOVER: latest open handover for item (if any)
      d. FEATURE_CONTEXT or BUG_CONTEXT: full document (§40 step 2); + PROJECT_CONTEXT sections {goals, technical_constraints, coding_conventions, architecture_overview}
      e. DECISION: DecisionManager.relevant_for(item, feature.affected_systems) with status ACCEPTED (§40 step 3)
      f. APPROVED_ARTIFACT: metadata (not payload) for artifacts whose scope covers item/feature/phase (§40 step 4)
 3. For each mandatory memory doc: fa = MemoryManager.assess_freshness(doc, head); if fa.status != CURRENT → requires_verification = True; fire ON_CONTEXT_STALE
 4. CANDIDATES (scored; §40 steps 6–7):
      g. CODE_GRAPH: CodeGraphProvider.neighbors(seeds = feature.relevant_files ∪ affected_systems, depth = code_graph_depth) → one item per neighbourhood summary
      h. SOURCE_FILE: files = feature.relevant_files ∪ graph nodes(kind=file) ∪ item.contract-mentioned paths; each file an item (content trimmed to 400 lines around symbols)
      i. EVIDENCE: latest evidence per kind for the item (QC reports, failing tests)
      j. related DECISIONs (PROPOSED/SUPERSEDED) and sibling story contexts
 5. score(c) = relevance(c) × freshness(c) × role_weight(c)
      relevance: direct link to item 1.0 | parent feature 0.8 | affected_systems overlap 0.6 | graph distance d → 0.5 / d | keyword match in title 0.3
      freshness: CURRENT 1.0 | POSSIBLY_STALE 0.7 | INVALID 0.0 (excluded unless directly linked, then included with requires_verification)
      role_weight: SOURCE_FILE ×1.2 for SENIOR_DEV/LEAD_DEV, ×0.5 for QC/PO/DESIGN; EVIDENCE ×1.5 for QC/LEAD_DEV review; CODE_GRAPH ×1.3 at effort ≥ HIGH
 6. budget_left = token_budget − tokens(mandatory); greedily add candidates by score desc while tokens(c) ≤ budget_left; count excluded
 7. order items: mandatory in §40 order, then CODE_GRAPH, then SOURCE_FILE, then rest (so the agent reads context → decisions → graph → source → execution, §6.8)
 8. return ContextBundle(items, total_tokens_estimate, excluded_count, head_commit = head)
 tokens(x) = len(text) / 3.5 (estimate; adapters may refine with provider token counting)
```

### 5.5 Freshness classification (§42) — `MemoryManager.assess_freshness`

```text
 Input: doc (front_matter.freshness F, relevant_files R), head
 1. if F is None → POSSIBLY_STALE("never stamped")
 2. if not GitProvider.is_ancestor(F.commit, head) and F.commit != head → INVALID("stamp commit not in history")   # rebased/removed
 3. missing = [p for p in R if not exists(worktree/p)]; if missing → INVALID(f"relevant files missing: {missing}")
 4. changed = GitProvider.changed_between(F.commit, head, paths=R); if changed → POSSIBLY_STALE("relevant files changed", changed)
 5. if now − F.timestamp > max_age_days (default 30) → POSSIBLY_STALE("age")
 6. else CURRENT
 Cache result in memory_index(freshness_status, freshness_checked_at) keyed by (path, head).
```

### 5.6 Phase gate intake (§70–§72)

```text
 decide_phase(phase, decision, feedback):
 GO:      phase_event(decide:GO) → COMPLETE; next = phases[ordinal+1]; if next → phase_event(next, start)
 REWORK:  phase_event(decide:REWORK) → REWORK; create Task(kind=TASK, title="Rework intake: <phase>", contract.goal=feedback,
          owner_role=PRODUCT_OWNER|ORCHESTRATOR, purpose=PLAN) → agent decomposes feedback into new_tasks (§71 example) inside phase scope;
          on COMPLETED → phase_event(rework_planned) → ACTIVE
 CHANGE:  phase_event(decide:CHANGE) → CHANGE_ANALYSIS; create ANALYSIS task for LEAD_DEV+PO producing ChangePlan evidence listing §72 items
          (affected GDD, specs, Jira work, code via CodeGraphProvider.impact, assets, save data, tests, future phases) → ApprovalRequest(USER)
          → approved → phase_event(change_plan_approved) → PLANNED → plan_phase() again
 STOP:    phase_event(decide:STOP) → STOPPED; Orchestrator.pause(); checkpoint all
 Every decision: ledger PHASE_GATE_DECISION; ImprovementManager.observe(source_signal="user_gate_<decision>") (§118)
```

---

## 6. CLI surface (`walk`) `[MVP]` unless marked

Global options: `--repo PATH` (default: cwd ancestor containing `.ai/` or `GDD/`), `--json` (machine output, §87), `--verbose`.

| Command | Arguments / options | Behaviour |
|---|---|---|
| `walk bootstrap` | `--gdd PATH...` `--provider local\|jira` `--name NAME` `--key KEY` `--unity-path PATH` `--yes` | §25: preflight → Production Kit (kernel defaults copied to `.ai/agents/`; `permissions.yaml` starts as an empty narrowing file) → `.ai/` init (project.md skeleton from GDD headings, kernel-versions.yaml, environment.yaml, .gitignore) → DB create + migrate. Idempotent. |
| `walk doctor` | `--fix` `--strict` | §26 preflight; prints `EnvironmentManifest`; `--fix` installs guard hooks, regenerates skill projections, repairs index; exit 1 on missing required. |
| `walk run` | `--max-parallel N` `--webhook-port PORT` `--poll-interval S` `--once` `--skip-preflight` | Start kernel daemon (ARCHITECTURE.md §3.4). `--once` = single tick then exit (tests). |
| `walk status` | `--watch` | `KernelStatus` (§87): phase, progress, active runs, blocked, pending approvals, budgets. |
| `walk feature add` | `TITLE` `--description TEXT` `--gdd REF...` `--execute` | §131 user feature → Feature(IDEA); `--execute` requires daemon and triggers PLAN run. |
| `walk work list` | `--state S...` `--kind K...` `--phase ID` | |
| `walk work show` | `ID` | item + contract + transitions + runs + cost. |
| `walk work transition` | `ID EVENT` `--reason TEXT` | Raises event as USER (guards still apply). |
| `walk work cancel` | `ID --reason TEXT` | §93 |
| `walk work priority` | `ID P0..P3` | §93 |
| `walk work force-review` | `ID` | §93 |
| `walk phase list` | | |
| `walk phase plan` | `ID` | `[Stage 6]` GDD compile into phase |
| `walk phase start` | `ID` | |
| `walk phase review` | `ID` | request_phase_review → evidence package path |
| `walk phase gate` | `ID --decision GO\|REWORK\|CHANGE\|STOP` `--feedback FILE\|TEXT` | §70 |
| `walk phase evidence` | `ID` `--open` | print/open evidence package |
| `walk handover show` | `ITEM_ID` \| `HO_ID` | latest/specified handover |
| `walk handover create` | `RUN_ID --reason REASON` | force checkpoint + handover (operator) |
| `walk runs list` / `walk runs show RUN_ID` / `walk runs cancel RUN_ID` | | |
| `walk pause` / `walk resume` | `[--agent RUN_ID]` | §93 |
| `walk approve` / `walk deny` | `APV_ID --note TEXT` | §92 |
| `walk approvals` | `--pending` | |
| `walk decisions list` / `show ID` / `override ID --outcome TEXT --rationale TEXT` | | §44, §93 |
| `walk debates list` / `show ID` | | `[MVP minimal]` |
| `walk ledger tail` | `--follow` `--since SEQ` | |
| `walk ledger query` | `--kind K...` `--item ID` `--run ID` `--phase ID` `--since ISO` `--until ISO` `--limit N` | |
| `walk report` | `task\|feature\|phase\|project\|cost\|improvement SUBJECT_ID` `--write` | §83; `--write` saves to `.ai/reports/` |
| `walk cost` | `--item ID` \| `--phase ID` \| `--project` | §85 |
| `walk policy set-model` | `ROLE --preferred M... --fallback M...` | §93 Change Model Policy (writes policies.yaml) |
| `walk policy set-autonomy` | `LEVEL` | §93 |
| `walk skills list` / `sync` / `check-drift` | | ADR-0007 |
| `walk memory index` / `walk memory freshness [DOC_ID]` | | §42 |
| `walk improvement observations` / `candidates` / `retro PHASE_ID` / `promote OBS_ID` | | `[Stage 10]`; `retro` and `observations` `[MVP skeleton]` |
| `walk db migrate` / `walk db backup PATH` | | |
| `walk version` | | kernel version + pinned behavior versions |

Exit codes: 0 ok · 1 validation/config error · 2 guard rejected / permission denied · 3 daemon required but not running · 4 preflight failed.
