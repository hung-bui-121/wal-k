"""`DefaultTaskRouter`: role and purpose of ready work (INTERFACES §4; E01-S29).

The rows come from the workflow's `scheduled_states.yaml` (the same file that decides which
items are schedulable). E01 resolves literal and contract roles; the full routing profile,
Invariant 4's implementer check and contract-path parallelism arrive with E03-S07.
"""

from pathlib import Path
from typing import Final, Literal

import yaml
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError, field_validator

from walk.agents.protocols import AgentManager
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.model_router.models import TaskProfile
from walk.orchestrator.errors import NoScheduledRole
from walk.orchestrator.models import RouteDecision
from walk.runtime.repository import AgentRunRepository
from walk.workflow.models import (
    Bug,
    Story,
    StoryContract,
    Task,
    WorkItem,
    WorkItemKind,
    WorkItemState,
)
from walk.workflow.protocols import WorkflowManager

_OWNER: Final = "contract.owner_role"
_REVIEWER: Final = "contract.reviewer_role"
_DEFAULT_CONTRACT_ROLES: Final = {_OWNER: AgentRole.SENIOR_DEV, _REVIEWER: AgentRole.LEAD_DEV}


class _Row(BaseModel):
    """One ``scheduled_states.yaml`` row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: WorkItemKind
    state: WorkItemState
    role: str
    fallback_role: AgentRole | None = None
    purpose: Literal["PLAN", "DESIGN", "IMPLEMENT", "REVIEW", "QC", "TRIAGE"]

    @field_validator("role")
    @classmethod
    def _known_role(cls, value: str) -> str:
        if value not in _DEFAULT_CONTRACT_ROLES and value not in AgentRole.__members__:
            msg = f"unknown role {value!r}"
            raise ValueError(msg)
        return value


class DefaultTaskRouter:
    """`TaskRouter` over the scheduled-states rows and the role catalogue."""

    def __init__(
        self,
        scheduled_states: Path,
        agents: AgentManager,
        runs: AgentRunRepository,
        workflow: WorkflowManager,
    ) -> None:
        """Load the rows once.

        Args:
            scheduled_states: `walk/workflow/tables/scheduled_states.yaml`.
            agents: Enabled roles (`list_roles`) and their runtime policies.
            runs: Run history (Invariant 4 implementer check, E03-S07).
            workflow: Work-item lookups (contract-path parallelism, E03-S07).

        Raises:
            ConfigError: The file is missing or invalid, or a role name is unknown.
        """
        self._rows = {(row.kind, row.state): row for row in _load_rows(scheduled_states)}
        self._agents = agents
        self._runs = runs
        self._workflow = workflow

    def route(self, item: WorkItem, state: WorkItemState) -> RouteDecision:
        """Role, purpose, task profile and cross-model preference for ``item`` in ``state``.

        A ``contract.*`` role reads the item's contract (SENIOR_DEV/LEAD_DEV without one); a
        role that is not enabled (`AgentManager.list_roles`) is replaced by ``fallback_role``.

        Raises:
            NoScheduledRole: ``(item.kind, state)`` has no row.
            ConstitutionError: The role's runtime policy cannot be loaded.
        """
        row = self._rows.get((item.kind, state))
        if row is None:
            msg = f"no scheduled role for {item.kind.value} in {state.value}"
            raise NoScheduledRole(msg, detail={"kind": item.kind.value, "state": state.value})
        contract = _contract(item)
        role = _role(row.role, contract)
        if row.fallback_role is not None and role not in self._agents.list_roles():
            role = row.fallback_role
        policy = self._agents.load_runtime_policy(role)
        profile = TaskProfile(
            required_capabilities=[],
            required_tools=list(policy.allowed_tools),
            required_skills=list(contract.required_skills) if contract is not None else [],
            estimated_context_tokens=0,
            risk=item.risk,
            implementer_model_id=None,
        )
        return RouteDecision(
            role=role,
            purpose=row.purpose,
            profile=profile,
            cross_model_review=policy.model_policy.cross_model_review,
        )

    def can_run_parallel(self, a: WorkItem, b: WorkItem) -> bool:
        """False for the same item, a dependency edge either way, or one explicit branch."""
        if a.id == b.id:
            return False
        if a.id in _dependencies(b) or b.id in _dependencies(a):
            return False
        return not (a.branch is not None and a.branch == b.branch)


def _load_rows(path: Path) -> list[_Row]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return TypeAdapter(list[_Row]).validate_python(data)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        msg = f"invalid {path.name}: {exc}"
        raise ConfigError(msg, detail={"path": str(path)}) from exc


def _contract(item: WorkItem) -> StoryContract | None:
    return item.contract if isinstance(item, Story | Task | Bug) else None


def _role(name: str, contract: StoryContract | None) -> AgentRole:
    if name == _OWNER:
        return contract.owner_role if contract is not None else _DEFAULT_CONTRACT_ROLES[name]
    if name == _REVIEWER:
        return contract.reviewer_role if contract is not None else _DEFAULT_CONTRACT_ROLES[name]
    return AgentRole(name)


def _dependencies(item: WorkItem) -> list[str]:
    contract = _contract(item)
    return list(contract.dependencies) if contract is not None else []
