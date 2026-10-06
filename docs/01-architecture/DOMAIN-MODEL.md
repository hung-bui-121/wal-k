# WAL-K Domain Model

**Status:** Draft v1. Companion to `ARCHITECTURE.md` and `INTERFACES.md`. Spec citations `§NN` refer to `requirements/WAL_K_REQ.md`.

All models are **pydantic v2** (ADR-0001) and live in `src/walk/<package>/models.py` of the package named in each section header. Code blocks are the normative definitions: field names, types, defaults and docstrings are to be implemented exactly as shown. Imports are listed once per section and are assumed for the rest of that section.

---

## 1. Conventions

### 1.1 Base model and common imports

```python
# src/walk/common/models.py
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Any, Literal, NewType

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class WalkModel(BaseModel):
    """Base for every kernel data contract.

    - extra="forbid": unknown fields are a validation error (contracts are explicit).
    - validate_assignment=True: mutations are validated.
    - Enums are kept as enum members in Python; serialised by value.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True, populate_by_name=True)


class FrozenModel(WalkModel):
    """Immutable value object (ledger events, evidence, checkpoints)."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


def utcnow() -> datetime:
    """Single clock function; tests patch `walk.common.clock.Clock`."""
    return datetime.now(timezone.utc)


JsonDict = dict[str, Any]


class Actor(FrozenModel):
    """Who did something: a role, optionally the model and run that executed it. Used by memory, telemetry, improvement."""
    role: "AgentRole"                 # walk.common.roles
    model_id: "ModelId | None" = None
    run_id: "RunId | None" = None
```

### 1.2 Identifier types

```python
# src/walk/common/ids.py
ProjectKey = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9]{1,9}$")]      # e.g. "ZOMB"
PhaseId = Annotated[str, StringConstraints(pattern=r"^PHASE-\d{2,}$")]
EpicId = Annotated[str, StringConstraints(pattern=r"^EPIC-\d{3,}$")]
FeatureId = Annotated[str, StringConstraints(pattern=r"^FEAT-\d{4,}$")]
StoryId = Annotated[str, StringConstraints(pattern=r"^STORY-\d{4,}$")]
TaskId = Annotated[str, StringConstraints(pattern=r"^TASK-\d{4,}$")]
BugId = Annotated[str, StringConstraints(pattern=r"^BUG-\d{4,}$")]
WorkItemId = Annotated[str, StringConstraints(pattern=r"^(EPIC|FEAT|STORY|TASK|BUG)-\d{3,}$")]
DecisionId = Annotated[str, StringConstraints(pattern=r"^DEC-\d{4,}$")]
DebateId = Annotated[str, StringConstraints(pattern=r"^DEB-\d{4,}$")]
EvidenceId = Annotated[str, StringConstraints(pattern=r"^EVD-\d{6,}$")]
ApprovedArtifactId = Annotated[str, StringConstraints(pattern=r"^APR-\d{4,}$")]
HandoverId = Annotated[str, StringConstraints(pattern=r"^HO-\d{4,}$")]
ApprovalRequestId = Annotated[str, StringConstraints(pattern=r"^APV-\d{4,}$")]
ReleaseCandidateId = Annotated[str, StringConstraints(pattern=r"^RC-\d{2,}$")]
ObservationId = Annotated[str, StringConstraints(pattern=r"^OBS(-K)?-\d{4,}$")]      # OBS-K-… = kernel scope
ImprovementId = Annotated[str, StringConstraints(pattern=r"^IMP-\d{2,}$")]
PatternId = Annotated[str, StringConstraints(pattern=r"^PATTERN-\d{3,}$")]
AntiPatternId = Annotated[str, StringConstraints(pattern=r"^ANTI-\d{3,}$")]
ExperimentId = Annotated[str, StringConstraints(pattern=r"^EXP-\d{4,}$")]
RetrospectiveId = Annotated[str, StringConstraints(pattern=r"^RETRO-[A-Z]+-[A-Z0-9-]+$")]  # RETRO-PHASE-03, RETRO-FEAT-0012
RunId = Annotated[str, StringConstraints(pattern=r"^RUN-[0-9A-HJKMNP-TV-Z]{26}$")]          # ULID
CheckpointId = Annotated[str, StringConstraints(pattern=r"^CKP-[0-9A-HJKMNP-TV-Z]{26}$")]   # ULID
LedgerEventId = Annotated[str, StringConstraints(pattern=r"^LED-[0-9A-HJKMNP-TV-Z]{26}$")]  # ULID
ModelId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_-]+/[A-Za-z0-9._-]+$")]       # "<provider>/<model>", e.g. "claude/claude-opus-5-5", "codex/gpt-5-codex"
SkillName = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
ToolName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")]   # "git.commit", "jira.create_bug", "bash"
HookNameStr = Annotated[str, StringConstraints(pattern=r"^on_[a-z_]+$")]
Sha = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{7,64}$")]
```

---

## 2. ID conventions

| Entity | Prefix | Min width | Allocator | Example |
|---|---|---|---|---|
| Project | project key | – | user at bootstrap | `ZOMB` |
| Phase | `PHASE-` | 2 | `id_sequences` | `PHASE-03` |
| Epic | `EPIC-` | 3 | `id_sequences` | `EPIC-004` |
| Feature | `FEAT-` | 4 | `id_sequences` | `FEAT-0012` |
| Story | `STORY-` | 4 | `id_sequences` | `STORY-0412` |
| Task | `TASK-` | 4 | `id_sequences` | `TASK-0931` |
| Bug | `BUG-` | 4 | `id_sequences` | `BUG-0031` |
| Decision | `DEC-` | 4 | `id_sequences` | `DEC-0007` |
| Debate | `DEB-` | 4 | `id_sequences` | `DEB-0002` |
| Evidence | `EVD-` | 6 | `id_sequences` | `EVD-000123` |
| Approved artifact | `APR-` | 4 | `id_sequences` | `APR-0003` |
| Handover | `HO-` | 4 | `id_sequences` | `HO-0005` |
| Approval request | `APV-` | 4 | `id_sequences` | `APV-0011` |
| Release candidate | `RC-` | 2 | `id_sequences` | `RC-02` |
| Observation | `OBS-` / `OBS-K-` | 4 | project / kernel `id_sequences` | `OBS-0001`, `OBS-K-0009` |
| Improvement candidate | `IMP-` | 2 | kernel `id_sequences` | `IMP-31` |
| Pattern / Anti-pattern | `PATTERN-` / `ANTI-` | 3 | kernel `id_sequences` | `PATTERN-021`, `ANTI-017` |
| Experiment | `EXP-` | 4 | kernel `id_sequences` | `EXP-0003` |
| Retrospective | `RETRO-<SCOPE>-<id>` | – | derived | `RETRO-PHASE-03` |
| Agent run / Checkpoint / Ledger event | `RUN-` / `CKP-` / `LED-` + ULID | 26 | ULID (time-ordered, generated in-process) | `RUN-01J9Z8K3M4N5P6Q7R8S9T0V1W` |

Rules: sequence IDs are allocated from the SQLite `id_sequences` table in the same transaction as the insert (single source of truth; never from file scans). Width is a *minimum*; parsers accept any width ≥ minimum. Jira keys (`GAME-381`) are **external refs**, stored in `WorkItem.external_ref`, never used as kernel IDs.

---

## 3. Enumerations

```python
# src/walk/common/roles.py
class AgentRole(StrEnum):
    """§10 required roles + §11 optional + §101 improvement role."""
    ORCHESTRATOR = "ORCHESTRATOR"      # §10.1
    PRODUCT_OWNER = "PRODUCT_OWNER"    # §10.2
    SCRUM_MASTER = "SCRUM_MASTER"      # §10.3
    DESIGN_LEADER = "DESIGN_LEADER"    # §10.4
    ART_DIRECTOR = "ART_DIRECTOR"      # §10.5
    LEAD_DEV = "LEAD_DEV"              # §10.6
    SENIOR_DEV = "SENIOR_DEV"          # §10.7
    QC = "QC"                          # §10.8
    UA_RELEASE = "UA_RELEASE"          # §10.9
    GAME_DIRECTOR = "GAME_DIRECTOR"    # §11 optional
    PROCESS_ARCHITECT = "PROCESS_ARCHITECT"  # §101 Kernel Improvement Agent
    USER = "USER"                      # the human; used as actor in ledger/approvals, never instantiated as an agent
    KERNEL = "KERNEL"                  # system actor for automatic transitions
```

```python
# src/walk/workflow/models.py (enums)
class WorkItemKind(StrEnum):
    EPIC = "EPIC"
    FEATURE = "FEATURE"
    STORY = "STORY"
    TASK = "TASK"
    BUG = "BUG"


class WorkItemState(StrEnum):
    """§53 states refined by §61 (REVIEW → READY_FOR_REVIEW + LEAD_DEV_REVIEW), §58 BLOCKED, §93 CANCELLED.

    Bug lifecycle (§64) maps onto the same enum: Triage=DISCOVERY, Assigned=READY, Fix=IMPLEMENTING,
    Review=READY_FOR_REVIEW/LEAD_DEV_REVIEW, Re-test=QC, Close=COMPLETE, Reopen=REWORK (ADR-0010).
    """
    IDEA = "IDEA"
    DISCOVERY = "DISCOVERY"
    DESIGN = "DESIGN"
    READY = "READY"
    BLOCKED = "BLOCKED"
    IMPLEMENTING = "IMPLEMENTING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    LEAD_DEV_REVIEW = "LEAD_DEV_REVIEW"
    INTEGRATION = "INTEGRATION"
    QC = "QC"
    REWORK = "REWORK"
    PHASE_REVIEW = "PHASE_REVIEW"
    USER_GATE = "USER_GATE"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"


class PhaseState(StrEnum):
    """§66–§72 phase lifecycle."""
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    EVIDENCE_REVIEW = "EVIDENCE_REVIEW"   # §69 package being assembled
    USER_GATE = "USER_GATE"               # §68/§70 waiting for user
    REWORK = "REWORK"                     # §71
    CHANGE_ANALYSIS = "CHANGE_ANALYSIS"   # §72
    COMPLETE = "COMPLETE"
    STOPPED = "STOPPED"


class PhaseDecision(StrEnum):
    """§70 user decisions at the Phase Gate."""
    GO = "GO"
    REWORK = "REWORK"
    CHANGE = "CHANGE"
    STOP = "STOP"


class ReleaseCandidateState(StrEnum):
    """§76."""
    BUILDING = "BUILDING"
    QC = "QC"
    REJECTED = "REJECTED"
    PASSED = "PASSED"
    RELEASED = "RELEASED"


class DoneDimension(StrEnum):
    """§6.5 Feature Done = sum of applicable dimensions."""
    FUNCTIONAL = "FUNCTIONAL"
    INTEGRATED = "INTEGRATED"
    DESIGN_VALIDATED = "DESIGN_VALIDATED"
    UX_COMPLETE = "UX_COMPLETE"
    ART_COMPLETE = "ART_COMPLETE"
    PERFORMANCE_ACCEPTABLE = "PERFORMANCE_ACCEPTABLE"
    TESTED = "TESTED"
    QC_ACCEPTED = "QC_ACCEPTED"


class Priority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class Risk(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Severity(StrEnum):
    """Bug severity (§10.8: QC identifies existence and severity)."""
    BLOCKER = "BLOCKER"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    TRIVIAL = "TRIVIAL"


class TransitionSource(StrEnum):
    AGENT = "AGENT"
    USER = "USER"
    KERNEL = "KERNEL"
    EXTERNAL = "EXTERNAL"            # Jira webhook / poll
    EXTERNAL_REJECTED = "EXTERNAL_REJECTED"
```

```python
# src/walk/common/enums.py — cross-cutting enums (ADR-0009 D-1): referenced by L1 telemetry and most L2 packages
class Effort(StrEnum):
    """§17 provider-independent effort levels; adapters translate (ADR-0011)."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class LearningScope(StrEnum):
    """§110 project vs kernel learning."""
    PROJECT = "PROJECT"
    KERNEL = "KERNEL"


class ImprovementScope(StrEnum):
    """§100 what may be improved; also the `kind` of a BehaviorVersion (§105)."""
    WORKFLOW = "WORKFLOW"
    CONSTITUTION = "CONSTITUTION"
    SKILL = "SKILL"
    PROMPT = "PROMPT"
    CONTEXT_FORMAT = "CONTEXT_FORMAT"
    STORY_TEMPLATE = "STORY_TEMPLATE"
    MODEL_ROUTING = "MODEL_ROUTING"
    EFFORT_POLICY = "EFFORT_POLICY"
    TOOL_USAGE = "TOOL_USAGE"
    HOOK = "HOOK"
    QUALITY_GATE = "QUALITY_GATE"
```

