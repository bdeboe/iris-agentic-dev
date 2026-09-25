"""Unit tests for the three arms — T024, written before `arms.py`.

FR-002 in test form. The bare arm is the denominator of every figure this program publishes, so a
bare run that quietly had tools is not a smaller result, it is a wrong one: the lift it produces is
the difference between "tools" and "tools", reported as the difference between "tools" and "nothing".

The rule is `assert_absent` raises rather than returning `False`. A contaminated arm must fail the
run. A boolean gets logged and the run continues, which is how 118's toolless nightlies published
nine skills at 0% — the environment was wrong, nothing raised, and the harness graded it anyway.

Nothing here starts a session or reaches IRIS. The subject is the environment an arm hands the
driver.
"""

import json
import os

import pytest

from tests.e2e.skill_eval.arms import (
    ARMS,
    BARE,
    TOOLS,
    TOOLS_ARM_TOOLSET,
    TOOLS_SKILLS,
    ArmContaminated,
    assert_absent,
    assert_present,
)


def env_vars(mcp=False, config_extra=None):
    config = {"provider": {}, "skills": {"paths": []}}
    if mcp:
        config["mcp"] = {
            "iris-agentic-dev": {
                "type": "local",
                "command": ["/usr/local/bin/iris-agentic-dev", "mcp"],
                "enabled": True,
            }
        }
    config.update(config_extra or {})
    return {"OPENCODE_CONFIG_CONTENT": json.dumps(config)}


def skills_dir(tmp_path, *names):
    root = tmp_path / "skills"
    root.mkdir(exist_ok=True)
    for name in names:
        (root / name).mkdir()
        (root / name / "SKILL.md").write_text(f"# {name}\n")
    return str(root)


# --- the three arms ----------------------------------------------------------------------------


def test_there_are_exactly_three_arms_and_they_are_ordered():
    """The ladder is bare → tools → tools+skills, and each adjacent pair is one comparison."""
    assert ARMS == (BARE, TOOLS, TOOLS_SKILLS)
    assert [arm.name for arm in ARMS] == ["bare", "tools", "tools+skills"]


def test_each_arm_declares_what_it_has():
    assert (BARE.tools, BARE.skills) == (False, False)
    assert (TOOLS.tools, TOOLS.skills) == (True, False)
    assert (TOOLS_SKILLS.tools, TOOLS_SKILLS.skills) == (True, True)


def test_the_tools_arm_registers_the_merged_toolset():
    """research.md § arms: `Merged`, because `Baseline` holds the Docker-dependent tools.

    This is the denominator for every Story 5 per-tool figure, so it is named in one place and
    asserted rather than left to whichever env var happened to be set.
    """
    assert TOOLS_ARM_TOOLSET == "merged"


# --- the bare arm's absence assertion (FR-002) --------------------------------------------------


def test_a_clean_bare_environment_passes(tmp_path):
    assert_absent(BARE, env_vars(), skills_dir=skills_dir(tmp_path))


def test_a_stale_mcp_registration_fails_the_bare_arm(tmp_path):
    with pytest.raises(ArmContaminated) as excinfo:
        assert_absent(BARE, env_vars(mcp=True), skills_dir=skills_dir(tmp_path))
    assert "iris-agentic-dev" in str(excinfo.value)


def test_a_reachable_skill_file_fails_the_bare_arm(tmp_path):
    directory = skills_dir(tmp_path, "objectscript-review")
    with pytest.raises(ArmContaminated) as excinfo:
        assert_absent(BARE, env_vars(), skills_dir=directory)
    assert "objectscript-review" in str(excinfo.value)


def test_a_claude_md_naming_an_iad_tool_fails_the_bare_arm(tmp_path):
    """The contamination that leaves no trace in the config: instructions in the working directory.

    A bare arm whose cwd holds `CLAUDE.md` saying "call `iris_doc(mode=\\"put\\")` after editing" is
    not a bare arm. It has the tools' knowledge without the tools, which measures neither.
    """
    guide = tmp_path / "CLAUDE.md"
    guide.write_text('After editing a .cls file, push it with iris_doc(mode="put").\n')
    with pytest.raises(ArmContaminated) as excinfo:
        assert_absent(BARE, env_vars(), project_files=[str(guide)])
    assert "CLAUDE.md" in str(excinfo.value)
    assert "iris_doc" in str(excinfo.value)


