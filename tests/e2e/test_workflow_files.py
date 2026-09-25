"""Every file in .github/workflows/ has to parse and describe runnable jobs.

An unparseable workflow does not fail loudly. GitHub records a 0-second run with no jobs,
labels it with the file path instead of the workflow name, and says "This run likely failed
because of a workflow file issue". That is a red X indistinguishable at a glance from a
test failure, so ci.yml sat broken from 2026-08-24 (commit 4dec14f, an inline `python -c`
heredoc at column 0 inside `run: |`) through 2026-08-26 with nothing running on master.

These tests parse the workflows the way GitHub does. They cannot protect the workflow they
run under — a broken ci.yml never reaches this file — so the same failure is also caught
before a push by `crates/iris-agentic-dev-bin/tests/unit/test_workflow_files.rs`, which
runs in `cargo test`. This layer covers the other workflows and the semantic checks a plain
text scan cannot make.
"""

import glob
import os

import pytest

yaml = pytest.importorskip("yaml")

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_WORKFLOW_DIR = os.path.join(_REPO_ROOT, ".github", "workflows")


def _workflow_files() -> list[str]:
    files = sorted(
        glob.glob(os.path.join(_WORKFLOW_DIR, "*.yml"))
        + glob.glob(os.path.join(_WORKFLOW_DIR, "*.yaml"))
    )
    assert files, f"no workflow files under {_WORKFLOW_DIR}"
    return files


def _load(path: str) -> dict:
    with open(path) as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as e:
            pytest.fail(f"{os.path.basename(path)} is not valid YAML: {e}")


@pytest.mark.parametrize("path", _workflow_files(), ids=os.path.basename)
def test_workflow_parses_and_declares_jobs(path):
    workflow = _load(path)
    assert isinstance(workflow, dict), (
        f"{os.path.basename(path)} must parse to a mapping"
    )

    # `on` is the YAML 1.1 boolean True once parsed, which is also how GitHub reads it.
    assert workflow.get("name"), f"{os.path.basename(path)} has no top-level `name`"
    assert "on" in workflow or True in workflow, (
        f"{os.path.basename(path)} has no trigger (`on:`) — it can never run"
    )

    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict) and jobs, (
        f"{os.path.basename(path)} declares no jobs — this is what a clipped block scalar "
        f"looks like after parsing, and what GitHub reports as a workflow file issue"
    )


@pytest.mark.parametrize("path", _workflow_files(), ids=os.path.basename)
def test_every_step_runs_something(path):
    """A step with neither `uses` nor a non-empty `run` is a step that lost its body."""
    workflow = _load(path)
    for job_name, job in (workflow.get("jobs") or {}).items():
        if "uses" in job:  # reusable workflow call — no steps of its own
            continue
        steps = job.get("steps")
        assert steps, f"{os.path.basename(path)}: job `{job_name}` has no steps"
        for position, step in enumerate(steps, start=1):
            label = step.get("name") or step.get("uses") or f"step {position}"
            if "uses" in step:
                continue
            run = step.get("run")
            assert isinstance(run, str) and run.strip(), (
                f"{os.path.basename(path)}: job `{job_name}` step `{label}` has neither "
                f"`uses` nor a non-empty `run:`"
            )


# --- the benchmark harness has to run somewhere ----------------------------------------------------
#
# Spec 121 added about 900 tests under `tests/e2e/` and CI ran three files. A harness nothing
# exercises is a harness that reports success while broken, which is the whole reason the nightly
# spent weeks scoring a bare model as a failing skill. These four assertions are in this file
# because CI already runs it, so they are live the moment the branch merges.


def _ci() -> dict:
    return _load(os.path.join(_WORKFLOW_DIR, "ci.yml"))


def _run_steps(workflow: dict):
    """(job_name, step_label, run_body) for every step that runs a shell command."""
    for job_name, job in (workflow.get("jobs") or {}).items():
        if "uses" in job:
            continue
        for position, step in enumerate(job.get("steps") or [], start=1):
            run = step.get("run")
            if isinstance(run, str) and run.strip():
                label = step.get("name") or f"step {position}"
                yield job_name, label, run


HARNESS_SUITES = ("tests/e2e/skill_eval", "benchmark/harbor")


def _covers(run: str, suite: str) -> bool:
    """Does this `pytest` invocation collect `suite`, directly or via an ancestor directory?

    `pytest tests/e2e` covers `tests/e2e/skill_eval`, so matching the exact string would fail on a
    broader step — which is the wrong direction to push a fix.
    """
    if "pytest" not in run:
        return False
    parts = suite.split("/")
    return any("/".join(parts[:depth]) in run for depth in range(1, len(parts) + 1))


def test_ci_runs_the_benchmark_harness_suite():
    """Some job has to invoke pytest over the harness directories."""
    bodies = [run for _, _, run in _run_steps(_ci())]
    for suite in HARNESS_SUITES:
        assert any(_covers(run, suite) for run in bodies), (
            f"no ci.yml step runs pytest over {suite}/. Spec 121's harness lives there and "
            f"nothing on master would notice it breaking"
        )


