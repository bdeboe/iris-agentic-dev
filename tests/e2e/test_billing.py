"""Tests for the billable-session opt-in — written before `billing.py` exists.

The working rule for this whole program has been "never run `pytest tests/e2e/skill_eval` as a
directory, because files in it spawn billable agent sessions". That rule lives in someone's memory, and
`harness-gaps.md` says why a list of safe files is the weaker fix: a file declared safe that later grows
a live test bills real money on the next nightly.

This is the stronger fix. A session refuses to start unless something explicitly asked for one, so the
directory sweep cannot spend money whatever it collects.

Spawns nothing — every spawn point here is asserted to refuse *before* it reaches `Popen`.
"""

from __future__ import annotations

import pytest

from tests.e2e import billing


@pytest.fixture(autouse=True)
def no_opt_in(monkeypatch):
    """Every test starts from "nothing asked for a session", whatever the caller's shell had set."""
    monkeypatch.delenv(billing.BILLABLE_ENV, raising=False)


# --- the gate itself -------------------------------------------------------------------------------


def test_a_session_is_refused_when_nothing_asked_for_one():
    with pytest.raises(billing.BillingRefused):
        billing.assert_allowed("one ladder session")


def test_the_refusal_says_what_to_set_and_what_asked():
    with pytest.raises(billing.BillingRefused) as raised:
        billing.assert_allowed("one ladder session")
    message = str(raised.value)
    assert billing.BILLABLE_ENV in message
    assert "one ladder session" in message


def test_the_env_var_is_what_allows_it(monkeypatch):
    monkeypatch.setenv(billing.BILLABLE_ENV, "1")
    assert billing.allowed() is True
    billing.assert_allowed("one ladder session")


def test_a_value_that_is_not_one_allows_nothing(monkeypatch):
    for value in ("", "0", "no", "false"):
        monkeypatch.setenv(billing.BILLABLE_ENV, value)
        assert billing.allowed() is False


def test_allow_holds_for_the_block_and_restores_what_was_there():
    assert billing.allowed() is False
    with billing.allow():
        assert billing.allowed() is True
    assert billing.allowed() is False


def test_allow_restores_even_when_the_run_raises():
    with pytest.raises(RuntimeError):
        with billing.allow():
            raise RuntimeError("the container died")
    assert billing.allowed() is False


# --- the spawn points ------------------------------------------------------------------------------


def never_spawns(*args, **kwargs):
    raise AssertionError("Popen was reached, so the gate did not hold")


def test_the_opencode_runner_refuses_before_it_spawns(monkeypatch):
    from tests.e2e import opencode_runner

    monkeypatch.setattr(opencode_runner.subprocess, "Popen", never_spawns)
    with pytest.raises(billing.BillingRefused):
        opencode_runner.collect_events("write a class", {})


def test_the_prime_agent_refuses_before_it_spawns(monkeypatch):
    from tests.e2e.skill_eval import prime_agent

    monkeypatch.setattr(prime_agent.subprocess, "Popen", never_spawns)
    driver = prime_agent.PrimeAgentDriver()
    with pytest.raises(billing.BillingRefused):
        driver.collect_events("write a class", {})


# --- the entry points that are allowed to spend --------------------------------------------------


def test_the_ladder_cli_asks_for_sessions(monkeypatch):
    """`--dry-run` returns before spawning, so this asserts the ask, not a session."""
    from tests.e2e.skill_eval import ladder

    seen = []
    monkeypatch.setattr(billing, "allow", lambda: seen.append(True) or _nothing())
    assert ladder.main(["--dry-run", "--task", "CORPUS-01"]) == 0
    assert seen == [True]


def test_the_pilot_cli_asks_for_sessions(monkeypatch):
    from tests.e2e.skill_eval import pilot

    seen = []
    monkeypatch.setattr(billing, "allow", lambda: seen.append(True) or _nothing())
    # No task matches, so argparse errors out after the ask and before any session.
    with pytest.raises(SystemExit):
        pilot.main(["--task", "NO-SUCH-TASK"])
    assert seen == [True]


class _nothing:
    """A context manager that does nothing, standing in for `allow()` in the two tests above."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# --- the pytest side of it -------------------------------------------------------------------------


class FakeItem:
    """Enough of a pytest item for `pytest_collection_modifyitems` to decide about."""

    def __init__(self, name, billable):
        self.name = name
        self._billable = billable
        self.own_markers = []

    def get_closest_marker(self, name):
        return object() if (name == "billable" and self._billable) else None

    def add_marker(self, marker):
        self.own_markers.append(marker)


def modify(items):
    from tests.e2e import conftest

    conftest.pytest_collection_modifyitems(None, items)
    return items


def test_a_billable_test_is_skipped_when_nothing_opted_in():
    item = FakeItem("test_spawns_a_real_session", billable=True)
    modify([item])
    assert (
        item.own_markers
    ), "a billable test collected with no opt-in must be skipped, not run"


def test_a_billable_test_runs_when_something_did_opt_in(monkeypatch):
    monkeypatch.setenv(billing.BILLABLE_ENV, "1")
    item = FakeItem("test_spawns_a_real_session", billable=True)
    modify([item])
    assert item.own_markers == []


def test_an_ordinary_test_is_left_alone():
    item = FakeItem("test_parses_a_string", billable=False)
    modify([item])
    assert item.own_markers == []


def test_the_marker_is_registered_so_strict_markers_does_not_error():
    from tests.e2e import conftest

    lines = []

    class Config:
        def addinivalue_line(self, _name, line):
            lines.append(line)

    conftest.pytest_configure(Config())
    assert any(line.startswith("billable:") for line in lines)
