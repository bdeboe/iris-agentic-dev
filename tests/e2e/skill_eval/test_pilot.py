"""Unit tests for the pilot runner — written before `pilot.py`, for T029/T030.

The statistics are already built: `comparison.pair_arms` pairs on task ID, `Comparison.pilot_verdict`
holds FR-024's go/no-go rule, and `stats.mcnemar_test` gives the exact p-value. What is left is the
bookkeeping between a session and a discordant count, and every mistake this file guards against is
one the earlier harness actually made:

- A session that could not run is a hole, not a failure. Nine skills published 0.00 from sessions that
  had no tools at all.
- A hole in one arm removes the *pair*, not just that arm's row. Counting a task the other arm did run
  would put a one-armed result into a paired test.
- The pilot's comparison is a design decision, never a result (FR-024).
"""

import json
import os

import pytest

from tests.e2e.skill_eval.arms import BARE, TOOLS, TOOLS_SKILLS
from tests.e2e.skill_eval.pilot import (
    PILOT_MODEL,
    PILOT_PURPOSE,
    RESULTS_DIR,
    SESSION_TIMEOUT,
    ArmRun,
    arm_results,
    completed_tool_calls,
    hit_the_clock,
    pilot_comparisons,
    report,
    shipped_skills,
    to_driver_run,
)


def run(
    task_id: str, arm: str, passed, reason: str | None = None, timed_out: bool = False
):
    return ArmRun(
        task_id=task_id,
        arm=arm,
        passed=passed,
        reason=reason,
        timed_out=timed_out,
        tool_calls=0,
    )


def three_arms(**overrides):
    """Eight tasks in three arms: bare fails all, tools passes six, tools+skills the same six."""
    runs = []
    for index in range(1, 9):
        task_id = f"PILOT-0{index}"
        runs.append(run(task_id, "bare", False))
        runs.append(run(task_id, "tools", index <= 6))
        runs.append(run(task_id, "tools+skills", index <= 6))
    return [overrides.get((r.task_id, r.arm), r) for r in runs]


# --- what counts as a result ---------------------------------------------------------------------


def test_a_scored_run_is_a_result():
    results = arm_results(
        [run("PILOT-01", "bare", True), run("PILOT-02", "bare", False)]
    )
    assert results == {"PILOT-01": True, "PILOT-02": False}


def test_an_unscored_run_is_absent_rather_than_false():
    """`passed=None` means the check never answered — a broken check or a session that could not
    start. Recording it as False is how a harness fault becomes the tools' fault."""
    results = arm_results(
        [
            run("PILOT-01", "bare", True),
            run("PILOT-02", "bare", None, reason="the binary did not resolve"),
        ]
    )
    assert results == {"PILOT-01": True}


def test_a_timeout_is_a_failure_and_not_a_hole():
    """A different case from an unscored run, and worth keeping apart.

    The clock is the same 300 seconds in every arm, and a session that spent it without changing IRIS
    did not solve the task. That is a real failure — but it is recorded as a timeout too, because a
    discordant pair that turns on the clock rather than on capability is a different claim.
    """
    results = arm_results([run("PILOT-01", "bare", False, timed_out=True)])
    assert results == {"PILOT-01": False}


# --- pairing --------------------------------------------------------------------------------------


def test_the_two_adjacent_comparisons_are_built():
    bare_to_tools, tools_to_skills = pilot_comparisons(three_arms())
    assert (bare_to_tools.arm_a, bare_to_tools.arm_b) == ("bare", "tools")
    assert (tools_to_skills.arm_a, tools_to_skills.arm_b) == ("tools", "tools+skills")


def test_the_counts_come_out_of_the_runs():
    bare_to_tools, tools_to_skills = pilot_comparisons(three_arms())
    assert (bare_to_tools.b, bare_to_tools.c) == (6, 0)
    # The skills arm matched the tools arm on every task, so there is nothing to say about it.
    assert (tools_to_skills.b, tools_to_skills.c) == (0, 0)


def test_a_hole_in_one_arm_drops_the_whole_pair():
    runs = [
        r for r in three_arms() if not (r.task_id == "PILOT-01" and r.arm == "bare")
    ]
    bare_to_tools, _ = pilot_comparisons(runs)
    assert bare_to_tools.n_pairs == 7
    assert any("PILOT-01" in hole for hole in bare_to_tools.holes)


