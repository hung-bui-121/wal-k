import sys

import pytest
from typer.testing import CliRunner

from walk.cli.app import app, main

runner = CliRunner()


def test_version_prints_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "walk 0.1.0" in result.output


def test_no_arguments_prints_help_and_exits_zero() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "--version" in result.output


def test_main_entry_point_runs_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["walk", "--version"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
