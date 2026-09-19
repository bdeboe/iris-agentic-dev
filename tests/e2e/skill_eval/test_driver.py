"""Unit tests for the agent-driver boundary — 120 T001, written before `driver.py`.

The boundary exists because the harness is not settled. `opencode` drove the pilot; `prime-agent` is
under evaluation. Two things go wrong when the agent is not behind an interface, and both are already
in this repo's history:

- **A driver reports a number it could not measure.** 118's shape: a session that never had tools
  scored as a session that failed. `DriverRun` refuses `scored=True` with no reward and
  `scored=False` with one, at construction, so no call site can decide otherwise.
- **The absence check goes vacuous rather than weaker.** `arms.py` asserts the bare arm empty by
  reading `OPENCODE_CONFIG_CONTENT` and nothing else. Point it at a second harness and it passes on
  every arm, including a contaminated one — a green check that checks nothing, which is worse than a
  missing one. So absence is driver-supplied, and a driver that names no place a registration could
  hide fails the arm instead of blessing it.
"""

import pytest

from tests.e2e.skill_eval.arms import ArmContaminated
from tests.e2e.skill_eval.driver import (
    DriverRun,
    McpSource,
    ToolCall,
    assert_absence_checkable,
    completed_calls,
)


class FakeDriver:
    """The contract, with nothing behind it. A driver interface with one implementation is a guess."""

    name = "fake"
    harness_version = "0.0.0-test"

    def __init__(self, sources=(McpSource(kind="env", locator="FAKE_CONFIG"),)):
        self._sources = tuple(sources)

    def mcp_sources(self):
        return self._sources

    def registered_mcp_servers(self, env_vars):
        raw = env_vars.get("FAKE_CONFIG") or ""
        return sorted(name for name in raw.split(",") if name)

    def run(self, prompt, **kwargs):
        return DriverRun(
            transcript=f"answered: {prompt}",
            tool_calls=(ToolCall(name="bash", completed=True),),
            reward=1.0,
            scored=True,
            logprobs=None,
        )


# --- what a run carries ---------------------------------------------------------------------------


def test_a_run_carries_the_five_declared_fields():
    """Spec 120 FR-006, which spec 121 § Driver interface recorded and gave to nobody: prompt in;
    transcript, tool-call log, scalar reward, `scored` flag, logprobs out."""
    run = FakeDriver().run("fix the class")
    assert run.transcript == "answered: fix the class"
    assert [call.name for call in run.tool_calls] == ["bash"]
    assert run.reward == 1.0
    assert run.scored is True
    assert run.logprobs is None


def test_logprobs_none_is_valid_and_is_what_every_subprocess_driver_returns():
    """Decision 2 closed as harness optimization, so no driver here has behaviour probabilities. The
    field stays because a vLLM-backed driver is then an addition rather than a rewrite."""
    assert (
        DriverRun(transcript="", tool_calls=(), reward=0.0, scored=True).logprobs
        is None
    )


# --- the two refusals (FR-010) --------------------------------------------------------------------


def test_scored_with_no_reward_raises():
    with pytest.raises(ValueError) as excinfo:
        DriverRun(transcript="", tool_calls=(), reward=None, scored=True)
    assert "scored" in str(excinfo.value)


def test_unscored_holding_a_reward_raises():
    """The 118 bug as a type error. A run the harness could not grade must not carry a number that
    something downstream will average."""
    with pytest.raises(ValueError) as excinfo:
        DriverRun(transcript="", tool_calls=(), reward=0.0, scored=False)
    assert "reward" in str(excinfo.value)


def test_an_unscored_run_wants_a_reason():
    """`passed=None` in the pilot always came with a reason, and a smaller `n` nobody can explain is
    the reason it did."""
    with pytest.raises(ValueError) as excinfo:
        DriverRun(transcript="", tool_calls=(), reward=None, scored=False)
    assert "reason" in str(excinfo.value)
    run = DriverRun(
        transcript="",
        tool_calls=(),
        reward=None,
        scored=False,
        reason="the binary did not resolve",
    )
    assert run.reason == "the binary did not resolve"


# --- the tool-call log ----------------------------------------------------------------------------


def test_only_completed_calls_count_as_reach():
    """FR-013's log is the source for Story 5's reach figures. A call the session started and
    abandoned is not evidence that the tool was reachable."""
    calls = (
        ToolCall(name="iris_doc", completed=True, server="iris-agentic-dev"),
        ToolCall(name="iris_compile", completed=False, server="iris-agentic-dev"),
        ToolCall(name="bash", completed=True),
    )
    assert completed_calls(calls) == 2


def test_a_call_records_which_server_served_it():
    """Spec 121's Story 5 counts reach over the advertised iad surface. A `bash` call and an
    `iris_doc` call are both tool calls and only one of them is the thing being measured."""
    calls = (
        ToolCall(name="iris_doc", completed=True, server="iris-agentic-dev"),
        ToolCall(name="bash", completed=True),
    )
    assert [call.server for call in calls] == ["iris-agentic-dev", None]


# --- absence is driver-supplied (FR-009) ----------------------------------------------------------


def test_a_driver_names_the_places_a_registration_could_hide():
    driver = FakeDriver()
    assert [source.locator for source in driver.mcp_sources()] == ["FAKE_CONFIG"]
    assert_absence_checkable(driver)  # does not raise


def test_a_driver_naming_nothing_fails_the_arm_rather_than_passing_it():
    """The vacuity case, and the reason this is a raise and not a warning: a check that inspects no
    place reports every arm clean, and the bare arm's whole job is to be verifiably empty."""
    driver = FakeDriver(sources=())
    with pytest.raises(ArmContaminated) as excinfo:
        assert_absence_checkable(driver)
    assert "fake" in str(excinfo.value)
    assert "no place" in str(excinfo.value)


def test_a_source_says_what_kind_of_place_it_is():
    """An env var and a settings file are read differently and fail differently. `prime-agent` keeps
    its registrations in `~/.prime/agent/settings.json`; opencode keeps them in an env var."""
    env = McpSource(kind="env", locator="OPENCODE_CONFIG_CONTENT")
    path = McpSource(kind="path", locator="~/.prime/agent/settings.json")
    assert env.kind == "env"
    assert path.kind == "path"
    with pytest.raises(ValueError):
        McpSource(kind="vibes", locator="somewhere")
