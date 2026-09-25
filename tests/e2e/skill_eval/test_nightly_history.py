"""The three nights that failed, re-read through 121's comparison — T018.

Runs 34744344877 (2026-09-13), 34817991701 (2026-09-14) and 34939912456 (2026-09-15) failed in a
row. Between them they reported five regressed rows, every one of them a Δ against the baseline
file's stored lift, judged against `--regression-threshold 0.05`.

The arm rates and item counts below are transcribed from those runs' own summary tables — the
`skill / mode / scored / base / skill / lift / Δ base / outcome` block each shard printed. Nothing
is re-run: the point is what the same measurements say once the gate knows its own resolution.

Ten or twenty scored items is five or ten task-pairs, against FR-008's floor of 37. Every row is
underpowered by construction: at most one task-pair disagreed in any of them, and the three with a
defined resolution resolve nothing finer than 0.25. The other two resolve nothing at all — zero
discordance leaves `mde_paired` undefined. The old gate could not have known any of that, because
it never computed a resolution; it compared a Δ to 0.05 and went red.

Note what this file does *not* claim. `iris-vector-ai`'s Δ of -0.30 at ten pairs is larger than the
0.25 threshold the new gate would apply, and the two zero-discordance rows sit exactly on the 0.20
fallback. That makes none of them a regression — the verdict is `UNDERPOWERED` before any Δ is
weighed, so nothing is asserted either way. Writing the claim as "every Δ is inside the threshold"
would have been false, and is what the first draft of this file asserted.
"""

import pytest

from tests.e2e.skill_eval.comparison import (
    GATE_THRESHOLD,
    MINIMUM_FLOOR,
    Comparison,
    TaskPair,
    Verdict,
)
from tests.e2e.skill_eval.stats import mde_paired


class Night:
    """One regressed row, exactly as the run printed it.

    `scored` is the summary table's own column, which sums both arms — `_item_counts` in
    `reporter.py` adds `items_scored` for baseline and skill together. So a row printing 10 scored
    ran five items per arm, and five items per arm is five task-pairs. `pairs` does that division
    once, here, rather than in five assertions.
    """

    def __init__(self, run, skill, scored, base, arm, lift, delta_base):
        self.run = run
        self.skill = skill
        self.scored = scored
        self.pairs = scored // 2
        self.base = base
        self.arm = arm
        self.lift = lift
        self.delta_base = delta_base

    def __repr__(self) -> str:
        return f"{self.run}/{self.skill}"


# `scored` is both arms summed, as printed; base and arm are per-arm pass rates; `lift` is arm −
# base as the shard printed it; `delta_base` is the Δ against the stored baseline lift, which is the
# number the gate actually failed on.
NIGHTS = [
    Night("34744344877", "objectscript-guardrails", 10, 0.40, 0.40, 0.00, -0.20),
    Night("34817991701", "iris-vector-ai", 20, 0.00, 0.10, +0.10, -0.10),
    Night("34817991701", "objectscript-review", 10, 0.80, 0.60, -0.20, -0.40),
    Night("34939912456", "iris-vector-ai", 20, 0.10, 0.00, -0.10, -0.30),
    Night("34939912456", "objectscript-review", 10, 0.80, 0.80, 0.00, -0.20),
]

# The threshold those runs were gated on. FR-009 replaced it with 0.20, itself clamped up to the
# MDE — this value is here to be shown as smaller than every MDE below, not to be used.
OLD_THRESHOLD = 0.05


def pairs_for(night: Night) -> list:
    """The most favourable pairing consistent with the printed rates.

    Only the two rates and the item count survive in the logs, so the discordant split is not
    recoverable exactly. This builds the *fewest* discordant pairs the rates allow, which is the
    pairing most favourable to the old gate: fewer discordant pairs means lower discordance,
    which means the smallest floor and the tightest MDE this row could possibly have had. If the
    row is underpowered even under its best case, it was underpowered.
    """
    n = night.pairs
    base_passes = round(night.base * n)
    arm_passes = round(night.arm * n)
    b = max(0, arm_passes - base_passes)  # arm passes, base fails
    c = max(0, base_passes - arm_passes)  # base passes, arm fails
    both_pass = min(base_passes, arm_passes)
    both_fail = n - both_pass - b - c
    assert both_fail >= 0, f"{night}: rates do not fit {n} items"

    def pair(tag: str, index: int, passed_a: bool, passed_b: bool) -> TaskPair:
        return TaskPair(
            task_id=f"{night.skill}-{tag}{index}",
            arm_a="baseline",
            arm_b=night.skill,
            passed_a=passed_a,
            passed_b=passed_b,
        )

    pairs = [pair("b", i, False, True) for i in range(b)]
    pairs += [pair("c", i, True, False) for i in range(c)]
    pairs += [pair("pp", i, True, True) for i in range(both_pass)]
    pairs += [pair("ff", i, False, False) for i in range(both_fail)]
    return pairs


