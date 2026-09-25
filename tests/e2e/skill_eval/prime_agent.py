"""The `prime-agent` driver — 120 T008, behind the boundary declared in `driver.py`.

Decision 5's second harness. What makes it more than an adapter is its tool model, probed in
research.md § prime-agent probe: `prime-agent` exposes exactly one model-visible tool, `ipython`, and
MCP servers are reachable only inside its kernel through `rlm.mcp`. So the JSON stream names
`ipython` and nothing else, and a tool call looks like this inside `tool_execution_start.args.code`:

    await mcp.call_tool("iris-agentic-dev", "iris_info", {"what": "metadata"})

FR-013 wants a per-tool log off that, which means parsing Python. The rule this module holds to is
that a literal call site is attributed and everything else — a server name in a variable, a cell that
will not parse — is reported as `UNATTRIBUTED`. An undercount is a smaller number and says so; an
invented attribution is a wrong number that publishes.

Two other differences from opencode are worth the reader's attention:

- **The arms are a settings file, not an env var.** `~/.prime/agent/settings.json` holds `mcpServers`,
  and its stdio `env` values must be `{"env": "NAME"}` references — a literal raises inside
  `prime-agent`. Convenient: no credential is ever written into a file an arm generates.
- **Skills load from six places, and three ship inside the install.** `enableBuiltinSkills: false` is
  therefore set in every arm, including `tools+skills`, which wants the iad pack and not `websearch`.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

from tests.e2e import billing
from tests.e2e.skill_eval.arms import (
    MCP_SERVER_NAME,
    TOOLS_ARM_TOOLSET,
    Arm,
    ArmContaminated,
)
from tests.e2e.skill_eval.driver import DriverRun, McpSource, ToolCall

#: Relative to `HOME`. Also the project-level path, relative to the session's working directory.
SETTINGS_RELPATH = ".prime/agent/settings.json"

#: The name a call gets when the code says a tool was called but not which one.
UNATTRIBUTED = "<unattributed>"

#: The one tool the model can see.
KERNEL_TOOL = "ipython"

#: The environment variables the iad server reads. Named here because the settings file may only
#: reference them, so the list is also the list the parent process has to export.
SERVER_ENV_NAMES = (
    "IRIS_HOST",
    "IRIS_WEB_PORT",
    "IRIS_CONTAINER",
    "IRIS_USERNAME",
    "IRIS_PASSWORD",
    "IRIS_TOOLSET",
)

MCP_SOURCES = (
    McpSource(kind="path", locator=f"~/{SETTINGS_RELPATH}"),
    McpSource(kind="path", locator=SETTINGS_RELPATH),
)

# Every place `docs/skills.md` says a skill is discovered from. The last two are not files this
# process can stat, and they are named anyway: the reader of a contamination message needs the whole
# list, and the built-in pack is the one that contaminates by default.
SKILL_SOURCES = (
    McpSource(kind="path", locator="~/.prime/agent/skills"),
    McpSource(kind="path", locator="~/.agents/skills"),
    McpSource(kind="path", locator=".prime/agent/skills"),
    McpSource(kind="path", locator=".agents/skills"),
    McpSource(kind="path", locator=f"the skills array in {SETTINGS_RELPATH}"),
    McpSource(kind="path", locator="the built-in pack inside the prime-agent install"),
)

_HOME_SKILL_DIRS = (".prime/agent/skills", ".agents/skills")


class SessionNeverRan(RuntimeError):
    """The process exited without emitting a single event, so there is nothing to grade.

    Raised rather than returned as an empty list: an empty list grades as a session the agent lost,
    and the two things are not the same claim.
    """


#: A unix socket path cannot exceed this on macOS (`sun_path`, 104 bytes; Linux allows 108).
SOCKET_PATH_LIMIT = 104

#: What `prime-agent`'s daemon appends to `TMPDIR` for a session worker:
#: `prime-agent-<10 digits>/worker-<12 hex>-<12 hex>.sock`, plus slack.
WORKER_SOCKET_RESERVE = 80


def reap_session_processes(tmpdir: str) -> None:
    """Kill the daemon and worker this session left behind, and nothing else.

    `prime-agent` starts a detached supervisor plus one worker per session. Killing the CLI leaves both
    alive: four timed-out gate sessions left eight processes running. Both name the session's `TMPDIR`
    in their command line — the socket lives there — so matching on it is precise enough to leave a
    developer's own interactive daemon alone.
    """
    if not tmpdir or not shutil.which("pkill"):
        return
    subprocess.run(
        ["pkill", "-9", "-f", tmpdir],
        capture_output=True,
        check=False,
    )


def remove_session_tmpdir(tmpdir: str) -> None:
    """Take the session's `TMPDIR` away, and never fail the run doing it.

    `reap_session_processes` kills the daemon while node is still writing its compile cache, so a file
    can land in the tree after the listing the cleanup walks and the final `rmdir` fails ENOTEMPTY.
    `tempfile.TemporaryDirectory` raises that at the caller, and the caller is `pilot.run_one`, which
    reads any exception here as a session that never ran — a finished bare arm was reported unscored
    exactly that way. What is left behind is a few kilobytes under `/tmp`; what would be lost is a
    graded run.
    """
    shutil.rmtree(tmpdir, ignore_errors=True)


def session_tmpdir_root() -> str:
    """A directory short enough that the daemon's worker socket still fits in a socket path.

    macOS hands every process a 49-character `/var/folders/...` `TMPDIR`, and `mkdtemp` under it adds
    another 15, which leaves the worker socket at about 127 bytes. The bind truncates, the supervisor
    `lstat`s the name it asked for, and the session dies `ENOENT` 30 seconds later — reported by every
    arm as a session with no tool calls, which is indistinguishable from an agent that ignored them.
    """
    candidates = [os.environ.get("PRIME_AGENT_TMP_ROOT"), "/tmp", tempfile.gettempdir()]
    for candidate in candidates:
        if not candidate or not os.path.isdir(candidate):
            continue
        # `mkdtemp` adds `/pa-XXXXXXXX`; 13 characters.
        if len(candidate) + 13 + WORKER_SOCKET_RESERVE <= SOCKET_PATH_LIMIT:
            return candidate
    return tempfile.gettempdir()


# --- reading the stream --------------------------------------------------------------------------


@dataclass(frozen=True)
class CallSite:
    """One `mcp.*` call found in a cell. `None` means the code did not say."""

    server: str | None
    tool: str | None
    arguments: dict | None = None


def _literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return None


def _is_mcp_call(func, attr: str) -> bool:
    """`mcp.<attr>(...)`, including `rlm.mcp.<attr>(...)`."""
    if not isinstance(func, ast.Attribute) or func.attr != attr:
        return False
    base = func.value
    if isinstance(base, ast.Name):
        return base.id == "mcp"
    return isinstance(base, ast.Attribute) and base.attr == "mcp"


def _sites(code: str, attr: str, arity: int) -> tuple[CallSite, ...]:
    if not code or f".{attr}" not in code:
        return ()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # The kernel may still have run part of it, and the text says a call was meant. Reporting one
        # unattributed call is the honest floor; guessing the name off a regex is not.
        return (CallSite(server=None, tool=None),)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_mcp_call(node.func, attr):
            continue
        keywords = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        positional = list(node.args)

        def pick(index, *names):
            if len(positional) > index:
                return _literal(positional[index])
            for name in names:
                if name in keywords:
                    return _literal(keywords[name])
            return None

        server = pick(0, "server", "server_name", "name" if arity == 1 else "server")
        tool = pick(1, "tool", "tool_name", "name") if arity > 1 else None
        arguments = pick(2, "arguments", "args", "params") if arity > 1 else None
        found.append(
            (
                (node.lineno, node.col_offset),
                CallSite(
                    server=server,
                    tool=tool,
                    arguments=arguments if isinstance(arguments, dict) else None,
                ),
            )
        )
    return tuple(site for _, site in sorted(found, key=lambda pair: pair[0]))


def mcp_call_sites(code: str) -> tuple[CallSite, ...]:
    """Every `mcp.call_tool(...)` in one cell, in source order.

    A call inside a loop is one site: the number of calls it makes is not knowable from the source,
    and reporting the site once is an undercount that can be explained.
    """
    return _sites(code, "call_tool", arity=3)


def list_tool_sites(code: str) -> tuple[CallSite, ...]:
    return _sites(code, "list_tools", arity=1)


def _cells(events):
    """`(toolCallId, code, completed)` per `ipython` cell, in stream order."""
    status = {}
    for event in events:
        if event.get("type") == "tool_execution_end":
            details = (event.get("result") or {}).get("details") or {}
            status[event.get("toolCallId")] = details.get("status") == "ok"
    for event in events:
        if event.get("type") != "tool_execution_start":
            continue
        call_id = event.get("toolCallId")
        yield (
            call_id,
            (event.get("args") or {}).get("code") or "",
            status.get(call_id, False),
            event.get("toolName") or KERNEL_TOOL,
        )


def tool_calls_from_events(events) -> tuple[ToolCall, ...]:
    """The tool-call log, per FR-013.

    Each cell contributes itself — it is a real tool call, with no MCP server behind it, the way
    opencode's `bash` is — followed by the MCP calls found inside it. A cell that ended in `error`
    completes nothing: which of its calls failed is not in the stream, and a tool the agent could not
    use must not read as reachable.
    """
    calls: list[ToolCall] = []
    for _, code, completed, tool_name in _cells(events):
        calls.append(
            ToolCall(
                name=tool_name,
                completed=completed,
                server=None,
                arguments={"code": code} if code else None,
            )
        )
        for site in mcp_call_sites(code):
            calls.append(
                ToolCall(
                    name=site.tool or UNATTRIBUTED,
                    completed=completed,
                    server=site.server,
                    arguments=site.arguments,
                )
            )
    return tuple(calls)


def listed_servers(events) -> tuple[str, ...]:
    """Servers the session asked for a tool list from, in order, deduplicated.

    Not tool calls — counting discovery as reach inflates every Story 5 figure — but still the
    strongest runtime evidence that the registration took.
    """
    seen = []
    for _, code, _, _ in _cells(events):
        for site in list_tool_sites(code):
            if site.server and site.server not in seen:
                seen.append(site.server)
    return tuple(seen)


def _assistant_usage(events):
    for event in events:
        if event.get("type") != "message_end":
            continue
        message = event.get("message") or {}
        if message.get("role") != "assistant":
            continue
        yield message.get("usage") or {}


def session_cost(events) -> float:
    """Dollars, summed over assistant messages.

    Not over `turn_end`: that event repeats its turn's last message usage rather than totalling the
    turn, so summing turns both double-counts and misses.
    """
    return sum(
        (usage.get("cost") or {}).get("total", 0.0)
        for usage in _assistant_usage(events)
    )


def session_tokens(events) -> int:
    return sum(usage.get("totalTokens", 0) for usage in _assistant_usage(events))


def agent_ended(events) -> bool:
    """Whether the run reported its own end. Beside the clock, not instead of it."""
    return any(event.get("type") == "agent_end" for event in events)


# --- the arms as settings -------------------------------------------------------------------------


def settings_for(
    arm: Arm, *, binary: str, cwd: str | None = None, skills_dir=None
) -> dict:
    """`settings.json` for one arm.

    The bare arm gets no `mcpServers` key rather than an empty one, for the reason
    `task_toml_environment` gives: an empty section is a section, and the next edit fills it in.
    """
    settings: dict = {"enableBuiltinSkills": False}
    if arm.tools:
        server = {
            "type": "stdio",
            "command": binary,
            "args": ["mcp"],
            "env": {name: {"env": name} for name in SERVER_ENV_NAMES},
        }
        if cwd:
            server["cwd"] = cwd
        settings["mcpServers"] = {MCP_SERVER_NAME: server}
    if arm.skills and skills_dir:
        settings["skills"] = [skills_dir]
    return settings


def write_settings(arm: Arm, home: str, **kwargs) -> str:
    path = os.path.join(home, SETTINGS_RELPATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(settings_for(arm, **kwargs), handle, indent=2)
    return path


@dataclass(frozen=True)
class DriverSession:
    """What the session produced, before anything grades it. Same shape as the opencode driver's."""

    transcript: str
    tool_calls: tuple[ToolCall, ...]
    session_seconds: float
    cost_usd: float = 0.0
    tokens: int = 0
    ended: bool = False


