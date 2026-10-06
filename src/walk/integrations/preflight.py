"""§26 environment detectors used by `IntegrationManager.preflight` (E02-S02).

Every detector probes through the injected `SubprocessRunner` with a 5 s timeout and maps the
outcome to a `ComponentStatus`: READY with the parsed version, MISSING when the executable is
absent, MISCONFIGURED when it exits non-zero (detail = first stderr line), UNKNOWN on timeout.
The Codex probe also checks the ADR-0014 flags (no login, no model call).
"""

import importlib.metadata
import re
from pathlib import Path
from typing import Final

from walk.common.errors import Timeout
from walk.common.ids import SkillName
from walk.integrations.credentials import CredentialStore
from walk.integrations.models import ComponentStatus, ReadinessState
from walk.integrations.subprocess import SubprocessResult, SubprocessRunner

REQUIRED_DEFAULT: tuple[str, ...] = (
    "git",
    "work_provider",
)
"""Components whose absence makes `walk doctor` exit 4."""

MISSING_COMPONENTS: Final = "missing_components"
"""`ConfigError.detail` key listing the required components a failed preflight found MISSING."""

_PROBE_TIMEOUT_S: Final = 5
_EXIT_NOT_FOUND: Final = 127  # `AsyncioSubprocessRunner` reports a missing executable so
_VERSION: Final = re.compile(r"\d+(?:\.\d+)+(?:[a-z]\d+)?")
_UNITY_PROJECT_VERSION: Final = re.compile(r"^m_EditorVersion:\s*(\S+)", re.MULTILINE)
_CLAUDE_DISTRIBUTION: Final = "claude-agent-sdk"
_CODEX: Final = "codex"
# ADR-0014 Codex table: the flags `walk.model_router.adapters.codex.command` relies on.
_CODEX_EXEC_FLAGS: Final = ("--json", "--sandbox", "--cd", "--config", "--output-schema")
_CODEX_RESUME_FLAGS: Final = ("--json", "--config", "--output-schema")


async def detect_git(runner: SubprocessRunner) -> ComponentStatus:
    """``git --version``."""
    return await _probe(runner, ["git", "--version"])


async def detect_unity(
    runner: SubprocessRunner, unity_path: str | None, project_path: str
) -> ComponentStatus:
    """``<unity> -version`` (``Unity`` on PATH when no path is configured, ADR-0015).

    The project's editor version from ``ProjectSettings/ProjectVersion.txt`` is added to the
    detail when the file exists.
    """
    status = await _probe(runner, [unity_path or "Unity", "-version"])
    project_version = _unity_project_version(Path(project_path))
    if status.state is ReadinessState.READY and project_version is not None:
        return status.model_copy(update={"detail": f"project editor {project_version}"})
    return status


async def detect_codex_cli(runner: SubprocessRunner) -> ComponentStatus:
    """``codex --version``, then the ADR-0014 flags of ``codex exec`` and ``exec resume``."""
    status = await _probe(runner, [_CODEX, "--version"])
    if status.state is not ReadinessState.READY:
        return status
    for argv, flags in (
        ([_CODEX, "exec", "--help"], _CODEX_EXEC_FLAGS),
        ([_CODEX, "exec", "resume", "--help"], _CODEX_RESUME_FLAGS),
    ):
        problem = await _missing_flags(runner, argv, flags)
        if problem is not None:
            return status.model_copy(
                update={"state": ReadinessState.MISCONFIGURED, "detail": problem}
            )
    return status


def detect_claude_sdk() -> ComponentStatus:
    """The installed ``claude-agent-sdk`` version (package metadata; the SDK is not imported)."""
    try:
        version = importlib.metadata.version(_CLAUDE_DISTRIBUTION)
    except importlib.metadata.PackageNotFoundError:
        return ComponentStatus(
            state=ReadinessState.MISSING,
            detail=f"{_CLAUDE_DISTRIBUTION} is not installed (the 'claude' extra)",
        )
    return ComponentStatus(state=ReadinessState.READY, version=version)


async def detect_graphify(runner: SubprocessRunner) -> ComponentStatus:
    """``graphify --version`` (recommended, not required; ADR-0009 D-9)."""
    return await _probe(runner, ["graphify", "--version"])


async def detect_dotnet(runner: SubprocessRunner) -> ComponentStatus:
    """``dotnet --version``."""
    return await _probe(runner, ["dotnet", "--version"])


async def detect_cli_tool(runner: SubprocessRunner, executable: str) -> ComponentStatus:
    """``<executable> --version`` for a ``kind == CLI`` tool of the registry."""
    return await _probe(runner, [executable, "--version"])


def detect_credentials(store: CredentialStore) -> dict[str, ReadinessState]:
    """Presence of every known credential; never values (§139)."""
    return store.presence()


def detect_required_skills(
    required: list[SkillName], available: list[SkillName]
) -> dict[SkillName, ReadinessState]:
    """READY for each required skill that is available, MISSING otherwise."""
    present = set(available)
    return {
        name: ReadinessState.READY if name in present else ReadinessState.MISSING
        for name in required
    }


async def _probe(runner: SubprocessRunner, argv: list[str]) -> ComponentStatus:
    result = await _run(runner, argv)
    if isinstance(result, ComponentStatus):
        return result
    if result.exit_code != 0:
        return ComponentStatus(state=ReadinessState.MISCONFIGURED, detail=_first_line(result))
    match = _VERSION.search(result.stdout) or _VERSION.search(result.stderr)
    return ComponentStatus(
        state=ReadinessState.READY,
        version=match.group(0) if match else None,
        detail="" if match else _first_line(result),
    )


async def _run(runner: SubprocessRunner, argv: list[str]) -> SubprocessResult | ComponentStatus:
    """The finished result, or the MISSING/UNKNOWN status when it could not finish."""
    try:
        result = await runner.run(argv, timeout_s=_PROBE_TIMEOUT_S)
    except FileNotFoundError:
        return ComponentStatus(state=ReadinessState.MISSING, detail=f"{argv[0]} not found")
    except Timeout:
        detail = f"{' '.join(argv)} timed out after {_PROBE_TIMEOUT_S} s"
        return ComponentStatus(state=ReadinessState.UNKNOWN, detail=detail)
    if result.exit_code == _EXIT_NOT_FOUND:
        return ComponentStatus(
            state=ReadinessState.MISSING, detail=_first_line(result) or f"{argv[0]} not found"
        )
    return result


async def _missing_flags(
    runner: SubprocessRunner, argv: list[str], flags: tuple[str, ...]
) -> str | None:
    """Why ``argv`` (a ``--help`` call) does not show every flag, or None when it does."""
    command = " ".join(argv)
    result = await _run(runner, argv)
    if isinstance(result, ComponentStatus):
        return f"{command}: {result.detail}"
    if result.exit_code != 0:
        return f"{command} failed: {_first_line(result)}"
    text = result.stdout + result.stderr
    missing = [flag for flag in flags if not re.search(rf"(?<![\w-]){re.escape(flag)}\b", text)]
    if missing:
        return f"{command} lacks {', '.join(missing)} (ADR-0014)"
    return None


def _first_line(result: SubprocessResult) -> str:
    for text in (result.stderr, result.stdout):
        for line in text.splitlines():
            if line.strip():
                return line.strip()
    return f"exit code {result.exit_code}"


def _unity_project_version(project: Path) -> str | None:
    path = project / "ProjectSettings" / "ProjectVersion.txt"
    if not path.is_file():
        return None
    match = _UNITY_PROJECT_VERSION.search(path.read_text(encoding="utf-8", errors="replace"))
    return match.group(1) if match else None
