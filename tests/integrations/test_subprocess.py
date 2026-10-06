import asyncio
import os
import sys
from pathlib import Path

import pytest

from tests.fakes.fake_shim import write_shim
from tests.fakes.fake_subprocess import FakeSubprocessRunner
from walk.common.errors import Timeout
from walk.integrations import AsyncioSubprocessRunner, SubprocessRunner
from walk.integrations.subprocess import (
    BATCH_UNSAFE_CHARS,
    resolve_executable,
    unsafe_batch_argument,
)


async def test_runner_returns_result_without_raising() -> None:
    runner: SubprocessRunner = AsyncioSubprocessRunner()

    ok = await runner.run([sys.executable, "-c", "print(1)"])
    failed = await runner.run([sys.executable, "-c", "import sys; sys.exit(3)"])

    assert ok.exit_code == 0
    assert ok.stdout.strip() == "1"
    assert ok.argv == [sys.executable, "-c", "print(1)"]
    assert ok.duration_ms >= 0
    assert failed.exit_code == 3


async def test_runner_timeout_kills_and_raises() -> None:
    runner = AsyncioSubprocessRunner()

    with pytest.raises(Timeout) as info:
        await runner.run([sys.executable, "-c", "import time; time.sleep(30)"], timeout_s=1)

    assert info.value.detail["timeout_s"] == 1


async def test_fake_runner_scripts_and_records() -> None:
    fake = FakeSubprocessRunner()
    fake.script(["git"], exit_code=1, stderr="generic")
    fake.script(["git", "rev-parse"], stdout="abc\n")
    runner: SubprocessRunner = fake

    result = await runner.run(["git", "rev-parse", "HEAD"], cwd="/repo", timeout_s=5)
    other = await runner.run(["git", "status"])

    assert result.stdout == "abc\n"
    assert result.exit_code == 0
    assert other.exit_code == 1
    assert fake.argvs == [["git", "rev-parse", "HEAD"], ["git", "status"]]
    assert fake.calls[0].cwd == "/repo"
    assert fake.calls[0].timeout_s == 5
    with pytest.raises(AssertionError, match="unscripted"):
        await runner.run(["unity"])


async def test_fake_runner_raises_scripted_error() -> None:
    fake = FakeSubprocessRunner()
    fake.script(["git"], error=Timeout("slow"))

    with pytest.raises(Timeout):
        await fake.run(["git", "status"])


async def test_runner_writes_input_and_uses_cwd(tmp_path: Path) -> None:
    runner = AsyncioSubprocessRunner()
    script = "import os, sys; print(sys.stdin.read().upper()); print(os.getcwd())"

    result = await runner.run([sys.executable, "-c", script], cwd=str(tmp_path), input_text="hi")

    lines = result.stdout.splitlines()
    assert lines[0] == "HI"
    assert Path(lines[1]).resolve() == tmp_path.resolve()  # noqa: ASYNC240 - test assertion


async def test_runner_env_dict_replaces_environment() -> None:
    runner = AsyncioSubprocessRunner()
    env = {"WALK_TEST_ONLY": "yes"}
    if "SYSTEMROOT" in os.environ:  # Windows Python needs SYSTEMROOT to start
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    script = "import os; print(os.environ.get('WALK_TEST_ONLY'), 'PATH' in os.environ)"

    result = await runner.run([sys.executable, "-c", script], env=env)

    assert result.stdout.split() == ["yes", "False"]


async def test_runner_missing_executable_returns_127() -> None:
    runner = AsyncioSubprocessRunner()

    result = await runner.run(["walk-no-such-executable-xyz"])

    assert result.exit_code == 127  # POSIX "command not found"
    assert "not found" in result.stderr


def _child_env(path: str) -> dict[str, str]:
    """A minimal explicit environment; a `.cmd` child also needs SystemRoot and ComSpec."""
    env = {"PATH": path}
    for name in ("SYSTEMROOT", "COMSPEC"):
        if name in os.environ:
            env[name] = os.environ[name]
    return env


@pytest.mark.skipif(sys.platform != "win32", reason="Windows shim")
async def test_run_resolves_windows_cmd_shim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_shim(tmp_path, "fake-tool", output="fake-tool 1.2.3")
    monkeypatch.setenv("PATH", str(tmp_path))

    result = await AsyncioSubprocessRunner().run(["fake-tool", "--version"])

    assert result.exit_code == 0, result.stderr
    assert "1.2.3" in result.stdout
    assert result.argv == ["fake-tool", "--version"]


async def test_run_resolves_against_the_env_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    write_shim(tools, "walk-env-only-tool", output="env-only 4.5.6")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    result = await AsyncioSubprocessRunner().run(["walk-env-only-tool"], env=_child_env(str(tools)))

    assert result.exit_code == 0, result.stderr
    assert "4.5.6" in result.stdout


async def test_run_unknown_executable_reports_127(tmp_path: Path) -> None:
    runner = AsyncioSubprocessRunner()

    inherited = await runner.run(["walk-no-such-executable-xyz"])
    explicit = await runner.run(["walk-no-such-executable-xyz"], env=_child_env(str(tmp_path)))

    for result in (inherited, explicit):
        assert result.exit_code == 127
        assert result.stderr.startswith("executable not found")
        assert "walk-no-such-executable-xyz" in result.stderr


@pytest.mark.skipif(sys.platform != "win32", reason="Windows shim")
async def test_run_refuses_unsafe_argument_to_batch_shim(tmp_path: Path) -> None:
    marker = tmp_path / "ran.txt"
    shim = write_shim(tmp_path, "fake-tool", output="ran", marker=marker)

    result = await AsyncioSubprocessRunner().run([str(shim), "a&b"])

    assert result.exit_code == 126
    assert "refused" in result.stderr
    assert "argument 1" in result.stderr
    assert not marker.exists()


def test_unsafe_batch_argument_detection() -> None:
    assert unsafe_batch_argument("C:/x/codex.CMD", ["exec", "a%PATH%"]) == 1
    assert unsafe_batch_argument("C:/x/codex.exe", ["exec", "a%PATH%"]) is None
    assert unsafe_batch_argument("/usr/bin/tool.bat", ["plain", "words only"]) is None
    for char in BATCH_UNSAFE_CHARS:
        assert unsafe_batch_argument("tool.bat", ["ok", f"x{char}y"]) == 1


def test_resolve_executable_matches_env_path_key_case_insensitively_on_windows(
    tmp_path: Path,
) -> None:
    write_shim(tmp_path, "walk-case-tool", output="case 1.0")
    key = "Path" if sys.platform == "win32" else "PATH"

    resolved = resolve_executable("walk-case-tool", {key: str(tmp_path)})

    assert resolved is not None
    assert Path(resolved).parent == tmp_path
    assert resolve_executable("walk-case-tool", {"OTHER": "x"}) is None


async def test_run_executable_removed_before_spawn_reports_127(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def vanished(*_args: object, **_kwargs: object) -> None:
        msg = "gone"
        raise FileNotFoundError(msg)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", vanished)

    result = await AsyncioSubprocessRunner().run([sys.executable, "-c", "print(1)"])

    assert result.exit_code == 127
    assert result.stderr.startswith("executable not found")


def test_resolve_executable_env_path_key_is_exact_off_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_shim(tmp_path, "walk-case-tool", output="case 1.0")
    monkeypatch.setattr("sys.platform", "linux")

    # "Path" is not PATH on POSIX: the lookup falls back to the kernel PATH, which lacks the tool.
    assert resolve_executable("walk-case-tool", {"Path": str(tmp_path)}) is None
