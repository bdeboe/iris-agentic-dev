"""The three arms — 121 T025.

An arm is a configuration, not a code path. research.md § arms found that Harbor's `task.toml` already
has `[[environment.mcp_servers]]`, so bare / tools / tools+skills are three values of a published
schema; `task_toml_environment` returns those values and `configure` applies the same three to the
local `IsolatedEnv` the pilot runs through. That is FR-023 satisfied by the format rather than by me.

What no schema can check is FR-002: that the bare arm really had nothing. So the rest of this module
is two assertions, and both raise:

- `assert_absent` — the bare arm has no MCP registration, no reachable skill file, and no project
  file that names an iad tool. A bare run that quietly had tools does not report a smaller lift, it
  reports the difference between tools and tools while labelled the difference between tools and
  nothing.
- `assert_present` — the mirror, and the 118 bug. `isolated_env.with_mcp` held a Homebrew path no
  runner has, so nine skills published 0% from sessions that had no tools at all. An arm missing what
  it is named for is as fatal as an arm holding what it is not.

Raising rather than returning a bool is the whole point. A boolean gets logged next to a number that
then gets published.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# The toolset the tools arm registers, and therefore the denominator of every Story 5 reach figure.
# `Merged` because Constitution III requires those tools to work without `IRIS_CONTAINER`, which is
# the constraint a task container runs under; `Baseline` holds the Docker-dependent tools, which
# cannot reach IRIS from inside one at all. See research.md § arms.
TOOLS_ARM_TOOLSET = "merged"

MCP_SERVER_NAME = "iris-agentic-dev"

# Substrings that give away tool knowledge in a file the agent can read. Not a general scan: these
# are the names a `CLAUDE.md` or `AGENTS.md` written for this repo actually uses, and each one only
# means anything if the tools are there.
_TOOL_TELLS = (
    "iris_doc",
    "iris_execute",
    "iris_query",
    "iris_compile",
    "iris-agentic-dev",
    "docs_introspect",
    "skill(action=",
)


class ArmContaminated(RuntimeError):
    """An arm's environment does not match what the arm claims. The run must not produce a number."""


@dataclass(frozen=True)
class Arm:
    name: str
    tools: bool
    skills: bool
    #: The skills this arm installs, when the arm is the one that decides. Empty means "whatever the
    #: call site passes", which is what the whole-pack arm wants and what a per-skill rung must not
    #: allow — see `skill_arm`.
    skill_names: tuple[str, ...] = ()


BARE = Arm(name="bare", tools=False, skills=False)
TOOLS = Arm(name="tools", tools=True, skills=False)
TOOLS_SKILLS = Arm(name="tools+skills", tools=True, skills=True)

# Ordered: each adjacent pair is one comparison. bare→tools is the tools' value, tools→tools+skills is
# the skills' value on top of them.
ARMS: tuple[Arm, ...] = (BARE, TOOLS, TOOLS_SKILLS)


def skill_arm(skill: str) -> Arm:
    """The rung that holds exactly one skill — Goal 2.

    PILOT-03 is why this is not just `TOOLS_SKILLS` with a shorter list. It passed in 3 tool calls in
    the tools arm and failed after 41 calls and 206 s with all 34 skills installed; a top rung that
    carries the whole pack measures the pack's bulk against the skills' content and reports the sum.
    One skill per rung is the only way `tools -> tools+X` is a statement about X.

    The name goes in the arm rather than in the call site's argument because `pilot.run_one` defaults
    `skill_names` to `shipped_skills()`. An arm that took its list from there would silently install
    34 into the rung whose whole purpose is to hold one, and the run would look fine.

    An unknown skill raises here. `_install_skill_local` would raise later anyway, but by then the
    arm is inside a session the run has paid for, and the message would be about a missing file.
    """
    if skill not in _pack_skills():
        raise ValueError(
            f"{skill!r} is not in the shipped pack, so this rung would install nothing and publish "
            f"the result as that skill's own. Known: {', '.join(_pack_skills())}"
        )
    return Arm(name=f"tools+{skill}", tools=True, skills=True, skill_names=(skill,))


