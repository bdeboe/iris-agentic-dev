"""Stdout summary table and JSON result writer — T010, rebuilt for 118 T029.

Every column and footer line here exists because its absence hid something. The old table was
skill, fire rate, implicit fire rate, two pass rates, lift, Δ, and a tick — no scorer, no
denominator, no threshold. `objectscript-review  +0% ✓` for a skill whose scorer was never
reachable printed the same as one that had been measured and held.

`regression_flag` is serialized from `outcome` and computed nowhere in this module.
"""

import dataclasses
import json
import os
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from tests.e2e.skill_eval.evaluator import SkillResult

# The enum carries the identifier; the table reads it as English.
_OUTCOME_TEXT = {
    "regressed": "regressed",
    "held": "held",
    "new_skill": "new skill",
    "not_comparable": "not comparable",
    # 121: a Δ measured over fewer task-pairs than FR-008's floor. Not a pass, not a regression.
    "underpowered": "underpowered",
}

# `Comparison.verdict` — what this run's two arms are entitled to claim, as against `outcome`,
# which is this run against the stored entry. The two answer different questions and the table
# needs both: a skill can hold against its baseline while its arms remain indistinguishable.
_VERDICT_TEXT = {
    "underpowered": "underpowered",
    "indistinguishable": "indistinguishable",
    "below_threshold": "below threshold",
    "regressed": "arm regression",
    "not_comparable": "arms not comparable",
}

#: Printed in the lift, pairs and MDE columns when the row has no comparison to read them from.
#: T014: the reporter refuses to format a lift it cannot qualify, and says why on the next line
#: rather than printing a bare number the reader would take for a finding.
_WITHHELD = "—"
_NO_COMPARISON = "lift withheld: no comparison recorded, so neither the item count nor the MDE is known"


@dataclasses.dataclass
class EvalRun:
    run_id: str
    model: str
    # Keeps its name on purpose: `shard.py` merges shard files by key, so a rename drops the
    # field silently in a mixed-version merge. It now holds the resolved scorer model rather
    # than the hardcoded "openai/gpt-4.1" it used to lie with.
    judge_model: Optional[str]
    timestamp: str
    regression_threshold: float
    skills: "list[SkillResult]"
    summary: dict
    scorer_model_requested: Optional[str] = None
    tool_surface: Optional[str] = None
    run_valid: bool = True
    items_unscored_share: Optional[float] = None
    # skill → the `run_id` a re-run shard displaced. Empty when each skill had one result.
    reruns: Optional[dict] = None


def _arm(result: "SkillResult", name: str) -> dict:
    return ((getattr(result, "arms", None) or {}).get(name)) or {}


def _item_counts(results) -> tuple:
    """(scored, total) summed over both arms of every skill that measured anything."""
    scored = total = 0
    for r in results:
        for name in ("baseline", "skill"):
            arm = _arm(r, name)
            scored += arm.get("items_scored") or 0
            total += arm.get("items_total") or 0
    return scored, total


def _fmt_rate(value) -> str:
    return f"{value:.2f}" if value is not None else "—"


def _fmt_signed(value) -> str:
    """`—` means no comparison was made. `0.00` means one was, and came out flat."""
    if value is None:
        return "—"
    return f"{value:+.2f}" if value else "0.00"


def _comparison(result: "SkillResult") -> dict:
    return getattr(result, "comparison", None) or {}


def _lift_cells(result: "SkillResult") -> tuple:
    """`(lift, pairs, mde, note)` for one row — the three columns that travel together.

    G1 of contracts/comparison.md, at the one place a lift reaches a human. A lift with no
    comparison beside it is the `unpowered-result` bug class, so it is not printed: the columns
    read `—` and the note says what is missing. `mde` reads `n/a` when the arms agreed on every
    task, because zero discordance bought no resolution and `0.00` would claim it bought perfect
    resolution.
    """
    comparison = _comparison(result)
    if result.lift is None:
        return _WITHHELD, _WITHHELD, _WITHHELD, None
    if not comparison:
        return _WITHHELD, _WITHHELD, _WITHHELD, _NO_COMPARISON

    n_pairs = comparison.get("n_pairs")
    mde = comparison.get("mde")
    return (
        _fmt_signed(result.lift),
        str(n_pairs) if n_pairs is not None else _WITHHELD,
        f"{mde:.2f}" if mde is not None else "n/a",
        None,
    )


def _outcome_cell(result: "SkillResult") -> str:
    """The outcome against the stored entry, qualified by what this run's arms can support.

    `underpowered` replaces the outcome rather than annotating it. `held` on eight task-pairs is
    the reading that failed three consecutive nightly runs, and printing both words would leave
    the wrong one first.
    """
    outcome = _OUTCOME_TEXT.get(
        getattr(result, "outcome", ""), getattr(result, "outcome", "—")
    )
    verdict = _comparison(result).get("verdict")
    if verdict == "underpowered" or outcome == "underpowered":
        return "underpowered"
    if verdict in _VERDICT_TEXT:
        return f"{outcome} ({_VERDICT_TEXT[verdict]})"
    return outcome


