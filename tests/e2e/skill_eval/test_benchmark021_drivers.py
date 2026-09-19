"""Contract tests for the two `benchmark/021` harnesses — 120 T005, written before `drivers.py`.

Spec 120 FR-006 declares one boundary; a boundary with one implementation is a guess. `benchmark/021`
already holds two other harnesses — an Anthropic-API tool loop that spawns `iris-dev mcp` itself, and
a Copilot stub that has never run — and they are the cheapest available proof that the interface is
not just opencode's shape written down.

They are adapters, not rewrites. `run_task` keeps its billable loop; `drivers.py` puts the five
declared fields, the three refusals and FR-009's absence sources around it. The Copilot stub stays
unimplemented on purpose: what it must not do is return a run at reward 0, which is exactly how 118
published nine skills at zero from sessions that never had tools.

`benchmark/021` is not an importable package name, so the module is loaded by path.
"""

import importlib.util
import json
import os

import pytest

from tests.e2e.skill_eval.arms import (
    BARE,
    TOOLS,
    ArmContaminated,
    assert_absent,
    assert_present,
)
from tests.e2e.skill_eval.driver import DriverRun, assert_absence_checkable

DRIVERS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "benchmark",
    "021",
    "runner",
    "drivers.py",
)


def load_drivers():
    spec = importlib.util.spec_from_file_location("benchmark021_drivers", DRIVERS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def drivers():
    return load_drivers()


def write_mcp_json(path, key="mcpServers"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({key: {"iris-agentic-dev": {"command": "iris-dev"}}}, handle)


# --- claude-code ---------------------------------------------------------------------------------


def test_the_claude_code_driver_names_where_claude_code_keeps_registrations(drivers):
    driver = drivers.ClaudeCodeDriver()
    assert driver.name == "claude-code"
    locators = [source.locator for source in driver.mcp_sources()]
    assert ".mcp.json" in locators
    assert_absence_checkable(driver)  # does not raise


def test_the_claude_code_driver_admits_the_server_it_spawns_itself(drivers, tmp_path):
    """This harness does not read a config to get its tools — `_spawn_mcp` starts `iris-dev mcp`
    unconditionally. A driver that reported no registration because no file said so would let the
    tools arm pass as unprovable and the bare arm pass while holding everything."""
    tools = drivers.ClaudeCodeDriver(tools=True, cwd=str(tmp_path), home=str(tmp_path))
    assert tools.registered_mcp_servers({}) == ["iris-agentic-dev"]
    assert_present(TOOLS, {}, skills_dir=None, driver=tools)
    with pytest.raises(ArmContaminated) as excinfo:
        assert_absent(BARE, {}, driver=tools)
    assert "iris-agentic-dev" in str(excinfo.value)


def test_a_stale_mcp_json_fails_the_bare_arm_under_the_claude_code_driver(
    drivers, tmp_path
):
    """The contamination opencode's env var cannot see: a project file in the sandbox cwd."""
    write_mcp_json(os.path.join(str(tmp_path), ".mcp.json"))
    driver = drivers.ClaudeCodeDriver(
        tools=False, cwd=str(tmp_path), home=str(tmp_path)
    )
    with pytest.raises(ArmContaminated) as excinfo:
        assert_absent(BARE, {}, driver=driver)
    assert "iris-agentic-dev" in str(excinfo.value)
    assert ".mcp.json" in str(excinfo.value)


def test_a_clean_sandbox_is_a_bare_arm_under_the_claude_code_driver(drivers, tmp_path):
    driver = drivers.ClaudeCodeDriver(
        tools=False, cwd=str(tmp_path), home=str(tmp_path)
    )
    assert driver.registered_mcp_servers({}) == []
    assert_absent(BARE, {}, driver=driver)


def test_the_claude_code_driver_returns_the_five_declared_fields(drivers):
    """`run_task` returns `{path, transcript, tool_call_count}`. The adapter turns that into the
    declared shape, and `logprobs` is `None` — Decision 2 chose harness optimization, and a
    subprocess driver has no behaviour probabilities to hand back."""
    driver = drivers.ClaudeCodeDriver()
    raw = {
        "path": "A",
        "tool_call_count": 2,
        "transcript": [
            {"role": "assistant", "tool_name": "iris_doc", "args": {}},
            {"role": "tool_result", "tool_result": "ok"},
            {"role": "assistant", "tool_name": "iris_compile", "args": {}},
            {"role": "assistant", "text": "done"},
        ],
    }
    run = driver.run_from_result(raw, reward=1.0, scored=True)
    assert isinstance(run, DriverRun)
    assert run.logprobs is None
    assert run.reward == 1.0
    assert [call.name for call in run.tool_calls] == ["iris_doc", "iris_compile"]
    assert all(call.server == "iris-agentic-dev" for call in run.tool_calls)
    assert "done" in run.transcript


def test_the_claude_code_adapter_obeys_the_refusals(drivers):
    driver = drivers.ClaudeCodeDriver()
    raw = {"path": "A", "transcript": [], "tool_call_count": 0}
    with pytest.raises(ValueError):
        driver.run_from_result(raw, reward=0.0, scored=False)
    with pytest.raises(ValueError):
        driver.run_from_result(raw, reward=None, scored=True)
    unscored = driver.run_from_result(
        raw, reward=None, scored=False, reason="no check was supplied"
    )
    assert unscored.reward is None
    assert unscored.reason == "no check was supplied"


# --- copilot -------------------------------------------------------------------------------------


def test_the_copilot_driver_names_vs_codes_registration_files(drivers):
    driver = drivers.CopilotDriver()
    assert driver.name == "copilot"
    locators = [source.locator for source in driver.mcp_sources()]
    assert ".vscode/mcp.json" in locators
    assert_absence_checkable(driver)  # a stub still has to be askable


def test_the_copilot_driver_reads_a_registration_out_of_its_own_file(drivers, tmp_path):
    driver = drivers.CopilotDriver(cwd=str(tmp_path), home=str(tmp_path))
    assert driver.registered_mcp_servers({}) == []
    write_mcp_json(os.path.join(str(tmp_path), ".vscode", "mcp.json"), key="servers")
    assert driver.registered_mcp_servers({}) == ["iris-agentic-dev"]


def test_the_unimplemented_copilot_driver_raises_rather_than_scoring_zero(drivers):
    """The 118 shape, refused at the boundary: a harness that cannot run must not produce a run. A
    `DriverRun` at reward 0 would be averaged into a published pass rate as the agent's failure.
    """
    driver = drivers.CopilotDriver()
    with pytest.raises(NotImplementedError) as excinfo:
        driver.run("write a class")
    assert "021" in str(excinfo.value)
