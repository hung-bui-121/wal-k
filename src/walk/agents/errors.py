"""Agent errors."""

from walk.common.errors import ConfigError


class ConstitutionError(ConfigError):
    """A constitution or runtime policy is invalid, unknown or widens a narrow-only field."""
