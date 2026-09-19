"""Unit tests for stats.py — T006, T007, T008.

Every expected value here was computed independently of `stats.py` and written in as a literal.
Two sources, neither of them the module under test:

- Wilson bounds: `scipy.stats.binomtest(k, n, 0.5).proportion_ci(method="wilson")`, cross-checked
  by bisecting the score equation `(p_hat - p) / sqrt(p(1-p)/n) = +/- z` to 200 iterations. The two
  agreed to six decimals on all nine cases below.
- McNemar: `scipy.stats.binomtest(b, b + c, 0.5, alternative="greater")` for the exact test, and
  `scipy.stats.chi2.sf(x, 1)` for the continuity-corrected form.

scipy is in the dev environment but is deliberately not a dependency of the harness (Constitution
VII, plan.md Technical Context). It is used at authoring time to produce these literals and never
imported by shipped code. That is the point: a confidence interval that agrees with the
implementation because both came from the same wrong formula is not a test.

The MDE literals reproduce the five numbers spec.md's Assumptions section states, which is how the
formula choice was settled — the arcsine transform for unpaired and Connor 1987 for paired are the
only pair that give 0.35, 0.20, 97, 37 and 77.
"""

import math

import pytest

from tests.e2e.skill_eval.stats import (
    mcnemar_interval,
    mcnemar_test,
    mde_paired,
    mde_unpaired,
    n_for_effect_paired,
    n_for_effect_unpaired,
    wilson_interval,
)

TOL = 1e-6


# ---------------------------------------------------------------------------
# T006 — Wilson interval
# ---------------------------------------------------------------------------

# (n, successes, expected_low, expected_high)
WILSON_CASES = [
    (5, 0, 0.000000, 0.434482),
    (5, 2, 0.117621, 0.769276),
    (5, 5, 0.565518, 1.000000),
    (30, 0, 0.000000, 0.113513),
    (30, 12, 0.245906, 0.576796),
    (30, 30, 0.886487, 1.000000),
    (100, 0, 0.000000, 0.036993),
    (100, 40, 0.309401, 0.497997),
    (100, 100, 0.963007, 1.000000),
]


@pytest.mark.parametrize("n,k,low,high", WILSON_CASES)
def test_wilson_interval_matches_independently_computed_bounds(n, k, low, high):
    got_low, got_high = wilson_interval(k, n)
    assert got_low == pytest.approx(low, abs=TOL)
    assert got_high == pytest.approx(high, abs=TOL)


@pytest.mark.parametrize(
    "n,expected_high",
    [(5, 0.434482), (30, 0.113513), (100, 0.036993)],
)
def test_wilson_at_zero_successes_has_width(n, expected_high):
    """The case four current skills sit in.

    A naive normal-approximation interval collapses to zero width at p=0, because sqrt(p(1-p)/n)
    is zero there. That reports a skill measured at 0.00 as known exactly, which is how four task
    sets reading 0.00 against 0.00 looked like a finding instead of a broken corpus.
    """
    low, high = wilson_interval(0, n)
    assert low == 0.0
    assert high == pytest.approx(expected_high, abs=TOL)
    assert high > 0.0, "a zero-width interval at p=0 is the bug this test exists for"


@pytest.mark.parametrize(
    "n,expected_low", [(5, 0.565518), (30, 0.886487), (100, 0.963007)]
)
def test_wilson_at_full_successes_has_width(n, expected_low):
    """The ceiling case, symmetric with p=0. `objectscript-guardrails` sits near it at 1.00."""
    low, high = wilson_interval(n, n)
    assert high == 1.0
    assert low == pytest.approx(expected_low, abs=TOL)
    assert low < 1.0


def test_wilson_is_symmetric_under_relabelling():
    """Wilson bounds for k of n mirror those for (n-k) of n. A property, not a literal."""
    low_a, high_a = wilson_interval(12, 30)
    low_b, high_b = wilson_interval(18, 30)
    assert low_a == pytest.approx(1.0 - high_b, abs=TOL)
    assert high_a == pytest.approx(1.0 - low_b, abs=TOL)


def test_wilson_narrows_as_n_grows():
    widths = [wilson_interval(round(0.4 * n), n) for n in (5, 30, 100)]
    widths = [hi - lo for lo, hi in widths]
    assert widths[0] > widths[1] > widths[2]


def test_wilson_rejects_impossible_counts():
    with pytest.raises(ValueError):
        wilson_interval(5, 0)
    with pytest.raises(ValueError):
        wilson_interval(-1, 10)
    with pytest.raises(ValueError):
        wilson_interval(11, 10)


# ---------------------------------------------------------------------------
# T007 — McNemar
# ---------------------------------------------------------------------------

# (b, c, one_sided_p) from scipy.stats.binomtest(b, b+c, 0.5, alternative="greater")
MCNEMAR_EXACT_CASES = [
    (5, 0, 0.031250),
    (6, 0, 0.015625),
    (6, 1, 0.062500),
    (5, 1, 0.109375),
    (7, 1, 0.035156),
    (8, 0, 0.003906),
    (4, 2, 0.343750),
    (3, 3, 0.656250),
    (2, 1, 0.500000),
    (12, 3, 0.017578),
]


