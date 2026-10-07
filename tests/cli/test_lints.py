from pathlib import Path

import pytest

import walk.agents
from tests.fakes.fake_model_adapter import fake_descriptor
from tests.fakes.fake_subprocess import FakeSubprocessRunner
from walk.agents import ConstitutionLoader
from walk.cli.lints import (
    PROVIDER_NAME_PATTERN,
    lint_constitutions_provider_names,
    lint_models_yaml,
    run_import_linter,
)
from walk.common.enums import Effort
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.model_router import CapabilityRegistry

DEFAULTS = Path(walk.agents.__file__).resolve().parent / "defaults"
BROKEN = """\
=============
Import Linter
=============
common: ARCHITECTURE 2.2 row KEPT
runtime: ARCHITECTURE 2.2 row BROKEN

Contracts: 1 kept, 1 broken.
"""


def test_constitution_provider_name_lint() -> None:
    loader = ConstitutionLoader(DEFAULTS, None)
    clean = [loader.load(role) for role in loader.available_roles()]
    lead = loader.load(AgentRole.LEAD_DEV)
    tainted = lead.model_copy(
        update={"body_markdown": lead.body_markdown + "\nPrefer Claude Opus for reviews.\n"}
    )

    assert lint_constitutions_provider_names(clean) == []
    findings = lint_constitutions_provider_names([*clean[:1], tainted])
    assert len(findings) == 1
    assert "LEAD_DEV" in findings[0]
    assert "claude" in findings[0]
    assert "opus" in findings[0]
    assert PROVIDER_NAME_PATTERN.startswith("(?i)")


def test_models_yaml_lint_prices() -> None:
    good = fake_descriptor("x/good", "x")
    free = fake_descriptor("x/free", "x", input_cost_per_mtok_usd=0.0)
    tight = fake_descriptor("x/tight", "x", context_window_tokens=1000, max_output_tokens=1000)
    no_effort = fake_descriptor("x/flat", "x", supports_effort_levels=[])
    disabled = fake_descriptor("x/off", "x", output_cost_per_mtok_usd=0.0, enabled=False)
    models = {d.id: d for d in (good, free, tight, no_effort, disabled)}

    findings = lint_models_yaml(CapabilityRegistry(models=models, version="1"))

    assert [f.split(":")[0] for f in findings] == ["x/free", "x/tight", "x/flat"]
    assert lint_models_yaml(CapabilityRegistry(models={good.id: good}, version="1")) == []
    assert Effort.LOW in good.supports_effort_levels


async def test_import_linter_wrapper(tmp_path: Path) -> None:
    runner = FakeSubprocessRunner()
    runner.script(["lint-imports"], exit_code=1, stdout=BROKEN)

    findings = await run_import_linter(runner, tmp_path)

    assert findings == ["runtime: ARCHITECTURE 2.2 row BROKEN"]
    assert runner.calls[-1].argv == ["lint-imports", "--config", "pyproject.toml"]
    assert runner.calls[-1].cwd == str(tmp_path)
    clean = FakeSubprocessRunner()
    clean.script(["lint-imports"], exit_code=0, stdout="Contracts: 2 kept, 0 broken.\n")
    assert await run_import_linter(clean, tmp_path) == []
    odd = FakeSubprocessRunner()
    odd.script(["lint-imports"], exit_code=2, stderr="something else went wrong\n")
    assert await run_import_linter(odd, tmp_path) == ["import-linter: something else went wrong"]
    missing = FakeSubprocessRunner()
    missing.script(["lint-imports"], exit_code=127, stderr="lint-imports: not found\n")
    with pytest.raises(ConfigError, match="import-linter not installed"):
        await run_import_linter(missing, tmp_path)
