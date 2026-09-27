"""Unit tests for IsolatedEnv — T005, extended for 118 T006/T007."""

import json
import os
import subprocess
import threading

import pytest

from tests.e2e.isolated_env import IsolatedEnv
from tests.e2e.skill_eval import provenance


@pytest.fixture
def stub_iad_binary(tmp_path):
    """An executable file standing in for the binary, so config tests need no install."""
    binary = tmp_path / "iris-agentic-dev"
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)
    return str(binary)


def test_temp_dir_created_and_torn_down():
    with IsolatedEnv(openai_api_key="sk-test") as env:
        assert os.path.isdir(env.skills_dir)
        assert os.path.isdir(os.path.dirname(env.db_path))
        skills_dir = env.skills_dir
    assert not os.path.isdir(skills_dir)


def test_retain_on_failure(tmp_path):
    env = IsolatedEnv(openai_api_key="sk-test", keep_on_failure=True)
    env.__enter__()
    skills_dir = env.skills_dir
    env.__exit__(ValueError, ValueError("test error"), None)
    assert os.path.isdir(skills_dir), "Should be retained on failure"
    import shutil

    shutil.rmtree(skills_dir, ignore_errors=True)


def test_teardown_on_clean_exit():
    env = IsolatedEnv(openai_api_key="sk-test", keep_on_failure=True)
    env.__enter__()
    skills_dir = env.skills_dir
    env.__exit__(None, None, None)
    assert not os.path.isdir(
        skills_dir
    ), "Should be torn down on clean exit even with keep_on_failure"


def test_config_content_has_options_apikey():
    with IsolatedEnv(openai_api_key="sk-test-key") as env:
        cfg = json.loads(env.config_content)
        # Must use options.apiKey, not direct apiKey (I1 fix)
        assert cfg["provider"]["openai"]["options"]["apiKey"] == "sk-test-key"
        assert (
            "apiKey" not in cfg["provider"]["openai"]
        ), "apiKey must be nested under options"


def test_config_content_has_skills_path():
    with IsolatedEnv(openai_api_key="sk-test") as env:
        cfg = json.loads(env.config_content)
        assert env.skills_dir in cfg["skills"]["paths"]


def test_config_content_no_mcp_by_default():
    """No mcp key by default — global isolation handled via XDG_CONFIG_HOME."""
    with IsolatedEnv(openai_api_key="sk-test") as env:
        cfg = json.loads(env.config_content)
        assert "mcp" not in cfg


def test_with_mcp_adds_iris_agentic_dev(stub_iad_binary):
    with IsolatedEnv(openai_api_key="sk-test") as env:
        env.with_mcp(
            iris_host="localhost",
            iris_web_port="52780",
            iris_container="iris-dev-iris",
            binary=stub_iad_binary,
        )
        cfg = json.loads(env.config_content)
        assert "mcp" in cfg
        assert "iris-agentic-dev" in cfg["mcp"]
        mcp_env = cfg["mcp"]["iris-agentic-dev"]["environment"]
        assert mcp_env["IRIS_HOST"] == "localhost"
        assert mcp_env["IRIS_WEB_PORT"] == "52780"
        assert mcp_env["IRIS_CONTAINER"] == "iris-dev-iris"


def test_with_mcp_command_comes_from_the_resolver(tmp_path, monkeypatch):
    """The MCP command is whatever resolution found — 118 T006.

    This was `/opt/homebrew/bin/iris-agentic-dev`, written into the config unconditionally.
    On a GitHub runner that path does not exist, opencode started the MCP server, the spawn
    failed, and the session ran with no iad tools; the harness scored the transcripts anyway
    and published the zeros as skill measurements.
    """

    binary = tmp_path / "iris-agentic-dev"
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)
    monkeypatch.setenv("IAD_BINARY", str(binary))

    with IsolatedEnv(openai_api_key="sk-test") as env:
        env.with_mcp(
            iris_host="localhost", iris_web_port="52780", iris_container="iris-dev-iris"
        )
        cfg = json.loads(env.config_content)
        command = cfg["mcp"]["iris-agentic-dev"]["command"]
        assert command == [str(binary), "mcp"]
        assert command[0] == provenance.resolve_binary()