def test_every_pilot_comparison_is_a_design_decision():
    """FR-024. The pilot decides whether to spend money; it does not establish a lift."""
    for comparison in pilot_comparisons(three_arms()):
        assert comparison.purpose == PILOT_PURPOSE == "design_decision"
        assert comparison.publishable is False


def test_the_go_verdict_comes_from_the_counts_not_from_the_runner():
    """The rule lives in `Comparison.pilot_verdict` and the runner does not get its own copy — two
    copies of a threshold is how one of them ends up out of date."""
    bare_to_tools, _ = pilot_comparisons(three_arms())
    assert bare_to_tools.pilot_verdict == "go"


def test_five_to_one_does_not_reach_go():
    """T030 says the p-value is binding, not decorative: (5, 1) gives 0.109 and does not qualify."""
    runs = []
    for index in range(1, 9):
        task_id = f"PILOT-0{index}"
        # tools wins five, bare wins one, two tasks both fail.
        bare_passed = index == 6
        tools_passed = index <= 5
        runs.append(run(task_id, "bare", bare_passed))
        runs.append(run(task_id, "tools", tools_passed))
        runs.append(run(task_id, "tools+skills", tools_passed))
    bare_to_tools, _ = pilot_comparisons(runs)
    assert (bare_to_tools.b, bare_to_tools.c) == (5, 1)
    assert bare_to_tools.p_value == pytest.approx(0.109, abs=0.001)
    assert bare_to_tools.pilot_verdict == "inconclusive"


def test_a_bare_arm_that_wins_more_stops_the_program():
    runs = []
    for index in range(1, 9):
        task_id = f"PILOT-0{index}"
        runs.append(run(task_id, "bare", index <= 4))
        runs.append(run(task_id, "tools", index > 6))
        runs.append(run(task_id, "tools+skills", index > 6))
    bare_to_tools, _ = pilot_comparisons(runs)
    assert bare_to_tools.pilot_verdict == "stop"


def test_an_arm_with_no_scored_run_at_all_is_an_error_not_a_zero():
    """The 118 shape exactly: an arm whose every session failed to start would otherwise pair as an
    arm that failed every task, and the tools would get the credit for the difference.
    """
    runs = []
    for index in range(1, 9):
        task_id = f"PILOT-0{index}"
        runs.append(run(task_id, "bare", None, reason="no session"))
        runs.append(run(task_id, "tools", True))
        runs.append(run(task_id, "tools+skills", True))
    with pytest.raises(ValueError) as excinfo:
        pilot_comparisons(runs)
    assert "bare" in str(excinfo.value)


# --- reading a session --------------------------------------------------------------------------


def completed(tool: str) -> dict:
    return {
        "type": "tool_use",
        "part": {"tool": tool, "state": {"status": "completed"}},
    }


def test_only_completed_tool_calls_are_counted():
    """Reported beside the verdict, never scored on. A call the session started and abandoned is not
    evidence of reach."""
    events = [
        completed("iris_doc"),
        {
            "type": "tool_use",
            "part": {"tool": "iris_compile", "state": {"status": "error"}},
        },
        completed("bash"),
    ]
    assert completed_tool_calls(events) == 2


def test_the_timeout_is_read_off_the_clock_and_not_off_the_events():
    """The first live pilot session finished in 44 s with 7 completed tool calls and a passing check,
    and emitted no `session.status` idle event at all. Inferring the timeout from a missing idle event
    would have labelled every run in the pilot a timeout, including the ones that solved the task.
    """
    assert hit_the_clock(43.8, 240) is False
    assert hit_the_clock(300.4, 300) is True


# --- what the arms are given ---------------------------------------------------------------------


def test_the_skills_arm_installs_the_shipped_pack():
    """Not a per-task selection. Choosing the skill that suits PILOT-03 would answer the task on the
    arm's behalf, and whether the agent finds the right skill is the reach question itself.
    """
    skills = shipped_skills()
    assert len(skills) > 20
    assert "objectscript-guardrails" in skills
    assert "objectscript-review" in skills


def test_the_three_arms_are_the_ones_the_runner_walks():
    """A fourth arm added to `arms.ARMS` becomes a third comparison here with no change to this file
    — FR-023's "no new code path", checked rather than asserted in prose."""
    from tests.e2e.skill_eval.pilot import ARMS

    assert ARMS == (BARE, TOOLS, TOOLS_SKILLS)
    assert len(pilot_comparisons(three_arms())) == len(ARMS) - 1