def skill_ladder(skill: str) -> tuple[Arm, Arm]:
    """One comparison: the shared tools arm, then that arm plus one skill.

    The lower rung is `TOOLS` itself and not a copy, so the skills question is asked against the same
    definition of "tools" the tools ladder publishes.
    """
    return (TOOLS, skill_arm(skill))


def installed_skill_names(
    arm: Arm, skill_names: tuple[str, ...] = ()
) -> tuple[str, ...]:
    """What `configure` would install for this arm, without running it.

    `pilot.report` records this. It used to record `shipped_skills()` unconditionally, so a subset
    install was reported as all 34 — a per-skill rung would have been labelled with the whole pack and
    the result unreadable a week later.
    """
    if not arm.skills:
        return ()
    return arm.skill_names or tuple(skill_names)


def _pack_skills() -> tuple[str, ...]:
    from tests.e2e.skill_eval.fire_rate import _SKILLS_PACK_DIR

    if not os.path.isdir(_SKILLS_PACK_DIR):
        return ()
    return tuple(
        sorted(
            name
            for name in os.listdir(_SKILLS_PACK_DIR)
            if os.path.isfile(os.path.join(_SKILLS_PACK_DIR, name, "SKILL.md"))
        )
    )


def task_toml_environment(arm: Arm, binary: str) -> dict:
    """The `[environment]` fragment for this arm, in Harbor's schema.

    The bare arm gets no `mcp_servers` key rather than an empty list — an empty list is a section
    that exists, and the next person to edit it fills it in.

    `command` is the executable and `args` the list, per Harbor's schema 1.3 (`core-concepts/tasks/
    configuration`). An earlier version of this put the whole argv in `command` and hung the toolset
    on a per-server `env` key, neither of which the schema has: Harbor would have taken the first as
    an executable named `iris-agentic-dev mcp` and dropped the second, so the tools arm would have
    registered nothing and reported it as the tools' score. The toolset belongs to `[environment.env]`,
    which `benchmark/harbor/export.py` writes.
    """
    if not arm.tools:
        return {}
    return {
        "mcp_servers": [
            {
                "name": MCP_SERVER_NAME,
                "transport": "stdio",
                "command": binary,
                "args": ["mcp"],
            }
        ]
    }


def configure(
    arm: Arm,
    env,
    skill_names: tuple[str, ...] = (),
    *,
    iris_host: str,
    iris_web_port: str,
    iris_container: str,
    binary: str | None = None,
):
    """Apply this arm to an entered `IsolatedEnv`, and return it.

    `skill_names` is ignored unless the arm has skills, so a caller cannot install a skill into the
    bare arm by passing the wrong argument — the arm decides, not the call site. An arm carrying its
    own `skill_names` overrides the argument entirely, for the same reason in the other direction.

    A skills arm with nothing to install raises rather than running. That is 118 in the one shape the
    arm can still reach: the session runs, `assert_present` fails it afterwards, and the model time is
    already spent.
    """
    if arm.tools:
        env.with_mcp(
            iris_host=iris_host,
            iris_web_port=iris_web_port,
            iris_container=iris_container,
            binary=binary,
            toolset=TOOLS_ARM_TOOLSET,
        )
    if arm.skills:
        from tests.e2e.skill_eval.fire_rate import _install_skill_local

        wanted = installed_skill_names(arm, tuple(skill_names))
        if not wanted:
            raise ArmContaminated(
                f"the {arm.name} arm has skills=True and nothing to install, so it would run as a "
                "tools session and report the difference as the skills' own zero"
            )
        for skill in wanted:
            _install_skill_local(skill, env.skills_dir)
    return env


def _default_driver():
    """opencode, the incumbent. Imported here rather than at module scope because `driver.py` reads
    `ArmContaminated` from this module, and because the default must stay a default: spec 120
    Decision 5 has `prime-agent` under evaluation, so no call site should name a harness.

    One function builds it, in `opencode_driver`, so the driver the arm assertions check under is the
    same object the session runs under and the report attributes it to.
    """
    from tests.e2e.skill_eval.opencode_driver import default_driver

    return default_driver()


