"""Load role constitutions: kernel defaults merged with project overrides (ADR-0013)."""

import re
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from walk.agents.errors import ConstitutionError
from walk.agents.models import Constitution
from walk.common.errors import ConfigError
from walk.common.models import JsonDict
from walk.common.roles import AgentRole
from walk.memory.frontmatter import split_document
from walk.permissions.models import PermissionEffect, PermissionRule

_TYPE: Final = "constitution"
_HEADER_ONLY: Final = ("id", "type", "title")
# ADR-0013 D-3 body order; unknown sections follow in file order (defaults, then override).
_SECTION_ORDER: Final = (
    "Identity",
    "Mission",
    "Responsibilities",
    "Authority",
    "Professional Bias",
    "Core Beliefs",
    "Decision Principles",
    "Risk Tolerance",
    "Preferred Evidence",
    "Conflict Behavior",
    "Escalation Rules",
    "Forbidden Actions",
    "Working Guidance",
)
# ADR-0013 D-5: constitutions are model-independent.
_PROVIDER_NAMES: Final = re.compile(r"\b(claude|codex|gpt|anthropic|openai)", re.IGNORECASE)
_SUBSET_AUTHORITY: Final = ("decision_scope", "may_approve", "may_reject", "may_create_work")


def _file_name(role: AgentRole) -> str:
    return f"{role.value.lower()}.md"


def _strings(value: object, where: str) -> list[tuple[str, str]]:
    """Every string inside ``value`` with the dotted field path it was found at."""
    if isinstance(value, str):
        return [(where, value)]
    if isinstance(value, dict):
        return [hit for key, item in value.items() for hit in _strings(item, f"{where}.{key}")]
    if isinstance(value, list):
        return [hit for item in value for hit in _strings(item, where)]
    return []


def _rule_key(rule: PermissionRule) -> JsonDict:
    return rule.model_dump(mode="json", exclude={"reason"})


