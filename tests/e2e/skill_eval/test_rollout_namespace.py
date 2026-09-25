"""Unit tests for the rollout namespace — 120 T019, written before `rollout_namespace.py`.

Decision 1 in spec 120 closed on shared IRIS over Atelier REST, and named one part of it
unproven: namespace-per-rollout. The pilot ran serial in one `BENCHMARK` namespace, so nothing
asserts that two rollouts cannot see each other's classes. Spec 121's Constitution Check already
claims per-task namespace creation and refusal — its open finding C4 — and this is where the
primitive lands, because the concurrency it exists for lives here.

Three properties, and they are different failures:

1. **The name is derived, not chosen.** Two rollouts that pick the same name are one rollout with
   twice the writes, and the symptom is a task that grades correctly in one arm and mysteriously
   passes in another. Derivation from `(task_id, index)` makes the collision impossible rather
   than unlikely.
2. **Grading refuses a namespace this process did not create.** A rollout that grades in the
   shared `BENCHMARK` namespace reads whatever the last serial run left there. That reads as a
   pass, not as an error, which is why it has to be a refusal and not a warning.

3. **A create is believed only when `iris_namespace_list` confirms it.** Added after T020's live
   run: `iris_namespace_create` reports `created: true` for a namespace the running instance does
   not have, so the create's own verdict proves nothing. See `rollout_namespace.py` § decision 3.

The live half is T020: real IRIS, two concurrent rollouts, neither seeing the other's documents.
Everything here is name derivation and lease bookkeeping, so it takes the IRIS calls as
callables — the same shape `export_task(validate=...)` uses in `benchmark/harbor`.
"""

from __future__ import annotations

import pytest

from tests.e2e.skill_eval.graded_task import BENCHMARK_NAMESPACE
from tests.e2e.skill_eval.rollout_namespace import (
    MAX_NAMESPACE_LENGTH,
    NAMESPACE_PREFIX,
    NamespaceCreateFailed,
    NamespaceInUse,
    NamespaceNotOurs,
    Rollout,
    RolloutNamespaces,
    create_namespace,
    delete_namespace,
    namespace_for,
)


class Recorder:
    """Stands in for the two IRIS calls, and records what it was asked to do.

    Not a mocked IRIS: nothing here asserts anything about IRIS behaviour. The assertions are
    about which name was passed and in what order, and T020's live test is what proves the calls
    themselves work against `iris-dev-iris`.
    """

    def __init__(self):
        self.created: list[str] = []
        self.cleared: list[tuple[str, tuple[str, ...]]] = []

    def create(self, namespace: str) -> None:
        self.created.append(namespace)

    def clear(self, namespace: str, names) -> None:
        self.cleared.append((namespace, tuple(names)))


def a_manager():
    recorder = Recorder()
    return RolloutNamespaces(create=recorder.create, clear=recorder.clear), recorder


# --- the name ------------------------------------------------------------------------------------


def test_the_same_rollout_always_gets_the_same_name():
    """Derived, so the grade step and the seed step do not need to pass a name to each other."""
    assert namespace_for("PILOT-01", 0) == namespace_for("PILOT-01", 0)


def test_two_rollouts_of_one_task_get_different_namespaces():
    names = {namespace_for("PILOT-01", index) for index in range(8)}
    assert len(names) == 8


def test_two_tasks_at_the_same_rollout_index_get_different_namespaces():
    assert namespace_for("PILOT-01", 3) != namespace_for("PILOT-02", 3)


def test_task_ids_that_flatten_to_the_same_label_still_differ():
    """`PILOT-01` and `PILOT_01` both flatten to `PILOT01`, and a name built from the flattened
    label alone would hand them one namespace. The digest is over the id as written."""
    assert namespace_for("PILOT-01", 1) != namespace_for("PILOT_01", 1)
    assert namespace_for("PILOT-01", 1) != namespace_for("PILOT-0-1", 1)


def test_the_name_says_which_task_and_which_rollout_it_belongs_to():
    """A leftover namespace has to name its owner. Rollout namespaces are kept between runs and
    reused by index, so someone will find these on a server and needs to know what made them."""
    name = namespace_for("PILOT-04", 2)
    assert "PILOT04" in name
    assert "R2" in name


def test_the_name_is_something_iris_will_accept():
    """Conservative on purpose — uppercase, alphanumeric and underscore, starting with a letter.
    T020 is what proves the real server takes it; this only keeps the generator honest.
    """
    for task_id, index in (("PILOT-01", 0), ("a-very-long-task-identifier-01", 199)):
        name = namespace_for(task_id, index)
        assert name[0].isalpha()
        assert name == name.upper()
        assert all(c.isalnum() or c == "_" for c in name), name
        assert len(name) <= MAX_NAMESPACE_LENGTH, name


def test_a_long_task_id_is_truncated_and_still_unique():
    long_a = "benchmark-task-with-a-very-long-name-alpha"
    long_b = "benchmark-task-with-a-very-long-name-beta"
    assert namespace_for(long_a, 1) != namespace_for(long_b, 1)
    assert len(namespace_for(long_a, 1)) <= MAX_NAMESPACE_LENGTH


