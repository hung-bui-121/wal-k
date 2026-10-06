"""Model router and adapter protocols (INTERFACES §1.4, §2.1; ADR-0004).

`ModelRouter.fallback` arrives with `FallbackRequest` in E01-S28.
"""

from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from walk.agents.models import AgentInput, AgentOutput, ModelPolicy
from walk.common.enums import Effort
from walk.common.ids import ModelId, RunId
from walk.common.roles import AgentRole
from walk.model_router.models import (
    AdapterHealth,
    AgentEvent,
    CapabilityRegistry,
    FallbackTrigger,
    ModelDescriptor,
    ProviderEffortConfig,
    ProviderSessionRef,
    RoutingDecision,
    RunSession,
    TaskProfile,
    UsageReport,
)
from walk.skills.protocols import SkillProjector


class ModelAdapter(Protocol):
    """One per provider. Stateless w.r.t. role (Invariant 1).

    Only module allowed to import the provider SDK / spawn its CLI.
    """

    provider: str

    def descriptors(self) -> list[ModelDescriptor]:
        """Capability descriptors for the models this adapter serves.

        Defaults; overridable in models.yaml.
        """
        ...

    async def health(self) -> AdapterHealth:
        """Cheap liveness/auth check (CLI present + logged in / API reachable). Cached ≤ 60 s."""
        ...

    def map_effort(self, effort: Effort, model_id: ModelId) -> ProviderEffortConfig:
        """§17 translate.

        Must be total over Effort for every supported model (degrade to nearest supported).
        """
        ...

    def run(self, input: AgentInput, session: RunSession) -> AsyncIterator[AgentEvent]:  # noqa: A002 - parameter name fixed by INTERFACES §2.1
        """Start a fresh provider session; stream normalised AgentEvents.

        Last event FINAL_OUTPUT(output=AgentOutput) or ERROR. MUST: drop thinking/reasoning
        blocks (§22); route every tool call through session.permission_authorizer before
        execution (Claude) or configure sandbox equivalently (Codex); emit USAGE at least at
        end; emit session ref in STARTED.
        """
        ...

    def resume(
        self, session_ref: ProviderSessionRef, instruction: str, session: RunSession
    ) -> AsyncIterator[AgentEvent]:
        """Continue provider-side session (Claude `resume=session_id`; Codex `exec resume <id>`).

        Raise NotResumable if unsupported.
        """
        ...

    async def cancel(self, run_id: RunId) -> None:
        """Stop the run's stream; it ends with ENDED."""
        ...

    def usage(self, run_id: RunId) -> UsageReport:
        """Cumulative usage of a run (also streamed as USAGE events)."""
        ...

    def skill_projector(self) -> SkillProjector:
        """The provider's skill projection format (ADR-0007)."""
        ...

    def parse_output(self, raw: str) -> AgentOutput:
        """Validate JSON against AgentOutput; raise OutputInvalid with field errors.

        Used for the repair turn.
        """
        ...


class ModelRouter(Protocol):
    """§14-§16, §21, §23. Hosted by walk.model_router."""

    def registry(self) -> CapabilityRegistry:
        """The descriptors of every configured model."""
        ...

    def adapter_for(self, model_id: ModelId) -> ModelAdapter:
        """The adapter serving ``model_id``."""
        ...

    async def select(
        self,
        role: AgentRole,
        policy: ModelPolicy,
        profile: TaskProfile,
        effort: Effort,
        *,
        exclude: Sequence[ModelId] = (),
        task_override: ModelId | None = None,
    ) -> RoutingDecision:
        """INTERFACES §5.3 steps 1-4.

        Ordered candidates (override, preferred, fallback) minus restricted/disabled/excluded;
        reject on capability (§16), context window, effort support, health; first survivor
        wins. Ledger MODEL_SELECTED by caller.
        """
        ...

    def classify_error(self, exc: BaseException, adapter: ModelAdapter) -> FallbackTrigger | None:
        """Maps adapter-specific exceptions/events to §21 triggers.

        None = not a fallback condition.
        """
        ...

    async def health_all(self) -> dict[ModelId, AdapterHealth]:
        """Health of every configured model, one adapter query each."""
        ...
