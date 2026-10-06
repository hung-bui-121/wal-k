from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_subprocess import FakeSubprocessRunner
from tests.integrations.test_preflight import build_manager, script_environment, write_work_provider
from walk.common.errors import ConfigError
from walk.integrations import (
    ComponentStatus,
    EnvironmentManifest,
    ManifestStore,
    ReadinessState,
)

AT = datetime(2026, 10, 7, 9, 0, tzinfo=UTC)
READY = ReadinessState.READY
MISSING = ReadinessState.MISSING


def _manifest(**fields: object) -> EnvironmentManifest:
    data: dict[str, object] = {
        "generated_at": AT,
        "machine_id": "machine-a",
        "unity": ComponentStatus(state=MISSING),
        "work_provider": ComponentStatus(state=READY),
    }
    data.update(fields)
    return EnvironmentManifest.model_validate(data)


async def test_preflight_writes_manifest_without_drift(tmp_path: Path) -> None:
    write_work_provider(tmp_path, "local")
    manager = build_manager(tmp_path, script_environment(FakeSubprocessRunner()))

    manifest = await manager.preflight([])

    path = tmp_path / ".ai" / "project" / "environment.yaml"
    assert path.is_file()
    assert manifest.drift_from is None
    assert manifest.drift_items == []
    assert EnvironmentManifest.model_validate(yaml.safe_load(path.read_text("utf-8"))) == manifest
    assert list(path.parent.glob("*.tmp")) == []


async def test_preflight_reports_drift_against_previous(tmp_path: Path) -> None:
    write_work_provider(tmp_path, "local")
    runner_a = script_environment(FakeSubprocessRunner(), git="git version 2.44.0")
    runner_b = script_environment(FakeSubprocessRunner(), git="git version 2.45.0")
    await build_manager(tmp_path, runner_a, machine_id="A").preflight([])

    manifest = await build_manager(tmp_path, runner_b, machine_id="B").preflight([])

    assert manifest.machine_id == "B"
    assert manifest.drift_from == "A"
    assert manifest.drift_items == ["tools.git: ready 2.44.0 -> ready 2.45.0"]
    stored = ManifestStore(tmp_path / ".ai", FakeClock(AT)).read()
    assert stored == manifest


def test_manifest_store_read_absent_and_path(tmp_path: Path) -> None:
    store = ManifestStore(tmp_path / ".ai", FakeClock(AT))

    assert store.read() is None
    assert store.path() == tmp_path / ".ai" / "project" / "environment.yaml"


def test_manifest_store_round_trips(tmp_path: Path) -> None:
    store = ManifestStore(tmp_path / ".ai", FakeClock(AT))
    manifest = _manifest(credentials={"JIRA_EMAIL": READY})

    path = store.write(manifest)

    assert path == store.path()
    assert store.read() == manifest


def test_manifest_store_rejects_invalid_file(tmp_path: Path) -> None:
    store = ManifestStore(tmp_path / ".ai", FakeClock(AT))
    store.path().parent.mkdir(parents=True)
    store.path().write_text("machine_id: [broken\n", encoding="utf-8")

    with pytest.raises(ConfigError, match=r"environment\.yaml"):
        store.read()
    store.path().write_text("machine_id: only\n", encoding="utf-8")
    with pytest.raises(ConfigError, match=r"environment\.yaml"):
        store.read()


def test_manifest_diff_covers_every_section(tmp_path: Path) -> None:
    store = ManifestStore(tmp_path / ".ai", FakeClock(AT))
    previous = _manifest(
        tools={"git": ComponentStatus(state=READY, version="2.44.0")},
        providers={"codex": ComponentStatus(state=READY, version="0.160.1")},
        credentials={"JIRA_EMAIL": READY},
        unity_packages={"com.walk.ci": ComponentStatus(state=READY, version="1.0.0")},
    )
    current = _manifest(
        machine_id="machine-b",
        unity=ComponentStatus(state=READY, version="6000.0.23f1", detail="new"),
        work_provider=ComponentStatus(state=READY, detail="other detail"),
        tools={"git": ComponentStatus(state=READY, version="2.44.0", detail="ignored")},
        credentials={"JIRA_EMAIL": MISSING},
        required_skills={"git-hygiene": READY},
        build_targets={"Android": MISSING},
    )

    items = store.diff(previous, current)

    assert items == [
        "unity: missing -> ready 6000.0.23f1",
        "unity_packages.com.walk.ci: ready 1.0.0 -> absent",
        "providers.codex: ready 0.160.1 -> absent",
        "credentials.JIRA_EMAIL: ready -> missing",
        "required_skills.git-hygiene: absent -> ready",
        "build_targets.Android: absent -> missing",
    ]
