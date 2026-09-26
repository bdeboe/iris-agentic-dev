"""Tests for `bootstrap.py` — 128 T013 (FR-009)."""

from __future__ import annotations

import pytest

from tests.e2e.skill_eval.optimize.bootstrap import paired_diff_ci


def test_clear_win_has_positive_lower_bound():
    seed = [0] * 30 + [1] * 10
    cand = [1] * 30 + [1] * 10
    d, lo, hi = paired_diff_ci(seed, cand)
    assert d == pytest.approx(0.75)
    assert lo > 0 and hi <= 1


def test_tie_straddles_zero():
    seed = [1, 0] * 20
    cand = [0, 1] * 20
    d, lo, hi = paired_diff_ci(seed, cand)
    assert d == 0
    assert lo < 0 < hi


def test_identical_is_degenerate_zero():
    assert paired_diff_ci([1, 0, 1], [1, 0, 1]) == (0.0, 0.0, 0.0)


def test_deterministic_under_the_fixed_seed():
    seed = [0, 1, 0, 1, 1, 0, 0, 1] * 4
    cand = [1, 1, 0, 1, 1, 1, 0, 0] * 4
    assert paired_diff_ci(seed, cand) == paired_diff_ci(seed, cand)


def test_rejects_unpaired_or_empty():
    with pytest.raises(ValueError):
        paired_diff_ci([1, 0], [1])
    with pytest.raises(ValueError):
        paired_diff_ci([], [])
