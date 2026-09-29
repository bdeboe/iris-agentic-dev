"""Unit tests for lift measurement — T013, rewritten for 118 T016.

The pass-rate cases moved to the new contract: an item carries `scored` alongside `score`, and
a rate is computed over the items that were scored. The old cases here passed bare `{"score":
N}` dicts, which is the shape that let an unreachable scorer read as a failing agent all the
way through to a published number.
"""

import pytest

from tests.e2e.skill_eval.lift import (
    compute_lift_from_scores,
    compute_pass_rate,
    format_transcript,
    verdict_from_assertions,
    verdict_from_patterns,
)


def make_events(tool_calls=None, text="The fix is correct."):
    events = []
    for tool in tool_calls or []:
        events.append(
            {
                "type": "tool_use",
                "part": {
                    "tool": tool,
                    "state": {"status": "completed", "input": {}, "output": "ok"},
                },
            }
        )
    events.append({"type": "text", "part": {"text": text, "time": {"end": 1}}})
    return events


def scored(score, mode="judge"):
    return {"scored": True, "score": score, "scoring_mode": mode}


UNSCORED = {"scored": False, "score": None, "scoring_mode": "judge"}


def test_compute_pass_rate_all_pass():
    assert compute_pass_rate([scored(3), scored(2), scored(3)]) == pytest.approx(1.0)


def test_compute_pass_rate_none_pass():
    assert compute_pass_rate([scored(0), scored(1), scored(1)]) == pytest.approx(0.0)


def test_compute_pass_rate_mixed():
    assert compute_pass_rate([scored(2), scored(1), scored(3)]) == pytest.approx(2 / 3)


def test_compute_pass_rate_is_the_shared_one():
    """`lift.compute_pass_rate` is `scoring.compute_pass_rate`, not a second implementation.

    Two copies of this arithmetic is how one of them kept counting unscored items: the module
    that reported to the baseline and the module that computed the lift disagreed silently.
    """
    from tests.e2e.skill_eval import scoring

    assert compute_pass_rate is scoring.compute_pass_rate


def test_compute_lift():
    result = compute_lift_from_scores(
        baseline_scores=[scored(1), scored(1)],
        skill_scores=[scored(3), scored(3)],
    )
    assert result["pass_rate_baseline"] == pytest.approx(0.0)
    assert result["pass_rate_skill"] == pytest.approx(1.0)
    assert result["lift"] == pytest.approx(1.0)


def test_lift_counts_what_each_arm_scored():
    """The denominators travel with the rates, so a report can show `6/8 scored`."""
    result = compute_lift_from_scores(
        baseline_scores=[scored(0), scored(3), UNSCORED],
        skill_scores=[scored(3), scored(3), scored(3)],
    )
    assert result["items_scored_baseline"] == 2
    assert result["items_unscored_baseline"] == 1
    assert result["items_scored_skill"] == 3
    assert result["pass_rate_baseline"] == pytest.approx(0.5)


def test_an_arm_that_scored_nothing_has_no_lift():
    """No baseline number means no subtraction. `0.0` here would read as "no improvement"."""
    result = compute_lift_from_scores(
        baseline_scores=[UNSCORED, UNSCORED],
        skill_scores=[scored(3), scored(3)],
    )
    assert result["pass_rate_baseline"] is None
    assert result["lift"] is None
    assert result["pass_rate_skill"] == pytest.approx(1.0)


def test_lift_reports_the_run_wide_unscored_share():
    result = compute_lift_from_scores(
        baseline_scores=[scored(3)] * 4 + [UNSCORED],
        skill_scores=[scored(3)] * 5,
    )
    assert result["items_unscored"] == 1
    assert result["unscored_share"] == pytest.approx(0.1)
    assert result["run_valid"] is True


def test_a_run_over_the_unscored_limit_is_invalid():
    result = compute_lift_from_scores(
        baseline_scores=[scored(3), UNSCORED],
        skill_scores=[scored(3), UNSCORED],
    )
    assert result["run_valid"] is False