def comparison_for(night: Night) -> Comparison:
    return Comparison.from_pairs("baseline", night.skill, pairs_for(night))


@pytest.mark.parametrize("night", NIGHTS, ids=repr)
def test_the_pairing_reproduces_the_lift_the_run_printed(night: Night):
    """If the reconstruction does not land on the printed lift, it is not this row."""
    comparison = comparison_for(night)
    assert comparison.n_pairs == night.pairs
    assert comparison.lift == pytest.approx(night.lift, abs=0.005)


@pytest.mark.parametrize("night", NIGHTS, ids=repr)
def test_every_failed_night_is_underpowered_rather_than_a_regression(night: Night):
    """US3's first claim: these are answers of "cannot tell", not answers of "worse"."""
    comparison = comparison_for(night)
    assert comparison.n_pairs < MINIMUM_FLOOR
    assert comparison.verdict == Verdict.UNDERPOWERED, comparison.summary()
    assert not comparison.passed


@pytest.mark.parametrize("night", NIGHTS, ids=repr)
def test_the_delta_that_failed_the_gate_decides_nothing(night: Night):
    """And US3's second: the Δ each night failed on is not the number that decides now.

    Deliberately *not* "every Δ is smaller than the threshold". `iris-vector-ai`'s -0.30 at ten
    pairs is not — the threshold there is 0.25 — and the two zero-discordance rows land exactly on
    the 0.20 fallback rather than inside it. The size is beside the point: the pairs the Δ was
    computed from are too few to license any verdict, so `passed` is False and no regression is
    asserted either. The message records Δ, MDE and threshold so a reader can see the arithmetic
    rather than take the verdict on faith.

    What every row does share is how thin the evidence is: at most one discordant task-pair. A Δ of
    -0.40 that rests on a single task changing its mind is what the old 0.05 gate called a
    regression three nights running.
    """
    comparison = comparison_for(night)
    resolution = (
        "no MDE at all" if comparison.mde is None else f"mde {comparison.mde:.2f}"
    )
    detail = (
        f"{night}: Δ {night.delta_base:+.2f} over {comparison.n_pairs} pairs "
        f"({comparison.b}+{comparison.c} discordant, {resolution}, threshold "
        f"{comparison.threshold_applied:.2f})"
    )
    assert comparison.verdict == Verdict.UNDERPOWERED, detail
    assert not comparison.passed, detail
    assert comparison.b + comparison.c <= 1, detail


@pytest.mark.parametrize("night", NIGHTS, ids=repr)
def test_zero_discordance_rows_have_no_resolution_to_report(night: Night):
    """Two of the five resolve nothing at all, and that is not the same as resolving 0.00.

    `mde_paired` is undefined at zero discordance — with no task-pair disagreeing there is no
    variance to invert — so `mde` is `None` and `threshold_applied` falls back to `GATE_THRESHOLD`.
    Both such rows printed a Δ of -0.20 against the baseline, landing exactly on that fallback. The
    verdict is still underpowered, which is the only defensible reading of five task-pairs in which
    nothing disagreed.
    """
    comparison = comparison_for(night)
    if comparison.discordance == 0:
        assert comparison.mde is None
        assert comparison.threshold_applied == pytest.approx(GATE_THRESHOLD)
    else:
        assert comparison.mde is not None


def test_the_resolutions_these_rows_did_report_dwarf_the_old_threshold():
    """Why the old gate could not have worked at this corpus size.

    The three rows with a defined MDE resolve 0.25 (ten pairs, 0.10 discordance) and 0.43 (five
    pairs, 0.20 discordance) — 5× and 8.7× the 0.05 the nightly was gated on. Any Δ the old gate
    could see was a Δ the harness could not.
    """
    resolutions = sorted(
        {
            round(comparison_for(night).mde, 4)
            for night in NIGHTS
            if comparison_for(night).mde is not None
        }
    )
    assert resolutions == [
        pytest.approx(0.2482, abs=5e-4),
        pytest.approx(0.4334, abs=5e-4),
    ]
    for mde in resolutions:
        assert mde > 4 * OLD_THRESHOLD, f"{mde:.2f} against {OLD_THRESHOLD}"


