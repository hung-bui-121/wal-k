# EPIC-01 — Kernel Core

**Roadmap stage:** §135 Stage 1 · **Status:** TODO · **Owner:** planning (2026-10-05)

## Goal
A runnable `walk` kernel process that persists workflow state in SQLite, drives one agent run through a `ModelAdapter` (Fake, Claude, Codex) with permission enforcement, budgets, checkpoints, fallback + handover, and records everything in the ledger.

## Requirements covered
§4, §6.1, §6.2, §6.8, §6.11, §7–§9, §12–§23, §30, §31 (enforcement point), §40 (skeleton), §41, §47, §52–§54, §57–§58, §60 (worktree per run), §66 (data model), §76 (data model), §81–§82, §84–§86, §87 (status), §89–§90, §122, §125–§126, §128, §137 (Inv. 1, 2, 9, 12), §138 (Model Lock-In, Tool Failure), §139 (spike).

## Epic gate
`tests/e2e/test_e01_gate.py`: `build_kernel` with two `FakeModelAdapter`s; a STORY in `READY` is scheduled, runs to `FINAL_OUTPUT(COMPLETED)` with 12 tool calls (→ 2 periodic checkpoints + WIP commits), transitions to `READY_FOR_REVIEW`; a second STORY's run is scripted to fail with `PROVIDER_OUTAGE` after 3 tool calls → fallback to the second fake with a `Handover`, second run continues and completes; `walk status --json`, `walk ledger query`, `walk work show` reflect all of it; import-linter contracts pass.

## Story index

| ID | Title | Depends on | Effort |
|---|---|---|---|
| E01-S01 | Project scaffold, `walk.common`, quality gate, `walk --version` | none | HIGH |
| E01-S02 | Provider CLI/SDK spike → ADR-0014 | none | MEDIUM |
| E01-S03 | SQLite `Database`, `MigrationRunner`, `0001_init.sql`, `walk db migrate/backup` | E01-S01 | HIGH |
| E01-S04 | `UnitOfWork`, `Repository[T]`, `IdSequenceStore`, `IdempotencyStore` | E01-S03 | MEDIUM |
| E01-S05 | Execution ledger: `LedgerManager`, `walk ledger tail/query` | E01-S04 | MEDIUM |
| E01-S06 | `TelemetryManager` and `EvidenceManager` | E01-S05 | MEDIUM |
| E01-S07 | Hooks runtime core: `HookManager` | E01-S05 | MEDIUM |
| E01-S08 | Work-item aggregates, repository, `WorkflowManager.create/get/query`, `walk work list/show` | E01-S04, E01-S05 | HIGH |
| E01-S09 | `StateMachine`, YAML tables, guard registry, `raise_event`, `story_workflow`, `walk work transition` | E01-S07, E01-S08 | HIGH |
| E01-S10 | `feature_workflow`/`bug_workflow` tables, remaining guards, DoR, `ready_items`, done dimensions | E01-S09 | HIGH |
| E01-S11 | Phases and release candidates: models, tables, `walk phase list/start/gate` | E01-S09 | MEDIUM |
| E01-S12 | Budgets and cost: `BudgetManager`, `CostManager`, `walk cost` | E01-S05, E01-S07 | HIGH |
| E01-S13 | Effort resolution: `EffortManager` | E01-S10, E01-S12 | MEDIUM |
| E01-S14 | Tool and skill catalogues: `ToolRegistry`, `tools.yaml`, `Skill`/`SkillProjector` models | E01-S12 | MEDIUM |
| E01-S15 | Permission policy core: `PermissionManager.decide/rules_for` | E01-S14 | MEDIUM |
| E01-S16 | Memory core: front matter, `MemoryDocument`, atomic `write`, `apply_updates`, handovers, index | E01-S05, E01-S07 | HIGH |
| E01-S17 | Constitutions and runtime policies: loaders, merge rules, MVP role defaults | E01-S13, E01-S15 | HIGH |
| E01-S18 | Agent execution contract: `AgentInput/AgentOutput/Handover`, templates, `instantiate` | E01-S14, E01-S16, E01-S17, E01-S24 | HIGH |
| E01-S19 | `ModelAdapter` protocol, `RunSession`, `AgentEvent`, `FakeModelAdapter` | E01-S18 | MEDIUM |
| E01-S20 | Model router: `CapabilityRegistry`, `models.yaml`, `select`, `classify_error`, costing | E01-S19, E01-S12 | HIGH |
| E01-S21 | `ClaudeAdapter` (claude-agent-sdk) | E01-S19, E01-S02 | HIGH |
| E01-S22 | `CodexAdapter` (`codex exec --json`) | E01-S19, E01-S02 | HIGH |
| E01-S23 | Integration protocols and `GitCliProvider` local operations | E01-S04, E01-S05 | HIGH |
| E01-S24 | Context manager skeleton: mandatory items, token budget, `ContextBundle` | E01-S08, E01-S16 | MEDIUM |
| E01-S25 | Runtime persistence: `AgentRun` repository, `SandboxManager`, `CheckpointManager`, `BoundaryAuditor` | E01-S18, E01-S20, E01-S23 | HIGH |
| E01-S26 | `ToolInvoker`: permission enforcement point, Claude `can_use_tool` bridge, Codex sandbox config | E01-S15, E01-S25, E01-S07, E01-S12 | HIGH |
| E01-S27 | `AgentExecutor` event loop, output validation/repair, `OutputApplier` core | E01-S26, E01-S20, E01-S24, E01-S06 | HIGH |
| E01-S28 | Fallback, handover and recovery | E01-S27 | HIGH |
| E01-S29 | `TaskRouter`, `Scheduler`, `Orchestrator` service | E01-S28, E01-S13, E01-S10, E01-S11 | HIGH |
| E01-S30 | Daemon and composition root: `build_kernel`, `KernelLock`, `CommandConsumer`, `walk run`, `walk status` | E01-S29 | HIGH |
| E01-S31 | Epic gate: kernel loop with fake adapters incl. fallback (e2e), import-linter contracts | E01-S30, E01-S21, E01-S22 | MEDIUM |
| E01-R01 | Review E01 | E01-S31 | MEDIUM |

## Reading order for implementers
1. `AGENTS.md` (repo root), then `docs/00-governance/IMPLEMENTATION-PROTOCOL.md`, `CONVENTIONS.md`, `DEFINITION-OF-DONE.md`, `COMMIT-POLICY.md`.
2. `docs/02-work-breakdown/WBS.md` §2–§3 (binding rules and planning conventions), then this file: the story being implemented, fully.
3. The `§NN` sections the story cites in `requirements/WAL_K_REQ.md` (summary in the story is authoritative when the file is absent).
4. The `INTERFACES.md` / `DOMAIN-MODEL.md` sections and ADRs the story names. Nothing else.

Conventions that apply to every story below (from WBS §3): implementation classes are `Default<Protocol>`; `Capability` lives in `walk.common.enums`; `EffortPolicy` in `walk.effort.models`; `BudgetPolicy` in `walk.budgets.models`; guards read `TransitionContext.payload` keys from WBS §3.4; ledger events are written only at ARCHITECTURE §4.3 write points; all subprocess calls go through `SubprocessRunner`; fakes live in `tests/fakes/`; epic gates in `tests/e2e/`.

---

### E01-S01 — Project scaffold, `walk.common`, quality gate, `walk --version`

**Status:** TODO
**Type:** chore
**Requirements:** §4 (objectives 12, 13), §7, §122, §125, §137 (Inv. 1)
**Depends on:** none
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A `uv`-managed Python 3.12 package `walk` exists with the full quality gate green, the `walk.common` primitives every other package imports, shared test fixtures, and a `walk --version` CLI entry point.

#### Scope
- In: `pyproject.toml`, `src/walk/` skeleton, `walk.common` (ids, clock, errors, models, roles, enums), `tests/conftest.py`, `tests/fakes/fake_clock.py`, `tests/fakes/fake_id_factory.py`, `scripts/check.sh`, `scripts/check.ps1`, `.gitignore` additions, `walk --version`.
- Out: persistence (E01-S03), import-linter contracts (E01-S31), any other package.

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `pyproject.toml` | create | — |
| `.gitignore` | modify | — |
| `src/walk/__init__.py` | create | `__version__` |
| `src/walk/py.typed` | create | — |
| `src/walk/common/__init__.py` | create | re-exports of all symbols below |
| `src/walk/common/models.py` | create | `WalkModel`, `FrozenModel`, `utcnow`, `JsonDict`, `Actor` |
| `src/walk/common/ids.py` | create | all `Annotated` id types of DOMAIN-MODEL §1.2, `IdFactory`, `new_ulid`, `format_seq_id`, `parse_prefix`, `ULID_PATTERN` |
| `src/walk/common/clock.py` | create | `Clock`, `SystemClock` |
| `src/walk/common/errors.py` | create | `WalkError`, `TransientError`, `ProviderUnavailable`, `RateLimited`, `Timeout`, `QuotaExhausted`, `ToolCrashed`, `PermanentError`, `PermissionDenied`, `GuardRejected`, `OutputInvalid`, `BoundaryViolation`, `ConfigError`, `RecoverableInterruption` |
| `src/walk/common/roles.py` | create | `AgentRole` |
| `src/walk/common/enums.py` | create | `Effort`, `LearningScope`, `ImprovementScope`, `Capability` |
| `src/walk/cli/__init__.py` | create | — |
| `src/walk/cli/app.py` | create | `app`, `main` |
| `tests/__init__.py`, `tests/common/__init__.py`, `tests/cli/__init__.py`, `tests/fakes/__init__.py` | create | — |
| `tests/conftest.py` | create | fixtures `tmp_repo`, `fake_clock`, `sequential_ids` |
| `tests/fakes/fake_clock.py` | create | `FakeClock` |
| `tests/fakes/fake_id_factory.py` | create | `SequentialIdFactory` |
| `tests/common/test_ids.py` | create | — |
| `tests/common/test_clock.py` | create | — |
| `tests/common/test_errors.py` | create | — |
| `tests/common/test_models.py` | create | — |
| `tests/cli/test_app.py` | create | — |
| `tests/test_scaffold.py` | create | — |
| `scripts/check.sh` | create | — |
| `scripts/check.ps1` | create | — |

#### Interface contract
`pyproject.toml` outline (values are normative):
```toml
[project]
name = "walk"; version = "0.1.0"; requires-python = ">=3.12"
dependencies = ["pydantic>=2.7", "typer>=0.12", "pyyaml>=6", "httpx>=0.27", "python-ulid>=2", "keyring>=25", "jinja2>=3.1"]
[project.optional-dependencies]
claude = ["claude-agent-sdk"]
dev = ["pytest", "pytest-asyncio", "pytest-cov", "ruff", "mypy", "import-linter", "types-PyYAML"]
[project.scripts]
walk = "walk.cli.app:main"
[tool.ruff]
line-length = 100; target-version = "py312"; src = ["src", "tests"]
[tool.ruff.lint]
select = ["ALL"]
ignore = ["D203",   # conflicts with D211 (blank line before class docstring)
          "D213",   # conflicts with D212 (summary on first line)
          "COM812", # handled by the formatter
          "ISC001", # handled by the formatter
          "PLR0913",# protocol methods mirror INTERFACES.md signatures with many args
          "ANN401", # JsonDict payloads are Any by contract
          "TD002", "TD003", "FIX002"]  # TODOs carry story ids, not authors/links
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "PLR2004", "D1", "ARG001", "INP001"]
[tool.mypy]
strict = true; python_version = "3.12"; plugins = ["pydantic.mypy"]
[tool.pytest.ini_options]
asyncio_mode = "auto"; testpaths = ["tests"]
addopts = "--cov=walk --cov-report=term-missing --cov-fail-under=85"
markers = ["integration: needs real external services; skipped by default"]
[tool.coverage.run]
omit = ["scripts/*"]
```
```python
# src/walk/common/ids.py
ULID_PATTERN: str = r"[0-9A-HJKMNP-TV-Z]{26}"
def new_ulid() -> str: ...                                   # 26 Crockford base32 chars, time-ordered (python-ulid)
def format_seq_id(prefix: str, n: int, width: int) -> str: ... # "FEAT", 12, 4 -> "FEAT-0012"; n < 1 -> ValueError
def parse_prefix(id_: str) -> str: ...                        # "FEAT-0012" -> "FEAT"; "OBS-K-0001" -> "OBS-K"; no dash -> ValueError
class IdFactory(Protocol):
    def next_sequence(self, prefix: str) -> str: ...
    def new_ulid(self) -> str: ...
# src/walk/common/clock.py
class Clock(Protocol):
    def now(self) -> datetime: ...          # tz-aware UTC
class SystemClock:
    def now(self) -> datetime: ...
# src/walk/common/models.py — DOMAIN-MODEL §1.1 verbatim (WalkModel, FrozenModel, utcnow, JsonDict, Actor)
# src/walk/common/errors.py — ARCHITECTURE §5.1 taxonomy; every class has a docstring and accepts (message: str, *, detail: JsonDict | None = None)
# src/walk/common/roles.py, enums.py — DOMAIN-MODEL §3 (AgentRole, Effort, LearningScope, ImprovementScope) + Capability (RELOCATE, WBS §3.2)
# src/walk/cli/app.py
app: typer.Typer                            # root; options --repo PATH, --json, --verbose stored in ctx.obj
def main() -> None: ...                     # entry point; `walk --version` prints "walk <__version__>" and exits 0
# tests/fakes
class FakeClock:   def __init__(self, start: datetime) -> None; def now(self) -> datetime; def advance(self, seconds: float) -> None
class SequentialIdFactory: def next_sequence(self, prefix: str) -> str  # FEAT-0001, FEAT-0002 … width from DOMAIN-MODEL §2 table
                           def new_ulid(self) -> str                      # deterministic increasing ULIDs
```

#### Behavior
1. `uv sync --all-extras` succeeds offline for everything except `claude-agent-sdk` (optional extra).
2. `scripts/check.sh` / `check.ps1` run, in order: `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy src tests`, `uv run pytest`; stop at the first failure; exit code is the failing command's exit code.
3. `new_ulid()` returns 26 characters matching `ULID_PATTERN`; two calls 1 ms apart sort lexicographically in creation order.
4. `format_seq_id` zero-pads to `width` and never truncates (`format_seq_id("EVD", 1234567, 6) == "EVD-1234567"`); `n < 1` raises `ValueError`.
5. `parse_prefix` returns everything before the last `-<digits>` group.
6. Every error class in ARCHITECTURE §5.1 exists with the stated parent; `WalkError.detail` defaults to `{}`.
7. `WalkModel` rejects unknown fields (`extra="forbid"`) and validates on assignment; `FrozenModel` raises on mutation.
8. `Actor` serialises enum members by value.
9. `walk --version` prints `walk 0.1.0`; `walk` with no arguments prints help and exits 0.
10. `tmp_repo` fixture creates a temp directory with `git init -b main`, `user.name`/`user.email` configured, and one initial commit.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the package, When `new_ulid()` is called twice with a 1 ms gap, Then both match `ULID_PATTERN` and the second sorts after the first | `tests/common/test_ids.py::test_new_ulid_is_26_chars_and_time_ordered` |
| 2 | When `format_seq_id("FEAT", 12, 4)`, Then `"FEAT-0012"` | `tests/common/test_ids.py::test_format_seq_id_zero_pads` |
| 3 | When `format_seq_id("X", 0, 4)`, Then `ValueError` | `tests/common/test_ids.py::test_format_seq_id_rejects_non_positive` |
| 4 | When `parse_prefix("OBS-K-0001")`, Then `"OBS-K"`; `parse_prefix("nodash")` raises `ValueError` | `tests/common/test_ids.py::test_parse_prefix_handles_compound_prefix_and_rejects_garbage` |
| 5 | Given `"FEAT-12"`, When validated as `FeatureId`, Then validation error (min width 4) | `tests/common/test_ids.py::test_feature_id_pattern_enforces_min_width` |
| 6 | When `SystemClock().now()`, Then tzinfo is UTC | `tests/common/test_clock.py::test_system_clock_returns_utc_aware` |
| 7 | Given `FakeClock`, When `advance(5)`, Then `now()` moved by 5 s exactly | `tests/common/test_clock.py::test_fake_clock_advances_deterministically` |
| 8 | For every error class, Then `issubclass` matches the ARCHITECTURE §5.1 tree (parametrised over all 13 leaves) | `tests/common/test_errors.py::test_error_hierarchy_matches_taxonomy` |
| 9 | When `WalkModel` subclass receives an unknown field, Then `ValidationError` | `tests/common/test_models.py::test_walk_model_forbids_extra_fields` |
| 10 | When a `FrozenModel` attribute is assigned, Then `ValidationError` | `tests/common/test_models.py::test_frozen_model_is_immutable` |
| 11 | When `Actor(role=AgentRole.QC).model_dump()`, Then `{"role": "QC", "model_id": None, "run_id": None}` | `tests/common/test_models.py::test_actor_serialises_by_value` |
| 12 | When `CliRunner.invoke(app, ["--version"])`, Then exit 0 and output contains `walk 0.1.0` | `tests/cli/test_app.py::test_version_prints_version` |
| 13 | When `scripts/check.sh` and `check.ps1` are read, Then each contains the four gate commands in order | `tests/test_scaffold.py::test_check_scripts_invoke_all_gate_commands` |
| 14 | When `pyproject.toml` is parsed, Then `select == ["ALL"]`, `strict == true`, `asyncio_mode == "auto"`, `--cov-fail-under=85` present | `tests/test_scaffold.py::test_pyproject_enforces_quality_gate` |
| 15 | Given `tmp_repo`, Then `git rev-parse HEAD` succeeds and branch is `main` | `tests/test_scaffold.py::test_tmp_repo_fixture_is_initialised_git_repo` |

