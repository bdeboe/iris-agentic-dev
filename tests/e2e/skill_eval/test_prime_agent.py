"""Unit tests for the `prime-agent` driver — 120 T007, written before `prime_agent.py`.

The fixture is a real headless run (`fixtures/prime_agent_session.jsonl`, see the README beside it),
so what is asserted here is parsing, not a guess about the format.

The one hard part is FR-013. `prime-agent` exposes exactly one model-visible tool, `ipython`; MCP
servers live inside its kernel behind `rlm.mcp`, so a tool call is a `mcp.call_tool("server", "tool",
{...})` call site in a Python string rather than an event with a name. Two rules follow, and both are
tested:

- **A recognised literal call site is attributed.** That is the shape the model actually emits, and
  the fixture proves it.
- **Anything else is reported as unattributed, never guessed.** A dynamic server name, a call built
  from variables, a cell that will not even parse. An undercount is a smaller number; an invented
  attribution is a wrong one, and reach figures are the thing this program publishes.

Nothing here starts a session, spawns `prime-agent`, or reaches IRIS.
"""

import errno
import json
import os
import subprocess

import pytest

from tests.e2e.skill_eval.arms import (BARE, MCP_SERVER_NAME, TOOLS,
                                       TOOLS_ARM_TOOLSET, TOOLS_SKILLS,
                                       ArmContaminated, assert_absent,
                                       assert_present)
from tests.e2e.skill_eval.driver import (ToolCall, assert_absence_checkable,
                                         completed_calls, iad_calls)
from tests.e2e.skill_eval.prime_agent import (SETTINGS_RELPATH,
                                              SOCKET_PATH_LIMIT, UNATTRIBUTED,
                                              WORKER_SOCKET_RESERVE,
                                              PrimeAgentDriver,
                                              SessionNeverRan, agent_ended,
                                              listed_servers, mcp_call_sites,
                                              remove_session_tmpdir,
                                              session_cost,
                                              session_tmpdir_root,
                                              session_tokens, settings_for,
                                              tool_calls_from_events,
                                              write_settings)

FIXTURE = os.path.join(
    os.path.dirname(__file__), "fixtures", "prime_agent_session.jsonl"
)


