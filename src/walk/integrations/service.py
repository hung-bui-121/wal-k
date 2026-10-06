"""`DefaultIntegrationManager`: the §26-§27 environment preflight (E02-S02).

Only `preflight` is implemented here. Inbound work events, reconciliation and idempotent
operations follow in E03-S03 (deferred-method pattern: they raise `ConfigError` naming it).
"""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime
from typing import Final

import yaml

from walk.common.clock import Clock
from walk.common.errors import ConfigError
from walk.common.ids import SkillName
from walk.integrations.credentials import CredentialStore
from walk.integrations.manifest import ManifestStore
from walk.integrations.models import (
    ComponentStatus,
    EnvironmentManifest,
    ReadinessState,
    WorkProviderEvent,
)
from walk.integrations.preflight import (
    MISSING_COMPONENTS,
    detect_claude_sdk,
    detect_cli_tool,
    detect_codex_cli,
    detect_credentials,
    detect_dotnet,
    detect_git,
    detect_graphify,
    detect_required_skills,
    detect_unity,
)
from walk.integrations.subprocess import SubprocessRunner
from walk.tools.models import ToolKind
from walk.tools.protocols import ToolRegistry

SdkOptionProbe = Callable[[], Sequence[str]]
"""Names of the ADR-0014 Claude SDK options missing from the installed SDK (introspection)."""

_DEFERRED: Final = "implemented in E03-S03"
_WORK_PROVIDER_FILE: Final = "work-provider.yaml"
_JIRA_CREDENTIALS: Final = ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")
# Executables with a dedicated detector; their registry CLI tools are not probed twice.
_DEDICATED: Final = frozenset({"git", "graphify", "dotnet", "unity"})