def test_lift_records_which_models_scored_it():
    """Comparability depends on the grader, so the arms' scorer models travel with the run."""
    a = {**scored(3), "scorer_model": "claude-sonnet-4-6"}
    b = {**scored(2), "scorer_model": "claude-sonnet-4-6"}
    result = compute_lift_from_scores(baseline_scores=[a], skill_scores=[b])
    assert result["scorer_models"] == ["claude-sonnet-4-6"]


# ---------------------------------------------------------------------------
# The two deterministic scoring modes
# ---------------------------------------------------------------------------


def test_tool_assertion_scoring_is_scored_with_no_model():
    """Assertion mode calls nothing, so it has no scorer model and no tokens — but it is
    scored: the assertion is a measurement."""
    verdict = verdict_from_assertions(
        passed=True, assertions=["iris_agentic_dev:iris_query"]
    )
    assert verdict["scored"] is True
    assert verdict["score"] == 3
    assert verdict["scoring_mode"] == "assertion"
    assert verdict["scorer_model"] is None
    assert verdict["input_tokens"] is None


def test_a_failed_tool_assertion_is_a_measured_zero():
    verdict = verdict_from_assertions(passed=False, assertions=["iris_query"])
    assert verdict["scored"] is True
    assert verdict["score"] == 0
    assert "iris_query" in verdict["reasoning"]


def test_pattern_scoring_declares_its_mode():
    verdict = verdict_from_patterns(2, "Compiled OK but patterns not fully met")
    assert verdict["scored"] is True
    assert verdict["score"] == 2
    assert verdict["scoring_mode"] == "pattern"
    assert verdict["scorer_model"] is None


def test_format_transcript_includes_tools():
    events = make_events(tool_calls=["iris_compile", "iris_execute"])
    turns = format_transcript(events)
    tool_names = [t.get("tool_name") for t in turns if t.get("tool_name")]
    assert "iris_compile" in tool_names
    assert "iris_execute" in tool_names
    texts = [t.get("text", "") for t in turns]
    assert any("The fix is correct" in t for t in texts)


# --- the judge has to be able to see the answer — 121 T021 ------------------------------------
#
# `format_transcript` cut every assistant message to 500 characters. An ObjectScript class or a
# connection script does not fit in 500 characters, so on every judged code-writing task the judge
# graded a fragment that stopped mid-sentence and said so in its reasoning: "only provided a partial
# template description before cutting off". Four skills read 0.00 against 0.00 for months on that.
#
# The reference solutions in /tmp/t021 score 3/3/3 through the same judge when it is shown the whole
# answer, and 1 when it is shown the first 500 characters. The check was never measuring the agent.


def _long_class(marker: str, filler: int) -> str:
    body = "\n".join(f"    // padding line {i}" for i in range(filler))
    return (
        f"Class Bench.Big Extends %RegisteredObject\n{{\n{body}\n    // {marker}\n}}\n"
    )


def test_format_transcript_keeps_a_whole_class_definition():
    """The answer the judge grades has to contain the code the agent wrote."""
    answer = _long_class("the part that decides the score", 120)
    assert len(answer) > 2000, "fixture must exceed the old 500-character cap"

    turns = format_transcript(make_events(text=answer))

    text = next(t["text"] for t in turns if t.get("text"))
    assert "the part that decides the score" in text
    assert text.rstrip().endswith("}")


def test_the_text_limit_is_not_below_what_the_judge_reads():
    """A cap smaller than the judge's own is a silent drop.

    `runner.judge._format_transcript` reads 8000 characters per turn. Whatever bound lives here
    must not be the tighter of the two, or the harness decides what the scorer sees and nothing
    says so.
    """
    from tests.e2e.skill_eval.lift import TRANSCRIPT_TEXT_LIMIT

    assert TRANSCRIPT_TEXT_LIMIT >= 8000

    answer = _long_class("still visible at seven thousand characters", 300)
    assert 4000 < len(answer) <= 8000
    text = next(
        t["text"] for t in format_transcript(make_events(text=answer)) if t.get("text")
    )
    assert "still visible at seven thousand characters" in text