```python
# src/walk/model_router/models.py (enums)
class Capability(StrEnum):
    """§16 capability dimensions."""
    CODING = "CODING"
    ARCHITECTURE = "ARCHITECTURE"
    REPOSITORY_NAVIGATION = "REPOSITORY_NAVIGATION"
    LONG_CONTEXT_REASONING = "LONG_CONTEXT_REASONING"
    DESIGN_REASONING = "DESIGN_REASONING"
    VISUAL_REASONING = "VISUAL_REASONING"
    TOOL_USE = "TOOL_USE"
    REVIEW = "REVIEW"
    PLANNING = "PLANNING"


class FallbackTrigger(StrEnum):
    """§21 fallback triggers."""
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    TOKEN_LIMIT = "TOKEN_LIMIT"
    PROVIDER_OUTAGE = "PROVIDER_OUTAGE"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    CONTEXT_OVERFLOW = "CONTEXT_OVERFLOW"
    TOOL_INCOMPATIBILITY = "TOOL_INCOMPATIBILITY"
    BUDGET_RESTRICTION = "BUDGET_RESTRICTION"
    MODEL_DISABLED = "MODEL_DISABLED"
    REPEATED_OUTPUT_INVALID = "REPEATED_OUTPUT_INVALID"   # kernel-added: output failed validation after repair turn
```

```python
# src/walk/telemetry/models.py (enums)
class EvidenceKind(StrEnum):
    """§6.6 evidence forms. `rank` (§47) is a property, see Evidence.rank."""
    PLAYER_TELEMETRY = "PLAYER_TELEMETRY"
    PLAYTEST = "PLAYTEST"
    GAMEPLAY_RECORDING = "GAMEPLAY_RECORDING"
    REPRODUCIBLE_BENCHMARK = "REPRODUCIBLE_BENCHMARK"
    PERFORMANCE_METRICS = "PERFORMANCE_METRICS"
    PROFILER_RESULT = "PROFILER_RESULT"
    AUTOMATED_TEST = "AUTOMATED_TEST"
    BUILD_ARTIFACT = "BUILD_ARTIFACT"
    SCREENSHOT = "SCREENSHOT"
    LOG = "LOG"
    QC_REPORT = "QC_REPORT"
    REPRODUCTION_PROOF = "REPRODUCTION_PROOF"
    PROJECT_DATA = "PROJECT_DATA"          # ledger/cost/coverage facts
    ESTABLISHED_PATTERN = "ESTABLISHED_PATTERN"
    EXPERT_REASONING = "EXPERT_REASONING"
    PREFERENCE = "PREFERENCE"


# §47 ranking: higher = stronger. Kinds sharing a tier share a value.
EVIDENCE_RANK: dict[EvidenceKind, int] = {
    EvidenceKind.PLAYER_TELEMETRY: 7,
    EvidenceKind.PLAYTEST: 6,
    EvidenceKind.GAMEPLAY_RECORDING: 6,
    EvidenceKind.REPRODUCIBLE_BENCHMARK: 5,
    EvidenceKind.PERFORMANCE_METRICS: 5,
    EvidenceKind.PROFILER_RESULT: 5,
    EvidenceKind.AUTOMATED_TEST: 5,
    EvidenceKind.REPRODUCTION_PROOF: 5,
    EvidenceKind.BUILD_ARTIFACT: 4,
    EvidenceKind.SCREENSHOT: 4,
    EvidenceKind.LOG: 4,
    EvidenceKind.QC_REPORT: 4,
    EvidenceKind.PROJECT_DATA: 4,
    EvidenceKind.ESTABLISHED_PATTERN: 3,
    EvidenceKind.EXPERT_REASONING: 2,
    EvidenceKind.PREFERENCE: 1,
}


class LedgerEventKind(StrEnum):
    """§81 examples + §86 required observability, exhaustive for the kernel."""
    PROJECT_STARTED = "PROJECT_STARTED"
    PHASE_TRANSITION = "PHASE_TRANSITION"
    PHASE_GATE_DECISION = "PHASE_GATE_DECISION"
    RC_TRANSITION = "RC_TRANSITION"
    WORK_ITEM_CREATED = "WORK_ITEM_CREATED"
    WORK_ITEM_TRANSITION = "WORK_ITEM_TRANSITION"
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    AGENT_ASSIGNED = "AGENT_ASSIGNED"
    AGENT_RUN_STARTED = "AGENT_RUN_STARTED"
    AGENT_RUN_ENDED = "AGENT_RUN_ENDED"
    MODEL_SELECTED = "MODEL_SELECTED"
    MODEL_FALLBACK = "MODEL_FALLBACK"
    EFFORT_SET = "EFFORT_SET"
    EFFORT_CHANGED = "EFFORT_CHANGED"
    TOOL_INVOKED = "TOOL_INVOKED"
    TOOL_DENIED = "TOOL_DENIED"
    CHECKPOINT_CREATED = "CHECKPOINT_CREATED"
    HANDOVER_CREATED = "HANDOVER_CREATED"
    RECOVERY_RESUMED = "RECOVERY_RESUMED"
    RETRY = "RETRY"
    ERROR = "ERROR"
    COMMIT = "COMMIT"
    PR_OPENED = "PR_OPENED"
    MERGED = "MERGED"
    BUILD_RESULT = "BUILD_RESULT"
    TEST_RESULT = "TEST_RESULT"
    QC_RESULT = "QC_RESULT"
    BUG_CREATED = "BUG_CREATED"
    DEBATE_OPENED = "DEBATE_OPENED"
    DEBATE_POSITION = "DEBATE_POSITION"
    DEBATE_RESOLVED = "DEBATE_RESOLVED"
    DECISION_RECORDED = "DECISION_RECORDED"
    ESCALATION_RAISED = "ESCALATION_RAISED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_DECIDED = "APPROVAL_DECIDED"
    BUDGET_EVENT = "BUDGET_EVENT"
    COST_RECORDED = "COST_RECORDED"
    CONTEXT_FRESHNESS = "CONTEXT_FRESHNESS"
    CONTEXT_UPDATED = "CONTEXT_UPDATED"
    ARTIFACT_APPROVED = "ARTIFACT_APPROVED"
    EVIDENCE_RECORDED = "EVIDENCE_RECORDED"
    HOOK_EXECUTED = "HOOK_EXECUTED"
    HOOK_FAILED = "HOOK_FAILED"
    USER_OVERRIDE = "USER_OVERRIDE"
    IMPROVEMENT_OBSERVATION = "IMPROVEMENT_OBSERVATION"
    IMPROVEMENT_CANDIDATE = "IMPROVEMENT_CANDIDATE"
    BEHAVIOR_VERSION_CHANGED = "BEHAVIOR_VERSION_CHANGED"
```

```python
# src/walk/decisions/models.py (enums)
class DecisionCategory(StrEnum):
    """§44."""
    TECH = "TECH"
    DESIGN = "DESIGN"
    ART = "ART"
    PRODUCT = "PRODUCT"
    QUALITY = "QUALITY"
    RELEASE = "RELEASE"
    PROCESS = "PROCESS"     # kernel-added: improvement decisions (§106)


class DecisionStatus(StrEnum):
    PROPOSED = "PROPOSED"       # an opinion (Invariant 5)
    ACCEPTED = "ACCEPTED"       # recorded by an authority
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"
    OVERRIDDEN = "OVERRIDDEN"   # by user (§93)


from enum import IntEnum


class AutonomyLevel(IntEnum):
    """§51."""
    LOCAL = 0            # agent decides
    MULTI_AGENT = 1      # debate resolves
    PO = 2               # PO resolves
    USER = 3             # user resolves (incl. Phase Gate)
```

```python
# src/walk/debate/models.py (enum)
class DebateState(StrEnum):
    """§46."""
    OPEN = "OPEN"
    IN_ROUND = "IN_ROUND"
    CONSENSUS_CHECK = "CONSENSUS_CHECK"
    ESCALATED_PO = "ESCALATED_PO"
    ESCALATED_USER = "ESCALATED_USER"
    RESOLVED = "RESOLVED"
    ABANDONED = "ABANDONED"     # budget/round limit without authority available
```

```python
# src/walk/memory/models.py (enums)
class FreshnessStatus(StrEnum):
    """§42."""
    CURRENT = "CURRENT"
    POSSIBLY_STALE = "POSSIBLY_STALE"
    INVALID = "INVALID"


class MemoryDocType(StrEnum):
    PROJECT = "project"
    PROJECT_CONSTITUTION = "project_constitution"
    PHASE = "phase"
    FEATURE = "feature"
    BUG = "bug"
    DECISION = "decision"
    APPROVED = "approved"
    HANDOVER = "handover"
    REPORT = "report"
    EVIDENCE_PACKAGE = "evidence_package"
    RETROSPECTIVE = "retrospective"
    OBSERVATION = "observation"
    IMPROVEMENT_CANDIDATE = "improvement_candidate"
    PATTERN = "pattern"
    ANTI_PATTERN = "anti_pattern"
    CONSTITUTION = "constitution"
    SKILL = "skill"


class ApprovedArtifactKind(StrEnum):
    """§33."""
    GAMEPLAY_CONCEPT = "GAMEPLAY_CONCEPT"
    MECHANIC_SPEC = "MECHANIC_SPEC"
    UX_FLOW = "UX_FLOW"
    UI_CONCEPT = "UI_CONCEPT"
    ART_DIRECTION = "ART_DIRECTION"
    ARCHITECTURE_DIRECTION = "ARCHITECTURE_DIRECTION"
    ASSET = "ASSET"
    PHASE_BASELINE = "PHASE_BASELINE"
    REFERENCE_MATERIAL = "REFERENCE_MATERIAL"


class ApprovalStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    CHANGE_REQUESTED = "CHANGE_REQUESTED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"
```

```python
# src/walk/permissions/models.py (enums)
class PermissionEffect(StrEnum):
    """§31: allow / deny / conditional (= REQUIRE_APPROVAL)."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class Approver(StrEnum):
    USER = "USER"
    PRODUCT_OWNER = "PRODUCT_OWNER"
    LEAD_DEV = "LEAD_DEV"
    ORCHESTRATOR = "ORCHESTRATOR"


class ApprovalState(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
```

```python
# src/walk/tools/models.py (enum)
class ToolKind(StrEnum):
    PROVIDER_NATIVE = "PROVIDER_NATIVE"   # file/shell tools of the model provider
    CLI = "CLI"                           # executable on PATH used through shell (graphify, dotnet)
    KERNEL = "KERNEL"                     # executed by the kernel via IntegrationManager (jira.*, git.*, unity.*)
    MCP = "MCP"                           # [Stage 8] MCP server tool
```

```python
# src/walk/budgets/models.py (enums)
class BudgetScope(StrEnum):
    """§20."""
    GLOBAL = "GLOBAL"
    PROJECT = "PROJECT"
    PHASE = "PHASE"
    ROLE = "ROLE"
    TASK = "TASK"


class BudgetDimension(StrEnum):
    """§20 + §84 cost dimensions."""
    TOKENS = "TOKENS"
    COST_USD = "COST_USD"
    AGENT_TURNS = "AGENT_TURNS"
    TOOL_CALLS = "TOOL_CALLS"
    EXECUTION_TIME_S = "EXECUTION_TIME_S"
    REVIEW_LOOPS = "REVIEW_LOOPS"
    EXTERNAL_CREDITS = "EXTERNAL_CREDITS"


class CostCategory(StrEnum):
    """§84 accounting tree root."""
    LLM = "LLM"
    ASSETS = "ASSETS"
    COMPUTE = "COMPUTE"
    TIME = "TIME"


class BudgetHardAction(StrEnum):
    BLOCK = "BLOCK"            # stop run, escalate
    DOWNGRADE_EFFORT = "DOWNGRADE_EFFORT"
    FALLBACK_MODEL = "FALLBACK_MODEL"
```

```python
# src/walk/runtime/models.py (enums)
class AgentRunState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED_FOR_APPROVAL = "PAUSED_FOR_APPROVAL"
    PAUSED_BY_USER = "PAUSED_BY_USER"
    INTERRUPTED = "INTERRUPTED"        # process died; resume pending
    HANDED_OVER = "HANDED_OVER"        # continued by another run
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    FAILED_HOOK = "FAILED_HOOK"
    FAILED_BOUNDARY = "FAILED_BOUNDARY"
    BLOCKED_BUDGET = "BLOCKED_BUDGET"
    BLOCKED_PROVIDER = "BLOCKED_PROVIDER"
    CANCELLED = "CANCELLED"


class CheckpointKind(StrEnum):
    START = "START"
    PERIODIC = "PERIODIC"
    AGENT_REQUESTED = "AGENT_REQUESTED"
    HANDOFF = "HANDOFF"
    PAUSE = "PAUSE"
    END = "END"


class AgentOutputStatus(StrEnum):
    """§126 Output.Status."""
    COMPLETED = "COMPLETED"       # task done per contract; triggers forward transition
    PARTIAL = "PARTIAL"           # progress made; needs another run (budget/time) — handover required
    BLOCKED = "BLOCKED"           # cannot proceed; escalations[] must be non-empty
    FAILED = "FAILED"
    NEEDS_INPUT = "NEEDS_INPUT"   # question for authority/user; escalations[] non-empty
    REJECTED = "REJECTED"         # reviewer/QC verdict: send back (REWORK)
    APPROVED = "APPROVED"         # reviewer/QC verdict: pass
```

