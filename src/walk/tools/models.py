"""Tool catalogue contracts (§30; DOMAIN-MODEL §3 `ToolKind`, §4.6 `ToolSpec`)."""

import re
from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

from walk.budgets.models import BudgetDimension, CostCategory
from walk.common.ids import ToolName
from walk.common.models import WalkModel


class ToolKind(StrEnum):
    """How a tool is executed."""

    PROVIDER_NATIVE = "PROVIDER_NATIVE"  # file/shell tools of the model provider
    CLI = "CLI"  # executable on PATH used through shell (graphify, dotnet)
    KERNEL = "KERNEL"  # executed by the kernel via IntegrationManager (jira.*, git.*, unity.*)
    MCP = "MCP"  # reserved; no provider in Stage 8 (ADR-0015 D-7)


class ToolSpec(WalkModel):
    """§30 registry entry. Tools are distinct from role, model and skill."""

    name: ToolName = Field(description="Unique tool name, e.g. 'git.commit', 'bash', 'git-cli'.")
    kind: ToolKind = Field(description="How the tool is executed.")
    description: str = Field(description="What the tool does.")
    provider: str | None = Field(
        default=None,
        description=(
            "Integration that executes KERNEL tools: 'jira', 'git', 'unity', 'graphify', 'meshy'"
        ),
    )
    executable: str | None = Field(default=None, description="CLI binary for kind=CLI")
    command_patterns: list[str] = Field(
        default_factory=list, description="Shell regexes that identify this tool in a command"
    )
    cost_dimension: BudgetDimension = Field(
        default=BudgetDimension.TOOL_CALLS, description="Budget dimension one call meters."
    )
    cost_category: CostCategory = Field(
        default=CostCategory.COMPUTE, description="Cost category of the tool's spend."
    )
    protected_action: str | None = Field(
        default=None, description="ProtectedAction.name if this tool is protected"
    )
    requires_env: list[str] = Field(
        default_factory=list,
        description="EnvironmentManifest keys that must be ready; 'a|b' = any alternative",
    )
    version: str = Field(default="1.0", description="Version of the tool definition.")

    @field_validator("command_patterns")
    @classmethod
    def _patterns_compile(cls, patterns: list[str]) -> list[str]:
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                msg = f"invalid command pattern {pattern!r}: {exc}"
                raise ValueError(msg) from exc
        return patterns

    @model_validator(mode="after")
    def _cli_needs_executable(self) -> Self:
        if self.kind is ToolKind.CLI and self.executable is None:
            msg = "a CLI tool needs an executable"
            raise ValueError(msg)
        return self
