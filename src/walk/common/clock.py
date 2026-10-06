"""Injectable UTC clock."""

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Source of the current time. Implementations return timezone-aware UTC datetimes."""

    def now(self) -> datetime:
        """Return the current time as a timezone-aware UTC datetime."""
        ...


class SystemClock:
    """Clock backed by the system wall clock."""

    def now(self) -> datetime:
        """Return the current wall-clock time in UTC."""
        return datetime.now(tz=UTC)
