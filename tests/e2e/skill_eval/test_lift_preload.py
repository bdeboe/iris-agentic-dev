"""The 118 skill-eval asks for its skill the way the ladder does — 130 round 3, before the code.

`run_task_and_score` installed the skill and sent the bare task. On the ladder that meant 0 of 12
skill-arm sessions opened the skill, so a with-skill score measured a session that never read it.
The same two prompt lines the ladder uses now go in front, and a with-skill session that never
loads the skill is unscored, not scored as the skill's result.
"""

from __future__ import annotations

from tests.e2e.skill_eval.lift import session_prompt, unloaded_skill_verdict
from tests.e2e.skill_eval.pilot import AUTONOMY_PREAMBLE, preload_preamble


def _skill_call(name):
    return {
        "type": "tool_use",
        "part": {
            "tool": "skill",
            "state": {"status": "completed", "input": {"name": name}},
        },
    }


def test_the_baseline_prompt_gets_the_autonomy_line_only():
    assert session_prompt("do the thing", None) == AUTONOMY_PREAMBLE + "do the thing"


def test_the_with_skill_prompt_asks_for_the_skill():
    assert session_prompt("do the thing", "objectscript-tdd") == (
        AUTONOMY_PREAMBLE + preload_preamble(("objectscript-tdd",)) + "do the thing"
    )


def test_a_with_skill_session_that_never_loaded_is_unscored():
    verdict = unloaded_skill_verdict("T1", "objectscript-tdd", [])
    assert verdict is not None
    assert verdict["score"] is None
    assert verdict["condition"] == "objectscript-tdd"
    assert "never loaded" in verdict["reasoning"]


def test_a_loaded_skill_or_a_baseline_session_is_left_to_the_scorer():
    assert unloaded_skill_verdict("T1", "a", [_skill_call("a")]) is None
    assert unloaded_skill_verdict("T1", None, []) is None


def test_loading_another_skill_does_not_count():
    assert unloaded_skill_verdict("T1", "a", [_skill_call("b")]) is not None
