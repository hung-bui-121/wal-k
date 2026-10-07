"""Kernel permission defaults and the project narrowing file (ADR-0006 D-6; §31, §92; E02-S10).

`defaults.yaml` is the single source of the kernel rules; `.ai/agents/permissions.yaml` may only
narrow it: add DENY / REQUIRE_APPROVAL rules, restate a default ALLOW with fewer patterns, and
add protected actions. A §92 protected action can never be removed or downgraded.

Both files write a rule as ``role``/``roles`` by ``tool``/``tools`` plus the `PermissionRule`
fields; role ``"*"`` stands for every agent role (not the USER/KERNEL actors).
"""

from pathlib import Path
from typing import Final

import yaml
from pydantic import Field, ValidationError

from walk.common.errors import ConfigError
from walk.common.models import JsonDict, WalkModel
from walk.common.roles import AgentRole
from walk.permissions.matching import match_tool
from walk.permissions.models import PermissionEffect, PermissionRule, ProtectedAction

DEFAULT_PROTECTED_ACTIONS: tuple[str, ...] = (
    "git.merge_protected",
    "git.delete_branch_protected",
    "repo.delete_data",
    "store.publish",
    "credentials.change",
    "monetization.change",
    "jira.delete",
    "permissions.alter",
)

_DEFAULTS_FILE: Final = Path(__file__).resolve().parent / "defaults.yaml"
_ALL_ROLES: Final = "*"
_ACTORS: Final = frozenset({AgentRole.USER, AgentRole.KERNEL})
_AGENT_ROLES: Final = tuple(role for role in AgentRole if role not in _ACTORS)
_FILE_KEYS: Final = frozenset({"rules", "protected_actions"})
_ANY_PATH: Final = "**"


class PermissionsFile(WalkModel):
    """A rule set: kernel defaults, a project narrowing file, or their merge."""

    rules: list[PermissionRule] = Field(default_factory=list, description="Permission rules.")
    protected_actions: list[ProtectedAction] = Field(
        default_factory=list, description="§92 protected actions; a project may add, never remove."
    )


def load_defaults() -> PermissionsFile:
    """The kernel rule set shipped as the package resource ``defaults.yaml``.

    Raises:
        ConfigError: The shipped file is malformed (a packaging error, surfaced at startup).
    """
    return _load(_DEFAULTS_FILE)


def load_project_rules(path: Path) -> PermissionsFile:
    """`.ai/agents/permissions.yaml`; an absent or empty file narrows nothing.

    Raises:
        ConfigError: Invalid YAML or an invalid entry.
    """
    if not path.is_file():
        return PermissionsFile()
    return _load(path)


def merge_narrowing(defaults: PermissionsFile, project: PermissionsFile) -> PermissionsFile:
    """The kernel defaults narrowed by ``project``.

    Project rule with effect DENY/REQUIRE_APPROVAL: added. Project rule with effect ALLOW:
    accepted only if a (role, tool) ALLOW exists in defaults; it then replaces those default
    rows and may only drop command/path patterns (narrowing) — otherwise ConfigError. A project
    ALLOW on a protected action → ConfigError("protected action cannot be downgraded").
    Project protected_actions are appended (with a REQUIRE_APPROVAL rule for every agent role);
    redefining a default one with another approver, or a merged list missing a default
    protected action → ConfigError. The result is de-duplicated on
    (role, tool, effect, command_patterns, path_patterns).
    """
    actions = _merged_actions(defaults.protected_actions, project.protected_actions)
    rules = list(defaults.rules)
    added = [a for a in actions if a.name not in {d.name for d in defaults.protected_actions}]
    for action in added:
        rules.extend(_approval_rules(action))
    for rule in project.rules:
        if rule.effect is not PermissionEffect.ALLOW:
            rules.append(rule)
            continue
        if any(match_tool(rule.tool, action.name) for action in actions):
            msg = "protected action cannot be downgraded"
            raise ConfigError(msg, detail={"role": rule.role.value, "tool": rule.tool})
        rules = _restate(rules, defaults.rules, rule)
    return PermissionsFile(rules=_unique(rules), protected_actions=actions)


def _load(path: Path) -> PermissionsFile:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        msg = f"invalid YAML in {path.name}: {exc}"
        raise ConfigError(msg, detail={"path": str(path)}) from exc
    return _parse(raw, path.name)


def _parse(raw: object, source: str) -> PermissionsFile:
    """A rule set from a parsed YAML document (``None`` = empty file)."""
    if raw is None:
        return PermissionsFile()
    if not isinstance(raw, dict) or not set(raw) <= _FILE_KEYS:
        msg = f"{source} must be a mapping with only 'rules' and 'protected_actions'"
        raise ConfigError(msg, detail={"source": source})
    rules = [rule for entry in _list(raw, "rules", source) for rule in _expand(entry, source)]
    actions = [_action(entry, source) for entry in _list(raw, "protected_actions", source)]
    return PermissionsFile(rules=rules, protected_actions=actions)


