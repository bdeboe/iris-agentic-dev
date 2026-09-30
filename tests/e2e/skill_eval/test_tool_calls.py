"""`tool_calls list <run_id>` — 132 T034 (User Story 5, FR-016), written before the code.

The FR-016 decision for a failed repeat (skill edit, tool proposal, or none) has to cite the calls the
session made, and a raw opencode stream is thousands of lines of JSON. This lists each session's calls,
one line each, so a failed repeat's calls can be assigned to a step by call number.

The fixture is a hand-trimmed opencode stream: three calls, one of them an error with a newline in it.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from tests.e2e.skill_eval import tool_calls

REPO = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).parent / "fixtures" / "tool_calls_session.jsonl"


def _results(tmp_path, names):
    run = tmp_path / "2026-09-30T120000.transcripts"
    run.mkdir()
    for name in names:
        shutil.copy(FIXTURE, run / name)
    return tmp_path


def test_each_session_is_a_block_and_each_call_a_line(tmp_path, capsys):
    results = _results(tmp_path, ["SKILL-22__tools__r0.jsonl"])

    assert (
        tool_calls.main(["list", "2026-09-30T120000", "--results", str(results)]) == 0
    )

    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "== SKILL-22 tools repeat=0 =="
    assert lines[1].split("\t")[:3] == ["1", "skill", "ok"]
    assert lines[2].split("\t")[:3] == ["2", "iris_execute", "ok"]
    assert lines[3].split("\t")[:3] == ["3", "iris_doc", "err"]
    assert len(lines) == 4


def test_the_text_is_the_first_120_characters_with_newlines_shown(tmp_path, capsys):
    results = _results(tmp_path, ["SKILL-22__tools__r0.jsonl"])

    tool_calls.main(["list", "2026-09-30T120000", "--results", str(results)])

    lines = capsys.readouterr().out.splitlines()
    first = lines[1].split("\t", 3)[3]
    assert first.startswith('<skill_content name="iris-ai-hub">⏎# Skill')
    error = lines[3].split("\t", 3)[3]
    assert error.startswith("COMPILE_ERROR: IadAihub139.Q22.Agent⏎ERROR #5559")
    for line in lines[1:]:
        assert len(line.split("\t", 3)[3]) <= 120
        assert "\n" not in line


def test_blocks_come_in_task_arm_repeat_order(tmp_path, capsys):
    results = _results(
        tmp_path,
        [
            "SKILL-24__tools__r1.jsonl",
            "SKILL-22__tools+iris-ai-hub__r0.jsonl",
            "SKILL-24__tools__r0.jsonl",
            "SKILL-22__tools__r2.jsonl",
        ],
    )

    tool_calls.main(["list", "2026-09-30T120000", "--results", str(results)])

    headers = [
        line for line in capsys.readouterr().out.splitlines() if line.startswith("==")
    ]
    assert headers == [
        "== SKILL-22 tools repeat=2 ==",
        "== SKILL-22 tools+iris-ai-hub repeat=0 ==",
        "== SKILL-24 tools repeat=0 ==",
        "== SKILL-24 tools repeat=1 ==",
    ]


def test_a_missing_transcripts_directory_exits_2_naming_the_path(tmp_path, capsys):
    assert tool_calls.main(["list", "no-such-run", "--results", str(tmp_path)]) == 2

    err = capsys.readouterr().err
    assert str(tmp_path / "no-such-run.transcripts") in err


def test_it_runs_as_a_module(tmp_path):
    results = _results(tmp_path, ["SKILL-23__tools__r0.jsonl"])

    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.e2e.skill_eval.tool_calls",
            "list",
            "2026-09-30T120000",
            "--results",
            str(results),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )

    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("== SKILL-23 tools repeat=0 ==")