```python
# src/walk/improvement/models.py (enums)
class RolloutStage(StrEnum):
    """§109."""
    DRAFT = "DRAFT"
    EXPERIMENTAL = "EXPERIMENTAL"
    LIMITED = "LIMITED"
    DEFAULT = "DEFAULT"
    DEPRECATED = "DEPRECATED"


class ImprovementRisk(StrEnum):
    """§104 authority tiers."""
    LOW = "LOW"        # auto-approvable
    MEDIUM = "MEDIUM"  # maintainer / PO review
    HIGH = "HIGH"      # user approval


class CandidateState(StrEnum):
    """§97 lifecycle before rollout."""
    OBSERVATION = "OBSERVATION"
    HYPOTHESIS = "HYPOTHESIS"
    CANDIDATE = "CANDIDATE"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

# `ImprovementScope` and `LearningScope` live in walk.common.enums (see above) because skills, agents and telemetry reference them.
```

---

## 4. Entities

### 4.1 `walk.workflow` — project decomposition (§52, §57)

```python
# src/walk/workflow/models.py
from walk.common.ids import *  # noqa
from walk.common.models import WalkModel, utcnow
from walk.common.roles import AgentRole


class Project(WalkModel):
    """Root aggregate (§52). One per game repository."""
    key: ProjectKey
    name: str
    repo_path: str = Field(description="Absolute path of the game repository root")
    gdd_paths: list[str] = Field(default_factory=list, description="GDD files relative to repo root (§48)")
    default_branch: str = "main"
    protected_branches: list[str] = Field(default_factory=lambda: ["main", "release/*"])
    work_provider: Literal["local", "jira"] = "local"
    autonomy_level_max: int = Field(default=2, ge=0, le=3, description="Highest AutonomyLevel agents may resolve without user (§51, §140)")
    current_phase_id: PhaseId | None = None
    created_at: datetime = Field(default_factory=utcnow)
    paused: bool = False


class GddRef(WalkModel):
    """Pointer into the GDD for traceability (§73)."""
    path: str
    anchor: str | None = None
    requirement_id: str | None = Field(default=None, description="Normalised requirement id after GDD compile [Stage 6]")


class Phase(WalkModel):
    """§66–§72."""
    id: PhaseId
    project_key: ProjectKey
    ordinal: int = Field(ge=1)
    name: str = Field(description="e.g. Prototype, Vertical Slice (§66)")
    state: PhaseState = PhaseState.PLANNED
    goal: str = ""
    scope_epic_ids: list[EpicId] = Field(default_factory=list, description="Approved scope (§67 boundary)")
    exit_criteria: list[str] = Field(default_factory=list)
    gate_round: int = Field(default=0, description="Incremented each time the phase enters USER_GATE (§71 revalidation)")
    baseline_artifact_id: ApprovedArtifactId | None = None
    budget_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_decision: PhaseDecision | None = None


class StoryContract(WalkModel):
    """§57 Executable Story Contract. Embedded in Story/Task/Bug."""
    goal: str
    source_requirements: list[GddRef] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    dependencies: list[WorkItemId] = Field(default_factory=list)
    required_evidence: list[EvidenceKind] = Field(default_factory=list)
    owner_role: AgentRole = AgentRole.SENIOR_DEV
    reviewer_role: AgentRole = AgentRole.LEAD_DEV
    required_skills: list[SkillName] = Field(default_factory=list, description="§29")
    risk: Risk = Risk.MEDIUM
    priority: Priority = Priority.P2
    complexity: Literal["TRIVIAL", "SMALL", "NORMAL", "LARGE", "CORE"] = "NORMAL"   # §18 task complexity input


class WorkItemBase(WalkModel):
    """Common fields of §52 hierarchy nodes. Persisted in `work_items`."""
    id: WorkItemId
    kind: WorkItemKind
    project_key: ProjectKey
    title: str
    description: str = ""
    state: WorkItemState = WorkItemState.IDEA
    state_version: int = Field(default=0, description="Optimistic concurrency + idempotency component")
    parent_id: WorkItemId | None = None
    phase_id: PhaseId | None = None
    external_ref: str | None = Field(default=None, description="Jira key or local provider ref (§55)")
    owner_role: AgentRole | None = None
    assigned_run_id: RunId | None = None
    priority: Priority = Priority.P2
    risk: Risk = Risk.MEDIUM
    labels: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None
    fix_loops: int = Field(default=0, description="QC rejections so far (§138 circuit breaker)")
    branch: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None


class Epic(WorkItemBase):
    kind: Literal[WorkItemKind.EPIC] = WorkItemKind.EPIC
    gdd_refs: list[GddRef] = Field(default_factory=list)


class Feature(WorkItemBase):
    """§6.5: done only when applicable dimensions are complete."""
    kind: Literal[WorkItemKind.FEATURE] = WorkItemKind.FEATURE
    gdd_refs: list[GddRef] = Field(default_factory=list)
    applicable_dimensions: list[DoneDimension] = Field(
        default_factory=lambda: [DoneDimension.FUNCTIONAL, DoneDimension.INTEGRATED, DoneDimension.TESTED, DoneDimension.QC_ACCEPTED]
    )
    done_dimensions: dict[DoneDimension, bool] = Field(default_factory=dict)
    context_path: str | None = Field(default=None, description=".ai/features/<id>.md")


class Story(WorkItemBase):
    kind: Literal[WorkItemKind.STORY] = WorkItemKind.STORY
    contract: StoryContract


class Task(WorkItemBase):
    kind: Literal[WorkItemKind.TASK] = WorkItemKind.TASK
    contract: StoryContract


class Bug(WorkItemBase):
    """§64 bug workflow uses WorkItemState (ADR-0010)."""
    kind: Literal[WorkItemKind.BUG] = WorkItemKind.BUG
    contract: StoryContract
    severity: Severity = Severity.MAJOR
    found_in_run_id: RunId | None = None
    found_against_commit: Sha | None = None
    reproduction: str = ""
    expected: str = ""
    observed: str = ""
    related_feature_id: FeatureId | None = None
    reopen_count: int = 0
    context_path: str | None = Field(default=None, description=".ai/bugs/<id>.md")


WorkItem = Annotated[Epic | Feature | Story | Task | Bug, Field(discriminator="kind")]


class WorkItemTransition(FrozenModel):
    """Row in `work_item_transitions`; `seq` is the idempotency component for provider sync."""
    seq: int
    work_item_id: WorkItemId
    from_state: WorkItemState
    to_state: WorkItemState
    event: str
    source: TransitionSource
    actor_role: AgentRole
    run_id: RunId | None = None
    reason: str | None = None
    at: datetime


class ReleaseCandidate(WalkModel):
    """§76."""
    id: ReleaseCandidateId
    project_key: ProjectKey
    number: int
    state: ReleaseCandidateState = ReleaseCandidateState.BUILDING
    commit: Sha
    build_evidence_ids: list[EvidenceId] = Field(default_factory=list)
    qc_report_evidence_id: EvidenceId | None = None
    rejection_bug_ids: list[BugId] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


class WorkItemDraft(WalkModel):
    """§126 New Tasks — input to WorkflowManager.create (also produced by agents in AgentOutput.new_tasks)."""
    kind: WorkItemKind
    title: str
    description: str
    parent_id: WorkItemId | None = None
    contract: StoryContract | None = None


class BugDraft(WalkModel):
    """§126 New Bugs (§63 QC authority) — input to WorkflowManager.create."""
    title: str
    severity: Severity
    reproduction: str
    expected: str
    observed: str
    related_feature_id: FeatureId | None = None
    evidence_ids: list[EvidenceId] = Field(default_factory=list)
    against_commit: Sha | None = None
```

### 4.2 `walk.agents` — roles, constitutions, runtime policy, execution contract (§9, §12–§15, §126)