def test_with_mcp_accepts_an_explicit_binary(tmp_path):
    """The preflight resolves once; the sessions are handed the answer, not the search."""
    binary = tmp_path / "iad"
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)
    with IsolatedEnv(openai_api_key="sk-test") as env:
        env.with_mcp(
            iris_host="localhost",
            iris_web_port="52780",
            iris_container="iris-dev-iris",
            binary=str(binary),
        )
        cfg = json.loads(env.config_content)
        assert cfg["mcp"]["iris-agentic-dev"]["command"][0] == str(binary)


def test_with_mcp_refuses_to_configure_a_binary_that_is_not_there(
    tmp_path, monkeypatch
):
    """No binary means no tools, and a toolless session must not be silently configurable.

    The failure the harness had for a month was exactly this: an MCP entry pointing at a
    missing file is valid JSON, so nothing complained until the scores came back at zero.
    """

    monkeypatch.delenv("IAD_BINARY", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(provenance, "HOMEBREW_FALLBACK", str(tmp_path / "never"))

    with IsolatedEnv(openai_api_key="sk-test") as env:
        with pytest.raises(RuntimeError) as excinfo:
            env.with_mcp(
                iris_host="localhost",
                iris_web_port="52780",
                iris_container="iris-dev-iris",
            )
    message = str(excinfo.value)
    assert "IAD_BINARY" in message and "PATH" in message


def test_opencode_db_path_is_isolated():
    with IsolatedEnv(openai_api_key="sk-test") as env1:
        with IsolatedEnv(openai_api_key="sk-test") as env2:
            assert env1.db_path != env2.db_path


def test_env_vars_dict():
    with IsolatedEnv(openai_api_key="sk-test") as env:
        ev = env.env_vars()
        assert ev["OPENCODE_CONFIG_CONTENT"] == env.config_content
        assert ev["OPENCODE_DB"] == env.db_path
        assert ev["XDG_CONFIG_HOME"] == env.xdg_config
        assert (
            "XDG_DATA_HOME" not in ev
        )  # intentionally NOT overridden — see isolated_env.py
        assert os.path.isdir(env.xdg_config)


def test_env_vars_turn_off_claude_code_compat():
    """opencode reads `~/.claude/CLAUDE.md`, `~/.claude/skills` and `~/.agents/skills` unless told not to.

    `XDG_CONFIG_HOME` blocks none of them. Until 130 round 2 every harness session, both arms, ran
    with the operator's global CLAUDE.md as instructions and ~160 personal skills in the listing,
    one of them a personal copy of `ensemble-production`. `OPENCODE_DISABLE_CLAUDE_CODE` turns off
    the prompt, the Claude skill dirs and the external skill dirs together (opencode 1.14.17).
    """
    with IsolatedEnv(openai_api_key="sk-test") as env:
        assert env.env_vars()["OPENCODE_DISABLE_CLAUDE_CODE"] == "1"


# ---------------------------------------------------------------------------
# 118 T007 — the assertion whose absence let six skills run toolless for a month
# ---------------------------------------------------------------------------


def _mcp_tool_names(command: list[str], env: dict, timeout: int = 30) -> list[str]:
    """Speak MCP over stdio to the configured command and return the tool names.

    A live agent is not needed to answer "would this session have tools": the session gets
    its tools from this exact command line, so running it is the measurement. No IRIS
    either — `tools/list` reads the router.
    """
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env={**os.environ, **env},
    )
    killer = threading.Timer(timeout, proc.kill)
    killer.start()
    try:
        for request in (
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "iad-eval-toolcheck", "version": "0"},
                },
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ):
            proc.stdin.write(json.dumps(request) + "\n")
            proc.stdin.flush()
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get("id") == 2:
                tools = message.get("result", {}).get("tools", [])
                return [t.get("name", "") for t in tools]
        return []
    finally:
        killer.cancel()
        proc.kill()
        proc.wait(timeout=5)


