"""The 021 harnesses behind spec 120's declared boundary — 120 T005.

`claude_code.run_task` and `copilot.run_task` predate the boundary and keep their own shapes:
`{path, transcript, tool_call_count}` for one, `NotImplementedError` for the other. Neither is
rewritten here. This module wraps them so that:

- the five declared fields come back in one object, `logprobs` included and `None` (FR-006);
- the three refusals apply — no reward without `scored`, no `scored` without a reward, no unscored run
  without a reason (FR-010);
- absence is answerable, because each driver names the files its own harness reads (FR-009). Claude
  Code reads `.mcp.json` and `~/.claude.json`; VS Code reads `.vscode/mcp.json` and the user
  `settings.json`. `OPENCODE_CONFIG_CONTENT` means nothing to either, which is the whole reason the
  bare arm's check had to move behind the driver.

`ClaudeCodeDriver` reports the server it spawns itself. `_spawn_mcp` starts `iris-dev mcp`
unconditionally, so a driver that answered "no registration" because no config file said so would
report a contaminated bare arm as clean — the vacuity FR-009 exists to stop.

The Copilot driver stays unimplemented, and raises. What it must not do is return a run at reward 0:
that is 118's bug, where sessions with no tools were averaged into published pass rates as the
agent's failure.
"""

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_HERE, "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from tests.e2e.skill_eval.driver import (  # noqa: E402  (path fixed above)
    DriverRun,
    McpSource,
    ToolCall,
)

MCP_SERVER_NAME = "iris-agentic-dev"

# The keys MCP registrations live under across these two harnesses: Claude Code writes `mcpServers`,
# VS Code writes `servers`. Both are read, because a file holding either one contaminates a bare arm.
_REGISTRATION_KEYS = ("mcpServers", "servers", "mcp")


def _sibling(name):
    """Load a module next to this one. `benchmark/021` is not an importable package name, so neither
    a relative import nor a plain `import` reaches these files reliably — the contract tests load this
    module by path, and `__main__.py` loads it as `runner.drivers`."""
    import importlib.util

    if _HERE not in sys.path:
        # `claude_code` falls back to `from _client import ...` when it is not a package.
        sys.path.insert(0, _HERE)
    spec = importlib.util.spec_from_file_location(
        f"benchmark021_{name}", os.path.join(_HERE, f"{name}.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve(locator, env_vars, cwd, home):
    """Where a locator lands. `~` off `HOME`, everything else off the session's working directory."""
    home = env_vars.get("HOME") or home or os.path.expanduser("~")
    cwd = env_vars.get("PWD") or cwd or os.getcwd()
    if locator.startswith("~"):
        return os.path.join(home, locator[2:] if locator[1:2] == "/" else locator[1:])
    if os.path.isabs(locator):
        return locator
    return os.path.join(cwd, locator)


def _registrations_in(path):
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            config = json.load(handle)
    except (json.JSONDecodeError, OSError):
        # A registration file the harness cannot parse is not an empty arm. Naming the file is what
        # the reader needs; the arm fails either way.
        return [f"unreadable:{os.path.basename(path)}"]
    names = []
    for key in _REGISTRATION_KEYS:
        names.extend(config.get(key, {}) or {})
    return names


class _FileConfiguredDriver:
    """Shared plumbing for a harness that keeps its registrations in files on disk."""

    name = "file-configured"
    harness_version = None
    sources = ()

    def __init__(self, cwd=None, home=None):
        self._cwd = cwd
        self._home = home

    def mcp_sources(self):
        return self.sources

    def registered_mcp_servers(self, env_vars):
        names = set()
        for source in self.sources:
            if source.kind != "path":
                continue
            names.update(
                _registrations_in(
                    _resolve(source.locator, env_vars, self._cwd, self._home)
                )
            )
        return sorted(names)

    def run(self, prompt, **kwargs):
        raise NotImplementedError


class ClaudeCodeDriver(_FileConfiguredDriver):
    """`claude_code.run_task` — Anthropic API tool loop over a `iris-dev mcp` subprocess."""

    name = "claude-code"
    sources = (
        McpSource(kind="path", locator=".mcp.json"),
        McpSource(kind="path", locator="~/.claude.json"),
        McpSource(kind="path", locator="~/.claude/settings.json"),
    )

    def __init__(self, tools=False, cwd=None, home=None, harness_version=None):
        super().__init__(cwd=cwd, home=home)
        self.tools = tools
        self.harness_version = harness_version

    def registered_mcp_servers(self, env_vars):
        names = set(super().registered_mcp_servers(env_vars))
        if self.tools:
            # `_spawn_mcp` starts the server itself. Silence here would make the bare arm
            # unfalsifiable and the tools arm unprovable at the same time.
            names.add(MCP_SERVER_NAME)
        return sorted(names)

    def run_from_result(self, result, *, reward=None, scored=False, reason=None):
        """Adapt `run_task`'s dict to the declared shape. No session runs here."""
        return DriverRun(
            transcript=_transcript_text(result.get("transcript", ())),
            tool_calls=_tool_calls(result.get("transcript", ())),
            reward=reward,
            scored=scored,
            reason=reason,
            metadata={
                "path": result.get("path"),
                "tool_call_count": result.get("tool_call_count"),
            },
        )

    def run(self, prompt, **kwargs):
        """One session, then graded by `check` if one is supplied.

        `claude_code` is imported here rather than at module scope: it imports `anthropic` and builds
        a client, and a contract test must be able to load this module without either.
        """
        claude_code = _sibling("claude_code")
        check = kwargs.pop("check", None)
        task = kwargs.pop("task", None) or {"description": prompt}
        result = claude_code.run_task(task, kwargs.pop("path", "A"), **kwargs)
        if check is None:
            return self.run_from_result(
                result, scored=False, reason="no check was supplied for this run"
            )
        reward, scored, reason = check()
        return self.run_from_result(result, reward=reward, scored=scored, reason=reason)


class CopilotDriver(_FileConfiguredDriver):
    """The Copilot stub. Askable about absence, unable to run — and it says so rather than scoring."""

    name = "copilot"
    sources = (
        McpSource(kind="path", locator=".vscode/mcp.json"),
        McpSource(kind="path", locator="~/.vscode/mcp.json"),
    )

    def run(self, prompt, **kwargs):
        return _sibling("copilot").run_task(
            kwargs.pop("task", None) or {"description": prompt}, "A"
        )


def _transcript_text(transcript) -> str:
    lines = []
    for entry in transcript:
        if entry.get("text"):
            lines.append(entry["text"])
        elif entry.get("tool_name"):
            lines.append(f"[tool] {entry['tool_name']}")
        elif entry.get("tool_result"):
            lines.append(f"[result] {entry['tool_result']}")
    return "\n".join(lines)


def _tool_calls(transcript) -> tuple:
    """One `ToolCall` per tool use in the transcript.

    A call is `completed` when a result came back for it. `run_task`'s loop records a `tool_result`
    entry for every call it executed, so a call with no result is a turn the loop cut short — not
    evidence the tool was reachable.
    """
    results = {
        entry.get("tool_use_id")
        for entry in transcript
        if entry.get("role") == "tool_result"
    }
    calls = []
    for entry in transcript:
        name = entry.get("tool_name")
        if not name:
            continue
        use_id = entry.get("tool_use_id")
        calls.append(
            ToolCall(
                name=name,
                completed=use_id in results if use_id is not None else True,
                server=MCP_SERVER_NAME,
                arguments=entry.get("args"),
            )
        )
    return tuple(calls)