@pytest.mark.parametrize("discordance", [0.10, 0.20, 0.40])
def test_more_pairs_resolve_more_at_a_fixed_discordance(discordance: float):
    """The scale claim, held apart from the rows.

    The five rows cannot carry it: the ten-pair rows also ran at half the discordance of the
    five-pair ones, so comparing their MDEs conflates count with disagreement. Hold discordance
    still and the count is what moves — which is what FR-008's floor of 37 is buying.
    """
    assert mde_paired(10, discordance) < mde_paired(5, discordance)
    assert mde_paired(MINIMUM_FLOOR, discordance) < mde_paired(10, discordance)


# --- the repeat measurement, T018's second half ------------------------------------------------
#
# Two runs of `python -m tests.e2e.skill_eval --skill objectscript-review --runs 5`, nothing changed
# between them, ~55 min and ~$0.4 each. Transcribed from the two result files' own `comparison`
# blocks (run ids below). The point is not that they agree — it is how little agreement the harness
# can currently detect.


class Repeat:
    """One of the two identical runs, as its result file recorded it."""

    skill = "objectscript-review"

    def __init__(self, run_id, base, arm, lift, pairs, b, c, mde):
        self.run_id = run_id
        self.base = base
        self.arm = arm
        self.lift = lift
        self.pairs = pairs
        self.b = b
        self.c = c
        self.mde = mde

    def __repr__(self) -> str:
        return self.run_id


REPEATS = (
    Repeat("2026-09-16T173038", 0.40, 0.20, -0.20, 5, 0, 1, 0.4334),
    Repeat("2026-09-16T181422", 0.00, 0.40, +0.40, 5, 2, 0, 0.6130),
)


@pytest.mark.parametrize("repeat", REPEATS, ids=repr)
def test_each_repeat_run_reproduces_its_recorded_comparison(repeat: Repeat):
    """Same reconstruction discipline as the nights: derive it, then check it against the file.

    `pairs_for` builds the fewest discordant pairs the two rates allow, and for both of these runs
    that lands on the discordant split the result file actually recorded — so the reconstruction
    used for the three nights is not a convenient fiction.
    """
    comparison = Comparison.from_pairs("baseline", "skill", pairs_for(repeat))
    assert comparison.n_pairs == repeat.pairs
    assert comparison.lift == pytest.approx(repeat.lift, abs=0.005)
    assert comparison.b == repeat.b
    assert comparison.c == repeat.c
    assert comparison.mde == pytest.approx(repeat.mde, abs=5e-4)


def test_two_identical_runs_land_inside_the_reported_mde():
    """US3's Independent Test, and it passes for an uncomfortable reason.

    The two lifts are -0.20 and +0.40 — opposite signs, 0.60 apart, from the same command run twice
    with nothing changed. That difference is inside the wider run's own reported MDE of 0.613, so
    the harness never claimed to be able to tell them apart, and neither run was publishable.

    Read the other way round, this is the whole case for FR-008: at five task-pairs a skill can look
    like -0.20 or +0.40 depending on the night. The old 0.05 gate would have called the first a
    regression and the second a large improvement, and it would have been reporting coin flips.
    """
    first, second = REPEATS
    spread = abs(first.lift - second.lift)
    resolution = max(first.mde, second.mde)
    assert spread == pytest.approx(0.60, abs=0.005)
    assert spread <= resolution, (
        f"lifts {first.lift:+.2f} and {second.lift:+.2f} differ by {spread:.2f}, outside the "
        f"reported resolution of {resolution:.2f} — that would mean the harness claims to resolve "
        f"a difference it cannot reproduce"
    )


def test_neither_repeat_run_was_publishable():
    """Nothing above is a lift anyone may quote. Both runs are five pairs against a floor of 37."""
    for repeat in REPEATS:
        assert repeat.pairs < MINIMUM_FLOOR
        assert repeat.mde > GATE_THRESHOLD
