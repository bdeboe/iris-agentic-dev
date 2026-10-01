"""The skill eval stops on measured spend, as the ladder does since 132. Written before the code.

`python -m tests.e2e.skill_eval` had no cap at all. It recorded what the scorer cost and never what
the agent sessions cost, though those are the bill: 132 measured them 3 to 35 times above
`COST_PER_SESSION_USD`. The cap sits in `billing`, the one place every opencode session already
passes through, so fire-rate, isolation and lift sessions all count against it.

No session starts here. `run_opencode` is replaced.
"""

from __future__ import annotations

import pytest

from tests.e2e import billing, opencode_runner


def _step(cost):
    return {"type": "step_finish", "part": {"type": "step-finish", "cost": cost}}


def _fake_opencode(costs, calls):
    def run_opencode(prompt, env_vars, **kwargs):
        billing.assert_allowed("an opencode session")
        calls.append(prompt)
        yield _step(costs[len(calls) - 1])

    return run_opencode


def test_charge_adds_the_measured_cost():
    with billing.allow(), billing.spend_cap(None) as meter:
        billing.charge([_step(0.5), {"type": "text"}, _step(0.25)])
        assert meter.spent == pytest.approx(0.75)


def test_no_session_starts_once_the_cap_is_reached(monkeypatch):
    calls = []
    monkeypatch.setattr(
        opencode_runner, "run_opencode", _fake_opencode([1.0, 2.5, 1.0], calls)
    )

    with billing.allow(), billing.spend_cap(3.0) as meter:
        opencode_runner.collect_events("a", {})
        opencode_runner.collect_events("b", {})
        # 3.5 spent: the session that crossed the cap ran to its end; the next one never starts.
        with pytest.raises(billing.SpendCapReached) as raised:
            opencode_runner.collect_events("c", {})

    assert calls == ["a", "b"]
    assert meter.spent == pytest.approx(3.5)
    assert "$3.50" in str(raised.value) and "$3.00" in str(raised.value)


def test_with_no_cap_sessions_go_on_and_are_still_counted(monkeypatch):
    calls = []
    monkeypatch.setattr(
        opencode_runner, "run_opencode", _fake_opencode([5.0, 5.0], calls)
    )

    with billing.allow(), billing.spend_cap(None) as meter:
        opencode_runner.collect_events("a", {})
        opencode_runner.collect_events("b", {})

    assert meter.spent == pytest.approx(10.0)


def test_outside_a_cap_block_nothing_is_counted_or_refused(monkeypatch):
    calls = []
    monkeypatch.setattr(opencode_runner, "run_opencode", _fake_opencode([5.0], calls))

    with billing.allow():
        opencode_runner.collect_events("a", {})
    assert calls == ["a"]
    assert billing.current_spend() is None


def test_the_cli_takes_a_cap():
    from tests.e2e.skill_eval.__main__ import build_parser

    assert build_parser().parse_args(["--cap", "5"]).cap == 5.0
    assert build_parser().parse_args([]).cap is None