```python
# src/walk/agents/models.py
# Imports from lower packages: Authority, EscalationRule, DecisionProposal, EscalationRequest (walk.decisions.models);
# WorkItemDraft, BugDraft (walk.workflow.models); EvidenceDraft (walk.telemetry.models); ContextUpdate (walk.memory.models);
# ContextBundle, ContextBundleRef (walk.context.models); Debate, DebatePosition (walk.debate.models).
class Constitution(WalkModel):
    """§12 Agent Constitution — model-independent. Loaded from kernel defaults `walk/agents/defaults/<role>.md`
    merged with project overrides `.ai/agents/roles/<role>.md` (ADR-0013)."""
    role: AgentRole
    version: str = Field(description="BehaviorVersion string, e.g. '1.3' (§105)")
    identity: str = Field(description="Display identity, e.g. 'Lead Developer'")
    mission: str
    responsibilities: list[str]
    authority: Authority
    professional_bias: str = Field(description="What this role optimises (§6.7)")
    core_beliefs: list[str]
    decision_principles: list[str]
    risk_tolerance: Literal["VERY_LOW", "LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    preferred_evidence: list[EvidenceKind]
    conflict_behavior: str
    escalation_rules: list[EscalationRule]
    tool_permissions: list["PermissionRule"]     # walk.permissions.models.PermissionRule
    forbidden_actions: list[str]
    body_markdown: str = Field(default="", description="Free-form guidance sections rendered into the system prompt")


class ModelPolicy(WalkModel):
    """§14."""
    preferred: list[ModelId]
    fallback: list[ModelId] = Field(default_factory=list)
    restricted: list[ModelId] = Field(default_factory=list, description="Never use for this role")
    required_capabilities: list[Capability] = Field(default_factory=list)
    cross_model_review: bool = Field(default=True, description="§23 prefer reviewer model != implementer model")
    allow_task_override: bool = True


class EffortPolicy(WalkModel):
    """§18–§19 inputs."""
    default: Effort = Effort.MEDIUM
    min: Effort = Effort.LOW
    max: Effort = Effort.HIGH
    auto_approve_upgrade_within_budget: bool = True
    complexity_map: dict[str, Effort] = Field(
        default_factory=lambda: {"TRIVIAL": Effort.LOW, "SMALL": Effort.LOW, "NORMAL": Effort.MEDIUM, "LARGE": Effort.HIGH, "CORE": Effort.VERY_HIGH}
    )
    risk_bump: dict[Risk, int] = Field(default_factory=lambda: {Risk.LOW: 0, Risk.MEDIUM: 0, Risk.HIGH: 1, Risk.CRITICAL: 2})
    stage_bump: dict[WorkItemState, int] = Field(default_factory=lambda: {WorkItemState.REWORK: 1})


class BudgetPolicy(WalkModel):
    """§20 per-role defaults; instantiated as Budget rows at ROLE and TASK scope."""
    per_task: dict[BudgetDimension, float] = Field(
        default_factory=lambda: {BudgetDimension.COST_USD: 15.0, BudgetDimension.TOOL_CALLS: 400, BudgetDimension.EXECUTION_TIME_S: 2700, BudgetDimension.REVIEW_LOOPS: 3}
    )
    soft_threshold_ratio: float = Field(default=0.8, ge=0, le=1)
    hard_action: BudgetHardAction = BudgetHardAction.BLOCK


class RuntimePolicy(WalkModel):
    """§13 how a role executes. From `.ai/agents/policies.yaml` merged over kernel defaults."""
    role: AgentRole
    version: str
    model_policy: ModelPolicy
    effort_policy: EffortPolicy
    budget_policy: BudgetPolicy
    default_skills: list[SkillName] = Field(default_factory=list)
    allowed_tools: list[ToolName] = Field(default_factory=list)
    execution_strategy: Literal["single_run", "plan_then_execute", "review_only"] = "single_run"
    max_parallel_runs: int = 1
    checkpoint_every_tool_calls: int = 10


class AgentInstance(WalkModel):
    """§9 Agent Instance = constitution + authority + policy + model + effort + budget + skills + tools + permissions + context."""
    role: AgentRole
    constitution: Constitution
    runtime_policy: RuntimePolicy
    skills: list[SkillName]
    tools: list[ToolName]
    permissions: list["PermissionRule"]
    model_id: ModelId
    effort: Effort
    budget_ids: list[str]


class ToolCallSummary(FrozenModel):
    tool: ToolName
    count: int
    denied: int = 0


class Finding(WalkModel):
    """§126 Findings — facts discovered, with evidence pointers."""
    summary: str
    detail: str = ""
    evidence_ids: list[EvidenceId] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    severity: Literal["INFO", "WARNING", "RISK"] = "INFO"


class FileChange(WalkModel):
    """§126 Changes — kernel verifies against git diff (ADR-0006 §D-2)."""
    path: str
    change: Literal["ADDED", "MODIFIED", "DELETED", "RENAMED"]
    summary: str = ""


class NextAction(WalkModel):
    description: str
    role: AgentRole | None = None
    blocked_on: str | None = None


class Handover(WalkModel):
    """§22 structured handover — part of the agent execution contract (AgentInput.handover / AgentOutput.handover).
    Persisted in `handovers` (runtime.CheckpointManager) and rendered to `.ai/handovers/HO-NNNN.md` through
    `walk.agents.handover.to_document()` → MemoryManager.write_handover(MemoryDocument). No chain-of-thought (ADR-0004)."""
    id: HandoverId
    work_item_id: WorkItemId
    role: AgentRole
    from_run_id: RunId
    from_model_id: ModelId
    to_run_id: RunId | None = None
    reason: Literal["FALLBACK", "PAUSE", "BUDGET", "PARTIAL", "REASSIGN", "RECOVERY"]
    task_summary: str                       # Task
    current_state: str                      # Current State
    completed_work: list[str]               # Completed Work
    modified_files: list[str]               # Modified Files
    findings: list[Finding]                 # Findings
    hypotheses: list[str]                   # Hypotheses
    decisions: list[DecisionId]             # Decisions (ids of recorded decisions)
    proposed_decisions: list[DecisionProposal] = Field(default_factory=list)
    risks: list[str]                        # Risks
    remaining_work: list[str]               # Remaining Work
    next_action: str                        # Next Action
    worktree_head: Sha
    branch: str
    created_at: datetime = Field(default_factory=utcnow)


class ObservationDraft(WalkModel):
    """§96 improvement observation from within a run."""
    observed: str
    potential_cause: str
    possible_improvement: str
    scope: ImprovementScope


class ExpectedOutput(WalkModel):
    """§126 Expected Output: what the run must produce."""
    status_options: list[AgentOutputStatus]
    deliverables: list[str] = Field(description="e.g. 'technical design section in FEAT-0012', 'passing EditMode tests'")
    required_evidence: list[EvidenceKind]
    output_schema_ref: str = "walk.agents.models.AgentOutput"


class AgentInput(WalkModel):
    """§126 structured input — every listed field present."""
    run_id: RunId
    role: AgentRole                                   # Agent Role
    constitution: Constitution                        # Constitution
    authority: Authority                              # Authority
    task: WorkItem                                    # Task
    workflow_state: WorkItemState                     # Workflow State
    phase: Phase | None                               # phase scope (§67)
    context: ContextBundle                            # Relevant Context (walk.context.models)
    approved_artifacts: list[ApprovedArtifact]        # Approved Artifacts
    decisions: list[Decision]                         # Relevant Decisions
    skills: list[Skill]                               # Available Skills
    allowed_tools: list[ToolSpec]                     # Allowed Tools
    permissions: list[PermissionRule]                 # Permissions
    budget: list[Budget]                              # Budget (TASK + ROLE scope rows)
    effort: Effort                                    # Effort
    required_evidence: list[EvidenceKind]             # Required Evidence
    expected_output: ExpectedOutput                   # Expected Output
    handover: Handover | None = None                  # present on fallback/resume (§22, §132)
    worktree_path: str
    branch: str
    debate: Debate | None = None                      # present when the run is a debate turn
    instructions_markdown: str = Field(default="", description="Rendered task prompt (kernel-owned template, versioned)")


class TriageVerdict(WalkModel):
    """Structured TRIAGE result (§10.8: QC finds severity; Lead Dev triages owner and may confirm or change severity). E03-S15."""
    severity: Severity
    owner_role: AgentRole
    rationale: str
    propose_wont_fix: bool = False


class AgentOutput(WalkModel):
    """§126 structured output — every listed field present. Persisted (never chain-of-thought, §22)."""
    status: AgentOutputStatus                         # Status
    result: str                                       # Result (summary, markdown)
    findings: list[Finding] = Field(default_factory=list)                 # Findings
    changes: list[FileChange] = Field(default_factory=list)               # Changes
    decisions: list[DecisionProposal] = Field(default_factory=list)       # Decisions (proposals)
    evidence: list[EvidenceDraft] = Field(default_factory=list)           # Evidence
    context_updates: list[ContextUpdate] = Field(default_factory=list)    # Context Updates
    new_tasks: list[WorkItemDraft] = Field(default_factory=list)          # New Tasks
    new_bugs: list[BugDraft] = Field(default_factory=list)                # New Bugs
    escalations: list[EscalationRequest] = Field(default_factory=list)    # Escalations
    next_actions: list[NextAction] = Field(default_factory=list)          # Next Actions
    # kernel-added structured extras
    handover: Handover | None = Field(default=None, description="Required when status is PARTIAL")
    effort_request: EffortRequest | None = None                           # §19 (walk.effort.models)
    debate_position: DebatePosition | None = None                         # §45 (walk.debate.models)
    observations: list[ObservationDraft] = Field(default_factory=list)    # §96
    no_context_change_reason: str | None = Field(default=None, description="Required if context_updates is empty and status != FAILED")
    triage: TriageVerdict | None = Field(default=None, description="Required for purpose TRIAGE with status COMPLETED")   # E03-S15
    reopen_bugs: list[BugId] = Field(default_factory=list, description="QC only: closed bugs that regressed (raises regression_reopen)")   # E03-S15
```

### 4.3 `walk.effort` (§17–§19)

```python
# src/walk/effort/models.py
class EffortRequest(WalkModel):
    """§19 dynamic effort change requested by an agent."""
    direction: Literal["UPGRADE", "DOWNGRADE"]
    target: Effort
    reason: str


class EffortResolution(FrozenModel):
    """Result of INTERFACES.md §5.2 algorithm; written as EFFORT_SET ledger payload."""
    role_default: Effort
    complexity_component: Effort
    risk_bump: int
    stage_bump: int
    escalation_bump: int
    effective: Effort
    clamped_by_policy: bool
    clamped_by_budget: bool
```

### 4.4 `walk.budgets` (§20, §84–§85)

```python
# src/walk/budgets/models.py
class Budget(WalkModel):
    """One limit for one dimension at one scope. Persisted in `budgets`."""
    id: str = Field(description="'<scope>:<scope_id>:<dimension>' e.g. 'TASK:STORY-0412:COST_USD'")
    scope: BudgetScope
    scope_id: str = Field(description="project key / PHASE-id / role name / work item id / 'GLOBAL'")
    dimension: BudgetDimension
    limit: float
    consumed: float = 0.0
    soft_threshold_ratio: float = 0.8
    hard_action: BudgetHardAction = BudgetHardAction.BLOCK
    soft_notified: bool = False
    updated_at: datetime = Field(default_factory=utcnow)


class BudgetSubject(FrozenModel):
    """Identifies which budget scopes a metered quantity applies to (passed by runtime instead of AgentRun to keep budgets below runtime)."""
    project_key: ProjectKey
    phase_id: PhaseId | None = None
    role: AgentRole | None = None
    work_item_id: WorkItemId | None = None
    run_id: RunId | None = None


class CostRecord(FrozenModel):
    """§84 one metered cost line. Persisted in `cost_records`; also emitted as COST_RECORDED ledger event.
    Built from adapter usage by `walk.model_router.costing.usage_to_cost_record(usage, descriptor, subject)`."""
    id: str
    at: datetime
    project_key: ProjectKey
    category: CostCategory
    provider: str = Field(description="claude / codex / meshy / ci / wallclock")
    model_id: ModelId | None = None
    dimension: BudgetDimension
    quantity: float
    unit: str = Field(description="tokens / usd / seconds / calls / credits")
    cost_usd: float = 0.0
    run_id: RunId | None = None
    work_item_id: WorkItemId | None = None
    phase_id: PhaseId | None = None
    role: AgentRole | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
```

### 4.5 `walk.permissions` (§31, §92)

```python
# src/walk/permissions/models.py
class PermissionRule(WalkModel):
    """§31 one rule. Matching: most specific `tool` pattern wins, then DENY > REQUIRE_APPROVAL > ALLOW (ADR-0006)."""
    role: AgentRole
    tool: str = Field(description="ToolName or glob: 'git.commit', 'git.*', 'bash', '*'")
    effect: PermissionEffect
    command_patterns: list[str] = Field(default_factory=list, description="For shell tools: regexes the command must match (ALLOW) or must not match (DENY)")
    path_patterns: list[str] = Field(default_factory=list, description="For file tools: globs relative to worktree")
    approver: Approver | None = Field(default=None, description="Required when effect == REQUIRE_APPROVAL")
    reason: str = ""


class ProtectedAction(WalkModel):
    """§92 configurable protected actions."""
    name: str = Field(description="git.merge_protected, store.publish, credentials.change, …")
    approver: Approver = Approver.USER
    description: str = ""


class ToolCallRequest(FrozenModel):
    """What the enforcement point evaluates."""
    run_id: RunId
    role: AgentRole
    tool: ToolName
    kind: ToolKind
    arguments: JsonDict
    command: str | None = None
    paths: list[str] = Field(default_factory=list)
    worktree_path: str


class PermissionDecision(FrozenModel):
    effect: PermissionEffect
    matched_rule: PermissionRule | None
    reason: str
    approval_request_id: ApprovalRequestId | None = None


class ApprovalRequest(WalkModel):
    """Pending human/authority approval (§92, §51 Level 3). Persisted in `approval_requests`."""
    id: ApprovalRequestId
    kind: Literal["TOOL_CALL", "PROTECTED_ACTION", "ESCALATION", "ARTIFACT_CHANGE", "IMPROVEMENT"]
    approver: Approver
    requested_by_role: AgentRole
    run_id: RunId | None
    work_item_id: WorkItemId | None
    payload: JsonDict
    state: ApprovalState = ApprovalState.PENDING
    requested_at: datetime = Field(default_factory=utcnow)
    decided_at: datetime | None = None
    decided_by: str | None = None
    decision_note: str | None = None
    expires_at: datetime | None = None
```

### 4.6 `walk.tools`, `walk.skills`, `walk.hooks` (§28–§32)

```python
# src/walk/tools/models.py
class ToolSpec(WalkModel):
    """§30 registry entry. Tools are distinct from role, model and skill."""
    name: ToolName
    kind: ToolKind
    description: str
    provider: str | None = Field(default=None, description="Integration that executes KERNEL tools: 'jira', 'git', 'unity', 'graphify', 'meshy'")
    executable: str | None = Field(default=None, description="CLI binary for kind=CLI")
    command_patterns: list[str] = Field(default_factory=list, description="Shell regexes that identify this tool in a command")
    cost_dimension: BudgetDimension = BudgetDimension.TOOL_CALLS
    cost_category: CostCategory = CostCategory.COMPUTE
    protected_action: str | None = Field(default=None, description="ProtectedAction.name if this tool is protected")
    requires_env: list[str] = Field(default_factory=list, description="EnvironmentManifest keys that must be ready")
    version: str = "1.0"
```

```python
# src/walk/skills/models.py
class Skill(WalkModel):
    """§28 canonical skill: `.ai/agents/skills/<name>/SKILL.md` (project) or `walk/skills/builtin/<name>/SKILL.md` (kernel)."""
    name: SkillName
    version: str
    description: str
    scope: LearningScope
    applies_to_roles: list[AgentRole] = Field(default_factory=list)
    requires_tools: list[ToolName] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    body_markdown: str
    source_path: str
    content_sha256: str


class SkillProjection(FrozenModel):
    """Generated provider representation (ADR-0007)."""
    skill: SkillName
    provider: str
    target_path: str = Field(description="e.g. <worktree>/.claude/skills/<name>/SKILL.md or <worktree>/AGENTS.md section")
    content_sha256: str
    generated_from_sha256: str
    generated_at: datetime


class DriftReport(FrozenModel):
    missing: list[SkillName]
    modified: list[SkillName]
    orphaned: list[str]
    ok: bool
```

