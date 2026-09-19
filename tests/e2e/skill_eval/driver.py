"""The agent-driver boundary — 120 T002, per spec 120 FR-006, FR-009 and FR-010.

Spec 121 recorded this interface in its § Driver interface as "adopted unchanged" and no task in
either spec created it. It is created here because the harness is not settled: `opencode` drove spec
121's pilot, `prime-agent` is under evaluation, and everything above this line — the three arms, the
checks, the pairing, the statistics — must not care which one ran.

Three rules, all enforced here rather than at the call sites:

1. **A run cannot carry a reward it did not earn or withhold one it did.** `scored=True` with no
   reward and `scored=False` with one both raise at construction. That is spec 118's bug expressed as
   a type: nine skills published 0.00 from sessions that had no tools, because an ungraded session and
   a failed one were the same value.
2. **An unscored run states why.** Otherwise the only trace of a broken arm is a smaller `n`.
3. **Absence is the driver's to describe.** `assert_absent` cannot know where a harness keeps its MCP
   registrations, and a check that inspects the wrong place does not weaken — it goes vacuous, passing
   every arm including a contaminated one. A driver that names no place fails the arm.

`logprobs` is `None` everywhere and is kept anyway: spec 120's Decision 2 chose harness optimization
over policy training, and the field is what keeps a vLLM-backed driver an addition rather than a
rewrite if that decision is ever reopened.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from tests.e2e.skill_eval.arms import ArmContaminated

# Where a harness can keep an MCP registration. `env` is read out of the session's environment,
# `path` off disk — opencode uses the first (`OPENCODE_CONFIG_CONTENT`), prime-agent the second
# (`~/.prime/agent/settings.json`), and a driver that uses both names both.
MCP_SOURCE_KINDS = ("env", "path")


@dataclass(frozen=True)
class McpSource:
    kind: str
    locator: str

    def __post_init__(self) -> None:
        if self.kind not in MCP_SOURCE_KINDS:
            raise ValueError(
                f"unknown mcp source kind {self.kind!r}; expected one of "
                f"{', '.join(MCP_SOURCE_KINDS)}"
            )

    def describe(self) -> str:
        return f"{self.kind} {self.locator}"


@dataclass(frozen=True)
class ToolCall:
    """One call the session made. `server` is the MCP server that served it, or None for a builtin.

    The distinction is the denominator of every Story 5 reach figure: a `bash` call and an `iris_doc`
    call are both tool calls, and only one of them is the surface under measurement.
    """

    name: str
    completed: bool
    server: str | None = None
    arguments: dict | None = None


@dataclass(frozen=True)
class DriverRun:
    """What one session produced, whoever drove it."""

    transcript: str
    tool_calls: tuple[ToolCall, ...]
    reward: float | None
    scored: bool
    logprobs: None = None
    reason: str | None = None
    session_seconds: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.scored and self.reward is None:
            raise ValueError(
                "a scored run with no reward is not a result: either the check answered, in which "
                "case pass its reward, or it did not, in which case scored is False"
            )
        if not self.scored and self.reward is not None:
            raise ValueError(
                f"an unscored run must not carry a reward, and this one carries {self.reward}. "
                "Averaging it is how a harness fault becomes the agent's fault (spec 118)"
            )
        if not self.scored and not self.reason:
            raise ValueError(
                "an unscored run must carry a reason saying why it could not be graded, or the only "
                "trace of a broken arm is a pair count nobody can explain"
            )


def completed_calls(tool_calls) -> int:
    """Calls that finished. An abandoned call is not evidence the tool was reachable."""
    return sum(1 for call in tool_calls if call.completed)


def iad_calls(tool_calls, server: str) -> tuple[ToolCall, ...]:
    """The completed calls served by the iad MCP server, which is what reach is measured over."""
    return tuple(
        call for call in tool_calls if call.completed and call.server == server
    )


@runtime_checkable
class AgentDriver(Protocol):
    """The boundary. `opencode_runner`, `prime_agent`, `claude_code` and `copilot` implement it."""

    name: str
    harness_version: str | None

    def mcp_sources(self) -> tuple[McpSource, ...]:
        """Every place this harness could be holding an MCP registration."""

    def registered_mcp_servers(self, env_vars: dict) -> list[str]:
        """The server names actually registered, read from this driver's own sources."""

    def run(self, prompt: str, **kwargs) -> DriverRun:
        """One session. Raises nothing for a failed session — that is `scored=False` with a reason."""


def assert_absence_checkable(driver) -> None:
    """Raise unless this driver can be asked where a registration would hide (FR-009).

    Called before the bare arm runs, not after. A driver naming no sources makes `assert_absent`
    report every arm clean, and the bare arm's entire job is to be verifiably empty — so an
    unaskable driver fails the arm rather than blessing it.
    """
    if not driver.mcp_sources():
        raise ArmContaminated(
            f"driver {driver.name} names no place an MCP registration could hide, so the bare arm's "
            "emptiness cannot be asserted and its number would be unfalsifiable (FR-002)"
        )
