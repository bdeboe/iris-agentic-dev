"""A graded task, and the validation that decides whether it is allowed to produce a number.

121 T026/T028. FR-003, FR-004 and FR-022 in code.

A task is a YAML file with four parts and no fifth:

```yaml
id: PILOT-01
prompt: |            what the agent is asked
fixtures:            classes written to the benchmark namespace before the session
  - name: Pilot.X
    content: |
      Class Pilot.X ...
check: |             ObjectScript that prints exactly PASS or exactly FAIL
  write $select(<assertion>:"PASS",1:"FAIL")
solution:            the reference: the same classes, correct
  - name: Pilot.X
    content: |
      ...
```

There is deliberately no rubric, no `expected_behavior`, and no judge. `benchmark/021`'s tasks have
all three, and the two defects that produced four skills at 0.00 against 0.00 both lived in the
distance between what an agent did and what a judge was shown. A check that prints PASS from an
ObjectScript assertion has no such distance.

Validation is two-stage, because the two halves can answer different amounts on their own:

- `validate_shape` — pure, runs in the unit suite on every commit. Fields present, no judge fields,
  the reference solution addresses the fixture's own classes, the check reads no clock and rolls no
  dice.
- `validate_live` — needs IRIS, which is the only thing that can answer FR-004 and FR-022: apply the
  fixture and the check must FAIL, apply the reference and the same check must PASS. Costs no model
  tokens, so it runs before every pilot session rather than once.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field

import yaml

BENCHMARK_NAMESPACE = "BENCHMARK"

BENCHMARK_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "tasks", "benchmark"
)

#: The eight tasks that decided the go/no-go. `tests/e2e/results/pilot-121.json` names them, so they
#: stay where they are: a task that changes directory stops matching its own recorded result.
PILOT_DIR = os.path.join(BENCHMARK_DIR, "pilot")

#: The tools ladder — bare against tools against tools+skills. 121 T031 grows this one.
CORPUS_DIR = os.path.join(BENCHMARK_DIR, "corpus")

#: The skills ladder. One named skill per task, and the discriminator is a documented convention the
#: model cannot infer from the prompt.
SKILL_TASK_DIR = os.path.join(BENCHMARK_DIR, "skills")

#: Everything the split has to cover. Not a glob over `BENCHMARK_DIR`: a directory added by accident
#: should not silently join the corpus, and the split file itself lives there.
TASK_DIRS = (PILOT_DIR, CORPUS_DIR, SKILL_TASK_DIR)

# Fields whose presence means a human wrote a grading criterion for a model to apply. Rejected by
# name rather than by inspection, because the reason to reject them is what they are for.
JUDGE_FIELDS = (
    "expected_behavior",
    "rubric",
    "judge_model",
    "judge",
    "criteria",
    "score_guidance",
)

# Constructs that make the same check answer differently on a second run: the clock, the dice, the
# process. A figure that moves with the date cannot be compared to last month's figure.
NONDETERMINISTIC = (
    "$H",
    "$HOROLOG",
    "$ZTS",
    "$NOW",
    "$ZH",
    "$ZHOROLOG",
    "$RANDOM",
    "$R(",
    "$JOB",
    "$J,",
)

PASS_WORD = "PASS"
FAIL_WORD = "FAIL"


class CorpusInvalid(ValueError):
    """A task is not allowed in the gated corpus. Validation fails; the run does not start."""


class CheckBroken(RuntimeError):
    """A check produced output that is neither PASS nor FAIL, so it has said nothing.

    Not a failure. Scoring unreadable check output 0 is the same mistake as scoring a killed session
    0 — it files a harness fault in the skill's column. See `lift.session_evidence_gap`.
    """


@dataclass(frozen=True)
class Document:
    name: str
    content: str


@dataclass(frozen=True)
class GradedTask:
    id: str
    prompt: str
    check: str
    fixtures: tuple[Document, ...]
    solution: tuple[Document, ...]
    namespace: str = BENCHMARK_NAMESPACE
    skill: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)


def check_verdict(output: str) -> bool:
    """Read a check's stdout. PASS or FAIL, or `CheckBroken` — never a silent third answer."""
    text = output.strip()
    has_pass = PASS_WORD in text
    has_fail = FAIL_WORD in text
    if has_pass and not has_fail:
        return True
    if has_fail and not has_pass:
        return False
    raise CheckBroken(
        f"check output is neither PASS nor FAIL, so it graded nothing: {text!r} — this is a broken "
        "check, not a failed task"
    )


