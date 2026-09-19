"""The opencode driver — 120 T003. The incumbent harness behind the declared boundary.

`tests/e2e/opencode_runner.py` keeps the subprocess mechanics: sandboxed cwd, env scrubbing, the kill
tree, the JSON event stream. This module is the thin layer that makes those mechanics one
implementation of `AgentDriver` instead of the only way to run anything.

Nothing here changes what a session does or what its numbers are. `test_opencode_driver.py` pins that
against `pilot.completed_tool_calls`, because `tests/e2e/results/pilot-121.json` is the only graded
evidence spec 121 has and a boundary that re-reads the stream differently would silently invalidate
it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from tests.e2e.opencode_runner import collect_events, parse_mcp_tool
from tests.e2e.skill_eval.arms import ArmContaminated
from tests.e2e.skill_eval.driver import DriverRun, McpSource, ToolCall

CONFIG_ENV_VAR = "OPENCODE_CONFIG_CONTENT"

# Where opencode could be holding a registration. The env var is what `IsolatedEnv` sets; the two
# paths are what `XDG_CONFIG_HOME` is overridden to block, and they are named here so the bare arm's
# assertion covers them if that override ever regresses.
MCP_SOURCES = (
    McpSource(kind="env", locator=CONFIG_ENV_VAR),
    McpSource(kind="path", locator="opencode/config.json"),
    McpSource(kind="path", locator="opencode.json"),
)


@dataclass(frozen=True)
class DriverSession:
    """What the session itself produced, before anything grades it."""

    transcript: str
    tool_calls: tuple[ToolCall, ...]
    session_seconds: float
    timed_out: bool = False


def tool_calls_from_events(events) -> tuple[ToolCall, ...]:
    """The tool-call log, per spec 120 FR-013.

    Two things are deliberately kept that a count would throw away: which server served the call, so
    reach can be measured over the advertised iad surface rather than over every tool the harness
    ships, and the calls that errored, because a tool the agent reached for and could not use is a
    description problem and dropping it reports it as never tried.
    """
    calls = []
    for event in events:
        if event.get("type") != "tool_use":
            continue
        part = event.get("part", {})
        raw_name = part.get("tool", "")
        if not raw_name:
            continue
        server, tool = parse_mcp_tool(raw_name)
        state = part.get("state", {}) or {}
        status = state.get("status")
        error = state.get("error")
        calls.append(
            ToolCall(
                name=tool,
                completed=status == "completed",
                server=server,
                status=status,
                # Kept as text rather than parsed. Whatever shape a harness reports an error in, the
                # thing an attribution table needs is the sentence a reader can act on.
                error=str(error) if error else None,
            )
        )
    return tuple(calls)


class OpencodeDriver:
    """`opencode run --format json`, behind the boundary."""

    name = "opencode"

    def __init__(self, harness_version: str | None = None):
        self.harness_version = harness_version

    def mcp_sources(self) -> tuple[McpSource, ...]:
        return MCP_SOURCES

    def registered_mcp_servers(self, env_vars: dict) -> list[str]:
        raw = env_vars.get(CONFIG_ENV_VAR)
        if not raw:
            return []
        try:
            config = json.loads(raw)
        except json.JSONDecodeError as exc:
            # A config opencode cannot read is opencode's own failure, and the session it would
            # produce is a bare one. Returning [] here reports that as a legitimately empty arm.
            raise ArmContaminated(f"{CONFIG_ENV_VAR} is not JSON: {exc}") from exc
        return sorted(config.get("mcp", {}))

    def configure_arm(
        self,
        arm,
        env,
        skill_names=(),
        *,
        iris_host: str,
        iris_web_port: str,
        iris_container: str,
        binary: str | None = None,
        **_ignored,
    ) -> dict:
        """Apply the arm to an entered `IsolatedEnv` and return the session's environment.

        `arms.configure` still does the work, so nothing about opencode's arms changes. What changes
        is who asks: the pilot used to call it directly and then read `OPENCODE_CONFIG_CONTENT`, which
        made its `driver` parameter decorative — a second harness would have been handed a config it
        does not read and would have run every arm bare.

        `**_ignored` swallows the arguments other harnesses need (`openai_api_key` is already inside
        the `IsolatedEnv` config here) so one call site can serve both.
        """
        from tests.e2e.skill_eval.arms import configure

        configure(
            arm,
            env,
            tuple(skill_names),
            iris_host=iris_host,
            iris_web_port=iris_web_port,
            iris_container=iris_container,
            binary=binary,
        )
        return env.env_vars()

    def collect_events(self, prompt: str, env_vars: dict, **kwargs) -> list:
        """One session, as the raw opencode event stream.

        Straight delegation on purpose: `tests/e2e/results/pilot-121.json` came out of
        `opencode_runner.collect_events`, and a second spawn path here would re-baseline it.
        """
        return collect_events(prompt, env_vars, **kwargs)

    def session_from_events(
        self, events, *, transcript: str = "", session_seconds: float = 0.0
    ) -> DriverSession:
        return DriverSession(
            transcript=transcript,
            tool_calls=tool_calls_from_events(events),
            session_seconds=session_seconds,
        )

    def grade(
        self,
        session: DriverSession,
        *,
        reward: float | None = None,
        scored: bool = False,
        reason: str | None = None,
    ) -> DriverRun:
        """Attach a verdict to a session. The refusals live in `DriverRun`, not here."""
        return DriverRun(
            transcript=session.transcript,
            tool_calls=session.tool_calls,
            reward=reward,
            scored=scored,
            reason=reason,
            session_seconds=session.session_seconds,
            metadata={"timed_out": session.timed_out},
        )

    def run(self, prompt: str, **kwargs) -> DriverRun:
        """One session, graded by `check` if one is supplied.

        `check` takes no arguments and returns `(reward, scored, reason)`. It is a callable rather
        than a field because in this harness the verifier runs against live IRIS after the session,
        while under Harbor it runs inside the task container — the boundary has to hold both.
        """
        check = kwargs.pop("check", None)
        env_vars = kwargs.pop("env_vars", {})
        session = self.session_from_events(
            collect_events(prompt, env_vars, **kwargs),
            transcript="",
        )
        if check is None:
            return self.grade(
                session, scored=False, reason="no check was supplied for this run"
            )
        reward, scored, reason = check()
        return self.grade(session, reward=reward, scored=scored, reason=reason)