@pytest.mark.requires_binary
def test_the_configured_mcp_command_serves_tools():
    """The command written into the config has to actually answer `tools/list`.

    This is the cheap half of T007 and the one that would have caught the real failure: the
    nightly wrote a Homebrew path into the MCP config on a runner that had no such file, and
    nothing between that and the published pass rate ever asked whether tools arrived.
    """
    binary = provenance.resolve_binary()
    if not binary:
        pytest.skip(
            "no iris-agentic-dev binary resolved — set IAD_BINARY to the build under test. "
            f"Searched: {'; '.join(c.describe() for c in provenance.binary_candidates())}"
        )
    with IsolatedEnv(openai_api_key="sk-test") as env:
        env.with_mcp(
            iris_host="localhost",
            iris_web_port="52780",
            iris_container="iris-dev-iris",
            binary=binary,
        )
        cfg = json.loads(env.config_content)
        command = cfg["mcp"]["iris-agentic-dev"]["command"]
        mcp_env = cfg["mcp"]["iris-agentic-dev"]["environment"]

    names = _mcp_tool_names(command, mcp_env)
    assert names, f"{command} served no tools, so a session using it would have none"
    assert any(n.startswith("iris_") for n in names), sorted(names)[:10]


@pytest.mark.skipif(
    os.environ.get("IAD_EVAL_LIVE_AGENT") != "1",
    reason=(
        "needs a real opencode session and an OpenAI key — set IAD_EVAL_LIVE_AGENT=1 to run. "
        "Skipped, NOT passed: nothing here has verified that an agent session sees iad tools."
    ),
)
@pytest.mark.billable  # spawns a real agent session
def test_isolated_env_has_tools():
    """A real session in an isolated env can call an iad tool.

    Named in the constitution's Bug Class Registry as the detector for
    `toolless-eval-session`. The 2026-08 nightlies ran nine skills a night with no iad
    tools, scored the transcripts, and published the zeros as measurements — for a month,
    because no test asked the agent to prove it had the tools.
    """
    from tests.e2e.opencode_runner import collect_events, parse_mcp_tool

    key = os.environ.get("OPENAI_API_KEY", "")
    assert key, "IAD_EVAL_LIVE_AGENT=1 needs OPENAI_API_KEY"

    with IsolatedEnv(openai_api_key=key) as env:
        env.with_mcp(
            iris_host=os.environ.get("IRIS_HOST", "localhost"),
            iris_web_port=os.environ.get("IRIS_WEB_PORT", "52780"),
            iris_container=os.environ.get("IRIS_CONTAINER", "iris-dev-iris"),
        )
        events = collect_events(
            "Call the check_config tool from the iris-agentic-dev MCP server and report "
            "the namespace it names. Do not answer from memory.",
            env.env_vars(),
            model=os.environ.get("IAD_EVAL_MODEL", "openai/gpt-4.1"),
        )

    called = set()
    for event in events:
        if event.get("type") != "tool_use":
            continue
        server, tool = parse_mcp_tool(event.get("part", {}).get("tool", ""))
        if server == "iris_agentic_dev":
            called.add(tool)
    assert called, (
        "the session called no iad tool, so it had none — every score from a session in "
        "this state measures the harness, not the skill"
    )


@pytest.mark.skipif(
    os.environ.get("IAD_EVAL_LIVE_AGENT") != "1",
    reason=(
        "needs a real opencode session and an OpenAI key — set IAD_EVAL_LIVE_AGENT=1 to run. "
        "Skipped, NOT passed: nothing here has verified what skills a session is offered."
    ),
)
@pytest.mark.billable  # spawns a real agent session
def test_isolated_env_offers_only_installed_skills():
    """The session's skill listing holds the installed skill and none of the operator's own.

    The 130 round-2 probe asked a session to list its skills and got ~60 names from
    `~/.claude/skills`. A tools arm that can load a personal skill is not a tools arm.
    """
    from tests.e2e.opencode_runner import collect_events
    from tests.e2e.skill_eval import fire_rate

    key = os.environ.get("OPENAI_API_KEY", "")
    assert key, "IAD_EVAL_LIVE_AGENT=1 needs OPENAI_API_KEY"

    with IsolatedEnv(openai_api_key=key) as env:
        fire_rate._install_skill_local("iris-query-plans", env.skills_dir)
        events = collect_events(
            "List, one per line, the name of every skill your skill tool can load. "
            "Print only the names. Load none of them.",
            env.env_vars(),
            model=os.environ.get("IAD_EVAL_MODEL", "openai/gpt-4.1"),
            timeout=180,
            working_dir=env.skills_dir,
        )
    text = "\n".join(
        e.get("part", {}).get("text", "") for e in events if e.get("type") == "text"
    )
    assert "iris-query-plans" in text, text[:500]
    for personal in ("grill-me", "grilling", "handoff", "eli5", "archify"):
        assert (
            personal not in text
        ), f"{personal} leaked into the session:\n{text[:800]}"
