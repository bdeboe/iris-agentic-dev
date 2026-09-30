"""The ladder stops on measured spend — 132 (T041 overrun), written before the code.

The 132 holdout ladder was estimated at $1.02 (12 sessions at `COST_PER_SESSION_USD` = $0.085) and
cost $12.29 by opencode's own `step_finish.cost`: SKILL-24's skill arm ran 54 to 94 steps at up to
$2.99 a session. Tom's cap was $3. The only cap the ladder knew was the $80 programme budget, and it
checked only the estimate, before the first session. `--cap` now bounds the run, and each session's
measured cost counts against it as the session ends.

No session starts here. `pilot.run_one` is replaced, as in `test_ladder.py`.
"""

from __future__ import annotations

import pytest

from tests.e2e.skill_eval.arms import TOOLS, TOOLS_SKILLS
from tests.e2e.skill_eval.test_ladder import FakeTask, run


def _step(cost):
    return {"type": "step_finish", "part": {"type": "step-finish", "cost": cost}}


def test_session_cost_sums_the_step_finish_costs():
    from tests.e2e.skill_eval.cost_estimator import session_cost

    events = [
        {"type": "text", "part": {}},
        _step(0.5),
        _step(0.25),
        {"type": "tool_use"},
    ]
    assert session_cost(events) == pytest.approx(0.75)


def test_session_cost_of_a_stream_with_no_cost_is_zero():
    from tests.e2e.skill_eval.cost_estimator import session_cost

    assert session_cost([{"type": "step_finish", "part": {}}, {"type": "text"}]) == 0.0
    assert session_cost([]) == 0.0


def _costed_run_one(costs, calls):
    def run_one(task, arm, on_events=None, **kwargs):
        calls.append((task.id, arm.name))
        if on_events is not None:
            on_events([_step(costs[len(calls) - 1])])
        return run(task.id, arm.name, True)

    return run_one


def test_the_run_stops_once_measured_spend_reaches_the_cap(monkeypatch):
    from tests.e2e.skill_eval import ladder, pilot

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    calls = []
    monkeypatch.setattr(pilot, "run_one", _costed_run_one([1.0, 1.5, 1.0, 1.0], calls))
    written = []

    with pytest.raises(ladder.LadderAborted) as raised:
        ladder.run_ladder(
            [FakeTask("CORPUS-01"), FakeTask("CORPUS-02")],
            (TOOLS, TOOLS_SKILLS),
            cap=3.0,
            spent=0.5,
            on_run=written.append,
        )

    # 0.5 + 1.0 + 1.5 = 3.0 reaches the cap after the second session; no third starts.
    assert len(calls) == 2
    assert len(written) == 2
    assert "$3.00" in str(raised.value)


def test_the_cap_counts_the_sessions_even_with_no_transcript_writer(monkeypatch):
    from tests.e2e.skill_eval import ladder, pilot

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    calls = []
    monkeypatch.setattr(pilot, "run_one", _costed_run_one([2.0, 2.0], calls))

    with pytest.raises(ladder.LadderAborted):
        ladder.run_ladder([FakeTask("CORPUS-01")], (TOOLS, TOOLS_SKILLS), cap=3.0)
    assert len(calls) == 2


def test_with_no_cap_the_run_goes_on(monkeypatch):
    from tests.e2e.skill_eval import ladder, pilot

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    calls = []
    monkeypatch.setattr(pilot, "run_one", _costed_run_one([5.0] * 4, calls))

    runs = ladder.run_ladder(
        [FakeTask("CORPUS-01"), FakeTask("CORPUS-02")], (TOOLS, TOOLS_SKILLS)
    )
    assert len(runs) == 4


def test_on_events_still_gets_every_stream(monkeypatch):
    from tests.e2e.skill_eval import ladder, pilot

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(pilot, "run_one", _costed_run_one([0.1, 0.1], []))
    seen = []

    ladder.run_ladder(
        [FakeTask("CORPUS-01")],
        (TOOLS, TOOLS_SKILLS),
        cap=3.0,
        on_events=lambda task, arm, repeat, events: seen.append(
            (task.id, arm.name, repeat)
        ),
    )
    assert seen == [("CORPUS-01", TOOLS.name, 0), ("CORPUS-01", TOOLS_SKILLS.name, 0)]


def test_cap_parses_and_defaults_to_none():
    from tests.e2e.skill_eval import ladder

    assert ladder.parse_args(["--cap", "3"]).cap == 3.0
    assert ladder.parse_args([]).cap is None


def test_an_estimate_over_the_cap_is_refused_before_any_session():
    from tests.e2e.skill_eval.cost_estimator import (
        BudgetExceeded,
        assert_within_budget,
        estimate_ladder,
    )

    estimate = estimate_ladder(2, ["tools", "tools+iris-ai-hub"], runs=3)
    with pytest.raises(BudgetExceeded):
        assert_within_budget(estimate, already_spent=2.5, budget=3.0)