```python
# src/walk/hooks/models.py
class HookName(StrEnum):
    """Full list and semantics: ARCHITECTURE.md §4.1."""
    ON_PROJECT_START = "on_project_start"
    ON_PROJECT_PAUSE = "on_project_pause"
    ON_PROJECT_RESUME = "on_project_resume"
    ON_PHASE_START = "on_phase_start"
    ON_PHASE_REVIEW_START = "on_phase_review_start"
    ON_PHASE_COMPLETE = "on_phase_complete"
    ON_PHASE_GATE_DECISION = "on_phase_gate_decision"
    ON_TASK_START = "on_task_start"
    ON_TASK_COMPLETE = "on_task_complete"
    ON_TASK_BLOCKED = "on_task_blocked"
    ON_TASK_FAILED = "on_task_failed"
    ON_TASK_CANCELLED = "on_task_cancelled"
    ON_STATE_TRANSITION = "on_state_transition"
    ON_AGENT_START = "on_agent_start"
    ON_AGENT_CHECKPOINT = "on_agent_checkpoint"
    ON_AGENT_END = "on_agent_end"
    ON_AGENT_HANDOFF = "on_agent_handoff"
    ON_MODEL_FALLBACK = "on_model_fallback"
    ON_EFFORT_CHANGE = "on_effort_change"
    ON_BUDGET_THRESHOLD = "on_budget_threshold"
    ON_BUDGET_EXHAUSTED = "on_budget_exhausted"
    ON_TOOL_BEFORE = "on_tool_before"
    ON_TOOL_AFTER = "on_tool_after"
    ON_TOOL_DENIED = "on_tool_denied"
    ON_PROTECTED_ACTION_REQUESTED = "on_protected_action_requested"
    ON_CODE_CHANGED = "on_code_changed"
    ON_COMMIT = "on_commit"
    ON_PR_OPENED = "on_pr_opened"
    ON_MERGED = "on_merged"
    ON_BUILD_START = "on_build_start"
    ON_BUILD_SUCCESS = "on_build_success"
    ON_BUILD_FAILURE = "on_build_failure"
    ON_TEST_RESULT = "on_test_result"
    ON_CONTEXT_STALE = "on_context_stale"
    ON_CONTEXT_UPDATED = "on_context_updated"
    ON_READY_FOR_QC = "on_ready_for_qc"
    ON_QC_RESULT = "on_qc_result"
    ON_BUG_CREATED = "on_bug_created"
    ON_DEBATE_OPENED = "on_debate_opened"
    ON_DEBATE_ROUND_COMPLETE = "on_debate_round_complete"
    ON_DEBATE_RESOLVED = "on_debate_resolved"
    ON_DECISION_RECORDED = "on_decision_recorded"
    ON_ESCALATION = "on_escalation"
    ON_RECOVERY_RESUME = "on_recovery_resume"
    ON_IMPROVEMENT_OBSERVATION = "on_improvement_observation"


class HookFailPolicy(StrEnum):
    FAIL_CLOSED = "fail_closed"
    LOG_AND_CONTINUE = "log_and_continue"


class Hook(WalkModel):
    """A registration. `builtin` hooks carry a dotted callable path; project hooks carry a shell command or kernel action."""
    name: HookName
    id: str = Field(description="unique within hook name, e.g. 'builtin.checkpoint', 'project.notify-slack'")
    kind: Literal["builtin", "project"]
    priority: int = Field(default=100, description="lower runs first; builtin MUST hooks use < 50")
    callable_path: str | None = None
    command: str | None = None
    kernel_action: str | None = None
    fail_policy: HookFailPolicy = HookFailPolicy.LOG_AND_CONTINUE
    required: bool = Field(default=False, description="MUST hooks: cannot be disabled by project config")
    enabled: bool = True
    timeout_s: int = 120


class HookContext(FrozenModel):
    name: HookName
    at: datetime
    project_key: ProjectKey
    work_item_id: WorkItemId | None = None
    run_id: RunId | None = None
    phase_id: PhaseId | None = None
    role: AgentRole | None = None
    payload: JsonDict = Field(default_factory=dict)


class HookResult(FrozenModel):
    hook_id: str
    status: Literal["OK", "FAILED", "SKIPPED", "TIMEOUT"]
    duration_ms: int
    message: str = ""


HookCallable = Callable[[HookContext], Awaitable[None]]   # built-in implementations live in walk.orchestrator.builtin_hooks (ADR-0016)
```

### 4.7 `walk.memory` — project memory documents (§22, §33, §36–§39, §42)

```python
# src/walk/memory/models.py   (Actor comes from walk.common.models)
class Freshness(WalkModel):
    """§42 stamps. Written by MemoryManager on every write (ADR-0003)."""
    commit: Sha
    branch: str
    timestamp: datetime
    pr: str | None = None
    build: str | None = None


class FreshnessAssessment(FrozenModel):
    """Result of INTERFACES.md §5.5 classification."""
    status: FreshnessStatus
    reason: str
    changed_relevant_files: list[str] = Field(default_factory=list)
    assessed_against: Sha
    assessed_at: datetime


class RelatedLinks(WalkModel):
    work_items: list[WorkItemId] = Field(default_factory=list)
    decisions: list[DecisionId] = Field(default_factory=list)
    approved: list[ApprovedArtifactId] = Field(default_factory=list)
    evidence: list[EvidenceId] = Field(default_factory=list)
    gdd: list[str] = Field(default_factory=list)


class FrontMatter(WalkModel):
    """Common YAML header of every `.ai/**/*.md` (ARCHITECTURE.md §8.2)."""
    id: str
    type: MemoryDocType
    title: str
    status: str | None = None
    version: int = 1
    schema_version: int = 1
    created_at: datetime
    updated_at: datetime
    updated_by: Actor
    freshness: Freshness | None = None
    related: RelatedLinks = Field(default_factory=RelatedLinks)
    relevant_files: list[str] = Field(default_factory=list)
    extra: JsonDict = Field(default_factory=dict, description="Type-specific scalar fields (e.g. approved_by, scope)")


class MemoryDocument(WalkModel):
    """Parsed Markdown document: front matter + ordered H2 sections."""
    path: str
    front_matter: FrontMatter
    sections: dict[str, str] = Field(description="H2 heading -> markdown body, insertion-ordered")
    raw_sha256: str


class ProjectContext(WalkModel):
    """§36 `.ai/project/project.md` sections."""
    goals: str
    platforms: list[str]
    technical_constraints: str
    performance_targets: str
    coding_conventions: str
    architecture_overview: str
    art_direction: str
    product_constraints: str
    major_decisions: list[DecisionId]
    known_limitations: str


class FeatureContext(WalkModel):
    """§37 `.ai/features/FEAT-NNNN.md` — section names are the H2 headings, in this order."""
    feature_id: FeatureId
    intent: str
    design_goal: str
    relevant_gdd: list[GddRef]
    current_status: str
    architecture: str
    affected_systems: list[str]
    dependencies: list[str]
    relevant_files: list[str]
    important_decisions: list[DecisionId]
    implementation_notes: str
    known_risks: str
    qc_notes: str
    evidence: list[EvidenceId]
    remaining_work: str
    freshness: Freshness | None = None


class BugContext(WalkModel):
    """§38 `.ai/bugs/BUG-NNNN.md`."""
    bug_id: BugId
    problem: str
    reproduction: str
    expected_behavior: str
    observed_behavior: str
    investigations: str
    hypotheses: str
    failed_attempts: str
    root_cause: str
    affected_systems: list[str]
    fix: str
    regression_risk: str
    verification: str
    freshness: Freshness | None = None


class ContextUpdate(WalkModel):
    """§126 Context Updates — targeted section edits to memory documents (§41). Produced by agents, consumed by MemoryManager.apply_updates."""
    doc_id: str = Field(description="FEAT-0012 / BUG-0031 / project")
    section: str = Field(description="H2 section name per MemoryDocType schema")
    operation: Literal["REPLACE", "APPEND"]
    content_markdown: str
    relevant_files: list[str] = Field(default_factory=list)


class ApprovedArtifact(WalkModel):
    """§33 first-class approved object; `.ai/approved/APR-NNNN.md` + payload folder."""
    id: ApprovedArtifactId
    kind: ApprovedArtifactKind
    title: str
    status: ApprovalStatus
    scope: str = Field(description="Project / PHASE-id / FEAT-id")
    version: int
    approved_by: Actor
    approved_at: datetime
    related_requirements: list[GddRef]
    payload_paths: list[str]
    content_sha256: str = Field(description="Hash over payload files; drift check (Invariant 10)")
    supersedes: ApprovedArtifactId | None = None
    change_request_decision: DecisionId | None = Field(default=None, description="Decision authorising the change that produced this version")
```

### 4.8 `walk.decisions`, `walk.debate` (§44–§47, §51)

```python
# src/walk/decisions/models.py   — the "Authority" half of the §7 "Debate / Decision / Authority" layer lives here
class Authority(WalkModel):
    """§12 Authority + §51 autonomy bounds. Embedded in Constitution."""
    decision_scope: list[DecisionCategory] = Field(default_factory=list, description="Categories this role may ACCEPT decisions in")
    max_autonomy_level: AutonomyLevel = AutonomyLevel.LOCAL
    may_approve: list[str] = Field(default_factory=list, description="ApprovedArtifactKind / review kinds this role may approve, e.g. 'review.approve', 'ART_DIRECTION'")
    may_reject: list[str] = Field(default_factory=list)
    may_create_work: list[WorkItemKind] = Field(default_factory=list)


class EscalationRule(WalkModel):
    """§12 Escalation Rules: when a role must escalate instead of deciding."""
    condition: str = Field(description="Human-readable trigger, e.g. 'core gameplay change' (§51 Level 3 list)")
    to_level: AutonomyLevel
    category: DecisionCategory | None = None


class DecisionProposal(WalkModel):
    """§126 Decisions as *proposals* (Invariant 5). Input to DecisionManager.propose."""
    category: DecisionCategory
    topic: str
    position: str
    rationale: str
    alternatives: list[str] = Field(default_factory=list)
    evidence_ids: list[EvidenceId] = Field(default_factory=list)
    autonomy_level: AutonomyLevel
    affected_systems: list[str] = Field(default_factory=list)


class EscalationRequest(WalkModel):
    """§126 Escalations. Input to DecisionManager.escalate."""
    to_level: AutonomyLevel
    category: DecisionCategory
    question: str
    options: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    evidence_ids: list[EvidenceId] = Field(default_factory=list)


class DecisionPosition(WalkModel):
    """A participant's position inside a Decision record (§44 'positions')."""
    role: AgentRole
    model_id: ModelId | None
    position: str
    confidence: float = Field(ge=0, le=1)


class Decision(WalkModel):
    """§44 decision record. `.ai/decisions/DEC-NNNN.md` + `decisions` table."""
    id: DecisionId
    category: DecisionCategory
    status: DecisionStatus
    topic: str
    participants: list[AgentRole]
    positions: list[DecisionPosition]
    evidence_ids: list[EvidenceId]
    outcome: str                                  # final outcome
    owner: AgentRole                              # who decided (authority or USER)
    rationale: str
    alternatives: list[str]
    affected_systems: list[str]
    related_work_items: list[WorkItemId]
    autonomy_level: AutonomyLevel
    debate_id: DebateId | None = None
    version: int = 1
    supersedes: DecisionId | None = None
    decided_at: datetime = Field(default_factory=utcnow)
    overridden_by_user_at: datetime | None = None


class Escalation(WalkModel):
    """§50 escalation instance routed by DecisionManager."""
    id: str
    from_role: AgentRole
    to_level: AutonomyLevel
    category: DecisionCategory
    question: str
    options: list[str]
    recommendation: str | None
    evidence_ids: list[EvidenceId]
    work_item_id: WorkItemId | None
    run_id: RunId | None
    approval_request_id: ApprovalRequestId | None = None
    resolved_decision_id: DecisionId | None = None
    created_at: datetime = Field(default_factory=utcnow)
```

```python
# src/walk/debate/models.py
class DebatePosition(WalkModel):
    """§45 one position in one round."""
    debate_id: DebateId
    round: int
    role: AgentRole
    model_id: ModelId
    run_id: RunId
    position: str
    reasoning: str
    evidence_ids: list[EvidenceId]
    cost: str = Field(description="Cost assessment in words / numbers")
    risk: str
    alternative: str
    confidence: float = Field(ge=0, le=1)
    changed_from_previous: bool = Field(default=False, description="§45 agents may change opinion")
    at: datetime = Field(default_factory=utcnow)


class Debate(WalkModel):
    """§46 lifecycle. Persisted in `debates` + `debate_positions`."""
    id: DebateId
    topic: str
    category: DecisionCategory
    state: DebateState = DebateState.OPEN
    participants: list[AgentRole]
    opened_by: AgentRole
    work_item_id: WorkItemId | None
    round: int = 0
    max_rounds: int = 3
    budget_id: str | None = None
    consensus_threshold: float = Field(default=0.75, description="Fraction of participants whose final positions agree")
    final_positions: list[DebatePosition] = Field(default_factory=list)
    decision_id: DecisionId | None = None
    opened_at: datetime = Field(default_factory=utcnow)
    resolved_at: datetime | None = None
```

