import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

import walk
from tests.fakes.fake_clock import FakeClock
from walk.cli.app import app
from walk.improvement import BehaviorVersionCatalog, KernelVersionPins

runner = CliRunner()
PACKAGE = Path(walk.__file__).resolve().parent


def _pins(repo: Path) -> KernelVersionPins:
    clock = FakeClock(datetime(2026, 10, 7, tzinfo=UTC))
    pins = KernelVersionPins.from_catalog(BehaviorVersionCatalog(PACKAGE, clock).scan())
    pins.write(repo / ".ai")
    return pins


def test_version_lists_pins(tmp_path: Path) -> None:
    pins = _pins(tmp_path)

    result = runner.invoke(app, ["version", "--repo", str(tmp_path)])

    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert lines[0] == f"walk {walk.__version__}"
    assert lines[1:] == [f"{key} {value}" for key, value in sorted(pins.pins.items())]
    assert "WORKFLOW/story_workflow 1.0" in lines
    assert "CONSTITUTION/LEAD_DEV 1.0" in lines
    assert "SKILL/walk-output-contract 1.0" in lines


def test_version_without_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["version"])
    flag = runner.invoke(app, ["--version"])

    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines() == [f"walk {walk.__version__}", "(no project)"]
    assert flag.exit_code == 0, flag.output
    assert flag.stdout == result.stdout


def test_version_json_and_empty_pin_file(tmp_path: Path) -> None:
    pins = _pins(tmp_path)

    listed = runner.invoke(app, ["--json", "version", "--repo", str(tmp_path)])
    (tmp_path / ".ai" / "project" / "kernel-versions.yaml").write_text("{}\n", encoding="utf-8")
    empty = runner.invoke(app, ["version", "--repo", str(tmp_path)])
    absent = runner.invoke(app, ["version", "--json", "--repo", str(tmp_path / "none")])

    assert json.loads(listed.stdout) == {"kernel": walk.__version__, "pins": pins.pins}
    assert empty.stdout.splitlines() == [f"walk {walk.__version__}", "(no pins)"]
    assert json.loads(absent.stdout) == {"kernel": walk.__version__, "pins": None}


def test_version_reports_an_invalid_pin_file(tmp_path: Path) -> None:
    path = tmp_path / ".ai" / "project" / "kernel-versions.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("pins: [1]\n", encoding="utf-8")

    result = runner.invoke(app, ["version", "--repo", str(tmp_path)])

    assert result.exit_code == 1
    assert "invalid kernel version pins" in result.stderr
