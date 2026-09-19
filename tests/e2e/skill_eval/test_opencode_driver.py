"""Unit tests for the opencode driver — 120 T003, written before `opencode_driver.py`.

The requirement is *no observable change*. The pilot's 24 sessions are the only graded evidence in
spec 121, and a boundary that quietly re-reads the event stream differently invalidates them. So each
test below pins a number the pilot already produced, computed through the boundary instead of beside
it.
"""

import json

import pytest

from tests.e2e.skill_eval.driver import DriverRun, McpSource, completed_calls
from tests.e2e.skill_eval.opencode_driver import OpencodeDriver, tool_calls_from_events
from tests.e2e.skill_eval.pilot import completed_tool_calls


def tool_event(tool: str, status: str = "completed") -> dict:
    return {"type": "tool_use", "part": {"tool": tool, "state": {"status": status}}}


def test_the_boundary_counts_what_the_pilot_counted():
    """The same events, the same number, computed two ways. `completed_tool_calls` reads the raw
    stream; `completed_calls` reads the parsed log. They cannot be allowed to disagree, because
    `pilot-121.json` records the first and every later reach figure reads the second."""
    events = [
        tool_event("iris-agentic-dev_iris_doc"),
        tool_event("iris-agentic-dev_iris_compile", status="error"),
        tool_event("bash"),
        tool_event("read"),
    ]
    assert completed_tool_calls(events) == 3
    assert completed_calls(tool_calls_from_events(events)) == 3


def test_a_call_keeps_the_server_that_served_it():
    """`parse_mcp_tool` already splits `iris-agentic-dev_iris_doc`; the boundary keeps the split
    rather than throwing the server away, which is what Story 5's denominator needs."""
    calls = tool_calls_from_events(
        [tool_event("iris-agentic-dev_iris_doc"), tool_event("bash")]
    )
    assert [(c.name, c.server) for c in calls] == [
        ("iris_doc", "iris_agentic_dev"),
        ("bash", None),
    ]


def test_an_errored_call_is_kept_and_marked_rather_than_dropped():
    """A tool the agent reached for and failed to use is the most interesting row in an attribution
    table — a description problem, not an absence. Dropping it reports it as never tried.
    """
    calls = tool_calls_from_events(
        [tool_event("iris-agentic-dev_iris_compile", status="error")]
    )
    assert len(calls) == 1
    assert calls[0].completed is False


def test_the_driver_names_where_opencode_keeps_registrations():
    driver = OpencodeDriver()
    assert driver.name == "opencode"
    assert (
        McpSource(kind="env", locator="OPENCODE_CONFIG_CONTENT") in driver.mcp_sources()
    )


def test_the_driver_reads_the_registered_servers_out_of_its_own_source():
    driver = OpencodeDriver()
    env_vars = {
        "OPENCODE_CONFIG_CONTENT": '{"mcp": {"iris-agentic-dev": {"type": "local"}}}'
    }
    assert driver.registered_mcp_servers(env_vars) == ["iris-agentic-dev"]
    assert driver.registered_mcp_servers({}) == []


def test_unreadable_config_is_an_error_not_an_empty_arm():
    """A config opencode cannot parse is opencode's failure, and the arm it would produce is a bare
    session. Returning `[]` here would report that as a legitimately empty bare arm."""
    driver = OpencodeDriver()
    with pytest.raises(Exception) as excinfo:
        driver.registered_mcp_servers({"OPENCODE_CONFIG_CONTENT": "{not json"})
    assert "OPENCODE_CONFIG_CONTENT" in str(excinfo.value)


def test_grading_a_session_produces_a_run_that_obeys_the_two_refusals():
    driver = OpencodeDriver()
    session = driver.session_from_events(
        [tool_event("bash")], transcript="done", session_seconds=44.2
    )
    passed = driver.grade(session, reward=1.0, scored=True)
    assert isinstance(passed, DriverRun)
    assert (passed.reward, passed.scored, passed.session_seconds) == (1.0, True, 44.2)
    unscored = driver.grade(session, scored=False, reason="the check printed nothing")
    assert unscored.reward is None
    assert unscored.reason == "the check printed nothing"
    with pytest.raises(ValueError):
        driver.grade(session, reward=0.0, scored=False)


# --- configuring and spawning are the driver's job too — 120 T008 --------------------------------


