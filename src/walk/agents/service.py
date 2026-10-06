"""Default agent manager: role constitutions and runtime policies (§8, §12-§15)."""

from typing import Final

from walk.agents.constitution_loader import ConstitutionLoader
from walk.agents.models import AgentInstance, Constitution, RuntimePolicy
from walk.agents.policy_loader import PolicyLoader
from walk.common.enums import Effort
from walk.common.errors import ConfigError
from walk.common.ids import ModelId
from walk.common.roles import AgentRole
from walk.permissions.protocols import PermissionManager
from walk.workflow.models import WorkItem

_EXECUTION_CONTRACT: Final = "E01-S18"


def _later(*_arguments: object) -> ConfigError:
    """The error of a protocol method that E01-S18 implements."""
    return ConfigError(
        f"implemented in {_EXECUTION_CONTRACT}", detail={"story": _EXECUTION_CONTRACT}
    )


class DefaultAgentManager:
    """`AgentManager` over the constitution and policy loaders."""

    def __init__(
        self,
        constitutions: ConstitutionLoader,
        policies: PolicyLoader,
        permissions: PermissionManager,
    ) -> None:
        """Wire the manager.

        Args:
            constitutions: Default + override constitutions.
            policies: Default + override runtime policies.
            permissions: Merges constitution rules at instantiation (E01-S18).
        """
        self._constitutions = constitutions
        self._policies = policies
        self._permissions = permissions

    def load_constitution(self, role: AgentRole) -> Constitution:
        """The role's merged constitution (ADR-0013).

        Raises:
            ConstitutionError: See `ConstitutionLoader.load`.
        """
        return self._constitutions.load(role)

    def load_runtime_policy(self, role: AgentRole) -> RuntimePolicy:
        """The role's merged runtime policy.

        Raises:
            ConstitutionError: See `PolicyLoader.load`.
        """
        return self._policies.load(role)

    async def instantiate(  # noqa: PLR0917 - signature fixed by INTERFACES §1.2
        self,
        role: AgentRole,
        item: WorkItem,
        model_id: ModelId,
        effort: Effort,
        budget_ids: list[str],
        available_env_keys: set[str],
    ) -> AgentInstance:
        """§9 assembly (E01-S18)."""
        raise _later(role, item, model_id, effort, budget_ids, available_env_keys)

    def render_instructions(self, agent: AgentInstance, item: WorkItem, purpose: str) -> str:
        """Task prompt rendering (E01-S18)."""
        raise _later(agent, item, purpose)

    def list_roles(self) -> list[AgentRole]:
        """Roles that have a default constitution."""
        return self._constitutions.available_roles()
