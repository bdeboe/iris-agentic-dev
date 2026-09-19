"""One namespace per rollout — 120 T020, the unproven half of Decision 1.

The pilot ran serial in one `BENCHMARK` namespace and reset the fixtures between tasks. That is
correct for one worker and silently wrong for two: the second rollout's `doc put` lands on top of
the first one's, and the check that reads the class afterwards cannot tell whose answer it is
grading. It does not error — it passes, or fails, for the wrong reason.

Four decisions, and the last two are limitations of the tool surface rather than preferences:

1. **The name is derived from `(task_id, index)`, not assigned.** A registry that hands out names
   has to be consulted, and anything that has to be consulted can be skipped. `namespace_for` is a
   pure function, so the seed step and the grade step arrive at the same namespace without talking
   to each other, and two different rollouts cannot arrive at one name. The digest is taken over
   the task id as written, because `PILOT-01` and `PILOT_01` flatten to the same legible label.
2. **Grading refuses a namespace this manager did not create.** Spec 121's Constitution Check
   claims this refusal and no task implemented it (its finding C4). `BENCHMARK` gets a message of
   its own: it is where the serial pilot ran, so it holds the last run's answers, and it is the
   value a call site reaches for out of habit.
3. **`iris_namespace_create` cannot create a usable namespace on its own, and does not say so.**
   T020's live run found two separate failures, neither of them visible to a caller who trusts the
   result:

   - It requires the database to exist already — `ERROR #420: Database IADB… does not exist` — and
     no tool in the 81-tool surface creates a database. `iris_database_list` and
     `iris_database_stats` read; nothing writes.
   - `Config.Namespaces.CreateOne` edits the CPF, which leaves the namespace on disk and absent
     from the running instance. The tool returns `{"created": true}` regardless, and the next call
     to touch the namespace gets `<NAMESPACE>` while `iris_namespace_list` never lists it.

   So `create_namespace` makes the database, creates the namespace, activates it, and then asks
   `iris_namespace_list` whether it is really there. The list is the authority; the create's own
   verdict is not. The database work and the activation both go through `iris_execute`, because
   there is no tool for either. Three tools worth adding: `iris_database_create`,
   `iris_namespace_delete`, and a `iris_namespace_create` that activates what it created.

4. **`drop` keeps the namespace for the next run of that index; `purge` takes it away.** A rollout
   namespace can be deleted — namespace, database, directory, all three through `iris_execute` —
   so `delete_namespace` exists and refuses any name it did not derive. The run loop still uses
   `drop`, because reuse by index costs one `iris_namespace_list` call where a create costs four
   round trips and a CPF edit, and the clear on drop is what makes reuse safe. `purge` is for
   housekeeping on a shared container, and for tests that should not leave a namespace behind.

`iris_namespace_create` is destructive-gated (`write_gate.rs`), so the live path exports
`IRIS_DESTRUCTIVE_TOOLS_ENABLED=1` for its own subprocess only. Creating a scratch namespace on
the benchmark container is exactly the gate's intended use — approved by the caller, per call —
and nothing here sets it in the ambient environment.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

from tests.e2e.skill_eval.graded_task import (
    BENCHMARK_NAMESPACE,
    CheckBroken,
    reset_documents,
)

#: Prefix for every rollout namespace, so `iris_namespace_list` groups them and a leftover one is
#: recognisable as this harness's rather than someone's real work.
NAMESPACE_PREFIX = "IADB"

#: Conservative: IRIS accepts longer, but nothing is gained by finding the limit. T020's live test
#: is what proves the server takes what this generates.
MAX_NAMESPACE_LENGTH = 30

#: Hex characters of `(task_id, index)` digest carried in the name. Six is 16.7M, against a corpus
#: heading for 50 tasks and single-digit rollouts.
DIGEST_LENGTH = 6


class NamespaceNotOurs(RuntimeError):
    """A rollout was asked to work in a namespace this manager did not create."""


class NamespaceInUse(RuntimeError):
    """A second lease was taken on one rollout, which is two writers in one namespace."""


class NamespaceCreateFailed(RuntimeError):
    """The create reported success and `iris_namespace_list` does not have the namespace."""


def _label(task_id: str) -> str:
    """The legible part: uppercase alphanumerics of the task id, so a name says who owns it."""
    return "".join(c for c in task_id.upper() if c.isalnum())


def namespace_for(task_id: str, index: int) -> str:
    """The namespace for one rollout of one task. Pure, so every step derives it independently."""
    digest = hashlib.sha256(f"{task_id}\x00{index}".encode()).hexdigest()[
        :DIGEST_LENGTH
    ]
    suffix = f"_R{index}_{digest.upper()}"
    room = MAX_NAMESPACE_LENGTH - len(NAMESPACE_PREFIX) - len(suffix)
    return f"{NAMESPACE_PREFIX}{_label(task_id)[:room]}{suffix}"


@dataclass(frozen=True)
class Rollout:
    """One attempt at one task. `index` distinguishes the repeats of a task inside a run."""

    task_id: str
    index: int

    def __post_init__(self) -> None:
        if not isinstance(self.index, int) or isinstance(self.index, bool):
            raise ValueError(f"rollout index must be an int, not {self.index!r}")
        if self.index < 0:
            raise ValueError(
                f"rollout index must be non-negative, not {self.index}. A negative index reads as "
                "a sentinel, and a sentinel in a namespace name is a namespace nobody owns"
            )
        if not self.task_id:
            raise ValueError("a rollout with no task id has no namespace to derive")

    @property
    def namespace(self) -> str:
        return namespace_for(self.task_id, self.index)


def _database_directory(namespace: str) -> str:
    """`<mgr>/<namespace lowercased>/`, derived in ObjectScript so nothing has to know the path."""
    return f'$system.Util.ManagerDirectory()_"{namespace.lower()}/"'


def ensure_database(namespace: str, *, run=None) -> None:
    """Make the database the namespace needs — directory, `IRIS.DAT`, and the CPF entry naming it.

    Through `iris_execute` because there is no `iris_database_create` tool. Every step is
    conditional, so a namespace being reused by index costs one round trip and changes nothing.
    """
    run = run or _exec
    code = (
        f'set ns="{namespace}" set dir={_database_directory(namespace)} '
        "if '##class(%Library.File).DirectoryExists(dir) { "
        "do ##class(%Library.File).CreateDirectoryChain(dir) } "
        "if '##class(SYS.Database).%ExistsId(dir) { "
        "set sc=##class(SYS.Database).CreateDatabase(dir) "
        'if $$$ISERR(sc) { write "ERROR:"_$system.Status.GetErrorText(sc),! quit } } '
        'if \'##class(Config.Databases).Exists(ns) { set p("Directory")=dir '
        "set sc=##class(Config.Databases).Create(ns,.p) "
        'if $$$ISERR(sc) { write "ERROR:"_$system.Status.GetErrorText(sc),! quit } } '
        'write "READY",!'
    )
    out = run(code)
    if "READY" not in out:
        raise NamespaceCreateFailed(
            f"could not make the database for {namespace}: {out.strip()[:300]}"
        )


def activate_namespace(namespace: str, *, run=None) -> None:
    """Load the CPF's new namespace into the running instance.

    The status is deliberately not checked. `Config.Namespaces.Activate` raises `<INVALID OREF>`
    from its own `%OnAfterActivateCallback` on this build while the activation itself takes effect,
    so reading the status would refuse a namespace that is now usable. `existing_namespaces` is
    what decides, right after this — see `create_namespace`.
    """
    run = run or _exec
    run(f'do ##class(Config.Namespaces).Activate("{namespace}") write "ACTIVATED",!')


def create_namespace(
    namespace: str,
    *,
    ensure_database=ensure_database,
    create=None,
    activate=activate_namespace,
    live=None,
) -> None:
    """Create the namespace in IRIS, or leave it alone if it is already there.

    Four steps, in this order, and the last one is the point. `iris_namespace_create` reports
    `created: true` for a namespace the running instance does not have, so the create's own verdict
    proves nothing and `iris_namespace_list` is the authority. Checking existence first is for the
    same reason in reverse: `CREATE_FAILED` covers a name clash and a broken CPF edit alike, and
    treating both as "fine, it exists" is how a rollout ends up grading in a namespace nobody made.
    """
    create = create or _create_in_cpf
    live = live or existing_namespaces
    if namespace in live():
        return
    ensure_database(namespace)
    create(namespace)
    activate(namespace)
    if namespace not in live():
        raise NamespaceCreateFailed(
            f"{namespace} was created and iris_namespace_list does not have it. The CPF edit "
            "landed and the running instance did not, so anything grading there would get "
            "<NAMESPACE> — or worse, grade somewhere else"
        )


def _create_in_cpf(namespace: str) -> None:
    _destructive_tool(
        "iris_namespace_create", {"name": namespace, "db_path": namespace}
    )


def delete_namespace(namespace: str, *, run=None) -> None:
    """Delete a rollout namespace: the namespace, the database behind it, and its directory.

    All three, because a half-deleted name is worse than a kept one — the next create of that name
    finds the database already there and the namespace not, which is the state that produced
    `ERROR #420` in the first place. Through `iris_execute` because there is no
    `iris_namespace_delete` tool.

    Refuses any name this module did not derive. This path removes a database file, so the guard is
    not a nicety: `%SYS`, `USER` and `BENCHMARK` must be unreachable from here by construction.
    """
    run = run or _exec
    if not namespace.startswith(NAMESPACE_PREFIX) or namespace == NAMESPACE_PREFIX:
        raise NamespaceNotOurs(
            f"refusing to delete {namespace!r}: only namespaces this harness derived start with "
            f"{NAMESPACE_PREFIX} and carry a rollout suffix, and this call deletes a database"
        )
    code = (
        f'set ns="{namespace}" set dir={_database_directory(namespace)} '
        "do ##class(Config.Namespaces).Delete(ns) "
        "do ##class(Config.Databases).Delete(ns) "
        "do ##class(SYS.Database).DeleteDatabase(dir) "
        "do ##class(%Library.File).RemoveDirectoryTree(dir) "
        'write "DELETED",!'
    )
    run(code)


def existing_namespaces() -> tuple[str, ...]:
    payload = _tool("iris_namespace_list", {})
    namespaces = (payload.get("result") or payload).get("namespaces") or []
    return tuple(str(name).upper() for name in namespaces)


def clear_documents(namespace: str, names) -> None:
    """Delete the named classes from `namespace`. Reused namespaces start from the fixture."""
    reset_documents(names, namespace)


class RolloutNamespaces:
    """The leases this process holds. One per rollout, and nothing grades outside them.

    The set is per instance, not global: two managers are two processes, and one vouching for the
    other's namespace is the concurrency bug wearing the guard's clothes.
    """

    def __init__(
        self, *, create=create_namespace, clear=clear_documents, delete=delete_namespace
    ):
        self._create = create
        self._clear = clear
        self._delete = delete
        self._leased: dict[str, Rollout] = {}

    @property
    def active(self) -> tuple[str, ...]:
        return tuple(sorted(self._leased))

    def create(self, rollout: Rollout) -> str:
        namespace = rollout.namespace
        if namespace in self._leased:
            raise NamespaceInUse(
                f"{namespace} is already leased by rollout {rollout.task_id} #{rollout.index}. "
                "Two writers in one namespace is what the derivation exists to prevent, so this "
                "refuses rather than interleaving"
            )
        self._create(namespace)
        self._leased[namespace] = rollout
        return namespace

    def assert_ours(self, namespace: str) -> None:
        """Raise unless this manager created `namespace` and still holds it."""
        if namespace in self._leased:
            return
        if namespace.upper() == BENCHMARK_NAMESPACE.upper():
            raise NamespaceNotOurs(
                f"refusing to work in {BENCHMARK_NAMESPACE}: it is the shared namespace the serial "
                "pilot ran in, so it holds the last run's answers. A concurrent rollout grading "
                "there does not fail — it reports someone else's document as its own result"
            )
        raise NamespaceNotOurs(
            f"refusing to work in {namespace}: this run did not create it, and holds "
            f"{', '.join(self.active) or 'nothing'}"
        )

    def reset(self, rollout: Rollout, document_names) -> None:
        """Clear the rollout's classes so the next arm starts from the fixture, not the last answer."""
        self.assert_ours(rollout.namespace)
        self._clear(rollout.namespace, tuple(document_names))

    def drop(self, rollout: Rollout, document_names=()) -> None:
        """Release the lease and clear what the rollout wrote. Idempotent — teardown runs in a
        `finally`, and a rollout that failed before its create still gets one."""
        namespace = rollout.namespace
        if namespace not in self._leased:
            return
        self._clear(namespace, tuple(document_names))
        del self._leased[namespace]

    def purge(self, rollout: Rollout, document_names=()) -> None:
        """`drop`, and then take the namespace away too.

        Not what the run loop does — reuse by index is cheaper than a CPF edit per rollout. This is
        housekeeping on a shared container, and the teardown for tests that should leave nothing.
        The clear runs first, so a purge that fails at the delete leaves an empty namespace rather
        than one still holding the last rollout's answers.
        """
        namespace = rollout.namespace
        if namespace not in self._leased:
            return
        self.drop(rollout, document_names)
        self._delete(namespace)


