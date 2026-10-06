"""Improvement package errors (E02-S04)."""

from walk.common.errors import PermanentError


class VersionPinError(PermanentError):
    """`.ai/project/kernel-versions.yaml` does not match the kernel's behavior versions (§105).

    ``detail["problems"]`` lists every mismatch: ``missing pin: X``, ``unknown pin: X`` and
    ``pin X wants A, kernel provides B``.
    """
