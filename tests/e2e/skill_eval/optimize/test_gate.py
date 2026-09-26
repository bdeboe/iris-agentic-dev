"""Tests for `gate.py` — 128 T014 (User Story 3, SC-004)."""

from __future__ import annotations

from tests.e2e.skill_eval.optimize.gate import HOLD, SHIP, Outcome, decide

LADDER_OK = {"seed": 0.80, "candidate": 0.80}


def _run(para, exact, noskill):
    """Build outcomes from per-slice lists of correct flags."""
    out = {}
    for sl, flags in (
        ("paraphrase", para),
        ("exact-name", exact),
        ("no-skill", noskill),
    ):
        for k, ok in enumerate(flags):
            out[f"{sl}-{k}"] = Outcome(slice=sl, correct=bool(ok))
    return out


SEED = _run([0] * 20 + [1] * 10, [1] * 5, [1] * 40)
WIN = _run([1] * 30, [1] * 5, [1] * 40)


def test_clear_win_ships():
    v = decide(SEED, WIN, ladder=LADDER_OK)
    assert v.verdict == SHIP, v.failed
    assert v.failed == []


def test_tie_holds_on_the_interval():
    v = decide(SEED, SEED, ladder=LADDER_OK)
    assert v.verdict == HOLD
    assert any("recall" in f for f in v.failed)


def test_win_that_raises_false_hints_holds():
    cand = _run([1] * 30, [1] * 5, [1] * 39 + [0])
    v = decide(SEED, cand, ladder=LADDER_OK)
    assert v.verdict == HOLD
    assert any("false-hint" in f for f in v.failed)


def test_win_that_drops_exact_name_holds():
    cand = _run([1] * 30, [1] * 4 + [0], [1] * 40)
    v = decide(SEED, cand, ladder=LADDER_OK)
    assert v.verdict == HOLD
    assert any("exact-name" in f for f in v.failed)


def test_ladder_below_margin_holds():
    v = decide(SEED, WIN, ladder={"seed": 0.80, "candidate": 0.74})
    assert v.verdict == HOLD
    assert any("ladder" in f for f in v.failed)


def test_ladder_within_margin_ships():
    assert decide(SEED, WIN, ladder={"seed": 0.80, "candidate": 0.76}).verdict == SHIP


def test_no_ladder_run_holds_and_says_so():
    v = decide(SEED, WIN, ladder=None)
    assert v.verdict == HOLD
    assert any("no live ladder" in f for f in v.failed)


def test_only_items_scored_under_both_are_paired():
    cand = dict(WIN)
    del cand["paraphrase-0"]
    v = decide(SEED, cand, ladder=LADDER_OK)
    assert v.figures["recall_n"] == 34


def test_figures_are_reported():
    f = decide(SEED, WIN, ladder=LADDER_OK).figures
    assert set(f) >= {
        "seed_recall",
        "cand_recall",
        "diff",
        "diff_lo",
        "diff_hi",
        "seed_false_hint",
        "cand_false_hint",
        "seed_exact",
        "cand_exact",
    }
