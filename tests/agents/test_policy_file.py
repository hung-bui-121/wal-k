from pathlib import Path

import pytest

from walk.agents.errors import ConstitutionError
from walk.agents.policy_file import PoliciesFile, update_model_policy
from walk.common.roles import AgentRole

PROJECT = (
    "# Project overrides of the kernel runtime policies.\n"
    "roles:\n"
    "  LEAD_DEV:\n"
    "    model_policy: {preferred: [claude/opus], fallback: []}  # reviewer\n"
    "    max_parallel_runs: 1\n"
    "\n"
    "  SENIOR_DEV:\n"
    "    model_policy: {preferred: [codex/default], fallback: [claude/sonnet]}\n"
    "    checkpoint_every_tool_calls: 5\n"
    "  QC:\n"
    "    max_parallel_runs: 2\n"
)


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "policies.yaml"
    path.write_bytes(text.encode("utf-8"))
    return path


def _block(text: str, role: str) -> list[str]:
    lines = text.splitlines()
    start = lines.index(f"  {role}:")
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if lines[i].startswith("  ") and lines[i][2] != " "
        ),
        len(lines),
    )
    return lines[start:end]


def test_update_model_policy_changes_single_role(tmp_path: Path) -> None:
    path = _write(tmp_path, PROJECT)

    policy = update_model_policy(
        path, AgentRole.SENIOR_DEV, ["claude/opus"], ["codex/default", "claude/sonnet"]
    )

    text = path.read_text(encoding="utf-8")
    assert _block(text, "LEAD_DEV") == _block(PROJECT, "LEAD_DEV")
    assert _block(text, "QC") == _block(PROJECT, "QC")
    assert text.startswith("# Project overrides of the kernel runtime policies.\nroles:\n")
    roles = PoliciesFile.load(path).roles
    assert roles[AgentRole.SENIOR_DEV] == {
        "model_policy": {
            "preferred": ["claude/opus"],
            "fallback": ["codex/default", "claude/sonnet"],
        },
        "checkpoint_every_tool_calls": 5,
    }
    assert policy.role is AgentRole.SENIOR_DEV
    assert policy.model_policy.preferred == ["claude/opus"]
    assert policy.checkpoint_every_tool_calls == 5
    assert not list(tmp_path.glob("*.check"))
    assert not list(tmp_path.glob("*.tmp"))


def test_update_model_policy_adds_a_missing_role_or_file(tmp_path: Path) -> None:
    path = _write(tmp_path, PROJECT)
    update_model_policy(path, AgentRole.ORCHESTRATOR, ["claude/opus"], [])
    created = tmp_path / "new" / "policies.yaml"
    update_model_policy(created, AgentRole.QC, ["claude/sonnet"], ["claude/opus"])
    (tmp_path / "x").mkdir()
    headless = _write(tmp_path / "x", "# nothing yet\n")
    update_model_policy(headless, AgentRole.QC, ["claude/sonnet"], [])

    roles = PoliciesFile.load(path).roles
    assert roles[AgentRole.ORCHESTRATOR] == {
        "model_policy": {"preferred": ["claude/opus"], "fallback": []}
    }
    assert _block(path.read_text(encoding="utf-8"), "QC") == _block(PROJECT, "QC")
    assert PoliciesFile.load(created).roles[AgentRole.QC]["model_policy"]["preferred"] == [
        "claude/sonnet"
    ]
    assert headless.read_text(encoding="utf-8").startswith("# nothing yet\n\nroles:\n")


def test_policies_file_load_and_write(tmp_path: Path) -> None:
    assert PoliciesFile.load(tmp_path / "absent.yaml") == PoliciesFile()
    assert PoliciesFile.load(_write(tmp_path, "")) == PoliciesFile()
    loaded = PoliciesFile.load(_write(tmp_path, PROJECT))

    written = loaded.write(tmp_path / "copy.yaml")

    assert PoliciesFile.load(written) == loaded
    for broken in ("roles: [unclosed\n", "roles:\n  NOBODY: {}\n", "other: 1\n"):
        with pytest.raises(ConstitutionError):
            PoliciesFile.load(_write(tmp_path, broken))


def test_invalid_update_leaves_the_file_unchanged(tmp_path: Path) -> None:
    text = "roles:\n  SENIOR_DEV:\n    execution_strategy: nope\n"
    path = _write(tmp_path, text)

    with pytest.raises(ConstitutionError):
        update_model_policy(path, AgentRole.SENIOR_DEV, ["claude/opus"], [])

    assert path.read_text(encoding="utf-8") == text


def test_splice_respects_following_keys_blank_lines_and_failed_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = (
        "roles:\n"
        "  SENIOR_DEV:\n"
        "    checkpoint_every_tool_calls: 5\n"
        "\n"
        "\n"
        "  QC:\n"
        "    max_parallel_runs: 2\n"
        "\n"
        "# trailing comment\n"
    )
    path = _write(tmp_path, text)

    update_model_policy(path, AgentRole.SENIOR_DEV, ["codex/default"], [])
    update_model_policy(path, AgentRole.LEAD_DEV, ["codex/default"], [])

    updated = path.read_text(encoding="utf-8")
    assert updated.endswith("# trailing comment\n")
    assert "  QC:\n    max_parallel_runs: 2\n" in updated
    assert PoliciesFile.load(path).roles[AgentRole.LEAD_DEV]["model_policy"]["preferred"] == [
        "codex/default"
    ]

    def refuse(self: Path, target: Path) -> Path:
        del self, target
        msg = "disk full"
        raise OSError(msg)

    before = path.read_bytes()
    monkeypatch.setattr(Path, "replace", refuse)
    with pytest.raises(OSError, match="disk full"):
        update_model_policy(path, AgentRole.QC, ["codex/default"], [])
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))
