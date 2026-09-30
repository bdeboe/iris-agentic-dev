"""FR-004 and FR-022 against live IRIS — T028's confirmation, and the pilot's preflight.

This is the half of corpus validation that only IRIS can answer: apply each task's fixture and the
check must FAIL; apply its reference solution and the same check must PASS. A task that cannot show
both is not allowed to produce a number, because a 0.00 from it is indistinguishable from the four
skills that read 0.00 through a broken check.

**No model tokens.** Every call here is `iris-agentic-dev exec` / `iris_compile` against
`iris-dev-iris`. This file is safe to run repeatedly, unlike the billable `test_debug_*.py` and
`test_integration.py` in this directory. It does need the container:

    docker ps --filter name=iris-dev-iris

Per-run isolation is by document reset before each task rather than by namespace drop: the pilot's
own runner drops and recreates BENCHMARK between arms, and dropping it here for a validation pass
would cost 30 seconds per task to prove something the reset already proves.
"""

import os
import subprocess

import pytest

from tests.e2e.skill_eval.graded_task import (
    BENCHMARK_NAMESPACE,
    CorpusInvalid,
    Document,
    GradedTask,
    all_tasks,
    apply_documents,
    created_classes,
    list_classes,
    package_prefixes,
    pilot_tasks,
    reset_documents,
    run_check,
    run_teardown,
    validate_live,
)

pytestmark = [
    # Load-bearing for CI: ci.yml filters on `not requires_iris`. Without the marker the filter
    # excuses nothing and the skipif below is the only thing keeping these off a runner with no
    # container -- which also means `pytest -m requires_iris` collected zero of them.
    pytest.mark.requires_iris,
    pytest.mark.skipif(
        subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                "name=iris-dev-iris",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
        ).stdout.strip()
        != "iris-dev-iris",
        reason="iris-dev-iris is not running, and IRIS is the only thing that can answer FR-004",
    ),
]


@pytest.fixture(scope="module", autouse=True)
def iris_connection():
    """The connection the CLI reads. Explicit rather than inherited, so a stray IRIS_NAMESPACE in the
    shell cannot point a validation pass at someone's working namespace."""
    previous = {
        key: os.environ.get(key)
        for key in (
            "IRIS_HOST",
            "IRIS_WEB_PORT",
            "IRIS_USERNAME",
            "IRIS_PASSWORD",
            "IRIS_NAMESPACE",
        )
    }
    os.environ.update(
        {
            "IRIS_HOST": os.environ.get("IRIS_HOST", "localhost"),
            "IRIS_WEB_PORT": os.environ.get("IRIS_WEB_PORT", "52780"),
            "IRIS_USERNAME": os.environ.get("IRIS_USERNAME", "_SYSTEM"),
            "IRIS_PASSWORD": os.environ.get("IRIS_PASSWORD", "SYS"),
            "IRIS_NAMESPACE": BENCHMARK_NAMESPACE,
        }
    )
    yield
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


AI_HUB_SKILL = "iris-ai-hub"
AI_HUB_CONTAINER = "iad-aihub-iris"
AI_HUB_WEB_PORT = "52781"


