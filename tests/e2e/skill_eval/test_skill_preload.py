"""The skill arm loads its skill — 130 round 3, written before the code.

Round 2 on clean isolation: 0 of 12 skill-arm sessions called the `skill` tool. gpt-4.1 saw the
skill listed and never opened it, so `tools -> tools+X` compared two arms that read the same text.
A skill arm now tells the agent to load its skill first, and a session that still does not is
unscored: it says nothing about the skill's content.

No session starts here. The driver is scripted, as in `test_pilot.py`.
"""

from __future__ import annotations

from tests.e2e.skill_eval.arms import TOOLS, skill_arm
from tests.e2e.skill_eval.test_pilot import RecordingDriver, fake_task


def _skill_call(name, status="completed"):
    return {
        "type": "tool_use",
        "part": {"tool": "skill", "state": {"status": status, "input": {"name": name}}},
    }


class ScriptedDriver(RecordingDriver):
    def __init__(self, events):
        super().__init__()
        self._events = events

    def collect_events(self, prompt, env_vars, **kwargs):
        super().collect_events(prompt, env_vars, **kwargs)
        return self._events


def _stub_iris(monkeypatch, passed=True):
    from tests.e2e.skill_eval import graded_task

    monkeypatch.setattr(graded_task, "validate_live", lambda _task: None)
    monkeypatch.setattr(graded_task, "reset_documents", lambda *a, **k: None)
    monkeypatch.setattr(graded_task, "apply_documents", lambda *a, **k: None)
    monkeypatch.setattr(graded_task, "run_check", lambda _task: passed)


def _run(monkeypatch, arm, events, passed=True):
    from tests.e2e.skill_eval import pilot

    _stub_iris(monkeypatch, passed)
    driver = ScriptedDriver(events)
    run = pilot.run_one(
        fake_task("FAKE-P1"),
        arm,
        openai_api_key="sk-test",
        iris_host="localhost",
        iris_web_port="52780",
        iris_container="iris-dev-iris",
        driver=driver,
    )
    return run, driver.collected[0][0]


# --- which arms preload ----------------------------------------------------------------------------


def test_a_skill_arm_preloads_and_the_tools_arm_does_not():
    assert skill_arm("iris-query-plans").preload is True
    assert TOOLS.preload is False


def test_the_preamble_names_the_skill_and_the_tool():
    from tests.e2e.skill_eval.pilot import preload_preamble

    text = preload_preamble(("iris-query-plans",))
    assert "iris-query-plans" in text
    assert "skill tool" in text


# --- the prompt ------------------------------------------------------------------------------------


def test_the_skill_arm_prompt_is_autonomy_then_preload_then_task(monkeypatch):
    from tests.e2e.skill_eval.pilot import AUTONOMY_PREAMBLE

    arm = skill_arm("iris-query-plans")
    _, prompt = _run(monkeypatch, arm, [_skill_call("iris-query-plans")])
    assert prompt.startswith(AUTONOMY_PREAMBLE)
    rest = prompt[len(AUTONOMY_PREAMBLE) :]
    assert rest.startswith("Before you start")
    assert "iris-query-plans" in rest
    assert prompt.endswith("do the thing")


def test_the_tools_arm_gets_the_same_autonomy_line_and_no_preload(monkeypatch):
    from tests.e2e.skill_eval.pilot import AUTONOMY_PREAMBLE

    _, prompt = _run(monkeypatch, TOOLS, [])
    assert prompt == AUTONOMY_PREAMBLE + "do the thing"


def test_the_autonomy_line_names_no_tool_and_no_skill():
    # It stands in for the operator instructions the isolation fix removed. Naming a tool or a skill
    # would make it part of what an arm is measured on.
    from tests.e2e.skill_eval.pilot import AUTONOMY_PREAMBLE

    text = AUTONOMY_PREAMBLE.lower()
    assert "skill" not in text
    assert "iris_" not in text
    assert "until" in text


# --- skill_loaded ----------------------------------------------------------------------------------


def test_a_skill_arm_that_loaded_its_skill_is_scored(monkeypatch):
    run, _ = _run(
        monkeypatch, skill_arm("iris-query-plans"), [_skill_call("iris-query-plans")]
    )
    assert run.skill_loaded is True
    assert run.passed is True


def test_a_skill_arm_that_never_loaded_is_unscored(monkeypatch):
    run, _ = _run(monkeypatch, skill_arm("iris-query-plans"), [], passed=True)
    assert run.skill_loaded is False
    assert run.passed is None
    assert "never loaded" in run.reason


def test_loading_a_different_skill_does_not_count(monkeypatch):
    run, _ = _run(
        monkeypatch, skill_arm("iris-query-plans"), [_skill_call("objectscript-tdd")]
    )
    assert run.skill_loaded is False
    assert run.passed is None


def test_a_failed_skill_call_does_not_count(monkeypatch):
    events = [_skill_call("iris-query-plans", status="error")]
    run, _ = _run(monkeypatch, skill_arm("iris-query-plans"), events)
    assert run.skill_loaded is False


def test_the_tools_arm_records_no_skill_loaded(monkeypatch):
    run, _ = _run(monkeypatch, TOOLS, [])
    assert run.skill_loaded is None
    assert run.passed is True


def test_skill_loaded_reads_the_opencode_event_shape():
    from tests.e2e.skill_eval.pilot import skill_loaded

    assert skill_loaded([_skill_call("a")], ("a",)) is True
    assert skill_loaded([_skill_call("b")], ("a",)) is False
    assert skill_loaded([{"type": "text", "text": "a"}], ("a",)) is False


# --- the ladder stops paying for skill arms that never load ---------------------------------------


def test_three_skill_arm_sessions_in_a_row_without_a_load_stop_the_ladder(monkeypatch):
    import pytest

    from tests.e2e.skill_eval import ladder, pilot
    from tests.e2e.skill_eval.pilot import ArmRun
    from tests.e2e.skill_eval.test_ladder import FakeTask

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def run_one(task, arm, **kwargs):
        if arm.preload:
            return ArmRun(
                task.id, arm.name, None, reason="never loaded", skill_loaded=False
            )
        return ArmRun(task.id, arm.name, True)

    monkeypatch.setattr(pilot, "run_one", run_one)
    with pytest.raises(ladder.LadderAborted, match="never loaded"):
        ladder.run_ladder(
            [FakeTask("SKILL-13")],
            (TOOLS, skill_arm("iris-query-plans")),
            repeats=3,
        )


def test_the_run_line_says_whether_the_skill_loaded(monkeypatch, capsys):
    from tests.e2e.skill_eval import ladder, pilot
    from tests.e2e.skill_eval.pilot import ArmRun
    from tests.e2e.skill_eval.test_ladder import FakeTask

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def run_one(task, arm, **kwargs):
        return ArmRun(
            task.id, arm.name, True, skill_loaded=True if arm.preload else None
        )

    monkeypatch.setattr(pilot, "run_one", run_one)
    ladder.run_ladder(
        [FakeTask("SKILL-13")], (TOOLS, skill_arm("iris-query-plans")), repeats=1
    )
    out = capsys.readouterr().out.splitlines()
    assert "skill loaded" in out[1]
    assert "skill" not in out[0].split("tools", 1)[1]
