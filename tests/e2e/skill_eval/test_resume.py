"""Tests for resuming and merging a ladder run — written before `resume.py` exists.

Spawns nothing. Every input here is a dict on disk, so this file is safe to run as part of the
unit sweep.
"""

from __future__ import annotations

import json
import os

import pytest

from tests.e2e.skill_eval import resume

ARM_NAMES = ("bare", "tools", "tools+skills")


def record(task, arm, passed, **extra):
    row = {
        "task_id": task,
        "arm": arm,
        "passed": passed,
        "reason": None,
        "run_index": 0,
        "seconds": 1.0,
        "session_seconds": 1.0,
        "calls": [],
        "tool_calls": 0,
        "timed_out": False,
    }
    row.update(extra)
    return row


def write(tmp_path, name, rows):
    path = os.path.join(str(tmp_path), name)
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    return path


def triple(task, passed=(False, True, True)):
    return [record(task, arm, ok) for arm, ok in zip(ARM_NAMES, passed)]


# --- reading ---------------------------------------------------------------------------------------


def test_read_sessions_returns_one_dict_per_line(tmp_path):
    path = write(tmp_path, "a.runs.jsonl", triple("CORPUS-01"))
    rows = resume.read_sessions(path)
    assert [row["arm"] for row in rows] == list(ARM_NAMES)


def test_read_sessions_refuses_a_line_that_is_not_a_session(tmp_path):
    path = os.path.join(str(tmp_path), "bad.runs.jsonl")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"arm": "tools"}) + "\n")
    with pytest.raises(resume.ResumeRefused):
        resume.read_sessions(path)


# --- what is left to run ---------------------------------------------------------------------------


def test_remaining_names_a_task_whose_triple_is_incomplete(tmp_path):
    rows = triple("CORPUS-01") + triple("CORPUS-02")[:2]
    path = write(tmp_path, "a.runs.jsonl", rows)
    assert resume.remaining(
        ["CORPUS-01", "CORPUS-02", "CORPUS-03"], [path], arms=ARM_NAMES
    ) == ["CORPUS-02", "CORPUS-03"]


def test_remaining_treats_an_unscored_session_as_not_run(tmp_path):
    rows = triple("CORPUS-01")
    rows[2]["passed"] = None
    rows[2]["reason"] = "the check did not answer"
    path = write(tmp_path, "a.runs.jsonl", rows)
    assert resume.remaining(["CORPUS-01"], [path], arms=ARM_NAMES) == ["CORPUS-01"]


def test_remaining_is_empty_when_every_triple_is_scored(tmp_path):
    path = write(tmp_path, "a.runs.jsonl", triple("CORPUS-01"))
    assert resume.remaining(["CORPUS-01"], [path], arms=ARM_NAMES) == []


# --- merging ---------------------------------------------------------------------------------------


def test_merge_prefers_the_later_file_for_the_same_task_and_arm(tmp_path):
    first = write(tmp_path, "a.runs.jsonl", triple("CORPUS-01", (False, False, False)))
    second = write(tmp_path, "b.runs.jsonl", triple("CORPUS-01", (False, True, True)))
    merged = resume.merge_sessions([first, second])
    assert len(merged) == 3
    assert {row["arm"]: row["passed"] for row in merged} == {
        "bare": False,
        "tools": True,
        "tools+skills": True,
    }


def test_merge_keeps_a_scored_session_over_a_later_unscored_one(tmp_path):
    first = write(tmp_path, "a.runs.jsonl", [record("CORPUS-01", "tools", True)])
    second = write(
        tmp_path,
        "b.runs.jsonl",
        [record("CORPUS-01", "tools", None, reason="IRIS gone")],
    )
    merged = resume.merge_sessions([first, second])
    assert [row["passed"] for row in merged] == [True]


def test_merge_is_sorted_by_task_then_by_arm_order(tmp_path):
    path = write(
        tmp_path,
        "a.runs.jsonl",
        [
            record("CORPUS-02", "tools", True),
            record("CORPUS-01", "tools+skills", True),
            record("CORPUS-01", "bare", False),
        ],
    )
    merged = resume.merge_sessions([path], arms=ARM_NAMES)
    assert [(row["task_id"], row["arm"]) for row in merged] == [
        ("CORPUS-01", "bare"),
        ("CORPUS-01", "tools+skills"),
        ("CORPUS-02", "tools"),
    ]


def test_merge_refuses_an_empty_input(tmp_path):
    with pytest.raises(resume.ResumeRefused):
        resume.merge_sessions([])


def test_unscored_lists_the_sessions_that_carry_no_verdict(tmp_path):
    rows = triple("CORPUS-01")
    rows[0]["passed"] = None
    rows[0]["reason"] = "the check did not answer"
    path = write(tmp_path, "a.runs.jsonl", rows)
    holes = resume.unscored(resume.merge_sessions([path]))
    assert [(row["task_id"], row["arm"]) for row in holes] == [("CORPUS-01", "bare")]


# --- runs, for the report --------------------------------------------------------------------------


def test_arm_runs_rebuilds_objects_the_report_can_read(tmp_path):
    path = write(tmp_path, "a.runs.jsonl", triple("CORPUS-01"))
    runs = resume.arm_runs(resume.merge_sessions([path]))
    assert [run.arm for run in runs] == list(ARM_NAMES)
    assert runs[1].passed is True
    assert runs[0].task_id == "CORPUS-01"


def test_arm_runs_drops_the_unscored_when_asked(tmp_path):
    rows = triple("CORPUS-01")
    rows[0]["passed"] = None
    path = write(tmp_path, "a.runs.jsonl", rows)
    merged = resume.merge_sessions([path])
    assert len(resume.arm_runs(merged, scored_only=True)) == 2
    assert len(resume.arm_runs(merged)) == 3