# --- what the run records ------------------------------------------------------------------------


def test_the_report_says_it_is_not_publishable():
    """FR-024 in the artifact, not only in the type. The JSON is what gets read six months later."""
    runs = three_arms()
    written = report(runs, pilot_comparisons(runs))
    assert written["purpose"] == "design_decision"
    assert written["publishable"] is False
    assert "FR-024" in written["note"]
    assert all(c["publishable"] is False for c in written["comparisons"])
    assert all(c["pilot_verdict"] for c in written["comparisons"])


def test_the_report_records_the_model_and_the_clock():
    """Both are conditions of the comparison. The arms are comparable to each other because the model
    and the timeout were the same in all three, and neither is recoverable from the counts.
    """
    runs = three_arms()
    written = report(runs, pilot_comparisons(runs))
    assert written["model"] == PILOT_MODEL == "openai/gpt-4.1"
    assert written["timeout_seconds"] == SESSION_TIMEOUT == 300


def test_the_report_keeps_every_run_including_the_unscored_ones():
    """A hole that is dropped from the pairing is still in the record, with its reason. Otherwise the
    only trace of a broken arm is a smaller `n_pairs` nobody can explain."""
    runs = three_arms() + [
        run("PILOT-09", "bare", None, reason="the arm was contaminated")
    ]
    written = report(runs, pilot_comparisons(runs))
    assert len(written["runs"]) == 25
    unscored = [r for r in written["runs"] if r["passed"] is None]
    assert [r["reason"] for r in unscored] == ["the arm was contaminated"]


# --- the committed artifact -----------------------------------------------------------------------


def committed_pilot() -> dict:
    with open(os.path.join(RESULTS_DIR, "pilot-121.json"), encoding="utf-8") as handle:
        return json.load(handle)


def test_the_committed_pilot_holds_the_counts_research_md_quotes():
    """research.md § Pilot result reads its table off this file. Prose and artifact drift apart
    silently, and the go/no-go is the one number in this spec nobody can re-measure for $6 later.
    """
    written = committed_pilot()
    counts = {
        (c["arm_a"], c["arm_b"]): (c["n_pairs"], c["b"], c["c"], c["pilot_verdict"])
        for c in written["comparisons"]
    }
    assert counts[("bare", "tools")] == (8, 7, 0, "go")
    assert counts[("tools", "tools+skills")] == (8, 1, 1, "stop")
    p_values = {
        (c["arm_a"], c["arm_b"]): c["p_value_one_sided"] for c in written["comparisons"]
    }
    assert p_values[("bare", "tools")] == pytest.approx(0.0078, abs=0.0001)
    assert p_values[("tools", "tools+skills")] == pytest.approx(0.75, abs=0.0001)


def test_the_committed_pilot_scored_every_session():
    """No holes and no `CheckBroken` is half of what the pilot established: the checks work. A later
    reader who finds 24 scored runs here knows the 7-0 count is over whole pairs."""
    written = committed_pilot()
    assert len(written["runs"]) == 24
    assert [r for r in written["runs"] if r["passed"] is None] == []
    assert all(c["holes"] == [] for c in written["comparisons"])


def test_the_committed_pilot_is_not_publishable():
    written = committed_pilot()
    assert written["purpose"] == PILOT_PURPOSE
    assert written["publishable"] is False
    assert written["model"] == PILOT_MODEL
    assert written["timeout_seconds"] == SESSION_TIMEOUT
    assert list(written["arms"]) == [BARE.name, TOOLS.name, TOOLS_SKILLS.name]
    assert written["skills_installed"] == list(shipped_skills())


# --- the pilot runs through the boundary — 120 T004/T005, Phase 1 gate ---------------------------


def test_run_one_takes_a_driver_and_defaults_to_opencode():
    """Nothing in the pilot should name a harness. The default keeps `pilot-121.json` reproducible;
    the parameter is what lets `prime-agent` run the same eight tasks without a second code path.
    """
    import inspect

    from tests.e2e.skill_eval.pilot import run_one

    parameter = inspect.signature(run_one).parameters["driver"]
    assert parameter.default is None