### 4.9 `walk.context` (§40–§43)

```python
# src/walk/context/models.py
class ContextItemKind(StrEnum):
    WORK_ITEM = "WORK_ITEM"
    FEATURE_CONTEXT = "FEATURE_CONTEXT"
    BUG_CONTEXT = "BUG_CONTEXT"
    PROJECT_CONTEXT = "PROJECT_CONTEXT"
    DECISION = "DECISION"
    APPROVED_ARTIFACT = "APPROVED_ARTIFACT"
    HANDOVER = "HANDOVER"
    WORKFLOW_STATE = "WORKFLOW_STATE"
    CODE_GRAPH = "CODE_GRAPH"
    SOURCE_FILE = "SOURCE_FILE"
    EVIDENCE = "EVIDENCE"
    SKILL = "SKILL"


class ContextItem(WalkModel):
    id: str
    kind: ContextItemKind
    title: str
    content: str
    tokens_estimate: int
    score: float
    freshness: FreshnessAssessment | None
    requires_verification: bool = False
    source_path: str | None = None
    mandatory: bool = False


class ContextRequest(WalkModel):
    work_item_id: WorkItemId
    role: AgentRole
    effort: Effort
    token_budget: int
    include_source: bool = True
    code_graph_depth: int = 2


class ContextBundle(WalkModel):
    """Output of ContextManager.build (§40 order preserved in `items`)."""
    request: ContextRequest
    items: list[ContextItem]
    total_tokens_estimate: int
    excluded_count: int
    built_at: datetime = Field(default_factory=utcnow)
    head_commit: Sha

    def ref(self) -> "ContextBundleRef":
        """Manifest for checkpoints (ids + stale flags, no contents)."""
        return ContextBundleRef(
            item_ids=[i.id for i in self.items],
            total_tokens_estimate=self.total_tokens_estimate,
            stale_item_ids=[i.id for i in self.items if i.requires_verification],
        )


class ContextBundleRef(FrozenModel):
    """Manifest of what context was given; stored in Checkpoint.context_manifest."""
    item_ids: list[str]
    total_tokens_estimate: int
    stale_item_ids: list[str] = Field(default_factory=list)
```

### 4.10 `walk.model_router` (§16, §21–§23)

```python
# src/walk/model_router/models.py
class ModelDescriptor(WalkModel):
    """§16 capability metadata. Defaults in `walk/model_router/defaults/models.yaml`, overrides in `.ai/agents/models.yaml`."""
    id: ModelId
    provider: str = Field(description="adapter key: 'claude' | 'codex' | plugin name")
    display_name: str
    capabilities: dict[Capability, int] = Field(description="0..5 per capability")
    context_window_tokens: int
    max_output_tokens: int
    supports_effort_levels: list[Effort]
    supports_native_resume: bool
    input_cost_per_mtok_usd: float
    output_cost_per_mtok_usd: float
    cache_read_cost_per_mtok_usd: float = 0.0
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)


class CapabilityRegistry(WalkModel):
    models: dict[ModelId, ModelDescriptor]
    version: str


class TaskProfile(FrozenModel):
    """What the router needs to know about the task (§16, §29)."""
    required_capabilities: list[Capability]
    required_tools: list[ToolName]
    required_skills: list[SkillName]
    estimated_context_tokens: int
    risk: Risk
    implementer_model_id: ModelId | None = Field(default=None, description="For §23 cross-model review")


class RoutingDecision(FrozenModel):
    model_id: ModelId
    provider: str
    effort: Effort
    reason: str
    rejected: list[tuple[ModelId, str]] = Field(default_factory=list)
    is_fallback: bool = False
    trigger: FallbackTrigger | None = None


MAX_FALLBACKS_PER_RUN = 2                                   # ARCHITECTURE.md §5.5


class FallbackRequest(FrozenModel):
    """Input of ModelRouter.fallback (INTERFACES.md §5.3 steps 7–9). Carries plain data instead of an AgentRun because
    model_router may not import runtime (ARCHITECTURE.md §2.2). Built by runtime.AgentExecutor. E01-S28."""
    role: AgentRole
    policy: ModelPolicy                                     # walk.agents.models
    current_model_id: ModelId
    trigger: FallbackTrigger
    profile: TaskProfile
    effort: Effort
    fallbacks_so_far: int = Field(description="AgentRun.fallbacks of the failing run (chain count)")
    max_fallbacks: int = MAX_FALLBACKS_PER_RUN
    measured_context_tokens: int | None = None              # CONTEXT_OVERFLOW only


class ProviderSessionRef(FrozenModel):
    """Opaque provider-side session handle enabling native resume (Claude session_id / Codex thread id)."""
    provider: str
    session_id: str
    resumable: bool


class UsageReport(FrozenModel):
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cost_usd: float
    turns: int
    tool_calls: int
    duration_s: float


class AdapterHealth(FrozenModel):
    ok: bool
    provider: str
    detail: str
    checked_at: datetime


class AgentEventKind(StrEnum):
    STARTED = "STARTED"
    TEXT = "TEXT"                        # visible assistant text (not persisted beyond logs)
    TOOL_CALL_REQUESTED = "TOOL_CALL_REQUESTED"
    TOOL_CALL_RESULT = "TOOL_CALL_RESULT"
    CHECKPOINT_HINT = "CHECKPOINT_HINT"
    USAGE = "USAGE"
    PARTIAL_OUTPUT = "PARTIAL_OUTPUT"
    FINAL_OUTPUT = "FINAL_OUTPUT"
    ERROR = "ERROR"
    ENDED = "ENDED"


class AgentEvent(FrozenModel):
    """Normalised adapter stream element (ADR-0004). Thinking/chain-of-thought is never emitted."""
    kind: AgentEventKind
    run_id: RunId
    at: datetime
    text: str | None = None
    tool_call: ToolCallRequest | None = None
    tool_result: JsonDict | None = None
    usage: UsageReport | None = None
    output: AgentOutput | None = None
    error: str | None = None
    trigger: FallbackTrigger | None = None
    session: ProviderSessionRef | None = None
```

### 4.11 `walk.runtime` — runs and checkpoints (§41, §54, §89)

```python
# src/walk/runtime/models.py
class AgentRun(WalkModel):
    """One adapter session for one (work item, role, state). Persisted in `agent_runs`."""
    id: RunId
    project_key: ProjectKey
    work_item_id: WorkItemId
    role: AgentRole
    model_id: ModelId
    provider: str
    effort: Effort
    state: AgentRunState = AgentRunState.PENDING
    purpose: Literal["IMPLEMENT", "DESIGN", "REVIEW", "QC", "TRIAGE", "DEBATE", "PLAN", "ANALYSIS", "RETRO"]
    worktree_path: str | None = None
    branch: str | None = None
    kernel_instance: str = Field(description="UUID of the kernel process that owns the run")
    parent_run_id: RunId | None = None
    handover_in_id: HandoverId | None = None
    handover_out_id: HandoverId | None = None
    provider_session: ProviderSessionRef | None = None
    tool_calls: int = 0
    fallbacks: int = 0
    repair_turns: int = 0
    started_at: datetime | None = None
    ended_at: datetime | None = None
    output: AgentOutput | None = None
    failure_reason: str | None = None


class Checkpoint(FrozenModel):
    """ADR-0002. Persisted in `checkpoints`; immutable."""
    id: CheckpointId
    run_id: RunId
    work_item_id: WorkItemId
    seq: int
    kind: CheckpointKind
    at: datetime
    role: AgentRole
    model_id: ModelId
    effort: Effort
    workflow_state: WorkItemState
    head_sha: Sha = Field(description="Work-branch HEAD after the WIP commit")
    wip_commit_sha: Sha | None
    dirty_files: list[str]
    tool_calls_so_far: int
    budget_consumed: dict[BudgetDimension, float]
    provider_session: ProviderSessionRef | None
    handover_id: HandoverId | None
    context_manifest: ContextBundleRef
```

### 4.12 `walk.telemetry` — ledger & evidence (§81–§83, §86)

```python
# src/walk/telemetry/models.py
class LedgerEvent(FrozenModel):
    """Append-only (§81). `seq` assigned by SQLite AUTOINCREMENT; `id` is a ULID."""
    seq: int | None = Field(default=None, description="None before insert")
    id: LedgerEventId
    kind: LedgerEventKind
    at: datetime
    project_key: ProjectKey
    actor_role: AgentRole
    work_item_id: WorkItemId | None = None
    run_id: RunId | None = None
    phase_id: PhaseId | None = None
    model_id: ModelId | None = None
    effort: Effort | None = None
    tool: ToolName | None = None
    duration_ms: int | None = None
    cost_usd: float | None = None
    outcome: Literal["OK", "FAILED", "DENIED", "SKIPPED"] | None = None
    payload: JsonDict = Field(default_factory=dict, description="Kind-specific structured detail (e.g. from/to states, trigger, sha)")
    behavior_versions: dict[str, str] = Field(default_factory=dict, description="§82 'with which version' — workflow/constitution/skill versions in effect")
```

Ledger payload contracts that other stories read (keys are normative; a writer may add keys, never drop or rename these). Writers per `ARCHITECTURE.md` §4.3.

| Kind | `work_item_id` / `run_id` | Payload keys | Writer (story) | Read by |
|---|---|---|---|---|
| `PROJECT_STARTED` | — / — | `kernel_instance`, recovery counts from `RecoveryReport` (`interrupted`, `resumed_native`, `restarted_with_handover`, `requeued`, `failed`) | `Orchestrator.start` (E01-S29) | status, reports |
| `MODEL_FALLBACK` | failing item / failing run | executor path: `trigger`, `from`, `to`, `handover_id`, `checkpoint_id`, `rejected`; recovery path: `trigger` (= `PROVIDER_OUTAGE`), `from`, `to` | `AgentExecutor` / `RecoveryManager` (E01-S28) | `ON_MODEL_FALLBACK` hooks, retrospective `fallbacks` metric |
| `RECOVERY_RESUMED` | item / new run | `from_run_id`, `mode` (`native` \| `handover`), `checkpoint_seq`, `handover_id` | `RecoveryManager` (E01-S28) | reports |
| `BUG_CREATED` | the bug / creating run | `bug_id`, `parent_id`, `severity`, `related_feature_id`, `found_in_run_id`, `found_against_commit`, `external_ref` | `Orchestrator` via `BugIntake` (E03-S14) | `top_defect` (E07-S08), reports |

`BUG_CREATED.parent_id` is the work item the defect is attributed to: `bug.parent_id` when set, else `bug.related_feature_id`, else `null`. `severity` is the bug's `Severity` value at creation (triage may change it later; the ledger keeps the creation value).

```python
# src/walk/telemetry/models.py (continued)
class Evidence(FrozenModel):
    """§6.6 evidence record. Files live under `.ai/<features|bugs|phases>/<id>/evidence/`; `evidence` table indexes them."""
    id: EvidenceId
    kind: EvidenceKind
    description: str
    uri: str = Field(description="repo-relative path or external URI")
    sha256: str | None
    produced_by: Actor
    produced_at: datetime
    work_item_id: WorkItemId | None
    phase_id: PhaseId | None
    commit: Sha | None
    metrics: JsonDict = Field(default_factory=dict)

    @property
    def rank(self) -> int:
        """§47 ranking."""
        return EVIDENCE_RANK[self.kind]


class EvidenceDraft(WalkModel):
    """Evidence declared by an agent or a CI job; EvidenceManager.record hashes the file and mints the EvidenceId."""
    kind: EvidenceKind
    path_or_uri: str
    description: str
    metrics: JsonDict = Field(default_factory=dict)


class RetrospectiveMetrics(WalkModel):
    """§115 figures / §116 metrics, computed by TelemetryManager from the ledger (§83). Embedded in improvement.Retrospective."""
    stories: int
    first_pass_success_rate: float
    reworked_stories: int
    qc_bugs: int
    escaped_bugs: int
    context_stale_incidents: int
    fallbacks: int
    failed_handoffs: int
    build_failures: int
    debate_rounds: int
    user_escalations: int
    total_cost_usd: float
    total_tokens: int
    mean_task_duration_s: float
```

### 4.15 `walk.orchestrator` — phase evidence package (§69)

```python
# src/walk/orchestrator/models.py
class PhaseEvidencePackage(WalkModel):
    """§69. Generated by orchestrator.EvidencePackager into `.ai/phases/PHASE-NN/evidence-package.md`."""
    phase_id: PhaseId
    gate_round: int
    generated_at: datetime
    gdd_coverage: dict[str, float]                 # GDD Coverage (§74) per GDD area
    stories_completed: list[WorkItemId]            # Stories Completed
    stories_open: list[WorkItemId]
    open_issues: list[BugId]                       # Open Issues
    known_limitations: list[str]                   # Known Limitations
    qc_status: str                                 # QC Status
    automated_tests: list[EvidenceId]              # Automated Tests
    performance_metrics: list[EvidenceId]          # Performance Metrics
    playable_build: EvidenceId | None              # Playable Build
    gameplay_recordings: list[EvidenceId]          # Gameplay Recording
    screenshots: list[EvidenceId]                  # Screenshots
    design_review: EvidenceId | None               # Design Review
    technical_review: EvidenceId | None            # Technical Review
    risk_summary: str                              # Risk Summary
    production_cost: dict[CostCategory, float]     # Production Cost (§84)
    retrospective_id: RetrospectiveId | None = None
```