def load_task(path: str) -> GradedTask:
    """Parse one task file and validate its shape. A file that cannot produce a valid task raises."""
    with open(path, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise CorpusInvalid(f"{path}: a task is a mapping, got {type(raw).__name__}")

    stem = os.path.splitext(os.path.basename(path))[0]
    declared = raw.get("id")
    if declared != stem:
        raise CorpusInvalid(
            f"{path}: id {declared!r} does not match the filename {stem!r} — a task loaded under one "
            "id and reported under another mislabels every row it appears in"
        )

    present_judge = [name for name in JUDGE_FIELDS if name in raw]
    if present_judge:
        raise CorpusInvalid(
            f"{stem}: FR-003 — {', '.join(present_judge)} is a field a model judge reads. Every "
            "gated task is graded by a deterministic check against IRIS state; there is nowhere for "
            "a judgement to enter"
        )

    for required in ("prompt", "check"):
        if not str(raw.get(required) or "").strip():
            raise CorpusInvalid(f"{stem}: no {required}")

    task = GradedTask(
        id=stem,
        prompt=str(raw["prompt"]),
        check=str(raw["check"]),
        fixtures=_documents(stem, raw.get("fixtures"), "fixtures"),
        solution=_documents(stem, raw.get("solution"), "solution"),
        namespace=str(raw.get("namespace", BENCHMARK_NAMESPACE)),
        skill=raw.get("skill"),
        tags=tuple(raw.get("tags") or ()),
    )
    validate_shape(task)
    return task


def validate_shape(task: GradedTask) -> None:
    """Everything about a task that can be decided without IRIS."""
    if not task.fixtures:
        raise CorpusInvalid(
            f"{task.id}: FR-004 — no fixture, so there is no untouched state for the check to be "
            "false against. A check that passes before the agent runs measures nothing: every arm "
            "clears it and the lift is 0.00 whatever the tools do"
        )
    if not task.solution:
        raise CorpusInvalid(
            f"{task.id}: FR-022 — no reference solution. A reference is the only thing that tells a "
            "hard task from a broken check, which is the failure that cost this program four skills"
        )
    fixture_names = {doc.name for doc in task.fixtures}
    strangers = sorted(
        doc.name for doc in task.solution if doc.name not in fixture_names
    )
    if strangers:
        raise CorpusInvalid(
            f"{task.id}: the reference solution writes {', '.join(strangers)}, which the fixture "
            f"never set up (fixture: {', '.join(sorted(fixture_names))}). That is a second task in "
            "the same file, not the answer to this one"
        )
    found = [token for token in NONDETERMINISTIC if token in task.check]
    if found:
        raise CorpusInvalid(
            f"{task.id}: the check reads {', '.join(found)}, so it can answer differently on a "
            "second run. FR-003's word is deterministic"
        )
    if PASS_WORD not in task.check or FAIL_WORD not in task.check:
        raise CorpusInvalid(
            f"{task.id}: the check must be able to print both {PASS_WORD} and {FAIL_WORD}; a check "
            "with only one of them cannot discriminate"
        )


def load_dir(path: str) -> tuple[GradedTask, ...]:
    """Every task file in one directory, in id order.

    A directory that does not exist yet is empty rather than an error. `corpus/` and `skills/` fill
    up over two separate goals, and the pilot's own tests should not wait on either.
    """
    if not os.path.isdir(path):
        return ()
    names = sorted(name for name in os.listdir(path) if name.endswith(".yaml"))
    return tuple(load_task(os.path.join(path, name)) for name in names)


def pilot_tasks() -> tuple[GradedTask, ...]:
    """The committed pilot corpus, in id order."""
    return load_dir(PILOT_DIR)


def all_tasks() -> tuple[GradedTask, ...]:
    """Every committed task across the three directories, in id order.

    A duplicate ID raises. Two tasks under one ID pair against each other across arms, and the lift
    is then computed over a row that is two different tasks — a failure with no symptom.
    """
    tasks: list[GradedTask] = []
    seen: dict[str, str] = {}
    for directory in TASK_DIRS:
        for task in load_dir(directory):
            if task.id in seen:
                raise CorpusInvalid(
                    f"{task.id} is declared twice: {seen[task.id]} and {directory}. One ID is one "
                    "task, or the arms pair rows that are not the same task"
                )
            seen[task.id] = directory
            tasks.append(task)
    return tuple(sorted(tasks, key=lambda task: task.id))


def tools_corpus() -> tuple[GradedTask, ...]:
    """The tools ladder: every task that names no skill."""
    return tuple(task for task in all_tasks() if task.skill is None)


def skill_corpus() -> tuple[GradedTask, ...]:
    """The skills ladder: every task that names one.

    The partition is the field and not the directory, so a skill task filed in the wrong place still
    runs in the right ladder rather than quietly inflating the tools number.
    """
    return tuple(task for task in all_tasks() if task.skill is not None)


# --- the live half: IRIS answers FR-004 and FR-022 ----------------------------------------------


def _iad(args: list[str], namespace: str) -> str:
    """One CLI call. Raises `CheckBroken` on a non-zero exit, because a check that could not run has
    not answered — the same rule the killed-session guard applies to sessions."""
    binary = os.environ.get("IAD_BINARY", "iris-agentic-dev")
    command = [binary, args[0], "-n", namespace, *args[1:]]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise CheckBroken(
            f"`{' '.join(command[:3])} …` exited {result.returncode}: "
            f"{(result.stderr or result.stdout).strip()[:400]}"
        )
    return result.stdout


def _tool(name: str, payload: dict, namespace: str) -> dict:
    """Dispatch one tool and parse its envelope. A tool the CLI could not run raises."""
    output = _iad(["tool", name, "-a", json.dumps(payload)], namespace)
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise CheckBroken(f"{name} returned no JSON: {output.strip()[:300]}") from exc


def apply_documents(documents, namespace: str = BENCHMARK_NAMESPACE) -> None:
    """Write each document, then compile it. The write must succeed; the compile need not.

    Two steps rather than `iris_doc(mode="put", compile=true)`, because a fixture that does not
    compile *is* the task in the debug cases — the one-call form exits non-zero on the compile error
    and the fixture never lands. Here the write is fatal and the compile is data: the check decides.

    Not `$system.OBJ.Compile` from `exec` either. The write gate blocks reaching class code through
    arbitrary execution (`CODE_EDIT_BLOCKED`, matched `$SYSTEM.OBJ.COMPILE`), which is the gate
    working as designed, and is why an earlier attempt compiled nothing while exiting 0.

    `allow_storage_regeneration` is set because a reference solution for a persistent class carries no
    Storage block while the server-side fixture already has a generated one. In a corpus namespace
    that is what is wanted; the confirmation exists to stop it happening to real data.
    """
    for doc in documents:
        _tool(
            "iris_doc",
            {
                "mode": "put",
                "name": f"{doc.name}.cls",
                "content": doc.content,
                "namespace": namespace,
                "allow_storage_regeneration": True,
            },
            namespace,
        )
    for doc in documents:
        try:
            _tool(
                "iris_compile",
                {"target": f"{doc.name}.cls", "namespace": namespace},
                namespace,
            )
        except CheckBroken:
            pass


def run_check(task: GradedTask) -> bool:
    return check_verdict(_iad(["exec", task.check], task.namespace))


def reset_documents(names, namespace: str = BENCHMARK_NAMESPACE) -> None:
    """Delete the named classes so the next arm starts from the fixture, not from the last arm's
    answer. The comparison is paired per task across arms, so carry-over would report one arm's work
    in the next arm's column.

    Deletion goes through `iris_doc(mode="delete")`, not `$system.OBJ.Delete` in `exec` — the write
    gate blocks that with `CODE_EDIT_BLOCKED`, correctly. A document that was not there is not an
    error here: the first run of a task has nothing to reset.
    """
    for name in sorted(set(names)):
        try:
            _tool(
                "iris_doc",
                {"mode": "delete", "name": f"{name}.cls", "namespace": namespace},
                namespace,
            )
        except CheckBroken:
            pass


def package_prefixes(documents) -> tuple[str, ...]:
    """The top-level packages a task's fixture lives in, which is where a session writes its classes.

    `iris_doc list` refuses a bare wildcard, so the snapshot is per package; a class a session writes
    outside these packages is not seen (130 FR-023).
    """
    return tuple(sorted({doc.name.split(".")[0] for doc in documents}))


def list_classes(prefixes, namespace: str = BENCHMARK_NAMESPACE) -> set[str]:
    """Every class under the given packages, without the `.cls`. A truncated list raises: deleting
    the difference against a partial snapshot would delete classes the session never touched.
    """
    names: set[str] = set()
    for prefix in prefixes:
        listing = _tool(
            "iris_doc",
            {"mode": "list", "category": "CLS", "pattern": f"{prefix}.*"},
            namespace,
        )
        if listing.get("truncated"):
            raise CheckBroken(
                f"iris_doc list {prefix}.* came back truncated, so the snapshot is not whole"
            )
        names.update(
            doc["name"].removesuffix(".cls") for doc in listing.get("documents", [])
        )
    return names


def created_classes(before, after) -> list[str]:
    """The classes that exist now and did not at the snapshot."""
    return sorted(set(after) - set(before))


def validate_live(task: GradedTask) -> None:
    """FR-004 and FR-022 against real IRIS: false before, true after.

    Order matters. The fixture goes on first and the check must fail; then the reference goes over it
    and the same check must pass. The other order would leave the reference in place and prove
    nothing about the precondition.
    """
    reset_documents([doc.name for doc in task.fixtures], task.namespace)
    apply_documents(task.fixtures, task.namespace)
    if run_check(task):
        raise CorpusInvalid(
            f"{task.id}: FR-004 — the check passes against the untouched fixture, so the task is "
            "already solved before the agent starts and every arm clears it"
        )
    apply_documents(task.solution, task.namespace)
    if not run_check(task):
        raise CorpusInvalid(
            f"{task.id}: FR-022 — the reference solution does not pass this task's own check. Either "
            "the reference is wrong or the check is, and until that is settled a 0.00 from this task "
            "says nothing about the agent"
        )


def _documents(task_id: str, raw, label: str) -> tuple[Document, ...]:
    if not raw:
        return ()
    if not isinstance(raw, list):
        raise CorpusInvalid(f"{task_id}: {label} must be a list of documents")
    documents = []
    for entry in raw:
        if not isinstance(entry, dict) or "name" not in entry or "content" not in entry:
            raise CorpusInvalid(
                f"{task_id}: each {label} entry needs a name and content"
            )
        documents.append(
            Document(name=str(entry["name"]), content=str(entry["content"]))
        )
    return tuple(documents)
