from pathlib import Path

from walk.runtime import DEFAULT_ALLOWED_PATHS, DEFAULT_FORBIDDEN_PATHS, DefaultBoundaryAuditor


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