def _list(raw: dict[str, object], key: str, source: str) -> list[object]:
    value = raw.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        msg = f"{source}: '{key}' must be a list"
        raise ConfigError(msg, detail={"source": source, "key": key})
    return value


def _expand(entry: object, source: str) -> list[PermissionRule]:
    """One file entry → one rule per (role, tool)."""
    if not isinstance(entry, dict):
        msg = f"{source}: a rule must be a mapping, not {entry!r}"
        raise ConfigError(msg, detail={"source": source})
    fields: JsonDict = dict(entry)
    roles = _names(fields, "role", "roles", source)
    tools = _names(fields, "tool", "tools", source)
    if _ALL_ROLES in roles:
        roles = [role.value for role in _AGENT_ROLES]
    rules: list[PermissionRule] = []
    for role in roles:
        for tool in tools:
            try:
                rules.append(PermissionRule.model_validate({**fields, "role": role, "tool": tool}))
            except ValidationError as exc:
                reasons = "; ".join(str(error["msg"]) for error in exc.errors())
                msg = f"{source}: invalid rule {role} {tool}: {reasons}"
                raise ConfigError(msg, detail={"source": source, "tool": tool}) from exc
    return rules


def _names(fields: JsonDict, one: str, many: str, source: str) -> list[str]:
    """``fields[one]`` or ``fields[many]`` (exactly one of them), removed from ``fields``."""
    single, several = fields.pop(one, None), fields.pop(many, None)
    if (single is None) == (several is None):
        msg = f"{source}: a rule needs exactly one of '{one}' and '{many}'"
        raise ConfigError(msg, detail={"source": source})
    names = [single] if single is not None else several
    if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
        msg = f"{source}: '{many}' must be a non-empty list of names"
        raise ConfigError(msg, detail={"source": source})
    return names


def _action(entry: object, source: str) -> ProtectedAction:
    try:
        return ProtectedAction.model_validate(entry)
    except ValidationError as exc:
        msg = f"{source}: invalid protected action {entry!r}"
        raise ConfigError(msg, detail={"source": source}) from exc


def _merged_actions(
    defaults: list[ProtectedAction], project: list[ProtectedAction]
) -> list[ProtectedAction]:
    merged = list(defaults)
    by_name = {action.name: action for action in defaults}
    for action in project:
        known = by_name.get(action.name)
        if known is None:
            merged.append(action)
            by_name[action.name] = action
        elif known.approver is not action.approver:
            msg = f"protected action {action.name} cannot be redefined"
            raise ConfigError(msg, detail={"action": action.name})
    missing = [name for name in DEFAULT_PROTECTED_ACTIONS if name not in by_name]
    if missing:
        msg = f"default protected actions cannot be removed: {missing}"
        raise ConfigError(msg, detail={"missing": missing})
    return merged


def _approval_rules(action: ProtectedAction) -> list[PermissionRule]:
    return [
        PermissionRule(
            role=role,
            tool=action.name,
            effect=PermissionEffect.REQUIRE_APPROVAL,
            approver=action.approver,
            reason=f"protected action {action.name}",
        )
        for role in _AGENT_ROLES
    ]


def _restate(
    rules: list[PermissionRule], defaults: list[PermissionRule], rule: PermissionRule
) -> list[PermissionRule]:
    """Replace the default ALLOW rows of ``rule``'s (role, tool) by ``rule`` if it narrows them."""
    same = [
        d
        for d in defaults
        if d.effect is PermissionEffect.ALLOW and d.role is rule.role and d.tool == rule.tool
    ]
    if not same:
        msg = f"project rule {rule.role.value} {rule.tool} ALLOW widens the kernel defaults"
        raise ConfigError(msg, detail={"role": rule.role.value, "tool": rule.tool})
    commands = {p for d in same for p in d.command_patterns}
    paths = {p for d in same for p in d.path_patterns}
    narrower_commands = not commands or (
        bool(rule.command_patterns) and set(rule.command_patterns) <= commands
    )
    narrower_paths = not paths or (
        bool(rule.path_patterns) and (_ANY_PATH in paths or set(rule.path_patterns) <= paths)
    )
    if not (narrower_commands and narrower_paths):
        msg = f"project rule {rule.role.value} {rule.tool} ALLOW adds patterns the defaults lack"
        raise ConfigError(msg, detail={"role": rule.role.value, "tool": rule.tool})
    return [r for r in rules if r not in same] + [rule]


def _unique(rules: list[PermissionRule]) -> list[PermissionRule]:
    seen: set[tuple[object, ...]] = set()
    unique: list[PermissionRule] = []
    for rule in rules:
        key = (
            rule.role,
            rule.tool,
            rule.effect,
            tuple(rule.command_patterns),
            tuple(rule.path_patterns),
        )
        if key not in seen:
            seen.add(key)
            unique.append(rule)
    return unique
