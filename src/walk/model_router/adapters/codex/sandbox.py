"""Codex sandbox configuration (ADR-0006 D-5, ADR-0009 D-5, ADR-0014)."""

from typing import Final

from pydantic import Field

from walk.common.models import FrozenModel

DEFAULT_SANDBOX_MODE: Final = "workspace-write"


class CodexSandboxConfig(FrozenModel):
    """How one `codex exec` run is sandboxed."""

    mode: str = Field(
        default=DEFAULT_SANDBOX_MODE,
        description="read-only | workspace-write | danger-full-access (never set by the kernel)",
    )
    cwd: str = Field(description="Working directory the sandbox may write: the run's worktree.")
    network_enabled: bool = Field(default=False, description="Allow network access in the sandbox.")
    writable_roots: list[str] = Field(
        default_factory=list, description="Extra writable directories beyond cwd (none by default)."
    )
