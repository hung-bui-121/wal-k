# EPIC-02 — Production Kit

**Roadmap stage:** §135 Stage 2
**Goal.** A game repository can be bootstrapped into a validated, reproducible Production Kit: environment manifest, `.ai/` tree, canonical skills with projections and drift detection, MUST hooks, permission rule set with protected actions and approvals, approved-artifact registry, security hardening.
**Requirements.** §24–§29, §31–§33, §91–§93 (pause/resume/priority/policy subset), §105 (pins), §123–§124, §137 (Inv. 7, 10, 11), §138 (Model Lock-In), §139 (credentials).
**Epic gate.** `tests/e2e/test_e02_gate.py`: on a fresh temp repo with a `GDD/` folder, `walk bootstrap --provider local --key DEMO --name Demo --yes` creates the full `.ai/` tree and DB; `walk doctor` exits 0 and writes `environment.yaml`; skills are projected for both providers and `walk skills check-drift` is clean, then a hand-edited projection is reported `modified`; a fake run requesting `git.merge_protected` pauses with an `ApprovalRequest`, `walk approve APV-0001` resumes it; `walk pause`/`walk resume` write `USER_OVERRIDE`; an agent diff touching `.ai/agents/roles/` is rejected by `BoundaryAuditor`.
**Precondition.** E01-R01 is `DONE` with no `BLOCKER` bugfix stories. All E01 symbols referenced below exist (`Default*` services per `WBS.md` §3.1).

## Story index

| ID | Title | Depends on | Effort |
|---|---|---|---|
| E02-S01 | `CredentialStore` and agent environment allowlist | E01-S23, E01-S25 | MEDIUM |
| E02-S02 | Environment preflight and `EnvironmentManifest`, `walk doctor` (basic) | E02-S01, E01-S14 | HIGH |
| E02-S03 | `walk bootstrap`: Production Kit generation and `.ai/` initialisation | E02-S02, E01-S16, E01-S17 | HIGH |
| E02-S04 | `kernel-versions.yaml` and behavior-version pins | E02-S03 | MEDIUM |
| E02-S05 | `SkillRegistry` loading and builtin skills | E01-S14 | MEDIUM |
| E02-S06 | Skill projections for Claude and Codex, lock file, `walk skills list/sync` | E02-S05, E01-S21, E01-S22, E01-S25 | HIGH |
| E02-S07 | Skill drift detection, `walk skills check-drift`, startup check | E02-S06, E02-S02 | MEDIUM |
| E02-S08 | Builtin MUST hooks (ARCHITECTURE §4.1 table) | E01-S07, E01-S28, E01-S16 | HIGH |
| E02-S09 | Project hooks from `.ai/agents/hooks.yaml` | E02-S08 | MEDIUM |
| E02-S10 | Permission defaults, `permissions.yaml` loader, protected actions | E01-S15, E02-S03 | MEDIUM |
| E02-S11 | Approval requests and `walk approve/deny/approvals` | E02-S10, E01-S26 | HIGH |
| E02-S12 | Approved artifact registry and `walk artifacts` | E02-S10, E01-S16 | HIGH |
| E02-S13 | Human override CLI subset | E01-S30, E02-S11 | MEDIUM |
| E02-S14 | Security hardening: forbidden paths, git guard hooks, secret scan, command restrictions | E02-S10, E01-S23, E01-S25 | HIGH |
| E02-S15 | `walk doctor --fix --strict` | E02-S07, E02-S14, E02-S04 | MEDIUM |
| E02-S16 | Epic gate: bootstrap → doctor → skills → approval → override (e2e) | E02-S15, E02-S13, E02-S12, E02-S09 | MEDIUM |
| E02-R01 | Review E02 | E02-S16 | MEDIUM |

## Reading order for implementers

1. `WBS.md` §2–§3 (rules, binding conventions), then this header.
2. The story itself; its `§NN` sections; `ARCHITECTURE.md` §3.4 (startup), §4.1 (hooks), §4.2 (enforcement), §6 (security), §8 (`.ai/` layout); `INTERFACES.md` §1.8, §1.10–§1.12, §6; ADR-0003, ADR-0006, ADR-0007, ADR-0009 (D-7, D-8, D-10, D-11), ADR-0013.
3. Existing E01 files named in the story's Files table and their tests.

Parallel sets (WBS.md §8): `{S05→S06→S07} ∥ {S08→S09} ∥ {S10→S11→S12}` after S03; `{S01} ∥ {S05}`; `{S13} ∥ {S14}`.

---

### E02-S01 — `CredentialStore` and agent environment allowlist

**Status:** TODO
**Type:** feat
**Requirements:** §91, §26, §139
**Depends on:** E01-S23, E01-S25
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Secrets are resolved only through `CredentialStore` (environment → OS keyring → absent) and agent subprocesses receive a scrubbed environment built from a fixed allowlist, so no provider or Jira credential can reach an agent.

#### Scope
- In: `CredentialStore`, credential name catalogue (ADR-0009 D-8), injectable keyring backend, `AGENT_ENV_ALLOWLIST`, `scrubbed_env`, wiring into `RunSession.env_allowlist` for both real adapters.
- Out: credential presence reporting in the manifest (E02-S02); secret-pattern scanning of written content (E02-S14); Jira credential use (E03-S04).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/integrations/credentials.py` | create | `CredentialStore`, `KeyringBackend` (Protocol), `SystemKeyringBackend`, `CREDENTIAL_NAMES` |
| `src/walk/integrations/__init__.py` | modify | re-export `CredentialStore`, `CREDENTIAL_NAMES` |
| `src/walk/runtime/sandbox.py` | modify | `AGENT_ENV_ALLOWLIST`, `scrubbed_env` |
| `src/walk/runtime/executor.py` | modify | — (passes `scrubbed_env(os.environ)` into `RunSession.env_allowlist`) |
| `src/walk/cli/composition.py` | modify | — (constructs `CredentialStore`, adds `KernelOverrides.keyring_backend`) |
| `tests/fakes/fake_keyring.py` | create | `FakeKeyringBackend` |
| `tests/integrations/test_credentials.py` | create | — |
| `tests/runtime/test_sandbox_env.py` | create | — |

#### Interface contract
```python
# src/walk/integrations/credentials.py
CREDENTIAL_NAMES: tuple[str, ...] = (
    "ANTHROPIC_API_KEY", "JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN",
    "WALK_WEBHOOK_SECRET", "MESHY_API_KEY", "OPENART_API_KEY",
)
KEYRING_SERVICE: str = "walk"

class KeyringBackend(Protocol):
    def get_password(self, service: str, username: str) -> str | None: ...

class SystemKeyringBackend:
    """Adapter over the `keyring` package (the only module importing `keyring`)."""
    def get_password(self, service: str, username: str) -> str | None: ...

class CredentialStore:
    def __init__(self, env: Mapping[str, str], backend: KeyringBackend | None) -> None: ...
    def get(self, name: str) -> SecretStr | None:
        """env[name] if set and non-empty, else backend.get_password(KEYRING_SERVICE, name), else None."""
    def present(self, name: str) -> bool: ...
    def presence(self) -> dict[str, ReadinessState]:
        """READY / MISSING for every CREDENTIAL_NAMES entry; never values."""

# src/walk/runtime/sandbox.py
AGENT_ENV_ALLOWLIST: tuple[str, ...] = ("PATH", "HOME", "TMP", "TEMP", "USERPROFILE", "SYSTEMROOT", "UNITY_*")
def scrubbed_env(os_env: Mapping[str, str]) -> dict[str, str]:
    """Keys equal to an allowlist entry or matching a trailing-`*` glob; values copied verbatim."""
```

#### Behavior
1. `get()` returns the env value when the variable exists and is non-empty; an empty string counts as absent and falls through to the keyring.
2. `get()` with no backend configured never raises; it returns `None` when env lookup misses.
3. A backend exception (keyring unavailable) is caught, logged at WARNING with `extra={"credential": name}`, and treated as absent.
4. `get()` for a name not in `CREDENTIAL_NAMES` raises `ConfigError("unknown credential name")`.
5. `presence()` returns exactly `len(CREDENTIAL_NAMES)` entries; `SecretStr` values never appear in `repr`, logs or the returned dict.
6. `scrubbed_env` keeps only allowlisted keys; glob entries match prefix (`UNITY_EDITOR_PATH` kept, `UNITYX` dropped); comparison is case-sensitive on POSIX and case-insensitive on Windows (`sys.platform == "win32"`).
7. `DefaultAgentExecutor` builds `RunSession.env_allowlist = scrubbed_env(os.environ)`; `CodexAdapter` spawns with exactly that mapping; `ClaudeAdapter` passes it as the SDK `env` option.
8. No module other than `credentials.py` imports `keyring` (ruff banned-api rule from ARCHITECTURE §2.3).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given env `JIRA_API_TOKEN=abc` When `get("JIRA_API_TOKEN")` Then `SecretStr("abc")` and backend not called | `tests/integrations/test_credentials.py::test_get_prefers_environment_over_keyring` |
| 2 | Given env unset and fake keyring holding the name When `get` Then keyring value returned | `tests/integrations/test_credentials.py::test_get_falls_back_to_keyring` |
| 3 | Given env empty string and keyring empty When `get` Then `None` | `tests/integrations/test_credentials.py::test_get_returns_none_when_absent` |
| 4 | Given backend raising `RuntimeError` When `get` Then `None` and a WARNING log record | `tests/integrations/test_credentials.py::test_get_treats_backend_error_as_absent` |
| 5 | Given name `FOO` When `get` Then `ConfigError` | `tests/integrations/test_credentials.py::test_get_unknown_name_raises_config_error` |
| 6 | Given two credentials present When `presence()` Then READY for those, MISSING for the rest, no values | `tests/integrations/test_credentials.py::test_presence_reports_states_without_values` |
| 7 | Given env with `ANTHROPIC_API_KEY`, `JIRA_API_TOKEN`, `PATH`, `UNITY_EDITOR_PATH` When `scrubbed_env` Then only `PATH` and `UNITY_EDITOR_PATH` remain | `tests/runtime/test_sandbox_env.py::test_scrubbed_env_drops_secrets_and_keeps_allowlist` |
| 8 | Given a Codex run via `FakeSubprocessRunner` When started Then the captured env has no key outside the allowlist | `tests/runtime/test_sandbox_env.py::test_codex_subprocess_env_is_scrubbed` |

#### Evidence required
- Quality gate output.
- Demo: `uv run python -c "from walk.integrations import CredentialStore; print(CredentialStore({'JIRA_EMAIL':'a@b'}, None).presence()['JIRA_EMAIL'])"` → `ReadinessState.READY`.

#### Notes
- ADR-0009 D-8; ARCHITECTURE §6 "Secret isolation".
- `NEW NAME:` `KeyringBackend`, `SystemKeyringBackend`, `CREDENTIAL_NAMES`, `KEYRING_SERVICE`, `AGENT_ENV_ALLOWLIST`, `scrubbed_env`, `KernelOverrides.keyring_backend`.
- Commit subject: `feat: add credential store and scrubbed agent environment (E02-S01)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S02 — Environment preflight and `EnvironmentManifest`, `walk doctor` (basic)

**Status:** TODO
**Type:** feat
**Requirements:** §26, §27, §25, §139
**Depends on:** E02-S01, E01-S14
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
`IntegrationManager.preflight` detects every §26 component, writes `.ai/project/environment.yaml`, reports drift against the previous manifest, and `walk doctor` prints the result with exit code 4 when a required component is missing.

#### Scope
- In: `DefaultIntegrationManager` class with `preflight` only; detectors; manifest write/read/drift; `walk doctor` without flags.
- Out: `ingest/reconcile/with_idempotency` (E03-S03); `--fix/--strict` (E02-S15); skill drift section (E02-S07); approved-artifact verification (E02-S12).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/integrations/preflight.py` | create | `detect_git`, `detect_unity`, `detect_codex_cli`, `detect_claude_sdk`, `detect_graphify`, `detect_dotnet`, `detect_credentials`, `detect_required_skills`, `REQUIRED_DEFAULT` |
| `src/walk/integrations/manifest.py` | create | `ManifestStore` |
| `src/walk/integrations/service.py` | create | `DefaultIntegrationManager` (only `preflight` implemented; other protocol methods raise `NotImplementedError` with the story id, replaced in E03-S03) |
| `src/walk/integrations/__init__.py` | modify | re-export `DefaultIntegrationManager`, `ManifestStore` |
| `src/walk/cli/cmd_doctor.py` | create | `doctor` |
| `src/walk/cli/app.py` | modify | register `doctor` |
| `src/walk/cli/composition.py` | modify | — (constructs `DefaultIntegrationManager`) |
| `tests/integrations/test_preflight.py` | create | — |
| `tests/integrations/test_manifest.py` | create | — |
| `tests/cli/test_cmd_doctor.py` | create | — |

#### Interface contract
See INTERFACES.md §1.12 `IntegrationManager.preflight`. Deltas:
```python
# src/walk/integrations/preflight.py
REQUIRED_DEFAULT: tuple[str, ...] = ("git", "work_provider")        # keys that make doctor exit 4 when MISSING
async def detect_git(runner: SubprocessRunner) -> ComponentStatus: ...            # `git --version`
async def detect_unity(runner: SubprocessRunner, unity_path: str | None, project_path: str) -> ComponentStatus: ...  # `<unity> -version`; reads ProjectSettings/ProjectVersion.txt
async def detect_codex_cli(runner: SubprocessRunner) -> ComponentStatus: ...      # `codex --version`
def detect_claude_sdk() -> ComponentStatus: ...                                   # importlib.metadata.version("claude-agent-sdk")
async def detect_graphify(runner: SubprocessRunner) -> ComponentStatus: ...       # `graphify --version`
async def detect_dotnet(runner: SubprocessRunner) -> ComponentStatus: ...         # `dotnet --version`
def detect_credentials(store: CredentialStore) -> dict[str, ReadinessState]: ...
def detect_required_skills(required: list[SkillName], available: list[SkillName]) -> dict[SkillName, ReadinessState]: ...

# src/walk/integrations/manifest.py
class ManifestStore:
    def __init__(self, ai_root: Path, clock: Clock) -> None: ...
    def path(self) -> Path: ...                                  # <ai_root>/project/environment.yaml
    def read(self) -> EnvironmentManifest | None: ...
    def write(self, manifest: EnvironmentManifest) -> Path: ...   # atomic tmp + rename
    def diff(self, previous: EnvironmentManifest, current: EnvironmentManifest) -> list[str]:
        """'<section>.<key>: <old state/version> -> <new state/version>' for every changed component."""

# src/walk/integrations/service.py
class DefaultIntegrationManager:
    def __init__(self, *, runner: SubprocessRunner, credentials: CredentialStore, manifest_store: ManifestStore,
                 tools: ToolRegistry, clock: Clock, machine_id: str, unity_path: str | None, project_path: str,
                 required_skills: list[SkillName], available_skills: list[SkillName]) -> None: ...
    async def preflight(self, required: list[str]) -> EnvironmentManifest: ...
