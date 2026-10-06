"""In-memory `KeyringBackend` for tests (E02-S01); the OS keyring is never touched."""


class FakeKeyringBackend:
    """Answers from a dict, or raises ``error`` on every lookup; records each lookup."""

    def __init__(
        self, values: dict[str, str] | None = None, *, error: Exception | None = None
    ) -> None:
        """Hold ``values`` (credential name → secret) under any service name."""
        self.values = dict(values or {})
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def get_password(self, service: str, username: str) -> str | None:
        """The stored value of ``username``, ``None`` when absent; raises ``error`` if set."""
        self.calls.append((service, username))
        if self.error is not None:
            raise self.error
        return self.values.get(username)


__all__ = ["FakeKeyringBackend"]
