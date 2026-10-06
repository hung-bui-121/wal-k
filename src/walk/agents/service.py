"""Default agent manager: constitutions, runtime policies and agent assembly (§8-§15, §126)."""

from typing import Final

from walk.agents.constitution_loader import ConstitutionLoader
from walk.agents.models import (
    AgentInstance,
    AgentOutputStatus,
    Constitution,
    ExpectedOutput,
    RuntimePolicy,
)
from walk.agents.policy_loader import PolicyLoader
from walk.agents.rendering import TemplateRenderer
from walk.common.enums import Effort
from walk.common.errors import ConfigError
from walk.common.ids import ModelId, ToolName
from walk.common.roles import AgentRole
from walk.permissions.protocols import PermissionManager
from walk.skills.protocols import SkillRegistry
from walk.tools.protocols import ToolRegistry
from walk.workflow.models import Bug, Story, StoryContract, Task, WorkItem

# StoryContract has no field for required tools (§29); a constraint `tool:<name>` marks one.
_REQUIRED_TOOL_PREFIX: Final = "tool:"

_BUILD = (
    AgentOutputStatus.COMPLETED,
    AgentOutputStatus.PARTIAL,
    AgentOutputStatus.BLOCKED,
    AgentOutputStatus.FAILED,
)
_VERDICT = (AgentOutputStatus.APPROVED, AgentOutputStatus.REJECTED, AgentOutputStatus.NEEDS_INPUT)
_ADVISORY = (AgentOutputStatus.COMPLETED, AgentOutputStatus.NEEDS_INPUT, AgentOutputStatus.FAILED)
_STATUS_OPTIONS: Final[dict[str, tuple[AgentOutputStatus, ...]]] = {
    "IMPLEMENT": _BUILD,
    "REVIEW": _VERDICT,
    "QC": _VERDICT,
    "TRIAGE": _ADVISORY,
    "PLAN": _ADVISORY,
    "DESIGN": _ADVISORY,
    "ANALYSIS": _ADVISORY,
    "RETRO": _ADVISORY,
    "DEBATE": _ADVISORY,
}
_DELIVERABLES: Final[dict[str, tuple[str, ...]]] = {
    "IMPLEMENT": ("changes in the worktree that meet every acceptance criterion", "tests"),
    "REVIEW": ("a review verdict with findings",),
    "QC": ("a QC verdict with evidence for each acceptance criterion",),
    "TRIAGE": ("a triage verdict: severity, owner role, affected systems",),
    "PLAN": ("new tasks with executable contracts",),
    "DESIGN": ("a technical design recorded as a context update",),
    "ANALYSIS": ("findings backed by evidence",),
    "RETRO": ("observations on what to keep and what to change",),
    "DEBATE": ("a debate position",),
}


class DefaultAgentManager:
    """`AgentManager` over the loaders, the permission policy and the tool catalogue."""

    def __init__(
        self,
        constitutions: ConstitutionLoader,
        policies: PolicyLoader,
        permissions: PermissionManager,
        tools: ToolRegistry,
        renderer: TemplateRenderer,
        *,
        skills: SkillRegistry | None = None,
    ) -> None:
        """Wire the manager.

        Args:
            constitutions: Default + override constitutions.
            policies: Default + override runtime policies.
            permissions: Merges constitution rules at instantiation.
            tools: Resolves the role's tools against the environment.
            renderer: Task prompt templates.
            skills: Validates skill names when given (wired in E02-S05).
        """
        self._constitutions = constitutions
        self._policies = policies
        self._permissions = permissions
        self._tools = tools
        self._renderer = renderer
        self._skills = skills

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
        """§9 assembly; the caller passes RoutingDecision.model_id/effort.

        Permissions are the kernel rules plus the constitution's (narrowing only). Tools are
        the policy's allowed tools available in the environment, plus the contract's
        ``tool:<name>`` constraints, which must be available. Skills are the policy defaults
        followed by the contract's required skills.

        Raises:
            ConfigError: A required tool is unavailable, or (with a skill registry) a skill
                is unknown.
            ConstitutionError: The constitution or policy cannot be loaded.
        """
        constitution = self.load_constitution(role)
        policy = self.load_runtime_policy(role)
        contract = _contract(item)
        permissions = self._permissions.rules_for(role, extra=constitution.tool_permissions)
        required_tools: list[ToolName] = []
        contract_skills: list[str] = []
        if contract is not None:
            required_tools = [
                c.removeprefix(_REQUIRED_TOOL_PREFIX).strip()
                for c in contract.constraints
                if c.startswith(_REQUIRED_TOOL_PREFIX)
            ]
            contract_skills = list(contract.required_skills)
        tools = self._tools.for_role(policy.allowed_tools, available_env_keys, required_tools)
        skills = list(dict.fromkeys([*policy.default_skills, *contract_skills]))
        if self._skills is not None:
            self._skills.for_role(role, skills)
        return AgentInstance(
            role=role,
            constitution=constitution,
            runtime_policy=policy,
            skills=skills,
            tools=[spec.name for spec in tools],
            permissions=permissions,
            model_id=model_id,
            effort=effort,
            budget_ids=list(budget_ids),
        )

    def render_instructions(self, agent: AgentInstance, item: WorkItem, purpose: str) -> str:
        """Render `templates/<purpose>.md.j2` for ``item`` without a handover.

        The executor (E01-S27) re-renders with the handover when one exists.

        Raises:
            ConfigError: Unknown purpose or a template error.
        """
        if purpose not in _STATUS_OPTIONS:
            msg = f"unknown template purpose: {purpose}"
            raise ConfigError(msg, detail={"purpose": purpose})
        contract = _contract(item)
        expected = ExpectedOutput(
            status_options=list(_STATUS_OPTIONS[purpose]),
            deliverables=list(_DELIVERABLES[purpose]),
            required_evidence=list(contract.required_evidence) if contract else [],
        )
        return self._renderer.render(
            purpose,
            item=item,
            agent=agent,
            expected_output=expected,
            handover=None,
        )

    def list_roles(self) -> list[AgentRole]:
        """Roles that have a default constitution."""
        return self._constitutions.available_roles()


def _contract(item: WorkItem) -> StoryContract | None:
    return item.contract if isinstance(item, Story | Task | Bug) else None
