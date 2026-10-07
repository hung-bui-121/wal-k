"""`CredentialStore`: the only reader of secrets (ADR-0009 D-8; ARCHITECTURE §6).

Resolution order: environment variable → OS keyring (service ``walk``, username = credential
name) → absent. This is the only kernel module that imports `keyring` (ARCHITECTURE §2.3).
"""

import logging
from collections.abc import Mapping
from typing import Final, Protocol

import keyring
from pydantic import SecretStr

from walk.common.errors import ConfigError
from walk.integrations.models import ReadinessState

_LOG = logging.getLogger(__name__)

CREDENTIAL_NAMES: tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "JIRA_BASE_URL",
    "JIRA_EMAIL",
    "JIRA_API_TOKEN",
    "WALK_WEBHOOK_SECRET",
    "MESHY_API_KEY",
    "OPENART_OAUTH_CLIENT",
    "OPENART_OAUTH_REFRESH_TOKEN",
    "UNITY_PASSWORD",
    "UNITY_SERIAL",
    "UNITY_LICENSE",
    "UNITY_EMAIL",
)
"""Every credential the kernel knows (ADR-0009 D-8)."""

UNITY_SECRET_NAMES: tuple[str, ...] = (
    "UNITY_PASSWORD",
    "UNITY_SERIAL",
    "UNITY_LICENSE",
    "UNITY_EMAIL",
)
"""Unity licence credentials (CI activation); never in an agent's environment (E02-S14)."""

KEYRING_SERVICE: Final[str] = "walk"
"""Keyring service name; the username is the credential name."""


class KeyringBackend(Protocol):
    """Read access to an OS keyring."""

    def get_password(self, service: str, username: str) -> str | None:
        """The stored secret, or ``None`` when nothing is stored."""
        ...


class SystemKeyringBackend:
    """Adapter over the `keyring` package (the only module importing `keyring`)."""

    def get_password(self, service: str, username: str) -> str | None:
        """`keyring.get_password`; may raise when no keyring backend is available."""
        return keyring.get_password(service, username)


class CredentialStore:
    """Resolves the `CREDENTIAL_NAMES` secrets; never logs or returns plain values."""

    def __init__(self, env: Mapping[str, str], backend: KeyringBackend | None) -> None:
        """Read from ``env`` first, then from ``backend`` (``None``: environment only).

        Args:
            env: Process environment (``os.environ`` in the kernel); read at every lookup.
            backend: OS keyring access, or ``None`` to skip the keyring.
        """
        self._env = env
        self._backend = backend

    def get(self, name: str) -> SecretStr | None:
        """``env[name]`` if set and non-empty, else the keyring value, else ``None``.

        An empty value in either source counts as absent. A keyring failure is logged at
        WARNING and treated as absent.

        Raises:
            ConfigError: ``name`` is not in `CREDENTIAL_NAMES`.
        """
        if name not in CREDENTIAL_NAMES:
            msg = f"unknown credential name: {name}"
            raise ConfigError(msg, detail={"credential": name})
        value = self._env.get(name)
        if value:
            return SecretStr(value)
        if self._backend is None:
            return None
        try:
            stored = self._backend.get_password(KEYRING_SERVICE, name)
        except Exception as exc:  # noqa: BLE001 - any keyring failure means "absent" (Behavior 3)
            _LOG.warning(
                "keyring lookup failed; credential treated as absent",
                extra={"credential": name, "error_type": type(exc).__name__},
            )
            return None
        return SecretStr(stored) if stored else None

    def present(self, name: str) -> bool:
        """Whether `get` finds a value.

        Raises:
            ConfigError: ``name`` is not in `CREDENTIAL_NAMES`.
        """
        return self.get(name) is not None

    def presence(self) -> dict[str, ReadinessState]:
        """READY / MISSING for every `CREDENTIAL_NAMES` entry; never values."""
        return {
            name: ReadinessState.READY if self.present(name) else ReadinessState.MISSING
            for name in CREDENTIAL_NAMES
        }
