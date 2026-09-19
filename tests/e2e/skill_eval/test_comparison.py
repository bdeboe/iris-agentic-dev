"""Unit tests for comparison.py — T010.

`Comparison` is where the `unpowered-result` bug class is fixed, and the guarantees are numbered
G1–G7 in contracts/comparison.md. The shipped instance was `lift.py:76`, two point estimates
subtracted with no item count beside them. Every case here is one of the ways that number could be
produced again.

The statistics themselves are tested in test_stats.py against independently computed literals.
These tests are about what a `Comparison` refuses to do.
"""

import pytest

from dataclasses import replace

from tests.e2e.skill_eval.comparison import (
    GATE_THRESHOLD,
    Comparison,
    TaskPair,
    Verdict,
    assert_publishable_from_holdout,
    pair_arms,
)
from tests.e2e.skill_eval.split import Split, SplitLeak, default_split


def pairs(b: int, c: int, both_pass: int = 0, both_fail: int = 0) -> list[TaskPair]:
    """Build a pair list with the requested 2x2 cell counts."""
    out = []
    n = 0
    for _ in range(b):
        out.append(TaskPair(f"t{n}", "bare", "tools", passed_a=False, passed_b=True))
        n += 1
    for _ in range(c):
        out.append(TaskPair(f"t{n}", "bare", "tools", passed_a=True, passed_b=False))
        n += 1
    for _ in range(both_pass):
        out.append(TaskPair(f"t{n}", "bare", "tools", passed_a=True, passed_b=True))
        n += 1
    for _ in range(both_fail):
        out.append(TaskPair(f"t{n}", "bare", "tools", passed_a=False, passed_b=False))
        n += 1
    return out


