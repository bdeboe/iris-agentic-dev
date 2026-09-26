"""The ship gate (spec 128 FR-009, User Story 3).

Four gates, all on holdout items scored under both the seed and the candidate:

1. the paired bootstrap 95% interval for the Recall@1 difference has its lower bound above 0;
2. the false-hint rate on `no-skill` prompts is not above the seed's;
3. exact-name Recall@1 is not below the seed's;
4. the live ladder for the candidate is not below the seed's by more than `LADDER_MARGIN`.

All four pass → SHIP. Anything else → HOLD, naming each failed gate. A missing ladder run is a
failure, not a pass: the proxy is a stand-in, and nothing ships on the stand-in alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tests.e2e.skill_eval.optimize.bootstrap import paired_diff_ci

SHIP = "SHIP"
HOLD = "HOLD"
LADDER_MARGIN = 0.05
SKILL_SLICES = ("paraphrase", "exact-name")


@dataclass(frozen=True)
class Outcome:
    slice: str
    correct: bool


@dataclass
class Verdict:
    verdict: str
    failed: list[str] = field(default_factory=list)
    figures: dict = field(default_factory=dict)


def _rate(flags):
    return sum(flags) / len(flags) if flags else 0.0


def decide(seed: dict, cand: dict, *, ladder: dict | None) -> Verdict:
    ids = sorted(set(seed) & set(cand))
    skill = [i for i in ids if seed[i].slice in SKILL_SLICES]
    exact = [i for i in ids if seed[i].slice == "exact-name"]
    none = [i for i in ids if seed[i].slice == "no-skill"]

    s_rec = [int(seed[i].correct) for i in skill]
    c_rec = [int(cand[i].correct) for i in skill]
    diff, lo, hi = paired_diff_ci(s_rec, c_rec) if skill else (0.0, 0.0, 0.0)
    f = {
        "recall_n": len(skill),
        "seed_recall": _rate(s_rec),
        "cand_recall": _rate(c_rec),
        "diff": diff,
        "diff_lo": lo,
        "diff_hi": hi,
        "false_hint_n": len(none),
        "seed_false_hint": _rate([not seed[i].correct for i in none]),
        "cand_false_hint": _rate([not cand[i].correct for i in none]),
        "exact_n": len(exact),
        "seed_exact": _rate([seed[i].correct for i in exact]),
        "cand_exact": _rate([cand[i].correct for i in exact]),
        "ladder": ladder,
    }

    failed = []
    if not lo > 0:
        failed.append(
            f"recall: interval lower bound {lo:+.3f} is not above 0 (diff {diff:+.3f}, n={len(skill)})"
        )
    if f["cand_false_hint"] > f["seed_false_hint"]:
        failed.append(
            f"false-hint: {f['cand_false_hint']:.3f} is above the seed's {f['seed_false_hint']:.3f}"
        )
    if f["cand_exact"] < f["seed_exact"]:
        failed.append(
            f"exact-name: {f['cand_exact']:.3f} is below the seed's {f['seed_exact']:.3f}"
        )
    if ladder is None:
        failed.append("ladder: no live ladder run")
    elif ladder["candidate"] < ladder["seed"] - LADDER_MARGIN - 1e-12:
        failed.append(
            f"ladder: {ladder['candidate']:.3f} is more than {LADDER_MARGIN} below the seed's {ladder['seed']:.3f}"
        )
    return Verdict(HOLD if failed else SHIP, failed, f)
