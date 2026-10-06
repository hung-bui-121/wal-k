from tests.fakes.fake_clock import FakeClock
from walk.persistence import Database, KernelInstanceRegistry


async def test_register_and_heartbeat(db: Database, fake_clock: FakeClock) -> None:
    registry = KernelInstanceRegistry(db, fake_clock)

    await registry.register("kernel-1", hostname="studio-pc", pid=4242)
    fake_clock.advance(30)
    await registry.heartbeat("kernel-1")
    await registry.register("kernel-1", hostname="studio-pc", pid=4343)
    fake_clock.advance(30)
    await registry.heartbeat("kernel-1")

    rows = db.connect().execute(
        "SELECT id, hostname, started_at, heartbeat_at, pid FROM kernel_instances"
    )
    assert [tuple(row) for row in rows.fetchall()] == [
        (
            "kernel-1",
            "studio-pc",
            "2026-01-01T00:00:30+00:00",
            "2026-01-01T00:01:00+00:00",
            4343,
        )
    ]