def test_a_runaway_answer_is_still_bounded():
    """Uncapped is not the fix either — the judge call is billed per token."""
    from tests.e2e.skill_eval.lift import TRANSCRIPT_TEXT_LIMIT

    answer = "x" * (TRANSCRIPT_TEXT_LIMIT * 4)
    text = next(
        t["text"] for t in format_transcript(make_events(text=answer)) if t.get("text")
    )
    assert len(text) == TRANSCRIPT_TEXT_LIMIT


# --- the judge has to see the code the agent wrote — 130 round 4 ------------------------------
#
# `judge._format_transcript` cut tool args to 120 characters of JSON and results to 200, and
# `format_transcript` cut results to 300 before that. For an `iris_doc put` the judge saw
# `{"mode": "put", "name": "EvalDemo.PatientLookup.cls", ...` and none of the class body, so on
# SQLCODE-SILENT it said "put call truncated" and graded the rest. 121 T021 raised assistant text
# to 8000 and left these two alone.


def _put_event(content: str, output: str) -> dict:
    return {
        "type": "tool_use",
        "part": {
            "tool": "iris_agentic_dev_iris_doc",
            "state": {
                "status": "completed",
                "input": {"mode": "put", "name": "Bench.Big.cls", "content": content},
                "output": output,
            },
        },
    }


def test_the_judge_sees_a_whole_class_body_in_a_tool_arg():
    from tests.e2e.skill_eval.judge import _format_transcript

    body = _long_class("the fix the judge must see", 250)
    assert 4000 < len(body) <= 7000
    rendered = _format_transcript(format_transcript([_put_event(body, "ok")]))
    assert "the fix the judge must see" in rendered


def test_the_judge_sees_a_long_tool_result():
    from tests.e2e.skill_eval.judge import _format_transcript

    output = _long_class("fixture line the agent read", 250)
    turns = format_transcript([_put_event("x", output)])
    assert "fixture line the agent read" in turns[0]["tool_result"]
    assert "fixture line the agent read" in _format_transcript(turns)


def test_runaway_tool_args_and_results_are_still_bounded():
    from tests.e2e.skill_eval.judge import _format_transcript
    from tests.e2e.skill_eval.lift import TRANSCRIPT_TEXT_LIMIT

    huge = "y" * (TRANSCRIPT_TEXT_LIMIT * 4)
    turns = format_transcript([_put_event(huge, huge)])
    assert len(turns[0]["tool_result"]) == TRANSCRIPT_TEXT_LIMIT
    rendered = _format_transcript(turns)
    call_line, result_line = rendered.split("\n")[:2]
    assert len(call_line) < TRANSCRIPT_TEXT_LIMIT + 200
    assert len(result_line) < TRANSCRIPT_TEXT_LIMIT + 50


# --- a session that was killed is not a failing agent — 121 T021 ------------------------------
#
# `opencode_runner.run_opencode` arms a 300 s timer, kills the process tree when it fires, and then
# yields whatever it collected. A killed session and a finished one come back the same shape, so the
# harness scored the partial transcript. SQLCODE-SILENT's live baseline run was one turn — "Let me
# begin by searching…", no completed tool calls — and went into the baseline as a 0.
#
# That is the same class 118 fixed for a missing credential: no model read a whole answer, so there
# is nothing to score. The signal is `run_opencode`'s own stop condition — the `session.status`
# event with `status.type == "idle"`. No idle event means the session did not end on its own.
#
# The rule is deliberately conservative: unscored only when the session did not reach idle AND
# produced no completed tool calls. A session killed after real work leaves real evidence, and
# throwing that away would cost more items than it saves.


def idle_event():
    return {"type": "session.status", "properties": {"status": {"type": "idle"}}}


def test_a_finished_session_has_no_evidence_gap():
    from tests.e2e.skill_eval.lift import session_evidence_gap

    events = make_events(tool_calls=["iris_query"]) + [idle_event()]
    assert session_evidence_gap(events) is None


