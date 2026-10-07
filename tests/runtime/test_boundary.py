from pathlib import Path

from walk.memory.secrets import contains_secret
from walk.runtime import (
    DEFAULT_ALLOWED_PATHS,
    DEFAULT_FORBIDDEN_PATHS,
    EVIDENCE_EXCEPTIONS,
    DefaultBoundaryAuditor,
)


def _audit(worktree: Path, changed: list[str], allowed: list[str] | None = None) -> list[str]:
    return DefaultBoundaryAuditor().audit(
        str(worktree),
        changed,
        list(DEFAULT_ALLOWED_PATHS) if allowed is None else allowed,
        list(DEFAULT_FORBIDDEN_PATHS),
    )


def test_audit_flags_forbidden_and_outside_paths(tmp_path: Path) -> None:
    changed = [
        "src/A.cs",
        ".ai/agents/roles/qc.md",
        "../outside.txt",
        ".ai/features/FEAT-0001/evidence/log.txt",
        "secrets.env",
    ]

    violations = _audit(tmp_path, changed)

    assert violations == [".ai/agents/roles/qc.md", "../outside.txt", "secrets.env"]


def test_audit_enforces_allowed_paths(tmp_path: Path) -> None:
    violations = _audit(tmp_path, ["Assets/Player.cs", "Packages/x.json"], ["Assets/**"])

    assert violations == ["Packages/x.json"]


def test_audit_default_forbidden_paths(tmp_path: Path) -> None:
    changed = [
        ".ai/approved/APR-0001.md",
        ".ai/bugs/BUG-0001/run-1/evidence/trace.txt",
        ".ai/phases/PHASE-01/evidence/report.md",
        ".ai/features/FEAT-0001/notes.md",
        ".ai/evidence/stray.txt",
        ".walk/output.json",
        ".git/config",
        ".claude/skills/x/SKILL.md",
        ".codex/config.toml",
        "AGENTS.md",
        "docs/AGENTS.md",
        "ProjectSettings/ApiSecrets.asset",
        "config/prod.env",
        "Assets/Scripts/Player.cs",
    ]

    violations = _audit(tmp_path, changed)

    assert violations == [
        ".ai/approved/APR-0001.md",
        ".ai/features/FEAT-0001/notes.md",
        ".ai/evidence/stray.txt",
        ".walk/output.json",
        ".git/config",
        ".claude/skills/x/SKILL.md",
        ".codex/config.toml",
        "AGENTS.md",
        "docs/AGENTS.md",  # PurePosixPath.match anchors relative patterns at the right
        "ProjectSettings/ApiSecrets.asset",
        "config/prod.env",
    ]


def test_audit_resolves_absolute_and_backslash_paths(tmp_path: Path) -> None:
    inside = str(tmp_path / "src" / "B.cs")
    outside = str(tmp_path.parent / "elsewhere.cs")
    sneaky = "src/../../escape.cs"

    violations = _audit(tmp_path, [inside, outside, sneaky, "src\\C.cs"])

    assert violations == [outside, sneaky]


# ---- E02-S14 ---------------------------------------------------------------------------


def _scanning() -> DefaultBoundaryAuditor:
    return DefaultBoundaryAuditor(secret_scan=contains_secret)


def test_audit_rejects_path_outside_worktree(tmp_path: Path) -> None:
    violations = _scanning().audit(str(tmp_path), ["../outside.txt", "/etc/passwd"], ["**"], [])

    assert violations == ["../outside.txt", "/etc/passwd"]


def test_audit_rejects_agents_dir(tmp_path: Path) -> None:
    changed = [".ai/agents/roles/lead_dev.md", ".ai/approved/APR-0001/a.png"]

    assert _scanning().audit(str(tmp_path), changed, ["**"], []) == changed
    assert ".ai/agents/**" in DEFAULT_FORBIDDEN_PATHS
    assert ".ai/approved/**" in DEFAULT_FORBIDDEN_PATHS


def test_audit_allows_evidence_exception(tmp_path: Path) -> None:
    changed = [".ai/features/FEAT-0001/evidence/a.png", ".ai/bugs/BUG-0001/evidence/log.txt"]

    assert _scanning().audit(str(tmp_path), changed, ["**"], []) == []
    assert ".ai/features/*/evidence/**" in EVIDENCE_EXCEPTIONS
    strict = DefaultBoundaryAuditor(exceptions=())
    assert strict.audit(str(tmp_path), changed, ["**"], []) == changed


def test_audit_qc_may_not_write(tmp_path: Path) -> None:
    assert _scanning().audit(str(tmp_path), ["Assets/Player.cs"], [], []) == ["Assets/Player.cs"]


def test_audit_flags_secret_in_added_file(tmp_path: Path) -> None:
    key = "sk-ant-" + "a1b2c3d4" * 4  # assembled so this file holds no key
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "Config.cs").write_text(f'const string Key = "{key}";\n', encoding="utf-8")
    (tmp_path / "src" / "Clean.cs").write_text("class Clean {}\n", encoding="utf-8")
    (tmp_path / "art.bin").write_bytes(b"\x00\x01" + key.encode())
    (tmp_path / "big.txt").write_bytes(key.encode() + b"x" * (1024 * 1024))
    changed = ["src/Config.cs", "src/Clean.cs", "art.bin", "big.txt", "src/Deleted.cs"]

    violations = _scanning().audit(str(tmp_path), changed, ["**"], [])

    assert violations == ["SECRET:src/Config.cs"]
    assert DefaultBoundaryAuditor().audit(str(tmp_path), changed, ["**"], []) == []