def test_the_arm_check_reports_an_unaskable_driver_as_a_hole_not_a_pass(tmp_path):
    """FR-009 at the pilot's own seam: a driver that names no place makes the bare arm unfalsifiable,
    and the run has to become a hole rather than a number."""
    from tests.e2e.skill_eval.pilot import _assert_arm

    class BlindDriver:
        name = "blind"
        harness_version = None

        def mcp_sources(self):
            return ()

        def registered_mcp_servers(self, env_vars):
            return []

        def run(self, prompt, **kwargs):
            raise NotImplementedError

    reason = _assert_arm(BARE, {}, str(tmp_path), str(tmp_path), driver=BlindDriver())
    assert reason is not None
    assert "no place" in reason


def test_a_scored_pilot_run_becomes_a_driver_run_with_a_reward():
    """The pilot's `passed` is a bool; the boundary's is a scalar reward with a `scored` flag beside
    it. Converting here rather than at the reporter is what makes 118's refusals apply to the pilot:
    a session the harness could not grade cannot carry a 0."""
    from tests.e2e.skill_eval.driver import DriverRun
    from tests.e2e.skill_eval.opencode_driver import OpencodeDriver

    driver = OpencodeDriver()
    session = driver.session_from_events([], transcript="", session_seconds=12.0)
    passed = to_driver_run(driver, session, passed=True, reason=None)
    assert isinstance(passed, DriverRun)
    assert (passed.reward, passed.scored) == (1.0, True)
    failed = to_driver_run(driver, session, passed=False, reason=None)
    assert (failed.reward, failed.scored) == (0.0, True)


def test_an_ungraded_pilot_run_carries_no_reward_at_all():
    from tests.e2e.skill_eval.opencode_driver import OpencodeDriver

    driver = OpencodeDriver()
    session = driver.session_from_events([], transcript="", session_seconds=1.0)
    hole = to_driver_run(
        driver, session, passed=None, reason="the check did not answer"
    )
    assert hole.reward is None
    assert hole.scored is False
    assert hole.reason == "the check did not answer"


def test_an_ungraded_pilot_run_without_a_reason_is_refused():
    """A hole with no reason is a smaller `n` nobody can explain, so the conversion refuses it."""
    from tests.e2e.skill_eval.opencode_driver import OpencodeDriver

    driver = OpencodeDriver()
    session = driver.session_from_events([], transcript="", session_seconds=1.0)
    with pytest.raises(ValueError):
        to_driver_run(driver, session, passed=None, reason=None)


# --- the pilot spawns through the driver too — 120 T008, Phase 2 gate ----------------------------
#
# `run_one` used to call `opencode_runner.collect_events` and `arms.configure` directly, which made
# the `driver` parameter a lie: a second harness could grade a session it never ran. Both now go
# through the driver, and a fake driver is enough to prove it without spending a session.


def fake_task(task_id: str):
    """A task with nothing in it. The session and the check are stubbed in these two tests, so the
    only thing the task has to be is well-formed."""
    from tests.e2e.skill_eval.graded_task import GradedTask

    return GradedTask(
        id=task_id,
        prompt="do the thing",
        check="write PASS",
        fixtures=(),
        solution=(),
    )


class RecordingDriver:
    """Answers every question the pilot asks, records what it was asked, runs nothing."""

    name = "recording"
    harness_version = "0.0.0-test"

    def __init__(self):
        self.collected = []
        self.configured = []

    def mcp_sources(self):
        from tests.e2e.skill_eval.driver import McpSource

        return (McpSource(kind="env", locator="RECORDING_CONFIG"),)

    def registered_mcp_servers(self, env_vars):
        return ["iris-agentic-dev"] if env_vars.get("RECORDING_TOOLS") else []

    def installed_skills(self, env_vars):
        return (
            list(env_vars.get("RECORDING_SKILLS", "").split(","))
            if env_vars.get("RECORDING_SKILLS")
            else []
        )

    def configure_arm(self, arm, env, skill_names=(), **kwargs):
        self.configured.append((arm.name, tuple(skill_names), kwargs))
        env_vars = {}
        if arm.tools:
            env_vars["RECORDING_TOOLS"] = "1"
        if arm.skills:
            env_vars["RECORDING_SKILLS"] = ",".join(skill_names) or "a-skill"
        return env_vars

    def collect_events(self, prompt, env_vars, **kwargs):
        self.collected.append((prompt, env_vars, kwargs))
        return []

    def session_from_events(self, events, *, transcript="", session_seconds=0.0):
        from tests.e2e.skill_eval.opencode_driver import DriverSession

        return DriverSession(
            transcript=transcript, tool_calls=(), session_seconds=session_seconds
        )

    def grade(self, session, *, reward=None, scored=False, reason=None):
        from tests.e2e.skill_eval.driver import DriverRun

        return DriverRun(
            transcript=session.transcript,
            tool_calls=session.tool_calls,
            reward=reward,
            scored=scored,
            reason=reason,
            session_seconds=session.session_seconds,
        )

    def run(self, prompt, **kwargs):  # pragma: no cover - the pilot never calls it
        raise NotImplementedError