```

#### Behavior
1. Each detector returns `READY` with `version` when the probe succeeds, `MISSING` when the executable is absent (`FileNotFoundError` from the runner), `MISCONFIGURED` when it exists but exits non-zero (detail = first stderr line), `UNKNOWN` on timeout (5 s).
2. `preflight(required)` runs all detectors concurrently (`asyncio.gather`), builds `EnvironmentManifest(generated_at=clock.now(), machine_id=…)`, sets `work_provider` from `.ai/project/work-provider.yaml` kind (`local` → READY; `jira` → READY only if the three Jira credentials are present, else MISCONFIGURED).
3. If a previous manifest exists, `drift_from = previous.machine_id` and `drift_items = ManifestStore.diff(previous, current)`; otherwise both unset.
4. The manifest is written before the function returns; `credentials` holds states only (rule S01-5).
5. `preflight` raises `ConfigError` listing the missing keys when any key in `required` is MISSING; the manifest is still written first.
6. `walk doctor` calls `preflight(REQUIRED_DEFAULT)`, prints a table (`component | state | version | detail`) grouped by section, and exits 0 when all required are READY, 4 when `ConfigError` from rule 5, 1 on any other `WalkError`. `--json` prints `EnvironmentManifest.model_dump_json()`.
7. `walk doctor` runs in-process (no daemon needed) and acquires `KernelLock` in shared mode only if the lock module supports it; otherwise it opens the DB read-only.
8. `tools` status for CLI tools comes from `ToolRegistry.all()` entries with `kind == CLI`: each `executable` is probed with `<exe> --version` through the runner.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given runner returning `git version 2.45.0` When `detect_git` Then READY with version `2.45.0` | `tests/integrations/test_preflight.py::test_detect_git_ready_with_version` |
| 2 | Given runner raising `FileNotFoundError` When `detect_codex_cli` Then MISSING | `tests/integrations/test_preflight.py::test_detect_missing_executable_reports_missing` |
| 3 | Given runner exit 1 with stderr When `detect_unity` Then MISCONFIGURED with detail | `tests/integrations/test_preflight.py::test_detect_nonzero_exit_reports_misconfigured` |
| 4 | Given runner timing out When `detect_dotnet` Then UNKNOWN | `tests/integrations/test_preflight.py::test_detect_timeout_reports_unknown` |
| 5 | Given no previous manifest When `preflight([])` Then file written, `drift_from is None` | `tests/integrations/test_manifest.py::test_preflight_writes_manifest_without_drift` |
| 6 | Given previous manifest with git 2.44 on machine A When `preflight` on machine B finds 2.45 Then `drift_from == "A"` and one drift item | `tests/integrations/test_manifest.py::test_preflight_reports_drift_against_previous` |
| 7 | Given git MISSING When `preflight(["git"])` Then `ConfigError` and manifest still written | `tests/integrations/test_preflight.py::test_preflight_required_missing_raises_after_writing` |
| 8 | Given all required READY When `walk doctor` Then exit 0 and table contains `git` | `tests/cli/test_cmd_doctor.py::test_doctor_exit_zero_when_ready` |
| 9 | Given git MISSING When `walk doctor` Then exit 4 | `tests/cli/test_cmd_doctor.py::test_doctor_exit_four_when_required_missing` |
| 10 | Given `--json` When `walk doctor` Then stdout parses as `EnvironmentManifest` | `tests/cli/test_cmd_doctor.py::test_doctor_json_output_is_manifest` |

#### Evidence required
- Quality gate output.
- Demo: `walk doctor` in a repo with git installed → table with `tools.git  ready  2.x`, exit 0; `walk doctor --json | head -c 200`.

#### Notes
- ADR-0009 D-8, D-9, D-11 (plugin versions recorded under `tools`); ARCHITECTURE §3.4 step 2.
- Jira status-map validation is E03-S05; the `work_provider` component here only checks kind + credentials.
- `NEW NAME:` `ManifestStore`, `REQUIRED_DEFAULT`, detector function names.
- Commit subject: `feat: add environment preflight manifest and doctor command (E02-S02)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S03 — `walk bootstrap`: Production Kit generation and `.ai/` initialisation

**Status:** TODO
**Type:** feat
**Requirements:** §24, §25, §123, §124, §34, §35, §36
**Depends on:** E02-S02, E01-S16, E01-S17
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
`walk bootstrap` turns a game repository into a Production Kit in one idempotent command: preflight, kernel defaults copied into `.ai/agents/`, `.ai/project/*` initialised from the GDD, `.ai/.gitignore`, DB created and migrated, `projects` row inserted, `ProductionKit` written.

#### Scope
- In: `Bootstrapper`, `cmd_bootstrap`, `.ai/` tree creation, `project.md`/`constitution.md` skeletons, `work-provider.yaml`, placeholder `kernel-versions.yaml` (content E02-S04), `production-kit.yaml`.
- Out: version pin content (E02-S04); skill projection (E02-S06); Jira status validation (E03-S05); `com.walk.ci` package install (E03-S10).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/integrations/bootstrap.py` | create | `Bootstrapper`, `BootstrapOptions`, `BootstrapResult` |
| `src/walk/integrations/__init__.py` | modify | re-export `Bootstrapper`, `BootstrapOptions` |
| `src/walk/integrations/defaults/work-provider.yaml` | create | — (template: `kind: local`, commented Jira mapping per ADR-0005 D-3) |
| `src/walk/integrations/defaults/ai.gitignore` | create | — (`kernel.db*`, `kernel.lock`) |
| `src/walk/integrations/defaults/root.gitignore.fragment` | create | — (`.walk/`, `graphify-out/`) |
| `src/walk/memory/skeletons.py` | create | `project_skeleton`, `project_constitution_skeleton` |
| `src/walk/cli/cmd_bootstrap.py` | create | `bootstrap` |
| `src/walk/cli/app.py` | modify | register `bootstrap` |
| `tests/integrations/test_bootstrap.py` | create | — |
| `tests/memory/test_skeletons.py` | create | — |
| `tests/cli/test_cmd_bootstrap.py` | create | — |

#### Interface contract
```python
# src/walk/integrations/bootstrap.py
class BootstrapOptions(WalkModel):
    repo_path: str
    project_key: ProjectKey
    name: str
    gdd_paths: list[str] = Field(default_factory=list, description="Relative to repo root; default: every *.md under GDD/")
    provider: Literal["local", "jira"] = "local"
    unity_path: str | None = None
    yes: bool = False

class BootstrapResult(WalkModel):
    kit: ProductionKit
    manifest: EnvironmentManifest
    created_paths: list[str]
    unchanged_paths: list[str]

class Bootstrapper:
    def __init__(self, *, integrations: IntegrationManager, memory: MemoryManager, database: Database,
                 migrations: MigrationRunner, work_repo: WorkflowRepository, clock: Clock, kit_version: str) -> None: ...
    async def run(self, options: BootstrapOptions) -> BootstrapResult: ...

# src/walk/memory/skeletons.py
def project_skeleton(project_key: ProjectKey, name: str, gdd_paths: list[str], gdd_headings: list[str], actor: Actor, now: datetime) -> MemoryDocument:
    """type=project, id='project', all §36 H2 sections present; 'Goals' holds one bullet per top-level GDD heading; related.gdd = gdd_paths."""
def project_constitution_skeleton(project_key: ProjectKey, name: str, actor: Actor, now: datetime) -> MemoryDocument:
    """type=project_constitution, id='constitution', sections: Product Authority, Constraints, Quality Bar, Forbidden."""
