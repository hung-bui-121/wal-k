"""Deterministic clock for tests."""

from datetime import datetime, timedelta


class FakeClock:
    """Clock that only moves when told to."""

    def __init__(self, start: datetime) -> None:
        """Start at ``start`` (must be timezone-aware)."""
        self._now = start

    def now(self) -> datetime:
        """Return the current fake time."""
        return self._now

    def advance(self, seconds: float) -> None:
        """Move the clock forward by ``seconds``."""
        self._now = self._now + timedelta(seconds=seconds)