def test_the_driver_configures_the_arm_and_spawns_the_session(monkeypatch, tmp_path):
    """One task, one arm, no session and no IRIS: the task validation and the check are stubbed, and
    what is asserted is that the harness-specific work happened behind the driver."""
    from tests.e2e.skill_eval import graded_task, pilot
    from tests.e2e.skill_eval.arms import TOOLS

    task = fake_task("FAKE-01")
    monkeypatch.setattr(graded_task, "validate_live", lambda _task: None)
    monkeypatch.setattr(graded_task, "reset_documents", lambda *a, **k: None)
    monkeypatch.setattr(graded_task, "apply_documents", lambda *a, **k: None)
    monkeypatch.setattr(graded_task, "run_check", lambda _task: True)

    driver = RecordingDriver()
    run = pilot.run_one(
        task,
        TOOLS,
        openai_api_key="sk-test",
        model="openai/gpt-4.1",
        timeout=42,
        skill_names=(),
        iris_host="localhost",
        iris_web_port="52780",
        iris_container="iris-dev-iris",
        binary="/tmp/fake-iad-binary",
        driver=driver,
    )

    assert run.passed is True
    assert [name for name, _, _ in driver.configured] == ["tools"]
    assert len(driver.collected) == 1
    prompt, env_vars, kwargs = driver.collected[0]
    assert prompt == "do the thing"
    assert kwargs["timeout"] == 42
    assert kwargs["model"] == "openai/gpt-4.1"
    # The environment the driver built is the environment the session got, and the same one the arm
    # assertions were made against.
    assert env_vars["RECORDING_TOOLS"] == "1"


def test_an_arm_the_driver_cannot_prove_is_a_hole_not_a_zero(monkeypatch):
    """The tools arm without its registration. Under the recording driver that means no
    `RECORDING_TOOLS`, which is 118's bug in miniature — and it has to come back unscored.
    """
    from tests.e2e.skill_eval import graded_task, pilot
    from tests.e2e.skill_eval.arms import TOOLS

    task = fake_task("FAKE-02")
    monkeypatch.setattr(graded_task, "validate_live", lambda _task: None)
    monkeypatch.setattr(graded_task, "reset_documents", lambda *a, **k: None)
    monkeypatch.setattr(graded_task, "apply_documents", lambda *a, **k: None)

    driver = RecordingDriver()
    driver.configure_arm = lambda arm, env, skill_names=(), **kwargs: {}
    run = pilot.run_one(
        task,
        TOOLS,
        openai_api_key="sk-test",
        iris_host="localhost",
        iris_web_port="52780",
        iris_container="iris-dev-iris",
        driver=driver,
    )
    assert run.passed is None
    assert "no mcp" in (run.reason or "").lower()
    assert driver.collected == []


def test_a_session_the_driver_could_not_start_is_unscored(monkeypatch):
    """A harness that could not spawn is a hole in the arm, not a task the agent failed. Under
    opencode this never came up — it fails by producing an empty transcript — but prime-agent's daemon
    can die before the model is ever reached, and three FAILs is a publishable-looking lie.
    """
    from tests.e2e.skill_eval import graded_task, pilot
    from tests.e2e.skill_eval.arms import TOOLS

    task = fake_task("FAKE-03")
    monkeypatch.setattr(graded_task, "validate_live", lambda _task: None)
    monkeypatch.setattr(graded_task, "reset_documents", lambda *a, **k: None)
    monkeypatch.setattr(graded_task, "apply_documents", lambda *a, **k: None)
    monkeypatch.setattr(
        graded_task, "run_check", lambda _task: pytest.fail("the check must not run")
    )

    driver = RecordingDriver()

    def explode(prompt, env_vars, **kwargs):
        raise RuntimeError("the daemon never answered")

    driver.collect_events = explode
    run = pilot.run_one(
        task,
        TOOLS,
        openai_api_key="sk-test",
        iris_host="localhost",
        iris_web_port="52780",
        iris_container="iris-dev-iris",
        driver=driver,
    )
    assert run.passed is None
    assert "daemon never answered" in (run.reason or "")


