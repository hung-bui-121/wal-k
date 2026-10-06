import json
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from walk.persistence import Database
from walk.telemetry import (
    DefaultTelemetryManager,
    JsonLineHandler,
    LedgerRepository,
    TelemetryManager,
    configure_logging,
)


def _lines(repo_root: Path) -> list[dict[str, object]]:
    path = repo_root / ".walk" / "logs" / "kernel.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def telemetry(
    tmp_path: Path, db: Database, fake_clock: FakeClock
) -> Iterator[DefaultTelemetryManager]:
    manager = DefaultTelemetryManager(tmp_path, LedgerRepository(db), fake_clock)
    yield manager
    manager.close()


class Opaque:
    def __repr__(self) -> str:
        return "<opaque>"


def test_log_writes_json_line(
    telemetry: DefaultTelemetryManager, tmp_path: Path, fake_clock: FakeClock
) -> None:
    telemetry.log("INFO", "x", a=1)
    telemetry.log("warning", "y", msg="field cannot override the message")
    first, last = _lines(tmp_path)
    assert first == {"ts": fake_clock.now().isoformat(), "level": "INFO", "msg": "x", "a": 1}
    assert (last["level"], last["msg"]) == ("WARNING", "y")


def test_log_falls_back_to_repr(telemetry: DefaultTelemetryManager, tmp_path: Path) -> None:
    telemetry.log("INFO", "odd", obj=Opaque(), items={1, 2})
    cyclic: list[object] = []
    cyclic.append(cyclic)
    telemetry.log("ERROR", "cycle", data=cyclic)
    odd, cycle = _lines(tmp_path)
    assert odd["obj"] == "<opaque>"
    assert odd["items"] == "{1, 2}"
    assert cycle["data"] == "[[...]]"


def test_log_accepts_unknown_level_names(
    telemetry: DefaultTelemetryManager, tmp_path: Path
) -> None:
    telemetry.log("trace", "fine-grained")
    assert _lines(tmp_path)[0]["level"] == "TRACE"


def test_counters_flush_periodically(
    telemetry: DefaultTelemetryManager, tmp_path: Path, fake_clock: FakeClock
) -> None:
    telemetry.counter("x")
    telemetry.counter("x")
    telemetry.timer("run", 1.5, role="QC")
    fake_clock.advance(59)
    telemetry.counter("x", 0.5)
    assert not (tmp_path / ".walk" / "logs" / "kernel.jsonl").exists()
    fake_clock.advance(1)
    telemetry.counter("y")
    (line,) = _lines(tmp_path)
    assert line["msg"] == "metrics"
    assert line["counters"] == {"x": 2.5}
    assert line["timers"] == {"run{role=QC}": {"count": 1, "total_s": 1.5, "max_s": 1.5}}
    telemetry.close()
    assert _lines(tmp_path)[-1]["counters"] == {"y": 1.0}


def test_close_without_metrics_writes_nothing(
    tmp_path: Path, db: Database, fake_clock: FakeClock
) -> None:
    manager = DefaultTelemetryManager(tmp_path, LedgerRepository(db), fake_clock)
    manager.close()
    assert not (tmp_path / ".walk" / "logs" / "kernel.jsonl").exists()


def test_default_telemetry_manager_satisfies_protocol(telemetry: DefaultTelemetryManager) -> None:
    manager: TelemetryManager = telemetry
    assert manager is telemetry


def test_configure_logging_routes_walk_loggers_to_json_lines(tmp_path: Path) -> None:
    walk_logger = logging.getLogger("walk")
    before = list(walk_logger.handlers)
    try:
        configure_logging(tmp_path, level="DEBUG")
        configure_logging(tmp_path, level="DEBUG")  # replaces, never stacks
        handlers = [h for h in walk_logger.handlers if isinstance(h, JsonLineHandler)]
        assert len(handlers) == 1
        logging.getLogger("walk.persistence").debug("opened", extra={"db": "kernel.db"})
        handlers[0].flush()
        (line,) = _lines(tmp_path)
        assert (line["level"], line["msg"], line["db"]) == ("DEBUG", "opened", "kernel.db")
        assert line["logger"] == "walk.persistence"
    finally:
        for handler in list(walk_logger.handlers):
            if handler not in before:
                walk_logger.removeHandler(handler)
                handler.close()