class FakeIsolatedEnv:
    """The two things `configure_arm` uses of `IsolatedEnv`, recorded."""

    def __init__(self, skills_dir):
        self.skills_dir = skills_dir
        self.mcp_kwargs = None

    def with_mcp(self, **kwargs):
        self.mcp_kwargs = kwargs
        return self

    def env_vars(self):
        config = (
            {"mcp": {"iris-agentic-dev": {"type": "local"}}} if self.mcp_kwargs else {}
        )
        return {"OPENCODE_CONFIG_CONTENT": json.dumps(config)}


def test_configuring_an_arm_goes_through_the_isolated_env_and_returns_its_variables(
    tmp_path,
):
    """Nothing about opencode's arms changes here — `arms.configure` still does the work — but the
    pilot now asks the driver for it, so a second harness configures itself instead of inheriting
    `OPENCODE_CONFIG_CONTENT` and running with no server at all."""
    from tests.e2e.skill_eval.arms import TOOLS

    env = FakeIsolatedEnv(str(tmp_path / "skills"))
    driver = OpencodeDriver()
    env_vars = driver.configure_arm(
        TOOLS,
        env,
        (),
        iris_host="localhost",
        iris_web_port="52780",
        iris_container="iris-dev-iris",
        binary="/tmp/fake-iad-binary",
        openai_api_key="sk-test",
    )
    assert env.mcp_kwargs["iris_container"] == "iris-dev-iris"
    assert env.mcp_kwargs["toolset"] == "merged"
    assert driver.registered_mcp_servers(env_vars) == ["iris-agentic-dev"]


def test_the_bare_arm_gets_no_registration_from_the_driver_either(tmp_path):
    from tests.e2e.skill_eval.arms import BARE

    env = FakeIsolatedEnv(str(tmp_path / "skills"))
    env_vars = OpencodeDriver().configure_arm(
        BARE,
        env,
        (),
        iris_host="localhost",
        iris_web_port="52780",
        iris_container="iris-dev-iris",
    )
    assert env.mcp_kwargs is None
    assert OpencodeDriver().registered_mcp_servers(env_vars) == []


def test_collect_events_is_the_opencode_runners_own_collector(monkeypatch):
    """Delegation, asserted rather than assumed: `pilot-121.json` was produced by
    `opencode_runner.collect_events`, and a second implementation here would quietly re-baseline it.
    """
    seen = {}

    def fake_collect(prompt, env_vars, **kwargs):
        seen.update({"prompt": prompt, "env_vars": env_vars, "kwargs": kwargs})
        return [tool_event("bash")]

    monkeypatch.setattr(
        "tests.e2e.skill_eval.opencode_driver.collect_events", fake_collect
    )
    events = OpencodeDriver().collect_events(
        "do the thing",
        {"OPENCODE_CONFIG_CONTENT": "{}"},
        model="openai/gpt-4.1",
        timeout=42,
    )
    assert seen["prompt"] == "do the thing"
    assert seen["kwargs"] == {"model": "openai/gpt-4.1", "timeout": 42}
    assert len(tool_calls_from_events(events)) == 1


# --- the failure mode, not just the failure — Goal 3 -----------------------------------------------


def test_a_call_keeps_the_status_opencode_reported():
    """`completed=False` says a call did not finish. It does not say whether the tool refused the
    arguments, the server died, or the model abandoned the call half-written, and those are three
    different findings about a tool description. The status string is what opencode already knows."""
    calls = tool_calls_from_events(
        [
            tool_event("iris-agentic-dev_iris_compile", status="error"),
            tool_event("iris-agentic-dev_iris_doc"),
            tool_event("bash", status="pending"),
        ]
    )
    assert [c.status for c in calls] == ["error", "completed", "pending"]


def test_an_errored_call_keeps_the_message_the_tool_returned():
    """The failure mode Goal 3 asks for is the text. A reach count of 4 with 4 errors saying
    "namespace not found" is a configuration fault; the same count saying "UNKNOWN_PARAMETER" is a
    schema the model cannot read, and only one of those is the tool's problem."""
    events = [
        {
            "type": "tool_use",
            "part": {
                "tool": "iris-agentic-dev_iris_execute",
                "state": {
                    "status": "error",
                    "error": "CODE_EDIT_BLOCKED: the write gate refused",
                },
            },
        }
    ]
    (call,) = tool_calls_from_events(events)
    assert call.error == "CODE_EDIT_BLOCKED: the write gate refused"
    assert call.completed is False


def test_a_completed_call_carries_no_error():
    (call,) = tool_calls_from_events([tool_event("iris-agentic-dev_iris_doc")])
    assert call.error is None