### 4.13 `walk.integrations` — environment & kit (§24–§27)

```python
# src/walk/integrations/models.py
class ReadinessState(StrEnum):
    READY = "ready"
    MISSING = "missing"
    MISCONFIGURED = "misconfigured"
    UNKNOWN = "unknown"


class ComponentStatus(WalkModel):
    state: ReadinessState
    version: str | None = None
    detail: str = ""


class EnvironmentManifest(WalkModel):
    """§26 `.ai/project/environment.yaml`; produced by `walk doctor` / bootstrap preflight."""
    generated_at: datetime
    machine_id: str
    unity: ComponentStatus
    unity_packages: dict[str, ComponentStatus] = Field(default_factory=dict)
    tools: dict[str, ComponentStatus] = Field(default_factory=dict, description="git, unity_cli, graphify, dotnet, …")
    providers: dict[str, ComponentStatus] = Field(default_factory=dict, description="claude, codex, meshy, …")
    work_provider: ComponentStatus
    credentials: dict[str, ReadinessState] = Field(default_factory=dict, description="Presence only — never values")
    required_skills: dict[SkillName, ReadinessState] = Field(default_factory=dict)
    build_targets: dict[str, ReadinessState] = Field(default_factory=dict)
    drift_from: str | None = Field(default=None, description="machine_id of the manifest this one was compared against (§27)")
    drift_items: list[str] = Field(default_factory=list)


class ProductionKit(WalkModel):
    """§24 what bootstrap creates/validates (ARCHITECTURE.md §8 paths)."""
    project_constitution_path: str          # .ai/project/constitution.md
    project_constraints_path: str           # section of project.md
    agent_instruction_paths: list[str]      # .ai/agents/roles/*.md
    skill_names: list[SkillName]
    hook_config_path: str                   # .ai/agents/hooks.yaml
    approved_artifact_ids: list[ApprovedArtifactId]
    tool_config_path: str                   # .ai/agents/permissions.yaml + models.yaml
    environment_manifest_path: str          # .ai/project/environment.yaml
    initial_memory_paths: list[str]         # project.md, kernel-versions.yaml
    kernel_versions_path: str               # .ai/project/kernel-versions.yaml
    kit_version: str
    validated_at: datetime


class WorkProviderEvent(FrozenModel):
    """Normalised inbound work-state change (webhook or poll)."""
    provider: str
    external_ref: str
    kind: Literal["CREATED", "UPDATED", "TRANSITIONED", "COMMENTED", "DELETED"]
    external_status: str | None
    fields: JsonDict
    at: datetime
    delivery_id: str = Field(description="Webhook delivery id / poll batch id for dedup")
```

### 4.14 `walk.improvement` (§96–§98, §105, §112–§115)

```python
# src/walk/improvement/models.py
class ImprovementObservation(WalkModel):
    """§96. `.ai/improvements/OBS-NNNN.md` (project) or `$WALK_HOME/.improvement/observations/OBS-K-NNNN.md`."""
    id: ObservationId
    scope: LearningScope
    origin_project: ProjectKey
    work_item_id: WorkItemId | None
    run_id: RunId | None
    observed: str
    potential_cause: str
    possible_improvement: str
    improvement_scope: ImprovementScope
    source_signal: str = Field(description="§99 source, e.g. 'stale_context', 'repeated_fallback', 'user_override'")
    evidence_ids: list[EvidenceId] = Field(default_factory=list)
    ledger_seq_refs: list[int] = Field(default_factory=list)
    created_by: Actor
    created_at: datetime = Field(default_factory=utcnow)
    promoted_to: ObservationId | None = None


class ImprovementCandidate(WalkModel):
    """§98. Kernel scope: `$WALK_HOME/.improvement/candidates/IMP-NN.md`; project scope: `.ai/improvements/IMP-NN.md`."""
    id: ImprovementId
    scope: LearningScope
    state: CandidateState
    risk: ImprovementRisk
    problem: str
    evidence_ids: list[EvidenceId]
    observation_ids: list[ObservationId]
    frequency: str
    impact: str
    suspected_cause: str
    proposed_change: str
    expected_benefit: str
    risk_description: str
    affected_components: list[ImprovementScope]
    validation_method: str
    experiment_id: ExperimentId | None = None
    decision_id: DecisionId | None = None
    resulting_behavior_version: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Pattern(WalkModel):
    """§112 success pattern."""
    id: PatternId
    scope: LearningScope
    title: str
    description: str
    observed_benefits: list[str]
    evidence_ids: list[EvidenceId]
    applies_to: list[ImprovementScope]
    source_candidate_id: ImprovementId | None = None


class AntiPattern(WalkModel):
    """§113."""
    id: AntiPatternId
    scope: LearningScope
    title: str
    pattern: str
    observed_harm: list[str]
    replacement: str
    evidence_ids: list[EvidenceId]
    source_candidate_id: ImprovementId | None = None


class Retrospective(WalkModel):
    """§114–§115 levels: TASK / FEATURE / PHASE / PROJECT. `metrics` is walk.telemetry.models.RetrospectiveMetrics."""
    id: RetrospectiveId
    level: Literal["TASK", "FEATURE", "PHASE", "PROJECT"]
    subject_id: str
    project_key: ProjectKey
    metrics: RetrospectiveMetrics
    top_bottleneck: str
    top_defect: str
    narrative_markdown: str = Field(default="", description="LLM-written analysis; optional for small tasks (§114)")
    candidate_ids: list[ImprovementId]
    generated_at: datetime = Field(default_factory=utcnow)


class BehaviorVersion(WalkModel):
    """§105 versioned kernel behavior artifact (workflow table, constitution, skill, template, routing policy)."""
    kind: ImprovementScope
    name: str = Field(description="e.g. 'feature_workflow', 'LEAD_DEV', 'unity-debugging', 'story_template'")
    version: str = Field(description="semver-ish 'MAJOR.MINOR'")
    stage: RolloutStage
    content_sha256: str
    source_path: str
    candidate_id: ImprovementId | None = None
    changelog_entry: str | None = None
    introduced_at: datetime
    deprecated_at: datetime | None = None
    shadow_of: str | None = Field(default=None, description="§108 version this one shadows, when stage == EXPERIMENTAL in shadow mode")


class Experiment(WalkModel):
    """§107 controlled comparison [Stage 10]."""
    id: ExperimentId
    candidate_id: ImprovementId
    control_version: str
    treatment_version: str
    assignment: Literal["AB_BY_WORK_ITEM_HASH", "SHADOW"]
    metrics: list[str]
    started_at: datetime
    ended_at: datetime | None = None
    result_summary: str | None = None
    result_evidence_ids: list[EvidenceId] = Field(default_factory=list)
```

---

## 5. Entity relationship summary

```text
 Project 1──* Phase 1──* Epic 1──* Feature 1──* Story / Task
                                        │              │
                                        │              └──* Bug (related_feature_id, found_in_run_id)
                                        └── FeatureContext (.ai/features)         Bug ── BugContext (.ai/bugs)

 WorkItem 1──* WorkItemTransition
 WorkItem 1──* AgentRun 1──* Checkpoint
                      │  1──0..1 Handover(out)  ── Handover(in) 0..1──1 AgentRun (next)
                      │  1──* LedgerEvent        (also: WorkItem, Phase, Debate, Decision, Hook → LedgerEvent)
                      │  1──* CostRecord ──* Budget (scope roll-up)
                      └──* Evidence
 Debate 1──* DebatePosition ;  Debate 0..1──1 Decision ;  Decision *──* Evidence ;  Decision *──* WorkItem
 Escalation 0..1──1 ApprovalRequest ;  ToolCallRequest 0..1──1 ApprovalRequest
 ApprovedArtifact *──* GddRef ;  ApprovedArtifact 0..1── Decision (change authorisation)
 Phase 1──* PhaseEvidencePackage (one per gate_round) ── Retrospective ──* ImprovementCandidate ──* ImprovementObservation
 ImprovementCandidate 0..1── Experiment ; ImprovementCandidate 0..1── BehaviorVersion ; Pattern/AntiPattern ── Candidate
 Constitution (per AgentRole) + RuntimePolicy (per AgentRole) + PermissionRule* + Skill* + ToolSpec*  ──assemble──▶ AgentInstance
 AgentInstance + WorkItem + ContextBundle ──▶ AgentInput ──adapter──▶ AgentOutput ──OutputApplier──▶ (memory, evidence, decisions, work items, escalations, git)
```

Ownership (single source of truth): workflow state → `work_items.state` (SQLite); work backlog/priority/assignee → `WorkProvider`; project knowledge → `.ai/*.md` (git) with `memory_index` as a cache; history → `ledger_events`; code → git.

---

## 6. SQLite schema

### 6.1 Principles (ADR-0002)

- One DB per project: `<repo>/.ai/kernel.db`. One kernel-global DB: `$WALK_HOME/kernel.db` (tables marked **K**). Tables marked **P** are project-scoped; **PK** exist in both.
- Pattern: **aggregate JSON + indexed projection columns**. Each row stores the pydantic `model_dump_json()` in `json` and copies the fields needed for querying/indexing into typed columns. Readers deserialise `json`; writers update both in one statement.
- `PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=5000`.
- Timestamps are ISO-8601 UTC `TEXT`. Enums are `TEXT`. Money is `REAL` (USD). IDs are `TEXT`.
- No `UPDATE`/`DELETE` on `ledger_events`, `checkpoints`, `cost_records`, `evidence`, `work_item_transitions` (enforced by triggers `*_immutable`).

### 6.2 Tables

