"""Tests for the Harbor exporter — 120 T010 and T012, written before `export.py`.

Two rules run through the whole file:

- **The `task.toml` is asserted by parsing the emitted string** (FR-002), never by reading back a dict
  the exporter also built. That is the #110 pattern: a field the writer forgets is a key the reader
  never misses, and a dict-literal assertion agrees with the bug.
- **Every refusal is tested by constructing the refused task** (FR-005). A task with no reference, a
  check that cannot discriminate, a check that already passes against the fixture — each one is a
  corpus defect that produces a plausible number rather than an error, which is the 118 failure class.
"""

from __future__ import annotations

import os
import tomllib

import pytest

from benchmark.harbor.export import (
    ExportRefused,
    arm_slug,
    export_arms,
    export_task,
    workspace_version,
)
from tests.e2e.skill_eval.arms import (
    ARMS,
    BARE,
    MCP_SERVER_NAME,
    TOOLS,
    TOOLS_ARM_TOOLSET,
    TOOLS_SKILLS,
)
from tests.e2e.skill_eval.graded_task import Document, GradedTask


def a_task(**overrides) -> GradedTask:
    """A task shaped like the pilot corpus: a fixture that does not compile, a reference that does."""
    fields = {
        "id": "EX-01",
        "prompt": "The class Ex.Buggy in the BENCHMARK namespace does not compile. Fix it.\n",
        "check": 'write $select($classmethod("Ex.Buggy","Ok"):"PASS",1:"FAIL")\n',
        "fixtures": (Document(name="Ex.Buggy", content="Class Ex.Buggy { broken }\n"),),
        "solution": (Document(name="Ex.Buggy", content="Class Ex.Buggy { }\n"),),
    }
    fields.update(overrides)
    return GradedTask(**fields)


def no_live_check(task) -> None:
    """A validator that answers nothing, for the tests that are not about the live refusal."""


def toml_of(exported) -> dict:
    with open(
        os.path.join(exported.directory, "task.toml"), encoding="utf-8"
    ) as handle:
        return tomllib.loads(handle.read())


def read(exported, *parts) -> str:
    with open(os.path.join(exported.directory, *parts), encoding="utf-8") as handle:
        return handle.read()


# --- the emitted task.toml (FR-002) --------------------------------------------------------------


def test_the_emitted_toml_parses_and_pins_the_schema_version(tmp_path):
    """FR-002's `schema_version = "1.3"`, read out of the file rather than out of a dict."""
    exported = export_task(a_task(), TOOLS, str(tmp_path), validate=no_live_check)
    config = toml_of(exported)
    assert config["schema_version"] == "1.3"
    assert config["task"]["name"].endswith("/ex-01-tools")


def test_the_three_arms_are_three_mcp_variants_of_one_source_task(tmp_path):
    """FR-023 in the format rather than in my code: one task, three `task.toml` files.

    The bare arm has no `[[environment.mcp_servers]]` table at all. An empty list is a declaration
    that happens to be empty today and the next edit fills it in without anything noticing.
    """
    exported = export_arms(a_task(), str(tmp_path), validate=no_live_check)
    assert [item.arm for item in exported] == [arm.name for arm in ARMS]
    by_arm = {item.arm: toml_of(item) for item in exported}

    assert "mcp_servers" not in by_arm[BARE.name]["environment"]
    for arm in (TOOLS, TOOLS_SKILLS):
        servers = by_arm[arm.name]["environment"]["mcp_servers"]
        assert len(servers) == 1
        assert servers[0]["name"] == MCP_SERVER_NAME
        assert servers[0]["transport"] == "stdio"
        # Harbor's schema: `command` is the executable, `args` the list. Not one list.
        assert isinstance(servers[0]["command"], str)
        assert servers[0]["args"] == ["mcp"]


def test_only_the_tool_arms_declare_a_toolset(tmp_path):
    """`Merged` sets the reach denominator (contracts/arm.md), and the bare arm names no toolset."""
    exported = export_arms(a_task(), str(tmp_path), validate=no_live_check)
    by_arm = {item.arm: toml_of(item) for item in exported}
    assert "IRIS_TOOLSET" not in by_arm[BARE.name]["environment"]["env"]
    for arm in (TOOLS, TOOLS_SKILLS):
        assert (
            by_arm[arm.name]["environment"]["env"]["IRIS_TOOLSET"] == TOOLS_ARM_TOOLSET
        )


