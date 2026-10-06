import logging

import pytest
from pydantic import SecretStr

from tests.fakes.fake_keyring import FakeKeyringBackend
from walk.common.errors import ConfigError
from walk.integrations import CREDENTIAL_NAMES, CredentialStore, ReadinessState
from walk.integrations.credentials import KEYRING_SERVICE, SystemKeyringBackend


def test_get_prefers_environment_over_keyring() -> None:
    backend = FakeKeyringBackend({"JIRA_API_TOKEN": "from-keyring"})
    store = CredentialStore({"JIRA_API_TOKEN": "abc"}, backend)

    value = store.get("JIRA_API_TOKEN")

    assert isinstance(value, SecretStr)
    assert value.get_secret_value() == "abc"
    assert backend.calls == []


def test_get_falls_back_to_keyring() -> None:
    backend = FakeKeyringBackend({"JIRA_API_TOKEN": "from-keyring"})
    store = CredentialStore({}, backend)

    value = store.get("JIRA_API_TOKEN")

    assert value is not None
    assert value.get_secret_value() == "from-keyring"
    assert backend.calls == [(KEYRING_SERVICE, "JIRA_API_TOKEN")]
    assert KEYRING_SERVICE == "walk"


def test_get_returns_none_when_absent() -> None:
    store = CredentialStore({"JIRA_API_TOKEN": ""}, FakeKeyringBackend({"JIRA_API_TOKEN": ""}))

    assert store.get("JIRA_API_TOKEN") is None
    assert store.present("JIRA_API_TOKEN") is False


def test_get_without_backend_returns_none_when_env_misses() -> None:
    store = CredentialStore({"JIRA_EMAIL": "a@b"}, None)

    assert store.get("JIRA_API_TOKEN") is None
    assert store.present("JIRA_EMAIL") is True


def test_get_treats_backend_error_as_absent(caplog: pytest.LogCaptureFixture) -> None:
    store = CredentialStore({}, FakeKeyringBackend(error=RuntimeError("no keyring backend")))

    with caplog.at_level(logging.WARNING, logger="walk.integrations.credentials"):
        value = store.get("MESHY_API_KEY")

    assert value is None
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].credential == "MESHY_API_KEY"  # type: ignore[attr-defined]  # logging extra field


def test_get_unknown_name_raises_config_error() -> None:
    store = CredentialStore({"FOO": "bar"}, FakeKeyringBackend({"FOO": "bar"}))

    with pytest.raises(ConfigError, match="unknown credential name"):
        store.get("FOO")
    with pytest.raises(ConfigError, match="unknown credential name"):
        store.present("FOO")


def test_presence_reports_states_without_values() -> None:
    backend = FakeKeyringBackend({"WALK_WEBHOOK_SECRET": "hook-secret"})
    store = CredentialStore({"JIRA_EMAIL": "a@b.example"}, backend)

    presence = store.presence()

    assert list(presence) == list(CREDENTIAL_NAMES)
    assert len(presence) == len(CREDENTIAL_NAMES)
    assert presence["JIRA_EMAIL"] is ReadinessState.READY
    assert presence["WALK_WEBHOOK_SECRET"] is ReadinessState.READY
    missing = set(CREDENTIAL_NAMES) - {"JIRA_EMAIL", "WALK_WEBHOOK_SECRET"}
    assert all(presence[name] is ReadinessState.MISSING for name in missing)
    rendered = repr(presence) + repr(store.get("WALK_WEBHOOK_SECRET"))
    assert "hook-secret" not in rendered
    assert "a@b.example" not in rendered


def test_system_backend_delegates_to_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_get_password(service: str, username: str) -> str | None:
        calls.append((service, username))
        return "from-os"

    monkeypatch.setattr("keyring.get_password", fake_get_password)

    value = CredentialStore({}, SystemKeyringBackend()).get("ANTHROPIC_API_KEY")

    assert value is not None
    assert value.get_secret_value() == "from-os"
    assert calls == [("walk", "ANTHROPIC_API_KEY")]
