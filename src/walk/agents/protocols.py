"""Agent service protocol (INTERFACES §1.2)."""

from typing import Protocol

from walk.agents.models import AgentInstance, Constitution, RuntimePolicy
from walk.common.enums import Effort
from walk.common.ids import ModelId
from walk.common.roles import AgentRole
from walk.workflow.models import WorkItem


class AgentManager(Protocol):
    """§8 role loading, constitution loading, agent lifecycle metadata. Hosted by walk.agents."""

    def load_constitution(self, role: AgentRole) -> Constitution:
        """Kernel default merged with `.ai/agents/roles/<role>.md` override (ADR-0013).

        Cached per process.
        """
        ...

    def load_runtime_policy(self, role: AgentRole) -> RuntimePolicy:
        """Kernel default merged with `.ai/agents/policies.yaml`."""
        ...

    async def instantiate(  # noqa: PLR0917 - signature fixed by INTERFACES §1.2
        self,
        role: AgentRole,
        item: WorkItem,
        model_id: ModelId,
        effort: Effort,
        budget_ids: list[str],
        available_env_keys: set[str],
    ) -> AgentInstance:
        """§9 assembly; the caller passes RoutingDecision.model_id/effort.

        (So agents stays below model_router.) Merges constitution.tool_permissions into
        PermissionManager.rules_for(role, extra=…). Validates required skills/tools available
        (§29) else raises ConfigError.
        """
        ...

    def render_instructions(self, agent: AgentInstance, item: WorkItem, purpose: str) -> str:
        """Render the versioned task prompt template `walk/agents/templates/<purpose>.md.j2`.

        BehaviorVersion kind=PROMPT.
        """
        ...

    def list_roles(self) -> list[AgentRole]:
        """Roles that have a default constitution."""
        ...
