import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from walk.hooks import Hook, HookContext, HookFailPolicy, HookName, HookResult

ARCHITECTURE = Path(__file__).resolve().parents[2] / "docs" / "01-architecture" / "ARCHITECTURE.md"


def _documented_hook_names() -> list[str]:
    text = ARCHITECTURE.read_text(encoding="utf-8")
    section = text[text.index("### 4.1 Lifecycle hooks") : text.index("### 4.2 ")]
    names: list[str] = []
    for line in section.splitlines():
        if line.startswith("| `ON_"):
            names.extend(re.findall(r"`(ON_[A-Z_]+)`", line.split("|")[1]))
    return names


def test_hook_names_match_architecture_table() -> None:
    documented = _documented_hook_names()
    assert len(documented) == 45
    assert [hook.name for hook in HookName] == documented
    assert all(hook.value == hook.name.lower() for hook in HookName)


def test_hook_defaults() -> None:
    hook = Hook(name=HookName.ON_COMMIT, id="builtin.commit", kind="builtin")
    assert hook.priority == 100
    assert hook.fail_policy is HookFailPolicy.LOG_AND_CONTINUE
    assert hook.required is False
    assert hook.enabled is True
    assert hook.timeout_s == 120
    assert hook.callable_path is None


def test_hook_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        Hook.model_validate({"name": "on_commit", "id": "x", "kind": "plugin"})


def test_hook_context_and_result_are_frozen() -> None:
    ctx = HookContext(
        name=HookName.ON_TASK_START, at=datetime(2026, 1, 1, tzinfo=UTC), project_key="DEMO"
    )
    assert ctx.payload == {}
    result = HookResult(hook_id="builtin.x", status="OK", duration_ms=3)
    assert result.message == ""
    with pytest.raises(ValidationError):
        result.status = "FAILED"  # type: ignore[misc]  # asserting the frozen model rejects it
