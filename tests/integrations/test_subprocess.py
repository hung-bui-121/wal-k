import os
import sys
from pathlib import Path

import pytest

from tests.fakes.fake_subprocess import FakeSubprocessRunner
from walk.common.errors import Timeout
from walk.integrations import AsyncioSubprocessRunner, SubprocessRunner


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