def _running(name: str) -> bool:
    names = subprocess.run(
        ["docker", "ps", "--filter", f"name={name}", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    ).stdout.split()
    return name in names


@pytest.mark.parametrize(
    "task",
    [task for task in all_tasks() if task.skill != AI_HUB_SKILL],
    ids=lambda task: task.id,
)
def test_every_committed_task_is_false_before_and_true_after(task):
    """FR-004 and FR-022 for one task, which is the whole of what makes it gradeable.

    Twice, because the second pass starts from the state the first pass left — the reference solution
    applied and whatever globals it wrote. A task that only satisfies FR-004 on a clean namespace
    leaks state into the next arm, and the pairing would then report one arm's work in the next arm's
    column. PILOT-05 failed exactly this way: its check read a global an earlier reference had already
    set, so it passed before the agent ran.
    """
    validate_live(task)
    validate_live(task)


def test_a_check_that_is_already_true_is_rejected():
    """The FR-004 rejection, demonstrated rather than asserted about.

    The fixture here is already correct, so the check passes before the agent does anything. That
    task would report 0.00 lift from every arm and read as "the tools did not help".
    """
    already_solved = GradedTask(
        id="PILOT-DEMO-TRIVIAL",
        prompt="nothing to do",
        check='try { set ok=(##class(Pilot.Trivial).Two()=2) } catch { set ok=0 } write $select(ok:"PASS",1:"FAIL")',
        fixtures=(
            Document(
                name="Pilot.Trivial",
                content=(
                    "Class Pilot.Trivial Extends %RegisteredObject\n{\n"
                    "ClassMethod Two() As %Integer\n{\n    Quit 2\n}\n}\n"
                ),
            ),
        ),
        solution=(
            Document(
                name="Pilot.Trivial",
                content=(
                    "Class Pilot.Trivial Extends %RegisteredObject\n{\n"
                    "ClassMethod Two() As %Integer\n{\n    Quit 2\n}\n}\n"
                ),
            ),
        ),
    )
    with pytest.raises(CorpusInvalid) as excinfo:
        validate_live(already_solved)
    assert "FR-004" in str(excinfo.value)


def test_a_reference_that_does_not_pass_its_own_check_is_rejected():
    """The FR-022 rejection. This is the shape of the four floors: a check nothing can satisfy."""
    unsatisfiable = GradedTask(
        id="PILOT-DEMO-BROKEN",
        prompt="make Three() return 3",
        check='try { set ok=(##class(Pilot.Broken).Three()=3) } catch { set ok=0 } write $select(ok:"PASS",1:"FAIL")',
        fixtures=(
            Document(
                name="Pilot.Broken",
                content=(
                    "Class Pilot.Broken Extends %RegisteredObject\n{\n"
                    "ClassMethod Three() As %Integer\n{\n    Quit 0\n}\n}\n"
                ),
            ),
        ),
        # The reference returns 4, so no agent could ever satisfy the check by copying it.
        solution=(
            Document(
                name="Pilot.Broken",
                content=(
                    "Class Pilot.Broken Extends %RegisteredObject\n{\n"
                    "ClassMethod Three() As %Integer\n{\n    Quit 4\n}\n}\n"
                ),
            ),
        ),
    )
    with pytest.raises(CorpusInvalid) as excinfo:
        validate_live(unsatisfiable)
    assert "FR-022" in str(excinfo.value)


def test_the_same_state_gives_the_same_verdict_twice():
    """Determinism, measured rather than argued: one state, two runs of the check, one answer."""
    task = pilot_tasks()[0]
    reset_documents([doc.name for doc in task.fixtures], task.namespace)
    apply_documents(task.fixtures, task.namespace)
    assert run_check(task) is False
    assert run_check(task) is False
    apply_documents(task.solution, task.namespace)
    assert run_check(task) is True
    assert run_check(task) is True


def test_the_reset_really_puts_the_fixture_back():
    """The pairing depends on it. If arm two started from arm one's answer, its pass rate would be
    the first arm's work reported as the second arm's."""
    task = pilot_tasks()[0]
    apply_documents(task.solution, task.namespace)
    assert run_check(task) is True
    reset_documents([doc.name for doc in task.fixtures], task.namespace)
    apply_documents(task.fixtures, task.namespace)
    assert run_check(task) is False


def test_a_session_leftover_is_deleted():
    """130 FR-023, the way `pilot.run_one` does it. A class the fixture never named appears between
    the two snapshots, as `Bench.Q2.CountOther` did, and the difference deletes it and nothing else.
    """
    fixture = (Document(name="Bench.Q2", content="Class Bench.Q2\n{\n}\n"),)
    stray = Document(
        name="Bench.Q2.Leftover130",
        content="Class Bench.Q2.Leftover130 Extends %RegisteredObject\n{\n}\n",
    )
    prefixes = package_prefixes(fixture)
    reset_documents([stray.name], BENCHMARK_NAMESPACE)
    before = list_classes(prefixes, BENCHMARK_NAMESPACE)
    assert stray.name not in before
    apply_documents((stray,), BENCHMARK_NAMESPACE)
    after = list_classes(prefixes, BENCHMARK_NAMESPACE)
    assert created_classes(before, after) == [stray.name]
    reset_documents(created_classes(before, after), BENCHMARK_NAMESPACE)
    assert list_classes(prefixes, BENCHMARK_NAMESPACE) == before


# --- the AI Hub tasks, on build 139 — 132 T040 -------------------------------------------------------

# What a teardown must leave behind: nothing. `write` prints one line per leftover, so an empty answer
# is a clean instance. Classes go through `list_classes`, since `exec` may not touch code storage.
AI_HUB_LEFTOVERS = (
    'for n="AI.LLM.IadAihub139Q23","AI.LLM.IadAihub139Q25" { set c="" '
    'if $$$ISOK(##class(%ConfigStore.Configuration).Get(n,.c)) write "config ",n,! } '
    'if ##class(%Wallet.Collection).Exists("IadAihub139") write "wallet IadAihub139",! '
    'new $namespace set $namespace="%SYS" '
    'if ##class(Security.Applications).Exists("/mcp/iadaihub139") write "webapp /mcp/iadaihub139",!'
)


@pytest.fixture
def ai_hub_connection():
    """139, not iris-dev-iris. Explicit host and port, because the repo's `.iris-agentic-dev.toml`
    pins iris-dev-iris and only an explicit IRIS_HOST outranks it."""
    if not _running(AI_HUB_CONTAINER):
        pytest.skip(f"{AI_HUB_CONTAINER} is not running")
    keys = ("IRIS_HOST", "IRIS_WEB_PORT", "IRIS_CONTAINER", "IRIS_NAMESPACE")
    previous = {key: os.environ.get(key) for key in keys}
    os.environ.update(
        {
            "IRIS_HOST": "localhost",
            "IRIS_WEB_PORT": AI_HUB_WEB_PORT,
            "IRIS_CONTAINER": AI_HUB_CONTAINER,
            "IRIS_NAMESPACE": "USER",
        }
    )
    yield
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _ai_hub_leftovers(task: GradedTask) -> list[str]:
    from tests.e2e.skill_eval.graded_task import _iad

    classes = [
        f"class {name}"
        for name in sorted(list_classes(("IadAihub139",), task.namespace))
    ]
    return classes + [
        line.strip()
        for line in _iad(["exec", AI_HUB_LEFTOVERS], task.namespace).splitlines()
        if line.strip()
    ]


@pytest.mark.parametrize(
    "task",
    [task for task in all_tasks() if task.skill == AI_HUB_SKILL],
    ids=lambda task: task.id,
)
def test_every_ai_hub_task_is_false_before_true_after_and_cleans_up(
    task, ai_hub_connection
):
    """FR-004 and FR-022 on 139, twice, and then the teardown and class reset leave no `IadAihub139`
    state. Leftover ConfigStore, Wallet or web app state would pass SKILL-23 or SKILL-24 for the next
    arm before its agent ran."""
    try:
        validate_live(task)
        validate_live(task)
    finally:
        run_teardown(task)
        names = {doc.name for doc in task.fixtures + task.solution}
        reset_documents(sorted(names), task.namespace)
    assert _ai_hub_leftovers(task) == []
