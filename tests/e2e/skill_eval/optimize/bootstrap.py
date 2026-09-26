"""Paired bootstrap interval for a candidate-minus-seed rate difference (spec 128 FR-009).

The same holdout items are scored under both descriptions, so items are resampled as pairs. 10,000
resamples with a fixed seed of 128 make the interval reproducible from the report alone.
"""

from __future__ import annotations

import random

RESAMPLES = 10_000
SEED = 128


def paired_diff_ci(seed, cand, *, resamples: int = RESAMPLES, level: float = 0.95):
    """Return (mean difference, lower, upper) for per-item 0/1 outcomes, candidate minus seed."""
    if len(seed) != len(cand):
        raise ValueError(
            f"unpaired outcomes: {len(seed)} seed against {len(cand)} candidate"
        )
    if not seed:
        raise ValueError("no paired outcomes")
    diffs = [c - s for s, c in zip(seed, cand)]
    n = len(diffs)
    point = sum(diffs) / n
    rng = random.Random(SEED)
    means = sorted(
        sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples)
    )
    tail = (1 - level) / 2
    lo = means[int(tail * resamples)]
    hi = means[min(resamples - 1, int((1 - tail) * resamples))]
    return point, lo, hi
