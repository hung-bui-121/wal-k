"""Persistence-specific exceptions."""

from walk.common.errors import PermanentError


class MigrationError(PermanentError):
    """A schema migration failed and was rolled back.

    `MigrationRunner.apply_pending` raises `ConfigError` chained from this error, so callers
    handle one configuration failure type while the cause keeps the failing migration.
    """
