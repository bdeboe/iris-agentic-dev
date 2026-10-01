"""Every lift figure printed in a document traces to the artifact it claims to come from.

The bug this exists for: the README advertised `+27%` for `objectscript-review` for months after
the harness that produced it was gone. Nobody lied — the number was true when it was measured,
under a model judge on a 22-task corpus, and then the corpus changed, the judge was replaced by an
ObjectScript `PASS`/`FAIL` check, and the sentence stayed. A stale figure on the front page is
worse than no figure, because a reader has no way to tell which one they are looking at.

So the two figures the project publishes are checked against the run that produced them. If a
future run moves them, these tests fail and the documents get updated in the same commit, which is
the only time anyone remembers to do it.

Not asserted here: that the figures are *good*. Its subject is whether the document agrees with
the data, not whether the data flatters the project. The 121 figures turned out to be void, not
bad: that run was not isolated, so a document may quote them only as withdrawn.
"""

from __future__ import annotations

import json
import os
import re
import subprocess

import pytest

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

#: The run behind `results.md`, `skills-verdict.md` and the README's skills section.
ARTIFACT = os.path.join(
    _REPO_ROOT, "tests", "e2e", "results", "ladder-121-tools-holdout.json"
)

#: Result-artifact filenames as they appear in test source. Matches bare names and path fragments.
_ARTIFACT_RE = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*\.jsonl?)")

#: Documents that quote a figure from that run, and must therefore quote this one.
CITING_DOCUMENTS = (
    "README.md",
    "specs/121-benchmark-program/results.md",
    "specs/121-benchmark-program/quickstart.md",
)


def _report() -> dict:
    if not os.path.isfile(ARTIFACT):
        pytest.skip(f"{ARTIFACT} not present")
    with open(ARTIFACT, encoding="utf-8") as handle:
        return json.load(handle)


def _comparison(report: dict, arm_a: str, arm_b: str) -> dict:
    for entry in report["comparisons"]:
        if entry["arm_a"] == arm_a and entry["arm_b"] == arm_b:
            return entry
    raise AssertionError(
        f"no {arm_a} -> {arm_b} comparison in {ARTIFACT}; the published figures name it"
    )


def _read(relative: str) -> str:
    with open(os.path.join(_REPO_ROOT, relative), encoding="utf-8") as handle:
        return handle.read()


def test_the_tools_figure_in_the_docs_is_the_figure_in_the_report():
    tools = _comparison(_report(), "bare", "tools")
    figure = f"{tools['lift']:+.3f}"
    low, high = tools["interval"]
    interval = f"[{low:+.3f}, {high:+.3f}]"
    for document in CITING_DOCUMENTS:
        body = _read(document)
        if figure not in body:
            continue  # this document does not quote the tools figure
        assert interval in body, (
            f"{document} quotes lift {figure} but not its interval {interval}. A lift without the "
            f"interval is not a result — it reads as precision the run does not have"
        )
        assert (
            f"n={tools['n_pairs']}" in body or f"{tools['n_pairs']} " in body
        ), f"{document} quotes lift {figure} without the item count n={tools['n_pairs']}"


#: What a document has to say near a 121 figure. That run was not isolated: opencode read
#: `~/.claude/CLAUDE.md` and `~/.claude/skills` into every session, in every arm, until
#: `OPENCODE_DISABLE_CLAUDE_CODE=1` was set (specs/130-content-skills/research.md). Both figures
#: are void, and 1.5.0's release notes say so.
WITHDRAWN_MARKERS = ("void", "withdrawn")

#: Where the finding is written down. A withdrawal with no reason reads as a figure that
#: embarrassed someone.
LEAK_FINDING = "specs/130-content-skills/research.md"


def test_no_document_presents_the_121_figures_as_current():
    """`+0.098` and `+0.829` may be named as history, next to the word that says they are void."""
    report = _report()
    figures = [
        f"{_comparison(report, 'tools', 'tools+skills')['lift']:+.3f}",
        f"{_comparison(report, 'bare', 'tools')['lift']:+.3f}",
    ]
    for document in CITING_DOCUMENTS:
        body = _read(document)
        # A note at the top withdraws the whole document.
        if "**withdrawn" in body[:800].lower():
            continue
        for figure in figures:
            for match in re.finditer(re.escape(figure), body):
                window = body[max(0, match.start() - 600) : match.end() + 600].lower()
                assert any(marker in window for marker in WITHDRAWN_MARKERS), (
                    f"{document} quotes {figure} near offset {match.start()} with nothing saying "
                    f"the 121 run is void. Every session in it had the operator's ~/.claude "
                    f"loaded; mark the figure withdrawn or drop it"
                )


