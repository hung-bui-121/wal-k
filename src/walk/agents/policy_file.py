"""The project's `.ai/agents/policies.yaml` as a document the user edits (§93; E02-S13).

`walk policy set-model` rewrites one role's ``model_policy`` and leaves every other role's text
byte-identical (comments included); the change applies to the role's next scheduled run
(ADR-0011 D-6). The file holds partial per-role overrides that `PolicyLoader` deep-merges over
the kernel defaults, so its entries are mappings, not complete `RuntimePolicy` objects.
"""

import re
from pathlib import Path
from typing import Final, Self

import yaml
from pydantic import Field, ValidationError

from walk.agents.errors import ConstitutionError
from walk.agents.models import RuntimePolicy
from walk.agents.policy_loader import PolicyLoader
from walk.common.ids import ModelId
from walk.common.models import JsonDict, WalkModel
from walk.common.roles import AgentRole

_DEFAULTS: Final = Path(__file__).resolve().parent / "defaults" / "policies.yaml"
_ROLES_LINE: Final = re.compile(r"^roles:\s*(#.*)?$")
_ROLE_INDENT: Final = "  "
_TMP_SUFFIX: Final = ".tmp"


class PoliciesFile(WalkModel):
    """``roles: {<ROLE>: <partial RuntimePolicy mapping>}`` (project overrides)."""

    roles: dict[AgentRole, JsonDict] = Field(
        default_factory=dict, description="Per-role overrides merged over the kernel defaults."
    )

    @classmethod
    def load(cls, path: Path) -> Self:
        """Parse ``path``; an absent or empty file holds no overrides.

        Raises:
            ConstitutionError: Invalid YAML, or not ``{roles: {ROLE: mapping}}``.
        """
        if not path.is_file():
            return cls()
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            return cls() if raw is None else cls.model_validate(raw)
        except (yaml.YAMLError, ValidationError) as exc:
            msg = f"invalid policy file {path.name}: {exc}"
            raise ConstitutionError(msg, detail={"path": str(path)}) from exc

    def write(self, path: Path) -> Path:
        """Write the whole file (block style, roles in file order) atomically; return ``path``."""
        data = {"roles": {role.value: entry for role, entry in self.roles.items()}}
        _atomic_write(path, yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
        return path


def update_model_policy(
    path: Path, role: AgentRole, preferred: list[ModelId], fallback: list[ModelId]
) -> RuntimePolicy:
    """Set ``role``'s ``model_policy.preferred``/``fallback`` in ``path``; return its new policy.

    Only the role's block is rewritten; other roles keep their exact text. The returned policy
    is the kernel default merged with the updated file (what the role's next run uses).

    Raises:
        ConstitutionError: The file is invalid, or the updated policy does not validate (the
            file is then left unchanged).
    """
    current = PoliciesFile.load(path)
    entry = dict(current.roles.get(role, {}))
    model_policy = dict(entry.get("model_policy") or {})
    model_policy |= {"preferred": list(preferred), "fallback": list(fallback)}
    entry["model_policy"] = model_policy
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    updated = _splice(text, role, entry)
    PoliciesFile.model_validate(yaml.safe_load(updated))  # the splice kept a valid file
    staged = path.with_name(path.name + ".check")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        staged.write_text(updated, encoding="utf-8", newline="\n")
        policy = PolicyLoader(_DEFAULTS, staged).load(role)
    finally:
        staged.unlink(missing_ok=True)
    _atomic_write(path, updated)
    return policy


def _splice(text: str, role: AgentRole, entry: JsonDict) -> str:
    """``text`` with the block of ``role`` under ``roles:`` replaced (or appended)."""
    block = yaml.safe_dump({role.value: entry}, sort_keys=False, default_flow_style=False)
    block_lines = [f"{_ROLE_INDENT}{line}" for line in block.splitlines()]
    lines = text.splitlines()
    roles_at = next((i for i, line in enumerate(lines) if _ROLES_LINE.match(line)), None)
    if roles_at is None:  # no block-style `roles:` section: start one
        prefix = [*lines, ""] if lines and lines[-1].strip() else lines
        return "\n".join([*prefix, "roles:", *block_lines]) + "\n"
    end = len(lines)
    for i in range(roles_at + 1, len(lines)):
        if lines[i].strip() and not lines[i].startswith(" "):
            end = i  # the next top-level key ends the roles section
            break
    start = next(
        (
            i
            for i in range(roles_at + 1, end)
            if lines[i].startswith(f"{_ROLE_INDENT}{role.value}:")
        ),
        None,
    )
    if start is None:
        insert_at = end
        while insert_at > roles_at + 1 and not lines[insert_at - 1].strip():
            insert_at -= 1
        merged = [*lines[:insert_at], *block_lines, *lines[insert_at:]]
        return "\n".join(merged) + "\n"
    stop = end
    for i in range(start + 1, end):
        line = lines[i]
        if line.strip() and not line.startswith(_ROLE_INDENT + " "):
            stop = i  # the next role (or a comment at role level) starts here
            break
    while stop > start + 1 and not lines[stop - 1].strip():
        stop -= 1
    return "\n".join([*lines[:start], *block_lines, *lines[stop:]]) + "\n"


def _atomic_write(target: Path, text: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + _TMP_SUFFIX)
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        tmp.replace(target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