def test_a_killed_session_with_nothing_in_it_is_a_gap():
    """The SQLCODE-SILENT case: one opening sentence, no tool calls, no idle event."""
    from tests.e2e.skill_eval.lift import session_evidence_gap

    events = make_events(text="Let me begin by searching for the class.")
    gap = session_evidence_gap(events)
    assert gap is not None
    assert "idle" in gap
    assert "0 completed tool call" in gap


def test_an_empty_event_stream_is_a_gap():
    from tests.e2e.skill_eval.lift import session_evidence_gap

    assert session_evidence_gap([]) is not None


# 130 round 3. `opencode run --format json` (1.14.17) never emits `session.status`. The stream is
# `step_start` / `text` / `tool_use` / `step_finish`, and a session that ended on its own closes with
# a `step_finish` whose `part.reason` is "stop". A killed one closes on "tool-calls" or mid-step. The
# test above builds an idle event by hand, so it passed while no real session ever reached "idle":
# every baseline session that answered in text, or whose tool calls all failed, went unscored. The
# skill arm always completes its `skill` call, so it never did — 11 of 18 iris-ai-hub baseline items
# unscored, 0 of 18 skill items. The shapes below are from a captured AI-HUB-WORKFLOW-SUSPEND session.


def _step(reason):
    return [
        {"type": "step_start", "part": {"type": "step-start"}},
        {"type": "step_finish", "part": {"type": "step-finish", "reason": reason}},
    ]


def _failed_call(tool):
    return {
        "type": "tool_use",
        "part": {"tool": tool, "state": {"status": "error", "input": {}}},
    }


def test_a_session_that_stopped_on_its_own_reached_idle():
    from tests.e2e.skill_eval.lift import _reached_idle

    assert _reached_idle(_step("tool-calls") + _step("stop"))


def test_a_text_only_answer_that_stopped_is_scored():
    from tests.e2e.skill_eval.lift import session_evidence_gap

    events = (
        [_failed_call("glob"), _failed_call("write")]
        + _step("tool-calls")
        + make_events(text="Here is the class you need: ...")
        + _step("stop")
    )
    assert session_evidence_gap(events) is None


def test_a_session_cut_after_a_tool_step_did_not_reach_idle():
    from tests.e2e.skill_eval.lift import _reached_idle, session_evidence_gap

    events = _step("tool-calls") + [
        {"type": "step_start", "part": {"type": "step-start"}}
    ]
    assert not _reached_idle(events)
    assert not _reached_idle(_step("tool-calls"))
    assert session_evidence_gap(events) is not None


def test_an_earlier_stop_does_not_count_when_the_stream_goes_on():
    from tests.e2e.skill_eval.lift import _reached_idle

    events = _step("stop") + [{"type": "step_start", "part": {"type": "step-start"}}]
    assert not _reached_idle(events)


def test_a_killed_session_that_did_real_work_is_still_scored():
    """Conservative on purpose — a truncated session with tool calls has evidence in it."""
    from tests.e2e.skill_eval.lift import session_evidence_gap

    events = make_events(tool_calls=["iris_doc", "iris_compile", "iris_execute"])
    assert session_evidence_gap(events) is None


def test_a_pending_tool_call_does_not_count_as_work():
    """A tool call the kill interrupted produced no output, so it is not evidence of anything."""
    from tests.e2e.skill_eval.lift import session_evidence_gap

    events = [
        {
            "type": "tool_use",
            "part": {
                "tool": "iris_search",
                "state": {"status": "running", "input": {}},
            },
        }
    ]
    assert session_evidence_gap(events) is not None


def test_the_gap_verdict_is_unscored_and_not_a_zero():
    """`score: None`, never `0` — `runner.judge.unscored`'s contract, 118's rule.

    A zero says a model read the transcript and rejected it. Here no model read anything.
    """
    from tests.e2e.skill_eval.lift import unscored_session

    verdict = unscored_session(
        "SQLCODE-SILENT", "baseline", "session never reached idle"
    )
    assert verdict["scored"] is False
    assert verdict["score"] is None
    assert verdict["task_id"] == "SQLCODE-SILENT"
    assert verdict["condition"] == "baseline"
    assert "never reached idle" in verdict["reasoning"]