def test_a_project_file_that_says_nothing_about_the_tools_is_fine(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("Fix the class so the loop stops on an empty element.\n")
    assert_absent(BARE, env_vars(), project_files=[str(readme)])


def test_a_missing_project_file_is_not_contamination(tmp_path):
    assert_absent(BARE, env_vars(), project_files=[str(tmp_path / "gone.md")])


def test_the_failure_names_the_arm_and_what_was_found(tmp_path):
    with pytest.raises(ArmContaminated) as excinfo:
        assert_absent(BARE, env_vars(mcp=True), skills_dir=skills_dir(tmp_path, "x"))
    message = str(excinfo.value)
    assert "bare" in message
    # Both problems, not just the first: a run fixed for one and still failing on the other wastes
    # a whole session to say so.
    assert "mcp" in message.lower() and "x" in message


# --- the tools arm has its own absence, and its own presence ------------------------------------


def test_the_tools_arm_must_have_no_skills_but_may_have_mcp(tmp_path):
    assert_absent(TOOLS, env_vars(mcp=True), skills_dir=skills_dir(tmp_path))


def test_a_skill_file_fails_the_tools_arm_too(tmp_path):
    with pytest.raises(ArmContaminated):
        assert_absent(
            TOOLS,
            env_vars(mcp=True),
            skills_dir=skills_dir(tmp_path, "iris-connectivity"),
        )


def test_the_tools_skills_arm_asserts_nothing_absent(tmp_path):
    assert_absent(
        TOOLS_SKILLS, env_vars(mcp=True), skills_dir=skills_dir(tmp_path, "a-skill")
    )


def test_a_tools_arm_with_no_mcp_registration_is_a_mislabelled_bare_run(tmp_path):
    """The mirror of FR-002, and the bug 118 spent a spec on.

    `isolated_env.py` held a Homebrew path no runner has, so every "tools" session ran with no tools
    and the harness scored it as the skill failing. Absence in the arm that should have it is as
    fatal as presence in the arm that should not.
    """
    with pytest.raises(ArmContaminated) as excinfo:
        assert_present(TOOLS, env_vars(mcp=False), skills_dir=skills_dir(tmp_path))
    assert "no mcp" in str(excinfo.value).lower()


def test_the_skills_arm_needs_a_skill_on_disk(tmp_path):
    with pytest.raises(ArmContaminated) as excinfo:
        assert_present(
            TOOLS_SKILLS, env_vars(mcp=True), skills_dir=skills_dir(tmp_path)
        )
    assert "skill" in str(excinfo.value).lower()


def test_a_fully_configured_skills_arm_passes(tmp_path):
    assert_present(
        TOOLS_SKILLS, env_vars(mcp=True), skills_dir=skills_dir(tmp_path, "a-skill")
    )


def test_the_bare_arm_needs_nothing_present(tmp_path):
    assert_present(BARE, env_vars(), skills_dir=skills_dir(tmp_path))


# --- the environment an arm builds --------------------------------------------------------------


def test_the_tools_arm_env_carries_the_toolset_it_declares():
    """The arm's toolset reaches the MCP server, or the denominator is whatever was inherited."""
    from tests.e2e.isolated_env import IsolatedEnv
    from tests.e2e.skill_eval.arms import configure

    with IsolatedEnv(openai_api_key="sk-test") as env:
        configure(
            TOOLS,
            env,
            skill_names=(),
            iris_host="localhost",
            iris_web_port="52780",
            iris_container="iris-dev-iris",
            binary="/tmp/fake-iad-binary",
        )
        config = json.loads(env.env_vars()["OPENCODE_CONFIG_CONTENT"])
    server = config["mcp"]["iris-agentic-dev"]
    assert server["environment"]["IRIS_TOOLSET"] == TOOLS_ARM_TOOLSET


def test_the_arms_are_task_toml_sections_not_harness_branches():
    """research.md § arms: Harbor's `[[environment.mcp_servers]]` already is the arm knob.

    FR-023 wanted a fourth arm to need no new code path. This is where that claim is cashed: the arm
    difference is data, so `task_toml_environment` is a lookup, not a branch per driver.
    """
    from tests.e2e.skill_eval.arms import task_toml_environment

    tools = task_toml_environment(TOOLS, binary="/usr/local/bin/iris-agentic-dev")
    assert len(tools["mcp_servers"]) == 1
    server = tools["mcp_servers"][0]
    assert server["name"] == "iris-agentic-dev"
    assert server["transport"] == "stdio"
    # Harbor's schema 1.3: `command` is the executable, `args` is the list. A whole argv in `command`
    # is an executable whose name contains a space, so the arm would register no server at all.
    assert server["command"] == "/usr/local/bin/iris-agentic-dev"
    assert server["args"] == ["mcp"]
    assert "env" not in server, (
        "schema 1.3 has no per-server env; the toolset goes in [environment.env]"
    )


def test_the_bare_arms_task_toml_has_no_mcp_section_at_all():
    """Absent, not empty. `mcp_servers = []` is a declaration that happens to be empty today, and
    the next edit fills it in without anything noticing."""
    from tests.e2e.skill_eval.arms import task_toml_environment

    assert "mcp_servers" not in task_toml_environment(BARE, binary="iris-agentic-dev")


def test_the_bare_arm_env_registers_nothing():
    from tests.e2e.isolated_env import IsolatedEnv
    from tests.e2e.skill_eval.arms import configure

    with IsolatedEnv(openai_api_key="sk-test") as env:
        configure(
            BARE,
            env,
            skill_names=(
                "objectscript-review",
            ),  # ignored: the bare arm installs nothing
            iris_host="localhost",
            iris_web_port="52780",
            iris_container="iris-dev-iris",
        )
        config = json.loads(env.env_vars()["OPENCODE_CONFIG_CONTENT"])
        assert "mcp" not in config
        assert os.listdir(env.skills_dir) == []
        # And the arm checks itself: configure() leaves an environment its own arm accepts.
        assert_absent(BARE, env.env_vars(), skills_dir=env.skills_dir)


# --- absence is the driver's to describe — 120 T004, FR-009 -------------------------------------
#
# The failure mode here is vacuity, not weakness. Before this task `assert_absent` read
# `OPENCODE_CONFIG_CONTENT` and nothing else; point it at a second harness and it passes every arm,
# including a contaminated one. So the driver names the places, and a driver that names none fails.


class SettingsFileDriver:
    """A second harness, shaped like `prime-agent`: registrations in a file, not an env var."""

    name = "settings-file"
    harness_version = "0.0.0-test"

    def __init__(self, locator="agent/settings.json"):
        self._locator = locator

    def mcp_sources(self):
        from tests.e2e.skill_eval.driver import McpSource

        return (McpSource(kind="path", locator=self._locator),)

    def registered_mcp_servers(self, env_vars):
        root = env_vars.get("XDG_CONFIG_HOME")
        if not root:
            return []
        path = os.path.join(root, self._locator)
        if not os.path.isfile(path):
            return []
        with open(path, encoding="utf-8") as handle:
            return sorted(json.load(handle).get("mcpServers", {}))

    def run(self, prompt, **kwargs):  # pragma: no cover - not exercised here
        raise NotImplementedError


class BlindDriver:
    """A driver that names no place a registration could hide."""

    name = "blind"
    harness_version = None

    def mcp_sources(self):
        return ()

    def registered_mcp_servers(self, env_vars):
        return []

    def run(self, prompt, **kwargs):  # pragma: no cover - not exercised here
        raise NotImplementedError


def test_the_default_driver_is_opencode_so_the_pilots_call_sites_are_unchanged(
    tmp_path,
):
    """`pilot.py` calls `assert_absent(arm, env_vars, ...)` with no driver, and `pilot-121.json` is
    the only graded evidence spec 121 has. The default has to keep catching what it caught.
    """
    with pytest.raises(ArmContaminated) as excinfo:
        assert_absent(BARE, env_vars(mcp=True), skills_dir=skills_dir(tmp_path))
    assert "iris-agentic-dev" in str(excinfo.value)


def test_the_opencode_driver_passed_explicitly_still_catches_its_env_var(tmp_path):
    from tests.e2e.skill_eval.opencode_driver import OpencodeDriver

    with pytest.raises(ArmContaminated) as excinfo:
        assert_absent(
            BARE,
            env_vars(mcp=True),
            skills_dir=skills_dir(tmp_path),
            driver=OpencodeDriver(),
        )
    assert "iris-agentic-dev" in str(excinfo.value)
    assert_absent(
        BARE, env_vars(), skills_dir=skills_dir(tmp_path), driver=OpencodeDriver()
    )


def test_a_driver_naming_nothing_fails_the_arm_rather_than_passing_it(tmp_path):
    """The vacuity case. A green check that inspects no place is worse than a missing one, because
    the number it blesses gets published."""
    with pytest.raises(ArmContaminated) as excinfo:
        assert_absent(
            BARE, env_vars(), skills_dir=skills_dir(tmp_path), driver=BlindDriver()
        )
    message = str(excinfo.value)
    assert "blind" in message
    assert "no place" in message


def test_a_second_harnesss_settings_file_fails_the_bare_arm_with_the_path_named(
    tmp_path,
):
    """A registration in a file `OPENCODE_CONFIG_CONTENT` knows nothing about. The message names the
    path, because the person reading it has to go delete something."""
    root = tmp_path / "config"
    (root / "agent").mkdir(parents=True)
    settings = root / "agent" / "settings.json"
    settings.write_text(
        json.dumps({"mcpServers": {"iris-agentic-dev": {"command": "iad"}}})
    )
    with pytest.raises(ArmContaminated) as excinfo:
        assert_absent(
            BARE,
            {"XDG_CONFIG_HOME": str(root)},
            skills_dir=skills_dir(tmp_path),
            driver=SettingsFileDriver(),
        )
    message = str(excinfo.value)
    assert "agent/settings.json" in message
    assert "iris-agentic-dev" in message


def test_an_empty_second_harness_is_a_legitimately_bare_arm(tmp_path):
    root = tmp_path / "config"
    root.mkdir()
    assert_absent(
        BARE,
        {"XDG_CONFIG_HOME": str(root)},
        skills_dir=skills_dir(tmp_path),
        driver=SettingsFileDriver(),
    )


def test_presence_is_read_through_the_same_driver(tmp_path):
    """The mirror. A tools arm under a second harness must be provable too, or 118's bug returns the
    moment the harness changes — every session bare, every score published as the skill's.
    """
    root = tmp_path / "config"
    (root / "agent").mkdir(parents=True)
    driver = SettingsFileDriver()
    with pytest.raises(ArmContaminated) as excinfo:
        assert_present(
            TOOLS,
            {"XDG_CONFIG_HOME": str(root)},
            skills_dir=skills_dir(tmp_path),
            driver=driver,
        )
    assert "agent/settings.json" in str(excinfo.value)
    (root / "agent" / "settings.json").write_text(
        json.dumps({"mcpServers": {"iris-agentic-dev": {"command": "iad"}}})
    )
    assert_present(
        TOOLS,
        {"XDG_CONFIG_HOME": str(root)},
        skills_dir=skills_dir(tmp_path),
        driver=driver,
    )


def test_presence_under_a_blind_driver_fails_too(tmp_path):
    """`assert_present` cannot be the loophole: a driver that cannot be asked would report the tools
    arm unprovable-but-fine, which is the same vacuity from the other side."""
    with pytest.raises(ArmContaminated) as excinfo:
        assert_present(
            TOOLS,
            env_vars(mcp=True),
            skills_dir=skills_dir(tmp_path),
            driver=BlindDriver(),
        )
    assert "no place" in str(excinfo.value)


# --- the per-skill rung — Goal 2 ------------------------------------------------------------------
#
# PILOT-03 is the reason this exists. It passed in 3 tool calls in the tools arm and failed after 41
# calls and 206 s with all 34 skills installed. A ladder whose top rung is the whole pack measures
# the pack's bulk, not a skill's content, so a per-skill question needs a rung that holds exactly one
# skill — and the arm has to carry that name itself, because a call site that can pass the wrong
# skill list eventually does.


def test_a_per_skill_arm_names_the_skill_it_installs():
    from tests.e2e.skill_eval.arms import skill_arm

    arm = skill_arm("objectscript-list-patterns")
    assert arm.name == "tools+objectscript-list-patterns"
    assert (arm.tools, arm.skills) == (True, True)
    assert arm.skill_names == ("objectscript-list-patterns",)


def test_the_per_skill_ladder_is_tools_then_tools_plus_that_one_skill():
    """One comparison, and the lower rung is the shared `TOOLS` arm — the same object the tools
    ladder uses, so the two ladders cannot drift into two different definitions of "tools"."""
    from tests.e2e.skill_eval.arms import skill_ladder

    from tests.e2e.skill_eval.arms import skill_arm

    lower, upper = skill_ladder("objectscript-sql-patterns")
    assert lower is TOOLS
    assert upper == skill_arm("objectscript-sql-patterns")


def test_a_skill_the_pack_does_not_have_is_refused_at_construction():
    """A typo installs nothing, `assert_present` sees an empty skills dir and calls the arm broken —
    but only after the session. Refusing here costs nothing and names the actual mistake."""
    from tests.e2e.skill_eval.arms import skill_arm

    with pytest.raises(ValueError) as excinfo:
        skill_arm("objectscript-list-pattern")  # missing the s
    assert "objectscript-list-pattern" in str(excinfo.value)


def test_every_skill_named_by_a_skill_ladder_task_has_a_rung():
    """The twelve Goal 2 tasks each name one skill. A task naming a skill the pack does not ship
    would run its upper arm with nothing installed and publish that as the skill's own zero."""
    from tests.e2e.skill_eval import graded_task
    from tests.e2e.skill_eval.arms import skill_arm

    named = {task.skill for task in graded_task.skill_corpus()}
    assert named, "the skills ladder has no tasks"
    for skill in sorted(named):
        assert skill_arm(skill).skill_names == (skill,)


def test_the_per_skill_arm_is_not_one_of_the_three():
    """The tools ladder stays three rungs. A per-skill arm that leaked into `ARMS` would triple the
    bill for every task in the corpus."""
    from tests.e2e.skill_eval.arms import skill_arm

    assert skill_arm("iris-sql") not in ARMS
    assert len(ARMS) == 3


def test_the_arm_decides_the_skill_list_not_the_call_site(tmp_path):
    """`configure` takes a `skill_names` argument for the whole-pack arm's sake. An arm that carries
    its own names must ignore it, or the pilot's `shipped_skills()` default installs all 34 into the
    rung whose entire purpose is to hold one."""
    from tests.e2e.isolated_env import IsolatedEnv
    from tests.e2e.skill_eval.arms import configure, skill_arm

    arm = skill_arm("objectscript-guardrails")
    with IsolatedEnv(openai_api_key="sk-test") as env:
        configure(
            arm,
            env,
            skill_names=("objectscript-review", "objectscript-tdd", "iris-sql"),
            iris_host="localhost",
            iris_web_port="52780",
            iris_container="iris-dev-iris",
            binary="/tmp/fake-iad-binary",
        )
        assert os.listdir(env.skills_dir) == ["objectscript-guardrails"]


def test_the_whole_pack_arm_still_takes_its_list_from_the_call_site(tmp_path):
    from tests.e2e.isolated_env import IsolatedEnv
    from tests.e2e.skill_eval.arms import configure

    with IsolatedEnv(openai_api_key="sk-test") as env:
        configure(
            TOOLS_SKILLS,
            env,
            skill_names=("objectscript-review", "iris-sql"),
            iris_host="localhost",
            iris_web_port="52780",
            iris_container="iris-dev-iris",
            binary="/tmp/fake-iad-binary",
        )
        assert sorted(os.listdir(env.skills_dir)) == ["iris-sql", "objectscript-review"]


def test_a_skills_arm_asked_to_install_nothing_refuses(tmp_path):
    """The 118 failure, in the one shape the arm can still reach: `skills=True` and an empty list
    installs nothing, `assert_present` then fails the run after the session has been paid for."""
    from tests.e2e.isolated_env import IsolatedEnv
    from tests.e2e.skill_eval.arms import configure

    with IsolatedEnv(openai_api_key="sk-test") as env:
        with pytest.raises(ArmContaminated) as excinfo:
            configure(
                TOOLS_SKILLS,
                env,
                skill_names=(),
                iris_host="localhost",
                iris_web_port="52780",
                iris_container="iris-dev-iris",
                binary="/tmp/fake-iad-binary",
            )
    assert "tools+skills" in str(excinfo.value)


def test_what_an_arm_installs_is_readable_without_running_it():
    """The pilot's report records `skills_installed`. It read `shipped_skills()` unconditionally, so a
    subset install was reported as all 34 — the report would have named 34 skills for a rung holding
    one, and the per-skill result would have been unreadable afterwards."""
    from tests.e2e.skill_eval.arms import installed_skill_names, skill_arm

    assert installed_skill_names(BARE, ("iris-sql",)) == ()
    assert installed_skill_names(TOOLS, ("iris-sql",)) == ()
    assert installed_skill_names(TOOLS_SKILLS, ("iris-sql", "a")) == ("iris-sql", "a")
    assert installed_skill_names(skill_arm("iris-sql"), ("nope",)) == ("iris-sql",)