def test_a_rollout_index_must_be_a_non_negative_integer():
    with pytest.raises(ValueError):
        Rollout(task_id="PILOT-01", index=-1)


def test_a_rollout_carries_its_own_namespace():
    rollout = Rollout(task_id="PILOT-01", index=2)
    assert rollout.namespace == namespace_for("PILOT-01", 2)


# --- the lease -----------------------------------------------------------------------------------


def test_creating_a_rollout_namespace_creates_it_in_iris_and_returns_the_name():
    manager, recorder = a_manager()
    name = manager.create(Rollout("PILOT-01", 0))
    assert name == namespace_for("PILOT-01", 0)
    assert recorder.created == [name]
    assert manager.active == (name,)


def test_grading_in_a_namespace_this_process_created_is_allowed():
    manager, _ = a_manager()
    name = manager.create(Rollout("PILOT-01", 0))
    manager.assert_ours(name)  # does not raise


def test_grading_in_a_namespace_this_process_did_not_create_refuses():
    """The failure this exists for: a rollout grading somewhere another run owns reads that run's
    documents and reports a pass."""
    manager, _ = a_manager()
    manager.create(Rollout("PILOT-01", 0))
    with pytest.raises(NamespaceNotOurs) as raised:
        manager.assert_ours(namespace_for("PILOT-02", 0))
    assert namespace_for("PILOT-02", 0) in str(raised.value)


def test_grading_in_the_shared_benchmark_namespace_refuses():
    """`BENCHMARK` is where the serial pilot ran, so it holds the last run's answers. Under
    concurrency it is the one namespace guaranteed to be wrong, and it is also the value someone
    will reach for out of habit."""
    manager, _ = a_manager()
    manager.create(Rollout("PILOT-01", 0))
    with pytest.raises(NamespaceNotOurs) as raised:
        manager.assert_ours(BENCHMARK_NAMESPACE)
    assert BENCHMARK_NAMESPACE in str(raised.value)


def test_two_rollouts_hold_two_leases_at_once():
    manager, recorder = a_manager()
    first = manager.create(Rollout("PILOT-01", 0))
    second = manager.create(Rollout("PILOT-01", 1))
    assert first != second
    assert manager.active == tuple(sorted((first, second)))
    assert recorder.created == [first, second]


def test_leasing_the_same_rollout_twice_refuses():
    """A second lease on one rollout is two writers in one namespace, which is the exact state
    the derivation exists to prevent. Better to fail here than to interleave."""
    manager, _ = a_manager()
    manager.create(Rollout("PILOT-01", 0))
    with pytest.raises(NamespaceInUse) as raised:
        manager.create(Rollout("PILOT-01", 0))
    assert "PILOT-01" in str(raised.value)


def test_resetting_clears_the_named_documents_in_that_rollouts_namespace():
    manager, recorder = a_manager()
    rollout = Rollout("PILOT-01", 0)
    name = manager.create(rollout)
    manager.reset(rollout, ["Bench.One", "Bench.Two"])
    assert recorder.cleared == [(name, ("Bench.One", "Bench.Two"))]


def test_resetting_a_rollout_nobody_leased_refuses():
    manager, recorder = a_manager()
    with pytest.raises(NamespaceNotOurs):
        manager.reset(Rollout("PILOT-01", 0), ["Bench.One"])
    assert recorder.cleared == []


def test_dropping_releases_the_lease_and_clears_what_the_rollout_wrote():
    """There is no namespace-delete tool in the surface, so `drop` clears the documents and
    releases the lease. The empty namespace stays behind, and the next rollout with that index
    reuses it — which is why the clear is not optional."""
    manager, recorder = a_manager()
    rollout = Rollout("PILOT-01", 0)
    name = manager.create(rollout)
    manager.drop(rollout, ["Bench.One"])
    assert recorder.cleared == [(name, ("Bench.One",))]
    assert manager.active == ()


def test_grading_after_the_drop_refuses():
    manager, _ = a_manager()
    rollout = Rollout("PILOT-01", 0)
    name = manager.create(rollout)
    manager.drop(rollout, [])
    with pytest.raises(NamespaceNotOurs):
        manager.assert_ours(name)


def test_dropping_twice_is_not_an_error():
    """Teardown runs in a `finally`, and a rollout that failed before its create still gets one."""
    manager, _ = a_manager()
    rollout = Rollout("PILOT-01", 0)
    manager.create(rollout)
    manager.drop(rollout, [])
    manager.drop(rollout, [])
    assert manager.active == ()


def test_the_lease_set_is_per_manager_not_global():
    """Two managers are two processes, and one must not vouch for the other's namespace."""
    first, _ = a_manager()
    second, _ = a_manager()
    name = first.create(Rollout("PILOT-01", 0))
    with pytest.raises(NamespaceNotOurs):
        second.assert_ours(name)


