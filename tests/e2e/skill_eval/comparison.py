"""Two arms over the same tasks, and what that comparison is allowed to claim — T011.

This module exists because of one line. `lift.py:76` computed a lift as
`skill.pass_rate - baseline.pass_rate`: two point estimates subtracted, with no item count and no
resolution beside them, and the result printed as a finding. Three consecutive nightly runs failed
on differences smaller than the harness could see, and four skills reported 0.00 against 0.00 as
though that were a measurement.

A `Comparison` is the fix, and the shape of the type is the enforcement. There is no constructor
that takes a lift on its own: `n_pairs` and the minimum detectable effect are required fields, so
anything holding a lift necessarily holds what it took to measure it. The seven guarantees are
numbered G1-G7 in contracts/comparison.md and tested one apiece in test_comparison.py.

The arithmetic all lives in stats.py. Nothing here computes an interval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from tests.e2e.skill_eval.split import (
    Split,
    SplitLeak,
    assert_holdout_only,
    default_split,
)
from tests.e2e.skill_eval.stats import (
    mcnemar_interval,
    mcnemar_test,
    mde_paired,
    n_for_effect_paired,
)

__all__ = [
    "GATE_THRESHOLD",
    "MINIMUM_FLOOR",
    "Comparison",
    "TaskPair",
    "Verdict",
    "assert_publishable_from_holdout",
    "pair_arms",
]

#: The declared gate threshold, matching Constitution IX's requirement for a new tool (FR-009).
#: The effective threshold is never below this and rises to the MDE when the MDE is larger. The
#: previous threshold sat far below the harness's own resolution, which is why the nightly kept
#: failing on noise, and it is deleted rather than lowered.
GATE_THRESHOLD = 0.20

#: FR-008's declared item floor: the smallest paired item count whose MDE reaches GATE_THRESHOLD at
#: the discordance rate spec.md's Assumptions section expects. Derived, not chosen — see
#: test_stats.py, which pins it to `n_for_effect_paired(0.20, 0.20)`.
MINIMUM_FLOOR = 37

_PURPOSES = ("result", "design_decision")

#: FR-024's go rule for the pilot. The p-value is a binding condition, not a description of the
#: counts: (5, 1) satisfies both count conditions and gives 0.109.
_PILOT_MAX_P = 0.07
_PILOT_MIN_B = 5
_PILOT_MAX_C = 1


class Verdict(str, Enum):
    """What a comparison is entitled to say.

    `PASSED` is unreachable from an underpowered comparison, which is the point of having a closed
    set rather than a boolean.
    """

    UNDERPOWERED = "underpowered"
    INDISTINGUISHABLE = "indistinguishable"
    BELOW_THRESHOLD = "below_threshold"
    PASSED = "passed"
    REGRESSED = "regressed"
    NOT_COMPARABLE = "not_comparable"


@dataclass(frozen=True)
class TaskPair:
    """One task, run in two arms. The unit McNemar counts over."""

    task_id: str
    arm_a: str
    arm_b: str
    passed_a: bool
    passed_b: bool

    @property
    def is_discordant(self) -> bool:
        return self.passed_a != self.passed_b

    @property
    def favours_b(self) -> bool:
        """A `b` cell: the upper arm passed where the lower failed."""
        return self.passed_b and not self.passed_a

    @property
    def favours_a(self) -> bool:
        """A `c` cell: the lower arm passed where the upper failed."""
        return self.passed_a and not self.passed_b


@dataclass(frozen=True)
class Comparison:
    """Two adjacent arms over a set of paired tasks.

    Build one with `from_pairs` or `pair_arms` rather than calling the constructor directly. The
    constructor's required fields are the guarantee — there is no way to get an object holding a
    lift without also holding `n_pairs` and `mde` — but computing them by hand invites the two
    getting out of step.
    """

    arm_a: str
    arm_b: str
    n_pairs: int
    b: int
    c: int
    discordance: float
    lift: float | None
    interval: tuple[float, float] | None
    p_value: float | None
    mde: float | None
    floor: int
    threshold_applied: float
    verdict: Verdict
    purpose: str = "result"
    pairs: tuple[TaskPair, ...] = ()
    holes: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default=())

    # -- construction --------------------------------------------------------

    @classmethod
    def from_pairs(
        cls,
        arm_a: str,
        arm_b: str,
        pairs: list[TaskPair],
        purpose: str = "result",
        holes: list[str] | None = None,
    ) -> Comparison:
        """Derive every field from the pair list. The only supported way in."""
        if purpose not in _PURPOSES:
            raise ValueError(f"purpose must be one of {_PURPOSES}, got {purpose!r}")
        if not pairs:
            raise ValueError(
                "a comparison needs at least one complete pair; zero pairs is the absence of a "
                "measurement, not a lift of 0.00"
            )

        n_pairs = len(pairs)
        b = sum(1 for p in pairs if p.favours_b)
        c = sum(1 for p in pairs if p.favours_a)
        discordance = (b + c) / n_pairs

        lift, interval = mcnemar_interval(b, c, n_pairs)
        test = mcnemar_test(b, c)
        mde = mde_paired(n_pairs, discordance)
        floor = cls._floor_for(discordance)
        threshold = max(GATE_THRESHOLD, mde) if mde is not None else GATE_THRESHOLD

        verdict = cls._verdict_for(
            purpose=purpose,
            n_pairs=n_pairs,
            floor=floor,
            lift=lift,
            interval=interval,
            mde=mde,
            threshold=threshold,
        )

        return cls(
            arm_a=arm_a,
            arm_b=arm_b,
            n_pairs=n_pairs,
            b=b,
            c=c,
            discordance=discordance,
            lift=lift,
            interval=interval,
            p_value=test.p_value_one_sided,
            mde=mde,
            floor=floor,
            threshold_applied=threshold,
            verdict=verdict,
            purpose=purpose,
            pairs=tuple(pairs),
            holes=tuple(holes or ()),
        )

    @staticmethod
    def _floor_for(discordance: float) -> int:
        """FR-008's floor, recomputed from measured discordance.

        One-way: worse-than-expected discordance raises the floor, better-than-expected never
        lowers it below `MINIMUM_FLOOR`. A run whose arms happened to agree does not get to shrink
        its own bar, because the agreement is a property of this sample rather than of the corpus.
        """
        if discordance <= 0.0:
            return MINIMUM_FLOOR
        try:
            required = n_for_effect_paired(GATE_THRESHOLD, discordance)
        except ValueError:
            # The gate's effect exceeds what this discordance rate can express at all. Nothing at
            # any item count clears it, and the MDE clamp on the threshold is what enforces that.
            return MINIMUM_FLOOR
        return max(MINIMUM_FLOOR, required)

    @staticmethod
    def _verdict_for(
        *,
        purpose: str,
        n_pairs: int,
        floor: int,
        lift: float | None,
        interval: tuple[float, float] | None,
        mde: float | None,
        threshold: float,
    ) -> Verdict:
        """Precedence, highest first. Order is the contract, not an implementation detail."""
        if lift is None or interval is None:
            return Verdict.NOT_COMPARABLE

        # G2 / G7. A design decision is exempt from the floor: it is not a reported figure, and
        # FR-024 requires it to state the counts it rests on instead.
        if purpose == "result" and n_pairs < floor:
            return Verdict.UNDERPOWERED

        # G4. The boundary counts as containing zero: a zero-width interval at zero discordance
        # has shown no difference and no evidence about one.
        low, high = interval
        if purpose == "result" and low <= 0.0 <= high:
            return Verdict.INDISTINGUISHABLE

        if lift < 0.0:
            return Verdict.REGRESSED
        if lift >= threshold:
            return Verdict.PASSED
        return Verdict.BELOW_THRESHOLD

    # -- reading -------------------------------------------------------------

    @property
    def passed(self) -> bool:
        return self.verdict == Verdict.PASSED

    @property
    def publishable(self) -> bool:
        """FR-021. A design decision is never published, and neither is an unresolved comparison."""
        if self.purpose != "result":
            return False
        if self.mde is None:
            return False
        return self.verdict not in (Verdict.UNDERPOWERED, Verdict.NOT_COMPARABLE)

    def assert_publishable(self) -> None:
        """Raise unless this comparison may appear in a published figure."""
        if self.purpose == "design_decision":
            raise ValueError(
                f"{self.arm_a} -> {self.arm_b} is a design decision, not a result (FR-024); "
                "it states the counts it rests on and is not published"
            )
        if self.mde is None:
            raise ValueError(
                f"{self.arm_a} -> {self.arm_b} measured zero discordant pairs over {self.n_pairs} "
                "tasks, so it bought no resolution and has no MDE to report"
            )
        if not self.publishable:
            raise ValueError(
                f"{self.arm_a} -> {self.arm_b} is {self.verdict.value} over {self.n_pairs} pairs "
                f"against a floor of {self.floor}; it is not a publishable figure"
            )

    @property
    def pilot_verdict(self) -> str:
        """FR-024's go/no-go, read off the discordant counts.

        Only available on a design decision. Reading a go/no-go off a published figure is a
        category error, and the exception says so rather than returning a plausible string.
        """
        if self.purpose != "design_decision":
            raise ValueError(
                "pilot_verdict is a design decision under FR-024; this comparison has "
                f"purpose={self.purpose!r}. Build it with purpose='design_decision'."
            )
        if self.b <= self.c:
            return "stop"
        if (
            self.c <= _PILOT_MAX_C
            and self.b >= _PILOT_MIN_B
            and self.p_value is not None
            and self.p_value <= _PILOT_MAX_P
        ):
            return "go"
        return "inconclusive"

    def to_dict(self) -> dict:
        """The measurement's own provenance, in one shape.

        `lift.py` writes this into the result JSON and `reporter.py` reads it back to print the
        item count and the MDE beside the lift. Both go through here so the two cannot drift:
        a key the reporter needs and the writer stopped emitting would be a silent `—` in a
        column whose whole purpose is to refuse to be silent.
        """
        return {
            "arm_a": self.arm_a,
            "arm_b": self.arm_b,
            "n_pairs": self.n_pairs,
            "b": self.b,
            "c": self.c,
            "discordance": round(self.discordance, 4),
            "lift": None if self.lift is None else round(self.lift, 4),
            "interval": (
                None
                if self.interval is None
                else [round(self.interval[0], 4), round(self.interval[1], 4)]
            ),
            "p_value_one_sided": None
            if self.p_value is None
            else round(self.p_value, 4),
            "mde": None if self.mde is None else round(self.mde, 4),
            "floor": self.floor,
            "threshold_applied": round(self.threshold_applied, 4),
            "verdict": self.verdict.value,
            "underpowered": self.verdict is Verdict.UNDERPOWERED,
            "publishable": self.publishable,
            "purpose": self.purpose,
            "holes": list(self.holes),
            "summary": self.summary(),
        }

    def summary(self) -> str:
        """One line, and it never omits what it took to measure the number (G1).

        The item count, the floor, the MDE and the verdict travel with the lift. `reporter.py`
        formats the table; this is the single-line form for logs and for `research.md`.
        """
        lift = "—" if self.lift is None else f"{self.lift:+.3f}"
        interval = (
            "—"
            if self.interval is None
            else f"[{self.interval[0]:+.3f}, {self.interval[1]:+.3f}]"
        )
        mde = "n/a" if self.mde is None else f"{self.mde:.3f}"
        parts = [
            f"{self.arm_a} -> {self.arm_b}",
            f"lift {lift} {interval}",
            f"n={self.n_pairs} pairs",
            f"floor={self.floor}",
            f"discordance={self.discordance:.2f} (b={self.b}, c={self.c})",
            f"mde={mde}",
            f"threshold={self.threshold_applied:.3f}",
            self.verdict.value,
        ]
        if self.p_value is not None:
            parts.append(f"p={self.p_value:.4f} one-sided")
        if self.purpose == "design_decision":
            parts.append("design decision, not a result (FR-024)")
        if self.holes:
            parts.append(f"holes: {', '.join(self.holes)}")
        return "  ".join(parts)


def pair_arms(
    arm_a: str,
    arm_b: str,
    results_a: dict[str, bool],
    results_b: dict[str, bool],
    purpose: str = "result",
) -> Comparison:
    """Pair two arms on task ID and record what could not be paired.

    A task present in one arm and absent from the other becomes a named hole rather than a silently
    dropped row (G6). An arm that crashed on ten tasks must not read as an arm that passed on the
    rest, and the only way to tell the difference after the fact is to have written it down.

    Pairing keys on task ID, never on position: the two arms are separate runs and there is no
    reason their iteration order agrees.
    """
    ids_a, ids_b = set(results_a), set(results_b)
    shared = sorted(ids_a & ids_b)

    holes = [f"{task_id} missing from {arm_b}" for task_id in sorted(ids_a - ids_b)]
    holes += [f"{task_id} missing from {arm_a}" for task_id in sorted(ids_b - ids_a)]

    if not shared:
        raise ValueError(
            f"{arm_a} and {arm_b} share no task IDs, so there is nothing to pair. "
            f"Holes: {'; '.join(holes) if holes else 'none'}"
        )

    pairs = [
        TaskPair(
            task_id=task_id,
            arm_a=arm_a,
            arm_b=arm_b,
            passed_a=bool(results_a[task_id]),
            passed_b=bool(results_b[task_id]),
        )
        for task_id in shared
    ]

    return Comparison.from_pairs(arm_a, arm_b, pairs, purpose=purpose, holes=holes)


def assert_publishable_from_holdout(
    comparison: Comparison, split: Split | None = None
) -> Comparison:
    """The one gate a figure passes through on its way into a published table — T033, FR-021.

    Two refusals, in this order:

    1. `assert_publishable`, which is about the measurement — purpose, power, and whether any
       resolution was bought at all.
    2. The split, which is about where the tasks came from. A figure over a train-side task is a
       figure over something the tool descriptions were fitted to, and no amount of statistical
       power repairs that.

    The order matters for the error someone reads. An underpowered figure over clean holdout tasks
    should say "underpowered", because that is the thing to fix.

    Returns the comparison so this reads as a checkpoint at the point of use:
    `table.append(assert_publishable_from_holdout(comparison))`. A guard whose return value is
    discarded is a guard someone eventually forgets to call.
    """
    comparison.assert_publishable()
    task_ids = [pair.task_id for pair in comparison.pairs]
    if not task_ids:
        raise SplitLeak(
            f"{comparison.arm_a} -> {comparison.arm_b} records no task IDs, so the split cannot "
            "vouch for it. A comparison rebuilt from to_dict() has lost its pairs; publish from the "
            "run's own artifact bundle instead"
        )
    assert_holdout_only(split or default_split(), task_ids)
    return comparison
