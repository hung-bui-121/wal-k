import sys
from pathlib import Path

import pytest

from tests.fakes.fake_shim import write_shim
from walk.model_router.adapters.codex.process import AsyncioCodexProcessLauncher


@pytest.mark.skipif(sys.platform != "win32", reason="Windows shim")
async def test_launch_refuses_unsafe_argument_to_batch_shim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "ran.txt"
    write_shim(tmp_path, "codex", output="codex-cli 0.160.1", marker=marker)
    monkeypatch.setenv("PATH", str(tmp_path))
    launcher = AsyncioCodexProcessLauncher()

    with pytest.raises(PermissionError, match="unsafe for batch file"):
        await launcher.launch(["codex", "exec", "a&b"], cwd=str(tmp_path), env={})

    assert not marker.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows shim")
async def test_version_probe_runs_cmd_shim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_shim(tmp_path, "codex", output="codex-cli 0.160.1")
    monkeypatch.setenv("PATH", str(tmp_path))

    ok, text = await AsyncioCodexProcessLauncher().version()

    assert ok is True
    assert "0.160.1" in text