def test_ci_runs_the_harness_as_a_directory_not_a_file_list():
    """A hand-listed set of files silently stops covering the next file someone adds.

    This is the anti-rot property: the suite is named by directory, so a new test file is gated by
    existing. The billable tests are excluded by their marker at collection time, not by being
    listed here — see `tests/e2e/billing.py`.
    """
    for _, label, run in _run_steps(_ci()):
        if "pytest" not in run:
            continue
        assert ".py" not in run, (
            f"ci.yml step `{label}` names individual test files. Name the directory instead and "
            f"let markers do the excluding, or the next file added is covered by nothing — which "
            f"is how ~1000 tests under tests/e2e sat behind three named files"
        )


def test_ci_still_covers_the_files_it_used_to_name():
    """The guards that were named steps before the directory sweep replaced them.

    A release workflow broken in ordering can only otherwise be found by cutting a tag, and an
    unparseable workflow shows up as a 0-second run with no jobs — ci.yml sat dead on master for two
    days that way. Widening the step must not have dropped either.
    """
    load_bearing = (
        "tests/e2e/test_release_workflow.py",
        "tests/e2e/test_workflow_files.py",
        # 122 added these three as named steps; they merged after the sweep existed.
        "tests/e2e/test_plugin_manifest.py",
        "tests/e2e/test_plugin_skills.py",
        "tests/e2e/test_setup_skill.py",
    )
    bodies = [run for _, _, run in _run_steps(_ci())]
    for path in load_bearing:
        assert any(_covers(run, path) for run in bodies), (
            f"nothing in ci.yml collects {path}. It was a named step until the suite was widened "
            f"to a directory; if the directory no longer contains it, restore a step for it"
        )
        assert os.path.isfile(os.path.join(_REPO_ROOT, path)), (
            f"{path} does not exist, so the directory sweep cannot be running it"
        )


BINARY_MARKER = "requires_binary"


def test_ci_runs_the_tests_that_need_a_built_binary():
    """A test that skips for a missing binary is a test CI is not running.

    `benchmark-lint` has python and no cargo, so the getting-started guard and the T007
    `tools/list` check resolved nothing and skipped — and `provenance` falls back to a Homebrew
    path, which on a runner is the #118 failure exactly: green over a suite that never ran. The
    step has to select by marker and name the build in the same command, since only the job that
    ran `cargo build` knows where it is.
    """
    steps = [
        (label, run)
        for _, label, run in _run_steps(_ci())
        if f"-m {BINARY_MARKER}" in run or f"'{BINARY_MARKER}'" in run
    ]
    assert steps, (
        f"no ci.yml step selects -m {BINARY_MARKER}. Without it every test marked that way "
        f"skips on the runner and the job still passes"
    )
    for label, run in steps:
        assert "IAD_BINARY" in run, (
            f"ci.yml step `{label}` selects -m {BINARY_MARKER} without setting IAD_BINARY, so "
            f"provenance falls through to a Homebrew path no runner has and the tests skip"
        )
        assert "target/debug/iris-agentic-dev" in run, (
            f"ci.yml step `{label}` sets IAD_BINARY to something other than the build this job "
            f"produced. Point it at target/debug/iris-agentic-dev or it is testing a release "
            f"nobody in this run compiled"
        )


def test_something_actually_carries_the_binary_marker():
    """The marker selection must not be vacuous.

    `pytest -m` over a directory that contains no match deselects everything and exits 0, so
    renaming the marker on the tests and leaving ci.yml alone turns the step into a no-op that
    still reports success.
    """
    marked = []
    for path in glob.glob(
        os.path.join(_REPO_ROOT, "tests", "e2e", "**", "test_*.py"), recursive=True
    ):
        with open(path, encoding="utf-8") as handle:
            if f"pytest.mark.{BINARY_MARKER}" in handle.read():
                marked.append(os.path.relpath(path, _REPO_ROOT))
    assert marked, (
        f"no test under tests/e2e/ carries @pytest.mark.{BINARY_MARKER}, so the ci.yml step "
        f"selecting it collects nothing and passes"
    )


def test_no_ci_step_opts_into_billable_sessions():
    """CI must never set the opt-in. A runner that spends money does it 365 nights a year."""
    from tests.e2e import billing

    workflows = {os.path.basename(path): _load(path) for path in _workflow_files()}
    for name, workflow in workflows.items():
        scopes = [workflow.get("env") or {}]
        for job in (workflow.get("jobs") or {}).values():
            if "uses" in job:
                continue
            scopes.append(job.get("env") or {})
            for step in job.get("steps") or []:
                scopes.append(step.get("env") or {})
        for scope in scopes:
            assert billing.BILLABLE_ENV not in scope, (
                f"{name} sets {billing.BILLABLE_ENV} in an env block. The four commands whose job "
                f"is to spend set it themselves for the length of the call; a workflow that "
                f"exports it opts every collected test in"
            )
        for _, label, run in _run_steps(workflow):
            assert f"{billing.BILLABLE_ENV}=1" not in run, (
                f"{name} step `{label}` exports {billing.BILLABLE_ENV}=1 inline"
            )


def test_the_nightly_is_the_only_workflow_that_starts_a_session():
    """Exactly one workflow is allowed to spend, and it is named so a diff has to justify a second."""
    spenders = set()
    for path in _workflow_files():
        workflow = _load(path)
        for _, _, run in _run_steps(workflow):
            if "skill_eval.nightly_canary" in run or "skill_eval.ladder" in run:
                spenders.add(os.path.basename(path))
    assert spenders == {"skill-regression.yml"}, (
        f"workflows that start agent sessions: {sorted(spenders) or 'none'}. Only "
        f"skill-regression.yml is budgeted for it"
    )
