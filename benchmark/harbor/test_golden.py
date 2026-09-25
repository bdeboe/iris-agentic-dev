"""The golden-file test — 120 T011, FR-003.

Harbor's task format is young and moving, and the exporter is the only place in this repo that knows
it (FR-001). This test is the tripwire: a format drift, or a well-meant edit to a generated script,
shows up as a diff against a committed directory rather than as a corpus that runs and grades nothing.

The golden export pins `image` explicitly. The version pin itself is covered by
`test_export.py::test_the_iad_image_is_pinned_to_the_workspace_version`; leaving it floating here
would turn every release bump into a golden-file failure that says nothing about the format.

To adopt a deliberate change:

    IAD_UPDATE_GOLDEN=1 python -m pytest benchmark/harbor/test_golden.py

and read the diff before committing it.
"""

from __future__ import annotations

import filecmp
import os
import shutil

from benchmark.harbor.export import export_task
from tests.e2e.skill_eval.arms import TOOLS
from tests.e2e.skill_eval.graded_task import load_task

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE_TASK = os.path.join(HERE, "fixtures", "GOLDEN-01.yaml")
GOLDEN_DIR = os.path.join(HERE, "golden", "golden-01-tools")

#: Pinned so the golden file measures format drift and nothing else.
GOLDEN_IMAGE = "ghcr.io/intersystems-community/iris-agentic-dev:v1.4.2"


def tree(root: str) -> dict[str, str]:
    """Every file under `root`, keyed by relative path, with its mode bits."""
    found = {}
    for directory, _subdirs, names in os.walk(root):
        for name in names:
            path = os.path.join(directory, name)
            relative = os.path.relpath(path, root)
            found[relative] = "x" if os.access(path, os.X_OK) else "-"
    return found


def test_one_complete_exported_task_directory_matches_the_golden_copy(tmp_path):
    exported = export_task(
        load_task(SOURCE_TASK),
        TOOLS,
        str(tmp_path),
        validate=lambda task: None,
        image=GOLDEN_IMAGE,
    )

    if os.environ.get("IAD_UPDATE_GOLDEN"):
        shutil.rmtree(GOLDEN_DIR, ignore_errors=True)
        shutil.copytree(exported.directory, GOLDEN_DIR)

    assert os.path.isdir(
        GOLDEN_DIR
    ), f"no golden copy at {GOLDEN_DIR} — run with IAD_UPDATE_GOLDEN=1 and read the diff"
    assert tree(exported.directory) == tree(GOLDEN_DIR), "the exported file set changed"

    for relative in sorted(tree(GOLDEN_DIR)):
        left = os.path.join(exported.directory, relative)
        right = os.path.join(GOLDEN_DIR, relative)
        with open(left, encoding="utf-8") as handle:
            produced = handle.read()
        with open(right, encoding="utf-8") as handle:
            committed = handle.read()
        assert produced == committed, f"{relative} drifted from the golden copy"
        assert filecmp.cmp(left, right, shallow=False)


def test_the_golden_source_task_is_a_valid_corpus_task():
    """The tripwire is only worth having over a task the corpus would actually accept."""
    task = load_task(SOURCE_TASK)
    assert task.id == "GOLDEN-01"
    assert task.fixtures and task.solution
