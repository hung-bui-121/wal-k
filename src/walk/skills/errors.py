"""Skill package errors (E02-S05)."""

from walk.common.errors import ConfigError


class SkillLoadError(ConfigError):
    """A ``SKILL.md`` cannot be loaded: bad front matter, name/folder mismatch, size or scope."""