class PrimeAgentDriver:
    """`prime-agent --mode json --no-session -p`, behind the boundary."""

    name = "prime-agent"

    def __init__(
        self,
        harness_version: str | None = None,
        binary: str = "prime-agent",
        node_bin: str | None = None,
    ):
        self.harness_version = harness_version
        self.binary = binary
        # Node 22.8.0 or newer, or the CLI refuses to start. Homebrew's default `node` is 20.
        self.node_bin = node_bin or os.environ.get("PRIME_AGENT_NODE_BIN")

    # --- FR-009: where things hide

    def mcp_sources(self) -> tuple[McpSource, ...]:
        return MCP_SOURCES

    def skill_sources(self) -> tuple[McpSource, ...]:
        return SKILL_SOURCES

    def _settings_paths(self, env_vars: dict) -> tuple[str, ...]:
        home = env_vars.get("HOME") or ""
        cwd = env_vars.get("PWD") or ""
        return tuple(
            os.path.join(root, SETTINGS_RELPATH) for root in (home, cwd) if root
        )

    def _settings(self, env_vars: dict):
        """Every settings file this session would read, parsed."""
        for path in self._settings_paths(env_vars):
            if not os.path.isfile(path):
                continue
            try:
                with open(path, encoding="utf-8") as handle:
                    yield json.load(handle)
            except (json.JSONDecodeError, OSError) as exc:
                # An unparseable settings file is not an empty arm. prime-agent's own behaviour here
                # is not something the harness should be guessing about mid-run.
                raise ArmContaminated(
                    f"{path} is not readable as JSON ({exc}), so what this arm registers is unknown"
                ) from exc

    def registered_mcp_servers(self, env_vars: dict) -> list[str]:
        names: set[str] = set()
        for settings in self._settings(env_vars):
            names.update(settings.get("mcpServers") or {})
        return sorted(names)

    def installed_skills(self, env_vars: dict) -> list[str]:
        """Skill names discoverable from the sandboxed home and working directory.

        The built-in pack is not enumerated here — it lives in the install directory and is switched
        off by `enableBuiltinSkills: false`, which `settings_for` sets in every arm. `skill_sources`
        names it so a contamination message can point at it.
        """
        roots = []
        for base in (env_vars.get("HOME"), env_vars.get("PWD")):
            if not base:
                continue
            roots.extend(os.path.join(base, relative) for relative in _HOME_SKILL_DIRS)
        # The `skills` array is a discovery location like the four directories, and it is the one a
        # settings file left over from another arm would carry.
        for settings in self._settings(env_vars):
            roots.extend(
                os.path.expanduser(entry)
                for entry in (settings.get("skills") or [])
                if isinstance(entry, str)
            )
        found: set[str] = set()
        for root in roots:
            if not os.path.isdir(root):
                continue
            for entry in os.listdir(root):
                if os.path.isfile(os.path.join(root, entry, "SKILL.md")):
                    found.add(entry)
        return sorted(found)

    # --- FR-006: what a session produces

    def env_for(
        self,
        arm: Arm,
        *,
        iris_host: str,
        iris_web_port: str,
        iris_container: str,
        iris_username: str | None = None,
        iris_password: str | None = None,
    ) -> dict:
        """The variables the settings file only references. Empty for an arm with no server."""
        if not arm.tools:
            return {}
        env = {
            "IRIS_HOST": iris_host,
            "IRIS_WEB_PORT": iris_web_port,
            "IRIS_CONTAINER": iris_container,
            "IRIS_TOOLSET": TOOLS_ARM_TOOLSET,
        }
        if iris_username:
            env["IRIS_USERNAME"] = iris_username
        if iris_password:
            env["IRIS_PASSWORD"] = iris_password
        return env

    def configure_arm(
        self,
        arm: Arm,
        env,
        skill_names=(),
        *,
        iris_host: str,
        iris_web_port: str,
        iris_container: str,
        binary: str | None = None,
        openai_api_key: str | None = None,
        iris_username: str | None = None,
        iris_password: str | None = None,
        **_ignored,
    ) -> dict:
        """Build this arm's whole environment: a sandboxed `HOME`, its settings file, its skills.

        The sandboxed `HOME` is the load-bearing part. `prime-agent` reads
        `~/.prime/agent/settings.json`, and `opencode_runner._sandbox_env` exempts `HOME` — so without
        one, every arm would inherit whatever is in the developer's own file and the bare arm would be
        whatever they last configured. It sits beside `env.skills_dir` so the `IsolatedEnv` context
        manager still owns the cleanup.

        `skill_names` is only honoured for an arm with skills, the rule `arms.configure` holds to: the
        arm decides, not the call site.
        """
        root = os.path.dirname(os.path.abspath(env.skills_dir))
        home = os.path.join(root, "prime-home")
        os.makedirs(home, exist_ok=True)

        skills_dir = None
        if arm.skills:
            from tests.e2e.skill_eval.fire_rate import _install_skill_local

            for skill in skill_names:
                _install_skill_local(skill, env.skills_dir)
            skills_dir = os.path.abspath(env.skills_dir)

        write_settings(
            arm,
            home,
            # The iad server, not `prime-agent` itself. Two different binaries, one of which the
            # settings file spawns.
            binary=binary or os.environ.get("IAD_BINARY", "iris-agentic-dev"),
            skills_dir=skills_dir,
        )

        env_vars = {
            "HOME": home,
            "PATH": os.environ.get("PATH", ""),
            **self.env_for(
                arm,
                iris_host=iris_host,
                iris_web_port=iris_web_port,
                iris_container=iris_container,
                iris_username=iris_username or os.environ.get("IRIS_USERNAME"),
                iris_password=iris_password or os.environ.get("IRIS_PASSWORD"),
            ),
        }
        key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        if key:
            env_vars["OPENAI_API_KEY"] = key
        return env_vars

    def session_from_events(
        self, events, *, transcript: str = "", session_seconds: float = 0.0
    ) -> DriverSession:
        events = list(events)
        return DriverSession(
            transcript=transcript,
            tool_calls=tool_calls_from_events(events),
            session_seconds=session_seconds,
            cost_usd=session_cost(events),
            tokens=session_tokens(events),
            ended=agent_ended(events),
        )

    def grade(
        self,
        session: DriverSession,
        *,
        reward: float | None = None,
        scored: bool = False,
        reason: str | None = None,
    ) -> DriverRun:
        """Attach a verdict. The refusals live in `DriverRun`, not here."""
        return DriverRun(
            transcript=session.transcript,
            tool_calls=session.tool_calls,
            reward=reward,
            scored=scored,
            reason=reason,
            session_seconds=session.session_seconds,
            metadata={
                "cost_usd": session.cost_usd,
                "tokens": session.tokens,
                "agent_ended": session.ended,
            },
        )

    def collect_events(
        self,
        prompt: str,
        env_vars: dict,
        *,
        model: str | None = None,
        provider: str | None = None,
        timeout: int = 300,
        working_dir: str | None = None,
        arm: Arm | None = None,
    ) -> list[dict]:
        """One headless run, as a list of events. Newline-delimited JSON on stdout.

        `TMPDIR` is replaced per session on purpose: the daemon derives its worker socket identity
        partly from it, and reusing the outer `TMPDIR` under a sandboxed `HOME` hangs for 30 seconds
        and then fails on a socket that was never created.
        """
        # `openai/gpt-4.1` is opencode's spelling and the one the pilot holds, because the arms are
        # only comparable when the model is the same string everywhere. prime-agent wants the two
        # halves separately, so the split belongs here rather than at each call site.
        if model and "/" in model and not provider:
            provider, model = model.split("/", 1)

        argv = [self.binary, "--mode", "json", "--no-session"]
        if provider:
            argv += ["--provider", provider]
        if model:
            argv += ["--model", model]
        if working_dir:
            argv += ["--cwd", working_dir]
        if arm is not None and not arm.skills:
            argv.append("--no-skills")
        argv += ["-p", prompt]

        # Before anything is spawned — see `tests/e2e/billing.py`. The candidate driver bills the same
        # as the incumbent, so it is gated at the same place rather than trusted to be cheaper.
        billing.assert_allowed("a prime-agent session")
        env = dict(env_vars)
        if self.node_bin:
            env["PATH"] = f"{self.node_bin}:{env.get('PATH', '')}"
        # `mkdtemp` and not `TemporaryDirectory`: its cleanup raises at the caller, and the caller
        # cannot tell a failed cleanup from a session that never started.
        tmpdir = tempfile.mkdtemp(prefix="pa-", dir=session_tmpdir_root())
        env["TMPDIR"] = tmpdir
        try:
            # `Popen` rather than `run`, for the timeout path: a kernel cell can block forever (a
            # `docker exec -it ... iris session` is one line the model reaches for), and the events the
            # session had already emitted are the arm's tool-call log. `run` would discard them.
            process = subprocess.Popen(
                argv,
                cwd=working_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired as expired:
                process.kill()
                stdout = expired.output or ""
                stderr = expired.stderr or ""
                if isinstance(stdout, bytes):
                    stdout = stdout.decode("utf-8", "replace")
                if isinstance(stderr, bytes):
                    stderr = stderr.decode("utf-8", "replace")
        finally:
            # The daemon outlives the CLI, so this runs whether the session finished or was killed,
            # and the directory goes with it either way.
            reap_session_processes(tmpdir)
            remove_session_tmpdir(tmpdir)

        events = []
        for line in (stdout or "").splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if not events:
            raise SessionNeverRan(
                f"{self.binary} produced no events (exit {process.returncode}): "
                f"{(stderr or '').strip()[-800:] or 'nothing on stderr'}"
            )
        return events

    def run(self, prompt: str, **kwargs) -> DriverRun:
        """One session, graded by `check` if one is supplied — the opencode driver's contract."""
        check = kwargs.pop("check", None)
        env_vars = kwargs.pop("env_vars", {})
        session = self.session_from_events(
            self.collect_events(prompt, env_vars, **kwargs)
        )
        if check is None:
            return self.grade(
                session, scored=False, reason="no check was supplied for this run"
            )
        reward, scored, reason = check()
        return self.grade(session, reward=reward, scored=scored, reason=reason)
