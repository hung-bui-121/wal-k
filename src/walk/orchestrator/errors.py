"""Orchestrator errors (E01-S29)."""

from walk.common.errors import ConfigError


class NoScheduledRole(ConfigError):
    """(kind, state) has no row in scheduled_states.yaml."""