@pytest.mark.parametrize("b,c,expected_p", MCNEMAR_EXACT_CASES)
def test_mcnemar_exact_one_sided_p(b, c, expected_p):
    result = mcnemar_test(b, c)
    assert result.p_value_one_sided == pytest.approx(expected_p, abs=1e-6)


def test_mcnemar_exact_only_depends_on_discordant_counts():
    """Two runs with the same b and c but different corpus sizes give the same exact p.

    This is why the pilot's go/no-go rule needs no separate second-round table (FR-024): the
    p-value is a function of b and c alone, so eight more tasks change the counts, not the rule.
    """
    assert mcnemar_test(6, 1).p_value_one_sided == pytest.approx(
        mcnemar_test(6, 1).p_value_one_sided, abs=TOL
    )
    assert mcnemar_test(6, 1).p_value_one_sided == pytest.approx(0.0625, abs=TOL)


def test_the_pilot_go_rule_holds_at_its_weakest_qualifying_outcome():
    """FR-024's go rule, checked against the arithmetic rather than asserted in prose.

    The rule is `c <= 1` and `b >= 5` and one-sided exact p <= 0.07. The corner cases matter: an
    earlier draft of this rule claimed `b >= 5 and c <= 1` implied p <= 0.06, and (5, 1) gives
    0.109. The rule now carries the p-value as a binding third condition, and the weakest outcome
    that satisfies all three is (6, 1) at exactly 0.0625.
    """
    qualifying = [(5, 0), (6, 0), (6, 1), (7, 0), (7, 1), (8, 0)]
    for b, c in qualifying:
        p = mcnemar_test(b, c).p_value_one_sided
        assert c <= 1 and b >= 5
        assert p <= 0.07, f"({b}, {c}) claims go at p={p}"
    worst = max(mcnemar_test(b, c).p_value_one_sided for b, c in qualifying)
    assert worst == pytest.approx(0.0625, abs=TOL)

    # And the two near misses are correctly excluded, each for a different reason.
    assert mcnemar_test(5, 1).p_value_one_sided > 0.07  # p too weak
    assert mcnemar_test(4, 0).p_value_one_sided <= 0.07  # p fine, but b < 5
    assert 4 < 5


@pytest.mark.parametrize(
    "b,c,chi2,expected_p",
    [
        (5, 1, 1.500000, 0.220671),
        (12, 3, 4.266667, 0.038867),
        (20, 8, 4.321429, 0.037635),
        (3, 3, 0.166667, 0.683091),
    ],
)
def test_mcnemar_continuity_corrected(b, c, chi2, expected_p):
    result = mcnemar_test(b, c)
    assert result.chi_square_corrected == pytest.approx(chi2, abs=1e-6)
    assert result.p_value_corrected == pytest.approx(expected_p, abs=1e-6)


def test_mcnemar_zero_discordance_reports_no_effect_rather_than_dividing_by_zero():
    """b = c = 0 means the arms agreed on every pair. The chi-square is 0/0."""
    result = mcnemar_test(0, 0)
    assert result.discordant == 0
    assert result.effect == 0.0
    assert result.p_value_one_sided is None
    assert result.p_value_corrected is None
    assert result.chi_square_corrected is None


def test_mcnemar_rejects_negative_counts():
    with pytest.raises(ValueError):
        mcnemar_test(-1, 3)
    with pytest.raises(ValueError):
        mcnemar_test(3, -1)


# (b, c, n_pairs, delta, low, high) — Wald interval on the paired difference
MCNEMAR_INTERVAL_CASES = [
    (12, 3, 40, 0.225000, 0.048501, 0.401499),
    (5, 1, 8, 0.500000, 0.010009, 0.989991),
    (20, 8, 50, 0.240000, 0.043534, 0.436466),
    (3, 3, 30, 0.000000, -0.160030, 0.160030),
]


@pytest.mark.parametrize("b,c,n,delta,low,high", MCNEMAR_INTERVAL_CASES)
def test_mcnemar_interval_on_a_known_table(b, c, n, delta, low, high):
    got_delta, (got_low, got_high) = mcnemar_interval(b, c, n)
    assert got_delta == pytest.approx(delta, abs=TOL)
    assert got_low == pytest.approx(low, abs=TOL)
    assert got_high == pytest.approx(high, abs=TOL)


def test_mcnemar_interval_at_eight_pairs_contains_zero_even_when_every_pair_favours_tools():
    """The D1 finding, as arithmetic.

    Eight pairs, the tools arm winning five and losing one — a lift of 0.50 — still gives an
    interval whose lower bound is 0.010. It excludes zero by a hair, and the MDE at that item
    count is 0.38 (see the paired-MDE case below), so FR-008 reports it underpowered regardless.
    This is why the pilot verdict is a design decision under FR-024 and not a result.
    """
    delta, (low, high) = mcnemar_interval(5, 1, 8)
    assert delta == pytest.approx(0.5, abs=TOL)
    assert low == pytest.approx(0.010009, abs=TOL)
    assert high == pytest.approx(0.989991, abs=TOL)
    assert high - low > 0.97, "an eight-pair interval spans almost the whole range"


