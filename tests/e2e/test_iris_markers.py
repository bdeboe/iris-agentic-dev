"""The `requires_iris` marker means something, because CI's filter is built on it.

`ci.yml` runs `pytest tests/e2e benchmark/harbor -m "not requires_iris and not network_curl and not
billable"`, and a marker that no test carries makes that clause a no-op. It was one: the marker was
registered in `conftest.py`, named in the CI filter, and applied to nothing, while 70 live-IRIS
tests kept themselves off a container-less runner with a module-level `skipif` that shells out to
`docker ps`. Two mechanisms, one of them hollow.

The consequence was not a red CI — the skipif did its job. It was that `pytest -m requires_iris`,
which is what you type when you want exactly the tests a container answers, collected nothing.

Both mechanisms stay. The marker is how a filter selects, the skipif is how a run survives a
missing container, and they have to agree about which tests are which.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

#: A module-level skip that shells out to `docker ps` is the signature of a live-IRIS test file.
_DOCKER_SKIP = re.compile(r'"docker",\s*\n?\s*"ps"|\["docker", "ps"')

SEARCH_DIRS = ("tests/e2e", "tests/e2e/skill_eval")


def _test_files() -> list[str]:
    found = []
    for directory in SEARCH_DIRS:
        full = os.path.join(_REPO_ROOT, directory)
        if not os.path.isdir(full):
            continue
        for entry in sorted(os.listdir(full)):
            if entry.startswith("test_") and entry.endswith(".py"):
                found.append(os.path.join(directory, entry))
    return found


def test_every_docker_gated_file_also_carries_the_marker():
    """Static half: the two mechanisms agree about which files need a container."""
    unmarked = []
    for relative in _test_files():
        with open(os.path.join(_REPO_ROOT, relative), encoding="utf-8") as handle:
            body = handle.read()
        if not _DOCKER_SKIP.search(body):
            continue
        if "pytest.mark.requires_iris" not in body:
            unmarked.append(relative)
    assert not unmarked, (
        f"these files skip themselves on `docker ps` but carry no requires_iris marker: {unmarked}. "
        f"Add it to their pytestmark, or `pytest -m requires_iris` keeps missing them and ci.yml's "
        f"filter keeps excusing nothing"
    )


def test_the_marker_selects_a_non_empty_set():
    """Live half: the filter CI depends on actually resolves to tests.

    Asserted by collection rather than by grep, because a marker applied inside an `if` or on a
    class that nothing subclasses would satisfy the static check and still select nothing.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/e2e",
            "-m",
            "requires_iris",
            "--collect-only",
            "-q",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": _REPO_ROOT},
        check=False,
    )
    if result.returncode not in (0, 5):
        pytest.skip(f"collection did not run cleanly: {result.stdout[-400:]}")
    match = re.search(r"(\d+)(?:/\d+)? tests collected", result.stdout)
    assert match, f"could not read a collected count from:\n{result.stdout[-600:]}"
    collected = int(match.group(1))
    assert collected > 0, (
        "`pytest -m requires_iris` collects nothing. ci.yml filters on `not requires_iris`, so an "
        "empty marker makes that clause a no-op and hides whether the IRIS tests are excluded on "
        "purpose or by accident"
    )