def test_only_the_skills_arm_declares_a_skills_dir(tmp_path):
    """`environment.skills_dir` is the arm's second knob, and it is absent — not empty — elsewhere."""
    skills_root = tmp_path / "pack"
    (skills_root / "objectscript-guardrails").mkdir(parents=True)
    (skills_root / "objectscript-guardrails" / "SKILL.md").write_text("# guardrails\n")

    exported = export_arms(
        a_task(),
        str(tmp_path / "out"),
        validate=no_live_check,
        skills_root=str(skills_root),
    )
    by_arm = {item.arm: (item, toml_of(item)) for item in exported}

    for arm in (BARE, TOOLS):
        item, config = by_arm[arm.name]
        assert "skills_dir" not in config["environment"]
        assert not os.path.exists(os.path.join(item.directory, "environment", "skills"))

    item, config = by_arm[TOOLS_SKILLS.name]
    assert config["environment"]["skills_dir"] == "/skills"
    assert os.path.isfile(
        os.path.join(
            item.directory,
            "environment",
            "skills",
            "objectscript-guardrails",
            "SKILL.md",
        )
    )


def test_the_connection_is_env_template_syntax_and_carries_no_credential(tmp_path):
    """Harbor resolves `${VAR}` from the host at run time, so no password lands in a committed file."""
    exported = export_task(a_task(), TOOLS, str(tmp_path), validate=no_live_check)
    env = toml_of(exported)["environment"]["env"]
    assert env["IRIS_HOST"] == "${IRIS_HOST}"
    assert env["IRIS_PASSWORD"] == "${IRIS_PASSWORD}"
    assert env["IRIS_NAMESPACE"] == "BENCHMARK"
    assert "SYS" not in read(exported, "task.toml")


def test_the_task_container_is_allowed_to_reach_the_iris_host(tmp_path):
    """The one thing every arm needs equally: a route to IRIS.

    Spec 121's T002 read this out of Harbor's own docs — `network_mode = "allowlist"` plus
    `allowed_hosts` is the documented way a task container reaches a service outside it, and a shared
    reachable IRIS is decision 1's answer. A task with no route grades every arm FAIL for the same
    reason and the report reads as a tool that does not work.
    """
    exported = export_task(a_task(), TOOLS, str(tmp_path), validate=no_live_check)
    environment = toml_of(exported)["environment"]
    assert environment["network_mode"] == "allowlist"
    assert "${IRIS_HOST}" in environment["allowed_hosts"]


def test_the_iad_image_is_pinned_to_the_workspace_version(tmp_path):
    """A floating tag would change the tool surface under a corpus that is meant to be comparable."""
    exported = export_task(a_task(), TOOLS, str(tmp_path), validate=no_live_check)
    dockerfile = read(exported, "environment", "Dockerfile")
    assert f":v{workspace_version()}" in dockerfile
    # The tools are the thing under test; the environment must not go looking for a newer one.
    assert ":latest" not in dockerfile


def test_the_source_task_is_named_in_the_metadata(tmp_path):
    """Three directories, one source. Without this the arms are three unrelated tasks in a report."""
    exported = export_arms(a_task(), str(tmp_path), validate=no_live_check)
    for item in exported:
        metadata = toml_of(item)["metadata"]
        assert metadata["source_task"] == "EX-01"
        assert metadata["arm"] == item.arm


def test_the_directory_holds_every_file_harbor_requires(tmp_path):
    exported = export_task(a_task(), TOOLS, str(tmp_path), validate=no_live_check)
    for relative in (
        "instruction.md",
        "task.toml",
        os.path.join("environment", "Dockerfile"),
        os.path.join("environment", "seed.sh"),
        os.path.join("tests", "test.sh"),
        os.path.join("solution", "solve.sh"),
    ):
        assert os.path.isfile(os.path.join(exported.directory, relative)), relative
    for script in ("environment/seed.sh", "tests/test.sh", "solution/solve.sh"):
        path = os.path.join(exported.directory, *script.split("/"))
        assert os.access(path, os.X_OK), f"{script} is not executable"