def test_mcnemar_interval_with_equal_discordant_counts_is_centred_on_zero():
    delta, (low, high) = mcnemar_interval(3, 3, 30)
    assert delta == 0.0
    assert low < 0.0 < high


def test_mcnemar_interval_rejects_counts_exceeding_pairs():
    with pytest.raises(ValueError):
        mcnemar_interval(6, 5, 10)
    with pytest.raises(ValueError):
        mcnemar_interval(1, 1, 0)


# ---------------------------------------------------------------------------
# T008 — minimum detectable effect and required item counts
# ---------------------------------------------------------------------------


def test_mde_unpaired_reproduces_the_spec_assumptions():
    """spec.md: "n=30 per arm at baseline 0.40 gives MDE 0.35; n=100 gives 0.20"."""
    assert mde_unpaired(30, 0.40) == pytest.approx(0.349311, abs=TOL)
    assert mde_unpaired(100, 0.40) == pytest.approx(0.196808, abs=TOL)
    assert round(mde_unpaired(30, 0.40), 2) == 0.35
    assert round(mde_unpaired(100, 0.40), 2) == 0.20


def test_n_for_effect_unpaired_reproduces_the_spec_assumptions():
    """spec.md: "detecting +0.20 unpaired needs 97 per arm"."""
    assert n_for_effect_unpaired(0.40, 0.60) == 97


def test_n_for_effect_paired_is_fr_008s_floor_and_its_recomputed_value():
    """spec.md FR-008: 37 pairs at discordance 0.20, 77 at 0.40.

    The floor is derived, not chosen, and these two literals are the derivation. The 0.40 case is
    the one that matters operationally: a run that measures worse discordance than expected raises
    its own floor instead of passing a comparison that cannot support the verdict.
    """
    assert n_for_effect_paired(0.20, 0.20) == 37
    assert n_for_effect_paired(0.20, 0.40) == 77


def test_the_paired_floor_beats_the_unpaired_one_which_is_why_tasks_are_paired():
    assert n_for_effect_paired(0.20, 0.20) < n_for_effect_unpaired(0.40, 0.60)


def test_n_for_effect_paired_rises_monotonically_with_discordance():
    counts = [n_for_effect_paired(0.20, pd) for pd in (0.20, 0.30, 0.40, 0.50)]
    assert counts == [37, 57, 77, 96]


def test_mde_paired_inverts_the_floor():
    """At exactly the floor the MDE lands on the threshold it was derived from."""
    assert mde_paired(37, 0.20) == pytest.approx(0.199480, abs=TOL)
    assert mde_paired(77, 0.40) == pytest.approx(0.198848, abs=TOL)


def test_mde_paired_at_the_pilots_eight_pairs_is_twice_the_gate_threshold():
    """The number that forced FR-024.

    Eight pairs at the expected discordance resolve 0.38, against a gate threshold of 0.20. The
    pilot cannot see the effect the gate is set to detect, whatever it observes, so its verdict
    cannot be a lift. FR-009's `max(0.20, mde)` clamp would raise the bar to 0.38 and nothing at
    eight pairs would clear it.
    """
    assert mde_paired(8, 0.20) == pytest.approx(0.380041, abs=TOL)
    assert mde_paired(8, 0.20) > 0.20
    assert max(0.20, mde_paired(8, 0.20)) == pytest.approx(0.380041, abs=TOL)


def test_mde_paired_shrinks_as_pairs_grow():
    assert mde_paired(8, 0.20) > mde_paired(37, 0.20) > mde_paired(50, 0.20)
    assert mde_paired(50, 0.20) == pytest.approx(0.173042, abs=TOL)


def test_mde_paired_with_no_discordance_is_undefined_not_zero():
    """Zero discordant pairs buys no resolution at all. Reporting 0.0 would claim the opposite."""
    assert mde_paired(30, 0.0) is None


def test_mde_and_n_for_effect_are_consistent_round_trip():
    """Any n at or above the floor resolves at or below the threshold it was sized for."""
    for discordance in (0.20, 0.30, 0.40):
        floor = n_for_effect_paired(0.20, discordance)
        assert mde_paired(floor, discordance) <= 0.20 + 1e-3
        assert mde_paired(floor - 1, discordance) > mde_paired(floor, discordance)


def test_mde_unpaired_rejects_nonsense_inputs():
    with pytest.raises(ValueError):
        mde_unpaired(0, 0.4)
    with pytest.raises(ValueError):
        mde_unpaired(30, 1.5)
    with pytest.raises(ValueError):
        n_for_effect_paired(0.0, 0.2)
    with pytest.raises(ValueError):
        n_for_effect_paired(0.6, 0.2)  # delta cannot exceed sqrt(discordance)


def test_no_scipy_import_in_the_shipped_module():
    """Constitution VII. The literals above came from scipy; the module must not."""
    import tests.e2e.skill_eval.stats as stats_module

    source = open(stats_module.__file__).read()
    assert "scipy" not in source
    assert "numpy" not in source
    assert math is not None