def test_the_readme_says_why_the_figures_were_withdrawn():
    readme = _read("README.md")
    assert (
        "OPENCODE_DISABLE_CLAUDE_CODE" in readme
    ), "README withdraws the 121 figures without naming the leak that voided them"
    assert (
        LEAK_FINDING in readme
    ), f"README does not point at the finding in {LEAK_FINDING}"


def test_no_document_advertises_the_retired_figure_as_current():
    """`+27%` may be named as history. It may not be presented as what the skills do."""
    stale = re.compile(r"\+27%")
    for document in CITING_DOCUMENTS:
        body = _read(document)
        for match in stale.finditer(body):
            window = body[max(0, match.start() - 400) : match.end() + 400].lower()
            assert any(
                marker in window
                for marker in ("retired", "not comparable", "older", "no longer")
            ), (
                f"{document} names +27% near offset {match.start()} with nothing marking it as a "
                f"figure from the retired model-judged harness. Say which harness measured it or "
                f"drop it"
            )


#: `ladder.py` stamps this on a graded report. `judge.py` stamps `judge` and `lift.py` stamps
#: `assertion`/`pattern`, so the field distinguishes a machine-graded run from a model-graded one —
#: which is the single claim every published figure rests on.
GRADED_SCORING_MODE = "machine"

MODEL_SCORED_MODES = ("judge",)


def test_the_artifact_was_machine_graded_not_model_graded():
    """Every doc says no model scored a task. That claim is this field, or it is not true."""
    report = _report()
    mode = report.get("scoring_mode")
    assert mode, f"{ARTIFACT} carries no scoring_mode"
    assert mode not in MODEL_SCORED_MODES, (
        f"{ARTIFACT} was scored by {mode!r}. results.md and the README both say no model graded "
        f"anything; either the figures came from the wrong run or those sentences are now false"
    )
    assert mode == GRADED_SCORING_MODE, (
        f"scoring_mode is {mode!r}, not {GRADED_SCORING_MODE!r}. If the ladder renamed it, update "
        f"this constant deliberately — an unrecognised mode is not evidence of machine grading"
    )


def test_every_result_artifact_a_test_depends_on_is_tracked():
    """An artifact a test opens without guarding has to be in the repo, or the test is a local pass.

    `tests/e2e/results/.gitignore` ignores `*.json`, which is right for the hundred run dumps and
    wrong for the handful that are evidence. Three tests in `test_pilot.py` opened
    `pilot-121.json` unguarded while it sat untracked: green on the machine that produced it, red on
    every clean checkout. A `git clone` found it in seconds and nothing before that did, because CI
    ran three named files and none of them were these.
    """
    results_dir = os.path.join(_REPO_ROOT, "tests", "e2e", "results")
    # A test may read a tracked copy under `skill_eval/fixtures/` instead; the name then also
    # exists, untracked, in `results/`, and the copy is what a clean checkout has.
    tracked = subprocess.run(
        ["git", "ls-files", "tests/e2e/results", "tests/e2e/skill_eval/fixtures"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if tracked.returncode != 0:
        pytest.skip(f"not a git work tree: {tracked.stderr.strip()}")
    tracked_names = {
        os.path.basename(line) for line in tracked.stdout.splitlines() if line
    }

    named = set()
    for directory in ("tests/e2e", "tests/e2e/skill_eval", "benchmark/harbor"):
        full_dir = os.path.join(_REPO_ROOT, directory)
        if not os.path.isdir(full_dir):
            continue
        for entry in sorted(os.listdir(full_dir)):
            if not (entry.startswith("test_") and entry.endswith(".py")):
                continue
            with open(os.path.join(full_dir, entry), encoding="utf-8") as handle:
                body = handle.read()
            for candidate in _ARTIFACT_RE.findall(body):
                if os.path.isfile(os.path.join(results_dir, candidate)):
                    named.add((directory, entry, candidate))

    missing = sorted(
        f"{directory}/{test_file} -> {artifact}"
        for directory, test_file, artifact in named
        if artifact not in tracked_names
    )
    assert not missing, (
        f"these tests name a result artifact that exists here but is not in the repo: {missing}. "
        f"Either `git add -f` it, because a test depends on it, or stop depending on it"
    )


def test_the_graded_scoring_mode_is_the_one_the_ladder_writes():
    """Guards the constant above against a rename in `ladder.py` that this file never heard about."""
    source = _read(os.path.join("tests", "e2e", "skill_eval", "ladder.py"))
    assert f'scoring_mode="{GRADED_SCORING_MODE}"' in source, (
        f"ladder.py no longer writes scoring_mode={GRADED_SCORING_MODE!r}, so the assertion that a "
        f"published artifact was machine-graded is checking a value nothing produces"
    )
