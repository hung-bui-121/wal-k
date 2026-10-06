"""Tool registry protocol (INTERFACES §1.11)."""

from typing import Protocol

from walk.common.ids import ToolName
from walk.tools.models import ToolSpec


class ToolRegistry(Protocol):
    """§30. Hosted by walk.tools."""

    def all(self) -> list[ToolSpec]:
        """Every registered tool."""
        ...

    def get(self, name: ToolName) -> ToolSpec:
        """The tool called ``name``; ConfigError when unknown."""
        ...

    def available(self, ready_env_keys: set[str]) -> list[ToolSpec]:
        """Tools whose requires_env ⊆ ready_env_keys.

        Keys of EnvironmentManifest components in state READY; passed by caller.
        """
        ...

    def for_role(
        self, allowed: list[ToolName], ready_env_keys: set[str], required: list[ToolName]
    ) -> list[ToolSpec]:
        """Available tools named in ``allowed`` or ``required``; missing required → ConfigError.

        `allowed` = RuntimePolicy.allowed_tools.
        """
        ...

    def identify(self, command: str) -> ToolSpec | None:
        """Match a shell command to a CLI ToolSpec by command_patterns.

        Used for permission checks and cost attribution.
        """
        ...
