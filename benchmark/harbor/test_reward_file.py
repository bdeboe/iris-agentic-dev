"""The reward contract — 120 T014, written before the script it tests.

FR-004 says the reward reaches the harness as a file. The interesting case is the third one: a check
that answered neither PASS nor FAIL has graded nothing, and writing `0` for it files a harness fault
in the arm's column. That is `graded_task.CheckBroken` in bash, and Harbor reads a missing reward file
as a trial with no reward rather than as a failure.

The generated `tests/test.sh` runs here for real — no Docker — against a stub `iris-agentic-dev` on
`PATH`, with `REWARD_DIR` pointed at a temp directory. That override exists so this contract is
testable at all: `/logs/verifier` is Harbor's path inside a container and is not writable here.
"""

from __future__ import annotations

import os
import stat
import subprocess

import pytest

from benchmark.harbor.export import export_task
from tests.e2e.skill_eval.arms import TOOLS
from tests.e2e.skill_eval.graded_task import Document, GradedTask

TASK = GradedTask(
    id="EX-02",
    prompt="Fix Ex.Buggy.\n",
    check='write $select(1=1:"PASS",1:"FAIL")\n',
    fixtures=(Document(name="Ex.Buggy", content="Class Ex.Buggy { broken }\n"),),
    solution=(Document(name="Ex.Buggy", content="Class Ex.Buggy { }\n"),),
)


def run_verifier(tmp_path, *, output: str, exit_code: int = 0):
    """Export the task, stub the CLI, run the verifier, and report what it wrote."""
    exported = export_task(
        TASK, TOOLS, str(tmp_path / "out"), validate=lambda task: None
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "iris-agentic-dev"
    stub.write_text(f"#!/bin/bash\nprintf '%s\\n' {output!r}\nexit {exit_code}\n")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

    reward_dir = tmp_path / "logs" / "verifier"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "REWARD_DIR": str(reward_dir),
    }
    # `test.sh` reads `IAD_BINARY` before falling back to `PATH`, so a shell that exports it — which
    # is how the live tests in this repo are run — would reach the real CLI and never see the stub.
    # Every case below then reports whatever the container answered instead of the stubbed output.
    env.pop("IAD_BINARY", None)
    result = subprocess.run(
        [os.path.join(exported.directory, "tests", "test.sh")],
        capture_output=True,
        text=True,
        env=env,
    )
    reward_file = reward_dir / "reward.txt"
    written = reward_file.read_text().strip() if reward_file.exists() else None
    return result, written


def test_a_passing_check_writes_a_reward_of_one(tmp_path):
    result, written = run_verifier(tmp_path, output="PASS")
    assert result.returncode == 0, result.stderr
    assert written == "1.0"


def test_a_failing_check_writes_a_reward_of_zero(tmp_path):
    result, written = run_verifier(tmp_path, output="FAIL")
    assert result.returncode == 0, result.stderr
    assert written == "0.0"


@pytest.mark.parametrize(
    "output",
    [
        "ERROR #5002: ObjectScript error",
        "PASS and FAIL",  # both words: `check_verdict`'s third answer
        "",
    ],
)
def test_a_check_that_answered_nothing_writes_no_reward_at_all(tmp_path, output):
    """Not a zero. An unreadable check is the harness's problem, and Harbor's missing-reward path is
    the honest one — the same rule `DriverRun` enforces with `scored=False`."""
    result, written = run_verifier(tmp_path, output=output)
    assert written is None
    assert result.returncode != 0
    assert "PASS" in result.stderr or "FAIL" in result.stderr


def test_a_check_that_could_not_run_writes_no_reward_either(tmp_path):
    """A non-zero exit from the CLI means the check never ran, which is not a failed task."""
    result, written = run_verifier(tmp_path, output="PASS", exit_code=3)
    assert written is None
    assert result.returncode != 0