#### Evidence required
- Quality gate output (`scripts/check.sh` summary: ruff ok, mypy ok, N passed, coverage %).
- Demo: `uv run walk --version` → `walk 0.1.0`.

#### Notes
- ADR-0001 (stack), ADR-0009 D-1/D-2/D-17 (common package, src layout, ULIDs).
- `RELOCATE: Capability → walk.common.enums` (WBS §3.2); `NEW NAME:` dependency `jinja2` recorded in ADR-0014 by E01-S02.
- Pitfall: `pydantic.mypy` plugin is required for `strict` to accept `Field(default_factory=…)` typing.
- Commit: `chore: scaffold package, common primitives and quality gate (E01-S01)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S02 — Provider CLI/SDK spike → ADR-0014

**Status:** TODO
**Type:** docs
**Requirements:** §6.1, §17, §21–§22, §128, §139
**Depends on:** none
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
Every Codex CLI flag and Claude Agent SDK option assumed by ADR-0004 D-7/D-8 and ADR-0011 is verified against the installed tools, and the results (verified / deviation / consequence) are recorded in ADR-0014 so E01-S21/S22 implement against facts.

#### Scope
- In: probe scripts, manual execution against real CLIs, ADR-0014, approval of the `jinja2` dependency.
- Out: adapter code (E01-S21, E01-S22).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/01-architecture/adr/ADR-0014-provider-cli-sdk-verification.md` | create | — |
| `scripts/spikes/codex_probe.sh` | create | — |
| `scripts/spikes/claude_probe.py` | create | — |
| `tests/docs/__init__.py` | create | — |
| `tests/docs/test_adr_0014.py` | create | — |

#### Interface contract
ADR-0014 follows `docs/00-governance/ADR-TEMPLATE.md`, `Status: Accepted`, and contains one table per provider with columns `Assumption | Source | Verified (version) | Deviation | Consequence (story)`. Rows required:

| Provider | Assumption rows |
|---|---|
| Codex CLI | `codex exec --json`; `--sandbox workspace-write`; `--cd <dir>`; `-c model=<id>`; `-c model_reasoning_effort=<low\|medium\|high\|xhigh>`; `--output-schema <file>`; `codex exec resume <thread_id>`; JSON event line kinds (thread id event, tool/command events, usage/token event, final message event); exit codes; network disabled by default under `workspace-write` |
| Claude Agent SDK | `query()` options `cwd`, `allowed_tools`, `permission_mode`, `can_use_tool`, `model`, `effort` (`low\|medium\|high\|xhigh\|max`), `max_turns`, `resume`; session id present in result/init messages; usage fields (input/output/cache-read tokens, cost); structured output mechanism (`output_format`/schema) or absence thereof |
| Kernel | `jinja2` approved as runtime dependency (ADR-0004 D-4 templates) |

Probe scripts print each flag probe and its raw output; they are run manually (real CLIs required) and the transcript is pasted into the ADR under "Evidence".

#### Behavior
1. Each assumption row states `Verified` with the tool version, or `Deviation` with the observed behaviour.
2. Every `Deviation` row names the affected story (`E01-S21` or `E01-S22`) and the required mapping change in the adapter.
3. If `--output-schema` is unavailable, the ADR records that `<worktree>/.walk/output.json` is the only output channel for Codex (ADR-0004 D-3 fallback remains the contract).
4. If the SDK lacks `effort`, the ADR records the alternative parameter and E01-S21 maps `Effort` to it.
5. The ADR "Consequences" section lists the ADRs it amends (ADR-0001 dependency list, ADR-0004, ADR-0011) without rewriting them.
6. Probe scripts are excluded from coverage (`[tool.coverage.run] omit`) and never imported by `src/`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the ADR file, When read, Then it has `Status: Accepted` and the ADR-TEMPLATE headings in order | `tests/docs/test_adr_0014.py::test_adr_has_template_structure` |
| 2 | Then every Codex flag string listed in the contract appears in the Codex table | `tests/docs/test_adr_0014.py::test_adr_covers_every_codex_flag` |
| 3 | Then every SDK option string listed in the contract appears in the SDK table | `tests/docs/test_adr_0014.py::test_adr_covers_every_sdk_option` |
| 4 | Then every row whose Deviation cell is non-empty names `E01-S21` or `E01-S22` | `tests/docs/test_adr_0014.py::test_every_deviation_names_affected_story` |
| 5 | Then the ADR contains a `jinja2` row marked Verified/Accepted | `tests/docs/test_adr_0014.py::test_adr_approves_jinja2_dependency` |
| 6 | Then both probe scripts exist and are referenced from the ADR Evidence section | `tests/docs/test_adr_0014.py::test_probe_scripts_exist_and_are_referenced` |

#### Evidence required
- Quality gate output.
- Manual transcript of `scripts/spikes/codex_probe.sh` and `uv run python scripts/spikes/claude_probe.py` pasted into the ADR (versions of `codex --version` and the SDK package).

#### Notes
- Architect flag: ADR-0004 D-8 says "Exact flags are verified in a Stage 1 spike story; the adapter owns the mapping" — this is that story.
- Pitfall: do not store provider transcripts containing repository content; probes run in an empty temp dir.
- Commit: `docs: record provider cli and sdk verification in ADR-0014 (E01-S02)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S03 — SQLite `Database`, `MigrationRunner`, `0001_init.sql`, `walk db migrate/backup`

**Status:** TODO
**Type:** feat
**Requirements:** §54, §81, §89, §137 (Inv. 9)
**Depends on:** E01-S01
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The project database `<repo>/.ai/kernel.db` can be created and migrated to the full DOMAIN-MODEL §6.2 schema with WAL mode, pragmas and immutability triggers, from code and from the CLI.

#### Scope
- In: `Database`, `MigrationRunner`, project migration `0001_init.sql`, kernel migration folder with `0001_init.sql` for the kernel DB subset, `walk db migrate`, `walk db backup PATH`.
- Out: `UnitOfWork`/repositories (E01-S04), `KernelLock` (E01-S30), dashboard views (E09-S04), local work provider table (E03-S02).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/persistence/__init__.py` | create | re-exports |
| `src/walk/persistence/database.py` | create | `Database`, `DbKind` |
| `src/walk/persistence/migrations.py` | create | `MigrationRunner`, `Migration` |
| `src/walk/persistence/migrations/__init__.py` | create | — |
| `src/walk/persistence/migrations/project/0001_init.sql` | create | — |
| `src/walk/persistence/migrations/kernel/0001_init.sql` | create | — |
| `src/walk/persistence/errors.py` | create | `MigrationError` |
| `src/walk/cli/cmd_db.py` | create | `db_app` |
| `src/walk/cli/app.py` | modify | registers `db_app` |
| `src/walk/cli/composition.py` | create | `open_database(repo: Path, *, read_only: bool = False) -> Database` |
| `tests/persistence/__init__.py` | create | — |
| `tests/persistence/test_database.py` | create | — |
| `tests/persistence/test_migrations.py` | create | — |
| `tests/cli/test_cmd_db.py` | create | — |
| `tests/conftest.py` | modify | fixture `db` (migrated in-memory/temp project DB) |

#### Interface contract
```python
DbKind = Literal["project", "kernel"]

class Database:
    def __init__(self, path: Path, *, read_only: bool = False) -> None: ...
    @property
    def path(self) -> Path: ...
    def connect(self) -> sqlite3.Connection:
        """Opens (or returns the process-wide) connection with PRAGMA journal_mode=WAL, foreign_keys=ON,
        synchronous=NORMAL, busy_timeout=5000; row_factory=sqlite3.Row; isolation_level=None (explicit BEGIN)."""
    def close(self) -> None: ...
    def backup_to(self, target: Path) -> None: ...   # sqlite3.Connection.backup

class Migration(FrozenModel):
    version: int; name: str; sql_path: str; py_path: str | None

class MigrationRunner:
    def __init__(self, db: Database, kind: DbKind) -> None: ...
    def discover(self) -> list[Migration]: ...        # files NNNN_<name>.sql under migrations/<kind>/, sorted, contiguous from 1
    def applied(self) -> list[int]: ...
    def apply_pending(self) -> list[int]:
        """Applies each missing migration in one BEGIN IMMEDIATE transaction per file; inserts schema_migrations row;
        sets PRAGMA user_version = latest; raises ConfigError (wrapping MigrationError) on failure after rollback."""
```
`0001_init.sql` (project) contains exactly the DDL of DOMAIN-MODEL §6.2 for: `schema_migrations, id_sequences, kernel_instances, idempotency_keys, projects, phases, work_items, work_item_transitions, release_candidates, agent_runs, checkpoints, handovers, ledger_events, cost_records, budgets, evidence, decisions, decision_work_items, debates, debate_positions, escalations, approval_requests, approved_artifacts, memory_index, hook_executions, commands, command_results, skill_projections, work_provider_sync, webhook_deliveries, improvement_observations, improvement_candidates, patterns, retrospectives, behavior_versions` with all indexes and the triggers `work_item_transitions_immutable`, `checkpoints_immutable`, `ledger_events_no_update`, `ledger_events_no_delete`, `cost_records_immutable`, `evidence_immutable`, plus `BEFORE DELETE` abort triggers for `work_item_transitions`, `checkpoints`, `cost_records`, `evidence` (ADR-0002 D-3). Kernel `0001_init.sql`: `schema_migrations, id_sequences, improvement_observations, improvement_candidates, patterns, retrospectives, behavior_versions, experiments, kernel_changelog`.

CLI: `walk db migrate` (exit 0, prints applied versions or `up to date`), `walk db backup PATH` (exit 0, prints target path; exit 1 if DB missing).

#### Behavior
1. `connect()` on a missing file creates it and its parent directory `.ai/`; with `read_only=True` it opens `file:…?mode=ro` and never creates.
2. Pragmas are applied on every new connection; `PRAGMA journal_mode` returns `wal`.
3. `discover()` raises `ConfigError` when numbering has a gap or duplicate.
4. `apply_pending()` is idempotent: second call returns `[]` and changes nothing.
5. A failing SQL statement rolls back the whole migration file; `schema_migrations` has no row for it; `user_version` unchanged; `ConfigError` raised with the migration name in `detail`.
6. A paired `NNNN_<name>.py` exposing `migrate(conn)` is executed after its SQL in the same transaction; `backup_to` is called before any migration with a `.py` step.
7. `UPDATE`/`DELETE` on `ledger_events`, `checkpoints`, `cost_records`, `evidence`, `work_item_transitions` raise `sqlite3.IntegrityError` (trigger abort).
8. `walk db migrate` with `--repo` pointing to a dir without `.ai/` creates it (bootstrap proper is E02-S03).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a temp repo, When `Database.connect()`, Then `.ai/kernel.db` exists and `journal_mode == "wal"` and `foreign_keys == 1` | `tests/persistence/test_database.py::test_connect_creates_db_with_wal_and_pragmas` |
| 2 | Given no DB file, When `Database(path, read_only=True).connect()`, Then `ConfigError` and no file created | `tests/persistence/test_database.py::test_read_only_never_creates_file` |
| 3 | When `backup_to(target)`, Then target is a valid SQLite DB with the same tables | `tests/persistence/test_database.py::test_backup_copies_database` |
| 4 | When `apply_pending()` on an empty DB, Then returns `[1]` and every table in the contract list exists | `tests/persistence/test_migrations.py::test_apply_pending_creates_all_tables` |
| 5 | Then `PRAGMA user_version == 1` and `schema_migrations` has one row named `init` | `tests/persistence/test_migrations.py::test_apply_pending_records_version` |
| 6 | When `apply_pending()` again, Then `[]` | `tests/persistence/test_migrations.py::test_apply_pending_is_idempotent` |
| 7 | Given a migrations dir with `0001`, `0003`, When `discover()`, Then `ConfigError` | `tests/persistence/test_migrations.py::test_discover_rejects_gap_in_numbering` |
| 8 | Given an extra migration with invalid SQL, When `apply_pending()`, Then `ConfigError`, no partial objects, `user_version` unchanged | `tests/persistence/test_migrations.py::test_failed_migration_rolls_back` |
| 9 | Given a migration with a `.py` step, When applied, Then `migrate(conn)` ran and a backup file exists | `tests/persistence/test_migrations.py::test_python_step_runs_after_sql_with_backup` |
| 10 | For each of the five append-only tables, When `UPDATE` or `DELETE`, Then `sqlite3.IntegrityError` | `tests/persistence/test_migrations.py::test_append_only_tables_reject_update_and_delete` |
| 11 | When `MigrationRunner(db, "kernel").apply_pending()`, Then kernel tables exist and project-only tables do not | `tests/persistence/test_migrations.py::test_kernel_migrations_create_kernel_subset` |
| 12 | When `walk db migrate --repo <tmp>`, Then exit 0 and output lists `0001_init` | `tests/cli/test_cmd_db.py::test_db_migrate_applies_and_prints` |
| 13 | When `walk db backup <path>` without DB, Then exit 1 | `tests/cli/test_cmd_db.py::test_db_backup_fails_without_database` |

#### Evidence required
- Quality gate output.
- Demo: `walk db migrate --repo ./demo` → `applied: 0001_init`; `walk db migrate --repo ./demo` → `up to date`; `walk db backup ./demo/backup.db` → `backup written: ./demo/backup.db`.

#### Notes
- ADR-0002 D-1/D-2/D-3/D-8; DOMAIN-MODEL §6.
- Pitfall: `isolation_level=None` so `BEGIN IMMEDIATE` is explicit (E01-S04 `UnitOfWork` relies on it). Windows: close connections before `backup_to`/file moves.
- Commit: `feat: add sqlite database and migration runner with initial schema (E01-S03)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S04 — `UnitOfWork`, `Repository[T]`, `IdSequenceStore`, `IdempotencyStore`

**Status:** TODO
**Type:** feat
**Requirements:** §54, §90, §137 (Inv. 9)
**Depends on:** E01-S03
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Transactional building blocks shared by every repository: one SQLite transaction per unit of work, a generic aggregate-JSON repository base, sequence ID allocation inside the transaction, and the idempotency-key store.

#### Scope
- In: `UnitOfWork`, `Repository[T]`, `IdSequenceStore`, `IdempotencyStore`.
- Out: concrete repositories (owning stories), `with_idempotency` facade (E03-S03).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/persistence/uow.py` | create | `UnitOfWork` |
| `src/walk/persistence/repository.py` | create | `Repository` |
| `src/walk/persistence/ids.py` | create | `IdSequenceStore`, `SEQUENCE_WIDTHS` |
| `src/walk/persistence/idempotency.py` | create | `IdempotencyStore`, `IdempotencyRecord` |
| `src/walk/persistence/__init__.py` | modify | re-exports |
| `tests/persistence/test_uow.py` | create | — |
| `tests/persistence/test_repository.py` | create | — |
| `tests/persistence/test_ids.py` | create | — |
| `tests/persistence/test_idempotency.py` | create | — |

#### Interface contract
```python
class UnitOfWork:
    """Async context manager around one SQLite transaction (ADR-0002 D-9)."""
    def __init__(self, db: Database) -> None: ...
    @property
    def conn(self) -> sqlite3.Connection: ...
    async def __aenter__(self) -> "UnitOfWork": ...     # BEGIN IMMEDIATE; nested use raises ConfigError
    async def __aexit__(self, *exc: object) -> None: ... # COMMIT on success, ROLLBACK on exception
    def after_commit(self, fn: Callable[[], Awaitable[None]]) -> None: ...  # hooks fired after COMMIT, in order

T = TypeVar("T", bound=WalkModel)
class Repository(Generic[T]):
    _table: ClassVar[str]; _model: type[T]; _key: ClassVar[str] = "id"
    def __init__(self, db: Database) -> None: ...
    def projection(self, obj: T) -> dict[str, object]: ...   # subclass hook: indexed columns; default {}
    async def insert(self, obj: T, uow: UnitOfWork) -> T: ...
    async def upsert(self, obj: T, uow: UnitOfWork) -> T: ...
    async def get(self, key: str) -> T | None: ...
    async def list_where(self, where: str = "1=1", params: Sequence[object] = (), *, order_by: str | None = None, limit: int | None = None) -> list[T]: ...

SEQUENCE_WIDTHS: dict[str, int]   # DOMAIN-MODEL §2: PHASE 2, EPIC 3, FEAT 4, STORY 4, TASK 4, BUG 4, DEC 4, DEB 4, EVD 6, APR 4, HO 4, APV 4, RC 2, OBS 4, OBS-K 4, IMP 2, PATTERN 3, ANTI 3, EXP 4
class IdSequenceStore:   # implements walk.common.ids.IdFactory
    def __init__(self, db: Database) -> None: ...
    def bind(self, uow: UnitOfWork) -> "IdSequenceStore": ...   # returns a view that allocates on uow.conn
    def next_sequence(self, prefix: str) -> str: ...            # ConfigError when unbound or prefix unknown
    def new_ulid(self) -> str: ...

class IdempotencyRecord(FrozenModel): key: str; operation: str; result_ref: str | None; created_at: datetime
class IdempotencyStore:
    def __init__(self, db: Database, clock: Clock) -> None: ...
    async def has(self, key: str) -> bool: ...
    async def get(self, key: str) -> IdempotencyRecord | None: ...
    async def put(self, key: str, operation: str, result_ref: str | None, uow: UnitOfWork) -> None: ...
    async def run(self, key: str, operation: str, fn: Callable[[], Awaitable[str]], uow: UnitOfWork) -> str: ...  # replay stored result_ref
```