class ConstitutionLoader:
    """Reads ``<role>.md`` constitutions (snake_case file names, ARCHITECTURE §8.1)."""

    def __init__(self, defaults_dir: Path, project_roles_dir: Path | None) -> None:
        """Read kernel defaults from ``defaults_dir`` and overrides from ``project_roles_dir``.

        Args:
            defaults_dir: Kernel defaults (``walk/agents/defaults``).
            project_roles_dir: ``.ai/agents/roles``; ``None`` or a missing folder = no overrides.
        """
        self._defaults_dir = defaults_dir
        self._project_roles_dir = project_roles_dir
        self._cache: dict[AgentRole, Constitution] = {}

    def available_roles(self) -> list[AgentRole]:
        """Roles with a default constitution file, in `AgentRole` order."""
        return [role for role in AgentRole if (self._defaults_dir / _file_name(role)).is_file()]

    def load(self, role: AgentRole) -> Constitution:
        """The role's default constitution merged with its project override (cached).

        Override scalars and lists replace defaults, ``authority`` merges per key, body
        sections replace by name or append. ``authority`` lists, ``tool_permissions`` and
        ``forbidden_actions`` may only narrow; ``max_autonomy_level`` may only drop.

        Raises:
            ConstitutionError: Unknown role; a file that does not parse, is not
                ``type: constitution`` for this role, or fails the schema; a widening override
                (the message names the field); a provider or model name anywhere.
        """
        cached = self._cache.get(role)
        if cached is not None:
            return cached
        default_path = self._defaults_dir / _file_name(role)
        if not default_path.is_file():
            msg = f"no default constitution for role {role.value}"
            raise ConstitutionError(msg, detail={"role": role.value})
        header, sections = self._read(default_path, role)
        default = self._build(default_path, role, header, sections)
        constitution = default
        override_path = self._override_path(role)
        if override_path is not None:
            extra_header, extra_sections = self._read(override_path, role)
            merged = dict(header)
            for key, value in extra_header.items():
                if key == "authority" and isinstance(value, dict):
                    merged[key] = {**header.get("authority", {}), **value}
                else:
                    merged[key] = value
            constitution = self._build(override_path, role, merged, {**sections, **extra_sections})
            _check_narrowing(override_path, default, constitution)
        self._cache[role] = constitution
        return constitution

    def _override_path(self, role: AgentRole) -> Path | None:
        if self._project_roles_dir is None:
            return None
        path = self._project_roles_dir / _file_name(role)
        return path if path.is_file() else None

    @staticmethod
    def _read(path: Path, role: AgentRole) -> tuple[JsonDict, dict[str, str]]:
        try:
            header, sections = split_document(path, path.read_text(encoding="utf-8"))
        except (ConfigError, OSError, UnicodeDecodeError) as exc:
            msg = f"cannot read constitution {path.name}: {exc}"
            raise ConstitutionError(msg, detail={"path": str(path), "role": role.value}) from exc
        if header.get("type") != _TYPE:
            msg = f"{path.name}: type must be {_TYPE!r}, not {header.get('type')!r}"
            raise ConstitutionError(msg, detail={"path": str(path)})
        if header.get("id", role.value) != role.value:
            msg = f"{path.name}: id {header.get('id')!r} does not match role {role.value}"
            raise ConstitutionError(msg, detail={"path": str(path)})
        return header, sections

    @staticmethod
    def _build(
        path: Path, role: AgentRole, header: JsonDict, sections: dict[str, str]
    ) -> Constitution:
        names: list[str] = [n for n in _SECTION_ORDER if n in sections]
        names += [n for n in sections if n not in _SECTION_ORDER]
        body = "\n\n".join(f"## {name}\n\n{sections[name]}".rstrip() for name in names)
        fields = {k: v for k, v in header.items() if k not in _HEADER_ONLY}
        hits = [*_strings(fields, "front matter"), *((f"## {n}", sections[n]) for n in names)]
        hits += [(f"## {n}", n) for n in names]
        for where, text in hits:
            found = _PROVIDER_NAMES.search(text)
            if found:
                msg = f"{path.name}: provider or model name {found.group(0)!r} in {where}"
                raise ConstitutionError(msg, detail={"path": str(path), "field": where})
        rules = fields.get("tool_permissions")
        if isinstance(rules, list):
            fields["tool_permissions"] = [
                {"role": role.value, **rule} if isinstance(rule, dict) else rule for rule in rules
            ]
        try:
            constitution = Constitution.model_validate({**fields, "body_markdown": body})
        except ValidationError as exc:
            msg = f"{path.name}: invalid constitution: {exc}"
            raise ConstitutionError(msg, detail={"path": str(path)}) from exc
        if constitution.role is not role or any(
            r.role is not role for r in constitution.tool_permissions
        ):
            msg = f"{path.name}: role fields must be {role.value}"
            raise ConstitutionError(msg, detail={"path": str(path)})
        return constitution


def _widened_field(default: Constitution, merged: Constitution) -> str | None:
    """The first narrow-only field that ``merged`` widens relative to ``default``, else None."""
    for name in _SUBSET_AUTHORITY:
        if not set(getattr(merged.authority, name)) <= set(getattr(default.authority, name)):
            return f"authority.{name}"
    if merged.authority.max_autonomy_level > default.authority.max_autonomy_level:
        return "authority.max_autonomy_level"
    if not set(default.forbidden_actions) <= set(merged.forbidden_actions):
        return "forbidden_actions"
    kept = [_rule_key(rule) for rule in default.tool_permissions]
    allowed_tools = {r.tool for r in default.tool_permissions if r.effect is PermissionEffect.ALLOW}
    for rule in merged.tool_permissions:
        narrows = (
            _rule_key(rule) in kept
            or rule.effect is PermissionEffect.DENY
            or (rule.effect is PermissionEffect.REQUIRE_APPROVAL and rule.tool in allowed_tools)
        )
        if not narrows:
            return "tool_permissions"
    return None


def _check_narrowing(path: Path, default: Constitution, merged: Constitution) -> None:
    """ADR-0013 D-4: overrides may remove permissions or lower autonomy, never add or raise.

    ``forbidden_actions`` narrow by growing: an override may add but not drop entries.
    """
    field = _widened_field(default, merged)
    if field is not None:
        msg = f"{path.name}: override widens {field}"
        raise ConstitutionError(msg, detail={"path": str(path), "field": field})