def fixture_events():
    with open(FIXTURE, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def home_with_settings(tmp_path, settings: dict) -> str:
    path = os.path.join(str(tmp_path), SETTINGS_RELPATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(settings, handle)
    return str(tmp_path)


# --- the tool-call log out of a real run ---------------------------------------------------------


def test_the_fixture_yields_the_one_iris_info_call_it_made():
    """The run listed the tools, then called `iris_info`. One iad call, completed, attributed."""
    calls = tool_calls_from_events(fixture_events())
    iad = iad_calls(calls, MCP_SERVER_NAME)
    assert [call.name for call in iad] == ["iris_info"]
    assert iad[0].arguments == {"what": "metadata"}
    assert UNATTRIBUTED not in [call.name for call in calls]


def test_the_ipython_cells_are_logged_as_the_builtin_calls_they_are():
    """Two cells ran, both `ok`. They are tool calls with no server, like opencode's `bash`."""
    calls = tool_calls_from_events(fixture_events())
    cells = [call for call in calls if call.name == "ipython"]
    assert len(cells) == 2
    assert all(call.server is None and call.completed for call in cells)
    assert completed_calls(calls) == len(calls)


def test_the_log_is_the_same_shape_the_opencode_driver_returns():
    calls = tool_calls_from_events(fixture_events())
    assert calls and all(isinstance(call, ToolCall) for call in calls)


def test_listing_the_tools_is_not_counted_as_calling_one():
    """`mcp.list_tools` is discovery. Counting it as a tool call inflates every reach figure by one,
    and it is reported separately because it is still proof the server answered."""
    events = fixture_events()
    assert listed_servers(events) == (MCP_SERVER_NAME,)
    assert "list_tools" not in [call.name for call in tool_calls_from_events(events)]


def test_a_cell_that_raised_leaves_its_calls_uncompleted():
    """`status: error` from the kernel. Which call failed is not knowable from the stream, so none of
    them counts as completed — a tool the agent could not use must not read as reachable.
    """
    events = [
        {
            "type": "tool_execution_start",
            "toolCallId": "c1",
            "toolName": "ipython",
            "args": {"code": 'await mcp.call_tool("iris-agentic-dev", "iris_doc", {})'},
        },
        {
            "type": "tool_execution_end",
            "toolCallId": "c1",
            "toolName": "ipython",
            "result": {"details": {"status": "error"}, "isError": True},
            "isError": True,
        },
    ]
    calls = tool_calls_from_events(events)
    assert [call.name for call in calls] == ["ipython", "iris_doc"]
    assert completed_calls(calls) == 0


def test_a_cell_with_no_end_event_is_not_a_completed_call():
    events = [
        {
            "type": "tool_execution_start",
            "toolCallId": "c1",
            "toolName": "ipython",
            "args": {"code": 'await mcp.call_tool("iris-agentic-dev", "iris_doc", {})'},
        }
    ]
    assert completed_calls(tool_calls_from_events(events)) == 0


# --- the parser's honesty ------------------------------------------------------------------------


def test_two_calls_in_one_cell_are_two_calls():
    code = (
        'await mcp.call_tool("iris-agentic-dev", "iris_doc", {"mode": "get"})\n'
        'await mcp.call_tool("iris-agentic-dev", "iris_compile", {})\n'
    )
    assert [(site.server, site.tool) for site in mcp_call_sites(code)] == [
        (MCP_SERVER_NAME, "iris_doc"),
        (MCP_SERVER_NAME, "iris_compile"),
    ]


def test_a_call_built_from_variables_is_unattributed_not_guessed():
    code = 'server = "iris-agentic-dev"\ntool = "iris_doc"\nawait mcp.call_tool(server, tool, {})'
    sites = mcp_call_sites(code)
    assert len(sites) == 1
    assert (sites[0].server, sites[0].tool) == (None, None)
    calls = tool_calls_from_events(
        [
            {
                "type": "tool_execution_start",
                "toolCallId": "c1",
                "toolName": "ipython",
                "args": {"code": code},
            },
            {
                "type": "tool_execution_end",
                "toolCallId": "c1",
                "toolName": "ipython",
                "result": {"details": {"status": "ok"}},
            },
        ]
    )
    unattributed = [call for call in calls if call.name == UNATTRIBUTED]
    assert len(unattributed) == 1
    assert unattributed[0].server is None
    # And it is not silently dropped: the cell plus one unattributed call.
    assert len(calls) == 2


def test_a_cell_that_will_not_parse_is_unattributed_rather_than_a_crash():
    code = 'await mcp.call_tool("iris-agentic-dev", "iris_doc",'
    sites = mcp_call_sites(code)
    assert len(sites) == 1
    assert sites[0].tool is None


def test_a_cell_with_no_mcp_call_in_it_contributes_nothing():
    assert mcp_call_sites("import pandas\nprint(2 + 2)") == ()


def test_a_loop_that_calls_a_tool_is_still_seen():
    """The call site is literal even though the number of calls is not knowable. One site, reported
    once, is an undercount that says so rather than an invented multiplier."""
    code = 'for name in ["A", "B"]:\n    await mcp.call_tool("iris-agentic-dev", "iris_doc", {"name": name})'
    sites = mcp_call_sites(code)
    assert [(site.server, site.tool) for site in sites] == [
        (MCP_SERVER_NAME, "iris_doc")
    ]
    assert sites[0].arguments is None  # not a literal dict


def test_keyword_form_is_read_too():
    code = 'await mcp.call_tool(server="iris-agentic-dev", tool="iris_query", arguments={"sql": "x"})'
    site = mcp_call_sites(code)[0]
    assert (site.server, site.tool, site.arguments) == (
        MCP_SERVER_NAME,
        "iris_query",
        {"sql": "x"},
    )


# --- the three arms as three settings files ------------------------------------------------------


def test_the_tools_arm_registers_exactly_one_stdio_server():
    settings = settings_for(TOOLS, binary="/opt/iad/iris-agentic-dev")
    assert list(settings["mcpServers"]) == [MCP_SERVER_NAME]
    server = settings["mcpServers"][MCP_SERVER_NAME]
    assert server["type"] == "stdio"
    assert server["command"] == "/opt/iad/iris-agentic-dev"
    assert server["args"] == ["mcp"]


def test_no_credential_is_ever_written_into_the_settings_file():
    """`prime-agent` refuses literal stdio env values — `ValueError: MCP stdio env values must use
    {"env": "NAME"} references` — and the refusal is also the harness rule worth keeping: the file
    names variables, the parent process holds the values."""
    server = settings_for(TOOLS, binary="iad")["mcpServers"][MCP_SERVER_NAME]
    assert server["env"]
    for name, value in server["env"].items():
        assert value == {"env": name}


def test_the_toolset_reaches_the_server_through_the_exported_environment():
    driver = PrimeAgentDriver()
    assert (
        driver.env_for(
            TOOLS,
            iris_host="localhost",
            iris_web_port="52780",
            iris_container="iris-dev-iris",
        )["IRIS_TOOLSET"]
        == TOOLS_ARM_TOOLSET
    )
    assert (
        "IRIS_TOOLSET"
        in settings_for(TOOLS, binary="iad")["mcpServers"][MCP_SERVER_NAME]["env"]
    )


def test_the_bare_arms_settings_has_no_mcp_section_at_all():
    """Absent, not empty — the same rule as `task_toml_environment`."""
    assert "mcpServers" not in settings_for(BARE, binary="iad")


def test_every_arm_switches_off_the_built_in_skill_pack():
    """`prime-agent` ships `prime-intellect`, `skill-creator` and `websearch` and loads them by
    default, so all three arms start contaminated. Even the skills arm wants only the iad pack: a
    built-in `websearch` description in the prompt is a skill nobody is measuring."""
    for arm in (BARE, TOOLS, TOOLS_SKILLS):
        assert settings_for(arm, binary="iad")["enableBuiltinSkills"] is False


def test_the_skills_arm_points_at_the_pack_and_the_others_do_not(tmp_path):
    pack = str(tmp_path / "skills")
    assert settings_for(TOOLS_SKILLS, binary="iad", skills_dir=pack)["skills"] == [pack]
    assert "skills" not in settings_for(TOOLS, binary="iad", skills_dir=pack)


def test_the_settings_file_is_asserted_as_a_parsed_string_not_a_dict(tmp_path):
    """The #110 pattern: assert on what was written, because a dict literal cannot catch a key that
    never reached the file."""
    path = write_settings(TOOLS, str(tmp_path), binary="iad")
    assert path == os.path.join(str(tmp_path), SETTINGS_RELPATH)
    with open(path, encoding="utf-8") as handle:
        written = json.loads(handle.read())
    assert list(written["mcpServers"]) == [MCP_SERVER_NAME]
    assert written["enableBuiltinSkills"] is False


# --- absence and presence, through this driver (FR-009) -----------------------------------------


def test_the_driver_names_where_prime_agent_keeps_registrations():
    driver = PrimeAgentDriver()
    assert driver.name == "prime-agent"
    locators = [source.locator for source in driver.mcp_sources()]
    assert "~/.prime/agent/settings.json" in locators
    assert_absence_checkable(driver)  # does not raise


def test_a_settings_file_holding_a_server_is_read_back(tmp_path):
    home = home_with_settings(
        tmp_path, {"mcpServers": {MCP_SERVER_NAME: {"type": "stdio"}}}
    )
    driver = PrimeAgentDriver()
    assert driver.registered_mcp_servers({"HOME": home}) == [MCP_SERVER_NAME]


def test_a_stale_settings_file_fails_the_bare_arm_with_the_path_named(tmp_path):
    home = home_with_settings(
        tmp_path, {"mcpServers": {MCP_SERVER_NAME: {"type": "stdio"}}}
    )
    driver = PrimeAgentDriver()
    with pytest.raises(ArmContaminated) as excinfo:
        assert_absent(BARE, {"HOME": home}, driver=driver)
    assert MCP_SERVER_NAME in str(excinfo.value)
    assert ".prime/agent/settings.json" in str(excinfo.value)


def test_a_project_settings_file_is_read_too(tmp_path):
    """`.prime/agent/settings.json` in the session's cwd, which a sandboxed HOME does not cover."""
    project = tmp_path / "work"
    path = project / SETTINGS_RELPATH
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"mcpServers": {MCP_SERVER_NAME: {}}}))
    driver = PrimeAgentDriver()
    assert driver.registered_mcp_servers(
        {"HOME": str(tmp_path / "empty-home"), "PWD": str(project)}
    ) == [MCP_SERVER_NAME]