def test_the_instruction_is_the_source_prompt_verbatim(tmp_path):
    """The prompt is the experiment. An exporter that rewrites it changes what the arms compare."""
    task = a_task()
    exported = export_task(task, TOOLS, str(tmp_path), validate=no_live_check)
    assert task.prompt.strip() in read(exported, "instruction.md")


def test_the_fixtures_travel_as_data_not_as_an_image(tmp_path):
    """Per plan.md: inline fixtures written into `environment/`, no per-task image to rebuild."""
    exported = export_task(a_task(), TOOLS, str(tmp_path), validate=no_live_check)
    assert "docker_image" not in toml_of(exported)["environment"]
    seed = read(exported, "environment", "seed.sh")
    assert "Class Ex.Buggy { broken }" in seed
    assert "Ex.Buggy.cls" in seed


def test_the_solution_applies_the_reference_and_not_the_fixture(tmp_path):
    exported = export_task(a_task(), TOOLS, str(tmp_path), validate=no_live_check)
    solve = read(exported, "solution", "solve.sh")
    assert "Class Ex.Buggy { }" in solve
    assert "broken" not in solve


def test_the_verifier_writes_the_reward_where_harbor_reads_it(tmp_path):
    """FR-004: the reward reaches the harness as a file, at Harbor's documented path."""
    exported = export_task(a_task(), TOOLS, str(tmp_path), validate=no_live_check)
    assert "/logs/verifier" in read(exported, "tests", "test.sh")


def test_the_timeouts_are_declared_for_both_the_agent_and_the_verifier(tmp_path):
    exported = export_task(
        a_task(), TOOLS, str(tmp_path), validate=no_live_check, agent_timeout_sec=300.0
    )
    config = toml_of(exported)
    assert config["agent"]["timeout_sec"] == 300.0
    assert config["verifier"]["timeout_sec"] > 0


# --- the refusals (FR-004, FR-005) ---------------------------------------------------------------


def test_export_refuses_a_task_with_no_reference_solution(tmp_path):
    """FR-005. Without a reference there is no way to tell a hard task from a broken check, which is
    the failure that cost this program four skills."""
    with pytest.raises(ExportRefused) as raised:
        export_task(a_task(solution=()), TOOLS, str(tmp_path), validate=no_live_check)
    assert "EX-01" in str(raised.value)
    assert not os.listdir(tmp_path)


def test_export_refuses_a_check_that_cannot_discriminate(tmp_path):
    """FR-004's word is deterministic, and a check with only one verdict word grades nothing."""
    with pytest.raises(ExportRefused) as raised:
        export_task(
            a_task(check='write "PASS"\n'), TOOLS, str(tmp_path), validate=no_live_check
        )
    assert "EX-01" in str(raised.value)


def test_export_refuses_a_check_that_already_passes_against_the_fixture(tmp_path):
    """FR-005's second half, and the only one that needs IRIS: a task every arm clears measures
    nothing, and it reports 0.00 lift with the tools working perfectly."""
    from tests.e2e.skill_eval.graded_task import CorpusInvalid

    def already_solved(task):
        raise CorpusInvalid(
            f"{task.id}: the check passes against the untouched fixture"
        )

    with pytest.raises(ExportRefused) as raised:
        export_task(a_task(), TOOLS, str(tmp_path), validate=already_solved)
    assert "EX-01" in str(raised.value)
    assert "untouched fixture" in str(raised.value)
    assert not os.listdir(tmp_path), (
        "a refused task must leave no half-written directory"
    )


def test_the_default_validator_is_the_live_one():
    """The live refusal is the default, so an export that skips it has to say so at the call site."""
    import inspect

    from tests.e2e.skill_eval import graded_task

    default = inspect.signature(export_task).parameters["validate"].default
    assert default is graded_task.validate_live


def test_the_validator_is_called_once_per_source_task_not_once_per_arm(tmp_path):
    """It costs a live IRIS round trip and the three arms share one source task."""
    calls = []
    export_arms(a_task(), str(tmp_path), validate=calls.append)
    assert [task.id for task in calls] == ["EX-01"]


def test_the_arm_slug_is_filesystem_safe():
    """`tools+skills` is an arm name and not a directory name."""
    assert arm_slug(TOOLS_SKILLS) == "tools-skills"
    assert arm_slug(BARE) == "bare"
