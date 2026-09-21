"""Every lift figure printed in a document traces to the artifact it claims to come from.

The bug this exists for: the README advertised `+27%` for `objectscript-review` for months after
the harness that produced it was gone. Nobody lied — the number was true when it was measured,
under a model judge on a 22-task corpus, and then the corpus changed, the judge was replaced by an
ObjectScript `PASS`/`FAIL` check, and the sentence stayed. A stale figure on the front page is
worse than no figure, because a reader has no way to tell which one they are looking at.

So the two figures the project publishes are checked against the run that produced them. If a
future run moves them, these tests fail and the documents get updated in the same commit, which is
the only time anyone remembers to do it.

Not asserted here: that the figures are *good*. `+0.098` for the skills is a bad result and the
test is just as happy — its subject is whether the document agrees with the data, not whether the
data flatters the project.
"""

from __future__ import annotations

import json
import os
import re

import pytest

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

#: The run behind `results.md`, `skills-verdict.md` and the README's skills section.
ARTIFACT = os.path.join(
    _REPO_ROOT, "tests", "e2e", "results", "ladder-121-tools-holdout.json"
)

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
        assert f"n={tools['n_pairs']}" in body or f"{tools['n_pairs']} " in body, (
            f"{document} quotes lift {figure} without the item count n={tools['n_pairs']}"
        )


def test_the_skills_figure_is_reported_as_indistinguishable():
    """The verdict, not just the number. `+0.098` read alone looks like a small win."""
    skills = _comparison(_report(), "tools", "tools+skills")
    assert not skills["publishable"] or skills["verdict"] != "passed", (
        f"the skills comparison now reads {skills['verdict']}; this test and the documents it "
        f"guards were written around a negative and both need revisiting"
    )
    readme = _read("README.md")
    assert f"{skills['lift']:+.3f}" in readme, (
        f"README does not carry the measured skills lift {skills['lift']:+.3f}. It advertised "
        f"+27% from a retired model-judged harness once; a figure with no artifact behind it is "
        f"how that happens again"
    )
    assert "indistinguishable" in readme.lower(), (
        "README quotes the skills lift without saying it is indistinguishable from no effect. "
        f"b={skills['b']} c={skills['c']} p={skills['p_value_one_sided']:.4f} — the number alone "
        f"reads as a small win"
    )


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


def test_the_graded_scoring_mode_is_the_one_the_ladder_writes():
    """Guards the constant above against a rename in `ladder.py` that this file never heard about."""
    source = _read(os.path.join("tests", "e2e", "skill_eval", "ladder.py"))
    assert f'scoring_mode="{GRADED_SCORING_MODE}"' in source, (
        f"ladder.py no longer writes scoring_mode={GRADED_SCORING_MODE!r}, so the assertion that a "
        f"published artifact was machine-graded is checking a value nothing produces"
    )
