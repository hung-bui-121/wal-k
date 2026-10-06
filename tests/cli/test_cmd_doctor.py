from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.fakes.fake_subprocess import FakeSubprocessRunner
from tests.integrations.test_preflight import build_manager, script_environment, write_work_provider
from walk.cli.app import app
from walk.common.errors import ConfigError, ProviderUnavailable
from walk.integrations import DefaultIntegrationManager, EnvironmentManifest

runner = CliRunner()


def _use(monkeypatch: pytest.MonkeyPatch, manager: DefaultIntegrationManager) -> list[Path]:
    opened: list[Path] = []

    def open_integrations(repo: Path) -> DefaultIntegrationManager:
        opened.append(repo)
        return manager

    monkeypatch.setattr("walk.cli.cmd_doctor.open_integrations", open_integrations)
    return opened


def test_doctor_exit_zero_when_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_work_provider(tmp_path, "local")
    opened = _use(monkeypatch, build_manager(tmp_path, script_environment(FakeSubprocessRunner())))

    result = runner.invoke(app, ["doctor", "--repo", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert opened == [tmp_path]
    lines = result.stdout.splitlines()
    assert lines[0].split() == ["component", "state", "version", "detail"]
    git_row = next(line for line in lines if line.startswith("tools.git "))
    assert git_row.split()[:3] == ["tools.git", "ready", "2.45.0"]
    assert any(line.startswith("work_provider ") for line in lines)
    assert (tmp_path / ".ai" / "project" / "environment.yaml").is_file()


def test_doctor_exit_four_when_required_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_work_provider(tmp_path, "local")
    manager = build_manager(tmp_path, script_environment(FakeSubprocessRunner(), git=None))
    _use(monkeypatch, manager)

    result = runner.invoke(app, ["--repo", str(tmp_path), "doctor"])

    assert result.exit_code == 4, result.output
    assert "tools.git" in result.stdout
    assert "git" in result.stderr


def test_doctor_json_output_is_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_work_provider(tmp_path, "local")
    _use(monkeypatch, build_manager(tmp_path, script_environment(FakeSubprocessRunner())))

    result = runner.invoke(app, ["doctor", "--json", "--repo", str(tmp_path)])

    assert result.exit_code == 0, result.output
    manifest = EnvironmentManifest.model_validate_json(result.stdout)
    assert manifest.tools["git"].version == "2.45.0"


def test_doctor_reports_drift_lines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_work_provider(tmp_path, "local")
    old = script_environment(FakeSubprocessRunner(), git="git version 2.44.0")
    _use(monkeypatch, build_manager(tmp_path, old, machine_id="A"))
    runner.invoke(app, ["doctor", "--repo", str(tmp_path)])
    _use(monkeypatch, build_manager(tmp_path, script_environment(FakeSubprocessRunner())))

    result = runner.invoke(app, ["doctor", "--repo", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "drift from A:" in result.stdout
    assert "tools.git: ready 2.44.0 -> ready 2.45.0" in result.stdout


def test_doctor_exit_one_on_other_kernel_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(repo: Path) -> DefaultIntegrationManager:
        msg = f"bad tools.yaml in {repo}"
        raise ConfigError(msg)

    monkeypatch.setattr("walk.cli.cmd_doctor.open_integrations", broken)

    result = runner.invoke(app, ["doctor", "--repo", str(tmp_path)])

    assert result.exit_code == 1
    assert "bad tools.yaml" in result.stderr


def test_doctor_exit_one_on_non_config_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Failing:
        async def preflight(self, required: list[str]) -> EnvironmentManifest:
            msg = f"probe crashed for {required}"
            raise ProviderUnavailable(msg)

    monkeypatch.setattr("walk.cli.cmd_doctor.open_integrations", lambda _repo: _Failing())

    result = runner.invoke(app, ["doctor", "--repo", str(tmp_path)])

    assert result.exit_code == 1
    assert "probe crashed" in result.stderr
