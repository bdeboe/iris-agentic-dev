"""Confidence intervals, paired significance tests, and power arithmetic — T009.

Pure functions, no I/O, no third-party dependency. `math` and `statistics.NormalDist` cover
everything here, which is the whole reason not to take a numerics dependency for two closed forms
and a bisection (Constitution VII).

Named `stats.py` rather than `statistics.py` on purpose: a module named `statistics.py` in this
directory shadows the stdlib module it imports the moment anything runs a file in here directly
rather than through the package.

## Which formulas, and why these ones

Three of the five functions have more than one textbook form, and the choice is pinned by
spec.md's Assumptions section rather than by preference. The arcsine transform for unpaired power
and Connor (1987) for paired are the only combination that reproduces all five numbers the spec
states — MDE 0.35 at n=30, 0.20 at n=100, 97 per arm for an unpaired +0.20, and paired floors of
37 and 77 at discordance 0.20 and 0.40. Substituting the pooled-variance formula gives 99 per arm
instead of 97 and the spec's numbers stop reconciling.

- **Wilson** for a single proportion, not the normal approximation. The approximation has zero
  width at p=0 and p=1, and four skills in the current corpus sit at exactly p=0. A zero-width
  interval there reports "measured at 0.00, exactly" for a task set that graded nothing.
- **McNemar** for two arms over the same tasks, not a two-sample z-test. Pairing is what buys a
  floor of 37 instead of 97 per arm, and the tasks are the same tasks by construction.
- **Connor (1987)** for paired sample size, inverted numerically for the paired MDE.

Alpha is 0.05 two-sided and power 0.80 throughout, and both are arguments rather than constants so
a caller must not edit this file to change them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

__all__ = [
    "McNemarResult",
    "mcnemar_interval",
    "mcnemar_test",
    "mde_paired",
    "mde_unpaired",
    "n_for_effect_paired",
    "n_for_effect_unpaired",
    "wilson_interval",
]

_NORMAL = NormalDist()

DEFAULT_ALPHA = 0.05
DEFAULT_POWER = 0.80


def _z_two_sided(alpha: float) -> float:
    """Critical value for a two-sided test at `alpha`. 1.959963984540054 at alpha=0.05."""
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    return _NORMAL.inv_cdf(1.0 - alpha / 2.0)


def _z_power(power: float) -> float:
    """One-sided quantile for the target power. 0.8416212335729143 at power=0.80."""
    if not 0.0 < power < 1.0:
        raise ValueError(f"power must be in (0, 1), got {power}")
    return _NORMAL.inv_cdf(power)


def _chi_square_sf_1df(x: float) -> float:
    """Upper tail of a chi-square with one degree of freedom.

    P(X > x) = 2(1 - Phi(sqrt(x))) = erfc(sqrt(x / 2)). Exact, and stdlib.
    """
    if x < 0.0:
        raise ValueError(f"chi-square statistic cannot be negative, got {x}")
    return math.erfc(math.sqrt(x / 2.0))


# ---------------------------------------------------------------------------
# Single proportion
# ---------------------------------------------------------------------------


def wilson_interval(
    successes: int, trials: int, alpha: float = DEFAULT_ALPHA
) -> tuple[float, float]:
    """Wilson score interval for a proportion.

    Returns `(low, high)`, clamped to [0, 1]. Unlike the normal approximation this keeps a real
    width at `successes == 0` and `successes == trials`, which is the only reason it is here.
    """
    if trials <= 0:
        raise ValueError(f"trials must be positive, got {trials}")
    if not 0 <= successes <= trials:
        raise ValueError(f"successes must be in [0, {trials}], got {successes}")

    z = _z_two_sided(alpha)
    n = float(trials)
    p_hat = successes / n
    z2_over_n = z * z / n

    denominator = 1.0 + z2_over_n
    centre = (p_hat + z2_over_n / 2.0) / denominator
    half_width = (z / denominator) * math.sqrt(
        p_hat * (1.0 - p_hat) / n + z * z / (4.0 * n * n)
    )

    low = max(0.0, centre - half_width)
    high = min(1.0, centre + half_width)

    # The closed form cancels to exactly 0 at p=0 and exactly 1 at p=1 in real arithmetic, but in
    # floating point it lands a few 1e-18 off. Pin the endpoints rather than leaving callers to
    # decide whether 3.5e-18 is a lower bound of zero.
    if successes == 0:
        low = 0.0
    if successes == trials:
        high = 1.0

    return (low, high)


# ---------------------------------------------------------------------------
# Paired comparison
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class McNemarResult:
    """The outcome of a paired test over discordant counts.

    `b` is the count of pairs where the upper arm passes and the lower fails; `c` is the reverse.
    Concordant pairs carry no information about the difference and do not appear.

    `effect` is the imbalance among discordant pairs, `(b - c) / (b + c)`. The population
    difference needs the total pair count and lives in `mcnemar_interval` instead — keeping them
    apart stops a discordant-only ratio being read as a pass-rate difference.

    Every p-value field is `None` when there are no discordant pairs. That is a real state, not a
    zero: two arms that agreed on every task have shown no difference and no evidence about one.
    """

    b: int
    c: int
    discordant: int
    effect: float
    p_value_one_sided: float | None
    p_value_corrected: float | None
    chi_square_corrected: float | None


def mcnemar_test(b: int, c: int) -> McNemarResult:
    """Exact and continuity-corrected McNemar tests on discordant counts.

    The exact one-sided p-value is the binomial tail `P(X >= b)` for `X ~ Binomial(b + c, 0.5)`:
    under the null, each discordant pair is equally likely to fall either way. It depends only on
    `b` and `c`, never on the number of pairs, which is why FR-024's go/no-go rule needs no
    separate table for a second round of tasks.

    The corrected form is Edwards' `(|b - c| - 1)^2 / (b + c)` against one degree of freedom. It is
    reported for continuity with anything that expects a chi-square, and the exact test is what the
    decision rule uses.
    """
    if b < 0 or c < 0:
        raise ValueError(f"discordant counts cannot be negative, got b={b}, c={c}")

    discordant = b + c
    if discordant == 0:
        return McNemarResult(
            b=b,
            c=c,
            discordant=0,
            effect=0.0,
            p_value_one_sided=None,
            p_value_corrected=None,
            chi_square_corrected=None,
        )

    one_sided = math.fsum(
        math.comb(discordant, i) for i in range(b, discordant + 1)
    ) / (2.0**discordant)

    chi_square = (abs(b - c) - 1) ** 2 / discordant
    return McNemarResult(
        b=b,
        c=c,
        discordant=discordant,
        effect=(b - c) / discordant,
        p_value_one_sided=one_sided,
        p_value_corrected=_chi_square_sf_1df(chi_square),
        chi_square_corrected=chi_square,
    )


def mcnemar_interval(
    b: int, c: int, n_pairs: int, alpha: float = DEFAULT_ALPHA
) -> tuple[float, tuple[float, float]]:
    """Difference in pass rates for paired data, with a confidence interval.

    Returns `(delta, (low, high))` where `delta = (b - c) / n_pairs` — the difference between the
    two arms' pass rates over the same tasks, which is what a reported lift means.

    The standard error is `sqrt((b + c) - (b - c)^2 / n) / n`. Concordant pairs enter only through
    `n`, which is why a large corpus of tasks both arms pass narrows nothing: resolution comes from
    disagreement, and that is the fact FR-008's floor is computed from.

    At `b == c == 0` the interval is `(0.0, 0.0)`. Degenerate, and correct: the arms agreed on every
    one of `n_pairs` tasks. It contains zero, so a `Comparison` reads it as indistinguishable, and
    the MDE is what records that no resolution was bought.
    """
    if n_pairs <= 0:
        raise ValueError(f"n_pairs must be positive, got {n_pairs}")
    if b < 0 or c < 0:
        raise ValueError(f"discordant counts cannot be negative, got b={b}, c={c}")
    if b + c > n_pairs:
        raise ValueError(f"discordant pairs {b + c} exceed total pairs {n_pairs}")

    n = float(n_pairs)
    delta = (b - c) / n
    variance = (b + c) - (b - c) ** 2 / n
    standard_error = math.sqrt(max(0.0, variance)) / n
    z = _z_two_sided(alpha)

    return (delta, (delta - z * standard_error, delta + z * standard_error))


# ---------------------------------------------------------------------------
# Power
# ---------------------------------------------------------------------------


def mde_unpaired(
    n_per_arm: int,
    baseline: float,
    alpha: float = DEFAULT_ALPHA,
    power: float = DEFAULT_POWER,
) -> float:
    """Smallest improvement over `baseline` detectable with `n_per_arm` items in each arm.

    Arcsine-transformed, so the effect size is Cohen's h and the variance does not depend on the
    proportion. Reproduces spec.md's 0.35 at n=30 and 0.20 at n=100 against a baseline of 0.40.

    Saturates at `1 - baseline`: no item count makes an effect larger than the room above the
    baseline detectable, and reporting a bigger number would be arithmetic with no meaning.
    """
    if n_per_arm <= 0:
        raise ValueError(f"n_per_arm must be positive, got {n_per_arm}")
    if not 0.0 <= baseline <= 1.0:
        raise ValueError(f"baseline must be in [0, 1], got {baseline}")

    h = math.sqrt((_z_two_sided(alpha) + _z_power(power)) ** 2 / (2.0 * n_per_arm))
    angle = math.asin(math.sqrt(baseline)) + h
    if angle >= math.pi / 2.0:
        return 1.0 - baseline
    return math.sin(angle) ** 2 - baseline


def n_for_effect_unpaired(
    baseline: float,
    target: float,
    alpha: float = DEFAULT_ALPHA,
    power: float = DEFAULT_POWER,
) -> int:
    """Items per arm needed to detect `baseline` -> `target` with two independent arms.

    Returns 97 for 0.40 -> 0.60, which is spec.md's figure and the number the paired design exists
    to avoid paying twice over.
    """
    if not 0.0 <= baseline <= 1.0:
        raise ValueError(f"baseline must be in [0, 1], got {baseline}")
    if not 0.0 <= target <= 1.0:
        raise ValueError(f"target must be in [0, 1], got {target}")
    if baseline == target:
        raise ValueError(
            "baseline and target are equal, so no effect is being detected"
        )

    h = abs(math.asin(math.sqrt(target)) - math.asin(math.sqrt(baseline)))
    return math.ceil((_z_two_sided(alpha) + _z_power(power)) ** 2 / (2.0 * h * h))


def _n_paired_raw(
    delta: float, discordance: float, alpha: float, power: float
) -> float:
    """Connor (1987), unrounded. Split out so `mde_paired` can invert the same expression."""
    z_alpha = _z_two_sided(alpha)
    z_beta = _z_power(power)
    numerator = (
        z_alpha * math.sqrt(discordance)
        + z_beta * math.sqrt(discordance - delta * delta)
    ) ** 2
    return numerator / (delta * delta)


def n_for_effect_paired(
    delta: float,
    discordance: float,
    alpha: float = DEFAULT_ALPHA,
    power: float = DEFAULT_POWER,
) -> int:
    """Task-pairs needed to detect a difference of `delta` at a given discordance rate.

    FR-008's floor: 37 pairs for delta=0.20 at discordance 0.20, and 77 at discordance 0.40. The
    harness recomputes this from each run's *measured* discordance rather than the expected one, so
    a run whose arms agree more than expected raises its own floor instead of passing a comparison
    that cannot support the verdict.

    `delta` cannot exceed `sqrt(discordance)`: the difference between two arms is bounded by how
    often they disagree at all, and asking for more is asking for an effect the design cannot hold.
    """
    if not 0.0 < discordance <= 1.0:
        raise ValueError(f"discordance must be in (0, 1], got {discordance}")
    if delta <= 0.0:
        raise ValueError(f"delta must be positive, got {delta}")
    if delta > math.sqrt(discordance):
        raise ValueError(
            f"delta {delta} exceeds sqrt(discordance) {math.sqrt(discordance):.4f}; "
            "no paired design can detect a difference larger than the disagreement rate allows"
        )

    return math.ceil(_n_paired_raw(delta, discordance, alpha, power))


def mde_paired(
    n_pairs: int,
    discordance: float,
    alpha: float = DEFAULT_ALPHA,
    power: float = DEFAULT_POWER,
) -> float | None:
    """Smallest difference `n_pairs` task-pairs can resolve at the measured discordance.

    Inverts `n_for_effect_paired` by bisection. `_n_paired_raw` rises without bound as delta falls
    toward zero and falls to `(z_alpha + z_beta)^2` as delta approaches `sqrt(discordance)`, so the
    root is unique and bisection needs no seed.

    Returns `None` at zero discordance. Two arms that never disagreed bought no resolution at all,
    and reporting 0.0 would claim they bought perfect resolution — the same inversion that let a
    lift of 0.00 read as a measured null.
    """
    if n_pairs <= 0:
        raise ValueError(f"n_pairs must be positive, got {n_pairs}")
    if not 0.0 <= discordance <= 1.0:
        raise ValueError(f"discordance must be in [0, 1], got {discordance}")
    if discordance == 0.0:
        return None

    low, high = 1e-12, math.sqrt(discordance) - 1e-12
    if _n_paired_raw(high, discordance, alpha, power) > n_pairs:
        # Not even the largest effect the design can hold is detectable at this item count.
        return math.sqrt(discordance)

    for _ in range(200):
        mid = (low + high) / 2.0
        if _n_paired_raw(mid, discordance, alpha, power) > n_pairs:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0