#### Behavior
1. `UnitOfWork` issues `BEGIN IMMEDIATE` on enter; `COMMIT` on clean exit; `ROLLBACK` on exception, re-raising it.
2. `after_commit` callbacks run only after a successful COMMIT, sequentially, and are discarded on rollback.
3. Entering a `UnitOfWork` while another is active on the same connection raises `ConfigError("nested transaction")`.
4. `Repository.insert` stores `obj.model_dump_json()` in `json` plus `projection()` columns; `upsert` uses `ON CONFLICT(<key>) DO UPDATE`.
5. `get` deserialises via `_model.model_validate_json`; unknown key returns `None`.
6. `next_sequence("FEAT")` reads/increments `id_sequences` within the bound transaction (`INSERT … ON CONFLICT DO UPDATE SET next = next + 1 RETURNING next`), formats with `SEQUENCE_WIDTHS`; unbound → `ConfigError`.
7. Sequences never repeat across rolled-back transactions beyond the gap (gaps are allowed, repeats are not).
8. `IdempotencyStore.run` returns the stored `result_ref` without calling `fn` when the key exists; otherwise calls `fn`, stores the result in the same transaction, returns it.
9. `put` on an existing key raises `ConfigError("duplicate idempotency key")`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a UoW, When the body raises, Then no rows persisted and the exception propagates | `tests/persistence/test_uow.py::test_uow_rolls_back_on_exception` |
| 2 | When the body completes, Then rows persisted and `after_commit` callbacks ran in order | `tests/persistence/test_uow.py::test_uow_commits_and_runs_after_commit_hooks` |
| 3 | When body raises, Then `after_commit` callbacks did not run | `tests/persistence/test_uow.py::test_after_commit_hooks_skipped_on_rollback` |
| 4 | When a UoW is entered inside another, Then `ConfigError` | `tests/persistence/test_uow.py::test_nested_uow_rejected` |
| 5 | Given a test model repo, When `insert` then `get`, Then round-trips equal; projection columns populated | `tests/persistence/test_repository.py::test_insert_and_get_round_trip` |
| 6 | When `upsert` twice, Then one row with second values | `tests/persistence/test_repository.py::test_upsert_replaces_existing` |
| 7 | When `get("missing")`, Then `None` | `tests/persistence/test_repository.py::test_get_missing_returns_none` |
| 8 | When `list_where` with `order_by`/`limit`, Then ordered subset | `tests/persistence/test_repository.py::test_list_where_orders_and_limits` |
| 9 | When `next_sequence("FEAT")` thrice in one UoW, Then `FEAT-0001..0003` | `tests/persistence/test_ids.py::test_next_sequence_allocates_contiguous_ids` |
| 10 | When unbound `next_sequence`, Then `ConfigError` | `tests/persistence/test_ids.py::test_next_sequence_requires_bound_uow` |
| 11 | Given a rolled-back allocation, When allocating again, Then id is never a repeat of a committed id | `tests/persistence/test_ids.py::test_sequences_never_repeat_committed_ids` |
| 12 | When `next_sequence("EVD")`, Then width 6 | `tests/persistence/test_ids.py::test_sequence_width_follows_table` |
| 13 | When `run(key, fn)` twice, Then `fn` called once and both return the same `result_ref` | `tests/persistence/test_idempotency.py::test_run_replays_stored_result` |
| 14 | When `put` on existing key, Then `ConfigError` | `tests/persistence/test_idempotency.py::test_put_rejects_duplicate_key` |
| 15 | Given `fn` raises inside `run`, Then key not stored | `tests/persistence/test_idempotency.py::test_run_does_not_store_key_on_failure` |

#### Evidence required
- Quality gate output.

#### Notes
- ADR-0002 D-7/D-9; ARCHITECTURE §5.4 key formats are used by callers, not validated here.
- Pitfall: keep `sqlite3` imports inside `walk.persistence` only (ARCHITECTURE §2.3) — other packages receive `Database`/`UnitOfWork`.
- Commit: `feat: add unit of work, repository base, id sequences and idempotency store (E01-S04)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S05 — Execution ledger: `LedgerManager`, `walk ledger tail/query`

**Status:** TODO
**Type:** feat
**Requirements:** §6.11, §81, §82, §86, §88, §137 (Inv. 9)
**Depends on:** E01-S04
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
An append-only execution ledger with a typed event model, query/tail API and CLI, so every later story has its audit write point available.

#### Scope
- In: `telemetry.models` (`LedgerEvent`, `LedgerEventKind`, `Report`), `LedgerRepository`, `DefaultLedgerManager.append/query/tail/report` (trivial `report`), `walk ledger tail|query`.
- Out: `TelemetryManager`/`EvidenceManager` (E01-S06); full reports (E09-S01/S02).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/telemetry/__init__.py` | create | re-exports |
| `src/walk/telemetry/models.py` | create | `LedgerEventKind`, `LedgerEvent`, `Report`, `EvidenceKind`, `EVIDENCE_RANK`, `Evidence`, `EvidenceDraft`, `RetrospectiveMetrics` (models only; services in S06) |
| `src/walk/telemetry/protocols.py` | create | `LedgerManager` |
| `src/walk/telemetry/repository.py` | create | `LedgerRepository` |
| `src/walk/telemetry/service.py` | create | `DefaultLedgerManager` |
| `src/walk/cli/cmd_ledger.py` | create | `ledger_app` |
| `src/walk/cli/output.py` | create | `render_table`, `render_json`, `exit_with` |
| `src/walk/cli/app.py` | modify | registers `ledger_app` |
| `tests/telemetry/__init__.py` | create | — |
| `tests/telemetry/test_models.py` | create | — |
| `tests/telemetry/test_ledger.py` | create | — |
| `tests/cli/test_cmd_ledger.py` | create | — |

#### Interface contract
Models: DOMAIN-MODEL §3 (`EvidenceKind`, `EVIDENCE_RANK`, `LedgerEventKind`) and §4.12 verbatim. Protocol: INTERFACES.md §1.14 `LedgerManager`. Deltas:
```python
class LedgerRepository:
    def __init__(self, db: Database) -> None: ...
    def insert(self, event: LedgerEvent, conn: sqlite3.Connection) -> LedgerEvent: ...   # returns copy with seq
    async def query(...same params as LedgerManager.query...) -> list[LedgerEvent]: ...
    async def after(self, seq: int, limit: int = 1000) -> list[LedgerEvent]: ...

class DefaultLedgerManager:
    def __init__(self, db: Database, repo: LedgerRepository, ids: IdFactory, clock: Clock) -> None: ...
    async def append(self, event: LedgerEvent, *, uow: UnitOfWork | None = None) -> LedgerEvent: ...
    async def query(...) -> list[LedgerEvent]: ...
    async def tail(self, after_seq: int) -> AsyncIterator[LedgerEvent]: ...   # polls every 0.25 s (injected sleep)
    async def report(self, kind: ..., subject_id: str) -> Report: ...        # Report(markdown="", data={"events": [e.model_dump(mode="json") …]})
```
CLI: `walk ledger tail [--since SEQ] [--follow]`, `walk ledger query [--kind K]... [--item ID] [--run ID] [--phase ID] [--since ISO] [--until ISO] [--limit N]`; both honour `--json`.