def test_an_unreadable_settings_file_is_not_an_empty_arm(tmp_path):
    path = os.path.join(str(tmp_path), SETTINGS_RELPATH)
    os.makedirs(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("{not json")
    with pytest.raises(ArmContaminated) as excinfo:
        PrimeAgentDriver().registered_mcp_servers({"HOME": str(tmp_path)})
    assert SETTINGS_RELPATH in str(excinfo.value)


def test_the_tools_arm_is_provable_once_its_settings_are_written(tmp_path):
    driver = PrimeAgentDriver()
    with pytest.raises(ArmContaminated):
        assert_present(TOOLS, {"HOME": str(tmp_path)}, driver=driver)
    write_settings(TOOLS, str(tmp_path), binary="iad")
    assert_present(TOOLS, {"HOME": str(tmp_path)}, driver=driver)


# --- skills are somewhere else entirely ---------------------------------------------------------


def test_the_driver_names_every_place_a_skill_is_discovered_from():
    """Six locations, including the pack inside the install directory, which is not under the
    sandboxed HOME. A driver that checked only `~/.prime/agent/skills` would call a bare arm clean
    while `websearch` sat in its system prompt."""
    locators = [source.locator for source in PrimeAgentDriver().skill_sources()]
    assert "~/.prime/agent/skills" in locators
    assert "~/.agents/skills" in locators
    assert ".prime/agent/skills" in locators
    assert ".agents/skills" in locators
    assert any("settings" in locator for locator in locators)
    assert any("built-in" in locator for locator in locators)


def test_a_skill_in_the_sandbox_home_is_found(tmp_path):
    pack = tmp_path / ".prime" / "agent" / "skills" / "objectscript-review"
    pack.mkdir(parents=True)
    (pack / "SKILL.md").write_text("# objectscript-review\n")
    assert PrimeAgentDriver().installed_skills({"HOME": str(tmp_path)}) == [
        "objectscript-review"
    ]


def test_a_skill_under_the_home_fails_the_bare_arm(tmp_path):
    pack = tmp_path / ".agents" / "skills" / "iris-connectivity"
    pack.mkdir(parents=True)
    (pack / "SKILL.md").write_text("# iris-connectivity\n")
    with pytest.raises(ArmContaminated) as excinfo:
        assert_absent(BARE, {"HOME": str(tmp_path)}, driver=PrimeAgentDriver())
    assert "iris-connectivity" in str(excinfo.value)


def test_a_clean_home_is_a_bare_arm(tmp_path):
    assert_absent(BARE, {"HOME": str(tmp_path)}, driver=PrimeAgentDriver())


# --- what the stream gives away for free --------------------------------------------------------


def test_cost_is_summed_over_assistant_messages_not_turns():
    """`turn_end` repeats the last message's usage rather than totalling the turn, so summing turns
    both double-counts and misses. The fixture's real cost is $0.062364 across three messages.
    """
    events = fixture_events()
    assert round(session_cost(events), 6) == 0.062364
    assert session_tokens(events) == 4216 + 20939 + 21168


def test_the_stream_says_whether_the_agent_finished():
    """Unlike opencode, which never reliably emits its idle event, so `hit_the_clock` reads the
    clock. Here the tell exists, and it is worth having beside the clock rather than instead of it.
    """
    events = fixture_events()
    assert agent_ended(events) is True
    assert (
        agent_ended([event for event in events if event["type"] != "agent_end"])
        is False
    )


def test_a_session_carries_its_seconds_and_its_calls_through_the_boundary():
    driver = PrimeAgentDriver()
    session = driver.session_from_events(fixture_events(), session_seconds=27.9)
    assert session.session_seconds == 27.9
    assert completed_calls(session.tool_calls) == len(session.tool_calls)
    graded = driver.grade(session, reward=1.0, scored=True)
    assert graded.reward == 1.0
    assert graded.logprobs is None
    assert graded.metadata["cost_usd"] == pytest.approx(0.062364)


def test_the_refusals_still_hold_under_this_driver():
    driver = PrimeAgentDriver()
    session = driver.session_from_events(fixture_events())
    with pytest.raises(ValueError):
        driver.grade(session, scored=True)
    with pytest.raises(ValueError):
        driver.grade(session, reward=0.0, scored=False)
    with pytest.raises(ValueError):
        driver.grade(session, scored=False)


# --- the arm the driver configures is the arm it can prove --------------------------------------


class FakeEnv:
    """`IsolatedEnv`'s two public surfaces, without opencode. The driver owns its own environment;
    all it borrows is a scratch directory the caller will clean up."""

    def __init__(self, root):
        self.skills_dir = os.path.join(str(root), "skills")
        os.makedirs(self.skills_dir, exist_ok=True)

    def env_vars(self):
        return {}


def test_configuring_the_tools_arm_writes_the_settings_and_exports_the_variables(
    tmp_path,
):
    driver = PrimeAgentDriver()
    env_vars = driver.configure_arm(
        TOOLS,
        FakeEnv(tmp_path),
        (),
        iris_host="localhost",
        iris_web_port="52780",
        iris_container="iris-dev-iris",
        binary="/tmp/fake-iad-binary",
        openai_api_key="sk-test",
    )
    assert env_vars["HOME"].startswith(str(tmp_path))
    assert env_vars["IRIS_TOOLSET"] == TOOLS_ARM_TOOLSET
    assert env_vars["IRIS_HOST"] == "localhost"
    assert env_vars["OPENAI_API_KEY"] == "sk-test"
    # The sandbox HOME is the point: without it prime-agent reads the developer's own
    # ~/.prime/agent/settings.json, and the bare arm inherits whatever is in it.
    assert env_vars["HOME"] != os.path.expanduser("~")
    assert driver.registered_mcp_servers(env_vars) == [MCP_SERVER_NAME]
    assert_present(TOOLS, env_vars, skills_dir=None, driver=driver)


def test_configuring_the_bare_arm_produces_an_arm_that_passes_its_own_absence_check(
    tmp_path,
):
    driver = PrimeAgentDriver()
    env_vars = driver.configure_arm(
        BARE,
        FakeEnv(tmp_path),
        ("objectscript-review",),  # ignored: the arm decides, not the call site
        iris_host="localhost",
        iris_web_port="52780",
        iris_container="iris-dev-iris",
        binary="/tmp/fake-iad-binary",
    )
    assert driver.registered_mcp_servers(env_vars) == []
    assert driver.installed_skills(env_vars) == []
    assert "IRIS_TOOLSET" not in env_vars
    assert_absent(BARE, env_vars, driver=driver)


def test_a_skills_entry_in_the_settings_file_contaminates_the_bare_arm(tmp_path):
    """The `skills` array is a discovery location like any other, and it is the one a stale settings
    file would carry. Checking only the two directories would call this arm clean."""
    pack = tmp_path / "pack" / "iris-connectivity"
    pack.mkdir(parents=True)
    (pack / "SKILL.md").write_text("# iris-connectivity\n")
    home = home_with_settings(tmp_path / "home", {"skills": [str(tmp_path / "pack")]})
    with pytest.raises(ArmContaminated) as excinfo:
        assert_absent(BARE, {"HOME": home}, driver=PrimeAgentDriver())
    assert "iris-connectivity" in str(excinfo.value)


def test_a_pilot_style_model_string_is_split_into_provider_and_model(monkeypatch):
    """The pilot names its model `openai/gpt-4.1`, one string, because that is opencode's spelling.
    `prime-agent` wants `--provider openai --model gpt-4.1`, so the split happens at the boundary
    rather than at every call site — otherwise the two harnesses cannot be handed the same run.
    """
    seen = {}

    def fake_popen(argv, **kwargs):
        seen["argv"] = argv
        seen["env"] = kwargs.get("env") or {}
        return FakePopen('{"type": "agent_end"}\n')

    spawning(monkeypatch, fake_popen)
    driver = PrimeAgentDriver(binary="prime-agent")
    driver.collect_events("do the thing", {"HOME": "/tmp/h"}, model="openai/gpt-4.1")
    argv = seen["argv"]
    assert argv[argv.index("--provider") + 1] == "openai"
    assert argv[argv.index("--model") + 1] == "gpt-4.1"
    assert seen["env"]["TMPDIR"] != os.environ.get("TMPDIR")


def test_the_session_tmpdir_is_short_enough_for_the_daemons_worker_socket(monkeypatch):
    """The Phase 2 gate failed three arms on this and nothing else.

    `prime-agent`'s daemon binds `$TMPDIR/prime-agent-<pid-ish>/worker-<12hex>-<12hex>.sock`, and macOS
    caps a unix socket path at 104 bytes. The default `TMPDIR` on macOS is a 49-character
    `/var/folders/...` path, so the worker socket comes out at ~127 bytes: the bind silently truncates,
    the supervisor `lstat`s the untruncated name, and the run dies with `ENOENT` after a 30-second
    daemon timeout. Every arm then reports zero tool calls in 31 seconds, which reads exactly like an
    agent that ignored its tools.
    """
    monkeypatch.setenv("TMPDIR", "/var/folders/sh/xd6ss5td5jvfcqcns6wptq5j63nmv7/T/")
    seen = {}

    def fake_popen(argv, **kwargs):
        seen["env"] = kwargs.get("env") or {}
        return FakePopen('{"type": "agent_end"}\n')

    spawning(monkeypatch, fake_popen)
    PrimeAgentDriver().collect_events("do the thing", {"HOME": "/tmp/h"})
    tmpdir = seen["env"]["TMPDIR"]
    assert len(tmpdir) + WORKER_SOCKET_RESERVE <= SOCKET_PATH_LIMIT
    assert not tmpdir.startswith("/var/folders")


def test_a_session_that_emitted_nothing_is_a_harness_fault_with_the_stderr_attached(
    monkeypatch,
):
    """A run with no events did not happen, and it must not read as a run that failed.

    This is the Phase 2 gate's first failure mode from the other side: three arms came back FAIL with
    zero tool calls because the daemon died before the session started. FAIL is a claim about the
    agent. `SessionNeverRan` carries what the process said on stderr so the reason names the daemon.
    """

    def fake_popen(argv, **kwargs):
        failed = FakePopen(
            "not json at all\n",
            stderr="Error: Timed out after 30000ms waiting for the Prime Agent daemon",
        )
        failed.returncode = 1
        return failed

    spawning(monkeypatch, fake_popen)
    with pytest.raises(SessionNeverRan) as excinfo:
        PrimeAgentDriver().collect_events("do the thing", {"HOME": "/tmp/h"})
    assert "daemon" in str(excinfo.value)
    assert "exit 1" in str(excinfo.value)


def spawning(monkeypatch, popen, *, reap=None):
    """Patch the spawn, and the reaper with it.

    The reaper shells out through `subprocess.run`, which is `Popen` underneath — so a test that
    patched only the spawn would find `pkill` arriving at its fake. It has its own test below.
    """
    monkeypatch.setattr("tests.e2e.skill_eval.prime_agent.subprocess.Popen", popen)
    monkeypatch.setattr(
        "tests.e2e.skill_eval.prime_agent.reap_session_processes",
        reap or (lambda tmpdir: None),
    )


class FakePopen:
    """Just enough of `Popen` to test the timeout path. `communicate` raises the first time."""

    def __init__(self, stdout: str, *, timeout_first: bool = False, stderr: str = ""):
        self._stdout = stdout
        self._stderr = stderr
        self._timeout_first = timeout_first
        self.pid = 4242
        self.killed = False
        self.returncode = 0

    def communicate(self, input=None, timeout=None):
        if self._timeout_first:
            self._timeout_first = False
            raise subprocess.TimeoutExpired(
                cmd="prime-agent", timeout=timeout or 0, output=self._stdout
            )
        return self._stdout, self._stderr

    def kill(self):
        self.killed = True


def test_a_session_killed_on_the_clock_keeps_the_calls_it_already_made(monkeypatch):
    """A cell inside `prime-agent`'s kernel can block forever — `docker exec -it ... iris session` is
    one line the model reaches for — so the wall clock is what ends some sessions. Throwing the stream
    away at that point loses every tool call the arm made, which is the Story 5 reach number.
    """
    stdout = (
        '{"type": "tool_execution_start", "toolCallId": "c1", "toolName": "ipython",'
        ' "args": {"code": "await mcp.call_tool(\\"iris-agentic-dev\\", \\"iris_doc\\", {})"}}\n'
        '{"type": "tool_execution_end", "toolCallId": "c1", "toolName": "ipython",'
        ' "result": {"details": {"status": "ok"}}}\n'
    )
    fake = FakePopen(stdout, timeout_first=True)
    spawning(monkeypatch, lambda *a, **k: fake)
    events = PrimeAgentDriver().collect_events(
        "do the thing", {"HOME": "/tmp/h"}, timeout=1
    )
    assert [call.name for call in tool_calls_from_events(events)] == [
        "ipython",
        "iris_doc",
    ]
    assert fake.killed


def test_the_session_reaps_the_daemon_it_left_behind(monkeypatch):
    """`prime-agent` starts a detached daemon plus a worker per session, and killing the CLI leaves
    both running — eight of them accumulated across four timed-out gate sessions. They are keyed by
    the session's `TMPDIR`, which is how they can be reaped without touching anyone else's daemon.
    """
    reaped = []
    spawning(
        monkeypatch,
        lambda *a, **k: FakePopen('{"type": "agent_end"}\n'),
        reap=reaped.append,
    )
    PrimeAgentDriver().collect_events("do the thing", {"HOME": "/tmp/h"})
    assert len(reaped) == 1
    assert reaped[0].startswith(session_tmpdir_root())


def test_the_tmpdir_cleanup_cannot_fail_a_session_that_ran(monkeypatch):
    """Housekeeping does not get to decide whether an arm scored.

    The bare arm of a gate run came back unscored with
    `[Errno 66] Directory not empty: '/tmp/pa-.../node-compile-cache/v22.22.1-arm64-...'`: the reaper
    kills the daemon mid-write, node's compile cache lands in `TMPDIR` after the directory listing the
    cleanup walks, and the final `rmdir` fails. That session had finished, and `pilot.run_one` turns any
    exception out of `collect_events` into `passed=None` — so a stray cache file read as "the
    prime-agent session did not run".
    """
    seen = {}

    def fake_rmtree(path, ignore_errors=False, **kwargs):
        seen["ignore_errors"] = ignore_errors
        if (
            not ignore_errors
        ):  # what the real one does when the daemon wrote after the listing
            raise OSError(errno.ENOTEMPTY, "Directory not empty", path)

    monkeypatch.setattr("tests.e2e.skill_eval.prime_agent.shutil.rmtree", fake_rmtree)
    remove_session_tmpdir("/tmp/pa-whatever")  # must not raise
    assert seen["ignore_errors"] is True


def test_a_session_takes_its_tmpdir_with_it(monkeypatch):
    """Ignoring cleanup errors is not the same as skipping cleanup: a normal session leaves nothing."""
    made = {}

    def fake_popen(argv, **kwargs):
        made["tmpdir"] = (kwargs.get("env") or {})["TMPDIR"]
        os.makedirs(os.path.join(made["tmpdir"], "node-compile-cache"), exist_ok=True)
        return FakePopen('{"type": "agent_end"}\n')

    spawning(monkeypatch, fake_popen)
    events = PrimeAgentDriver().collect_events("do the thing", {"HOME": "/tmp/h"})
    assert [event["type"] for event in events] == ["agent_end"]
    assert not os.path.exists(made["tmpdir"])
