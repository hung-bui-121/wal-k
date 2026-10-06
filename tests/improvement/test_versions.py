import hashlib
import re
from pathlib import Path

import pytest
import yaml

import walk
from tests.cli.conftest import POLICIES, fake_adapters, migrate
from tests.fakes.fake_clock import FakeClock
from walk.cli.composition import KernelOverrides, KernelSettings, build_kernel
from walk.common.enums import ImprovementScope
from walk.common.errors import ConfigError, PermanentError
from walk.improvement import (
    PINS_PATH,
    BehaviorVersion,
    BehaviorVersionCatalog,
    KernelVersionPins,
    RolloutStage,
    VersionPinError,
)
from walk.telemetry import LedgerEventKind

PACKAGE = Path(walk.__file__).resolve().parent
VERSION = re.compile(r"^\d+\.\d+$")


def _scan(clock: FakeClock, root: Path = PACKAGE) -> list[BehaviorVersion]:
    return BehaviorVersionCatalog(root, clock).scan()


def _keys(catalog: list[BehaviorVersion], clock: FakeClock) -> set[str]:
    keys = BehaviorVersionCatalog(PACKAGE, clock)
    return {keys.key(v) for v in catalog}


def _write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


async def _no_sleep(seconds: float) -> None:
    del seconds


def test_catalog_scans_all_builtin_artifacts(fake_clock: FakeClock) -> None:
    catalog = _scan(fake_clock)
    keys = _keys(catalog, fake_clock)

    tables = {p.name.removesuffix(".yaml") for p in (PACKAGE / "workflow" / "tables").iterdir()}
    expected = {f"WORKFLOW/{t}" for t in tables if t.endswith("_workflow")}
    expected |= {"CONSTITUTION/LEAD_DEV", "CONSTITUTION/ORCHESTRATOR", "CONSTITUTION/QC"}
    expected |= {"CONSTITUTION/SENIOR_DEV"}
    expected |= {
        f"SKILL/{p.name}" for p in (PACKAGE / "skills" / "builtin").iterdir() if p.is_dir()
    }
    templates = (PACKAGE / "agents" / "templates").glob("*.md.j2")
    expected |= {f"PROMPT/{p.name.removesuffix('.md.j2')}" for p in templates}
    expected |= {"MODEL_ROUTING/models", "TOOL_USAGE/tools", "EFFORT_POLICY/LEAD_DEV"}
    assert expected <= keys
    assert "WORKFLOW/story_workflow" in keys
    assert len(keys) == len(catalog)
    assert not any(v.kind is ImprovementScope.CONTEXT_FORMAT for v in catalog)
    for version in catalog:
        source = PACKAGE / version.source_path
        assert VERSION.match(version.version), version
        assert version.stage is RolloutStage.DEFAULT
        assert version.content_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
        assert not Path(version.source_path).is_absolute()
        assert version.introduced_at == fake_clock.now()


def test_catalog_rejects_artifact_without_version(tmp_path: Path, fake_clock: FakeClock) -> None:
    path = _write(tmp_path, "workflow/tables/demo_workflow.yaml", "transitions: []\n")

    with pytest.raises(ConfigError, match="missing version") as info:
        _scan(fake_clock, tmp_path)

    assert str(path) in info.value.message


@pytest.mark.parametrize(
    ("relative", "text", "problem"),
    [
        ("workflow/tables/a_workflow.yaml", 'version: "1.0.0"\n', "MAJOR.MINOR"),
        ("workflow/tables/a_workflow.yaml", "version: 1.0\n", "MAJOR.MINOR"),
        ("workflow/tables/a_workflow.yaml", "- not a mapping\n", "missing version"),
        ("agents/templates/PLAN.md.j2", "# Task\n", "missing version"),
        ("agents/defaults/qc.md", "no front matter\n", "missing version"),
        ("agents/defaults/policies.yaml", "roles:\n  QC: {model_policy: {}}\n", "missing version"),
        ("context/ranking.yaml", "weights: {}\n", "missing version"),
        ("agents/defaults/policies.yaml", "defaults: {}\n", "missing version"),
        ("skills/builtin/x/SKILL.md", "---\nname: [x\n---\nbody\n", "invalid YAML"),
        ("workflow/tables/a_workflow.yaml", "version: [\n", "invalid YAML"),
    ],
)
def test_catalog_rejects_invalid_artifacts(
    tmp_path: Path, fake_clock: FakeClock, relative: str, text: str, problem: str
) -> None:
    _write(tmp_path, relative, text)

    with pytest.raises(ConfigError, match=re.escape(problem)):
        _scan(fake_clock, tmp_path)


