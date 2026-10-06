from datetime import UTC, datetime, timedelta

from tests.fakes.fake_clock import FakeClock
from walk.common.clock import SystemClock


def test_system_clock_returns_utc_aware() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_fake_clock_advances_deterministically() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    clock = FakeClock(start)
    clock.advance(5)
    assert clock.now() - start == timedelta(seconds=5)
