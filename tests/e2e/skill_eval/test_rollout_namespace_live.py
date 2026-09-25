"""Two concurrent rollouts cannot see each other's documents — 120 T020, against live IRIS.

The Phase 5 gate. Everything in `test_rollout_namespace.py` is name derivation and lease
bookkeeping; this file is the part only IRIS can answer: two rollouts write a class of the *same
name* at the same time, with different bodies, and each one reads back its own.

**No model tokens.** Every call is `iris-agentic-dev` against `iris-dev-iris`. It does need the
container: it creates two `IADB…` namespaces, reuses them the way a real run does, and deletes both
at the end. `drop` is what the tests use, because reuse by index is what a run does and one test
asserts the clear that makes reuse safe — see `rollout_namespace.py` § decisions 3 and 4 for what
`iris_namespace_create` does not do on its own.

Concurrency is two threads, not two processes, deliberately: the thing under test is IRIS-side
isolation, and each thread's CLI call is its own process anyway. Two `RolloutNamespaces` instances,
because in a real run the two rollouts are two workers, and one must not vouch for the other's
namespace.
"""

from __future__ import annotations

import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.e2e.skill_eval.graded_task import (
    BENCHMARK_NAMESPACE,
    Document,
    _iad,
    apply_documents,
)
from tests.e2e.skill_eval.rollout_namespace import (
    NamespaceNotOurs,
    Rollout,
    RolloutNamespaces,
    delete_namespace,
    existing_namespaces,
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
        reason="iris-dev-iris is not running, and IRIS is the only thing that can answer isolation",
    ),
]

CLASS_NAME = "Rollout.Marker"


def body(marker: str) -> str:
    """One class name, two bodies. If the namespaces are not isolated, one of these overwrites the
    other and both rollouts read the same marker back. Built by concatenation rather than `format`
    or an f-string, because the ObjectScript braces would have to be escaped in either.
    """
    return (
        "Class " + CLASS_NAME + " Extends %RegisteredObject\n"
        "{\n"
        "ClassMethod Marker() As %String\n"
        "{\n"
        '    Quit "' + marker + '"\n'
        "}\n"
        "}\n"
    )


def check(marker: str) -> str:
    """`PASS` only if this namespace's class returns this rollout's marker. A missing class and
    another rollout's marker are both `FAIL`, and the failure text says which."""
    return (
        'set m="" try { set m=##class(' + CLASS_NAME + ").Marker() } catch { } "
        'write $select(m="' + marker + '":"PASS",m="":"FAIL:absent",1:"FAIL:"_m)'
    )


@pytest.fixture(scope="module", autouse=True)
def iris_connection():
    """The connection the CLI reads, set explicitly so a stray `IRIS_NAMESPACE` in the shell cannot
    point a rollout at someone's working namespace — which is the exact failure under test.
    """
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


ROLLOUTS = (Rollout("PILOT-CONC", 0), Rollout("PILOT-CONC", 1))


@pytest.fixture(scope="module", autouse=True)
def no_namespaces_left_behind(iris_connection):
    """The tests use `drop`, because reuse by index is what a real run does and one of them asserts
    the clear that makes reuse safe. This puts the container back where it started afterwards.
    """
    yield
    for rollout in ROLLOUTS:
        delete_namespace(rollout.namespace)


def _seed_and_read(rollout: Rollout, marker: str, barrier=None) -> str:
    """One rollout, end to end: lease the namespace, write the class, read it back, drop.

    The barrier is what makes the concurrent version discriminating. Without it the two rollouts can
    each finish their write-then-read before the other starts, and a single shared namespace would
    pass twice. Both write, both wait, then both read — so if one namespace were backing both, the
    second write is already on top of the first when either one reads. Checked by running exactly
    that: one namespace, two markers, and the verdicts come back `['PASS', 'FAIL:ROLLOUT-ZERO']`.

    The barrier timeout is short because it is a failure path, not a wait: if the sibling thread
    died before reaching it, the barrier is the only thing left holding this one up.
    """
    manager = RolloutNamespaces()
    namespace = manager.create(rollout)
    try:
        manager.assert_ours(namespace)
        apply_documents([Document(name=CLASS_NAME, content=body(marker))], namespace)
        if barrier is not None:
            barrier.wait(timeout=30)
        return _iad(["exec", check(marker)], namespace).strip()
    finally:
        manager.drop(rollout, [CLASS_NAME])


def test_two_concurrent_rollouts_each_read_their_own_document():
    """The gate. One class name, two bodies, two namespaces, both written before either is read."""
    markers = ("ROLLOUT-ZERO", "ROLLOUT-ONE")
    barrier = threading.Barrier(len(ROLLOUTS))
    with ThreadPoolExecutor(max_workers=len(ROLLOUTS)) as pool:
        results = list(
            pool.map(_seed_and_read, ROLLOUTS, markers, [barrier] * len(ROLLOUTS))
        )
    for verdict in results:
        assert "PASS" in verdict, results
        assert "FAIL" not in verdict, results


def test_the_namespaces_are_two_namespaces_on_the_server():
    """Named, so a leftover is traceable, and distinct — the derivation's whole claim, read back
    from `iris_namespace_list` rather than from the function that generated them."""
    first, second = ROLLOUTS
    manager = RolloutNamespaces()
    manager.create(first)
    manager.create(second)
    try:
        live = existing_namespaces()
        assert first.namespace.upper() in live
        assert second.namespace.upper() in live
        assert first.namespace != second.namespace
    finally:
        manager.drop(first, [CLASS_NAME])
        manager.drop(second, [CLASS_NAME])


def test_a_rollout_refuses_to_grade_in_the_other_rollouts_namespace():
    """Live counterpart of the unit refusal: the namespace exists and is reachable, and the answer
    is still no. Reachability is what makes the shared-namespace mistake so easy."""
    first, second = ROLLOUTS
    mine = RolloutNamespaces()
    mine.create(first)
    theirs = RolloutNamespaces()
    theirs.create(second)
    try:
        assert second.namespace.upper() in existing_namespaces()
        with pytest.raises(NamespaceNotOurs):
            mine.assert_ours(second.namespace)
        with pytest.raises(NamespaceNotOurs):
            mine.assert_ours(BENCHMARK_NAMESPACE)
    finally:
        mine.drop(first, [CLASS_NAME])
        theirs.drop(second, [CLASS_NAME])


def test_a_reused_namespace_starts_without_the_last_rollouts_class():
    """Reuse is the consequence of having no namespace-delete tool, so the clear on drop is what
    keeps it honest: the second lease of one rollout index must not read the first one's answer.
    """
    rollout = ROLLOUTS[0]
    assert "PASS" in _seed_and_read(rollout, "FIRST-PASS")

    manager = RolloutNamespaces()
    namespace = manager.create(rollout)
    try:
        verdict = _iad(["exec", check("FIRST-PASS")], namespace).strip()
        assert (
            "PASS" not in verdict
        ), f"{namespace} still holds the previous rollout's class: {verdict!r}"
    finally:
        manager.drop(rollout, [CLASS_NAME])