```
CLI: `walk bootstrap [--gdd PATH]... --provider local|jira --name NAME --key KEY [--unity-path PATH] --yes` (INTERFACES §6).

#### Behavior
1. Order of steps (each idempotent): (a) create `.ai/` and `.walk/`; (b) `Database` open + `MigrationRunner.apply_pending`; (c) `preflight(REQUIRED_DEFAULT)` — failure aborts with exit 4 before any copy; (d) copy kernel defaults: `src/walk/agents/defaults/*.md` → `.ai/agents/roles/`, `agents/defaults/policies.yaml` → `.ai/agents/policies.yaml`, `permissions/defaults.yaml` → `.ai/agents/permissions.yaml`, `model_router/defaults/models.yaml` → `.ai/agents/models.yaml`, empty `hooks.yaml` (`hooks: []`), empty `skills/` dir, `projections.lock.yaml` (`projections: []`); (e) `work-provider.yaml` with `kind: <provider>`; (f) `project.md`, `constitution.md` via `MemoryManager.write` (actor `USER`, head = repo HEAD or `0000000` when the repo has no commits); (g) `kernel-versions.yaml` placeholder `{}` (E02-S04 replaces); (h) `.ai/.gitignore`, append fragment to root `.gitignore` if lines absent; (i) `projects` row upsert; (j) `production-kit.yaml`.
2. Existing files are never overwritten; they are listed in `unchanged_paths`. A second run produces `created_paths == []` and exit 0.
3. Without `--yes`, a non-TTY stdin aborts with exit 1 and message `bootstrap requires --yes in non-interactive mode`; with a TTY the command prompts `Create Production Kit in <repo>? [y/N]`.
4. `--key` must match `ProjectKey`; invalid → exit 1 before any filesystem change.
5. GDD headings are collected from H1/H2 lines of every GDD file; when `--gdd` is omitted and `GDD/` exists, all `*.md` files under it are used; when neither exists, `Goals` contains the single bullet `- (no GDD provided)`.
6. `ProductionKit` fields are filled with repo-relative paths; `skill_names` = builtin skill names present under `src/walk/skills/builtin/` (names read from directories; registry service is E02-S05); `approved_artifact_ids = []`.
7. `--provider jira` additionally requires the three Jira credentials present; absence → exit 4 with the missing names (status-map validation added in E03-S05).
8. All writes go through `MemoryManager.write` (Markdown) or atomic `tmp + rename` helpers (YAML) — no direct `open().write` outside `walk.persistence`/`walk.memory` helpers (CONVENTIONS §2).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given an empty temp git repo with `GDD/combat.md` When `run(options)` Then every path of ARCHITECTURE §8 `[MVP]` + `agents/` exists | `tests/integrations/test_bootstrap.py::test_bootstrap_creates_full_ai_tree` |
| 2 | Given the same repo When `run` twice Then second `created_paths == []` and file hashes unchanged | `tests/integrations/test_bootstrap.py::test_bootstrap_is_idempotent` |
| 3 | Given preflight MISSING git When `run` Then `ConfigError` and no `.ai/agents/` created | `tests/integrations/test_bootstrap.py::test_bootstrap_aborts_on_preflight_failure` |
| 4 | Given GDD with headings `# Combat`, `## Shotgun` When `project_skeleton` Then `Goals` has bullet `Combat` and `related.gdd` lists the file | `tests/memory/test_skeletons.py::test_project_skeleton_seeds_goals_from_gdd_headings` |
| 5 | Given skeleton When parsed by `MemoryManager.read("project")` Then all ten §36 sections present in order | `tests/memory/test_skeletons.py::test_project_skeleton_has_all_sections_in_order` |
| 6 | Given `--provider jira` and no credentials When `walk bootstrap --yes` Then exit 4 listing `JIRA_BASE_URL` | `tests/cli/test_cmd_bootstrap.py::test_bootstrap_jira_requires_credentials` |
| 7 | Given no `--yes` and non-TTY When `walk bootstrap` Then exit 1 and nothing created | `tests/cli/test_cmd_bootstrap.py::test_bootstrap_requires_yes_when_non_interactive` |
| 8 | Given `--key demo` (lowercase) When `walk bootstrap --yes` Then exit 1 | `tests/cli/test_cmd_bootstrap.py::test_bootstrap_rejects_invalid_project_key` |
| 9 | Given a successful run When reading `production-kit.yaml` Then it validates as `ProductionKit` with `kit_version` | `tests/integrations/test_bootstrap.py::test_bootstrap_writes_production_kit_file` |
| 10 | Given a successful run When querying `projects` Then one row with `key`, `repo_path`, `work_provider` | `tests/integrations/test_bootstrap.py::test_bootstrap_inserts_project_row` |

#### Evidence required
- Quality gate output.
- Demo: `walk bootstrap --provider local --key DEMO --name Demo --yes` → prints created paths; `tree .ai` (or `Get-ChildItem -Recurse .ai`) shows the layout; second run prints `nothing to do`.

#### Notes
- §25 ordering; ADR-0003 D-7/D-8; ARCHITECTURE §8.
- `NEW NAME:` `Bootstrapper`, `BootstrapOptions`, `BootstrapResult`, `.ai/project/production-kit.yaml`, `walk.memory.skeletons`, defaults files under `integrations/defaults/`.
- Pitfall: repo without commits has no HEAD — use `Sha("0000000")` placeholder and document it in `MemoryManager.write` tests.
- Commit subject: `feat: add bootstrap command generating the production kit (E02-S03)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S04 — `kernel-versions.yaml` and behavior-version pins

**Status:** TODO
**Type:** feat
**Requirements:** §105, §24, §137
**Depends on:** E02-S03
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every builtin behaviour artifact is catalogued as a `BehaviorVersion`; bootstrap writes `.ai/project/kernel-versions.yaml` pinning the `DEFAULT` versions; startup validates pins; `walk version` lists them.

#### Scope
- In: improvement enums/models, `BehaviorVersionCatalog`, pin file schema + load + validate, bootstrap integration, startup step 3 check, `walk version`.
- Out: `register_version`, rollout stages, changelog (E10-S05); using pinned versions to select among multiple builtin versions (E10-S05 — until then exactly one version per artifact exists and must equal the pin).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/improvement/__init__.py` | create | re-exports |
| `src/walk/improvement/models.py` | create | `RolloutStage`, `ImprovementRisk`, `CandidateState`, `BehaviorVersion` |
| `src/walk/improvement/versions.py` | create | `BehaviorVersionCatalog`, `KernelVersionPins`, `PINS_PATH` |
| `src/walk/improvement/errors.py` | create | `VersionPinError` |
| `src/walk/integrations/bootstrap.py` | modify | — (step g writes pins from catalog) |
| `src/walk/orchestrator/service.py` | modify | — (startup step 3 calls `KernelVersionPins.validate`) |
| `src/walk/cli/cmd_version.py` | create | `version` |
| `src/walk/cli/app.py` | modify | `--version` now delegates to `cmd_version` |
| `tests/improvement/test_versions.py` | create | — |
| `tests/cli/test_cmd_version.py` | create | — |

#### Interface contract
Models: DOMAIN-MODEL §3 (`RolloutStage`, `ImprovementRisk`, `CandidateState`) and §4.14 `BehaviorVersion`, verbatim.
```python
# src/walk/improvement/versions.py
PINS_PATH: str = "project/kernel-versions.yaml"      # relative to .ai/

class BehaviorVersionCatalog:
    """Scans builtin behaviour files and yields one BehaviorVersion per artifact (stage=DEFAULT)."""
    def __init__(self, package_root: Path, clock: Clock) -> None: ...
    def scan(self) -> list[BehaviorVersion]:
        """WORKFLOW: walk/workflow/tables/*.yaml (`version`); CONSTITUTION: walk/agents/defaults/*.md (front matter `version`);
        SKILL: walk/skills/builtin/*/SKILL.md; PROMPT: walk/agents/templates/*.md.j2 (first-line comment `{# version: X.Y #}`);
        MODEL_ROUTING: walk/model_router/defaults/models.yaml; EFFORT_POLICY: walk/agents/defaults/policies.yaml;
        TOOL_USAGE: walk/tools/defaults/tools.yaml; CONTEXT_FORMAT: walk/context/ranking.yaml (if present)."""
    def key(self, v: BehaviorVersion) -> str: ...     # f"{v.kind.value}/{v.name}"

class KernelVersionPins(WalkModel):
    pins: dict[str, str] = Field(description="'<KIND>/<name>' -> 'MAJOR.MINOR'")
    @classmethod
    def from_catalog(cls, catalog: list[BehaviorVersion]) -> "KernelVersionPins": ...
    @classmethod
    def load(cls, ai_root: Path) -> "KernelVersionPins": ...
    def write(self, ai_root: Path) -> Path: ...
    def validate(self, catalog: list[BehaviorVersion]) -> None:
        """Raises VersionPinError listing: pins without catalog entry, catalog entries without pin, version mismatches."""
```
`walk version` output: `walk <kernel version>` then one line per pin `<KIND>/<name> <version>`; `--json` → `{"kernel": "...", "pins": {...}}`.

#### Behavior
1. Every artifact file lacking a `version` field makes `scan()` raise `ConfigError("<path>: missing version")` — this also protects E01 artefacts (ADR-0008 consequence).
2. `version` must match `^\d+\.\d+$`; otherwise `ConfigError`.
3. `content_sha256` is the SHA-256 of the file bytes; `source_path` is package-relative; `introduced_at = clock.now()` (not persisted in E02).
4. `from_catalog` pins every entry; `write` produces sorted keys for stable diffs.
5. `validate` collects all three problem classes before raising `VersionPinError(PermanentError)`; message lines are `missing pin: X`, `unknown pin: X`, `pin X wants 1.1, kernel provides 1.0`.
6. Bootstrap step (g) now writes real pins; an existing non-empty pin file is left untouched (idempotency rule S03-2).
7. Startup (`DefaultOrchestrator.start`, ARCHITECTURE §3.4 step 3) calls `validate`; failure aborts startup with exit 1 and the guidance `run 'walk version' and update .ai/project/kernel-versions.yaml`.
8. `walk version` works without a bootstrapped repo (prints kernel version only, pins section `(no project)`).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the kernel package When `scan()` Then one entry per workflow table, constitution, builtin skill and template, each with `version` and sha | `tests/improvement/test_versions.py::test_catalog_scans_all_builtin_artifacts` |
| 2 | Given a temp table file without `version` When `scan()` Then `ConfigError` naming the path | `tests/improvement/test_versions.py::test_catalog_rejects_artifact_without_version` |
| 3 | Given catalog When `from_catalog().write()` then `load()` Then equal pins and sorted keys | `tests/improvement/test_versions.py::test_pins_roundtrip_sorted` |
| 4 | Given pins with an extra key When `validate` Then `VersionPinError` containing `unknown pin` | `tests/improvement/test_versions.py::test_validate_reports_unknown_pin` |
| 5 | Given pins missing one key When `validate` Then `VersionPinError` containing `missing pin` | `tests/improvement/test_versions.py::test_validate_reports_missing_pin` |
| 6 | Given a pin `1.1` for a `1.0` artifact When `validate` Then message `wants 1.1, kernel provides 1.0` | `tests/improvement/test_versions.py::test_validate_reports_version_mismatch` |
| 7 | Given bootstrapped repo When `walk version` Then kernel version line plus every pin | `tests/cli/test_cmd_version.py::test_version_lists_pins` |
| 8 | Given cwd outside any repo When `walk version` Then exit 0 and `(no project)` | `tests/cli/test_cmd_version.py::test_version_without_project` |
| 9 | Given a mismatched pin file When `DefaultOrchestrator.start()` Then startup raises `VersionPinError` before `ON_PROJECT_START` fires | `tests/improvement/test_versions.py::test_startup_fails_on_pin_mismatch` |

#### Evidence required
- Quality gate output.
- Demo: `walk version` → `walk 0.1.0` + lines such as `WORKFLOW/story_workflow 1.0`, `CONSTITUTION/LEAD_DEV 1.0`, `SKILL/walk-output-contract 1.0`.

#### Notes
- ADR-0008 D-3/D-4 (data model fixed now, tooling Stage 10); ARCHITECTURE §9.
- `NEW NAME:` `BehaviorVersionCatalog`, `KernelVersionPins`, `VersionPinError`, `PINS_PATH`, template version comment convention `{# version: X.Y #}`.
- Commit subject: `feat: add behavior version catalog and kernel version pins (E02-S04)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S05 — `SkillRegistry` loading and builtin skills

**Status:** TODO
**Type:** feat
**Requirements:** §28, §29, §30, §137
**Depends on:** E01-S14
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Canonical skills (`SKILL.md` + front matter) are loaded from kernel built-ins and `.ai/agents/skills/`, project skills shadow built-ins by name, `for_role` resolves role defaults plus required skills, and the five builtin skills ship with real content.

#### Scope
- In: `DefaultSkillRegistry.load/get/for_role`, front-matter schema, builtin skill folders, loader errors.
- Out: `project_all` (E02-S06), `check_drift` (E02-S07), skill version pinning behaviour (E10-S05).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/skills/service.py` | create | `DefaultSkillRegistry` |
| `src/walk/skills/loader.py` | create | `SkillFrontMatter`, `parse_skill_file`, `discover_skill_dirs` |
| `src/walk/skills/errors.py` | create | `SkillLoadError` |
| `src/walk/skills/__init__.py` | modify | re-export `DefaultSkillRegistry`, `parse_skill_file` |
| `src/walk/skills/builtin/walk-output-contract/SKILL.md` | create | — |
| `src/walk/skills/builtin/unity-csharp-conventions/SKILL.md` | create | — |
| `src/walk/skills/builtin/git-hygiene/SKILL.md` | create | — |
| `src/walk/skills/builtin/qc-exploratory-testing/SKILL.md` | create | — |
| `src/walk/skills/builtin/code-review-checklist/SKILL.md` | create | — |
| `src/walk/agents/defaults/policies.yaml` | modify | — (`default_skills` per role, see Behavior 7) |
| `src/walk/cli/composition.py` | modify | — (constructs `DefaultSkillRegistry`) |
| `tests/skills/test_loader.py` | create | — |
| `tests/skills/test_service.py` | create | — |
| `tests/skills/test_builtin_skills.py` | create | — |

#### Interface contract
See INTERFACES.md §1.11 `SkillRegistry` (`load`, `get`, `for_role`). Deltas:
```python
# src/walk/skills/loader.py
class SkillFrontMatter(WalkModel):
    name: SkillName
    version: str = Field(pattern=r"^\d+\.\d+$")
    description: str = Field(min_length=1, max_length=300)
    scope: LearningScope
    applies_to_roles: list[AgentRole] = Field(default_factory=list)
    requires_tools: list[ToolName] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

def discover_skill_dirs(root: Path) -> list[Path]: ...        # <root>/<kebab-name>/SKILL.md present
def parse_skill_file(path: Path) -> Skill: ...                 # front matter + body; content_sha256 over file bytes

# src/walk/skills/service.py
class DefaultSkillRegistry:
    def __init__(self, builtin_root: Path, project_root: Path | None, role_defaults: Mapping[AgentRole, list[SkillName]]) -> None: ...
```

#### Behavior
1. `load()` reads built-ins then project skills; a project skill with the same `name` replaces the builtin entry (`source_path` points to the project file). Result is cached until `load()` is called again.
2. Directory name must equal front-matter `name`; mismatch → `SkillLoadError(ConfigError)` naming both.
3. Missing/invalid front matter, body > 64 KB, or `scope: KERNEL` under the project root → `SkillLoadError`.
4. `get(name)` raises `ConfigError("unknown skill <name>")` when absent.
5. `for_role(role, required)` returns `role_defaults[role] ∪ required` in that order, de-duplicated; every `required` name must resolve, otherwise `ConfigError` listing the missing names (§29).
6. Builtin skill bodies (each ≤ 4 KB, Markdown):
   - `walk-output-contract`: the `AgentOutput` JSON schema field by field (`status` values and when to use each, `result`, `findings`, `changes`, `decisions` as proposals, `evidence`, `context_updates` with `doc_id/section/operation`, `new_tasks`, `new_bugs`, `escalations`, `next_actions`, `handover` required on `PARTIAL`, `effort_request`, `observations`, `no_context_change_reason`), the mandatory last step "write `<worktree>/.walk/output.json`", and the rule "never write under `.ai/` directly". `applies_to_roles`: all MVP roles.
   - `unity-csharp-conventions`: namespaces, assembly definitions, serialization, MonoBehaviour lifecycle, async/await vs coroutines, EditMode/PlayMode test placement. Roles: SENIOR_DEV, LEAD_DEV. `requires_tools: []`.
   - `git-hygiene`: work only on the provided branch, never switch branches, small commits are made by the kernel, no force operations, read `git status` before finishing. Roles: SENIOR_DEV, LEAD_DEV, QC. `requires_tools: ["git.status"]` is NOT used (kernel tool) — leave `requires_tools: []`.
   - `qc-exploratory-testing`: §65 question list, severity rubric mapped to `Severity`, reproduction-step format for `BugDraft.reproduction`. Roles: QC.
   - `code-review-checklist`: architecture fit, tests present, boundary/permission concerns, evidence check, verdict → `APPROVED`/`REJECTED` with findings. Roles: LEAD_DEV.
7. `policies.yaml` `default_skills`: ORCHESTRATOR `[walk-output-contract]`; LEAD_DEV `[walk-output-contract, code-review-checklist, unity-csharp-conventions, git-hygiene]`; SENIOR_DEV `[walk-output-contract, unity-csharp-conventions, git-hygiene]`; QC `[walk-output-contract, qc-exploratory-testing, git-hygiene]`.
8. `Skill.version` of every builtin is `1.0`; `BehaviorVersionCatalog` (E02-S04) picks them up without changes.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the five builtin folders When `load()` Then five `Skill`s with matching names and sha | `tests/skills/test_service.py::test_load_returns_builtin_skills` |
| 2 | Given a project skill named `git-hygiene` When `load()` Then the returned skill's `source_path` is the project file | `tests/skills/test_service.py::test_project_skill_shadows_builtin` |
| 3 | Given folder `foo/` with front matter `name: bar` When `parse_skill_file` Then `SkillLoadError` | `tests/skills/test_loader.py::test_parse_rejects_name_directory_mismatch` |
| 4 | Given project skill with `scope: KERNEL` When `load()` Then `SkillLoadError` | `tests/skills/test_loader.py::test_project_skill_cannot_claim_kernel_scope` |
| 5 | Given `get("nope")` Then `ConfigError` | `tests/skills/test_service.py::test_get_unknown_raises_config_error` |
| 6 | Given QC role and required `[unity-csharp-conventions]` When `for_role` Then defaults first then the required skill, no duplicates | `tests/skills/test_service.py::test_for_role_merges_defaults_and_required` |
| 7 | Given required `[missing-skill]` When `for_role` Then `ConfigError` listing it | `tests/skills/test_service.py::test_for_role_missing_required_raises` |
| 8 | Given each builtin SKILL.md When measured Then body ≤ 4096 bytes and `walk-output-contract` mentions every `AgentOutput` field name | `tests/skills/test_builtin_skills.py::test_builtin_skills_size_and_contract_coverage` |

#### Evidence required
- Quality gate output.
- Demo: `uv run python -c "from walk.skills import DefaultSkillRegistry; ..."` is not a CLI; `walk skills list` arrives in E02-S06 — record the test transcript of `test_builtin_skills.py` instead.

#### Notes
- ADR-0007 D-1, D-4, D-6; names per WBS.md §3.10 (`NEW NAME` already registered).
- `NEW NAME:` `SkillFrontMatter`, `parse_skill_file`, `discover_skill_dirs`, `SkillLoadError`.
- Commit subject: `feat: add skill registry loader and builtin skills (E02-S05)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S06 — Skill projections for Claude and Codex, lock file, `walk skills list/sync`

**Status:** TODO
**Type:** feat
**Requirements:** §28, §29, §137, §138
**Depends on:** E02-S05, E01-S21, E01-S22, E01-S25
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Each adapter projects canonical skills into the run worktree in its native format; `project_all` records projections in `skill_projections` and `.ai/agents/projections.lock.yaml`, excludes them from git, and `SandboxManager.create` performs it for every run.

#### Scope
- In: `ClaudeSkillProjector`, `CodexSkillProjector`, `project_all`, lock file, `.git/info/exclude`, sandbox hook-in, `walk skills list`, `walk skills sync`, roundtrip test.
- Out: drift detection (E02-S07); MCP-served skills (deferred, ADR-0007).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/model_router/adapters/claude/projector.py` | create | `ClaudeSkillProjector` |
| `src/walk/model_router/adapters/codex/projector.py` | create | `CodexSkillProjector`, `AGENTS_MD_START`, `AGENTS_MD_END`, `INLINE_LIMIT_BYTES` |
| `src/walk/model_router/adapters/claude/adapter.py` | modify | `ClaudeAdapter.skill_projector` returns `ClaudeSkillProjector` |
| `src/walk/model_router/adapters/codex/adapter.py` | modify | `CodexAdapter.skill_projector` returns `CodexSkillProjector` |
| `src/walk/skills/service.py` | modify | `DefaultSkillRegistry.project_all` |
| `src/walk/skills/lockfile.py` | create | `ProjectionLock`, `LOCK_PATH` |
| `src/walk/skills/repository.py` | create | `SkillProjectionRepository` |
| `src/walk/runtime/sandbox.py` | modify | — (`DefaultSandboxManager.create` calls `project_all` with the run's adapter projector) |
| `src/walk/cli/cmd_skills.py` | create | `skills_list`, `skills_sync` |
| `src/walk/cli/app.py` | modify | register `skills` group |
| `tests/fakes/fake_model_adapter.py` | modify | `FakeSkillProjector` (writes `<worktree>/.walk/fake-skills/<name>.md`) |
| `tests/model_router/adapters/claude/test_projector.py` | create | — |
| `tests/model_router/adapters/codex/test_projector.py` | create | — |
| `tests/skills/test_projection_roundtrip.py` | create | — |
| `tests/skills/test_lockfile.py` | create | — |
| `tests/cli/test_cmd_skills.py` | create | — |

#### Interface contract
See INTERFACES.md §1.11 `SkillProjector.project`, `SkillRegistry.project_all`; DOMAIN-MODEL §4.6 `SkillProjection`.
```python
# codex/projector.py
AGENTS_MD_START = "<!-- walk:skills:start -->"
AGENTS_MD_END = "<!-- walk:skills:end -->"
INLINE_LIMIT_BYTES = 4096
class CodexSkillProjector:
    provider = "codex"
    def project(self, skill: Skill, worktree_path: str) -> SkillProjection: ...   # target_path = <worktree>/AGENTS.md (section) ; body > limit → also <worktree>/.walk/skills/<name>/SKILL.md
    def render_section(self, skills: list[Skill], worktree_path: str) -> str: ...  # full managed section text

# claude/projector.py
class ClaudeSkillProjector:
    provider = "claude"
    def project(self, skill: Skill, worktree_path: str) -> SkillProjection: ...   # target_path = <worktree>/.claude/skills/<name>/SKILL.md ; copies references/ scripts/

# src/walk/skills/lockfile.py
LOCK_PATH = "agents/projections.lock.yaml"
class ProjectionLock(WalkModel):
    projections: list[SkillProjection]
    @classmethod
    def load(cls, ai_root: Path) -> "ProjectionLock": ...
    def write(self, ai_root: Path) -> Path: ...
    def for_provider(self, provider: str) -> list[SkillProjection]: ...

# src/walk/skills/repository.py
class SkillProjectionRepository:
    def __init__(self, db: Database) -> None: ...
    async def upsert(self, uow: UnitOfWork, projections: list[SkillProjection]) -> None: ...
    async def list(self, provider: str | None = None) -> list[SkillProjection]: ...
```
CLI: `walk skills list [--json]` (name, version, scope, source, roles); `walk skills sync [--worktree PATH]` (projects all skills for every configured adapter into the given worktree, default repo root `.walk/projections/<provider>/`, and rewrites the lock file).

#### Behavior
1. `project()` is pure: it returns `SkillProjection` with `content_sha256` of the rendered content and `generated_from_sha256 = skill.content_sha256`; `project_all` performs the writes.
2. Claude target: `<worktree>/.claude/skills/<name>/SKILL.md` — rendered as the canonical front matter reduced to `name`, `description` plus the body verbatim; `references/` and `scripts/` copied if present.
3. Codex target: one managed section in `<worktree>/AGENTS.md` between the markers, containing for each skill `### <name> (v<version>)`, the description, and the body inline when `len(body.encode()) <= INLINE_LIMIT_BYTES`, otherwise the line `See .walk/skills/<name>/SKILL.md` and that file is written. Content outside the markers is preserved byte-for-byte; a missing `AGENTS.md` is created with only the section.
4. `project_all` writes atomically, appends every target (relative) path to `<worktree>/.git/info/exclude` once (worktrees: resolves the common git dir via `git rev-parse --git-path info/exclude` through `GitProvider`), upserts `skill_projections`, writes the lock file, and returns the projections.
5. Re-running `project_all` with unchanged skills produces identical files and identical hashes (determinism; no timestamps inside rendered content — `generated_at` lives only in the lock).
6. `DefaultSandboxManager.create` calls `project_all([adapter.skill_projector()], worktree, skills)` after `add_worktree` and before guard-hook installation; failure → `ConfigError` and the worktree is removed.
7. `walk skills sync` without a daemon runs in-process; with `--json` prints the lock content.
8. The `FakeSkillProjector` writes one file per skill so E01/E02 e2e tests can assert projection without real adapters.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a 1 KB skill When Claude `project` Then target under `.claude/skills/<name>/SKILL.md` and content starts with reduced front matter | `tests/model_router/adapters/claude/test_projector.py::test_claude_projection_target_and_content` |
| 2 | Given two skills, one 5 KB When Codex `render_section` Then small body inline, large one linked to `.walk/skills/<name>/SKILL.md` | `tests/model_router/adapters/codex/test_projector.py::test_codex_section_inlines_small_and_links_large` |
| 3 | Given existing `AGENTS.md` with user text When `project_all` Then text preserved and exactly one managed section | `tests/model_router/adapters/codex/test_projector.py::test_codex_preserves_content_outside_markers` |
| 4 | Given canonical skills When `project_all` twice Then identical file hashes and lock entries | `tests/skills/test_projection_roundtrip.py::test_projection_is_deterministic_for_both_providers` |
| 5 | Given `project_all` When reading `.git/info/exclude` Then every target path listed once | `tests/skills/test_projection_roundtrip.py::test_projection_targets_excluded_from_git` |
| 6 | Given lock written When `ProjectionLock.load` Then equals written model | `tests/skills/test_lockfile.py::test_lock_roundtrip` |
| 7 | Given a run with `FakeModelAdapter` When `SandboxManager.create` Then fake projection files exist in the worktree | `tests/skills/test_projection_roundtrip.py::test_sandbox_create_projects_skills` |
| 8 | Given projector raising When `SandboxManager.create` Then `ConfigError` and worktree removed | `tests/skills/test_projection_roundtrip.py::test_sandbox_create_removes_worktree_on_projection_failure` |
| 9 | Given bootstrapped repo When `walk skills list` Then five rows | `tests/cli/test_cmd_skills.py::test_skills_list_shows_builtins` |
| 10 | Given bootstrapped repo When `walk skills sync` Then lock file has entries for `claude` and `codex` | `tests/cli/test_cmd_skills.py::test_skills_sync_writes_lock_for_all_providers` |

#### Evidence required
- Quality gate output.
- Demo: `walk skills list`; `walk skills sync` → `projected 5 skills for 2 providers`; `cat .ai/agents/projections.lock.yaml | head`.

#### Notes
- ADR-0007 D-2; Invariant 11.
- `NEW NAME:` `ClaudeSkillProjector`, `CodexSkillProjector`, `AGENTS_MD_START/END`, `INLINE_LIMIT_BYTES`, `ProjectionLock`, `LOCK_PATH`, `SkillProjectionRepository`, `FakeSkillProjector`.
- Pitfall: in a linked worktree `.git` is a file; always resolve `info/exclude` through git, never by path concatenation.
- Commit subject: `feat: add provider skill projections and lock file (E02-S06)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S07 — Skill drift detection, `walk skills check-drift`, startup check

**Status:** TODO
**Type:** feat
**Requirements:** §28, §27, §137, §138
**Depends on:** E02-S06, E02-S02
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
`check_drift` reports missing, modified and orphaned projections against the lock; the CLI, startup step 3 and `walk doctor` use it; non-strict mode regenerates and logs a `CONTEXT_UPDATED` ledger event.

#### Scope
- In: `check_drift`, `walk skills check-drift [--strict]`, startup integration, doctor section.
- Out: `--fix` semantics in doctor (E02-S15 delegates to `skills sync`).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/skills/service.py` | modify | `DefaultSkillRegistry.check_drift`, `DefaultSkillRegistry.regenerate` |
| `src/walk/skills/drift.py` | create | `compute_drift` |
| `src/walk/cli/cmd_skills.py` | modify | `skills_check_drift` |
| `src/walk/cli/cmd_doctor.py` | modify | — (adds `skills` section from `check_drift`) |
| `src/walk/orchestrator/service.py` | modify | — (startup step 3: `check_drift`; strict per `KernelSettings.strict`) |
| `src/walk/cli/composition.py` | modify | `KernelSettings.strict: bool = False` |
| `tests/skills/test_drift.py` | create | — |
| `tests/cli/test_cmd_skills_drift.py` | create | — |

#### Interface contract
See INTERFACES.md §1.11 `SkillRegistry.check_drift`; DOMAIN-MODEL §4.6 `DriftReport`.
```python
# src/walk/skills/drift.py
def compute_drift(canonical: list[Skill], lock: list[SkillProjection], on_disk: Mapping[str, str | None]) -> DriftReport:
    """on_disk: target_path -> sha256 of current file content (None if absent).
    missing  = canonical skills with no lock entry for the provider, or lock entry whose file is absent;
    modified = lock entries whose on-disk sha != recorded content_sha256, or whose generated_from_sha256 != canonical sha;
    orphaned = lock entries (or managed-section skills) with no canonical skill.
    ok = all three lists empty."""

class DefaultSkillRegistry:
    async def check_drift(self, projectors: list[SkillProjector], worktree_path: str) -> DriftReport: ...
    async def regenerate(self, projectors: list[SkillProjector], worktree_path: str, report: DriftReport) -> list[SkillProjection]:
        """project_all for affected skills; ledger CONTEXT_UPDATED payload {'skills_drift': report}."""
```
CLI: `walk skills check-drift [--strict] [--worktree PATH]` → exit 0 when `ok`; with drift: `--strict` → exit 1 after printing the report; without → regenerate, print `regenerated N projections`, exit 0.

#### Behavior
1. For Codex, "on-disk sha" of a skill is the sha of its sub-section text inside the managed block (so a hand edit of one skill is attributed to that skill); for Claude it is the file sha.
2. A canonical skill whose `content_sha256` changed since the lock was written is reported `modified` (lock `generated_from_sha256` mismatch), distinguishing the reason in `DriftReport` messages? — `DriftReport` has no messages; the CLI prints `modified (canonical changed)` vs `modified (projection edited)` by re-deriving the cause; the model itself is unchanged.
3. `regenerate` rewrites only skills in `missing ∪ modified`, deletes orphaned Claude files and removes orphaned Codex sub-sections, then rewrites the lock.
4. Startup step 3 runs `check_drift` on the repo-level projection directory `.walk/projections/<provider>/`; drift with `strict=True` → `ConfigError` aborts startup; otherwise `regenerate` and continue.
5. `walk doctor` prints a `skills` section: `ok` or counts per category; drift does not change doctor's exit code (that is `--strict`, E02-S15).
6. `check_drift` never writes; `regenerate` is the only mutating path.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given lock and intact files When `compute_drift` Then `ok` | `tests/skills/test_drift.py::test_drift_ok_when_lock_matches_disk` |
| 2 | Given a Claude projection file edited When `compute_drift` Then skill in `modified` | `tests/skills/test_drift.py::test_drift_detects_edited_claude_projection` |
| 3 | Given one Codex sub-section edited When `compute_drift` Then only that skill in `modified` | `tests/skills/test_drift.py::test_drift_attributes_codex_edit_to_single_skill` |
| 4 | Given canonical skill changed after lock When `compute_drift` Then `modified` | `tests/skills/test_drift.py::test_drift_detects_canonical_change` |
| 5 | Given lock entry for removed skill When `compute_drift` Then `orphaned` | `tests/skills/test_drift.py::test_drift_detects_orphaned_projection` |
| 6 | Given new canonical skill without projection When `compute_drift` Then `missing` | `tests/skills/test_drift.py::test_drift_detects_missing_projection` |
| 7 | Given drift When `regenerate` Then files restored, lock rewritten, one `CONTEXT_UPDATED` ledger event | `tests/skills/test_drift.py::test_regenerate_restores_and_logs` |
| 8 | Given drift When `walk skills check-drift --strict` Then exit 1 and report printed | `tests/cli/test_cmd_skills_drift.py::test_check_drift_strict_exits_one` |
| 9 | Given drift When `walk skills check-drift` Then exit 0 and `regenerated` message | `tests/cli/test_cmd_skills_drift.py::test_check_drift_regenerates_by_default` |
| 10 | Given drift and `strict=True` When `DefaultOrchestrator.start()` Then `ConfigError` before `ON_PROJECT_START` | `tests/skills/test_drift.py::test_startup_strict_fails_on_drift` |

#### Evidence required
- Quality gate output.
- Demo: `walk skills sync && walk skills check-drift` → `ok`; edit `.walk/projections/claude/.claude/skills/git-hygiene/SKILL.md`; `walk skills check-drift --strict` → `modified: git-hygiene`, exit 1.

#### Notes
- ADR-0007 D-3; Invariant 11; ARCHITECTURE §3.4 step 3.
- `NEW NAME:` `compute_drift`, `DefaultSkillRegistry.regenerate`, `KernelSettings.strict`.
- Commit subject: `feat: add skill projection drift detection (E02-S07)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S08 — Builtin MUST hooks (ARCHITECTURE §4.1 table)

**Status:** TODO
**Type:** feat
**Requirements:** §32, §41, §22, §137
**Depends on:** E01-S07, E01-S28, E01-S16
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every MUST attachment of ARCHITECTURE §4.1 whose dependencies exist by E02 is registered as a `required=True` builtin hook with priority < 50, fires in its trigger path, and cannot be disabled by project configuration.

#### Scope
- In: `builtins.py`, `register_builtins()` body, wiring of hook callables to E01 services, exclusion table for later stories.
- Out: ledger writes (done at §4.3 write points, WBS.md §3.5); project hooks (E02-S09); attachments listed in the exclusion table.

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/hooks/builtins.py` | create | `BuiltinHookDeps`, `builtin_hooks`, `register_builtins` |
| `src/walk/hooks/service.py` | modify | `DefaultHookManager.register_builtins` delegates to `builtins.register_builtins(self, deps)` |
| `src/walk/hooks/__init__.py` | modify | re-export `BuiltinHookDeps` |
| `src/walk/cli/composition.py` | modify | — (builds `BuiltinHookDeps` and calls `register_builtins` after all services exist) |
| `tests/hooks/test_builtins.py` | create | — |
| `tests/hooks/test_builtins_required.py` | create | — |

#### Interface contract
```python
# src/walk/hooks/builtins.py
class BuiltinHookDeps(WalkModel):
    """Protocol-typed service handles the builtin hooks call (arbitrary_types_allowed)."""
    checkpoints: CheckpointManager
    memory: MemoryManager
    git: GitProvider
    executor: AgentExecutor
    budgets: BudgetManager
    permissions: PermissionManager
    telemetry: TelemetryManager

def builtin_hooks(deps: BuiltinHookDeps) -> list[tuple[Hook, Callable[[HookContext], Awaitable[None]]]]: ...
def register_builtins(manager: HookManager, deps: BuiltinHookDeps) -> None: ...
```
Registered MUST hooks (id → behaviour; all `required=True`, `kind="builtin"`, `fail_policy=FAIL_CLOSED`, priority as given):

| HookName | id | prio | Callable behaviour |
|---|---|---|---|
| `ON_PROJECT_START` | `builtin.memory_index` | 10 | `memory.rebuild_index()` (default attachment, but shipped `required=False`, prio 60) |
| `ON_PROJECT_PAUSE` | `builtin.pause_checkpoint_all` | 10 | `checkpoints.checkpoint(run, PAUSE)` for every `executor.running()` |
| `ON_PHASE_START` | `builtin.phase_baseline` | 10 | `memory.approve_artifact(PHASE_BASELINE manifest of phase scope ids + HEAD, actor KERNEL)` |
| `ON_TASK_START` | `builtin.ensure_branch` | 10 | `git.ensure_branch(item.branch or feat/<id>-<slug>, base=default_branch, idempotency_key=f"git.branch:{item.id}")` |
| `ON_TASK_COMPLETE` | `builtin.remaining_work_check` | 10 | reads feature/bug doc; if section `Remaining Work` non-empty and not `- none` → `telemetry.counter("remaining_work_nonempty")` and payload flag `remaining_work_present=True` (does not fail; §6.5 guard decides) |
| `ON_AGENT_START` | `builtin.freshness_check` | 10 | for each memory doc id in `ctx.payload["context_doc_ids"]`: `memory.assess_freshness`; non-CURRENT → `fire(ON_CONTEXT_STALE)` (E04-S04 adds flagging; here fires only) |
| `ON_AGENT_CHECKPOINT` | `builtin.wip_commit` | 10 | no-op guard asserting `ctx.payload["wip_commit_done"] is True` (the commit is made inside `CheckpointManager.checkpoint`; the hook fails closed if the invariant is violated) |
| `ON_AGENT_END` | `builtin.final_checkpoint` | 10 | `checkpoints.checkpoint(run, END)` |
| `ON_AGENT_HANDOFF` | `builtin.handoff_checkpoint_and_handover` | 10 | `checkpoints.checkpoint(run, HANDOFF, handover=ctx.payload["handover"])` (which writes the handover document) |
| `ON_MODEL_FALLBACK` | `builtin.fallback_chain` | 10 | `fire(ON_AGENT_HANDOFF, ctx)` |
| `ON_BUDGET_EXHAUSTED` | `builtin.budget_block` | 10 | `checkpoints.checkpoint(run, PAUSE)`; `executor.pause(run_id)` → state `BLOCKED_BUDGET` via executor API; `permissions.request_approval(kind="ESCALATION", approver=USER, …)` |
| `ON_PROTECTED_ACTION_REQUESTED` | `builtin.pause_for_approval` | 10 | `executor.pause(run_id)` → `PAUSED_FOR_APPROVAL` |
| `ON_TASK_CANCELLED` | `builtin.cancel_cleanup` | 10 | `executor.cancel(run_id, reason)`; sandbox removal is performed by executor |
| `ON_RECOVERY_RESUME` | `builtin.load_handover` | 10 | asserts `ctx.payload["handover_id"]` resolves via `memory.read_handover` |
| `ON_CONTEXT_UPDATED` | `builtin.index_update` | 10 | `memory.rebuild_index()` restricted to `ctx.payload["path"]` (index upsert for one doc) |

Deferred attachments (not registered here): `ON_STATE_TRANSITION → WorkProvider.transition` (E03-S03); `ON_TASK_BLOCKED → WorkProvider.transition + comment` (E03-S03); `ON_TASK_FAILED → escalation` (E03-S16); `ON_READY_FOR_QC → QC run with different model` (E03-S07); `ON_BUG_CREATED → WorkProvider.create + bug skeleton` (E03-S14/E04-S01); `ON_COMMIT/ON_PR_OPENED/ON_MERGED → relevant_files refresh` (E04-S04); `ON_BUILD_*`/`ON_TEST_RESULT → evidence` (E03-S11); `ON_CONTEXT_STALE → requires_verification` (E04-S04); `ON_DEBATE_*`, `ON_DECISION_RECORDED`, `ON_ESCALATION` (E04-S05/E05); `ON_PHASE_REVIEW_START/COMPLETE/GATE_DECISION` (E07); `ON_IMPROVEMENT_OBSERVATION` (E04-S13); `ON_EFFORT_CHANGE`, `ON_BUDGET_THRESHOLD`, `ON_TOOL_*` (ledger-only → write points, nothing to register).

#### Behavior
1. `register_builtins` registers every row above; calling it twice raises `ConfigError("builtin hooks already registered")`.
2. Each callable receives `HookContext` and reads only documented payload keys; a missing key raises `HookFailed` (FAIL_CLOSED) with the key name.
3. `builtin.pause_checkpoint_all` continues through all running runs even if one checkpoint fails, then raises `HookFailed` listing failed run ids.
4. `builtin.ensure_branch` passes the idempotency key from ARCHITECTURE §5.4 so repeated `ON_TASK_START` (REWORK) is a no-op.
5. `builtin.freshness_check` fires `ON_CONTEXT_STALE` once per non-CURRENT doc with payload `{doc_id, status, reason}`.
6. Hooks never write ledger events directly (WBS.md §3.5); `HookManager.fire` records `HOOK_EXECUTED`/`HOOK_FAILED`.
7. `HookManager.register(hook)` with `kind="project"` and `id` equal to a required builtin id, or `enabled=False` targeting a required id, raises `ConfigError` (enforced in E01-S07; re-tested here with the real builtin set).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a kernel with fakes When `register_builtins` Then `hooks_for(name)` contains each id in the table with `required=True` and priority < 50 | `tests/hooks/test_builtins.py::test_all_must_hooks_registered_required_low_priority` |
| 2 | Given registration done When `register_builtins` again Then `ConfigError` | `tests/hooks/test_builtins.py::test_register_builtins_twice_raises` |
| 3 | Given two running fake runs When `fire(ON_PROJECT_PAUSE)` Then two `PAUSE` checkpoints exist | `tests/hooks/test_builtins.py::test_project_pause_checkpoints_all_running_runs` |
| 4 | Given a story entering IMPLEMENTING When `fire(ON_TASK_START)` twice Then branch exists once and second call is a no-op | `tests/hooks/test_builtins.py::test_task_start_ensures_branch_idempotently` |
| 5 | Given a fallback When `fire(ON_MODEL_FALLBACK)` with handover payload Then a `HANDOFF` checkpoint and `HO-0001.md` exist | `tests/hooks/test_builtins.py::test_model_fallback_chains_handoff_checkpoint_and_handover` |
| 6 | Given `fire(ON_AGENT_HANDOFF)` without `handover` in payload Then `HookFailed` naming `handover` | `tests/hooks/test_builtins.py::test_handoff_without_handover_fails_closed` |
| 7 | Given budget hard limit When `fire(ON_BUDGET_EXHAUSTED)` Then run `BLOCKED_BUDGET`, `PAUSE` checkpoint, pending `ApprovalRequest(kind=ESCALATION)` | `tests/hooks/test_builtins.py::test_budget_exhausted_blocks_run_and_escalates` |
| 8 | Given a stale doc id When `fire(ON_AGENT_START)` Then one `ON_CONTEXT_STALE` execution recorded | `tests/hooks/test_builtins.py::test_agent_start_fires_context_stale_for_stale_docs` |
| 9 | Given project hook with id `builtin.final_checkpoint` and `enabled=False` When `register` Then `ConfigError` | `tests/hooks/test_builtins_required.py::test_project_cannot_disable_required_builtin` |
| 10 | Given `fire(ON_AGENT_END)` Then exactly one `END` checkpoint and no direct ledger write by the hook (ledger count unchanged except `HOOK_EXECUTED`, `CHECKPOINT_CREATED`) | `tests/hooks/test_builtins_required.py::test_hooks_do_not_duplicate_ledger_events` |

#### Evidence required
- Quality gate output.
- Demo: `walk run --once` on a bootstrapped repo then `walk ledger query --kind HOOK_EXECUTED --limit 5` → shows `builtin.memory_index` under `ON_PROJECT_START`.

#### Notes
- ARCHITECTURE §4.1 (table), §4.3; ADR-0009 D-7; WBS.md §3.5.
- `NEW NAME:` `BuiltinHookDeps`, `builtin_hooks`, builtin hook ids (`builtin.*`), payload keys `context_doc_ids`, `wip_commit_done`, `handover`, `handover_id`, `path`, `remaining_work_present`.
- Pitfall: `ON_MODEL_FALLBACK → ON_AGENT_HANDOFF` is a nested `fire`; ensure `HookManager.fire` is re-entrant (no shared mutable state).
- Commit subject: `feat: register builtin must hooks (E02-S08)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S09 — Project hooks from `.ai/agents/hooks.yaml`

**Status:** TODO
**Type:** feat
**Requirements:** §32, §24, §137
**Depends on:** E02-S08
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Projects declare additional hooks in `.ai/agents/hooks.yaml` as shell commands or allowlisted kernel actions; they run with timeouts and fail policies, receive the `HookContext` through `WALK_HOOK_*` environment variables, and can never replace or disable required builtins.

#### Scope
- In: YAML schema, `load_project_hooks`, shell execution, kernel-action dispatch, timeout handling, startup loading (ARCHITECTURE §3.4 step 3).
- Out: builtin hooks (E02-S08); improvement-related kernel actions (E10).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/hooks/project.py` | create | `ProjectHooksFile`, `ProjectHookSpec`, `KERNEL_ACTIONS`, `HOOK_ENV_PREFIX`, `hook_env` |
| `src/walk/hooks/service.py` | modify | `DefaultHookManager.load_project_hooks`, `DefaultHookManager.set_kernel_actions` |
| `src/walk/hooks/__init__.py` | modify | re-export `ProjectHooksFile` |
| `src/walk/cli/composition.py` | modify | — (loads project hooks after builtins; registers kernel actions) |
| `tests/hooks/test_project_hooks.py` | create | — |
| `tests/hooks/test_project_hooks_exec.py` | create | — |

#### Interface contract
See INTERFACES.md §1.11 `HookManager.load_project_hooks`, `HookManager.fire`; DOMAIN-MODEL §4.6 `Hook`.
```python
# src/walk/hooks/project.py
HOOK_ENV_PREFIX = "WALK_HOOK_"
KERNEL_ACTIONS: tuple[str, ...] = ("memory.rebuild_index", "skills.sync", "telemetry.counter")

class ProjectHookSpec(WalkModel):
    name: HookName
    id: str = Field(pattern=r"^project\.[a-z0-9-]+$")
    command: str | None = None
    kernel_action: str | None = None
    priority: int = Field(default=100, ge=50)
    fail_policy: HookFailPolicy = HookFailPolicy.LOG_AND_CONTINUE
    timeout_s: int = Field(default=120, ge=1, le=3600)
    enabled: bool = True
    # exactly one of command / kernel_action (model_validator)

class ProjectHooksFile(WalkModel):
    hooks: list[ProjectHookSpec] = Field(default_factory=list)
    @classmethod
    def load(cls, path: Path) -> "ProjectHooksFile": ...
    def to_hooks(self) -> list[Hook]: ...

def hook_env(ctx: HookContext, base_env: Mapping[str, str]) -> dict[str, str]:
    """base_env + WALK_HOOK_NAME, WALK_HOOK_PROJECT_KEY, WALK_HOOK_WORK_ITEM_ID, WALK_HOOK_RUN_ID, WALK_HOOK_PHASE_ID,
    WALK_HOOK_ROLE, WALK_HOOK_AT, WALK_HOOK_PAYLOAD (JSON)."""

class DefaultHookManager:
    def set_kernel_actions(self, actions: Mapping[str, Callable[[HookContext], Awaitable[None]]]) -> None: ...
```

#### Behavior
1. `load_project_hooks(path)` returns `[]` when the file is absent; invalid YAML or schema → `ConfigError` with the offending hook `id`.
2. `priority < 50` or `id` not starting with `project.` → validation error → `ConfigError` (project hooks always run after builtins).
3. `kernel_action` not in `KERNEL_ACTIONS` → `ConfigError("unknown kernel action")`.
4. Shell hooks run through `SubprocessRunner` with `cwd = repo root`, env from `hook_env(ctx, scrubbed_env(os.environ))` (no secrets), `timeout_s`; exit 0 → `OK`; non-zero → `FAILED` (message = last stderr line); timeout → `TIMEOUT`.
5. `FAIL_CLOSED` project hooks raise `HookFailed` after recording; `LOG_AND_CONTINUE` record and continue (E01-S07 semantics confirmed with project hooks).
6. `enabled: false` disables a project hook; targeting a builtin id is rejected (E02-S08 rule 7).
7. `telemetry.counter` action increments counter `hook.<id>`; `memory.rebuild_index` and `skills.sync` call the respective services.
8. Composition loads `.ai/agents/hooks.yaml` after `register_builtins`; registration order does not affect execution order (priority sort).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given valid `hooks.yaml` with one command hook When `load_project_hooks` Then one `Hook(kind="project")` | `tests/hooks/test_project_hooks.py::test_load_valid_file` |
| 2 | Given missing file When `load_project_hooks` Then `[]` | `tests/hooks/test_project_hooks.py::test_load_missing_file_returns_empty` |
| 3 | Given hook with both `command` and `kernel_action` When load Then `ConfigError` | `tests/hooks/test_project_hooks.py::test_load_rejects_command_and_action_together` |
| 4 | Given `priority: 10` When load Then `ConfigError` | `tests/hooks/test_project_hooks.py::test_load_rejects_priority_below_fifty` |
| 5 | Given `kernel_action: foo.bar` When load Then `ConfigError` | `tests/hooks/test_project_hooks.py::test_load_rejects_unknown_kernel_action` |
| 6 | Given command hook and fake runner exit 0 When `fire` Then result `OK` and env contains `WALK_HOOK_NAME` and no `JIRA_API_TOKEN` | `tests/hooks/test_project_hooks_exec.py::test_command_hook_runs_with_context_env` |
| 7 | Given command hook exceeding timeout When `fire` Then `TIMEOUT` and `HOOK_FAILED` ledger | `tests/hooks/test_project_hooks_exec.py::test_command_hook_timeout` |
| 8 | Given `fail_policy: fail_closed` and exit 1 When `fire` Then `HookFailed` | `tests/hooks/test_project_hooks_exec.py::test_fail_closed_project_hook_raises` |
| 9 | Given `kernel_action: telemetry.counter` When `fire` Then counter `hook.project.x` incremented | `tests/hooks/test_project_hooks_exec.py::test_kernel_action_counter` |

#### Evidence required
- Quality gate output.
- Demo: add `hooks: [{name: on_project_start, id: project.echo, command: "echo hello"}]`; `walk run --once`; `walk ledger query --kind HOOK_EXECUTED` shows `project.echo`.

#### Notes
- ADR-0009 D-7; ARCHITECTURE §4.1 failure policy paragraph.
- `NEW NAME:` `ProjectHooksFile`, `ProjectHookSpec`, `KERNEL_ACTIONS`, `HOOK_ENV_PREFIX`, `hook_env`, `set_kernel_actions`.
- Commit subject: `feat: load project hooks from hooks.yaml (E02-S09)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S10 — Permission defaults, `permissions.yaml` loader, protected actions

**Status:** TODO
**Type:** feat
**Requirements:** §31, §92, §91, §63, §137
**Depends on:** E01-S15, E02-S03
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The kernel ships the ADR-0006 D-6 rule set in `defaults.yaml`; projects may only narrow it through `.ai/agents/permissions.yaml`; protected actions always evaluate to `REQUIRE_APPROVAL(approver=USER)` and cannot be downgraded.

#### Scope
- In: defaults file, loader + narrowing merge, `ProtectedAction` defaults, `decide()` protected-action branch, default command patterns.
- Out: approval lifecycle (E02-S11); worktree path checks and guard hooks (E02-S14).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/permissions/defaults.yaml` | create | — |
| `src/walk/permissions/loader.py` | create | `PermissionsFile`, `load_defaults`, `load_project_rules`, `merge_narrowing`, `DEFAULT_PROTECTED_ACTIONS` |
| `src/walk/permissions/service.py` | modify | `DefaultPermissionManager.__init__(rules, protected_actions, …)`, protected-action branch in `decide` |
| `src/walk/permissions/__init__.py` | modify | re-export loader symbols |
| `src/walk/cli/composition.py` | modify | — (loads defaults + project file) |
| `tests/permissions/test_loader.py` | create | — |
| `tests/permissions/test_defaults_rules.py` | create | — |
| `tests/permissions/test_protected_actions.py` | create | — |

#### Interface contract
See INTERFACES.md §1.10 `PermissionManager`; DOMAIN-MODEL §4.5 `PermissionRule`, `ProtectedAction`.
```python
# src/walk/permissions/loader.py
class PermissionsFile(WalkModel):
    rules: list[PermissionRule] = Field(default_factory=list)
    protected_actions: list[ProtectedAction] = Field(default_factory=list)   # project may ADD, never remove

DEFAULT_PROTECTED_ACTIONS: tuple[str, ...] = ("git.merge_protected", "git.delete_branch_protected", "repo.delete_data",
    "store.publish", "credentials.change", "monetization.change", "jira.delete", "permissions.alter")

def load_defaults() -> PermissionsFile: ...                       # package resource defaults.yaml
def load_project_rules(path: Path) -> PermissionsFile: ...        # [] when absent
def merge_narrowing(defaults: PermissionsFile, project: PermissionsFile) -> PermissionsFile:
    """Project rule with effect DENY/REQUIRE_APPROVAL: added. Project rule with effect ALLOW: accepted only if an identical
    (role, tool) ALLOW exists in defaults (acts as a restatement, may remove command/path patterns = narrowing) — otherwise ConfigError.
    Project protected_actions appended; any default protected action missing from the merged list → ConfigError."""
```
`defaults.yaml` rows (effect per role; `*` = all roles):

| role | tool | effect | notes |
|---|---|---|---|
| SENIOR_DEV | `Read`,`Edit`,`Write`,`Glob`,`Grep` | ALLOW | `path_patterns: ["**"]` (worktree-relative) |
| SENIOR_DEV | `bash` | ALLOW | `command_patterns`: `^(dotnet|unity|Unity|graphify|git (status|diff|log|add|stash)|pytest|npm test|ls|cat|rg|grep|find)\b` |
| SENIOR_DEV | `git.commit` | ALLOW | kernel executes |
| SENIOR_DEV | `git.merge_protected`,`git.push_protected`,`jira.close_feature`,`review.approve`,`review.reject`,`qc.*` | DENY | |
| LEAD_DEV | as SENIOR_DEV ALLOW rows + `review.approve`,`review.reject`,`jira.create_task` | ALLOW | |
| LEAD_DEV | `jira.close_feature` | DENY | QC only |
| LEAD_DEV | `git.merge_protected` | REQUIRE_APPROVAL | approver USER |
| QC | `Read`,`Glob`,`Grep` | ALLOW | |
| QC | `bash` | ALLOW | test/run patterns only: `^(dotnet test|unity|Unity|pytest|npm test|ls|cat|rg|grep|find)\b` |
| QC | `jira.create_bug`,`jira.reopen`,`qc.approve`,`qc.reject` | ALLOW | |
| QC | `Edit`,`Write`,`git.commit` | DENY | QC does not fix code |
| ORCHESTRATOR | `jira.create_*`,`jira.transition`,`work.plan`,`Read`,`Glob`,`Grep` | ALLOW | |
| ORCHESTRATOR | `Edit`,`Write`,`bash` | DENY | |
| PRODUCT_OWNER, DESIGN_LEADER, ART_DIRECTOR | `Read`,`Glob`,`Grep`,`decision.propose` | ALLOW | |
| same | `Edit`,`Write`,`bash` | DENY | |
| `*` | `bash` | DENY | `command_patterns`: `rm\s+-rf\s+/`, `git\s+push\s+.*--force`, `\bcurl\b`, `\bwget\b`, `^(pip|uv|npm|dotnet)\s+(install|add)\b`, `git\s+merge\b` |
| `*` | each `DEFAULT_PROTECTED_ACTIONS` entry | REQUIRE_APPROVAL | approver USER |

#### Behavior
1. `load_defaults()` validates the shipped file at import of the service; a malformed default is a packaging error surfaced as `ConfigError` at startup.
2. `merge_narrowing` applies the rules in its docstring; the result is de-duplicated on `(role, tool, effect, command_patterns, path_patterns)`.
3. `decide()` first checks `request.tool` (or `ToolSpec.protected_action` resolved by the caller into `request.tool`) against protected actions → `REQUIRE_APPROVAL(approver=action.approver, reason="protected action")` regardless of any ALLOW rule; then applies E01-S15 specificity/DENY-wins evaluation.
4. A project rule attempting `effect: ALLOW` for a protected action → `ConfigError("protected action cannot be downgraded")`.
5. Bash `DENY` patterns for `*` apply to every role in addition to role ALLOW patterns (DENY wins, ADR-0006 D-3).
6. Role-specific ALLOW for `bash` without a matching ALLOW pattern → DENY with reason `command not allowlisted`.
7. `rules_for(role, extra)` (E01-S15) now receives the merged file; `extra` (constitution `tool_permissions`) is merged with the same narrowing function.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given shipped defaults When `load_defaults` Then validates and contains a rule for every (role, tool) row above | `tests/permissions/test_loader.py::test_defaults_file_loads_and_covers_table` |
| 2 | Given project rule `SENIOR_DEV bash DENY ^npm` When `merge_narrowing` Then rule present in result | `tests/permissions/test_loader.py::test_project_can_add_deny` |
| 3 | Given project rule `QC Edit ALLOW` When `merge_narrowing` Then `ConfigError` | `tests/permissions/test_loader.py::test_project_cannot_widen_with_new_allow` |
| 4 | Given project file omitting `store.publish` from protected actions When merge Then `ConfigError` | `tests/permissions/test_loader.py::test_default_protected_actions_cannot_be_removed` |
| 5 | Given SENIOR_DEV `git.commit` When `decide` Then ALLOW | `tests/permissions/test_defaults_rules.py::test_senior_dev_may_commit` |
| 6 | Given SENIOR_DEV `review.approve` When `decide` Then DENY | `tests/permissions/test_defaults_rules.py::test_senior_dev_cannot_approve_review` |
| 7 | Given QC `Edit` When `decide` Then DENY; QC `jira.create_bug` ALLOW | `tests/permissions/test_defaults_rules.py::test_qc_read_only_but_may_create_bug` |
| 8 | Given LEAD_DEV `bash` `git push --force origin main` When `decide` Then DENY (global pattern) | `tests/permissions/test_defaults_rules.py::test_force_push_denied_for_all_roles` |
| 9 | Given SENIOR_DEV `bash` `curl http://x` When `decide` Then DENY; `dotnet test` ALLOW | `tests/permissions/test_defaults_rules.py::test_bash_command_patterns` |
| 10 | Given LEAD_DEV `git.merge_protected` When `decide` Then `REQUIRE_APPROVAL` with approver USER even with a project ALLOW attempt rejected at load | `tests/permissions/test_protected_actions.py::test_protected_action_requires_user_approval` |
| 11 | Given project adds protected action `analytics.purge` When ORCHESTRATOR requests it Then `REQUIRE_APPROVAL` | `tests/permissions/test_protected_actions.py::test_project_added_protected_action` |

#### Evidence required
- Quality gate output.
- Demo: `cat .ai/agents/permissions.yaml | head -20` after bootstrap shows the copied defaults header.

#### Notes
- ADR-0006 D-3, D-6; ADR-0013 D-4; ARCHITECTURE §6 (protected actions list).
- `NEW NAME:` `PermissionsFile`, `load_defaults`, `load_project_rules`, `merge_narrowing`, `DEFAULT_PROTECTED_ACTIONS`, tool names `decision.propose`, `work.plan`, `qc.*`.
- Commit subject: `feat: add default permission rules and protected actions (E02-S10)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S11 — Approval requests and `walk approve/deny/approvals`

**Status:** TODO
**Type:** feat
**Requirements:** §92, §31, §51, §93, §137
**Depends on:** E02-S10, E01-S26
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A `REQUIRE_APPROVAL` decision creates a persisted `ApprovalRequest`, pauses the run with a `PAUSE` checkpoint, and `walk approve|deny` resolves it and wakes the waiting tool invocation; unanswered requests expire to DENY.

#### Scope
- In: full `request_approval/decide_approval/pending`, `EventApprovalWaiter` (event-driven implementation of the `ApprovalWaiter` protocol from E01-S26) in runtime, expiry, CLI (in-process and via `CommandClient`), `ON_PROTECTED_ACTION_REQUESTED` payload.
- Out: escalation-kind approvals routing (E05-S02); artifact-change approvals content (E02-S12 uses this API).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/permissions/service.py` | modify | `DefaultPermissionManager.request_approval/decide_approval/pending/expire_due` |
| `src/walk/permissions/repository.py` | modify | `ApprovalRequestRepository.list_pending`, `expire_before` |
| `src/walk/runtime/approvals.py` | create | `EventApprovalWaiter` (implements `walk.runtime.tool_invoker.ApprovalWaiter`; replaces `PollingApprovalWaiter` in the composition root) |
| `src/walk/runtime/tool_invoker.py` | modify | — (`authorize` awaits `ApprovalWaiter.wait(approval_id, timeout)`) |
| `src/walk/orchestrator/commands.py` | modify | — (`approve`, `deny` commands) |
| `src/walk/orchestrator/service.py` | modify | — (`Scheduler.tick` calls `expire_due`) |
| `src/walk/cli/cmd_approvals.py` | create | `approve`, `deny`, `approvals` |
| `src/walk/cli/app.py` | modify | register commands |
| `src/walk/agents/defaults/policies.yaml` | modify | — (`approval_timeout_s: 86400` kernel default) |
| `tests/permissions/test_approvals.py` | create | — |
| `tests/runtime/test_approval_waiter.py` | create | — |
| `tests/cli/test_cmd_approvals.py` | create | — |

#### Interface contract
See INTERFACES.md §1.10 `PermissionManager.request_approval/decide_approval/pending`; DOMAIN-MODEL §4.5 `ApprovalRequest`.
```python
# src/walk/permissions/service.py (deltas)
class DefaultPermissionManager:
    async def expire_due(self, now: datetime) -> list[ApprovalRequest]:
        """PENDING with expires_at <= now → EXPIRED; ledger APPROVAL_DECIDED outcome=DENIED payload {'reason': 'expired'}."""

# src/walk/runtime/approvals.py
class EventApprovalWaiter:  # implements ApprovalWaiter protocol (E01-S26)
    """In-process registry of asyncio.Events keyed by ApprovalRequestId; resolved by decide_approval through a callback."""
    def register(self, approval_id: ApprovalRequestId) -> None: ...
    async def wait(self, approval_id: ApprovalRequestId, timeout_s: int) -> ApprovalState:
        """Returns APPROVED/DENIED/EXPIRED; timeout → EXPIRED (and the request is expired in the DB)."""
    def resolve(self, approval_id: ApprovalRequestId, state: ApprovalState) -> None: ...
```
CLI: `walk approve APV_ID [--note TEXT]`, `walk deny APV_ID [--note TEXT]`, `walk approvals [--pending] [--json]`.

#### Behavior
1. `request_approval` allocates `APV-NNNN` via `IdSequenceStore`, sets `expires_at = requested_at + approval_timeout_s`, persists PENDING, writes `APPROVAL_REQUESTED`, fires `ON_PROTECTED_ACTION_REQUESTED` (payload `{approval_id, tool, run_id}`) — whose builtin (E02-S08) pauses the run; then `ToolInvoker.authorize` creates a `PAUSE` checkpoint and awaits `ApprovalWaiter.wait`.
2. `decide_approval(id, approve, by, note)`: PENDING → APPROVED/DENIED, `decided_at`, `decided_by`, ledger `APPROVAL_DECIDED` (`outcome` OK/DENIED, actor `USER`), then `EventApprovalWaiter.resolve`; run state returns to `RUNNING` through `executor.resume(run_id)`; a non-PENDING request → `PermanentError("approval already decided")`.
3. APPROVED → `authorize` returns `PermissionDecision(effect=ALLOW, approval_request_id=id)`; DENIED/EXPIRED → `DENY` + `TOOL_DENIED` ledger + `ON_TOOL_DENIED`.
4. `expire_due` runs every scheduler tick and on `wait` timeout; expiry is idempotent.
5. After a kernel restart the waiter registry is empty: `RecoveryManager` (E01-S28) re-registers waiters for runs in `PAUSED_FOR_APPROVAL` with PENDING requests and re-enters `wait`; APPROVED-while-down requests resume immediately.
6. CLI: when a daemon lock is held, `approve/deny` go through `CommandClient` (`commands.name = "approve"`), else in-process (DB write + waiter not needed). `approvals --pending` reads the DB directly.
7. Exit codes: unknown id → 1; already decided → 2.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a fake run requesting `git.merge_protected` When tool call authorised Then `ApprovalRequest` PENDING persisted, run `PAUSED_FOR_APPROVAL`, `PAUSE` checkpoint, `APPROVAL_REQUESTED` ledger | `tests/permissions/test_approvals.py::test_require_approval_pauses_run_and_persists_request` |
| 2 | Given pending request When `decide_approval(approve=True)` Then `authorize` returns ALLOW with `approval_request_id` and run `RUNNING` | `tests/permissions/test_approvals.py::test_approve_resumes_run_with_allow` |
| 3 | Given pending request When `decide_approval(approve=False)` Then DENY, `TOOL_DENIED` ledger | `tests/permissions/test_approvals.py::test_deny_results_in_tool_denied` |
| 4 | Given decided request When `decide_approval` again Then `PermanentError` | `tests/permissions/test_approvals.py::test_decide_twice_raises` |
| 5 | Given request with `expires_at` in the past When `expire_due(now)` Then EXPIRED and `APPROVAL_DECIDED` outcome DENIED | `tests/permissions/test_approvals.py::test_expire_due_marks_expired` |
| 6 | Given waiter and `FakeClock` When `wait` times out Then returns EXPIRED | `tests/runtime/test_approval_waiter.py::test_wait_timeout_returns_expired` |
| 7 | Given run paused for approval, kernel restarted, request approved meanwhile When recovery runs Then run resumes without new request | `tests/runtime/test_approval_waiter.py::test_recovery_reregisters_and_resumes_approved` |
| 8 | Given pending request When `walk approve APV-0001 --note ok` Then exit 0 and state APPROVED | `tests/cli/test_cmd_approvals.py::test_approve_command` |
| 9 | Given unknown id When `walk deny APV-9999` Then exit 1 | `tests/cli/test_cmd_approvals.py::test_deny_unknown_exits_one` |
| 10 | Given two pending, one decided When `walk approvals --pending --json` Then two entries | `tests/cli/test_cmd_approvals.py::test_approvals_pending_lists_only_pending` |

#### Evidence required
- Quality gate output.
- Demo: in e2e transcript — `walk approvals --pending` showing `APV-0001 PROTECTED_ACTION git.merge_protected`, then `walk approve APV-0001 --note "ok"` → `APV-0001 APPROVED`.

#### Notes
- ADR-0006 D-4, D-7; ARCHITECTURE §6 protected actions paragraph.
- `NEW NAME:` `EventApprovalWaiter` (the `ApprovalWaiter` protocol itself is defined by E01-S26), `expire_due`, `approval_timeout_s` policy key, command names `approve`/`deny` in `CommandConsumer`.
- Pitfall: `wait` must not hold a DB connection; poll the DB on wake-up to tolerate decisions made in-process by the CLI while the daemon is running.
- Commit subject: `feat: add approval request lifecycle and approve commands (E02-S11)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S12 — Approved artifact registry and `walk artifacts`

**Status:** TODO
**Type:** feat
**Requirements:** §33, §24, §137, §139
**Depends on:** E02-S10, E01-S16
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Approved artifacts are first-class: `MemoryManager.approve_artifact` writes `.ai/approved/APR-NNNN.md` plus a hashed payload folder, writes under `approved/` without a change decision are refused, startup/doctor verify hashes and flag drift as `INVALID`, and `walk artifacts` lists/approves/verifies.

#### Scope
- In: `approve_artifact`, `verify_approved_artifacts`, `ApprovedArtifactRepository`, `write()` guard for `approved/`, CLI group, startup step integration.
- Out: `ApprovedArtifact` as context items (E04-S08); `PHASE_BASELINE` creation (E02-S08 hook calls this API; E07-S02 fills content); change-request workflow via decisions (E05).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/memory/approved.py` | create | `hash_payload`, `approved_doc`, `APPROVED_DIR` |
| `src/walk/memory/repository.py` | modify | `ApprovedArtifactRepository` |
| `src/walk/memory/service.py` | modify | `DefaultMemoryManager.approve_artifact/verify_approved_artifacts`, `write` guard |
| `src/walk/memory/errors.py` | modify | `ApprovedArtifactDrift`, `ApprovalNotAuthorized` |
| `src/walk/orchestrator/service.py` | modify | — (startup step 3: `verify_approved_artifacts`) |
| `src/walk/cli/cmd_doctor.py` | modify | — (`approved` section) |
| `src/walk/cli/cmd_artifacts.py` | create | `artifacts_list`, `artifacts_approve`, `artifacts_verify` |
| `src/walk/cli/app.py` | modify | register `artifacts` group |
| `tests/memory/test_approved.py` | create | — |
| `tests/memory/test_approved_write_guard.py` | create | — |
| `tests/cli/test_cmd_artifacts.py` | create | — |

#### Interface contract
See INTERFACES.md §1.8 `MemoryManager.approve_artifact`, `verify_approved_artifacts`, `write`; DOMAIN-MODEL §4.7 `ApprovedArtifact`.
```python
# src/walk/memory/approved.py
APPROVED_DIR = "approved"
def hash_payload(root: Path, payload_paths: list[str]) -> str:
    """SHA-256 over sorted (relative path, file bytes) pairs; raises ConfigError if a path is missing."""
def approved_doc(artifact: ApprovedArtifact, actor: Actor, now: datetime) -> MemoryDocument:
    """type=approved, id=artifact.id, sections: Summary, Scope, Related Requirements, Payload, Change History;
    front_matter.extra = {kind, scope, approved_by, content_sha256, supersedes, change_request_decision}."""

class ApprovedArtifactRepository:
    async def upsert(self, uow: UnitOfWork, artifact: ApprovedArtifact) -> None: ...
    async def get(self, artifact_id: ApprovedArtifactId) -> ApprovedArtifact: ...
    async def list(self, *, status: ApprovalStatus | None = None, scope: str | None = None) -> list[ApprovedArtifact]: ...
```
CLI: `walk artifacts list [--json]`; `walk artifacts approve PATH... --kind KIND --title TITLE --scope SCOPE [--supersedes APR_ID]` (actor USER; copies payload files into `.ai/approved/APR-NNNN/`); `walk artifacts verify` (exit 0 ok / 2 drift).

#### Behavior
1. `approve_artifact(artifact, actor)`: authority check — `actor.role == USER`, or `Constitution(actor.role).authority.may_approve` contains `artifact.kind.value`; otherwise `ApprovalNotAuthorized(PermissionDenied)`.
2. The id `APR-NNNN` is allocated if `artifact.id` is a placeholder (`APR-0000`); payload files are copied into `.ai/approved/<id>/`, `content_sha256 = hash_payload`, `status = APPROVED`, `version` = previous version + 1 when `supersedes` is set (and the superseded row becomes `SUPERSEDED`), else 1.
3. The metadata document is written through `write()` with an internal bypass token for the `approved/` guard (`_approved_write=True` keyword only usable by `approve_artifact`); ledger `ARTIFACT_APPROVED` payload `{id, kind, sha}`.
4. `write(doc)` for any path under `approved/` from any other caller is refused with `PermissionDenied("approved artifacts change only through approve_artifact")` unless `doc.front_matter.extra["change_request_decision"]` is a `DecisionId` that exists (E04-S05 provides lookup; until then any syntactically valid id is accepted and a WARNING is logged).
5. `verify_approved_artifacts()` recomputes hashes for all `APPROVED` artifacts; mismatch or missing payload → `memory_index.freshness_status = INVALID` for the metadata doc, `ON_CONTEXT_STALE` fired with `{doc_id, status: INVALID, reason: "approved artifact drift"}`, returns the drifted ids. Status in `approved_artifacts` is unchanged (re-approval restores).
6. Startup step 3 calls `verify_approved_artifacts`; drift never aborts startup but is printed by `walk doctor` under `approved`.
7. `BoundaryAuditor` forbidden path `.ai/approved/**` is confirmed in E02-S14.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given USER actor and two payload files When `approve_artifact` Then `APR-0001.md` + `APR-0001/` exist, row APPROVED, sha equals `hash_payload`, `ARTIFACT_APPROVED` ledger | `tests/memory/test_approved.py::test_approve_writes_doc_payload_row_and_ledger` |
| 2 | Given SENIOR_DEV actor When `approve_artifact(kind=ART_DIRECTION)` Then `ApprovalNotAuthorized` | `tests/memory/test_approved.py::test_approve_requires_authority` |
| 3 | Given LEAD_DEV actor whose `may_approve` includes `ARCHITECTURE_DIRECTION` When approve that kind Then APPROVED | `tests/memory/test_approved.py::test_role_with_may_approve_can_approve_kind` |
| 4 | Given `supersedes=APR-0001` When approve Then new version 2 and APR-0001 `SUPERSEDED` | `tests/memory/test_approved.py::test_supersede_bumps_version_and_marks_previous` |
| 5 | Given payload path missing When `hash_payload` Then `ConfigError` | `tests/memory/test_approved.py::test_hash_payload_missing_file_raises` |
| 6 | Given a doc path under `approved/` When `write` without change decision Then `PermissionDenied` | `tests/memory/test_approved_write_guard.py::test_write_under_approved_refused_without_decision` |
| 7 | Given a payload file modified on disk When `verify_approved_artifacts` Then id returned, index INVALID, `ON_CONTEXT_STALE` fired | `tests/memory/test_approved.py::test_verify_detects_payload_drift` |
| 8 | Given intact artifacts When `verify_approved_artifacts` Then `[]` | `tests/memory/test_approved.py::test_verify_clean_returns_empty` |
| 9 | Given files When `walk artifacts approve a.png --kind UI_CONCEPT --title X --scope FEAT-0001` Then exit 0 and `walk artifacts list` shows APR-0001 | `tests/cli/test_cmd_artifacts.py::test_artifacts_approve_and_list` |
| 10 | Given drift When `walk artifacts verify` Then exit 2 listing the id | `tests/cli/test_cmd_artifacts.py::test_artifacts_verify_exit_two_on_drift` |

#### Evidence required
- Quality gate output.
- Demo: `walk artifacts approve GDD/concept.png --kind GAMEPLAY_CONCEPT --title "Core loop" --scope project` → `APR-0001 approved (sha …)`; `walk artifacts verify` → `ok`.

#### Notes
- ADR-0003 D-4, D-5; Invariant 10; ARCHITECTURE §7 row 10.
- `NEW NAME:` `walk artifacts` group (WBS §6), `hash_payload`, `approved_doc`, `APPROVED_DIR`, `ApprovedArtifactRepository`, `ApprovedArtifactDrift`, `ApprovalNotAuthorized`, `_approved_write` internal flag.
- Commit subject: `feat: add approved artifact registry and artifacts commands (E02-S12)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S13 — Human override CLI subset

**Status:** TODO
**Type:** feat
**Requirements:** §93, §6.12, §137
**Depends on:** E01-S30, E02-S11
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The user can pause/resume the project or one agent, cancel a work item, change priority, change a role's model policy and the project autonomy level from the CLI; every action is recorded as `USER_OVERRIDE` and routed through the daemon when it is running.

#### Scope
- In: `walk pause/resume [--agent]`, `walk work cancel`, `walk work priority`, `walk policy set-model`, `walk policy set-autonomy`, `CommandConsumer` handlers, hooks `ON_PROJECT_PAUSE/RESUME`, `ON_TASK_CANCELLED`.
- Out: `walk work force-review` (E03-S16); `walk phase stop` (E07-S05); `walk decisions override` (E05-S09).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/service.py` | modify | `DefaultOrchestrator.pause/resume/cancel_work_item/set_priority/set_autonomy` |
| `src/walk/orchestrator/commands.py` | modify | — (handlers `pause`, `resume`, `work.cancel`, `work.priority`, `policy.set_model`, `policy.set_autonomy`) |
| `src/walk/agents/policy_file.py` | create | `PoliciesFile`, `update_model_policy` |
| `src/walk/workflow/repository.py` | modify | `WorkflowRepository.set_priority`, `ProjectRepository.set_autonomy_level_max`, `ProjectRepository.set_paused` |
| `src/walk/cli/cmd_run.py` | modify | `pause`, `resume` |
| `src/walk/cli/cmd_work.py` | modify | `work_cancel`, `work_priority` |
| `src/walk/cli/cmd_policy.py` | create | `policy_set_model`, `policy_set_autonomy` |
| `src/walk/cli/app.py` | modify | register commands |
| `tests/orchestrator/test_overrides.py` | create | — |
| `tests/agents/test_policy_file.py` | create | — |
| `tests/cli/test_cmd_overrides.py` | create | — |

#### Interface contract
See INTERFACES.md §1.1 `Orchestrator.pause/resume/cancel_work_item`. Deltas:
```python
class DefaultOrchestrator:
    async def set_priority(self, work_item_id: WorkItemId, priority: Priority, *, actor: str) -> WorkItem: ...
    async def set_autonomy(self, level: AutonomyLevel, *, actor: str) -> Project: ...

# src/walk/agents/policy_file.py
class PoliciesFile(WalkModel):
    roles: dict[AgentRole, RuntimePolicy]
    @classmethod
    def load(cls, path: Path) -> "PoliciesFile": ...
    def write(self, path: Path) -> Path: ...
def update_model_policy(path: Path, role: AgentRole, preferred: list[ModelId], fallback: list[ModelId]) -> RuntimePolicy: ...
```
CLI (INTERFACES §6): `walk pause [--agent RUN_ID]`, `walk resume [--agent RUN_ID]`, `walk work cancel ID --reason TEXT`, `walk work priority ID P0|P1|P2|P3`, `walk policy set-model ROLE --preferred M... [--fallback M...]`, `walk policy set-autonomy 0|1|2|3`.

#### Behavior
1. `pause()` without run: `projects.paused = 1`, fire `ON_PROJECT_PAUSE` (builtin checkpoints all runs), each running run → `PAUSED_BY_USER`; `resume()` clears the flag, fires `ON_PROJECT_RESUME`, re-queues paused runs via the scheduler (idempotency key with incremented `state_version` is not needed — the run resumes natively or via handover per E01-S28).
2. `pause(run_id)`: `PAUSE` checkpoint, run `PAUSED_BY_USER`; `resume(run_id)` → `AgentExecutor.resume_native(latest checkpoint)`; unknown run → exit 1.
3. `cancel_work_item(id, reason)`: raise workflow event `cancel` as USER (guards apply: COMPLETE/CANCELLED items → `GuardRejected`, exit 2), fire `ON_TASK_CANCELLED` (builtin cancels the run; executor removes the worktree keeping the branch).
4. `set_priority`: updates `work_items.priority` + json; next tick re-sorts. `set_autonomy`: updates `Project.autonomy_level_max`.
5. `set-model`: validates every model id exists and is enabled in the `CapabilityRegistry`, rewrites `.ai/agents/policies.yaml` for that role only (other roles byte-identical), effective on the next scheduled run.
6. Every command writes `USER_OVERRIDE` with payload `{"command": "<name>", "args": {...}}`, `actor_role = USER` (write point `orchestrator`, ARCHITECTURE §4.3).
7. With a daemon running, commands go through `CommandClient` and the consumer executes rules 1–6; without a daemon, `pause/resume --agent` exit 3 (daemon required), all others run in-process.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given two running fake runs When `pause()` Then project paused, both `PAUSED_BY_USER`, two `PAUSE` checkpoints, one `USER_OVERRIDE` | `tests/orchestrator/test_overrides.py::test_pause_project_checkpoints_and_pauses_runs` |
| 2 | Given paused project When `resume()` Then flag cleared and next `tick` restarts runs | `tests/orchestrator/test_overrides.py::test_resume_project_restarts_runs` |
| 3 | Given one run When `pause(run_id)`/`resume(run_id)` Then only that run paused then resumed natively | `tests/orchestrator/test_overrides.py::test_pause_resume_single_agent` |
| 4 | Given an IMPLEMENTING story with a run When `cancel_work_item` Then state CANCELLED, run CANCELLED, worktree removed, branch kept | `tests/orchestrator/test_overrides.py::test_cancel_work_item_cleans_up` |
| 5 | Given a COMPLETE story When `cancel_work_item` Then `GuardRejected` | `tests/orchestrator/test_overrides.py::test_cancel_complete_item_rejected` |
| 6 | Given story P2 When `set_priority(P0)` Then persisted and `USER_OVERRIDE` written | `tests/orchestrator/test_overrides.py::test_set_priority_persists_and_logs` |
| 7 | Given policies file When `update_model_policy(SENIOR_DEV, …)` Then only SENIOR_DEV changed | `tests/agents/test_policy_file.py::test_update_model_policy_changes_single_role` |
| 8 | Given unknown model id When `walk policy set-model SENIOR_DEV --preferred nope/x` Then exit 1 | `tests/cli/test_cmd_overrides.py::test_set_model_rejects_unknown_model` |
| 9 | Given `walk policy set-autonomy 1` Then `Project.autonomy_level_max == 1` and `USER_OVERRIDE` | `tests/cli/test_cmd_overrides.py::test_set_autonomy` |
| 10 | Given no daemon When `walk pause --agent RUN-…` Then exit 3 | `tests/cli/test_cmd_overrides.py::test_pause_agent_requires_daemon` |

#### Evidence required
- Quality gate output.
- Demo: `walk pause` → `project paused`; `walk ledger query --kind USER_OVERRIDE --limit 1` → payload `{"command": "pause"}`; `walk resume`.

#### Notes
- ARCHITECTURE §6 "Human override"; ADR-0011 D-6 (policy changes apply on next run).
- `NEW NAME:` `set_priority`, `set_autonomy`, `PoliciesFile`, `update_model_policy`, command handler names.
- Commit subject: `feat: add human override commands (E02-S13)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S14 — Security hardening: forbidden paths, git guard hooks, secret scan, command restrictions

**Status:** TODO
**Type:** feat
**Requirements:** §91, §92, §31, §60, §137, §138
**Depends on:** E02-S10, E01-S23, E01-S25
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Repository boundary, protected branches, secret isolation and command restrictions are enforced mechanically: `BoundaryAuditor` ships the default forbidden-path set, every worktree gets git guard hooks, `push` refuses protected branches, and one shared secret scanner protects `.ai/` writes and agent diffs.

#### Scope
- In: `DEFAULT_FORBIDDEN_PATHS`, `allowed_paths` from policy, `install_guard_hooks` (sh scripts), `push` protected check, `contains_secret`, `BoundaryAuditor` secret scan of added files, `SandboxManager.create` guard-hook installation.
- Out: remote push mechanics/PR (E03-S01); Codex sandbox flags (E01-S26, verified by ADR-0014).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/runtime/boundary.py` | modify | `DEFAULT_FORBIDDEN_PATHS`, `EVIDENCE_EXCEPTIONS`, `DefaultBoundaryAuditor.audit` (secret scan added) |
| `src/walk/memory/secrets.py` | create | `contains_secret`, `SECRET_PATTERNS` |
| `src/walk/memory/service.py` | modify | — (`write` uses `contains_secret`) |
| `src/walk/integrations/git/provider.py` | modify | `GitCliProvider.install_guard_hooks`, `GitCliProvider.push` protected check |
| `src/walk/integrations/git/hooks/pre-commit.sh` | create | — |
| `src/walk/integrations/git/hooks/pre-push.sh` | create | — |
| `src/walk/runtime/sandbox.py` | modify | — (`create` calls `install_guard_hooks(path, project.protected_branches)`) |
| `src/walk/agents/models.py` | modify | `RuntimePolicy.allowed_paths: list[str]` (default `["**"]`) |
| `src/walk/agents/defaults/policies.yaml` | modify | — (`allowed_paths` per role; QC `[]`) |
| `tests/runtime/test_boundary.py` | create | — |
| `tests/memory/test_secrets.py` | create | — |
| `tests/integrations/git/test_guard_hooks.py` | create | — |

#### Interface contract
See INTERFACES.md §1.13 `BoundaryAuditor.audit`, §2.3 `GitProvider.install_guard_hooks`, `GitProvider.push`.
```python
# src/walk/runtime/boundary.py
DEFAULT_FORBIDDEN_PATHS: tuple[str, ...] = (".ai/**", ".walk/**", "**/*.env", "ProjectSettings/*Secrets*", ".ai/agents/**", ".ai/approved/**")
EVIDENCE_EXCEPTIONS: tuple[str, ...] = (".ai/features/*/evidence/**", ".ai/bugs/*/evidence/**")
class DefaultBoundaryAuditor:
    def __init__(self, *, forbidden: tuple[str, ...] = DEFAULT_FORBIDDEN_PATHS, exceptions: tuple[str, ...] = EVIDENCE_EXCEPTIONS) -> None: ...
    def audit(self, worktree_path: str, changed_files: list[str], allowed_paths: list[str], forbidden_paths: list[str]) -> list[str]:
        """violations: path outside worktree (absolute/..), path matching forbidden (unless matching an exception),
        path not matching any allowed glob, or 'SECRET:<path>' when contains_secret(file) for added/modified files."""

# src/walk/memory/secrets.py
SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    ("anthropic_key", r"sk-ant-[A-Za-z0-9_-]{20,}"), ("openai_key", r"sk-[A-Za-z0-9]{32,}"),
    ("aws_access_key", r"AKIA[0-9A-Z]{16}"), ("github_token", r"gh[pousr]_[A-Za-z0-9]{36,}"),
    ("jira_token", r"ATATT3[A-Za-z0-9_-]{20,}"), ("private_key", r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ("generic_assignment", r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"\s]{12,}['\"]"),
)
def contains_secret(text: str) -> str | None: ...   # pattern name or None
```
Guard hook scripts: `pre-commit.sh` aborts when current branch matches any protected pattern (`main`, `release/*` expanded from `WALK_PROTECTED_BRANCHES` written into the script at install time); `pre-push.sh` aborts when any pushed ref matches a protected pattern. Both exit 1 with message `walk: protected branch <name>`.

#### Behavior
1. `audit` normalises paths (POSIX separators, resolved against worktree); any path resolving outside the worktree is a violation.
2. Forbidden match wins over allowed; exceptions win over forbidden (`.ai/features/FEAT-0001/evidence/shot.png` is allowed).
3. `allowed_paths` default `["**"]` for SENIOR_DEV/LEAD_DEV; QC `[]` (any write is a violation — QC does not fix code, ADR-0006 D-6).
4. Secret scan reads added/modified files ≤ 1 MB as UTF-8 (errors ignored); binary files are skipped; a hit yields violation `SECRET:<path>`.
5. `MemoryManager.write` refuses content where `contains_secret(doc body or front matter)` → `PermissionDenied("secret-like content: <pattern>")` (ADR-0003 D-4).
6. `install_guard_hooks` resolves the worktree's hooks dir via `git rev-parse --git-path hooks`, writes both scripts with `0o755`, substituting the protected patterns; idempotent (same content → no rewrite). Existing non-walk hooks are preserved by chaining (`exec <hooks>/pre-commit.local` if present).
7. `push(path, branch, protected_branches)` raises `PermissionDenied` when `branch` matches any protected pattern before invoking git (remote mechanics E03-S01).
8. `SandboxManager.create` installs guard hooks after projection; failure → `ConfigError` and worktree removed.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given changed `../outside.txt` When `audit` Then violation | `tests/runtime/test_boundary.py::test_audit_rejects_path_outside_worktree` |
| 2 | Given changed `.ai/agents/roles/lead_dev.md` When `audit` Then violation | `tests/runtime/test_boundary.py::test_audit_rejects_agents_dir` |
| 3 | Given changed `.ai/features/FEAT-0001/evidence/a.png` When `audit` Then no violation | `tests/runtime/test_boundary.py::test_audit_allows_evidence_exception` |
| 4 | Given QC `allowed_paths=[]` and one changed file When `audit` Then violation | `tests/runtime/test_boundary.py::test_audit_qc_may_not_write` |
| 5 | Given added file containing `sk-ant-…` When `audit` Then `SECRET:<path>` | `tests/runtime/test_boundary.py::test_audit_flags_secret_in_added_file` |
| 6 | Given each pattern sample When `contains_secret` Then pattern name; given lorem text Then None | `tests/memory/test_secrets.py::test_contains_secret_patterns_and_negative` |
| 7 | Given doc with a token in body When `MemoryManager.write` Then `PermissionDenied` | `tests/memory/test_secrets.py::test_memory_write_refuses_secret` |
| 8 | Given a real temp worktree When `install_guard_hooks(["main","release/*"])` Then both scripts exist, executable, contain patterns; second call no rewrite | `tests/integrations/git/test_guard_hooks.py::test_install_guard_hooks_idempotent` |
| 9 | Given hooks installed and checkout `main` When `git commit` via runner Then exit 1 with `protected branch` | `tests/integrations/git/test_guard_hooks.py::test_pre_commit_blocks_protected_branch` |
| 10 | Given `push(path, "main", ["main"])` Then `PermissionDenied` and git not invoked | `tests/integrations/git/test_guard_hooks.py::test_push_refuses_protected_branch` |

#### Evidence required
- Quality gate output.
- Demo: after `walk run --once` with a scheduled fake run, `ls .walk/worktrees/<run>/.git` hooks dir (via `git rev-parse --git-path hooks`) shows `pre-commit`, `pre-push`.

#### Notes
- ARCHITECTURE §6 table, §4.2 last row; ADR-0006 D-5; ADR-0009 consequence (sh on Windows via Git for Windows).
- `NEW NAME:` `DEFAULT_FORBIDDEN_PATHS`, `EVIDENCE_EXCEPTIONS`, `walk.memory.secrets` (`contains_secret`, `SECRET_PATTERNS`), `RuntimePolicy.allowed_paths`, hook script files.
- Pitfall: test 9 requires `sh` on PATH; mark `@pytest.mark.skipif(shutil.which("sh") is None)` — not `integration`, since Git for Windows ships `sh`.
- Commit subject: `feat: enforce repository boundary guard hooks and secret scan (E02-S14)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S15 — `walk doctor --fix --strict`

**Status:** TODO
**Type:** feat
**Requirements:** §26, §27, §28, §91, §105, §137
**Depends on:** E02-S07, E02-S14, E02-S04
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
`walk doctor --fix` repairs guard hooks, skill projections, the memory index and the manifest; `--strict` adds lints (import-linter contracts, constitution provider-name check, `models.yaml` validation, version pins, skill drift) and fails on any finding.

#### Scope
- In: `--fix`, `--strict`, lint implementations, exit codes, `doctor` sections for `skills`, `approved`, `versions`, `lints`.
- Out: Jira status-map gap report (E03-S05).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/cli/cmd_doctor.py` | modify | `doctor` (`--fix`, `--strict`), `DoctorReport` |
| `src/walk/cli/lints.py` | create | `lint_constitutions_provider_names`, `lint_models_yaml`, `run_import_linter`, `PROVIDER_NAME_PATTERN` |
| `src/walk/cli/composition.py` | modify | — (exposes services needed by fixes) |
| `tests/cli/test_cmd_doctor_fix.py` | create | — |
| `tests/cli/test_lints.py` | create | — |

#### Interface contract
```python
# src/walk/cli/cmd_doctor.py
class DoctorReport(WalkModel):
    manifest: EnvironmentManifest
    skills: DriftReport
    approved_drift: list[ApprovedArtifactId]
    version_pins_ok: bool
    lints: list[str]            # empty when clean
    fixes_applied: list[str]
    exit_code: int

# src/walk/cli/lints.py
PROVIDER_NAME_PATTERN = r"(?i)\b(claude|anthropic|codex|openai|gpt|sonnet|opus)\b"
def lint_constitutions_provider_names(constitutions: list[Constitution]) -> list[str]: ...   # ADR-0013 D-5
def lint_models_yaml(registry: CapabilityRegistry) -> list[str]:
    """every enabled model: prices > 0, supports_effort_levels non-empty, context_window_tokens > max_output_tokens > 0."""
async def run_import_linter(runner: SubprocessRunner, repo_root: Path) -> list[str]:
    """`lint-imports --config pyproject.toml`; returns broken contract lines; [] if clean; ConfigError if tool missing."""
```
CLI: `walk doctor [--fix] [--strict] [--json]`. Exit: 0 clean; 4 required component missing; 1 any strict lint finding or fix failure.

#### Behavior
1. `--fix` runs, in order: `install_guard_hooks` for every existing worktree under `.walk/worktrees/` and the repo root hooks dir; `skills regenerate` for drift; `memory.rebuild_index()`; re-run preflight to refresh `environment.yaml`. Each fix appended to `fixes_applied`; a failing fix is recorded and does not stop the others; any failure → exit 1.
2. `--strict` runs all lints after fixes; findings printed under `lints`; drift (skills or approved) and pin problems are findings under `--strict`.
3. Without `--strict`, lints are not executed (doctor stays fast); drift is reported informationally.
4. `run_import_linter` is executed only when `import-linter` is installed (dev environment); absence under `--strict` → finding `import-linter not installed` (ConfigError mapped to a finding, exit 1).
5. `--json` prints `DoctorReport`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given missing guard hooks in a worktree When `walk doctor --fix` Then hooks installed and listed in `fixes_applied` | `tests/cli/test_cmd_doctor_fix.py::test_fix_installs_guard_hooks` |
| 2 | Given skill drift When `walk doctor --fix` Then projections regenerated | `tests/cli/test_cmd_doctor_fix.py::test_fix_regenerates_skill_projections` |
| 3 | Given stale `memory_index` row When `--fix` Then index rebuilt | `tests/cli/test_cmd_doctor_fix.py::test_fix_rebuilds_memory_index` |
| 4 | Given clean repo When `walk doctor --strict` Then exit 0 and `lints == []` | `tests/cli/test_cmd_doctor_fix.py::test_strict_clean_exit_zero` |
| 5 | Given constitution body mentioning a provider name When `lint_constitutions_provider_names` Then one finding | `tests/cli/test_lints.py::test_constitution_provider_name_lint` |
| 6 | Given model with zero price When `lint_models_yaml` Then finding | `tests/cli/test_lints.py::test_models_yaml_lint_prices` |
| 7 | Given fake runner returning broken contract output When `run_import_linter` Then findings; given missing tool Then `ConfigError` | `tests/cli/test_lints.py::test_import_linter_wrapper` |
| 8 | Given mismatched pins When `walk doctor --strict` Then exit 1 and `version_pins_ok == False` | `tests/cli/test_cmd_doctor_fix.py::test_strict_fails_on_pin_mismatch` |
| 9 | Given `--json` When doctor Then output parses as `DoctorReport` | `tests/cli/test_cmd_doctor_fix.py::test_doctor_json_report` |

#### Evidence required
- Quality gate output.
- Demo: `walk doctor --fix --strict` on the bootstrapped demo repo → sections `tools`, `providers`, `skills: ok`, `approved: ok`, `versions: ok`, `lints: none`, exit 0.

#### Notes
- ADR-0009 D-10; ADR-0013 D-5; ADR-0011 consequence (`walk doctor` validates `models.yaml`).
- `NEW NAME:` `DoctorReport`, `walk.cli.lints`, `PROVIDER_NAME_PATTERN`.
- Commit subject: `feat: add doctor fix and strict lint modes (E02-S15)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S16 — Epic gate: bootstrap → doctor → skills → approval → override (e2e)

**Status:** TODO
**Type:** feat
**Requirements:** §24, §25, §26, §28, §31, §32, §33, §91, §92, §93, §136, §137
**Depends on:** E02-S15, E02-S13, E02-S12, E02-S09
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** QC   **Reviewer role:** LeadDev

#### Goal
One end-to-end test module proves the Production Kit: a fresh repository is bootstrapped, validated, projected, protected and overridable exactly as the epic gate describes.

#### Scope
- In: `tests/e2e/test_e02_gate.py`, shared e2e fixtures, CLI invocation helper, documentation of the gate transcript.
- Out: any new kernel behaviour (defects found here become `E02-B*` stories via E02-R01).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `tests/e2e/conftest.py` | modify | `bootstrapped_repo`, `cli` (typer `CliRunner` wrapper returning exit code + stdout), `kernel_with_fakes` |
| `tests/e2e/test_e02_gate.py` | create | — |
| `docs/02-work-breakdown/EPIC-02-production-kit.md` | modify | — (Evidence section of this story) |

#### Interface contract
```python
# tests/e2e/conftest.py
@pytest.fixture
def bootstrapped_repo(tmp_game_repo: Path) -> Path:
    """tmp_game_repo (E01) + GDD/combat.md + `walk bootstrap --provider local --key DEMO --name Demo --yes` executed."""
@pytest.fixture
def kernel_with_fakes(bootstrapped_repo: Path) -> KernelHandle:
    """build_kernel(KernelSettings(repo_path=…), overrides=KernelOverrides(adapters={'fake-codex': FakeModelAdapter(...), 'fake-claude': FakeModelAdapter(...)}, keyring_backend=FakeKeyringBackend()))."""
```

#### Behavior
Each gate assertion is one test; tests run in file order but must not depend on each other's side effects (each uses its own fixture instance).
1. Bootstrap creates every `[MVP]` + `agents/` path of ARCHITECTURE §8, `.ai/.gitignore`, `kernel.db`, `production-kit.yaml`, pins.
2. `walk doctor` exits 0 (git present in CI image; unity MISSING is not required) and `environment.yaml` validates.
3. `walk skills sync` then `walk skills check-drift --strict` exits 0; lock has `claude` and `codex` entries.
4. Editing one Claude projection file then `walk skills check-drift --strict` exits 1 and names the skill.
5. A `FakeModelAdapter` script for LEAD_DEV emits `TOOL_CALL_REQUESTED(tool="git.merge_protected")`; after one tick the run is `PAUSED_FOR_APPROVAL`, `walk approvals --pending` lists `APV-0001`; `walk approve APV-0001` → run completes; ledger contains `APPROVAL_REQUESTED`, `APPROVAL_DECIDED`, `TOOL_INVOKED`.
6. `walk pause` then `walk resume` → two `USER_OVERRIDE` events with commands `pause`, `resume`.
7. A fake SENIOR_DEV run whose scripted tool writes `.ai/agents/roles/senior_dev.md` ends `FAILED_BOUNDARY`, the file change is reverted, `TOOL_DENIED` ledger event present.
8. A project hook `project.echo` on `on_project_start` appears in `HOOK_EXECUTED` after `walk run --once`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given fresh repo When bootstrap Then full tree per Behavior 1 | `tests/e2e/test_e02_gate.py::test_bootstrap_creates_production_kit` |
| 2 | Given bootstrapped repo When `walk doctor` Then exit 0 and manifest file valid | `tests/e2e/test_e02_gate.py::test_doctor_passes_and_writes_manifest` |
| 3 | Given sync When `check-drift --strict` Then exit 0 with both providers in lock | `tests/e2e/test_e02_gate.py::test_skill_projections_clean_for_both_providers` |
| 4 | Given edited projection When `check-drift --strict` Then exit 1 naming skill | `tests/e2e/test_e02_gate.py::test_edited_projection_detected_as_modified` |
| 5 | Given fake run requesting protected action When tick + approve Then run completes with approval trail | `tests/e2e/test_e02_gate.py::test_protected_action_pauses_and_approval_resumes` |
| 6 | Given `walk pause`/`walk resume` Then two `USER_OVERRIDE` events | `tests/e2e/test_e02_gate.py::test_pause_resume_recorded_as_user_override` |
| 7 | Given fake run writing under `.ai/agents/roles/` Then `FAILED_BOUNDARY` and change reverted | `tests/e2e/test_e02_gate.py::test_boundary_auditor_rejects_agents_dir_write` |
| 8 | Given project hook on `on_project_start` When `walk run --once` Then `HOOK_EXECUTED` for `project.echo` | `tests/e2e/test_e02_gate.py::test_project_hook_executes_on_start` |

#### Evidence required
- Quality gate output including `tests/e2e/test_e02_gate.py` 8 passed.
- Demo transcript (pasted into Evidence): `walk bootstrap … --yes`, `walk doctor`, `walk skills check-drift --strict`, `walk approvals --pending`, `walk approve APV-0001 --note ok`, `walk ledger query --kind USER_OVERRIDE`.

#### Notes
- Gate text: WBS.md §4 E02. Uses only fakes and a real temp git repo (WBS.md §3.6).
- Commit subject: `feat: add epic 02 production kit gate test (E02-S16)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-R01 — Review E02

**Status:** TODO
**Type:** docs
**Requirements:** §24–§29, §31–§33, §91–§93, §105, §137
**Depends on:** E02-S16
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
An independent agent instance (different model than the implementer of the majority of E02 stories) verifies every E02 story against the Definition of Done and the epic's invariants, and records defects as `E02-B*` bugfix stories.

#### Scope
- In: review of E02-S01…S16 commits; invariant checks 7, 10, 11; MUST-hook completeness; secret hygiene; bugfix story creation.
- Out: fixing defects (bugfix stories), re-planning (planner).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-02-production-kit.md` | modify | — (this task's Evidence; appended `E02-B*` stories) |
| `docs/02-work-breakdown/WBS.md` | modify | — (status rows for E02-R01 and any `E02-B*`) |

#### Interface contract
Reviewer protocol: `docs/00-governance/IMPLEMENTATION-PROTOCOL.md` "Reviewer protocol" steps 1–5. Checklist per story: DoD "Code", "Tests", "Documentation", "Evidence", "Delivery" boxes; per acceptance-criteria row the named test exists and passes (`uv run pytest <nodeid>`).

#### Behavior
1. For every story S01–S16: `git show <sha>` touches only Files-table paths (or the commit body justifies extras); public symbols match the Interface contract; each acceptance test exists by exact name and passes; coverage ≥ 90 % for touched modules (`pytest --cov=walk --cov-report=term-missing`).
2. Invariant 7: every protected action resolves to `REQUIRE_APPROVAL(USER)` and `set-autonomy` is the only path changing `autonomy_level_max`.
3. Invariant 10: no code path other than `approve_artifact` writes under `.ai/approved/`; `verify_approved_artifacts` runs at startup.
4. Invariant 11: no provider-specific skill content outside `adapters/*/projector.py`; `walk skills check-drift` clean on the demo repo.
5. MUST hooks: every row of ARCHITECTURE §4.1 is registered in `builtins.py` or listed in the E02-S08 deferral table with a story id.
6. Secret hygiene: `grep -rE` over `tests/` and `.ai/` fixtures with `SECRET_PATTERNS` yields only the deliberate test samples inside `tests/memory/test_secrets.py` and `tests/runtime/test_boundary.py`.
7. Each defect → one `E02-Bnn` story using the template, `Depends on: E02-R01`, linked here; `BLOCKER` severity noted when it breaks the gate.
8. Commit `docs: review epic 02 stories s01-s16 (E02-R01)` and push.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given each story commit When diffed against its Files table Then no unlisted file without justification | `tests/e2e/test_e02_gate.py::test_bootstrap_creates_production_kit` (re-run as part of review; manual check recorded in Evidence) |
| 2 | Given each acceptance row When `pytest <nodeid>` Then passes | `tests/e2e/test_e02_gate.py::test_doctor_passes_and_writes_manifest` |
| 3 | Given the demo repo When `walk doctor --strict` Then exit 0 | `tests/cli/test_cmd_doctor_fix.py::test_strict_clean_exit_zero` |
| 4 | Given §4.1 table When compared with `builtins.py` + deferral table Then every row accounted for | `tests/hooks/test_builtins.py::test_all_must_hooks_registered_required_low_priority` |
| 5 | Given fixtures When scanned for secrets Then only deliberate samples | `tests/memory/test_secrets.py::test_contains_secret_patterns_and_negative` |

#### Evidence required
- Gate output of the full suite on `main` after the last E02 story.
- Table in Evidence: story → sha → DoD result → defects (ids).
- `walk doctor --strict` transcript on the demo repo.

#### Notes
- Reviewer must be a different agent instance/model than the implementer of ≥ 50 % of E02 stories (IMPLEMENTATION-PROTOCOL, §23).
- Do not fix in place; create `E02-B*` stories.

#### Evidence (filled by implementer)
_pending_
