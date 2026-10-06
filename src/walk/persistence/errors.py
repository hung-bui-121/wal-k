"""Persistence-specific exceptions."""

from walk.common.errors import ConfigError, PermanentError


class MigrationError(PermanentError):
    """A schema migration failed and was rolled back.

    `MigrationRunner.apply_pending` raises `ConfigError` chained from this error, so callers
    handle one configuration failure type while the cause keeps the failing migration.
    """


class KernelLockHeld(ConfigError):
    """Another live process holds the kernel lock; detail = holder pid, instance, started_at."""