def progress_line(skill: str, lift_data: dict) -> str:
    """The per-skill line the nightly log is read from, with the lift's resolution on it.

    Lives here rather than in `__main__.py` because it is the same refusal the table makes, and
    two copies of a refusal is one copy of a refusal. What it replaces printed
    `[iris-connectivity] lift=0.5 (16/16 scored)` — sixteen scored items is eight task-pairs,
    a fifth of FR-008's floor, and the line was the first number anyone read.
    """
    scored = lift_data.get("items_scored") or 0
    total = scored + (lift_data.get("items_unscored") or 0)
    counts = f"({scored}/{total} scored)"
    lift = lift_data.get("lift")
    comparison = lift_data.get("comparison") or {}

    if lift is None:
        return f"  [{skill}] no lift {counts}"
    if not comparison:
        return f"  [{skill}] lift withheld: no comparison recorded {counts}"
    if comparison.get("underpowered"):
        return (
            f"  [{skill}] lift={lift:+.2f} over {comparison.get('n_pairs')} pairs against a "
            f"floor of {comparison.get('floor')} — underpowered {counts}"
        )
    mde = comparison.get("mde")
    resolution = f"mde {mde:.2f}" if mde is not None else "mde n/a"
    return (
        f"  [{skill}] lift={lift:+.2f} over {comparison.get('n_pairs')} pairs "
        f"({resolution}) {counts}"
    )


def print_summary(run: EvalRun) -> None:
    """Print the table and footer of contracts/eval-run.md to stdout."""
    header = f"\nSkill Evaluation Results — {run.timestamp}"
    print(header)
    print("=" * len(header.strip()))
    print(
        f"{'skill':<31}{'mode':<10}{'scored':<9}{'base':>6}{'skill':>7}"
        f"{'lift':>7}{'pairs':>7}{'mde':>6}{'Δ base':>8}  {'outcome'}"
    )
    print(
        f"{'-' * 30} {'-' * 9} {'-' * 8} {'-' * 5} {'-' * 6} {'-' * 6} {'-' * 6} "
        f"{'-' * 5} {'-' * 7} {'-' * 20}"
    )

    for r in sorted(
        run.skills, key=lambda x: x.lift if x.lift is not None else -9, reverse=True
    ):
        base_arm, skill_arm = _arm(r, "baseline"), _arm(r, "skill")
        scored = (base_arm.get("items_scored") or 0) + (
            skill_arm.get("items_scored") or 0
        )
        total = (base_arm.get("items_total") or 0) + (skill_arm.get("items_total") or 0)
        mode = (getattr(r, "provenance", None) or {}).get("scoring_mode") or "—"
        outcome = _outcome_cell(r)
        if r.no_task_coverage:
            mode, outcome = "—", "no coverage"
        lift, pairs, mde, withheld = _lift_cells(r)
        print(
            f"{r.skill:<31}{mode:<10}{f'{scored}/{total}' if total else '—':<9}"
            f"{_fmt_rate(r.pass_rate_baseline):>6}{_fmt_rate(r.pass_rate_skill):>7}"
            f"{lift:>7}{pairs:>7}{mde:>6}{_fmt_signed(r.lift_delta):>8}  {outcome}"
        )
        # Why the lift was withheld, why a comparison was refused, and the binary or harness
        # change that did not refuse it. The floor rides along on an underpowered row so the verdict is checkable
        # from the report rather than only from the JSON.
        floor = _comparison(r).get("floor")
        underpowered = _comparison(r).get("underpowered")
        for note in (
            withheld,
            (
                f"{_comparison(r).get('n_pairs')} task-pairs against a floor of {floor} (FR-008)"
                if underpowered and floor
                else None
            ),
            getattr(r, "outcome_reason", None),
            getattr(r, "surface_note", None),
            getattr(r, "driver_note", None),
        ):
            if note:
                print(f"{'':<31}↳ {note}")

    print()
    scored, total = _item_counts(run.skills)
    unscored = total - scored
    share = (
        run.items_unscored_share
        if run.items_unscored_share is not None
        else (unscored / total if total else 0.0)
    )
    requested = run.scorer_model_requested
    print(
        f"scorer: {run.judge_model or 'unresolved'}"
        + (f" (requested {requested})" if requested else "")
    )
    print(
        f"tool surface: {run.tool_surface or run.summary.get('tool_surface') or 'unknown'}"
    )
    cost = run.summary.get("estimated_cost_usd")
    line = (
        f"threshold: {run.regression_threshold:.2f}   "
        f"unscored: {unscored}/{total} ({share * 100:.1f}%)"
    )
    if cost:
        line += f"   estimated cost: ${cost:.2f}"
    print(line)
    print(f"run valid: {'yes' if run.run_valid else 'no'}")
    if run.reruns:
        print(
            "re-runs merged: "
            + ", ".join(
                f"{skill} (discarded {run_id})"
                for skill, run_id in sorted(run.reruns.items())
            )
        )

    regressions = run.summary.get("regressions", [])
    improvements = run.summary.get("improvements", [])
    uncovered = run.summary.get("uncovered", [])
    print(f"regressions: {len(regressions)}", end="")
    print(f"  [{', '.join(regressions)}]" if regressions else "")
    print(f"improvements: {len(improvements)}")
    if uncovered:
        print(
            f"no task coverage: {len(uncovered)} skills (add eval.yaml to cover them)"
        )


def write_result(run: EvalRun, output_dir: str) -> str:
    """Write EvalRun to JSON. Returns path."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"skill-eval-{run.run_id}.json")
    data = dataclasses.asdict(run)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path