#### Behavior
1. `append` without `uow` opens its own `UnitOfWork`; with `uow` inserts on `uow.conn` (participates in caller's transaction).
2. `append` fills `id` (ULID) and `at` (clock) when the event's `id` is empty / `at` is missing; otherwise keeps caller values. `seq` is always assigned by SQLite and returned.
3. `query` filters are ANDed; `limit` default 1000, max 10000; ordered by `seq` ascending.
4. `tail(after_seq)` yields events with `seq > after_seq` in order and keeps polling; cancellation stops it cleanly.
5. Attempts to `UPDATE`/`DELETE` through any public API do not exist; the repository has no such methods (Invariant 9).
6. `report()` returns a `Report` containing the queried events for `subject_id` as `work_item_id` (task/feature), `phase_id` (phase), or all (project/cost/improvement); `markdown` is empty until E09.
7. CLI prints a table (`seq | at | kind | actor | item | run | outcome`) or JSON list; invalid `--since` ISO → exit 1.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `LedgerEventKind` members are enumerated, Then they equal the DOMAIN-MODEL §3 list (count and names) | `tests/telemetry/test_models.py::test_ledger_event_kinds_match_domain_model` |
| 2 | When `EVIDENCE_RANK` is checked, Then every `EvidenceKind` has a rank and `PLAYER_TELEMETRY` is highest | `tests/telemetry/test_models.py::test_evidence_rank_is_total_and_ordered` |
| 3 | When `append(event)` without id/at, Then returned event has ULID id, clock time, `seq == 1` | `tests/telemetry/test_ledger.py::test_append_assigns_id_time_and_seq` |
| 4 | Given a UoW that rolls back, When `append(event, uow=uow)`, Then no row persisted | `tests/telemetry/test_ledger.py::test_append_participates_in_caller_transaction` |
| 5 | Given 5 events of mixed kinds/items, When `query(kinds=[…], work_item_id=…)`, Then only matching rows in seq order | `tests/telemetry/test_ledger.py::test_query_filters_and_orders` |
| 6 | When `query(limit=20000)`, Then `ValueError`-free clamp to 10000 | `tests/telemetry/test_ledger.py::test_query_clamps_limit` |
| 7 | Given events appended after `tail(0)` started, When iterating, Then they arrive in order; cancelling the task stops iteration | `tests/telemetry/test_ledger.py::test_tail_streams_new_events_until_cancelled` |
| 8 | When a raw `UPDATE ledger_events` is attempted, Then `sqlite3.IntegrityError` | `tests/telemetry/test_ledger.py::test_ledger_rows_are_immutable` |
| 9 | When `report("task", "STORY-0001")`, Then `data["events"]` contains that item's events only | `tests/telemetry/test_ledger.py::test_report_returns_subject_events` |
| 10 | When `walk ledger query --kind WORK_ITEM_CREATED --json`, Then exit 0 and JSON list | `tests/cli/test_cmd_ledger.py::test_ledger_query_json_output` |
| 11 | When `walk ledger query --since not-a-date`, Then exit 1 | `tests/cli/test_cmd_ledger.py::test_ledger_query_rejects_bad_timestamp` |
| 12 | When `walk ledger tail --since 0` (no follow) on 3 events, Then 3 rows printed | `tests/cli/test_cmd_ledger.py::test_ledger_tail_prints_events_after_seq` |

#### Evidence required
- Quality gate output.
- Demo: `walk ledger query --limit 5` on a demo DB → table with ≤ 5 rows; `walk ledger query --json | head -c 200`.

#### Notes
- ARCHITECTURE §4.3 (write points), ADR-0002 D-3.
- `report()` is intentionally minimal and is extended (not replaced) by E09-S01.
- Commit: `feat: add append-only execution ledger and ledger cli (E01-S05)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S06 — `TelemetryManager` and `EvidenceManager`

**Status:** TODO
**Type:** feat
**Requirements:** §6.6, §47, §86, §116
**Depends on:** E01-S05
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Structured JSON logging, counters/timers, ledger-derived `RetrospectiveMetrics`, and evidence recording with hashing and §47 ranking.

#### Scope
- In: `DefaultTelemetryManager`, `DefaultEvidenceManager`, `EvidenceRepository`.
- Out: log rotation and metric completeness audit (E09-S06); evidence as context candidates (E04-S10).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/telemetry/protocols.py` | modify | `TelemetryManager`, `EvidenceManager` |
| `src/walk/telemetry/service.py` | modify | `DefaultTelemetryManager`, `DefaultEvidenceManager` |
| `src/walk/telemetry/repository.py` | modify | `EvidenceRepository` |
| `src/walk/telemetry/metrics.py` | create | `METRIC_QUERIES`, `compute_metrics` |
| `src/walk/telemetry/logging.py` | create | `JsonLineHandler`, `configure_logging` |
| `tests/telemetry/test_telemetry.py` | create | — |
| `tests/telemetry/test_metrics.py` | create | — |
| `tests/telemetry/test_evidence.py` | create | — |

#### Interface contract
Protocols: INTERFACES.md §1.14 `TelemetryManager`, `EvidenceManager`. Deltas:
```python
class DefaultTelemetryManager:
    def __init__(self, repo_root: Path, ledger: LedgerRepository, clock: Clock) -> None: ...   # log file <repo>/.walk/logs/kernel.jsonl
class DefaultEvidenceManager:
    def __init__(self, db: Database, ai_root: Path, repo: EvidenceRepository, ledger: LedgerManager, ids: IdSequenceStore, clock: Clock) -> None: ...
```
`METRIC_QUERIES` — one SQL per `RetrospectiveMetrics` field, scoped by optional `phase_id`/`since`:
| Field | Definition over `ledger_events` (`e`) |
|---|---|
| `stories` | count distinct `work_item_id` with `WORK_ITEM_TRANSITION` to `COMPLETE` and payload.kind in (STORY, TASK) |
| `first_pass_success_rate` | among those, share whose payload.fix_loops == 0 (0.0 when no stories) |
| `reworked_stories` | distinct items with a transition to `REWORK` |
| `qc_bugs` | count `BUG_CREATED` |
| `escaped_bugs` | count `BUG_CREATED` with payload.found_in_state == "COMPLETE" |
| `context_stale_incidents` | count `CONTEXT_FRESHNESS` with payload.status != "CURRENT" |
| `fallbacks` | count `MODEL_FALLBACK` |
| `failed_handoffs` | count `AGENT_RUN_ENDED` with payload.handover_in_id set and outcome == "FAILED" |
| `build_failures` | count `BUILD_RESULT` with outcome == "FAILED" |
| `debate_rounds` | count `DEBATE_POSITION` distinct (debate_id, round) |
| `user_escalations` | count `ESCALATION_RAISED` with payload.to_level == 3 |
| `total_cost_usd` | sum `cost_usd` of `COST_RECORDED` |
| `total_tokens` | sum payload.input_tokens + payload.output_tokens of `COST_RECORDED` |
| `mean_task_duration_s` | mean of (AGENT_RUN_ENDED.at − AGENT_RUN_STARTED.at) per run |

#### Behavior
1. `log()` writes one JSON object per line with keys `ts, level, msg, **fields`; never raises on unserialisable fields (falls back to `repr`).
2. `counter`/`timer` accumulate in-process and are flushed as a `metrics` log line every 60 s (injected clock) and on `close()`; they are diagnostics, not the ledger.
3. `metrics()` evaluates `METRIC_QUERIES` and returns a fully populated `RetrospectiveMetrics` (zeros when empty).
4. `EvidenceManager.record` copies `path_or_uri` (if a local file) under `.ai/<features|bugs|phases>/<id>/evidence/<basename>` (folder chosen by `work_item_id` prefix `FEAT`/`BUG`, else `phase_id`; STORY/TASK evidence goes under the parent feature folder passed as `work_item_id` by the caller — when it is a STORY id the folder is `.ai/features/<story-parent>`? No: STORY/TASK evidence is filed under `.ai/features/<work_item_id>/evidence/` using the item id as stem; keep it literal), computes sha256, mints `EVD-` id, inserts `evidence` row and `EVIDENCE_RECORDED` in one transaction.
5. External URIs (`http://`, `https://`, `s3://`) are stored as-is with `sha256=None`.
6. `strongest` returns max by `rank`, ties by `produced_at` desc; empty → `None`.
7. `satisfies(required, present)` returns the kinds missing from `present`, preserving `required` order.
8. Missing local file → `ConfigError`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `log("INFO", "x", a=1)`, Then last line of `kernel.jsonl` parses to `{"level":"INFO","msg":"x","a":1,…}` | `tests/telemetry/test_telemetry.py::test_log_writes_json_line` |
| 2 | When logging a non-serialisable field, Then the line still parses with its `repr` | `tests/telemetry/test_telemetry.py::test_log_falls_back_to_repr` |
| 3 | When `counter("x")` twice and clock advances 60 s, Then a `metrics` line with `x: 2` is flushed | `tests/telemetry/test_telemetry.py::test_counters_flush_periodically` |
| 4 | Given an empty ledger, When `metrics()`, Then all fields zero/0.0 | `tests/telemetry/test_metrics.py::test_metrics_zero_on_empty_ledger` |
| 5 | Given a seeded ledger fixture (2 complete stories, 1 with fix_loops=1, 1 fallback, 2 cost records), When `metrics()`, Then `stories == 2`, `first_pass_success_rate == 0.5`, `fallbacks == 1`, `total_cost_usd` is the sum | `tests/telemetry/test_metrics.py::test_metrics_computed_from_seeded_ledger` |
| 6 | Given `phase_id`, When `metrics(phase_id=…)`, Then only that phase's events count | `tests/telemetry/test_metrics.py::test_metrics_scoped_by_phase` |
| 7 | When `record(draft)` with a local file, Then file copied under the evidence folder, `sha256` set, `EVD-000001`, ledger `EVIDENCE_RECORDED` | `tests/telemetry/test_evidence.py::test_record_copies_hashes_and_logs` |
| 8 | When `record` with `https://…`, Then `uri` kept, `sha256 is None` | `tests/telemetry/test_evidence.py::test_record_external_uri` |
| 9 | When `record` with a missing file, Then `ConfigError` and no row | `tests/telemetry/test_evidence.py::test_record_missing_file_raises` |
| 10 | Given evidence of kinds LOG and AUTOMATED_TEST, When `strongest`, Then AUTOMATED_TEST | `tests/telemetry/test_evidence.py::test_strongest_uses_rank` |
| 11 | Given two AUTOMATED_TEST, Then newer wins | `tests/telemetry/test_evidence.py::test_strongest_breaks_ties_by_recency` |
| 12 | When `satisfies([TESTED kinds…], present)`, Then missing kinds returned in order | `tests/telemetry/test_evidence.py::test_satisfies_returns_missing_kinds` |
| 13 | When `for_item(id, kinds=[SCREENSHOT])`, Then filtered list | `tests/telemetry/test_evidence.py::test_for_item_filters_by_kind` |

#### Evidence required
- Quality gate output.

#### Notes
- ADR-0001 (logs are diagnostics), ADR-0009 D-16 (JSON lines path; rotation in E09-S06), ADR-0003 (evidence folders).
- Evidence folder rule is literal: `.ai/features/<id>/evidence/` for FEAT/STORY/TASK ids, `.ai/bugs/<id>/evidence/` for BUG ids, `.ai/phases/<phase>/evidence/` when only `phase_id` is given.
- Commit: `feat: add telemetry logging, ledger metrics and evidence manager (E01-S06)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S07 — Hooks runtime core: `HookManager`

**Status:** TODO
**Type:** feat
**Requirements:** §32, §41, §138 (Tool Failure)
**Depends on:** E01-S05
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A deterministic, synchronous, priority-ordered hook dispatcher with timeouts, fail policies and full execution records, ready for packages to register builtin hooks.

#### Scope
- In: `hooks.models`, `hooks.protocols`, `DefaultHookManager` engine, `HookExecutionRepository`, `HookFailed`.
- Out: MUST attachment table (E02-S08), `hooks.yaml` parsing (E02-S09) — `register_builtins` registers nothing and `load_project_hooks` raises `NotSupported` until then.

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/hooks/__init__.py` | create | re-exports |
| `src/walk/hooks/models.py` | create | `HookName`, `HookFailPolicy`, `Hook`, `HookContext`, `HookResult`, `HookCallable` |
| `src/walk/hooks/protocols.py` | create | `HookManager` |
| `src/walk/hooks/errors.py` | create | `HookFailed` |
| `src/walk/hooks/repository.py` | create | `HookExecutionRepository` |
| `src/walk/hooks/service.py` | create | `DefaultHookManager` |
| `tests/hooks/__init__.py` | create | — |
| `tests/hooks/test_models.py` | create | — |
| `tests/hooks/test_service.py` | create | — |

#### Interface contract
Models: DOMAIN-MODEL §4.6 (`walk.hooks.models`) verbatim. Protocol: INTERFACES.md §1.11 `HookManager`. Deltas:
```python
HookCallable = Callable[[HookContext], Awaitable[None]]
class HookFailed(PermanentError): """A FAIL_CLOSED hook failed; carries hook_id and results so far in detail."""
class DefaultHookManager:
    def __init__(self, repo: HookExecutionRepository, ledger: LedgerManager, clock: Clock, *, callables: dict[str, HookCallable] | None = None) -> None: ...
    def register(self, hook: Hook, fn: HookCallable | None = None) -> None: ...   # builtin: fn required (or resolvable callable_path); project: fn None
    def register_builtins(self) -> None: ...                                       # no-op in this story (E02-S08)
    def load_project_hooks(self, path: str) -> list[Hook]: ...                     # raises NotSupported until E02-S09
    async def fire(self, name: HookName, ctx: HookContext) -> list[HookResult]: ...
    def hooks_for(self, name: HookName) -> list[Hook]: ...
```

#### Behavior
1. `register` rejects duplicate `(name, id)` with `ConfigError`; rejects a `kind="project"` hook whose `id` equals a registered `required` builtin (`ConfigError`); rejects `enabled=False` for a `required` hook.
2. `hooks_for` returns enabled hooks ordered by `priority` ascending, then `id` ascending.
3. `fire` runs hooks strictly sequentially; each wrapped in `asyncio.wait_for(timeout_s)`; a timeout yields `status="TIMEOUT"`.
4. On failure/timeout of a `FAIL_CLOSED` hook: record the result, write `HOOK_FAILED`, raise `HookFailed` — remaining hooks are not run.
5. On failure of `LOG_AND_CONTINUE`: record, write `HOOK_FAILED`, continue.
6. Every execution inserts a `hook_executions` row and `HOOK_EXECUTED` (status OK) or `HOOK_FAILED` ledger event with `duration_ms`.
7. `fire` for a name with no hooks returns `[]` and writes nothing.
8. `HookContext.at` is taken from the caller; results carry `duration_ms` measured by the clock.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `HookName` members are enumerated, Then they equal the ARCHITECTURE §4.1 list (43 values, snake_case) | `tests/hooks/test_models.py::test_hook_names_match_architecture_table` |
| 2 | Given hooks with priorities 100, 10, 10 (ids b, a), When `hooks_for`, Then order is `10/a, 10/b, 100` | `tests/hooks/test_service.py::test_hooks_ordered_by_priority_then_id` |
| 3 | When registering the same `(name,id)` twice, Then `ConfigError` | `tests/hooks/test_service.py::test_register_rejects_duplicate_id` |
| 4 | Given a required builtin, When a project hook with the same id is registered, Then `ConfigError` | `tests/hooks/test_service.py::test_project_hook_cannot_replace_required_builtin` |
| 5 | Given two hooks, When `fire`, Then both ran sequentially (second starts after first ends) and two `HOOK_EXECUTED` events exist | `tests/hooks/test_service.py::test_fire_runs_sequentially_and_records` |
| 6 | Given a FAIL_CLOSED hook that raises before a second hook, When `fire`, Then `HookFailed`, second hook not run, `HOOK_FAILED` written | `tests/hooks/test_service.py::test_fail_closed_aborts_and_raises` |
| 7 | Given a LOG_AND_CONTINUE hook that raises, Then result FAILED, next hook runs, no exception | `tests/hooks/test_service.py::test_log_and_continue_continues` |
| 8 | Given a hook exceeding `timeout_s`, Then status TIMEOUT and policy applied | `tests/hooks/test_service.py::test_timeout_is_recorded_and_policy_applied` |
| 9 | When `fire` on a name without hooks, Then `[]` and no ledger rows | `tests/hooks/test_service.py::test_fire_without_hooks_is_noop` |
| 10 | When `load_project_hooks`, Then `NotSupported` (until E02-S09) | `tests/hooks/test_service.py::test_load_project_hooks_not_supported_yet` |
| 11 | Given a disabled non-required hook, Then it is skipped with no record | `tests/hooks/test_service.py::test_disabled_hook_is_skipped` |

#### Evidence required
- Quality gate output.

#### Notes
- ADR-0009 D-7; ARCHITECTURE §4.1 failure policy; WBS §3.5 (hooks never duplicate ledger write points).
- `NEW NAME: HookFailed` (WBS §6). `NotSupported` is defined in E01-S23 — until then S07 imports a temporary local `NotSupported`? No: define `NotSupported` in `walk.common.errors`? WBS places it in `walk.integrations.errors`. Resolution for ordering: S07 raises `ConfigError("project hooks available from E02-S09")`; E02-S09 replaces it. Use `ConfigError` here (test 10 asserts `ConfigError`).
- Commit: `feat: add hook manager with ordered dispatch and fail policies (E01-S07)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S08 — Work-item aggregates, repository, `WorkflowManager.create/get/query`, `walk work list/show`

**Status:** TODO
**Type:** feat
**Requirements:** §52, §54, §57, §81
**Depends on:** E01-S04, E01-S05
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The §52 hierarchy (Project, Epic, Feature, Story, Task, Bug) is persisted with sequence IDs and `WORK_ITEM_CREATED` events, queryable from code and CLI.

#### Scope
- In: `workflow.models` (all of DOMAIN-MODEL §4.1 and §3 workflow enums), `WorkflowRepository`, `ProjectRepository`, `DefaultWorkflowManager.create/get/query`, `walk work list|show`.
- Out: transitions (E01-S09), DoR/ready items (E01-S10), phases/RC repositories (E01-S11), provider sync (E03-S08).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/workflow/__init__.py` | create | re-exports |
| `src/walk/workflow/models.py` | create | DOMAIN-MODEL §3 workflow enums + §4.1 models; `TransitionContext`, `GuardResult`, `Transition`, `TransitionTable` |
| `src/walk/workflow/protocols.py` | create | `WorkflowManager`, `Guard` |
| `src/walk/workflow/errors.py` | create | `WorkItemNotFound` |
| `src/walk/workflow/repository.py` | create | `WorkflowRepository`, `ProjectRepository` |
| `src/walk/workflow/service.py` | create | `DefaultWorkflowManager` (create/get/query; other methods added by S09–S11) |
| `src/walk/cli/cmd_work.py` | create | `work_app` |
| `src/walk/cli/app.py` | modify | registers `work_app` |
| `tests/workflow/__init__.py` | create | — |
| `tests/workflow/test_models.py` | create | — |
| `tests/workflow/test_repository.py` | create | — |
| `tests/workflow/test_service_create.py` | create | — |
| `tests/cli/test_cmd_work.py` | create | — |
| `tests/conftest.py` | modify | fixture `project` (persisted `Project(key="DEMO")`) |

#### Interface contract
Models: DOMAIN-MODEL §4.1 verbatim; INTERFACES.md §1.3 value objects. Protocol: INTERFACES.md §1.3 `WorkflowManager` (this story implements `create`, `get`, `query`; remaining methods raise `ConfigError("implemented in E01-S09/S10/S11")` until those stories land — the only permitted deferred-method pattern, see E01-S29 Notes). Deltas:
```python
class WorkItemNotFound(PermanentError): ...
class WorkflowRepository(Repository[WorkItem]):   # table work_items; projection: kind, project_key, parent_id, phase_id, state, state_version, title, owner_role, assigned_run_id, external_ref, priority, risk, fix_loops, created_at, updated_at
    async def by_external_ref(self, external_ref: str) -> WorkItem | None: ...
    async def children(self, parent_id: WorkItemId) -> list[WorkItem]: ...
class ProjectRepository(Repository[Project]): ...   # table projects, key "key"
class DefaultWorkflowManager:
    def __init__(self, db: Database, items: WorkflowRepository, projects: ProjectRepository, ids: IdSequenceStore, ledger: LedgerManager, hooks: HookManager, clock: Clock, tables_dir: Path) -> None: ...
```
CLI: `walk work list [--state S]... [--kind K]... [--phase ID]`, `walk work show ID` (item + contract + transitions + runs + cost — transitions/runs/cost sections print "none" until their stories exist).

#### Behavior
1. `create(WorkItemDraft)` allocates the id from `IdSequenceStore` using the prefix for `draft.kind` (`EPIC/FEAT/STORY/TASK`), validates `parent_id` exists and is of the allowed parent kind (EPIC→none, FEATURE→EPIC|none, STORY/TASK→FEATURE, BUG→none or FEATURE via `related_feature_id`), sets `state=IDEA`, `project_key` from the single `Project`, persists and writes `WORK_ITEM_CREATED` (payload: kind, title, parent_id) in one transaction.
2. `create(BugDraft)` builds a `Bug` with `contract.goal = title`, `severity`, `reproduction/expected/observed`, `related_feature_id`, `found_against_commit`; `owner_role` unset until triage.
3. STORY/TASK drafts without `contract` raise `ConfigError`.
4. `get` raises `WorkItemNotFound`; `query` ANDs filters and orders by `created_at, id`.
5. Discriminated union round-trips: a `Bug` stored and read back is a `Bug` instance.
6. `walk work show` on unknown id exits 1.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `WorkItemState` members are enumerated, Then exactly the 15 ADR-0010 D-1 values | `tests/workflow/test_models.py::test_work_item_state_matches_adr_0010` |
| 2 | When a `Bug` JSON is validated as `WorkItem`, Then a `Bug` instance | `tests/workflow/test_models.py::test_work_item_union_discriminates_on_kind` |
| 3 | When `WorkflowRepository.insert(feature)` then `get`, Then equal; `state` column populated | `tests/workflow/test_repository.py::test_insert_and_get_feature` |
| 4 | When `by_external_ref("LOCAL-1")`, Then the item | `tests/workflow/test_repository.py::test_by_external_ref` |
| 5 | When `children(feature_id)`, Then its stories only | `tests/workflow/test_repository.py::test_children_returns_direct_children` |
| 6 | When `create(FEATURE draft)`, Then id `FEAT-0001`, state IDEA, `WORK_ITEM_CREATED` event with same item id | `tests/workflow/test_service_create.py::test_create_feature_allocates_id_and_logs` |
| 7 | When `create(STORY draft, parent=FEAT-0001)`, Then `STORY-0001` with `parent_id` set | `tests/workflow/test_service_create.py::test_create_story_under_feature` |
| 8 | When `create(STORY draft, parent=EPIC-001)`, Then `ConfigError` | `tests/workflow/test_service_create.py::test_create_rejects_invalid_parent_kind` |
| 9 | When `create(STORY draft)` without contract, Then `ConfigError` | `tests/workflow/test_service_create.py::test_create_story_requires_contract` |
| 10 | When `create(BugDraft)`, Then `BUG-0001`, severity set, `owner_role is None` | `tests/workflow/test_service_create.py::test_create_bug_from_draft` |
| 11 | Given a failing ledger (injected), When `create`, Then no work item persisted | `tests/workflow/test_service_create.py::test_create_is_atomic_with_ledger` |
| 12 | When `get("STORY-9999")`, Then `WorkItemNotFound` | `tests/workflow/test_service_create.py::test_get_unknown_raises` |
| 13 | When `query(states=[IDEA], kinds=[STORY])`, Then filtered list in creation order | `tests/workflow/test_service_create.py::test_query_filters` |
| 14 | When `walk work list --kind FEATURE`, Then table with the feature row | `tests/cli/test_cmd_work.py::test_work_list_filters_by_kind` |
| 15 | When `walk work show FEAT-0001 --json`, Then JSON with `id`, `state`, `contract` keys | `tests/cli/test_cmd_work.py::test_work_show_json` |
| 16 | When `walk work show NOPE-1`, Then exit 1 | `tests/cli/test_cmd_work.py::test_work_show_unknown_exits_1` |

#### Evidence required
- Quality gate output.
- Demo: `walk work list` → table `id | kind | state | title | owner`; `walk work show FEAT-0001`.

#### Notes
- ADR-0010; DOMAIN-MODEL §2 ID rules (allocated in the insert transaction, never from file scans).
- Pitfall: `WorkItem` is an `Annotated` union, so `Repository[WorkItem]._model` uses a `TypeAdapter`, not `model_validate_json`.
- Commit: `feat: add work item aggregates, repository and work cli (E01-S08)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S09 — `StateMachine`, YAML tables, guard registry, `raise_event`, `story_workflow`, `walk work transition`

**Status:** TODO
**Type:** feat
**Requirements:** §53, §54, §61, §81, §105 (tables as versioned data), §137 (Inv. 4, 9)
**Depends on:** E01-S07, E01-S08
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Explicit, data-driven, guarded state transitions committed atomically with the ledger event and the transition row, with hooks fired after commit; `story_workflow v1.0` is loaded from YAML and driven from the CLI.

#### Scope
- In: `StateMachine`, YAML table loader + schema, guard registry, guards needed by `story_workflow`, `raise_event`, `story_workflow.yaml`, `walk work transition`.
- Out: feature/bug tables and their guards (E01-S10), phase/RC tables (E01-S11), provider sync on transition (E03-S03).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/workflow/state_machine.py` | create | `StateMachine`, `TableLoader`, `TABLES_DIR` |
| `src/walk/workflow/guards.py` | create | `register_guard`, `get_guard`, `registered_guards`, guard callables listed below |
| `src/walk/workflow/tables/story_workflow.yaml` | create | — |
| `src/walk/workflow/service.py` | modify | `DefaultWorkflowManager.table_for`, `raise_event` |
| `src/walk/workflow/errors.py` | modify | `UnknownTransition` |
| `src/walk/cli/cmd_work.py` | modify | `transition` command |
| `tests/workflow/test_state_machine.py` | create | — |
| `tests/workflow/test_guards.py` | create | — |
| `tests/workflow/test_tables.py` | create | — |
| `tests/workflow/test_service_transitions.py` | create | — |
| `tests/cli/test_cmd_work.py` | modify | — |

#### Interface contract
```python
class TableLoader:
    def load(self, path: Path) -> TransitionTable: ...     # validates schema below; every guard name must be registered; ConfigError otherwise
class StateMachine:
    def __init__(self, tables: dict[WorkItemKind, TransitionTable]) -> None: ...
    def transition_for(self, kind: WorkItemKind, state: WorkItemState, event: str, item: WorkItem, ctx: TransitionContext) -> Transition:
        """Candidates = rows with (from_state, event) incl. wildcard rows ('*' / '* except …'); evaluates guards in row order;
        returns the first row whose guards all pass; raises UnknownTransition when no row matches (from,event),
        GuardRejected(reason) when rows exist but all guards fail, PermissionDenied when actor_role ∉ allowed_roles."""
    def resolve_target(self, transition: Transition, item: WorkItem, ctx: TransitionContext) -> WorkItemState:
        """to_state, or ctx.payload['resume_state'] for the pseudo-state 'PREVIOUS' (BLOCKED → unblock)."""

def register_guard(name: str) -> Callable[[Guard], Guard]: ...
def get_guard(name: str) -> Guard: ...                      # ConfigError on unknown
def registered_guards() -> dict[str, Guard]: ...
```
YAML schema (`story_workflow.yaml`):
```yaml
name: story_workflow
version: "1.0"
kinds: [STORY, TASK]
transitions:
  - {from: IDEA, event: ready, to: READY, guards: [definition_of_ready], roles: [ORCHESTRATOR, LEAD_DEV, SCRUM_MASTER], hooks: []}
  - {from: IDEA, event: block, to: BLOCKED, guards: [], roles: [ANY_AGENT], hooks: [on_task_blocked]}
  - {from: READY, event: start_implementation, to: IMPLEMENTING, guards: [dependencies_complete, branch_available, budget_available], roles: [KERNEL], hooks: [on_task_start]}
  - {from: IMPLEMENTING, event: submit_for_review, to: READY_FOR_REVIEW, guards: [output_status_is_completed, has_commit, required_evidence_present], roles: [SENIOR_DEV], hooks: []}
  - {from: IMPLEMENTING, event: partial, to: IMPLEMENTING, guards: [handover_present], roles: [SENIOR_DEV], hooks: [on_agent_handoff]}
  - {from: IMPLEMENTING, event: block, to: BLOCKED, guards: [escalations_non_empty], roles: [SENIOR_DEV], hooks: [on_task_blocked]}
  - {from: READY_FOR_REVIEW, event: start_review, to: LEAD_DEV_REVIEW, guards: [reviewer_role_differs, reviewer_model_differs_or_disabled], roles: [KERNEL], hooks: []}
  - {from: LEAD_DEV_REVIEW, event: review_approved, to: INTEGRATION, guards: [output_status_is_approved], roles: [LEAD_DEV], hooks: []}
  - {from: LEAD_DEV_REVIEW, event: review_rejected, to: REWORK, guards: [], roles: [LEAD_DEV], hooks: []}
  - {from: INTEGRATION, event: integration_passed, to: QC, guards: [ci_green], roles: [KERNEL], hooks: [on_ready_for_qc]}
  - {from: INTEGRATION, event: ci_failed, to: REWORK, guards: [], roles: [KERNEL], hooks: [on_build_failure]}
  - {from: QC, event: qc_passed, to: COMPLETE, guards: [output_status_is_approved, required_evidence_present], roles: [QC], hooks: [on_task_complete, on_qc_result]}
  - {from: QC, event: qc_rejected, to: REWORK, guards: [fix_loops_below_max], roles: [QC], hooks: [on_qc_result, on_bug_created], effects: [increment_fix_loops]}
  - {from: QC, event: qc_rejected, to: BLOCKED, guards: [fix_loops_at_max], roles: [QC], hooks: [on_task_failed]}
  - {from: REWORK, event: start_implementation, to: IMPLEMENTING, guards: [budget_available], roles: [KERNEL], hooks: [on_task_start]}
  - {from: BLOCKED, event: unblock, to: PREVIOUS, guards: [blocker_resolved], roles: [ORCHESTRATOR, SCRUM_MASTER, USER], hooks: []}
  - {from: "* except COMPLETE", event: cancel, to: CANCELLED, guards: [], roles: [USER], hooks: [on_task_cancelled]}
  - {from: IMPLEMENTING, event: force_review, to: READY_FOR_REVIEW, guards: [], roles: [USER], hooks: []}
```
Role aliases: `KERNEL` = `AgentRole.KERNEL`; `USER` = `AgentRole.USER`; `ANY_AGENT` = any `AgentRole` except `USER`/`KERNEL`. `effects` (`NEW NAME:` table key) names kernel-side mutations applied in the same transaction: `increment_fix_loops`, `increment_reopen_count`, `store_resume_state`.

Guards registered in this story (all read WBS §3.4 payload keys): `definition_of_ready` (delegates to `check_definition_of_ready`, E01-S10 — in S09 it checks `contract.goal` and `acceptance_criteria` non-empty), `dependencies_complete`, `branch_available`, `budget_available`, `output_status_is_completed`, `output_status_is_approved`, `has_commit`, `required_evidence_present`, `handover_present`, `escalations_non_empty`, `reviewer_role_differs`, `reviewer_model_differs_or_disabled`, `ci_green`, `fix_loops_below_max`, `fix_loops_at_max`, `blocker_resolved`.

`raise_event`: INTERFACES.md §1.3 docstring. CLI: `walk work transition ID EVENT [--reason TEXT] [--payload JSON]` raises as `actor_role=USER, source=USER`.

#### Behavior
1. Loading a table whose guard, hook or role name is unknown raises `ConfigError` naming the row.
2. `transition_for` evaluates rows in file order; wildcard `*` matches any state; `* except A,B` excludes listed states.
3. `raise_event` runs in one `UnitOfWork`: `state`, `state_version += 1`, `updated_at`, effects, `work_item_transitions` row, `WORK_ITEM_TRANSITION` ledger (payload: `from, to, event, reason, resume_state?, state_version`); then after commit fires `ON_STATE_TRANSITION` and each transition hook with `HookContext(payload={"from":…, "to":…, "event":…})`.
4. `block` stores `resume_state = item.state` in the transition payload and on the item (`blocked_reason` from `ctx.reason` or payload); `unblock` with pseudo-target `PREVIOUS` resolves to the stored `resume_state`, else `GuardRejected("no resume_state")`.
5. `GuardRejected.detail` lists each failing guard and its reason; `PermissionDenied.detail` carries actor and allowed roles.
6. A hook failure (`HookFailed`) after commit does not roll back the transition; it is re-raised to the caller.
7. `state_version` mismatch (optimistic concurrency: `expected_state_version` in payload differing from current) raises `GuardRejected("stale state_version")`.
8. CLI exit codes: 0 ok, 2 guard rejected / permission denied, 1 unknown item/event.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `story_workflow.yaml`, When loaded, Then 18 transitions, version `1.0`, kinds STORY/TASK | `tests/workflow/test_tables.py::test_story_workflow_loads_with_expected_rows` |
| 2 | Given a YAML row with guard `nope`, When loaded, Then `ConfigError` naming the row | `tests/workflow/test_tables.py::test_loader_rejects_unknown_guard` |
| 3 | When `transition_for(READY, start_implementation)` with all payload facts true, Then row to IMPLEMENTING | `tests/workflow/test_state_machine.py::test_transition_for_selects_matching_row` |
| 4 | When event has no row for the state, Then `UnknownTransition` | `tests/workflow/test_state_machine.py::test_unknown_transition_raises` |
| 5 | Given QC/`qc_rejected` with `fix_loops=3, max_fix_loops=3`, Then the BLOCKED row is selected | `tests/workflow/test_state_machine.py::test_guard_order_selects_second_row` |
| 6 | Given actor SENIOR_DEV raising `review_approved`, Then `PermissionDenied` | `tests/workflow/test_state_machine.py::test_role_not_allowed_raises_permission_denied` |
| 7 | Given `cancel` from COMPLETE, Then `UnknownTransition` (excluded by wildcard) | `tests/workflow/test_state_machine.py::test_wildcard_except_excludes_states` |
| 8 | For each guard in the list, Given payload true/false, Then ok/not ok with reason (parametrised) | `tests/workflow/test_guards.py::test_payload_guards_evaluate_payload_keys` |
| 9 | When `reviewer_model_differs_or_disabled` with same model and `cross_model_review=False`, Then ok | `tests/workflow/test_guards.py::test_reviewer_model_guard_respects_disabled_flag` |
| 10 | When `raise_event(STORY READY, start_implementation)`, Then state IMPLEMENTING, `state_version == 1`, one transition row, one `WORK_ITEM_TRANSITION`, `ON_STATE_TRANSITION` + `ON_TASK_START` fired in order | `tests/workflow/test_service_transitions.py::test_raise_event_commits_atomically_and_fires_hooks` |
| 11 | Given ledger insert fails, When `raise_event`, Then state unchanged and no transition row | `tests/workflow/test_service_transitions.py::test_raise_event_rolls_back_on_ledger_failure` |
| 12 | When `block` then `unblock` with `blocker_resolved=True`, Then state returns to the previous state | `tests/workflow/test_service_transitions.py::test_block_and_unblock_restore_previous_state` |
| 13 | When `qc_rejected` with `fix_loops_below_max`, Then `fix_loops` incremented in the same transaction | `tests/workflow/test_service_transitions.py::test_qc_rejected_increments_fix_loops` |
| 14 | Given `expected_state_version` stale, Then `GuardRejected` | `tests/workflow/test_service_transitions.py::test_stale_state_version_rejected` |
| 15 | Given a FAIL_CLOSED hook raising, When `raise_event`, Then transition persisted and `HookFailed` raised | `tests/workflow/test_service_transitions.py::test_hook_failure_after_commit_does_not_roll_back` |
| 16 | When `walk work transition STORY-0001 ready`, Then exit 0 and `READY` printed; with a failing guard exit 2 | `tests/cli/test_cmd_work.py::test_work_transition_exit_codes` |

#### Evidence required
- Quality gate output.
- Demo: `walk work transition STORY-0001 ready` → `STORY-0001: IDEA -> READY`; `walk work transition STORY-0001 start_implementation` → exit 2 with guard reasons (`branch_available: payload missing`).

#### Notes
- ADR-0010 D-4/D-5; ADR-0002 D-9; INTERFACES §3.2.
- `NEW NAME:` YAML keys `effects` and pseudo-state `PREVIOUS`; role alias `ANY_AGENT` (table data, not Python symbols).
- Pitfall: hooks fire after COMMIT via `UnitOfWork.after_commit`; do not fire inside the transaction.
- Commit: `feat: add state machine, guard registry and story workflow table (E01-S09)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S10 — `feature_workflow`/`bug_workflow` tables, remaining guards, DoR, `ready_items`, done dimensions

**Status:** TODO
**Type:** feat
**Requirements:** §6.5, §53, §58, §61, §64, §131, §137 (Inv. 6)
**Depends on:** E01-S09
**Effort:** HIGH   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every INTERFACES §3.1–§3.3 transition and guard exists as data plus callables; Definition of Ready, ready-item selection and feature done dimensions are implemented.

#### Scope
- In: `feature_workflow.yaml`, `bug_workflow.yaml`, `scheduled_states.yaml`, remaining guards, `check_definition_of_ready`, `ready_items`, `set_done_dimension`, `increment_reopen_count` effect.
- Out: phases/RC (E01-S11), real CI/commit facts (E03), scope guard real implementation (E06-S07 — here `in_phase_scope` passes when `item.phase_id is None or payload.phase_state == "ACTIVE" and item.phase_id == ctx.phase.id`).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/workflow/tables/feature_workflow.yaml` | create | — |
| `src/walk/workflow/tables/bug_workflow.yaml` | create | — |
| `src/walk/workflow/tables/scheduled_states.yaml` | create | — |
| `src/walk/workflow/guards.py` | modify | new guards listed below |
| `src/walk/workflow/readiness.py` | create | `definition_of_ready_checks` |
| `src/walk/workflow/service.py` | modify | `check_definition_of_ready`, `ready_items`, `set_done_dimension` |
| `tests/workflow/test_tables.py` | modify | — |
| `tests/workflow/test_guards.py` | modify | — |
| `tests/workflow/test_readiness.py` | create | — |
| `tests/workflow/test_service_ready.py` | create | — |

#### Interface contract
Tables encode INTERFACES §3.1 (feature, 20 rows incl. `force_review` whose target is the pseudo-state `CHILDREN_READY_FOR_REVIEW` handled as effect `force_children_review`) and §3.3 (bug, 17 rows). New guards: `in_phase_scope`, `has_gdd_refs_or_user_feature`, `technical_design_section_present`, `required_approved_artifacts_present`, `children_created`, `all_stories_integrated`, `ci_green_on_integration_branch`, `all_applicable_dimensions_done`, `no_open_blocker_bugs`, `rework_children_created`, `phase_in_evidence_review`, `has_children_implementing`, `severity_set`, `owner_role_set`, `decision_recorded_quality`, `root_cause_section_present`, `regression_test_evidence`, `reproduction_no_longer_reproduces_evidence`, `reopen_below_max`, `reopen_at_max`. New effects: `increment_reopen_count`, `force_children_review`.
```yaml
# scheduled_states.yaml — INTERFACES §4 rows for kinds FEATURE/STORY/TASK/BUG (phase/debate rows are E05/E07)
- {kind: FEATURE, state: IDEA, role: ORCHESTRATOR, purpose: PLAN}
- {kind: FEATURE, state: DISCOVERY, role: DESIGN_LEADER, fallback_role: ORCHESTRATOR, purpose: DESIGN}
- {kind: FEATURE, state: DESIGN, role: LEAD_DEV, purpose: DESIGN}
- {kind: FEATURE, state: QC, role: QC, purpose: QC}
- {kind: STORY, state: READY, role: contract.owner_role, purpose: IMPLEMENT}   # same for TASK, and for REWORK
- {kind: STORY, state: READY_FOR_REVIEW, role: contract.reviewer_role, purpose: REVIEW}
- {kind: STORY, state: QC, role: QC, purpose: QC}
- {kind: BUG, state: DISCOVERY, role: LEAD_DEV, purpose: TRIAGE}
- {kind: BUG, state: READY, role: contract.owner_role, purpose: IMPLEMENT}    # and REWORK
- {kind: BUG, state: READY_FOR_REVIEW, role: LEAD_DEV, purpose: REVIEW}
- {kind: BUG, state: QC, role: QC, purpose: QC}
```
```python
def definition_of_ready_checks(item: WorkItem, deps: list[WorkItem]) -> list[tuple[str, bool, str]]:
    """§58: ('requirement_complete', goal non-empty), ('acceptance_criteria', non-empty), ('dependencies_resolved', all deps COMPLETE),
    ('design_approved', not required or payload/feature flag), ('assets_available', contract has no 'asset:' constraint or payload flag),
    ('constraints_known', constraints list non-empty or complexity TRIVIAL/SMALL)."""
# DefaultWorkflowManager
def check_definition_of_ready(self, item: WorkItem) -> GuardResult: ...                # reason lists failing check names
async def ready_items(self, phase_id: PhaseId | None) -> list[WorkItem]: ...            # scheduled_states ∩ dependencies complete ∩ (phase scope)
async def set_done_dimension(self, feature_id: FeatureId, dimension: DoneDimension, done: bool, evidence_id: EvidenceId | None) -> Feature: ...
```

#### Behavior
1. Both tables load with every guard/hook/role resolvable; `TABLES_DIR` contains exactly `story_workflow.yaml`, `feature_workflow.yaml`, `bug_workflow.yaml` (+ `phase_workflow.yaml`, `rc_workflow.yaml` after S11) and `scheduled_states.yaml`.
2. `check_definition_of_ready` returns `ok=False` with comma-separated failing check names; `definition_of_ready` guard delegates to it.
3. `ready_items` returns items whose `(kind, state)` appears in `scheduled_states.yaml`, whose contract dependencies are all `COMPLETE`, not `BLOCKED`, with `assigned_run_id is None`, and (when `phase_id` given) `item.phase_id in (phase_id, None)`; ordered by `priority`, then `created_at`.
4. `set_done_dimension` raises `ConfigError` when `dimension not in feature.applicable_dimensions`; records `evidence_id` in payload of a `WORK_ITEM_TRANSITION`? No — writes no transition; it updates `done_dimensions` and writes ledger `TASK_COMPLETED`? No — it updates the aggregate only and relies on `qc_passed` guard `all_applicable_dimensions_done`. Literal rule: update `done_dimensions`, persist, no ledger event.
5. `all_applicable_dimensions_done` is `ok` iff every `applicable_dimensions` entry maps to `True` in `done_dimensions`.
6. `qc_rejected` on a feature does not increment `fix_loops` of children; `reopen` on a bug increments `reopen_count` (effect).
7. `wont_fix` requires `decision_id` in payload (guard `decision_recorded_quality` checks presence and `payload["decision_category"] == "QUALITY"`).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `feature_workflow.yaml` loads, Then 20 rows and every INTERFACES §3.1 `(from, event)` pair present | `tests/workflow/test_tables.py::test_feature_workflow_matches_interfaces` |
| 2 | When `bug_workflow.yaml` loads, Then 17 rows and every INTERFACES §3.3 pair present | `tests/workflow/test_tables.py::test_bug_workflow_matches_interfaces` |
| 3 | When `scheduled_states.yaml` loads, Then every INTERFACES §4 FEATURE/STORY/TASK/BUG row present | `tests/workflow/test_tables.py::test_scheduled_states_match_routing_table` |
| 4 | For each new guard, Given payload true/false, Then expected result (parametrised) | `tests/workflow/test_guards.py::test_feature_and_bug_guards_evaluate_payload_keys` |
| 5 | Given a feature with `done_dimensions` missing one applicable dimension, Then `all_applicable_dimensions_done` fails naming it | `tests/workflow/test_guards.py::test_all_dimensions_guard_names_missing_dimension` |
| 6 | Given a story with empty acceptance criteria and an incomplete dependency, When `check_definition_of_ready`, Then `ok=False` reason contains both check names | `tests/workflow/test_readiness.py::test_dor_reports_all_failing_checks` |
| 7 | Given a complete contract and COMPLETE deps, Then `ok=True` | `tests/workflow/test_readiness.py::test_dor_passes_when_ready` |
| 8 | Given items in READY/IDEA/BLOCKED and one with an incomplete dependency, When `ready_items(None)`, Then only READY items with complete deps, ordered by priority | `tests/workflow/test_service_ready.py::test_ready_items_filters_and_orders` |
| 9 | Given `phase_id`, Then items of other phases excluded, phase-less items included | `tests/workflow/test_service_ready.py::test_ready_items_respects_phase_scope` |
| 10 | When `set_done_dimension(FEAT, TESTED, True)`, Then persisted; unknown dimension → `ConfigError` | `tests/workflow/test_service_ready.py::test_set_done_dimension_updates_or_rejects` |
| 11 | When bug `reopen` with `reopen_count < max_reopen`, Then REWORK and `reopen_count` incremented | `tests/workflow/test_service_ready.py::test_bug_reopen_increments_count` |
| 12 | When bug `wont_fix` without `decision_id`, Then `GuardRejected` | `tests/workflow/test_service_ready.py::test_wont_fix_requires_quality_decision` |

#### Evidence required
- Quality gate output.
- Demo: `walk work transition BUG-0001 triaged --payload '{"severity_set": true, "owner_role_set": true}'` → `BUG-0001: DISCOVERY -> READY`.

#### Notes
- ADR-0010 D-2/D-6; INTERFACES §3.1, §3.3, §4; §58.
- `NEW NAME:` `src/walk/workflow/tables/scheduled_states.yaml` (routing data consumed by `ready_items` and E01-S29 `TaskRouter`), effects `increment_reopen_count`, `force_children_review`, pseudo-state `CHILDREN_READY_FOR_REVIEW`.
- Commit: `feat: add feature and bug workflow tables, readiness and done dimensions (E01-S10)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S11 — Phases and release candidates: models, tables, `walk phase list/start/gate`

**Status:** TODO
**Type:** feat
**Requirements:** §66, §68, §70, §76, §93 (stop phase)
**Depends on:** E01-S09
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Phase and release-candidate lifecycles exist as persisted aggregates with data-driven transitions; the CLI can list/start phases and record a gate decision (intake algorithms come in E07).

#### Scope
- In: `PhaseRepository`, `ReleaseCandidateRepository`, `phase_workflow.yaml`, `rc_workflow.yaml`, `phase_event`, `rc_event`, phase/RC guards (payload-based), `walk phase list|start|gate`.
- Out: evidence package, REWORK/CHANGE intake, next-phase start (E07-S03…S07); `walk phase plan` (E06-S04); RC service (E11-S02).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/workflow/tables/phase_workflow.yaml` | create | — |
| `src/walk/workflow/tables/rc_workflow.yaml` | create | — |
| `src/walk/workflow/repository.py` | modify | `PhaseRepository`, `ReleaseCandidateRepository` |
| `src/walk/workflow/state_machine.py` | modify | `PhaseStateMachine`, `RcStateMachine` (same engine generic over state enum) |
| `src/walk/workflow/guards.py` | modify | phase/RC guards listed below |
| `src/walk/workflow/service.py` | modify | `phase_event`, `rc_event`, `create_phase`, `list_phases` |
| `src/walk/cli/cmd_phase.py` | create | `phase_app` |
| `src/walk/cli/app.py` | modify | registers `phase_app` |
| `tests/workflow/test_tables.py` | modify | — |
| `tests/workflow/test_service_phase.py` | create | — |
| `tests/cli/test_cmd_phase.py` | create | — |

#### Interface contract
Tables encode INTERFACES §3.4 (phase, 13 rows; events `decide:GO|REWORK|CHANGE|STOP`) and §3.6 (RC, 6 rows). Guards: `previous_phase_complete_or_first`, `scope_non_empty`, `kit_validated` (payload `kit_validated`, default True until E02-S03 supplies it), `all_scope_features_terminal`, `evidence_package_written`, `retrospective_written`, `feedback_non_empty`, `rework_work_items_created`, `impact_analysis_evidence_present`, `approval_user`, `build_evidence_present`, `qc_report_evidence`, `rejection_bugs_created`, `rejection_bugs_complete`.
```python
# DefaultWorkflowManager additions
async def create_phase(self, name: str, ordinal: int, *, goal: str = "", scope_epic_ids: list[EpicId] = ()) -> Phase: ...   # id PHASE-NN
async def list_phases(self) -> list[Phase]: ...
async def phase_event(self, phase_id: PhaseId, event: str, ctx: TransitionContext) -> Phase: ...   # ledger PHASE_TRANSITION; decide:* also PHASE_GATE_DECISION (payload decision, feedback); gate_round += 1 on package_ready
async def rc_event(self, rc_id: ReleaseCandidateId, event: str, ctx: TransitionContext) -> ReleaseCandidate: ...   # ledger RC_TRANSITION
```
CLI: `walk phase list`, `walk phase start ID`, `walk phase gate ID --decision GO|REWORK|CHANGE|STOP [--feedback TEXT|@FILE]`.

#### Behavior
1. `create_phase` enforces unique `ordinal` (`ix_phases_ordinal`) → `ConfigError` on duplicate.
2. `phase_event("start")` sets `started_at`; `decide:GO` sets `completed_at` and `last_decision`; `decide:STOP` sets `Project.paused = True`.
3. `decide:REWORK|CHANGE` require `feedback` in payload (guard `feedback_non_empty`).
4. `package_ready` increments `gate_round`.
5. `PHASE_GATE_DECISION` is written by `phase_event` for `decide:*` in the same transaction as `PHASE_TRANSITION` (ARCHITECTURE §4.3 names `orchestrator.PhaseGate` as the write point; E07-S05 moves the write there and this story's write is removed then — state this in E07-X01 refine).
6. `rc_event("next_rc")` creates a new `ReleaseCandidate` with `number + 1` in `BUILDING`.
7. CLI `gate` with `--decision` outside the enum exits 1; guard rejection exits 2.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `phase_workflow.yaml` loads, Then 13 rows covering every INTERFACES §3.4 pair | `tests/workflow/test_tables.py::test_phase_workflow_matches_interfaces` |
| 2 | When `rc_workflow.yaml` loads, Then 6 rows covering §3.6 | `tests/workflow/test_tables.py::test_rc_workflow_matches_interfaces` |
| 3 | When `create_phase("Prototype", 1)`, Then `PHASE-01`, PLANNED; duplicate ordinal → `ConfigError` | `tests/workflow/test_service_phase.py::test_create_phase_allocates_id_and_unique_ordinal` |
| 4 | When `phase_event(start)` with scope and first phase, Then ACTIVE, `started_at` set, `PHASE_TRANSITION` written, `ON_PHASE_START` fired | `tests/workflow/test_service_phase.py::test_phase_start_transitions_and_fires_hook` |
| 5 | Given ordinal 2 and phase 1 not COMPLETE, When `start`, Then `GuardRejected` | `tests/workflow/test_service_phase.py::test_phase_start_requires_previous_complete` |
| 6 | Given USER_GATE, When `decide:REWORK` without feedback, Then `GuardRejected`; with feedback → REWORK and `PHASE_GATE_DECISION` | `tests/workflow/test_service_phase.py::test_gate_rework_requires_feedback` |
| 7 | When `decide:STOP`, Then STOPPED and project paused | `tests/workflow/test_service_phase.py::test_gate_stop_pauses_project` |
| 8 | When `package_ready`, Then `gate_round == 1` | `tests/workflow/test_service_phase.py::test_package_ready_increments_gate_round` |
| 9 | When `rc_event(next_rc)` from REJECTED with bugs complete, Then new RC number 2 in BUILDING | `tests/workflow/test_service_phase.py::test_rc_next_creates_successor` |
| 10 | When `walk phase list`, Then table with id/ordinal/state; `walk phase start PHASE-01` → `ACTIVE` | `tests/cli/test_cmd_phase.py::test_phase_list_and_start` |
| 11 | When `walk phase gate PHASE-01 --decision MAYBE`, Then exit 1 | `tests/cli/test_cmd_phase.py::test_phase_gate_rejects_unknown_decision` |

#### Evidence required
- Quality gate output.
- Demo: `walk phase list` → `PHASE-01 | 1 | Prototype | PLANNED`; `walk phase start PHASE-01` → `PHASE-01: PLANNED -> ACTIVE`.

#### Notes
- ADR-0010 D-3; INTERFACES §3.4, §3.6; ARCHITECTURE §10 ("gate CLI minimal").
- Phase `USER_GATE`/`PHASE_REVIEW` projections onto features are not implemented here (dashboards, E07).
- Commit: `feat: add phase and release candidate lifecycles with phase cli (E01-S11)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S12 — Budgets and cost: `BudgetManager`, `CostManager`, `walk cost`

**Status:** TODO
**Type:** feat
**Requirements:** §20, §84, §85, §86
**Depends on:** E01-S05, E01-S07
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Budgets at Global/Project/Phase/Role/Task scope with soft/hard thresholds and hooks, cost records with roll-ups, and a `walk cost` CLI.

#### Scope
- In: `budgets.models` incl. RELOCATED `BudgetPolicy` and `BudgetVerdict`, `BudgetRepository`, `CostRepository`, `DefaultBudgetManager`, `DefaultCostManager`, `walk cost`.
- Out: token→USD conversion (`model_router.costing`, E01-S20); CI/compute/time cost completeness (E09-S03).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/budgets/__init__.py` | create | re-exports |
| `src/walk/budgets/models.py` | create | `BudgetScope`, `BudgetDimension`, `CostCategory`, `BudgetHardAction`, `Budget`, `BudgetSubject`, `CostRecord`, `BudgetPolicy`, `BudgetVerdict` |
| `src/walk/budgets/protocols.py` | create | `BudgetManager`, `CostManager` |
| `src/walk/budgets/repository.py` | create | `BudgetRepository`, `CostRepository` |
| `src/walk/budgets/service.py` | create | `DefaultBudgetManager`, `DefaultCostManager` |
| `src/walk/budgets/errors.py` | create | `BudgetExhausted` |
| `src/walk/cli/cmd_cost.py` | create | `cost_app` |
| `src/walk/cli/app.py` | modify | registers `cost_app` |
| `tests/budgets/__init__.py` | create | — |
| `tests/budgets/test_models.py` | create | — |
| `tests/budgets/test_budget_manager.py` | create | — |
| `tests/budgets/test_cost_manager.py` | create | — |
| `tests/cli/test_cmd_cost.py` | create | — |

#### Interface contract
Models: DOMAIN-MODEL §3 budgets enums, §4.4, plus `BudgetPolicy` (DOMAIN-MODEL §4.2 definition, relocated) and `BudgetVerdict` (INTERFACES §1.6). Protocols: INTERFACES.md §1.6. Deltas:
```python
class BudgetExhausted(PermanentError): """hard limit reached; detail: budget id, hard_action"""
class DefaultBudgetManager:
    def __init__(self, db: Database, repo: BudgetRepository, ledger: LedgerManager, hooks: HookManager, clock: Clock) -> None: ...
class DefaultCostManager:
    def __init__(self, db: Database, repo: CostRepository, ledger: LedgerManager, budgets: BudgetManager, items: WorkflowRepository) -> None: ...
```
CLI: `walk cost --item ID | --phase ID | --project` → table `category | usd` and total; `--json`.

#### Behavior
1. `ensure` creates one `Budget` per dimension in `policy.per_task` (or `limits`) with id `<scope>:<scope_id>:<dimension>`; existing rows are untouched (idempotent).
2. `applicable(subject)` returns budgets for GLOBAL, PROJECT(subject.project_key), PHASE, ROLE, TASK where the subject field is set.
3. `meter` adds `quantity` to every applicable budget in one transaction and writes one `BUDGET_EVENT` (payload: dimension, quantity, per-budget consumed/limit). Verdict: `EXHAUSTED(hard_action)` if any budget `consumed >= limit`; else `SOFT_THRESHOLD` if any crossed `soft_threshold_ratio` for the first time (`soft_notified` set, `ON_BUDGET_THRESHOLD` fired once per budget); else `OK`. `ON_BUDGET_EXHAUSTED` fired on EXHAUSTED.
4. `headroom` = min over applicable `(limit − consumed)` per dimension; dimensions without budgets are absent from the dict (callers treat absent as unlimited).
5. `can_afford` true iff for every listed scope id the budget for `dimension` has `limit − consumed >= quantity` (missing budget → true).
6. `CostManager.record` inserts `cost_records` + `COST_RECORDED` then meters `COST_USD` (and `TOKENS` when `dimension == TOKENS`) on the subject derived from the record.
7. `cost_of(work_item_id)` sums records of the item and all descendants (recursive `parent_id`, plus bugs with `related_feature_id`), grouped by `CostCategory`; `cost_of(phase_id)`/`cost_of(project_key)` group directly.
8. `meter` with negative quantity raises `ValueError`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `BudgetPolicy()` defaults, Then `per_task` has COST_USD 15, TOOL_CALLS 400, EXECUTION_TIME_S 2700, REVIEW_LOOPS 3 | `tests/budgets/test_models.py::test_budget_policy_defaults` |
| 2 | When `ensure(TASK, "STORY-0001", policy)` twice, Then 4 rows once, ids formatted `TASK:STORY-0001:COST_USD` | `tests/budgets/test_budget_manager.py::test_ensure_is_idempotent_and_formats_ids` |
| 3 | Given GLOBAL, PROJECT, ROLE, TASK budgets, When `applicable(subject)`, Then all four returned, PHASE absent when `phase_id is None` | `tests/budgets/test_budget_manager.py::test_applicable_covers_subject_scopes` |
| 4 | Given TASK COST_USD limit 10, When `meter(…, 8.5)`, Then `SOFT_THRESHOLD`, `ON_BUDGET_THRESHOLD` fired once, `BUDGET_EVENT` written | `tests/budgets/test_budget_manager.py::test_meter_soft_threshold_fires_once` |
| 5 | When `meter` again with 0.5 (still above soft), Then `OK` and no second threshold hook | `tests/budgets/test_budget_manager.py::test_soft_threshold_not_refired` |
| 6 | When `meter` pushes `consumed >= limit`, Then `EXHAUSTED` with `hard_action` and `ON_BUDGET_EXHAUSTED` fired | `tests/budgets/test_budget_manager.py::test_meter_exhausted_fires_hook` |
| 7 | Given TASK and ROLE budgets, When `meter`, Then both consumed in one transaction (ledger failure → neither) | `tests/budgets/test_budget_manager.py::test_meter_is_atomic_across_budgets` |
| 8 | When `headroom`, Then min across scopes per dimension | `tests/budgets/test_budget_manager.py::test_headroom_is_minimum_across_scopes` |
| 9 | When `meter(…, -1)`, Then `ValueError` | `tests/budgets/test_budget_manager.py::test_meter_rejects_negative` |
| 10 | When `record(cost_record)`, Then `cost_records` row, `COST_RECORDED`, and TASK COST_USD consumed | `tests/budgets/test_cost_manager.py::test_record_persists_and_meters` |
| 11 | Given a feature with 2 stories and a bug, When `cost_of(work_item_id=FEAT)`, Then sums descendants by category | `tests/budgets/test_cost_manager.py::test_cost_of_rolls_up_descendants` |
| 12 | When `cost_of(phase_id=…)`, Then phase-scoped totals | `tests/budgets/test_cost_manager.py::test_cost_of_phase` |
| 13 | When `walk cost --item FEAT-0001 --json`, Then JSON with categories and `total_usd` | `tests/cli/test_cmd_cost.py::test_cost_item_json` |

#### Evidence required
- Quality gate output.
- Demo: `walk cost --project` → `LLM | 0.00` … `total 0.00` on a fresh DB.

#### Notes
- `RELOCATE: BudgetPolicy → walk.budgets.models` (WBS §3.2). `NEW NAME: BudgetExhausted`.
- ARCHITECTURE §4.3: `BUDGET_EVENT`, `COST_RECORDED` written here; hooks `ON_BUDGET_THRESHOLD`/`ON_BUDGET_EXHAUSTED` default attachments are E02-S08.
- Commit: `feat: add budget metering and cost accounting (E01-S12)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S13 — Effort resolution: `EffortManager`

**Status:** TODO
**Type:** feat
**Requirements:** §17, §18, §19
**Depends on:** E01-S10, E01-S12
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Effective effort is resolved deterministically from role default, task complexity, risk, workflow stage, escalation and budget headroom; dynamic changes are evaluated per §19 and take effect on the next run.

#### Scope
- In: `effort.models` incl. RELOCATED `EffortPolicy`, `DefaultEffortManager.resolve/request_change`, static cost table + rolling mean hook.
- Out: provider mapping (`map_effort`, E01-S19/S21/S22), approval persistence (E02-S11) — `request_change` receives an injected `request_approval` callback.

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/effort/__init__.py` | create | re-exports |
| `src/walk/effort/models.py` | create | `EffortPolicy`, `EffortRequest`, `EffortResolution`, `EFFORT_ORDER`, `STATIC_COST_USD` |
| `src/walk/effort/protocols.py` | create | `EffortManager`, `CostEstimator` |
| `src/walk/effort/service.py` | create | `DefaultEffortManager`, `StaticCostEstimator` |
| `tests/effort/__init__.py` | create | — |
| `tests/effort/test_resolve.py` | create | — |
| `tests/effort/test_request_change.py` | create | — |

#### Interface contract
`EffortPolicy` = DOMAIN-MODEL §4.2 definition (relocated); `EffortRequest`, `EffortResolution` = DOMAIN-MODEL §4.3. Protocol: INTERFACES.md §1.5. Deltas:
```python
EFFORT_ORDER: tuple[Effort, ...] = (Effort.LOW, Effort.MEDIUM, Effort.HIGH, Effort.VERY_HIGH)
STATIC_COST_USD: dict[Effort, float] = {LOW: 1, MEDIUM: 3, HIGH: 8, VERY_HIGH: 20}   # ADR-0011 D-5
class CostEstimator(Protocol):
    def estimate(self, role: AgentRole, effort: Effort) -> float: ...
class StaticCostEstimator: ...   # STATIC_COST_USD; E09-S03 adds the rolling-mean estimator (>= 10 samples)
class DefaultEffortManager:
    def __init__(self, estimator: CostEstimator, ledger: LedgerManager, hooks: HookManager, clock: Clock,
                 request_approval: Callable[[RunId, EffortRequest], Awaitable[bool]]) -> None: ...
    def resolve(self, policy: EffortPolicy, item: WorkItem, state: WorkItemState, escalation_bump: int, budget_headroom: dict[BudgetDimension, float]) -> EffortResolution: ...
    async def request_change(self, run_id: RunId, current: Effort, request: EffortRequest, policy: EffortPolicy, headroom: dict[BudgetDimension, float]) -> Effort: ...
```

#### Behavior
1. `resolve` implements INTERFACES §5.2 steps 1–8 literally; items without a contract (EPIC/FEATURE) use `policy.default` as base.
2. `clamped_by_policy` is true iff step 6 changed the index; `clamped_by_budget` iff step 7 reduced it; missing `COST_USD` headroom means unlimited.
3. `resolve` is pure: no I/O, no ledger.
4. `request_change`: (a) target outside `[policy.min, policy.max]` → return `current`, no event; (b) UPGRADE with `auto_approve_upgrade_within_budget=False` → await `request_approval`; denied → return `current`; (c) UPGRADE whose `estimate(target) − estimate(current) > headroom[COST_USD]` → return `current` and fire nothing (observation is E04-S13); (d) otherwise fire `ON_EFFORT_CHANGE` and write `EFFORT_CHANGED` (payload: from, to, direction, reason) and return `target`.
5. DOWNGRADE never needs approval or budget.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given complexity NORMAL, default MEDIUM, risk MEDIUM, state READY, bump 0, Then `effective == MEDIUM` | `tests/effort/test_resolve.py::test_resolve_baseline_medium` |
| 2 | Given complexity SMALL (LOW) and default MEDIUM, Then floor keeps MEDIUM (step 2) | `tests/effort/test_resolve.py::test_role_default_is_a_floor` |
| 3 | Given risk CRITICAL (+2), Then HIGH→VERY_HIGH clamped by `policy.max=HIGH` with `clamped_by_policy` | `tests/effort/test_resolve.py::test_risk_bump_and_policy_clamp` |
| 4 | Given state REWORK, Then +1 stage bump | `tests/effort/test_resolve.py::test_stage_bump_for_rework` |
| 5 | Given escalation_bump 1, Then +1 | `tests/effort/test_resolve.py::test_escalation_bump_applied` |
| 6 | Given headroom COST_USD 2.5 and effective HIGH, Then downgraded to LOW with `clamped_by_budget` | `tests/effort/test_resolve.py::test_budget_headroom_downgrades` |
| 7 | Given no COST_USD headroom key, Then no budget clamp | `tests/effort/test_resolve.py::test_missing_headroom_is_unlimited` |
| 8 | Given a FEATURE (no contract), Then base is `policy.default` | `tests/effort/test_resolve.py::test_items_without_contract_use_default` |
| 9 | When `request_change(UPGRADE to VERY_HIGH)` with `max=HIGH`, Then returns current, no ledger | `tests/effort/test_request_change.py::test_target_outside_policy_is_denied` |
| 10 | Given auto-approve false and approval callback returns False, Then current | `tests/effort/test_request_change.py::test_upgrade_requires_approval_when_configured` |
| 11 | Given upgrade cost delta > headroom, Then current, no event | `tests/effort/test_request_change.py::test_upgrade_denied_by_budget` |
| 12 | Given valid upgrade, Then returns target, `ON_EFFORT_CHANGE` fired, `EFFORT_CHANGED` written | `tests/effort/test_request_change.py::test_upgrade_approved_fires_hook_and_ledger` |
| 13 | Given DOWNGRADE with no headroom, Then returns target | `tests/effort/test_request_change.py::test_downgrade_always_allowed` |

#### Evidence required
- Quality gate output.

#### Notes
- ADR-0011 D-5/D-6; INTERFACES §5.2. `RELOCATE: EffortPolicy → walk.effort.models`. `NEW NAME: CostEstimator`, `StaticCostEstimator`, `EFFORT_ORDER`, `STATIC_COST_USD`.
- Commit: `feat: add effort resolution and dynamic effort requests (E01-S13)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S14 — Tool and skill catalogues: `ToolRegistry`, `tools.yaml`, `Skill`/`SkillProjector` models

**Status:** TODO
**Type:** feat
**Requirements:** §28, §29, §30, §91 (tool allowlist)
**Depends on:** E01-S12
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The closed set of kernel tools exists as data with availability resolution and shell-command identification, and the skill data contracts adapters implement exist.

#### Scope
- In: `tools.models/protocols/service`, `src/walk/tools/builtin/tools.yaml`, `skills.models`, `skills.protocols.SkillProjector`.
- Out: `SkillRegistry` service and builtin skills (E02-S05), projections (E02-S06), permission rules (E01-S15).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/tools/__init__.py` | create | re-exports |
| `src/walk/tools/models.py` | create | `ToolKind`, `ToolSpec` |
| `src/walk/tools/protocols.py` | create | `ToolRegistry` |
| `src/walk/tools/service.py` | create | `DefaultToolRegistry`, `load_tool_specs` |
| `src/walk/tools/builtin/__init__.py` | create | — |
| `src/walk/tools/builtin/tools.yaml` | create | — |
| `src/walk/skills/__init__.py` | create | re-exports |
| `src/walk/skills/models.py` | create | `Skill`, `SkillProjection`, `DriftReport` |
| `src/walk/skills/protocols.py` | create | `SkillProjector`, `SkillRegistry` (protocol only; service in E02-S05) |
| `tests/tools/__init__.py`, `tests/skills/__init__.py` | create | — |
| `tests/tools/test_registry.py` | create | — |
| `tests/tools/test_builtin_tools.py` | create | — |
| `tests/skills/test_models.py` | create | — |

#### Interface contract
Models: DOMAIN-MODEL §3 `ToolKind`, §4.6 `ToolSpec`, `Skill`, `SkillProjection`, `DriftReport`. Protocols: INTERFACES.md §1.11 `ToolRegistry`, `SkillProjector`, `SkillRegistry`. Deltas:
```python
def load_tool_specs(paths: list[Path]) -> list[ToolSpec]: ...   # builtin yaml + project overrides; duplicate name → ConfigError
class DefaultToolRegistry:
    def __init__(self, specs: list[ToolSpec]) -> None: ...
```
`tools.yaml` rows (`name | kind | provider | protected_action | requires_env | command_patterns`):
PROVIDER_NATIVE: `bash`, `read`, `write`, `edit`, `glob`, `grep` · KERNEL/git: `git.commit`, `git.push`, `git.merge_protected` (protected `git.merge_protected`), `git.delete_branch_protected` (protected) · KERNEL/jira: `jira.create_task`, `jira.create_bug`, `jira.transition`, `jira.comment`, `jira.close_feature`, `jira.reopen`, `jira.delete` (protected) · KERNEL/kernel: `review.approve`, `review.reject`, `qc.approve`, `qc.reject`, `work.plan`, `permissions.alter` (protected), `credentials.change` (protected), `monetization.change` (protected), `repo.delete_data` (protected), `store.publish` (protected) · KERNEL/unity: `unity.compile`, `unity.run_tests`, `unity.build` (requires_env `unity`) · KERNEL/graphify: `graph.query`, `graph.neighbors` (requires_env `graphify`) · KERNEL/asset: `asset.generate` (requires_env `meshy|openart`). CLI patterns: `bash` identifies `^git\b`, `^dotnet\b`, `^graphify\b`, `^Unity(\.exe)?\b` as CLI sub-tools `git-cli`, `dotnet`, `graphify-cli`, `unity-cli` (kind CLI, `executable` set).

#### Behavior
1. `load_tool_specs` merges builtin then project files; a project row with an existing name replaces it; invalid rows → `ConfigError` with row index.
2. `available(ready_env_keys)` keeps specs whose `requires_env ⊆ ready_env_keys`; specs with `requires_env` containing `a|b` alternatives are available when any alternative is ready.
3. `for_role(allowed, ready, required)` = specs named in `allowed ∪ required` that are available; a required tool missing or unavailable → `ConfigError` listing it.
4. `identify(command)` returns the first CLI spec whose `command_patterns` regex matches the command start, else `None`.
5. `get(unknown)` → `ConfigError`.
6. `Skill.content_sha256` is the sha256 of `body_markdown`; `SkillProjection` is frozen.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `tools.yaml` loads, Then every tool name in the contract list exists with the stated kind | `tests/tools/test_builtin_tools.py::test_builtin_tools_cover_mvp_list` |
| 2 | Then every protected tool has `protected_action == name` | `tests/tools/test_builtin_tools.py::test_protected_tools_declare_protected_action` |
| 3 | Given a project yaml redefining `bash`, When loaded, Then the project row wins | `tests/tools/test_registry.py::test_project_override_replaces_builtin` |
| 4 | Given duplicate names within one file, Then `ConfigError` | `tests/tools/test_registry.py::test_duplicate_tool_name_rejected` |
| 5 | Given `ready={"git"}`, When `available`, Then unity tools excluded | `tests/tools/test_registry.py::test_available_filters_by_env` |
| 6 | Given `required=["unity.compile"]` and no unity env, When `for_role`, Then `ConfigError` names it | `tests/tools/test_registry.py::test_for_role_missing_required_raises` |
| 7 | When `identify("git status --porcelain")`, Then `git-cli`; `identify("ls")` → `None` | `tests/tools/test_registry.py::test_identify_matches_cli_patterns` |
| 8 | When `get("nope")`, Then `ConfigError` | `tests/tools/test_registry.py::test_get_unknown_raises` |
| 9 | When a `Skill` is built, Then `content_sha256` matches sha256 of body; `SkillProjection` immutable | `tests/skills/test_models.py::test_skill_hash_and_projection_frozen` |

#### Evidence required
- Quality gate output.

#### Notes
- §30 "Role → Skill → Tool → Provider"; ADR-0006 D-2 (kernel tools executed by the kernel); ADR-0007 D-6.
- `NEW NAME:` CLI sub-tool names `git-cli`, `dotnet`, `graphify-cli`, `unity-cli`; `load_tool_specs`.
- Commit: `feat: add tool registry with builtin catalogue and skill contracts (E01-S14)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S15 — Permission policy core: `PermissionManager.decide/rules_for`

**Status:** TODO
**Type:** feat
**Requirements:** §31, §63, §91, §92, §137 (Inv. 4, 7)
**Depends on:** E01-S14
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Pure, deterministic permission evaluation (ADR-0006 D-3) with default deny, plus persistence-only approval request storage so the enforcement point (E01-S26) can be built.

#### Scope
- In: `permissions.models`, `permissions.protocols`, `DefaultPermissionManager.rules_for/decide`, `ApprovalRepository`, persistence-only `request_approval/decide_approval/pending` (rows + ledger events, no run pausing/timeouts/CLI).
- Out: default rule set YAML, `permissions.yaml` loader, protected-action list config (E02-S10); run pausing, expiry, `walk approve/deny` (E02-S11).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/permissions/__init__.py` | create | re-exports |
| `src/walk/permissions/models.py` | create | `PermissionEffect`, `Approver`, `ApprovalState`, `PermissionRule`, `ProtectedAction`, `ToolCallRequest`, `PermissionDecision`, `ApprovalRequest` |
| `src/walk/permissions/protocols.py` | create | `PermissionManager` |
| `src/walk/permissions/matching.py` | create | `tool_pattern_specificity`, `match_tool`, `command_allowed`, `path_inside_worktree` |
| `src/walk/permissions/repository.py` | create | `ApprovalRepository` |
| `src/walk/permissions/service.py` | create | `DefaultPermissionManager` |
| `tests/permissions/__init__.py` | create | — |
| `tests/permissions/test_matching.py` | create | — |
| `tests/permissions/test_decide.py` | create | — |
| `tests/permissions/test_rules_for.py` | create | — |
| `tests/permissions/test_approvals.py` | create | — |

#### Interface contract
Models: DOMAIN-MODEL §3 permissions enums, §4.5 verbatim. Protocol: INTERFACES.md §1.10. Deltas:
```python
def tool_pattern_specificity(pattern: str) -> int: ...      # exact 3 > dotted prefix glob "git.*" 2 > "*" 1 > no match 0
def match_tool(pattern: str, tool: ToolName) -> bool: ...
def command_allowed(command: str, allow_rules: list[PermissionRule], deny_rules: list[PermissionRule]) -> tuple[bool, str]: ...
def path_inside_worktree(path: str, worktree: str) -> bool: ...   # resolves symlinks/.., Windows-safe
class DefaultPermissionManager:
    def __init__(self, rules: list[PermissionRule], protected: list[ProtectedAction], repo: ApprovalRepository, ledger: LedgerManager, hooks: HookManager, ids: IdSequenceStore, clock: Clock) -> None: ...
```

#### Behavior
1. `rules_for(role, extra)`: kernel rules for `role` + `extra`; duplicates `(tool, effect)` collapsed; an `extra`/project rule may only narrow: an `ALLOW` on a tool the kernel set denies or requires approval for is dropped with a logged warning (ADR-0013 D-4).
2. `decide`: collect rules for `request.role` matching `request.tool`; keep the most specific group; effect precedence `DENY > REQUIRE_APPROVAL > ALLOW`; no rule → `DENY("no matching rule")`.
3. If `request.tool` names a `ProtectedAction` (or the matching `ToolSpec.protected_action`), effect is forced to `REQUIRE_APPROVAL(approver=action.approver)` regardless of rules (D-3 "cannot be downgraded").
4. For shell tools (`request.command` set): must match at least one `command_patterns` entry of an ALLOW rule and none of a DENY rule; otherwise `DENY` with the offending pattern in `reason`.
5. For file tools (`request.paths` set): every path must be inside `request.worktree_path` and, when the matched rule has `path_patterns`, match one of them; otherwise `DENY`.
6. `request_approval` persists `ApprovalRequest(PENDING)` with `APV-` id, writes `APPROVAL_REQUESTED`, fires `ON_PROTECTED_ACTION_REQUESTED`; `decide_approval` sets `APPROVED|DENIED`, `decided_at/by/note`, writes `APPROVAL_DECIDED`; `pending(approver)` lists PENDING rows. Run pausing/wakeup and expiry are E02-S11.
7. `decide` is pure (no I/O) and never raises for well-formed requests.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When specificity of `git.commit`, `git.*`, `*`, `jira.*` vs tool `git.commit`, Then 3, 2, 1, 0 | `tests/permissions/test_matching.py::test_tool_pattern_specificity` |
| 2 | When `path_inside_worktree("../x", wt)`, Then False; a path via symlink outside → False | `tests/permissions/test_matching.py::test_path_inside_worktree_rejects_escapes` |
| 3 | Given ALLOW `git.*` and DENY `git.push`, When tool `git.push`, Then DENY (more specific) | `tests/permissions/test_decide.py::test_most_specific_rule_wins` |
| 4 | Given ALLOW and REQUIRE_APPROVAL with equal specificity, Then REQUIRE_APPROVAL | `tests/permissions/test_decide.py::test_precedence_deny_over_approval_over_allow` |
| 5 | Given no rule for the tool, Then DENY with reason `no matching rule` | `tests/permissions/test_decide.py::test_default_deny` |
| 6 | Given `bash` ALLOW with pattern `^pytest`, When command `rm -rf /`, Then DENY | `tests/permissions/test_decide.py::test_shell_command_must_match_allow_pattern` |
| 7 | Given DENY pattern `git push --force` and ALLOW `^git`, When `git push --force`, Then DENY naming the deny pattern | `tests/permissions/test_decide.py::test_shell_deny_pattern_overrides_allow` |
| 8 | Given file tool with a path outside the worktree, Then DENY | `tests/permissions/test_decide.py::test_file_path_outside_worktree_denied` |
| 9 | Given ALLOW `git.merge_protected` for LEAD_DEV and protected action configured, Then REQUIRE_APPROVAL(USER) | `tests/permissions/test_decide.py::test_protected_action_forces_approval` |
| 10 | Given extra rule ALLOW `jira.close_feature` for SENIOR_DEV while kernel denies it, When `rules_for`, Then the extra rule is dropped | `tests/permissions/test_rules_for.py::test_extra_rules_may_only_narrow` |
| 11 | Given duplicate rules, Then de-duplicated | `tests/permissions/test_rules_for.py::test_rules_for_deduplicates` |
| 12 | When `request_approval`, Then row PENDING with `APV-0001`, `APPROVAL_REQUESTED`, hook fired | `tests/permissions/test_approvals.py::test_request_approval_persists_and_logs` |
| 13 | When `decide_approval(id, True, by="user")`, Then APPROVED, `APPROVAL_DECIDED`; unknown id → `ConfigError` | `tests/permissions/test_approvals.py::test_decide_approval_updates_or_rejects` |
| 14 | When `pending(Approver.USER)`, Then only PENDING rows for USER | `tests/permissions/test_approvals.py::test_pending_filters_by_approver` |

#### Evidence required
- Quality gate output.

#### Notes
- ADR-0006 D-1/D-3/D-7; ADR-0013 D-4. Default rule set data lives in E02-S10; this story's tests construct rules inline.
- `NEW NAME:` module `walk.permissions.matching` and its functions.
- Commit: `feat: add permission evaluation core and approval persistence (E01-S15)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S16 — Memory core: front matter, `MemoryDocument`, atomic `write`, `apply_updates`, handovers, index

**Status:** TODO
**Type:** feat
**Requirements:** §6.2, §22, §34, §35, §41, §42 (stamping), §91 (secret isolation), §130, §137 (Inv. 2)
**Depends on:** E01-S05, E01-S07
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every `.ai/` document is parsed and written through one validated, atomic path that stamps freshness, refuses secrets, maintains `memory_index`, and supports section-level updates and handover documents.

#### Scope
- In: `memory.models` subset, front-matter parser/renderer, section-order tables, `DefaultMemoryManager.root/read/write/apply_updates/write_handover/read_handover/rebuild_index/write_report`, `MemoryIndexRepository`, `walk memory index`.
- Out: typed `FeatureContext/BugContext/ProjectContext` parsing (E04-S01), `assess_freshness` (E04-S03), `approve_artifact/verify_approved_artifacts` (E02-S12) — declared in the protocol, implemented there.

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/memory/__init__.py` | create | re-exports |
| `src/walk/memory/models.py` | create | `FreshnessStatus`, `MemoryDocType`, `ApprovedArtifactKind`, `ApprovalStatus`, `Freshness`, `FreshnessAssessment`, `RelatedLinks`, `FrontMatter`, `MemoryDocument`, `ContextUpdate`, `ApprovedArtifact`, `ProjectContext`, `FeatureContext`, `BugContext` |
| `src/walk/memory/protocols.py` | create | `MemoryManager` |
| `src/walk/memory/errors.py` | create | `DocumentNotFound`, `SecretDetected`, `ApprovedWriteRefused` |
| `src/walk/memory/frontmatter.py` | create | `parse_document`, `render_document` |
| `src/walk/memory/sections.py` | create | `SECTION_ORDER`, `sections_for`, `skeleton_for` |
| `src/walk/memory/secrets.py` | create | `SECRET_PATTERNS`, `find_secrets` |
| `src/walk/memory/paths.py` | create | `doc_path_for`, `folder_for_type` |
| `src/walk/memory/repository.py` | create | `MemoryIndexRepository`, `MemoryIndexRow` |
| `src/walk/memory/service.py` | create | `DefaultMemoryManager` |
| `src/walk/cli/cmd_memory.py` | create | `memory_app` |
| `src/walk/cli/app.py` | modify | registers `memory_app` |
| `tests/memory/__init__.py` | create | — |
| `tests/memory/test_frontmatter.py` | create | — |
| `tests/memory/test_sections.py` | create | — |
| `tests/memory/test_secrets.py` | create | — |
| `tests/memory/test_service_write.py` | create | — |
| `tests/memory/test_service_updates.py` | create | — |
| `tests/memory/test_index.py` | create | — |
| `tests/cli/test_cmd_memory.py` | create | — |

#### Interface contract
Models: DOMAIN-MODEL §3 memory enums, §4.7 verbatim. Protocol: INTERFACES.md §1.8 (`approve_artifact`, `verify_approved_artifacts`, `assess_freshness`, `read_feature_context`, `read_bug_context`, `read_project_context` raise `ConfigError("implemented in E02-S12 / E04-S01 / E04-S03")` until those stories). Deltas:
```python
def parse_document(path: Path, text: str) -> MemoryDocument: ...        # YAML front matter between leading '---' lines; H2 sections in order; unknown H2 kept
def render_document(doc: MemoryDocument) -> str: ...                    # deterministic: sorted-key YAML, sections in SECTION_ORDER then unknown in original order
SECTION_ORDER: dict[MemoryDocType, tuple[str, ...]]   # feature §37 (14), bug §38 (12), project §36 (10), handover §22 (10), decision §44 (11: Topic, Participants, Positions, Evidence, Outcome, Owner, Rationale, Alternatives, Affected Systems, Related Work, Version), approved §33 (Status, Scope, Version, Approved By, Related Requirements, Payload)
def skeleton_for(doc_type: MemoryDocType, id_: str, title: str, actor: Actor, now: datetime) -> MemoryDocument: ...   # all sections present, empty
SECRET_PATTERNS: tuple[re.Pattern[str], ...]   # r"AKIA[0-9A-Z]{16}", r"\bsk-[A-Za-z0-9]{20,}", r"\bghp_[A-Za-z0-9]{36}", r"\bATATT[A-Za-z0-9_-]{20,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
def find_secrets(text: str) -> list[str]: ...  # pattern names found
def doc_path_for(ai_root: Path, doc_type: MemoryDocType, id_: str) -> Path: ...   # ARCHITECTURE §8 layout; project → project/project.md
class DefaultMemoryManager:
    def __init__(self, ai_root: Path, index: MemoryIndexRepository, ledger: LedgerManager, hooks: HookManager, ids: IdSequenceStore, clock: Clock) -> None: ...
```

#### Behavior
1. `parse_document` raises `ConfigError` when front matter is missing, `id` ≠ file stem, or `type` unknown.
2. `write(doc, actor, head, branch)`: validate; `version = existing.version + 1` (1 for new); `updated_at = now`, `updated_by = actor`; `freshness = Freshness(commit=head, branch=branch, timestamp=now)` preserving `pr/build` if given; `find_secrets(rendered)` non-empty → `SecretDetected`, nothing written; path under `approved/` without `extra["change_request_decision"]` → `ApprovedWriteRefused`; write to `<path>.tmp` then `os.replace`; upsert `memory_index`; fire `ON_CONTEXT_UPDATED`; write `CONTEXT_UPDATED` (payload: doc_id, type, version, sections changed).
3. `apply_updates`: for each `ContextUpdate`, load the doc by `doc_id` (create `skeleton_for` when missing — type inferred from id prefix FEAT/BUG/`project`), REPLACE or APPEND the section (unknown section name → `ConfigError`), merge `relevant_files` into front matter, then one `write` per touched doc.
4. `write_handover(doc)` writes to `.ai/handovers/<id>.md` and writes `HANDOVER_CREATED` (payload: handover id, work item, reason) in addition to `CONTEXT_UPDATED`; `read_handover` returns the raw document or `DocumentNotFound`.
5. `rebuild_index` scans `.ai/**/*.md` (excluding `reports/`), parses, upserts rows, deletes rows whose files vanished, returns count.
6. `write_report(kind, subject_id, markdown)` writes `.ai/reports/<kind>/<subject_id>.md` without front-matter validation or index entry (ADR-0003 D-6).
7. `root()` returns the absolute `.ai/` path; `read(doc_id)` resolves via `memory_index` then falls back to `doc_path_for`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the ARCHITECTURE §8.2 sample document, When parsed then rendered, Then round-trip equality (modulo key order) and unknown H2 preserved | `tests/memory/test_frontmatter.py::test_parse_render_round_trip_preserves_unknown_sections` |
| 2 | Given a file whose `id` ≠ stem, Then `ConfigError` | `tests/memory/test_frontmatter.py::test_parse_rejects_id_mismatch` |
| 3 | When `SECTION_ORDER[FEATURE]`, Then the 14 §37 headings in order; `skeleton_for` produces all of them empty | `tests/memory/test_sections.py::test_feature_section_order_and_skeleton` |
| 4 | For each secret pattern, Given a matching string, Then `find_secrets` names it; clean text → `[]` | `tests/memory/test_secrets.py::test_secret_patterns_detect_and_pass` |
| 5 | When `write` a new feature doc, Then file exists, `version == 1`, freshness stamped with head/branch/now, index row, `ON_CONTEXT_UPDATED` fired, `CONTEXT_UPDATED` written | `tests/memory/test_service_write.py::test_write_new_document_stamps_and_indexes` |
| 6 | When `write` again, Then `version == 2` and no `.tmp` left behind | `tests/memory/test_service_write.py::test_write_bumps_version_atomically` |
| 7 | Given content with `AKIA…`, When `write`, Then `SecretDetected` and file unchanged | `tests/memory/test_service_write.py::test_write_refuses_secrets` |
| 8 | Given an `approved/` doc without change decision, Then `ApprovedWriteRefused` | `tests/memory/test_service_write.py::test_write_refuses_unauthorised_approved_change` |
| 9 | Given an injected failure after tmp write, Then original file intact | `tests/memory/test_service_write.py::test_write_is_atomic_on_failure` |
| 10 | When `apply_updates([REPLACE "Architecture"], [APPEND "Implementation Notes"])` on a missing FEAT doc, Then skeleton created, sections set/appended, `relevant_files` merged, one write | `tests/memory/test_service_updates.py::test_apply_updates_creates_skeleton_and_edits_sections` |
| 11 | When an update names an unknown section, Then `ConfigError` and no write | `tests/memory/test_service_updates.py::test_apply_updates_rejects_unknown_section` |
| 12 | When `write_handover`, Then `.ai/handovers/HO-0001.md` and `HANDOVER_CREATED`; `read_handover` returns it; unknown → `DocumentNotFound` | `tests/memory/test_service_updates.py::test_write_and_read_handover` |
| 13 | Given 3 docs on disk and a stale index row, When `rebuild_index`, Then 3 rows, stale removed, returns 3 | `tests/memory/test_index.py::test_rebuild_index_syncs_rows` |
| 14 | When `write_report("task", "STORY-0001", md)`, Then file written, no index row | `tests/memory/test_index.py::test_write_report_bypasses_index` |
| 15 | When `walk memory index`, Then prints count and exit 0 | `tests/cli/test_cmd_memory.py::test_memory_index_cli` |

#### Evidence required
- Quality gate output.
- Demo: `walk memory index` → `indexed 1 documents`.

#### Notes
- ADR-0003 D-2/D-4/D-6; ARCHITECTURE §8.2 front matter; §6 secret scan.
- `NEW NAME:` modules `walk.memory.sections`, `walk.memory.secrets`, `walk.memory.paths`, `walk.memory.frontmatter`; errors `DocumentNotFound`, `SecretDetected`, `ApprovedWriteRefused`.
- Pitfall: YAML dump must use `sort_keys=True`, `allow_unicode=True`, block style, so renders are deterministic (ADR-0012 D-7 depends on it).
- Commit: `feat: add memory document core with atomic writes and index (E01-S16)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S17 — Constitutions and runtime policies: loaders, merge rules, MVP role defaults

**Status:** TODO
**Type:** feat
**Requirements:** §8, §9, §12, §13, §14, §15, §105, §127, §137 (Inv. 1)
**Depends on:** E01-S13, E01-S15
**Effort:** HIGH   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Role constitutions and runtime policies load from kernel defaults merged with project overrides under narrowing rules, for the four MVP roles.

#### Scope
- In: `agents.models` (Constitution, ModelPolicy, RuntimePolicy, AgentInstance), `ConstitutionLoader`, `PolicyLoader`, `DefaultAgentManager.load_constitution/load_runtime_policy/list_roles`, default constitutions and `policies.yaml`.
- Out: execution contract models and `instantiate` (E01-S18), full constitution bodies (E03-S06), provider-name lint (E02-S15), narrowing on `authority` widening approvals (E05-S07).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/agents/__init__.py` | create | re-exports |
| `src/walk/agents/models.py` | create | `Constitution`, `ModelPolicy`, `RuntimePolicy`, `AgentInstance` |
| `src/walk/agents/protocols.py` | create | `AgentManager` |
| `src/walk/agents/errors.py` | create | `ConstitutionError` |
| `src/walk/agents/constitution_loader.py` | create | `ConstitutionLoader` |
| `src/walk/agents/policy_loader.py` | create | `PolicyLoader` |
| `src/walk/agents/service.py` | create | `DefaultAgentManager` |
| `src/walk/agents/defaults/orchestrator.md` | create | — |
| `src/walk/agents/defaults/lead_dev.md` | create | — |
| `src/walk/agents/defaults/senior_dev.md` | create | — |
| `src/walk/agents/defaults/qc.md` | create | — |
| `src/walk/agents/defaults/policies.yaml` | create | — |
| `src/walk/decisions/__init__.py` | create | re-exports |
| `src/walk/decisions/models.py` | create | `DecisionCategory`, `DecisionStatus`, `AutonomyLevel`, `Authority`, `EscalationRule`, `DecisionProposal`, `EscalationRequest`, `DecisionPosition`, `Decision`, `Escalation` |
| `tests/agents/__init__.py`, `tests/decisions/__init__.py` | create | — |
| `tests/agents/test_constitution_loader.py` | create | — |
| `tests/agents/test_policy_loader.py` | create | — |
| `tests/agents/test_defaults.py` | create | — |
| `tests/decisions/test_models.py` | create | — |

#### Interface contract
Models: DOMAIN-MODEL §4.2 (`Constitution`, `ModelPolicy`, `RuntimePolicy`, `AgentInstance` — `EffortPolicy`/`BudgetPolicy` imported from `walk.effort.models`/`walk.budgets.models`), §4.8 decisions models (needed by `Constitution.authority`; services in E04-S05/E05). Protocol: INTERFACES.md §1.2 (`instantiate`, `render_instructions` are E01-S18). Deltas:
```python
class ConstitutionLoader:
    def __init__(self, defaults_dir: Path, project_roles_dir: Path | None) -> None: ...
    def load(self, role: AgentRole) -> Constitution: ...     # ADR-0013 D-1..D-4; ConstitutionError on schema/merge violations
    def available_roles(self) -> list[AgentRole]: ...
class PolicyLoader:
    def __init__(self, defaults_path: Path, project_path: Path | None) -> None: ...
    def load(self, role: AgentRole) -> RuntimePolicy: ...    # deep-merge: project scalars/lists replace defaults per key
class DefaultAgentManager:
    def __init__(self, constitutions: ConstitutionLoader, policies: PolicyLoader, permissions: PermissionManager) -> None: ...
```
`policies.yaml` schema: `roles: {<ROLE>: {version, model_policy: {preferred: [family…], fallback, restricted, required_capabilities, cross_model_review, allow_task_override}, effort_policy: {...}, budget_policy: {...}, default_skills, allowed_tools, execution_strategy, max_parallel_runs, checkpoint_every_tool_calls}}` with ADR-0011 D-3 defaults for every `AgentRole` except USER/KERNEL. Default constitutions: front matter exactly as ADR-0013 D-2 for the role (ids `ORCHESTRATOR`, `LEAD_DEV`, `SENIOR_DEV`, `QC`; `version: "1.0"`; `authority` per ADR-0006 D-6; `tool_permissions` per ADR-0006 D-6), body sections ADR-0013 D-3 with one-paragraph placeholders derived from §10.1/§10.6/§10.7/§10.8.

#### Behavior
1. `ConstitutionLoader.load` parses `<defaults>/<role>.md` via `walk.memory.frontmatter.parse_document`, validates `type: constitution`, `role == id`, and builds `Constitution` (front matter authoritative, body sections → `body_markdown` in D-3 order).
2. Project override `.ai/agents/roles/<role>.md` (when present): scalars/lists replace; `authority.decision_scope`, `authority.may_approve/may_reject/may_create_work`, `tool_permissions`, `forbidden_actions` may only be narrowed (subset / lower `max_autonomy_level`) — widening raises `ConstitutionError` naming the field; body sections with the same name replace, new sections append.
3. Any field value containing a provider/model name (`claude`, `codex`, `gpt`, `anthropic`, `openai`, case-insensitive) raises `ConstitutionError` (ADR-0013 D-5; the `--strict` doctor lint in E02-S15 reuses this check).
4. `PolicyLoader.load` resolves model families to `ModelId`s? No — policies keep family strings (`claude/opus`) as `preferred`; `ModelId` pattern accepts them; resolution to concrete ids happens in E01-S20.
5. Unknown role in either loader → `ConstitutionError`; `list_roles` returns roles having a default constitution.
6. Loaders cache per instance; `reload()` is not provided (process restart).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | For each of the four default files, When loaded, Then valid `Constitution` with `version == "1.0"` and role matching file | `tests/agents/test_defaults.py::test_default_constitutions_load` |
| 2 | Then `LEAD_DEV.authority.decision_scope == [TECH]`, QC may create `[BUG]`, SENIOR_DEV `max_autonomy_level == 0` | `tests/agents/test_defaults.py::test_default_authorities_match_adr` |
| 3 | When `policies.yaml` loads for every MVP role, Then preferred/fallback families equal ADR-0011 D-3 | `tests/agents/test_defaults.py::test_default_policies_match_adr_0011` |
| 4 | Given an override lowering `max_autonomy_level` and removing a permission, When loaded, Then merged values applied | `tests/agents/test_constitution_loader.py::test_override_may_narrow` |
| 5 | Given an override adding `DESIGN` to LEAD_DEV `decision_scope`, Then `ConstitutionError` naming `authority.decision_scope` | `tests/agents/test_constitution_loader.py::test_override_widening_rejected` |
| 6 | Given an override with a new body section, Then appended after defaults; same-name section replaced | `tests/agents/test_constitution_loader.py::test_override_body_sections_merge` |
| 7 | Given a constitution mentioning `claude`, Then `ConstitutionError` | `tests/agents/test_constitution_loader.py::test_provider_names_rejected` |
| 8 | Given a file with `type: feature`, Then `ConstitutionError` | `tests/agents/test_constitution_loader.py::test_wrong_doc_type_rejected` |
| 9 | Given project `policies.yaml` overriding `checkpoint_every_tool_calls: 5` for SENIOR_DEV, Then merged policy has 5 and other defaults intact | `tests/agents/test_policy_loader.py::test_policy_deep_merge` |
| 10 | When `load(AgentRole.UA_RELEASE)` with no default, Then `ConstitutionError`; `list_roles()` == 4 MVP roles | `tests/agents/test_policy_loader.py::test_unknown_role_and_list_roles` |
| 11 | When `AutonomyLevel` compared, Then `USER > PO > MULTI_AGENT > LOCAL` (IntEnum) | `tests/decisions/test_models.py::test_autonomy_levels_ordered` |

#### Evidence required
- Quality gate output.

#### Notes
- ADR-0013 D-1–D-5, ADR-0011 D-3, ADR-0006 D-6. Decision models are created here because `Constitution` embeds `Authority`/`EscalationRule`; the decisions service arrives in E04-S05.
- `NEW NAME:` `ConstitutionLoader` (in ARCHITECTURE key classes), `PolicyLoader`, `ConstitutionError`.
- Commit: `feat: add constitution and runtime policy loading with role defaults (E01-S17)`.

#### Evidence (filled by implementer)
_pending_

<!-- CONTINUE -->