def assert_absent(
    arm: Arm,
    env_vars: dict,
    skills_dir: str | None = None,
    project_files=(),
    driver=None,
) -> None:
    """Raise `ArmContaminated` if the arm holds anything it claims not to (FR-002).

    `driver` supplies the places a registration could hide (spec 120 FR-009). Reading one harness's
    env var, as this did before, does not weaken under a second harness — it goes vacuous, passing
    every arm including a contaminated one. So the driver is asked first, and a driver that names
    nowhere fails the arm rather than blessing it.
    """
    from tests.e2e.skill_eval.driver import assert_absence_checkable

    driver = driver or _default_driver()
    assert_absence_checkable(driver)
    problems: list[str] = []
    if not arm.tools:
        problems.extend(_mcp_problems(driver, env_vars))
        problems.extend(_instruction_problems(project_files))
    if not arm.skills:
        problems.extend(_skill_problems(skills_dir))
        problems.extend(_driver_skill_problems(driver, env_vars))
    if problems:
        raise ArmContaminated(
            f"the {arm.name} arm is contaminated, so its number would be a measurement of "
            f"something else: {'; '.join(problems)}"
        )


def assert_present(
    arm: Arm, env_vars: dict, skills_dir: str | None = None, driver=None
) -> None:
    """Raise `ArmContaminated` if the arm is missing what it is named for — the 118 failure.

    Same driver, same sources. An unaskable driver fails here too: a tools arm nobody can prove has
    tools is 118 from the other side, every session bare and every score published as the skill's.
    """
    from tests.e2e.skill_eval.driver import assert_absence_checkable

    driver = driver or _default_driver()
    assert_absence_checkable(driver)
    problems: list[str] = []
    if arm.tools and not driver.registered_mcp_servers(env_vars):
        problems.append(
            f"no mcp server registered in any place the {driver.name} driver names "
            f"({_sources(driver)}), so this would run as a bare session reported as a tools session"
        )
    if arm.skills and not (
        _installed_skills(skills_dir) or _driver_skills(driver, env_vars)
    ):
        problems.append(f"no skill installed under {skills_dir}")
    if problems:
        raise ArmContaminated(
            f"the {arm.name} arm is not configured: {'; '.join(problems)}"
        )


def _sources(driver) -> str:
    return ", ".join(source.describe() for source in driver.mcp_sources())


def _installed_skills(skills_dir: str | None) -> list[str]:
    if not skills_dir or not os.path.isdir(skills_dir):
        return []
    return sorted(
        name
        for name in os.listdir(skills_dir)
        if os.path.isfile(os.path.join(skills_dir, name, "SKILL.md"))
    )


def _mcp_problems(driver, env_vars: dict) -> list[str]:
    servers = driver.registered_mcp_servers(env_vars)
    if not servers:
        return []
    return [
        f"mcp servers registered: {', '.join(servers)} — the {driver.name} driver reads "
        f"{_sources(driver)}, and one of those holds a registration this arm claims not to have"
    ]


def _driver_skills(driver, env_vars: dict) -> list[str]:
    """Skills this harness would discover on its own, if it can say.

    `skills_dir` is the one directory `IsolatedEnv` controls, and under opencode that is the whole
    story. `prime-agent` discovers from six places and ships three skills inside its own install, so
    a harness that can enumerate its own is asked to.
    """
    enumerate_skills = getattr(driver, "installed_skills", None)
    return list(enumerate_skills(env_vars)) if enumerate_skills else []


def _driver_skill_problems(driver, env_vars: dict) -> list[str]:
    found = _driver_skills(driver, env_vars)
    if not found:
        return []
    sources = ", ".join(
        source.describe() for source in getattr(driver, "skill_sources", lambda: ())()
    )
    return [
        f"skills the {driver.name} driver would load: {', '.join(found)}"
        + (f" — it discovers from {sources}" if sources else "")
    ]


def _skill_problems(skills_dir: str | None) -> list[str]:
    installed = _installed_skills(skills_dir)
    if not installed:
        return []
    return [f"skills reachable on disk: {', '.join(installed)}"]


def _instruction_problems(project_files) -> list[str]:
    problems = []
    for path in project_files:
        if not os.path.isfile(path):
            continue
        text = open(path, encoding="utf-8", errors="replace").read()
        tells = [tell for tell in _TOOL_TELLS if tell in text]
        if tells:
            problems.append(
                f"{os.path.basename(path)} names {', '.join(tells)} — tool knowledge without "
                "the tools measures neither"
            )
    return problems