def test_a_gapped_session_leaves_the_pass_rate_alone():
    """The whole point: an unscored item leaves the denominator, it does not fail in it."""
    result = compute_lift_from_scores(
        baseline_scores=[scored(3), scored(3), UNSCORED],
        skill_scores=[scored(3), scored(3), scored(3)],
    )
    assert result["pass_rate_baseline"] == pytest.approx(1.0)


# --- pairing: one pair per (task, run), not one per task -------------------------------------
#
# 121 T018 found this by running a gated comparison for real: five runs of one task reported
# `n_pairs: 1` in the same result file that reported `items_total: 5` per arm. `_pair_key` keys on
# `(task_id, run_index)`, `measure_lift` never set `run_index`, so all five items keyed
# `("STATUS-CHECK", None)` and `_arm_outcomes` overwrote four of them into a dict. The floor FR-008
# gates on is counted in pairs, so a silent 5→1 collapse is a silent 5× loss of resolution.


def scored_item(task_id, run_index, passed, scored=True):
    return {
        "task_id": task_id,
        "run_index": run_index,
        "scored": scored,
        "score": 3 if passed else 0,
    }


def test_pair_key_separates_runs_of_the_same_task():
    from tests.e2e.skill_eval.lift import _pair_key

    first = _pair_key(scored_item("STATUS-CHECK", 0, True), 0)
    second = _pair_key(scored_item("STATUS-CHECK", 1, True), 1)
    assert first != second


def test_arm_outcomes_keeps_every_run_of_one_task():
    from tests.e2e.skill_eval.lift import _arm_outcomes

    items = [scored_item("STATUS-CHECK", i, i < 2) for i in range(5)]
    outcomes, holes = _arm_outcomes(items)
    assert len(outcomes) == 5, outcomes
    assert sum(outcomes.values()) == 2
    assert holes == []


def test_arm_outcomes_reports_a_key_collision_instead_of_overwriting():
    """The guard that would have caught the collapse the moment it shipped.

    Two items with the same key are not a measurement of one item. Whatever the caller meant, the
    honest outcome is a named hole — dropping one silently is how `items_total: 5` and
    `n_pairs: 1` ended up in the same file.
    """
    from tests.e2e.skill_eval.lift import _arm_outcomes

    items = [
        scored_item("STATUS-CHECK", None, True),
        scored_item("STATUS-CHECK", None, False),
    ]
    outcomes, holes = _arm_outcomes(items)
    assert len(outcomes) == 1
    assert any("STATUS-CHECK" in hole and "collision" in hole for hole in holes), holes


def test_paired_comparison_over_five_runs_of_one_task_has_five_pairs():
    from tests.e2e.skill_eval.lift import _paired_comparison

    baseline = [scored_item("STATUS-CHECK", i, i == 0) for i in range(5)]
    skill = [scored_item("STATUS-CHECK", i, False) for i in range(5)]
    comparison = _paired_comparison(baseline, skill)
    assert comparison is not None
    assert comparison.n_pairs == 5
    assert comparison.b == 0
    assert comparison.c == 1


def test_measure_lift_stamps_the_run_index_on_every_item(monkeypatch):
    """The fix at its source: the item knows which run it came from.

    Stamping in `measure_lift` rather than at the pair key means every downstream reader — the
    result file, a rerun, a later re-analysis — sees the run, not just the harness's pairing.
    """
    import tests.e2e.skill_eval.lift as lift_module

    calls = []

    def fake_run_task_and_score(task_id, skill, *args, **kwargs):
        calls.append((task_id, skill))
        return {"task_id": task_id, "scored": True, "score": 3}

    monkeypatch.setattr(lift_module, "run_task_and_score", fake_run_task_and_score)

    class Config:
        skill = "objectscript-review"
        benchmark_tasks = ["STATUS-CHECK"]
        no_mcp_for_benchmark = False

    result = lift_module.measure_lift(Config(), 3, "key", "openai/gpt-4.1")
    assert len(calls) == 6  # three runs, two arms
    assert result["comparison"]["n_pairs"] == 3
