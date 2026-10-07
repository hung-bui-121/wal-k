"""`walk doctor --strict` lints (E02-S15): provider names, models.yaml, import contracts.

Each lint returns its findings as readable lines; an empty list means clean.
"""

import re
from pathlib import Path
from typing import Final

from walk.agents import Constitution
from walk.common.errors import ConfigError
from walk.integrations import SubprocessRunner
from walk.model_router import CapabilityRegistry

PROVIDER_NAME_PATTERN = r"(?i)\b(claude|anthropic|codex|openai|gpt|sonnet|opus)\b"

_PROVIDER_NAMES: Final = re.compile(PROVIDER_NAME_PATTERN)
_EXIT_NOT_FOUND: Final = 127
_BROKEN: Final = "BROKEN"


def lint_constitutions_provider_names(constitutions: list[Constitution]) -> list[str]:
    """One finding per constitution whose text names a model provider (ADR-0013 D-5).

    Constitutions describe a role, not a model: identity, mission, responsibilities, bias,
    beliefs, principles, conflict behaviour, forbidden actions and the body are scanned.
    """
    findings: list[str] = []
    for constitution in constitutions:
        text = "\n".join(
            [
                constitution.identity,
                constitution.mission,
                *constitution.responsibilities,
                constitution.professional_bias,
                *constitution.core_beliefs,
                *constitution.decision_principles,
                constitution.conflict_behavior,
                *constitution.forbidden_actions,
                constitution.body_markdown,
            ]
        )
        names = sorted({match.lower() for match in _PROVIDER_NAMES.findall(text)})
        if names:
            findings.append(
                f"constitution {constitution.role.value} names model providers "
                f"({', '.join(names)}); roles must stay provider-neutral (ADR-0013 D-5)"
            )
    return findings


def lint_models_yaml(registry: CapabilityRegistry) -> list[str]:
    """Every enabled model: prices > 0, supports_effort_levels non-empty, context_window_tokens > max_output_tokens > 0."""  # noqa: E501 - contract line (E02-S15)
    findings: list[str] = []
    for model_id, d in registry.models.items():
        if not d.enabled:
            continue
        if d.input_cost_per_mtok_usd <= 0 or d.output_cost_per_mtok_usd <= 0:
            findings.append(f"{model_id}: prices must be > 0")
        if not d.context_window_tokens > d.max_output_tokens > 0:
            findings.append(f"{model_id}: needs context_window_tokens > max_output_tokens > 0")
        if not d.supports_effort_levels:
            findings.append(f"{model_id}: supports_effort_levels is empty")
    return findings


async def run_import_linter(runner: SubprocessRunner, repo_root: Path) -> list[str]:
    """`lint-imports --config pyproject.toml`; returns broken contract lines; [] if clean; ConfigError if tool missing."""  # noqa: E501 - contract line (E02-S15)
    result = await runner.run(["lint-imports", "--config", "pyproject.toml"], cwd=str(repo_root))
    if result.exit_code == _EXIT_NOT_FOUND:
        msg = "import-linter not installed"
        raise ConfigError(msg, detail={"repo_root": str(repo_root)})
    if result.exit_code == 0:
        return []
    broken = [
        line.strip() for line in result.stdout.splitlines() if line.rstrip().endswith(_BROKEN)
    ]
    if broken:
        return broken
    lines = [line.strip() for line in (result.stderr or result.stdout).splitlines() if line.strip()]
    return [f"import-linter: {lines[-1] if lines else f'exit code {result.exit_code}'}"]