class DefaultIntegrationManager:
    """`IntegrationManager` (INTERFACES §1.12); providers and ingestion arrive in E03-S03."""

    def __init__(
        self,
        *,
        runner: SubprocessRunner,
        credentials: CredentialStore,
        manifest_store: ManifestStore,
        tools: ToolRegistry,
        clock: Clock,
        machine_id: str,
        unity_path: str | None,
        project_path: str,
        required_skills: list[SkillName],
        available_skills: list[SkillName],
        sdk_option_probe: SdkOptionProbe | None = None,
    ) -> None:
        """Wire the preflight.

        Args:
            runner: Runs every probe command.
            credentials: Presence of the known credentials.
            manifest_store: Previous manifest (drift) and where the new one is written.
            tools: ``kind == CLI`` entries are probed with ``<executable> --version``.
            clock: Stamps ``generated_at``.
            machine_id: Identifies this machine in the manifest (§27 drift).
            unity_path: Unity editor executable; ``Unity`` on PATH when ``None``.
            project_path: Game repository root (reads ``ProjectSettings/ProjectVersion.txt``).
            required_skills: Skills the project requires.
            available_skills: Skills present in the registry.
            sdk_option_probe: Lists missing ADR-0014 Claude SDK options when the SDK is
                installed; the composition root wires it from the Claude adapter (the only
                package allowed to import the SDK).
        """
        self._runner = runner
        self._credentials = credentials
        self._manifests = manifest_store
        self._tools = tools
        self._clock = clock
        self._machine_id = machine_id
        self._unity_path = unity_path
        self._project_path = project_path
        self._required_skills = list(required_skills)
        self._available_skills = list(available_skills)
        self._sdk_option_probe = sdk_option_probe

    async def preflight(self, required: list[str]) -> EnvironmentManifest:
        """§26 checks; writes `.ai/project/environment.yaml`; reports drift (§27).

        ``required`` names components: ``work_provider``, ``unity``, a key of ``tools`` or
        ``providers`` (e.g. ``git``, ``codex``), or ``<section>.<key>`` (e.g.
        ``credentials.JIRA_EMAIL``). The manifest is written before a failure is raised.

        Raises:
            ConfigError: A required component is MISSING (``detail["missing_components"]``),
                a required name is unknown, or the previous manifest is unreadable.
        """
        cli_tools = [
            spec
            for spec in self._tools.all()
            if spec.kind is ToolKind.CLI
            and spec.executable is not None
            and spec.executable.lower() not in _DEDICATED
        ]
        git, unity, codex, graphify, dotnet, *cli_statuses = await asyncio.gather(
            detect_git(self._runner),
            detect_unity(self._runner, self._unity_path, self._project_path),
            detect_codex_cli(self._runner),
            detect_graphify(self._runner),
            detect_dotnet(self._runner),
            *(detect_cli_tool(self._runner, str(spec.executable)) for spec in cli_tools),
        )
        tools = {"git": git, "graphify": graphify, "dotnet": dotnet}
        tools.update(
            {spec.name: status for spec, status in zip(cli_tools, cli_statuses, strict=True)}
        )
        manifest = EnvironmentManifest(
            generated_at=self._clock.now(),
            machine_id=self._machine_id,
            unity=unity,
            tools=tools,
            providers={"codex": codex, "claude": self._claude()},
            work_provider=self._work_provider(),
            credentials=detect_credentials(self._credentials),
            required_skills=detect_required_skills(self._required_skills, self._available_skills),
        )
        previous = self._manifests.read()
        if previous is not None:
            manifest = manifest.model_copy(
                update={
                    "drift_from": previous.machine_id,
                    "drift_items": self._manifests.diff(previous, manifest),
                }
            )
        states = {name: _state_of(manifest, name) for name in required}
        self._manifests.write(manifest)
        missing = [name for name, state in states.items() if state is ReadinessState.MISSING]
        if missing:
            msg = f"required components missing: {', '.join(missing)}"
            raise ConfigError(msg, detail={MISSING_COMPONENTS: missing})
        return manifest

    async def ingest(self, event: WorkProviderEvent) -> None:
        """Deferred to E03-S03.

        Raises:
            ConfigError: Always.
        """
        raise ConfigError(_DEFERRED, detail={"delivery_id": event.delivery_id})

    async def reconcile(self, since: datetime | None) -> int:
        """Deferred to E03-S03.

        Raises:
            ConfigError: Always.
        """
        raise ConfigError(_DEFERRED, detail={"since": since.isoformat() if since else None})

    async def with_idempotency(
        self, key: str, operation: str, fn: Callable[[], Awaitable[str]]
    ) -> str:
        """Deferred to E03-S03.

        Raises:
            ConfigError: Always.
        """
        del fn
        raise ConfigError(_DEFERRED, detail={"key": key, "operation": operation})

    def _claude(self) -> ComponentStatus:
        status = detect_claude_sdk()
        if status.state is not ReadinessState.READY or self._sdk_option_probe is None:
            return status
        try:
            missing = list(self._sdk_option_probe())
        except ConfigError as exc:
            return status.model_copy(
                update={"state": ReadinessState.MISCONFIGURED, "detail": exc.message}
            )
        if not missing:
            return status
        detail = f"ClaudeAgentOptions lacks {', '.join(missing)} (ADR-0014)"
        return status.model_copy(update={"state": ReadinessState.MISCONFIGURED, "detail": detail})

    def _work_provider(self) -> ComponentStatus:
        """Kind from ``.ai/project/work-provider.yaml``; Jira also needs its credentials."""
        path = self._manifests.path().parent / _WORK_PROVIDER_FILE
        if not path.is_file():
            return ComponentStatus(
                state=ReadinessState.UNKNOWN, detail=f"no {path.name}; run 'walk bootstrap'"
            )
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            return ComponentStatus(
                state=ReadinessState.MISCONFIGURED, detail=f"{path.name} is not valid YAML: {exc}"
            )
        kind = data.get("kind") if isinstance(data, dict) else None
        if kind == "local":
            return ComponentStatus(state=ReadinessState.READY, detail="local")
        if kind == "jira":
            absent = [name for name in _JIRA_CREDENTIALS if not self._credentials.present(name)]
            if absent:
                detail = f"jira credentials missing: {', '.join(absent)}"
                return ComponentStatus(state=ReadinessState.MISCONFIGURED, detail=detail)
            return ComponentStatus(state=ReadinessState.READY, detail="jira")
        return ComponentStatus(
            state=ReadinessState.MISCONFIGURED, detail=f"unknown work provider kind {kind!r}"
        )


def _state_of(manifest: EnvironmentManifest, name: str) -> ReadinessState:
    """State of the component ``name`` (see `DefaultIntegrationManager.preflight`).

    Raises:
        ConfigError: ``name`` names no component of the manifest.
    """
    if name in {"unity", "work_provider"}:
        status: ComponentStatus = getattr(manifest, name)
        return status.state
    section, dot, key = name.partition(".")
    sections: dict[str, dict[str, ComponentStatus] | dict[str, ReadinessState]] = {
        "unity_packages": manifest.unity_packages,
        "tools": manifest.tools,
        "providers": manifest.providers,
        "credentials": manifest.credentials,
        "required_skills": manifest.required_skills,
        "build_targets": manifest.build_targets,
    }
    if dot and section in sections:
        candidates: list[ComponentStatus | ReadinessState] = (
            [sections[section][key]] if key in sections[section] else []
        )
    else:
        candidates = [d[name] for d in (manifest.tools, manifest.providers) if name in d]
    if not candidates:
        msg = f"unknown preflight component {name!r}"
        raise ConfigError(msg, detail={"component": name})
    found = candidates[0]
    return found if isinstance(found, ReadinessState) else found.state