# --- what the report says about skills — Goal 2 ---------------------------------------------------


def test_the_report_records_what_each_arm_actually_installed():
    """`skills_installed` was `list(shipped_skills())`, computed without looking at the arms.

    Run the per-skill ladder with it and the artifact claims 34 skills for a rung holding one. The
    skills verdict is the whole point of that ladder, and the file recording it would name the wrong
    intervention.
    """
    from tests.e2e.skill_eval.arms import skill_arm, skill_ladder

    runs = three_arms()
    written = report(runs, pilot_comparisons(runs))
    assert written["skills_installed"] == {"tools+skills": list(shipped_skills())}

    lower, upper = skill_ladder("objectscript-list-patterns")
    per_skill = report(
        runs, pilot_comparisons(runs), arms=(lower, upper), skill_names=None
    )
    assert per_skill["skills_installed"] == {
        "tools+objectscript-list-patterns": ["objectscript-list-patterns"]
    }
    assert per_skill["arms"] == ["tools", "tools+objectscript-list-patterns"]
    assert skill_arm("objectscript-list-patterns").skill_names == (
        "objectscript-list-patterns",
    )


def test_the_report_records_a_subset_install_as_the_subset():
    runs = three_arms()
    written = report(
        runs, pilot_comparisons(runs), skill_names=("iris-sql", "objectscript-review")
    )
    assert written["skills_installed"] == {
        "tools+skills": ["iris-sql", "objectscript-review"]
    }


def test_the_report_names_no_skills_for_a_ladder_that_installs_none():
    runs = three_arms()
    written = report(runs, pilot_comparisons(runs), arms=(BARE, TOOLS))
    assert written["skills_installed"] == {}


# --- the call log travels with the run — Goal 3 -----------------------------------------------------


def test_an_arm_run_carries_the_calls_not_only_their_count():
    """Story 5 is a join over Story 1's sessions, so the sessions have to keep what the join reads.
    `tool_calls: int` throws away every name, and a count cannot answer which tool was reached for."""
    from tests.e2e.skill_eval.driver import ToolCall
    from tests.e2e.skill_eval.pilot import ArmRun, call_records

    records = call_records(
        (
            ToolCall(
                name="iris_doc", completed=True, server="iris_agentic_dev", status="completed"
            ),
            ToolCall(
                name="iris_compile",
                completed=False,
                server="iris_agentic_dev",
                status="error",
                error="CODE_EDIT_BLOCKED",
            ),
            ToolCall(name="bash", completed=True, server=None, status="completed"),
        )
    )
    run = ArmRun(task_id="CORPUS-01", arm="tools", passed=True, calls=records)
    assert [record["name"] for record in run.calls] == [
        "iris_doc",
        "iris_compile",
        "bash",
    ]
    assert run.calls[1]["error"] == "CODE_EDIT_BLOCKED"
    assert run.calls[2]["server"] is None


def test_the_call_records_survive_json_because_the_artifact_is_json():
    """`asdict(run)` goes straight into the report and the incremental jsonl. A `ToolCall` in there
    serializes today and stops the moment the dataclass gains a field that does not."""
    import json

    from tests.e2e.skill_eval.driver import ToolCall
    from tests.e2e.skill_eval.pilot import call_records

    records = call_records((ToolCall(name="iris_query", completed=True, server="s"),))
    assert json.loads(json.dumps(records)) == list(records)


def test_the_arguments_are_not_recorded():
    """A call's arguments hold whole ObjectScript classes. The published artifact is committed, and a
    per-tool table needs the name and the outcome, not the payload."""
    from tests.e2e.skill_eval.driver import ToolCall
    from tests.e2e.skill_eval.pilot import call_records

    records = call_records(
        (ToolCall(name="iris_doc", completed=True, arguments={"content": "x" * 5000}),)
    )
    assert "arguments" not in records[0]


def test_an_arm_run_with_no_calls_records_an_empty_log():
    from tests.e2e.skill_eval.pilot import ArmRun

    assert ArmRun(task_id="CORPUS-01", arm="bare", passed=False).calls == ()