```sql
-- 0001_init.sql ---------------------------------------------------------------
CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL);
CREATE TABLE id_sequences (prefix TEXT PRIMARY KEY, next INTEGER NOT NULL);                    -- PK
CREATE TABLE kernel_instances (id TEXT PRIMARY KEY, hostname TEXT, started_at TEXT, heartbeat_at TEXT, pid INTEGER);
CREATE TABLE idempotency_keys (key TEXT PRIMARY KEY, operation TEXT NOT NULL, result_ref TEXT, created_at TEXT NOT NULL);

CREATE TABLE projects (key TEXT PRIMARY KEY, name TEXT NOT NULL, repo_path TEXT NOT NULL, current_phase_id TEXT,
                       paused INTEGER NOT NULL DEFAULT 0, json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);

CREATE TABLE phases (id TEXT PRIMARY KEY, project_key TEXT NOT NULL REFERENCES projects(key), ordinal INTEGER NOT NULL,
                     state TEXT NOT NULL, gate_round INTEGER NOT NULL DEFAULT 0, json TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE UNIQUE INDEX ix_phases_ordinal ON phases(project_key, ordinal);
CREATE INDEX ix_phases_state ON phases(project_key, state);

CREATE TABLE work_items (id TEXT PRIMARY KEY, kind TEXT NOT NULL, project_key TEXT NOT NULL REFERENCES projects(key),
                         parent_id TEXT REFERENCES work_items(id), phase_id TEXT REFERENCES phases(id),
                         state TEXT NOT NULL, state_version INTEGER NOT NULL DEFAULT 0, title TEXT NOT NULL,
                         owner_role TEXT, assigned_run_id TEXT, external_ref TEXT, priority TEXT NOT NULL, risk TEXT NOT NULL,
                         fix_loops INTEGER NOT NULL DEFAULT 0, json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX ix_work_items_state ON work_items(project_key, state);
CREATE INDEX ix_work_items_parent ON work_items(parent_id);
CREATE INDEX ix_work_items_phase ON work_items(phase_id, state);
CREATE UNIQUE INDEX ix_work_items_external ON work_items(external_ref) WHERE external_ref IS NOT NULL;

CREATE TABLE work_item_transitions (seq INTEGER PRIMARY KEY AUTOINCREMENT, work_item_id TEXT NOT NULL REFERENCES work_items(id),
                         from_state TEXT NOT NULL, to_state TEXT NOT NULL, event TEXT NOT NULL, source TEXT NOT NULL,
                         actor_role TEXT NOT NULL, run_id TEXT, reason TEXT, at TEXT NOT NULL);
CREATE INDEX ix_transitions_item ON work_item_transitions(work_item_id, seq);
CREATE TRIGGER work_item_transitions_immutable BEFORE UPDATE ON work_item_transitions BEGIN SELECT RAISE(ABORT,'immutable'); END;

CREATE TABLE release_candidates (id TEXT PRIMARY KEY, project_key TEXT NOT NULL, number INTEGER NOT NULL, state TEXT NOT NULL,
                         commit_sha TEXT NOT NULL, json TEXT NOT NULL, created_at TEXT NOT NULL);

CREATE TABLE agent_runs (id TEXT PRIMARY KEY, project_key TEXT NOT NULL, work_item_id TEXT NOT NULL REFERENCES work_items(id),
                         role TEXT NOT NULL, model_id TEXT NOT NULL, provider TEXT NOT NULL, effort TEXT NOT NULL, state TEXT NOT NULL,
                         purpose TEXT NOT NULL, kernel_instance TEXT NOT NULL, parent_run_id TEXT, provider_session_id TEXT,
                         started_at TEXT, ended_at TEXT, json TEXT NOT NULL);
CREATE INDEX ix_runs_state ON agent_runs(state, kernel_instance);
CREATE INDEX ix_runs_item ON agent_runs(work_item_id, started_at);

CREATE TABLE checkpoints (id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES agent_runs(id), work_item_id TEXT NOT NULL,
                         seq INTEGER NOT NULL, kind TEXT NOT NULL, head_sha TEXT NOT NULL, handover_id TEXT, at TEXT NOT NULL, json TEXT NOT NULL);
CREATE UNIQUE INDEX ix_checkpoints_run_seq ON checkpoints(run_id, seq);
CREATE TRIGGER checkpoints_immutable BEFORE UPDATE ON checkpoints BEGIN SELECT RAISE(ABORT,'immutable'); END;

CREATE TABLE handovers (id TEXT PRIMARY KEY, work_item_id TEXT NOT NULL, from_run_id TEXT NOT NULL, to_run_id TEXT,
                         reason TEXT NOT NULL, ai_path TEXT NOT NULL, created_at TEXT NOT NULL, json TEXT NOT NULL);
CREATE INDEX ix_handovers_item ON handovers(work_item_id, created_at);

CREATE TABLE ledger_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, at TEXT NOT NULL,
                         project_key TEXT NOT NULL, actor_role TEXT NOT NULL, work_item_id TEXT, run_id TEXT, phase_id TEXT,
                         model_id TEXT, tool TEXT, cost_usd REAL, outcome TEXT, json TEXT NOT NULL);
CREATE INDEX ix_ledger_kind_at ON ledger_events(kind, at);
CREATE INDEX ix_ledger_item ON ledger_events(work_item_id, seq);
CREATE INDEX ix_ledger_run ON ledger_events(run_id, seq);
CREATE INDEX ix_ledger_phase ON ledger_events(phase_id, kind);
CREATE TRIGGER ledger_events_no_update BEFORE UPDATE ON ledger_events BEGIN SELECT RAISE(ABORT,'ledger is append-only'); END;
CREATE TRIGGER ledger_events_no_delete BEFORE DELETE ON ledger_events BEGIN SELECT RAISE(ABORT,'ledger is append-only'); END;

CREATE TABLE cost_records (id TEXT PRIMARY KEY, at TEXT NOT NULL, project_key TEXT NOT NULL, category TEXT NOT NULL, provider TEXT NOT NULL,
                         model_id TEXT, dimension TEXT NOT NULL, quantity REAL NOT NULL, unit TEXT NOT NULL, cost_usd REAL NOT NULL DEFAULT 0,
                         run_id TEXT, work_item_id TEXT, phase_id TEXT, role TEXT, json TEXT NOT NULL);
CREATE INDEX ix_cost_item ON cost_records(work_item_id);
CREATE INDEX ix_cost_phase ON cost_records(phase_id, category);
CREATE INDEX ix_cost_run ON cost_records(run_id);
CREATE TRIGGER cost_records_immutable BEFORE UPDATE ON cost_records BEGIN SELECT RAISE(ABORT,'immutable'); END;

CREATE TABLE budgets (id TEXT PRIMARY KEY, scope TEXT NOT NULL, scope_id TEXT NOT NULL, dimension TEXT NOT NULL, "limit" REAL NOT NULL,
                         consumed REAL NOT NULL DEFAULT 0, soft_notified INTEGER NOT NULL DEFAULT 0, json TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX ix_budgets_scope ON budgets(scope, scope_id);

CREATE TABLE evidence (id TEXT PRIMARY KEY, kind TEXT NOT NULL, work_item_id TEXT, phase_id TEXT, run_id TEXT, uri TEXT NOT NULL,
                         sha256 TEXT, produced_at TEXT NOT NULL, json TEXT NOT NULL);
CREATE INDEX ix_evidence_item ON evidence(work_item_id, kind);
CREATE INDEX ix_evidence_phase ON evidence(phase_id, kind);
CREATE TRIGGER evidence_immutable BEFORE UPDATE ON evidence BEGIN SELECT RAISE(ABORT,'immutable'); END;

CREATE TABLE decisions (id TEXT PRIMARY KEY, category TEXT NOT NULL, status TEXT NOT NULL, topic TEXT NOT NULL, owner_role TEXT NOT NULL,
                         autonomy_level INTEGER NOT NULL, debate_id TEXT, version INTEGER NOT NULL DEFAULT 1, ai_path TEXT NOT NULL,
                         decided_at TEXT NOT NULL, json TEXT NOT NULL);
CREATE INDEX ix_decisions_status ON decisions(status, category);
CREATE TABLE decision_work_items (decision_id TEXT NOT NULL REFERENCES decisions(id), work_item_id TEXT NOT NULL, PRIMARY KEY (decision_id, work_item_id));

CREATE TABLE debates (id TEXT PRIMARY KEY, topic TEXT NOT NULL, category TEXT NOT NULL, state TEXT NOT NULL, work_item_id TEXT,
                         round INTEGER NOT NULL DEFAULT 0, max_rounds INTEGER NOT NULL, decision_id TEXT, opened_at TEXT NOT NULL, json TEXT NOT NULL);
CREATE TABLE debate_positions (id INTEGER PRIMARY KEY AUTOINCREMENT, debate_id TEXT NOT NULL REFERENCES debates(id), round INTEGER NOT NULL,
                         role TEXT NOT NULL, run_id TEXT NOT NULL, at TEXT NOT NULL, json TEXT NOT NULL);
CREATE INDEX ix_positions_debate ON debate_positions(debate_id, round);

CREATE TABLE escalations (id TEXT PRIMARY KEY, from_role TEXT NOT NULL, to_level INTEGER NOT NULL, category TEXT NOT NULL, work_item_id TEXT,
                         run_id TEXT, approval_request_id TEXT, resolved_decision_id TEXT, created_at TEXT NOT NULL, json TEXT NOT NULL);

CREATE TABLE approval_requests (id TEXT PRIMARY KEY, kind TEXT NOT NULL, approver TEXT NOT NULL, requested_by_role TEXT NOT NULL,
                         run_id TEXT, work_item_id TEXT, state TEXT NOT NULL, requested_at TEXT NOT NULL, decided_at TEXT, json TEXT NOT NULL);
CREATE INDEX ix_approvals_state ON approval_requests(state, approver);

CREATE TABLE approved_artifacts (id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL, scope TEXT NOT NULL, version INTEGER NOT NULL,
                         content_sha256 TEXT NOT NULL, ai_path TEXT NOT NULL, approved_at TEXT NOT NULL, json TEXT NOT NULL);

CREATE TABLE memory_index (path TEXT PRIMARY KEY, doc_id TEXT NOT NULL, type TEXT NOT NULL, title TEXT NOT NULL, status TEXT,
                         version INTEGER NOT NULL, updated_at TEXT NOT NULL, freshness_commit TEXT, freshness_status TEXT,
                         freshness_checked_at TEXT, raw_sha256 TEXT NOT NULL, relevant_files_json TEXT NOT NULL, related_json TEXT NOT NULL);
CREATE INDEX ix_memory_doc ON memory_index(doc_id);
CREATE INDEX ix_memory_type ON memory_index(type, status);

CREATE TABLE hook_executions (id INTEGER PRIMARY KEY AUTOINCREMENT, hook_name TEXT NOT NULL, hook_id TEXT NOT NULL, at TEXT NOT NULL,
                         run_id TEXT, work_item_id TEXT, status TEXT NOT NULL, duration_ms INTEGER NOT NULL, message TEXT);
CREATE INDEX ix_hooks_name_at ON hook_executions(hook_name, at);

CREATE TABLE commands (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, args_json TEXT NOT NULL, requested_at TEXT NOT NULL,
                         requested_by TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'PENDING');
CREATE TABLE command_results (command_id INTEGER PRIMARY KEY REFERENCES commands(id), finished_at TEXT NOT NULL, ok INTEGER NOT NULL, result_json TEXT NOT NULL);

CREATE TABLE skill_projections (skill TEXT NOT NULL, provider TEXT NOT NULL, target_path TEXT NOT NULL, content_sha256 TEXT NOT NULL,
                         generated_from_sha256 TEXT NOT NULL, generated_at TEXT NOT NULL, PRIMARY KEY (skill, provider, target_path));

CREATE TABLE work_provider_sync (provider TEXT PRIMARY KEY, last_sync_at TEXT NOT NULL, last_delivery_id TEXT);
CREATE TABLE webhook_deliveries (delivery_id TEXT PRIMARY KEY, received_at TEXT NOT NULL);                     -- dedup

-- improvement (PK = both DBs; project DB holds scope=PROJECT rows, kernel DB holds scope=KERNEL rows)
CREATE TABLE improvement_observations (id TEXT PRIMARY KEY, scope TEXT NOT NULL, origin_project TEXT NOT NULL, improvement_scope TEXT NOT NULL,
                         source_signal TEXT NOT NULL, work_item_id TEXT, run_id TEXT, promoted_to TEXT, created_at TEXT NOT NULL, json TEXT NOT NULL);
CREATE INDEX ix_obs_signal ON improvement_observations(source_signal, created_at);
CREATE TABLE improvement_candidates (id TEXT PRIMARY KEY, scope TEXT NOT NULL, state TEXT NOT NULL, risk TEXT NOT NULL, created_at TEXT NOT NULL, json TEXT NOT NULL);
CREATE TABLE patterns (id TEXT PRIMARY KEY, scope TEXT NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('PATTERN','ANTI')), title TEXT NOT NULL, json TEXT NOT NULL);
CREATE TABLE retrospectives (id TEXT PRIMARY KEY, level TEXT NOT NULL, subject_id TEXT NOT NULL, project_key TEXT NOT NULL, generated_at TEXT NOT NULL, json TEXT NOT NULL);
CREATE TABLE behavior_versions (kind TEXT NOT NULL, name TEXT NOT NULL, version TEXT NOT NULL, stage TEXT NOT NULL, content_sha256 TEXT NOT NULL,
                         introduced_at TEXT NOT NULL, json TEXT NOT NULL, PRIMARY KEY (kind, name, version));
CREATE TABLE experiments (id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT, json TEXT NOT NULL);  -- K
CREATE TABLE kernel_changelog (version TEXT NOT NULL, entry_seq INTEGER NOT NULL, candidate_id TEXT, changed TEXT NOT NULL, reason TEXT NOT NULL,
                         evidence TEXT NOT NULL, at TEXT NOT NULL, PRIMARY KEY (version, entry_seq));                                 -- K
```

Table → DB: all tables above except `experiments`, `kernel_changelog` exist in the project DB; the kernel DB (`$WALK_HOME/kernel.db`) contains `schema_migrations`, `id_sequences`, `improvement_observations`, `improvement_candidates`, `patterns`, `retrospectives`, `behavior_versions`, `experiments`, `kernel_changelog`.

### 6.3 Migration approach

- Files: `src/walk/persistence/migrations/project/NNNN_<name>.sql` and `.../kernel/NNNN_<name>.sql`, `NNNN` zero-padded 4 digits, strictly increasing, immutable once released.
- `MigrationRunner.apply_pending(db, kind)` at every kernel/CLI start: reads `schema_migrations`, applies each missing file inside one transaction (`BEGIN IMMEDIATE`), records `(version, name, applied_at)`, then sets `PRAGMA user_version = <latest>`. Failure aborts startup with `ConfigError`.
- Backward-compatible evolutions (new nullable column, new index, new table) are SQL-only. Data reshaping uses a paired Python step `NNNN_<name>.py` exposing `def migrate(conn: sqlite3.Connection) -> None`, run after the SQL of the same number.
- JSON payload evolution is handled by pydantic: models keep `schema_version`-free defaults for new fields; renamed fields use `AliasChoices` for one release.
- `walk db backup` copies the DB via `sqlite3.Connection.backup()` before any migration with a Python step.
