"""Base models and common value objects (DOMAIN-MODEL §1.1)."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from walk.common.ids import ModelId, RunId
from walk.common.roles import AgentRole

JsonDict = dict[str, Any]


class WalkModel(BaseModel):
    """Base for every kernel data contract.

    Unknown fields are a validation error and assignments are validated. Enum fields hold
    enum members in Python and serialise by value.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True, populate_by_name=True)


class FrozenModel(WalkModel):
    """Immutable value object (ledger events, evidence, checkpoints)."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


def utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime.

    Services take an injected ``Clock`` instead; this helper is for model defaults only.
    """
    return datetime.now(tz=UTC)


class Actor(FrozenModel):
    """Who did something: a role, optionally the model and the run that executed it."""

    role: AgentRole = Field(description="Role that acted; USER and KERNEL are actors too.")
    model_id: ModelId | None = Field(default=None, description="Model that executed, if any.")
    run_id: RunId | None = Field(default=None, description="Agent run that acted, if any.")
