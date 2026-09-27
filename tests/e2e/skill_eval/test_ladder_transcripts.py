"""Transcripts and the triage rule — 130 T015 (User Story 4, FR-009, FR-010), written before the code.

The first 130 ladder run lost SKILL-13, SKILL-14 and SKILL-16 with the skill loaded and kept nothing
but call names, so there was no sentence to point at. Round 2 keeps every session's raw event stream,
and decides which skills get fixed by a rule in code rather than by reading the table:

- a skill is flagged on a task when its arm FAILED at least 2 scored runs and the tools arm PASSED at
  least 2 (grill round 2, Q6: majority against majority);
- an unscored run counts for neither side, and a task with fewer than 2 scored runs on either arm is
  `unmeasured`, never flagged.

No session starts here. The driver is scripted, as in `test_pilot.py`.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.e2e.skill_eval.arms import TOOLS, skill_arm
from tests.e2e.skill_eval.pilot import ArmRun
from tests.e2e.skill_eval.test_ladder import FakeTask
from tests.e2e.skill_eval.test_pilot import RecordingDriver, fake_task

REPO = Path(__file__).resolve().parents[3]


def _run(task_id, arm, passed, run_index=0):
    return ArmRun(
        task_id=task_id,
        arm=arm,
        passed=passed,
        reason=None if passed is not None else "the check did not answer",
        run_index=run_index,
    )


def _runs(task_id, skill, tools, skilled):
    arm = skill_arm(skill).name
    return [_run(task_id, TOOLS.name, p, i) for i, p in enumerate(tools)] + [
        _run(task_id, arm, p, i) for i, p in enumerate(skilled)
    ]


# --- the event stream reaches the caller ----------------------------------------------------------


class EventDriver(RecordingDriver):
    def collect_events(self, prompt, env_vars, **kwargs):
        super().collect_events(prompt, env_vars, **kwargs)
        return [{"type": "text", "text": "hello"}, {"type": "tool", "name": "x"}]


def _stub_iris(monkeypatch):
    from tests.e2e.skill_eval import graded_task

    monkeypatch.setattr(graded_task, "validate_live", lambda _task: None)
    monkeypatch.setattr(graded_task, "reset_documents", lambda *a, **k: None)
    monkeypatch.setattr(graded_task, "apply_documents", lambda *a, **k: None)
    monkeypatch.setattr(graded_task, "run_check", lambda _task: False)


def test_run_one_hands_the_raw_events_to_on_events(monkeypatch):
    from tests.e2e.skill_eval import pilot

    _stub_iris(monkeypatch)
    seen = []
    run = pilot.run_one(
        fake_task("FAKE-T1"),
        TOOLS,
        openai_api_key="sk-test",
        iris_host="localhost",
        iris_web_port="52780",
        iris_container="iris-dev-iris",
        driver=EventDriver(),
        on_events=seen.append,
    )
    assert run.passed is False
    assert seen == [[{"type": "text", "text": "hello"}, {"type": "tool", "name": "x"}]]


def test_run_one_without_on_events_still_runs(monkeypatch):
    from tests.e2e.skill_eval import pilot

    _stub_iris(monkeypatch)
    run = pilot.run_one(
        fake_task("FAKE-T2"),
        TOOLS,
        openai_api_key="sk-test",
        iris_host="localhost",
        iris_web_port="52780",
        iris_container="iris-dev-iris",
        driver=EventDriver(),
    )
    assert run.passed is False


def test_run_ladder_names_each_stream_by_task_arm_and_repeat(monkeypatch):
    from tests.e2e.skill_eval import ladder, pilot

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def run_one(task, arm, *, on_events=None, **kwargs):
        on_events([{"task": task.id, "arm": arm.name}])
        return _run(task.id, arm.name, True)

    monkeypatch.setattr(pilot, "run_one", run_one)
    got = []
    ladder.run_ladder(
        [FakeTask("SKILL-13"), FakeTask("SKILL-14")],
        (TOOLS, skill_arm("iris-query-plans")),
        repeats=2,
        on_events=lambda task, arm, repeat, events: got.append(
            (task.id, arm.name, repeat, events[0]["task"])
        ),
    )
    assert len(got) == 8
    assert len({g[:3] for g in got}) == 8, "one stream per session"
    assert all(g[0] == g[3] for g in got)
    assert {g[2] for g in got} == {0, 1}


def test_the_transcript_writer_writes_one_jsonl_file_per_session(tmp_path):
    from tests.e2e.skill_eval import ladder

    write = ladder.transcript_writer(str(tmp_path / "run.transcripts"))
    arm = skill_arm("iris-query-plans")
    events = [{"type": "text", "text": "a"}, {"type": "tool", "name": "b"}]
    write(FakeTask("SKILL-13"), arm, 2, events)
    write(FakeTask("SKILL-13"), TOOLS, 2, events[:1])

    files = sorted(p.name for p in (tmp_path / "run.transcripts").iterdir())
    assert files == [
        f"SKILL-13__{arm.name}__r2.jsonl",
        "SKILL-13__tools__r2.jsonl",
    ]
    lines = (tmp_path / "run.transcripts" / files[0]).read_text().strip().splitlines()
    assert [json.loads(x) for x in lines] == events


def test_the_report_names_the_transcript_directory():
    from tests.e2e.skill_eval import ladder
    from tests.e2e.skill_eval.test_ladder import a_split

    runs = _runs("SKILL-13", "iris-query-plans", [True], [False])
    written = ladder.report(
        runs,
        arms=(TOOLS,),
        split=a_split(["SKILL-13"]),
        model="m",
        container="c",
        repeats=1,
        pooled=True,
        tasks=[],
        transcripts="tests/e2e/results/ladder-x.transcripts",
    )
    assert written["transcripts"] == "tests/e2e/results/ladder-x.transcripts"
    assert "triage" in written


def test_git_ignores_transcript_directories():
    probe = "tests/e2e/results/ladder-x.transcripts/SKILL-13__tools__r0.jsonl"
    out = subprocess.run(["git", "check-ignore", "-q", probe], cwd=REPO, check=False)
    assert out.returncode == 0, f"{probe} is not ignored"


# --- the triage rule -------------------------------------------------------------------------------


def test_two_skill_failures_against_two_tools_passes_flag_the_skill():
    from tests.e2e.skill_eval import ladder

    runs = _runs(
        "SKILL-13", "iris-query-plans", [True, True, True], [False, False, True]
    )
    assert ladder.needs_fix(runs) == {"iris-query-plans": ["SKILL-13"]}


def test_one_skill_failure_is_noise():
    from tests.e2e.skill_eval import ladder

    runs = _runs(
        "SKILL-13", "iris-query-plans", [True, True, True], [False, True, True]
    )
    assert ladder.needs_fix(runs) == {}


def test_a_skill_loss_where_tools_also_mostly_failed_is_not_flagged():
    from tests.e2e.skill_eval import ladder

    runs = _runs(
        "SKILL-14", "objectscript-unit-test", [True, False, False], [False] * 3
    )
    assert ladder.needs_fix(runs) == {}


def test_unscored_runs_count_for_neither_side():
    from tests.e2e.skill_eval import ladder

    # Skill arm: one scored FAIL and two holes. Not two failures.
    runs = _runs("SKILL-16", "ensemble-production", [True] * 3, [False, None, None])
    assert ladder.needs_fix(runs) == {}
    rows = {r["task"]: r for r in ladder.triage(runs)}
    assert rows["SKILL-16"]["status"] == "unmeasured"

    # Tools arm: two holes, so tools never passed twice.
    runs = _runs("SKILL-16", "ensemble-production", [True, None, None], [False] * 3)
    assert ladder.needs_fix(runs) == {}
    assert ladder.triage(runs)[0]["status"] == "unmeasured"


def test_triage_groups_tasks_under_their_skill_and_keeps_the_rest():
    from tests.e2e.skill_eval import ladder

    runs = (
        _runs("SKILL-13", "iris-query-plans", [True] * 3, [False] * 3)
        + _runs("SKILL-19", "iris-query-plans", [True] * 3, [False, False, True])
        + _runs("SKILL-14", "objectscript-unit-test", [True] * 3, [True] * 3)
    )
    assert ladder.needs_fix(runs) == {"iris-query-plans": ["SKILL-13", "SKILL-19"]}
    rows = {r["task"]: r for r in ladder.triage(runs)}
    assert rows["SKILL-14"]["status"] == "keep"
    assert rows["SKILL-13"] == {
        "task": "SKILL-13",
        "skill": "iris-query-plans",
        "tools_passed": 3,
        "tools_scored": 3,
        "skill_failed": 3,
        "skill_scored": 3,
        "status": "fix",
    }