# --- the CLI calls ------------------------------------------------------------------------------


def _binary() -> str:
    return os.environ.get("IAD_BINARY", "iris-agentic-dev")


def _tool(
    name: str, payload: dict, *, namespace: str = "%SYS", destructive=False
) -> dict:
    """One tool call through the CLI, in `%SYS` unless told otherwise.

    Separate from `graded_task._tool` for one reason: the gate. This is the only place in the
    harness that needs `IRIS_DESTRUCTIVE_TOOLS_ENABLED`, and it sets it on the child's environment
    for that call rather than on the process, so nothing else in the run inherits it.
    """
    import json
    import subprocess

    env = dict(os.environ)
    if destructive:
        env["IRIS_DESTRUCTIVE_TOOLS_ENABLED"] = "1"
    command = [_binary(), "tool", name, "-n", namespace, "-a", json.dumps(payload)]
    result = subprocess.run(
        command, capture_output=True, text=True, timeout=180, env=env
    )
    if result.returncode != 0:
        raise CheckBroken(
            f"`{name}` exited {result.returncode}: "
            f"{(result.stderr or result.stdout).strip()[:400]}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CheckBroken(
            f"{name} returned no JSON: {result.stdout.strip()[:300]}"
        ) from exc


def _destructive_tool(name: str, payload: dict) -> dict:
    return _tool(name, payload, destructive=True)


def _exec(code: str, *, namespace: str = "%SYS") -> str:
    """One `iris_execute` through the CLI, for the two things no tool does: making a database and
    activating a namespace. Returns stdout; the caller reads it for its own sentinel, because
    `exec` exits 0 on an ObjectScript error and writes the text."""
    import subprocess

    command = [_binary(), "exec", code, "-n", namespace]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise CheckBroken(
            f"`exec` exited {result.returncode}: "
            f"{(result.stderr or result.stdout).strip()[:400]}"
        )
    return result.stdout
