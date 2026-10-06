"""Load runtime policies: kernel ``policies.yaml`` deep-merged with the project file (§13)."""

from pathlib import Path
from typing import Final

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from walk.agents.errors import ConstitutionError
from walk.agents.models import RuntimePolicy
from walk.common.models import JsonDict
from walk.common.roles import AgentRole

_ROLES: Final = "roles"


class _PolicyFile(BaseModel):
    """Top level of a ``policies.yaml``: ``roles: {<ROLE>: {...}}``."""

    model_config = ConfigDict(extra="forbid")

    roles: dict[AgentRole, JsonDict]


def _deep_merge(base: JsonDict, override: JsonDict) -> JsonDict:
    """Mappings merge recursively; scalars and lists in ``override`` replace."""
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def _read(path: Path) -> dict[AgentRole, JsonDict]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return _PolicyFile.model_validate(raw).roles
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        msg = f"invalid policy file {path.name}: {exc}"
        raise ConstitutionError(msg, detail={"path": str(path)}) from exc


class PolicyLoader:
    """Reads per-role `RuntimePolicy` defaults and project overrides (cached per instance)."""

    def __init__(self, defaults_path: Path, project_path: Path | None) -> None:
        """Read kernel defaults from ``defaults_path``; overrides from ``project_path``.

        Args:
            defaults_path: Kernel ``walk/agents/defaults/policies.yaml``.
            project_path: ``.ai/agents/policies.yaml``; ``None`` or a missing file = none.
        """
        self._defaults_path = defaults_path
        self._project_path = project_path
        self._files: tuple[dict[AgentRole, JsonDict], dict[AgentRole, JsonDict]] | None = None
        self._cache: dict[AgentRole, RuntimePolicy] = {}

    def load(self, role: AgentRole) -> RuntimePolicy:
        """The role's default policy deep-merged with its project entry.

        The project entry merges over the validated default (model defaults included), so a
        partial mapping such as ``budget_policy.per_task`` keeps the dimensions it omits.

        Raises:
            ConstitutionError: If a file does not parse or match the schema, the role has no
                default policy, or the merged policy is invalid (the message names the file).
        """
        cached = self._cache.get(role)
        if cached is not None:
            return cached
        defaults, project = self._load_files()
        if role not in defaults:
            msg = f"no default runtime policy for role {role.value}"
            raise ConstitutionError(msg, detail={"role": role.value})
        default = self._validate(role, defaults[role], self._defaults_path)
        policy = default
        if role in project and self._project_path is not None:
            merged = _deep_merge(default.model_dump(mode="json"), project[role])
            policy = self._validate(role, merged, self._project_path)
        self._cache[role] = policy
        return policy

    @staticmethod
    def _validate(role: AgentRole, data: JsonDict, source: Path) -> RuntimePolicy:
        try:
            return RuntimePolicy.model_validate({**data, "role": role})
        except ValidationError as exc:
            msg = f"invalid runtime policy for {role.value} in {source.name}: {exc}"
            raise ConstitutionError(msg, detail={"role": role.value, "path": str(source)}) from exc

    def _load_files(self) -> tuple[dict[AgentRole, JsonDict], dict[AgentRole, JsonDict]]:
        if self._files is None:
            defaults = _read(self._defaults_path)
            path = self._project_path
            project = _read(path) if path is not None and path.is_file() else {}
            self._files = (defaults, project)
        return self._files