def build(b, c, both_pass=0, both_fail=0, **kwargs) -> Comparison:
    return Comparison.from_pairs(
        arm_a="bare",
        arm_b="tools",
        pairs=pairs(b, c, both_pass, both_fail),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# G1 — a lift never travels alone
# ---------------------------------------------------------------------------


def test_a_comparison_always_carries_an_item_count_and_an_mde():
    """Governance detector 1, as a type rather than a scanner."""
    comparison = build(b=12, c=3, both_pass=15, both_fail=10)
    assert comparison.n_pairs == 40
    assert comparison.mde is not None
    assert comparison.mde > 0.0


def test_constructing_a_comparison_without_an_item_count_raises():
    with pytest.raises((TypeError, ValueError)):
        Comparison(arm_a="bare", arm_b="tools", lift=0.25)  # type: ignore[call-arg]


def test_a_comparison_over_no_pairs_raises_rather_than_reporting_zero():
    """Zero pairs is not a lift of 0.00. It is the absence of a measurement."""
    with pytest.raises(ValueError):
        Comparison.from_pairs(arm_a="bare", arm_b="tools", pairs=[])


def test_the_formatted_summary_names_the_item_count_and_the_mde():
    """Whatever prints a lift has both to hand without asking."""
    text = build(b=12, c=3, both_pass=15, both_fail=10).summary()
    assert "40" in text
    assert "mde" in text.lower()


# ---------------------------------------------------------------------------
# G2 — below the floor, underpowered and never passed
# ---------------------------------------------------------------------------


def test_a_comparison_below_the_floor_reports_underpowered():
    """FR-008. Eight pairs cannot clear a floor of 37."""
    comparison = build(b=5, c=1, both_fail=2)
    assert comparison.n_pairs == 8
    assert comparison.verdict == Verdict.UNDERPOWERED
    assert comparison.verdict != Verdict.PASSED


def test_an_underpowered_comparison_is_not_a_pass_even_with_a_huge_lift():
    """The lift is 0.50 and the interval excludes zero. It is still underpowered."""
    comparison = build(b=5, c=1, both_fail=2)
    assert comparison.lift == pytest.approx(0.5)
    assert comparison.interval[0] > 0.0
    assert comparison.verdict == Verdict.UNDERPOWERED
    assert not comparison.passed


def test_the_declared_floor_is_37_pairs_at_the_expected_discordance():
    comparison = build(b=4, c=4, both_pass=20, both_fail=12)  # discordance 0.20
    assert comparison.discordance == pytest.approx(0.20)
    assert comparison.floor == 37


def test_a_comparison_at_the_floor_is_not_underpowered():
    # 37 pairs, discordance 0.20 by construction: 6 + 1 discordant of 37 is 0.189, so pad to 0.20.
    comparison = build(
        b=6, c=2, both_pass=20, both_fail=12
    )  # 40 pairs, discordance 0.20
    assert comparison.n_pairs == 40
    assert comparison.floor == 37
    assert comparison.verdict != Verdict.UNDERPOWERED


# ---------------------------------------------------------------------------
# G3 — the floor is recomputed from measured discordance
# ---------------------------------------------------------------------------


def test_a_run_measuring_discordance_of_040_recomputes_the_floor_to_77():
    """FR-008's recomputation. 40 pairs would clear a floor of 37 and does not clear 77."""
    comparison = build(b=10, c=6, both_pass=14, both_fail=10)  # 40 pairs, 16 discordant
    assert comparison.discordance == pytest.approx(0.40)
    assert comparison.floor == 77
    assert comparison.verdict == Verdict.UNDERPOWERED


def test_the_recomputed_floor_is_reported_not_just_applied():
    comparison = build(b=10, c=6, both_pass=14, both_fail=10)
    assert "77" in comparison.summary()


def test_better_than_expected_discordance_never_lowers_the_floor_below_37():
    """One-way by design. A lucky run does not get to shrink its own bar."""
    comparison = build(b=2, c=0, both_pass=20, both_fail=18)  # discordance 0.05
    assert comparison.discordance == pytest.approx(0.05)
    assert comparison.floor == 37


# ---------------------------------------------------------------------------
# G4 — an interval containing zero is indistinguishable
# ---------------------------------------------------------------------------


def test_a_lift_whose_interval_contains_zero_reports_indistinguishable():
    """FR-010, and the fix for three consecutive nightly failures inside their own noise."""
    comparison = build(
        b=9, c=7, both_pass=20, both_fail=44
    )  # 80 pairs, discordance 0.20
    assert comparison.n_pairs == 80
    assert comparison.floor == 37
    assert comparison.interval[0] < 0.0 < comparison.interval[1]
    assert comparison.verdict == Verdict.INDISTINGUISHABLE
    assert not comparison.passed


def test_a_flat_comparison_is_indistinguishable_not_a_regression():
    comparison = build(b=8, c=8, both_pass=20, both_fail=44)
    assert comparison.lift == pytest.approx(0.0)
    assert comparison.verdict == Verdict.INDISTINGUISHABLE


def test_a_powered_positive_result_passes():
    comparison = build(b=30, c=2, both_pass=30, both_fail=38)  # 100 pairs, lift 0.28
    assert comparison.n_pairs == 100
    assert comparison.lift == pytest.approx(0.28)
    assert comparison.interval[0] > 0.0
    assert comparison.verdict == Verdict.PASSED
    assert comparison.passed


def test_a_powered_negative_result_regresses():
    comparison = build(b=2, c=30, both_pass=30, both_fail=38)
    assert comparison.lift == pytest.approx(-0.28)
    assert comparison.verdict == Verdict.REGRESSED
    assert not comparison.passed


# ---------------------------------------------------------------------------
# G5 — the threshold is max(0.20, mde)
# ---------------------------------------------------------------------------


def test_the_declared_gate_threshold_is_020_matching_constitution_ix():
    assert GATE_THRESHOLD == 0.20


def test_the_threshold_is_clamped_up_to_the_mde_when_the_mde_is_larger():
    """FR-009. A threshold below the instrument's resolution is not a threshold."""
    comparison = build(b=5, c=1, both_fail=2)  # 8 pairs, mde ~0.60
    assert comparison.mde > GATE_THRESHOLD
    assert comparison.threshold_applied == pytest.approx(comparison.mde)


def test_the_threshold_stays_at_020_when_the_mde_is_smaller():
    comparison = build(b=30, c=2, both_pass=30, both_fail=38)
    assert comparison.mde < GATE_THRESHOLD
    assert comparison.threshold_applied == pytest.approx(GATE_THRESHOLD)


def test_a_lift_above_zero_but_below_the_threshold_does_not_pass():
    # 200 pairs, discordance 0.20: 24 vs 16 gives lift 0.04, powered, interval may exclude zero.
    comparison = build(b=24, c=16, both_pass=60, both_fail=100)
    assert comparison.n_pairs == 200
    assert comparison.lift == pytest.approx(0.04)
    assert comparison.lift < comparison.threshold_applied
    assert comparison.verdict != Verdict.PASSED


def test_the_old_005_threshold_is_gone():
    """The 0.05 that produced the three failing nightly runs sat below the harness's resolution."""
    assert GATE_THRESHOLD != 0.05
    import tests.e2e.skill_eval.comparison as module

    assert "0.05" not in open(module.__file__).read().replace("alpha=0.05", "")


# ---------------------------------------------------------------------------
# G6 — dropped tasks are named
# ---------------------------------------------------------------------------


def test_a_task_missing_from_one_arm_becomes_a_named_hole():
    """An arm that crashed on ten tasks must not look like an arm that passed on the rest."""
    arm_a = {"t1": True, "t2": False, "t3": True}
    arm_b = {"t1": True, "t2": True}
    comparison = pair_arms("bare", "tools", arm_a, arm_b)
    assert comparison.n_pairs == 2
    assert len(comparison.holes) == 1
    assert "t3" in comparison.holes[0]
    assert "tools" in comparison.holes[0]


def test_holes_are_reported_in_the_summary():
    comparison = pair_arms("bare", "tools", {"t1": True, "t2": False}, {"t1": True})
    assert "t2" in comparison.summary()


def test_pairing_keys_on_task_id_not_on_position():
    arm_a = {"t1": False, "t2": False}
    arm_b = {"t2": True, "t1": False}
    comparison = pair_arms("bare", "tools", arm_a, arm_b)
    assert comparison.b == 1
    assert comparison.c == 0
    by_id = {p.task_id: p for p in comparison.pairs}
    assert by_id["t2"].passed_b is True
    assert by_id["t1"].passed_b is False


def test_an_arm_with_no_overlapping_tasks_raises_rather_than_reporting_nothing():
    with pytest.raises(ValueError):
        pair_arms("bare", "tools", {"t1": True}, {"t2": True})


# ---------------------------------------------------------------------------
# G7 — the design-decision carve-out
# ---------------------------------------------------------------------------


def test_a_design_decision_at_eight_pairs_is_not_underpowered():
    """FR-024. The pilot is exempt from the floor and the interval rule."""
    comparison = build(b=6, c=1, both_fail=1, purpose="design_decision")
    assert comparison.n_pairs == 8
    assert comparison.verdict != Verdict.UNDERPOWERED
    assert comparison.purpose == "design_decision"


def test_a_design_decision_carries_its_counts_and_its_exact_p_value():
    comparison = build(b=6, c=1, both_fail=1, purpose="design_decision")
    assert comparison.b == 6
    assert comparison.c == 1
    assert comparison.p_value == pytest.approx(0.0625, abs=1e-6)


def test_a_design_decision_cannot_be_published():
    comparison = build(b=6, c=1, both_fail=1, purpose="design_decision")
    assert not comparison.publishable
    with pytest.raises(ValueError, match="design decision"):
        comparison.assert_publishable()


def test_a_result_purpose_comparison_is_publishable_when_powered():
    comparison = build(b=30, c=2, both_pass=30, both_fail=38)
    assert comparison.publishable
    comparison.assert_publishable()


def test_an_underpowered_result_is_not_publishable():
    comparison = build(b=5, c=1, both_fail=2)
    assert not comparison.publishable


def test_the_pilot_go_rule_reads_off_a_design_decision_comparison():
    """The rule from plan.md's table, applied to the object that carries the counts."""
    go = build(b=6, c=1, both_fail=1, purpose="design_decision")
    assert go.c <= 1 and go.b >= 5 and go.p_value <= 0.07
    assert go.pilot_verdict == "go"

    stop = build(b=2, c=4, both_fail=2, purpose="design_decision")
    assert stop.b <= stop.c
    assert stop.pilot_verdict == "stop"

    near_miss = build(b=5, c=1, both_fail=2, purpose="design_decision")
    assert near_miss.p_value > 0.07
    assert near_miss.pilot_verdict == "inconclusive"

    thin = build(b=4, c=0, both_fail=4, purpose="design_decision")
    assert thin.p_value <= 0.07
    assert thin.pilot_verdict == "inconclusive"


def test_pilot_verdict_is_unavailable_on_a_result_purpose_comparison():
    """The go/no-go rule is a design decision. Reading it off a published figure is a category error."""
    with pytest.raises(ValueError):
        _ = build(b=6, c=1, both_fail=1).pilot_verdict


def test_an_unknown_purpose_raises():
    with pytest.raises(ValueError):
        build(b=6, c=1, purpose="whatever")


# ---------------------------------------------------------------------------
# Zero-discordance and unmeasured arms
# ---------------------------------------------------------------------------


def test_two_arms_that_agreed_on_everything_are_indistinguishable_not_passed():
    comparison = build(b=0, c=0, both_pass=20, both_fail=20)
    assert comparison.discordance == 0.0
    assert comparison.lift == pytest.approx(0.0)
    assert comparison.verdict == Verdict.INDISTINGUISHABLE


def test_zero_discordance_reports_no_mde_rather_than_a_perfect_one():
    """Resolution comes from disagreement. Zero discordance bought none."""
    comparison = build(b=0, c=0, both_pass=20, both_fail=20)
    assert comparison.mde is None
    assert comparison.verdict != Verdict.PASSED
    assert not comparison.publishable


# ---------------------------------------------------------------------------
# to_dict — one shape, read by the result JSON and by the reporter
# ---------------------------------------------------------------------------


def test_to_dict_carries_the_item_count_and_the_mde():
    """G1 survives serialization. A consumer reading the JSON has both without asking."""
    data = build(b=6, c=2, both_pass=20, both_fail=12).to_dict()
    assert data["n_pairs"] == 40
    assert data["mde"] is not None and data["mde"] > 0.0
    assert data["floor"] == 37
    assert data["b"] == 6 and data["c"] == 2


def test_to_dict_marks_an_underpowered_comparison_as_underpowered():
    data = build(b=5, c=1, both_fail=2).to_dict()
    assert data["verdict"] == "underpowered"
    assert data["underpowered"] is True
    assert data["publishable"] is False


def test_to_dict_reports_no_mde_at_zero_discordance_rather_than_zero():
    data = build(b=0, c=0, both_pass=20, both_fail=20).to_dict()
    assert data["mde"] is None
    assert data["verdict"] == "indistinguishable"


def test_to_dict_is_json_serialisable():
    """It goes into `skill-eval-<run>.json`, which `shard.py` merges and the report reads."""
    import json

    data = build(b=12, c=3, both_pass=15, both_fail=10).to_dict()
    round_tripped = json.loads(json.dumps(data))
    assert round_tripped["n_pairs"] == 40
    assert round_tripped["interval"][0] < round_tripped["interval"][1]


def test_to_dict_names_its_holes():
    comparison = pair_arms("bare", "tools", {"t1": True, "t2": False}, {"t1": True})
    assert any("t2" in hole for hole in comparison.to_dict()["holes"])


# ---------------------------------------------------------------------------
# T033 — the publish path refuses a figure computed over a train-split task
# ---------------------------------------------------------------------------

#: A powered, publishable cell mix at 41 pairs: 8 discordant is a discordance of 0.195, whose floor
#: is 36, so the item count clears it with room. Anything close to fully discordant drives the floor
#: past 190 and every case below would refuse as underpowered before reaching the split at all.
_DISCORDANT_FOR_B = 7
_DISCORDANT_FOR_A = 1


def mixed_pairs(task_ids):
    """Pairs over the given IDs with a cell mix that publishes, so the split is what decides."""
    out = []
    for index, task_id in enumerate(task_ids):
        if index < _DISCORDANT_FOR_B:
            passed_a, passed_b = False, True
        elif index < _DISCORDANT_FOR_B + _DISCORDANT_FOR_A:
            passed_a, passed_b = True, False
        else:
            passed_a, passed_b = True, True
        out.append(TaskPair(task_id, "bare", "tools", passed_a, passed_b))
    return out


def holdout_ids(n):
    ids = list(default_split().holdout)
    assert len(ids) >= n, f"the committed holdout has {len(ids)} tasks, this test wants {n}"
    return ids[:n]


def test_a_figure_over_holdout_tasks_only_publishes():
    """The whole point of the split is that this path stays open. A guard that refuses everything
    would be satisfied by deleting the report."""
    comparison = Comparison.from_pairs("bare", "tools", mixed_pairs(holdout_ids(41)))
    assert comparison.publishable
    assert assert_publishable_from_holdout(comparison) is comparison


def test_a_figure_containing_one_train_task_refuses_and_names_it():
    leaked = default_split().train[0]
    comparison = Comparison.from_pairs(
        "bare", "tools", mixed_pairs(holdout_ids(40) + [leaked])
    )
    assert comparison.publishable, "the measurement itself is fine; the split is the objection"
    with pytest.raises(SplitLeak) as caught:
        assert_publishable_from_holdout(comparison)
    assert leaked in str(caught.value)


def test_a_figure_over_ids_the_split_has_never_heard_of_refuses():
    """Not a leak by the letter, and worse: nothing vouches for the task at all."""
    comparison = Comparison.from_pairs(
        "bare", "tools", mixed_pairs([f"t{n}" for n in range(41)])
    )
    with pytest.raises(SplitLeak) as caught:
        assert_publishable_from_holdout(comparison)
    assert "neither side" in str(caught.value)


def test_the_holdout_guard_runs_after_the_power_check_not_instead_of_it():
    """An underpowered figure is refused on its own terms even when every task is holdout, so a
    clean split cannot be mistaken for a publishable number."""
    comparison = Comparison.from_pairs("bare", "tools", mixed_pairs(holdout_ids(10)))
    with pytest.raises(ValueError) as caught:
        assert_publishable_from_holdout(comparison)
    assert not isinstance(caught.value, SplitLeak)
    assert "underpowered" in str(caught.value)


def test_a_figure_that_recorded_no_pairs_refuses_rather_than_passing_vacuously():
    """`assert_holdout_only` over an empty ID list is silent, so the guard has to refuse the empty
    case itself. A `Comparison` rebuilt from `to_dict` has no pairs, and reporting a lift from one is
    exactly the case where nobody can say which tasks it came from."""
    powered = Comparison.from_pairs("bare", "tools", mixed_pairs(holdout_ids(41)))
    stripped = replace(powered, pairs=())
    with pytest.raises(SplitLeak) as caught:
        assert_publishable_from_holdout(stripped)
    assert "records no task IDs" in str(caught.value)


def test_the_guard_accepts_an_explicit_split_for_a_corpus_that_is_not_the_committed_one():
    """The nightly canary and the skills ladder run over their own ID sets, and neither should have
    to be in the committed corpus file to be checked against a split."""
    ids = [f"t{n}" for n in range(41)]
    own = Split(train=("t99",), holdout=tuple(ids))
    comparison = Comparison.from_pairs("bare", "tools", mixed_pairs(ids))
    assert assert_publishable_from_holdout(comparison, split=own) is comparison