# --- creating one for real: the three steps the tool surface does not do ---------------------------
#
# The live run of T020 found `iris_namespace_create` cannot create a usable namespace by itself, in
# two separate ways, and neither of them reports a failure the caller can see:
#
# 1. It requires the database to exist already (`ERROR #420: Database X does not exist`), and no
#    tool in the surface creates a database.
# 2. `Config.Namespaces.CreateOne` edits the CPF, so the namespace exists on disk and not in the
#    running instance. `iris_namespace_create` returns `created: true` anyway, and the next thing
#    to touch the namespace gets `<NAMESPACE>`.
#
# So `create_namespace` does four things in a fixed order, and the last one is the point: the
# authority on whether a namespace exists is `iris_namespace_list`, never the create's own verdict.


class Steps:
    """Records the four steps of a create, in order."""

    def __init__(self, *, live_after: bool = True):
        self.calls: list[tuple[str, str]] = []
        self._live_after = live_after

    def live(self):
        made = [name for step, name in self.calls if step == "create"]
        return tuple(made) if self._live_after else ()

    def _step(self, label):
        def record(namespace: str) -> None:
            self.calls.append((label, namespace))

        return record

    def kwargs(self):
        return {
            "ensure_database": self._step("database"),
            "create": self._step("create"),
            "activate": self._step("activate"),
            "live": self.live,
        }


def test_creating_a_namespace_makes_the_database_first_then_activates_it():
    """Order is the whole content of this function: the database has to exist before the CPF edit,
    and the CPF edit has to be activated before anything can use the namespace."""
    steps = Steps()
    name = namespace_for("PILOT-01", 0)
    create_namespace(name, **steps.kwargs())
    assert [step for step, _ in steps.calls] == ["database", "create", "activate"]
    assert {n for _, n in steps.calls} == {name}


def test_creating_a_namespace_that_is_already_there_does_nothing():
    """Rollout namespaces are reused by index, so the second run of a task must not re-edit the CPF."""
    name = namespace_for("PILOT-01", 0)
    steps = Steps()
    steps.calls.append(("create", name))  # as if a previous run had made it
    create_namespace(name, **steps.kwargs())
    assert [step for step, _ in steps.calls] == ["create"]


def test_a_namespace_that_does_not_appear_in_the_list_afterwards_is_a_failure():
    """The lying success, caught. `iris_namespace_create` reported `created: true` for a namespace
    that `iris_namespace_list` did not have and `$namespace=` could not enter, and a rollout that
    trusts the report grades in a namespace that is not there."""
    steps = Steps(live_after=False)
    with pytest.raises(NamespaceCreateFailed) as raised:
        create_namespace(namespace_for("PILOT-01", 0), **steps.kwargs())
    assert namespace_for("PILOT-01", 0) in str(raised.value)
    assert "iris_namespace_list" in str(raised.value)


# --- deleting one: possible, but only through `iris_execute` ---------------------------------------


class Script:
    """Captures the ObjectScript a delete would run, instead of running it."""

    def __init__(self):
        self.ran: list[str] = []

    def __call__(self, code: str) -> str:
        self.ran.append(code)
        return "DELETED"


def test_deleting_a_namespace_names_it_the_database_and_the_directory():
    """Three objects, not one: the namespace in the CPF, the database that backs it, and the
    directory holding `IRIS.DAT`. Leaving any of them behind means the next create of that name
    finds a half-existing namespace."""
    script = Script()
    name = namespace_for("PILOT-01", 0)
    delete_namespace(name, run=script)
    assert len(script.ran) == 1
    code = script.ran[0]
    assert name in code
    assert "Config.Namespaces" in code
    assert "Config.Databases" in code
    assert "SYS.Database" in code
    assert "RemoveDirectoryTree" in code


@pytest.mark.parametrize(
    "namespace", ["%SYS", "USER", BENCHMARK_NAMESPACE, "", NAMESPACE_PREFIX]
)
def test_deleting_anything_that_is_not_a_rollout_namespace_refuses(namespace):
    """The one guard that matters here. This code path deletes a database and its directory, so a
    name it did not derive is never worth attempting — including the bare prefix."""
    script = Script()
    with pytest.raises(NamespaceNotOurs):
        delete_namespace(namespace, run=script)
    assert script.ran == []


def test_purging_a_rollout_clears_it_deletes_it_and_releases_the_lease():
    """Housekeeping for a shared container: `drop` keeps the namespace for the next run of that
    index, `purge` takes it away. The clear still runs first, so a purge that fails at the delete
    leaves a namespace with no documents rather than one holding the last answers."""
    recorder = Recorder()
    deleted: list[str] = []
    manager = RolloutNamespaces(
        create=recorder.create, clear=recorder.clear, delete=deleted.append
    )
    rollout = Rollout("PILOT-01", 0)
    name = manager.create(rollout)
    manager.purge(rollout, ["Bench.One"])
    assert recorder.cleared == [(name, ("Bench.One",))]
    assert deleted == [name]
    assert manager.active == ()


def test_purging_a_rollout_nobody_leased_deletes_nothing():
    recorder = Recorder()
    deleted: list[str] = []
    manager = RolloutNamespaces(
        create=recorder.create, clear=recorder.clear, delete=deleted.append
    )
    manager.purge(Rollout("PILOT-01", 0), ["Bench.One"])
    assert deleted == []
    assert recorder.cleared == []