def test_catalog_reads_optional_context_format(tmp_path: Path, fake_clock: FakeClock) -> None:
    _write(tmp_path, "context/ranking.yaml", 'version: "2.3"\n')

    [entry] = _scan(fake_clock, tmp_path)

    assert entry.kind is ImprovementScope.CONTEXT_FORMAT
    assert (entry.name, entry.version, entry.source_path) == (
        "ranking",
        "2.3",
        "context/ranking.yaml",
    )


def test_pins_roundtrip_sorted(tmp_path: Path, fake_clock: FakeClock) -> None:
    catalog = _scan(fake_clock)
    pins = KernelVersionPins.from_catalog(catalog)

    path = pins.write(tmp_path)
    loaded = KernelVersionPins.load(tmp_path)

    assert path == tmp_path / PINS_PATH
    assert loaded == pins
    assert set(pins.pins) == _keys(catalog, fake_clock)
    written = list(yaml.safe_load(path.read_text(encoding="utf-8"))["pins"])
    assert written == sorted(written)
    assert KernelVersionPins.load(tmp_path / "absent") == KernelVersionPins(pins={})


def test_pins_load_accepts_the_bootstrap_placeholder_and_rejects_garbage(tmp_path: Path) -> None:
    _write(tmp_path, PINS_PATH, "{}\n")
    assert KernelVersionPins.load(tmp_path).pins == {}

    _write(tmp_path, PINS_PATH, "pins: [1, 2]\n")
    with pytest.raises(ConfigError, match="invalid kernel version pins"):
        KernelVersionPins.load(tmp_path)


def test_validate_reports_unknown_pin(fake_clock: FakeClock) -> None:
    catalog = _scan(fake_clock)
    pins = KernelVersionPins.from_catalog(catalog)
    pins.pins["SKILL/retired-skill"] = "1.0"

    with pytest.raises(VersionPinError, match="unknown pin: SKILL/retired-skill") as info:
        pins.validate(catalog)

    assert isinstance(info.value, PermanentError)
    assert "run 'walk version' and update .ai/project/kernel-versions.yaml" in info.value.message


def test_validate_reports_missing_pin(fake_clock: FakeClock) -> None:
    catalog = _scan(fake_clock)
    pins = KernelVersionPins.from_catalog(catalog)
    del pins.pins["WORKFLOW/story_workflow"]

    with pytest.raises(VersionPinError, match="missing pin: WORKFLOW/story_workflow"):
        pins.validate(catalog)


def test_validate_reports_version_mismatch(fake_clock: FakeClock) -> None:
    catalog = _scan(fake_clock)
    pins = KernelVersionPins.from_catalog(catalog)
    pins.pins["WORKFLOW/story_workflow"] = "1.1"
    del pins.pins["SKILL/git-hygiene"]
    pins.pins["PROMPT/GONE"] = "1.0"

    with pytest.raises(VersionPinError) as info:
        pins.validate(catalog)

    assert "pin WORKFLOW/story_workflow wants 1.1, kernel provides 1.0" in info.value.message
    assert info.value.detail["problems"] == [
        "missing pin: SKILL/git-hygiene",
        "unknown pin: PROMPT/GONE",
        "pin WORKFLOW/story_workflow wants 1.1, kernel provides 1.0",
    ]
    KernelVersionPins.from_catalog(catalog).validate(catalog)  # a matching set passes


@pytest.fixture
def kernel_repo(tmp_game_repo: Path) -> Path:
    """A migrated game repository with the DEMO project and fake-model policies."""
    migrate(tmp_game_repo)
    _write(tmp_game_repo / ".ai", "agents/policies.yaml", POLICIES)
    return tmp_game_repo


async def test_startup_fails_on_pin_mismatch(kernel_repo: Path, fake_clock: FakeClock) -> None:
    ai = kernel_repo / ".ai"
    pins = KernelVersionPins.from_catalog(_scan(fake_clock))
    pins.pins["WORKFLOW/story_workflow"] = "1.1"
    pins.write(ai)
    overrides = KernelOverrides(
        adapters=fake_adapters(fake_clock),
        clock=fake_clock,
        sleep=_no_sleep,
        kernel_instance="test-instance",
        ready_env_keys={"git"},
    )
    handle = build_kernel(KernelSettings(repo_path=kernel_repo), overrides=overrides)
    try:
        with pytest.raises(VersionPinError, match=re.escape("wants 1.1, kernel provides 1.0")):
            await handle.orchestrator.start()
        started = await handle.ledger.query(kinds=[LedgerEventKind.PROJECT_STARTED])
    finally:
        await handle.aclose()
    assert started == []
