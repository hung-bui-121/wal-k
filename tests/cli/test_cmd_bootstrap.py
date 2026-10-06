import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_keyring import FakeKeyringBackend
from tests.fakes.fake_subprocess import FakeSubprocessRunner
from tests.integrations.test_preflight import script_environment
from tests.orchestrator.test_bootstrap import ProbeRunner
from walk.cli import composition
from walk.cli.app import app
from walk.orchestrator import BootstrapOptions, Bootstrapper

runner = CliRunner()
AT = datetime(2026, 10, 7, 9, 0, tzinfo=UTC)
JIRA = ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")
BASE = ["bootstrap", "--key", "DEMO", "--name", "Demo"]


def _no_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in JIRA:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("walk.cli.cmd_bootstrap.SystemKeyringBackend", FakeKeyringBackend)


def _scripted(monkeypatch: pytest.MonkeyPatch, *, git: str | None = "git version 2.45.0") -> None:
    """`open_bootstrapper` with scripted preflight probes, a fake keyring and a fixed clock."""

    def open_bootstrapper(repo: Path, options: BootstrapOptions) -> Bootstrapper:
        probes = ProbeRunner(script_environment(FakeSubprocessRunner(), git=git))
        return composition.open_bootstrapper(
            repo, options, runner=probes, keyring_backend=FakeKeyringBackend(), clock=FakeClock(AT)
        )

    monkeypatch.setattr("walk.cli.cmd_bootstrap.open_bootstrapper", open_bootstrapper)


def test_bootstrap_jira_requires_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_keyring(monkeypatch)

    result = runner.invoke(app, [*BASE, "--provider", "jira", "--yes", "--repo", str(tmp_path)])

    assert result.exit_code == 4, result.output
    assert "JIRA_BASE_URL" in result.stderr
    assert "JIRA_API_TOKEN" in result.stderr
    assert not (tmp_path / ".ai").exists()


def test_bootstrap_jira_with_credentials_proceeds(
    tmp_game_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in JIRA:
        monkeypatch.setenv(name, "set")
    _scripted(monkeypatch)

    result = runner.invoke(
        app, [*BASE, "--provider", "jira", "--yes", "--repo", str(tmp_game_repo)]
    )

    assert result.exit_code == 0, result.output
    assert (tmp_game_repo / ".ai" / "project" / "work-provider.yaml").is_file()


def test_bootstrap_requires_yes_when_non_interactive(tmp_path: Path) -> None:
    result = runner.invoke(app, [*BASE, "--repo", str(tmp_path)])

    assert result.exit_code == 1, result.output
    assert "bootstrap requires --yes in non-interactive mode" in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_bootstrap_rejects_invalid_project_key(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["bootstrap", "--key", "demo", "--name", "Demo", "--yes", "--repo", str(tmp_path)]
    )

    assert result.exit_code == 1, result.output
    assert "invalid project key 'demo'" in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_bootstrap_prints_created_paths_then_nothing_to_do(
    tmp_game_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scripted(monkeypatch)

    first = runner.invoke(app, ["--repo", str(tmp_game_repo), *BASE, "--yes"])
    second = runner.invoke(app, ["--repo", str(tmp_game_repo), *BASE, "--yes"])

    assert first.exit_code == 0, first.output
    assert first.stdout.splitlines()[0] == "created:"
    assert "  .ai/project/project.md" in first.stdout.splitlines()
    assert second.exit_code == 0, second.output
    assert second.stdout.strip() == "nothing to do"


def test_bootstrap_json_output_is_the_result(
    tmp_game_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scripted(monkeypatch)

    result = runner.invoke(app, ["--json", "--repo", str(tmp_game_repo), *BASE, "--yes"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["kit"]["kit_version"]
    assert ".ai/project/project.md" in payload["created_paths"]


def test_bootstrap_exit_four_when_preflight_fails(
    tmp_game_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scripted(monkeypatch, git=None)

    result = runner.invoke(app, [*BASE, "--yes", "--repo", str(tmp_game_repo)])

    assert result.exit_code == 4, result.output
    assert "git" in result.stderr
    assert not (tmp_game_repo / ".ai" / "agents").exists()


def test_bootstrap_other_kernel_error_exits_one(
    tmp_game_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scripted(monkeypatch)

    result = runner.invoke(
        app, [*BASE, "--yes", "--gdd", "GDD/absent.md", "--repo", str(tmp_game_repo)]
    )

    assert result.exit_code == 1, result.output
    assert "GDD file not found" in result.stderr


@pytest.mark.parametrize(("answer", "code"), [("n\n", 1), ("y\n", 0)])
def test_bootstrap_prompts_on_a_terminal(
    tmp_game_repo: Path, monkeypatch: pytest.MonkeyPatch, answer: str, code: int
) -> None:
    _scripted(monkeypatch)
    monkeypatch.setattr("walk.cli.cmd_bootstrap._interactive", lambda: True)

    result = runner.invoke(app, [*BASE, "--repo", str(tmp_game_repo)], input=answer)

    assert result.exit_code == code, result.output
    assert f"Create Production Kit in {tmp_game_repo}? [y/N]" in result.stdout
    assert (tmp_game_repo / ".ai" / "agents").exists() is (code == 0)


def test_bootstrap_refused_secret_exits_one(
    tmp_game_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scripted(monkeypatch)
    secret_name = "AKIA" + "ABCDEFGHIJKLMNOP"  # an AWS access key shape, refused by the scan

    result = runner.invoke(
        app,
        [
            "bootstrap",
            "--key",
            "DEMO",
            "--name",
            secret_name,
            "--yes",
            "--repo",
            str(tmp_game_repo),
        ],
    )

    assert result.exit_code == 1, result.output
    assert "secret" in result.stderr.lower()
