"""Project hooks declared in `.ai/agents/hooks.yaml` (§32; ARCHITECTURE §4.1; E02-S09).

A project hook runs a shell command or an allowlisted kernel action. It always runs after the
builtins (priority ≥ 50) and can never replace or disable a required builtin: its id lives in
the ``project.`` namespace. Shell commands receive the `HookContext` as ``WALK_HOOK_*``
environment variables on top of the scrubbed agent environment (no secrets).
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Final, Self

import yaml
from pydantic import Field, ValidationError, model_validator

from walk.common.errors import ConfigError
from walk.common.models import WalkModel
from walk.hooks.models import Hook, HookContext, HookFailPolicy, HookName

HOOK_ENV_PREFIX = "WALK_HOOK_"
KERNEL_ACTIONS: tuple[str, ...] = ("memory.rebuild_index", "skills.sync", "telemetry.counter")

_MIN_PROJECT_PRIORITY: Final = 50  # builtin MUST hooks use < 50 and always run first
_MAX_TIMEOUT_S: Final = 3600
_DEFAULT_TIMEOUT_S: Final = 120
_DEFAULT_PRIORITY: Final = 100


class ProjectHookSpec(WalkModel):
    """One hook of `.ai/agents/hooks.yaml`: exactly one of ``command`` / ``kernel_action``."""

    name: HookName = Field(description="Lifecycle point the hook attaches to.")
    id: str = Field(pattern=r"^project\.[a-z0-9-]+$", description="Unique id, 'project.<name>'.")
    command: str | None = Field(default=None, description="Shell command run in the repo root.")
    kernel_action: str | None = Field(default=None, description="One of KERNEL_ACTIONS.")
    priority: int = Field(
        default=_DEFAULT_PRIORITY,
        ge=_MIN_PROJECT_PRIORITY,
        description="Lower runs first; project hooks run after the builtins (>= 50).",
    )
    fail_policy: HookFailPolicy = Field(
        default=HookFailPolicy.LOG_AND_CONTINUE, description="Effect of a failure or timeout."
    )
    timeout_s: int = Field(
        default=_DEFAULT_TIMEOUT_S,
        ge=1,
        le=_MAX_TIMEOUT_S,
        description="Seconds before the run counts as TIMEOUT.",
    )
    enabled: bool = Field(default=True, description="Disabled hooks are not run.")

    @model_validator(mode="after")
    def _one_target(self) -> Self:
        if (self.command is None) == (self.kernel_action is None):
            msg = "exactly one of command and kernel_action is required"
            raise ValueError(msg)
        if self.kernel_action is not None and self.kernel_action not in KERNEL_ACTIONS:
            msg = f"unknown kernel action {self.kernel_action!r}; allowed: {list(KERNEL_ACTIONS)}"
            raise ValueError(msg)
        return self


class ProjectHooksFile(WalkModel):
    """`.ai/agents/hooks.yaml`: ``hooks: [ProjectHookSpec, ...]``."""

    hooks: list[ProjectHookSpec] = Field(default_factory=list, description="Declared hooks.")

    @classmethod
    def load(cls, path: Path) -> Self:
        """Parse ``path``; an absent file declares no hooks.

        Raises:
            ConfigError: Invalid YAML, a file that is not ``{hooks: [...]}``, or an invalid
                hook (the message names its ``id``).
        """
        if not path.is_file():
            return cls()
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            msg = f"invalid YAML in {path.name}: {exc}"
            raise ConfigError(msg, detail={"path": str(path)}) from exc
        if raw is None:
            return cls()
        if not isinstance(raw, dict) or not isinstance(raw.get("hooks", []), list):
            msg = f"{path.name} must be a mapping with a 'hooks' list"
            raise ConfigError(msg, detail={"path": str(path)})
        unknown = sorted(set(raw) - {"hooks"})
        if unknown:
            msg = f"unknown keys in {path.name}: {unknown}"
            raise ConfigError(msg, detail={"path": str(path)})
        return cls(hooks=[_spec(item, path) for item in raw.get("hooks", [])])

    def to_hooks(self) -> list[Hook]:
        """The declared hooks as ``kind="project"`` registrations."""
        return [
            Hook(
                name=spec.name,
                id=spec.id,
                kind="project",
                priority=spec.priority,
                command=spec.command,
                kernel_action=spec.kernel_action,
                fail_policy=spec.fail_policy,
                required=False,
                enabled=spec.enabled,
                timeout_s=spec.timeout_s,
            )
            for spec in self.hooks
        ]


def _spec(item: object, path: Path) -> ProjectHookSpec:
    hook_id = item.get("id") if isinstance(item, dict) else None
    try:
        return ProjectHookSpec.model_validate(item)
    except ValidationError as exc:
        reasons = "; ".join(str(error["msg"]) for error in exc.errors())
        msg = f"invalid project hook {hook_id!r} in {path.name}: {reasons}"
        raise ConfigError(msg, detail={"path": str(path), "hook_id": hook_id}) from exc


def hook_env(ctx: HookContext, base_env: Mapping[str, str]) -> dict[str, str]:
    """``base_env`` plus the context as ``WALK_HOOK_*`` variables (absent values are empty).

    WALK_HOOK_NAME, WALK_HOOK_PROJECT_KEY, WALK_HOOK_WORK_ITEM_ID, WALK_HOOK_RUN_ID,
    WALK_HOOK_PHASE_ID, WALK_HOOK_ROLE, WALK_HOOK_AT (ISO 8601) and WALK_HOOK_PAYLOAD (JSON).
    """
    facts = {
        "NAME": ctx.name.value,
        "PROJECT_KEY": ctx.project_key,
        "WORK_ITEM_ID": ctx.work_item_id or "",
        "RUN_ID": ctx.run_id or "",
        "PHASE_ID": ctx.phase_id or "",
        "ROLE": ctx.role.value if ctx.role is not None else "",
        "AT": ctx.at.isoformat(),
        "PAYLOAD": json.dumps(ctx.payload, sort_keys=True, default=str),
    }
    return {**base_env, **{f"{HOOK_ENV_PREFIX}{key}": value for key, value in facts.items()}}
