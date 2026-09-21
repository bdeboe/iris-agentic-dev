"""One graded harness, and the rule that keeps a second from growing back — 121 T043/T044, FR-018.

Four things in this repo could be called a benchmark before spec 121 finished. Two survive and two
do not, and the difference is not taste:

- **`tests/e2e/skill_eval/` survives.** It is the graded harness: machine-checkable tasks, a
  committed train/holdout split, a publish guard, and the artifact behind
  `specs/121-benchmark-program/results.md`.
- **`crates/iris-agentic-dev-core/src/benchmark/` survives.** Different job entirely — it is the
  `iris-agentic-dev benchmark` subcommand shipped to users, with its tasks embedded at compile time
  via `include_str!`. `skills/BENCHMARKING.md` documents it. Nothing about it competes with the
  graded harness, and deleting it would break a released CLI.
- **`benchmark/021/` is gone.** A second Python harness with its own 39 tasks, its own runner and
  its own results layout, reachable only by a `sys.path.insert`. Two harnesses over overlapping
  tasks means two pass rates and no way to say which one a number came from.
- **`tools/gepa-optimizer/` stays** and is not a harness. It consumes the train side of the split,
  which is the reason the split exists.

The 39 tasks and the runner are recoverable from git history; nothing was lost, it was retired. Its
`results/` directory was never tracked (`.gitignore` line 28), so whatever is on a given disk is
local evidence and this deletion does not touch it.

What this file is for: the deletion is easy to undo by accident. A new `sys.path.insert` into a
resurrected directory, or a doc telling a contributor to add tasks there, and the repo has two
harnesses again with nothing complaining.
"""

from __future__ import annotations

import os
import subprocess

import pytest

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

#: The retired harness. Named once so a future rename cannot leave a half-updated test.
RETIRED = "benchmark/021"

#: Files allowed to say `benchmark/021` — the record of what happened, not a live pointer.
#: `specs/**` is the project's history and must keep naming the system a past figure came from.
HISTORY_PREFIXES = ("specs/", "tests/e2e/test_one_harness.py", "CHANGELOG.md")

#: Ways a file can *reach* the retired tree, as opposed to talking about it. This is the line the
#: guard draws, and it is drawn here rather than at "mentions the string" on purpose: half the
#: corpus records which 021 task it was drawn from and which judge scored the original, and that
#: provenance is the most useful thing anyone kept. Erasing it to satisfy a grep would trade the
#: record of where these tasks came from for a tidier search result.
EXECUTABLE_REFERENCES = (
    'sys.path.insert(0, "benchmark/021")',
    "sys.path.insert(0, 'benchmark/021')",
    'sys.path.insert(0, "benchmark/021/runner")',
    "from benchmark.021",
    "import benchmark.021",
    "benchmark/021/runner')",
    'benchmark/021/runner")',
    "python benchmark/021",
    "python -m benchmark.021",
    "benchmark/run_021.py",
    "benchmark/021/tasks/",
)


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=_REPO_ROOT, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        pytest.skip(f"not a git work tree: {result.stderr.strip()}")
    return [line for line in result.stdout.splitlines() if line]


def test_the_retired_harness_is_not_tracked():
    """Existing on someone's disk is fine. Being in the repo is what makes it a second harness."""
    tracked = [path for path in _tracked_files() if path.startswith(f"{RETIRED}/")]
    assert not tracked, (
        f"{RETIRED}/ is tracked again ({len(tracked)} files, e.g. {tracked[:3]}). Spec 121 T044 "
        f"retired it so one harness owns the graded number; two pass rates over overlapping tasks "
        f"cannot both be cited"
    )


def test_nothing_reaches_into_the_retired_harness():
    """A `sys.path` shim into a deleted tree, or a doc telling a contributor to add tasks there.

    Both are how the second harness comes back. Prose about 021's design is left alone — see
    `EXECUTABLE_REFERENCES` for why the line sits at reaching rather than at naming.
    """
    offenders = {}
    for path in _tracked_files():
        if path.startswith(HISTORY_PREFIXES):
            continue
        full = os.path.join(_REPO_ROOT, path)
        if not os.path.isfile(full):
            continue
        try:
            with open(full, encoding="utf-8") as handle:
                body = handle.read()
        except (UnicodeDecodeError, OSError):
            continue
        hits = [pattern for pattern in EXECUTABLE_REFERENCES if pattern in body]
        if hits:
            offenders[path] = hits
    assert not offenders, (
        f"these tracked files still reach into the retired {RETIRED}/: {offenders}. Point them at "
        f"tests/e2e/skill_eval/ (the graded harness) or at the `iris-agentic-dev benchmark` "
        f"subcommand, whichever the reader actually needs"
    )


def test_the_graded_harness_is_the_one_with_a_split():
    """What makes `skill_eval` the survivor, asserted rather than asserted-in-a-comment."""
    from tests.e2e.skill_eval.graded_task import all_tasks
    from tests.e2e.skill_eval.split import default_split

    split = default_split()
    assert all_tasks(), "the graded harness has no tasks"
    assert split.train and split.holdout, (
        "the surviving harness must carry a train/holdout split"
    )


def test_the_absorbed_modules_are_importable_from_the_survivor():
    """`judge` and `scorer_client` resolve as ordinary modules, with no `sys.path` mutation.

    The old spelling worked only because this package's `__init__` inserted a directory into
    `sys.path` on import. That resolves under `pytest` from the repo root and nowhere else.
    """
    from tests.e2e.skill_eval.judge import score_result, unscored  # noqa: F401
    from tests.e2e.skill_eval.scorer_client import (  # noqa: F401
        CREDENTIAL_VARS,
        auth_source,
        haiku_model,
        make_client,
    )


def test_the_harness_imports_without_the_anthropic_sdk():
    """The graded corpus is scored by an ObjectScript check, so the SDK is not its dependency.

    `scorer_client` imported `anthropic` at module scope when it lived in the retired tree, which
    made the whole package unimportable without it. CI installs pytest, pyyaml and requests; if this
    regresses, every harness test fails at collection with an error about a package CI has no reason
    to carry.
    """
    import importlib
    import sys

    class Blocked:
        def find_module(self, name, path=None):
            return (
                self if name == "anthropic" or name.startswith("anthropic.") else None
            )

        def load_module(self, name):
            raise ImportError("anthropic not installed (simulated)")

    blocker = Blocked()
    sys.meta_path.insert(0, blocker)
    buried = [name for name in sys.modules if name.startswith("anthropic")]
    saved = {name: sys.modules.pop(name) for name in buried}
    try:
        for name in (
            "tests.e2e.skill_eval.scorer_client",
            "tests.e2e.skill_eval.judge",
            "tests.e2e.skill_eval.preflight",
            "tests.e2e.skill_eval.lift",
            "tests.e2e.skill_eval.ladder",
        ):
            sys.modules.pop(name, None)
            importlib.import_module(name)
    finally:
        sys.meta_path.remove(blocker)
        sys.modules.update(saved)


def test_the_shipped_benchmark_subcommand_keeps_its_own_tasks():
    """The other survivor. Deleting these would break `iris-agentic-dev benchmark` for users."""
    embedded = os.path.join(
        _REPO_ROOT, "crates", "iris-agentic-dev-core", "src", "benchmark", "tasks"
    )
    assert os.path.isdir(embedded), (
        f"{embedded} is missing. `skills/BENCHMARKING.md` documents "
        f"`iris-agentic-dev benchmark` against these, and they are embedded with include_str!, so "
        f"a missing directory is a build failure for a released subcommand"
    )
