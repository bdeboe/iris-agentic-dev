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
import re
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

# 130 round 3. A withdrawal verdict is triage vocabulary; the table says what it means. The full
# evidence stays in `triage_records.py` and the result JSON.
_WITHDRAWN_TEXT = {
    "too_easy": "tasks too easy: the agent passes them without the skill",
    "broken_check": "no working tasks here: the old tasks could not register what the skill does",
    "too_hard": "tasks too hard: neither arm passes them",
    "not_helped": "the skill's earlier lift was inside the noise",
}

_WITHDRAWN = re.compile(r"^withdrawn(?: \((?P<verdict>[a-z_]+)\))?:")


def _withdrawn_verdict(reason) -> Optional[str]:
    """`too_easy` from `withdrawn (too_easy): …`, `""` for a bare `withdrawn:`, else `None`."""
    match = _WITHDRAWN.match(reason or "")
    if not match:
        return None
    return match.group("verdict") or ""


def ladder_coverage(task_dir: Optional[str] = None) -> dict:
    """skill → the sorted ids of the ladder tasks that name it, read off each task's `skill:` field.

    File reads only, no IRIS. The ladder grades some skills the skill-eval does not, and a report
    that calls those "no coverage" sends someone to write tasks that already exist.
    """
    from tests.e2e.skill_eval import graded_task

    coverage: dict = {}
    for task in graded_task.load_dir(task_dir or graded_task.SKILL_TASK_DIR):
        if task.skill:
            coverage.setdefault(task.skill, []).append(task.id)
    return {skill: sorted(ids) for skill, ids in coverage.items()}


def _task_ranges(ids) -> str:
    """`SKILL-01–05, SKILL-17` for SKILL-01 … SKILL-05 and SKILL-17."""
    groups: list = []
    for task_id in sorted(ids):
        prefix, _, number = task_id.rpartition("-")
        if (
            groups
            and number.isdigit()
            and groups[-1][0] == prefix
            and int(number) == int(groups[-1][2]) + 1
            and len(number) == len(groups[-1][2])
        ):
            groups[-1][2] = number
        else:
            groups.append([prefix, number, number])
    return ", ".join(
        f"{prefix}-{first}" if first == last else f"{prefix}-{first}–{last}"
        for prefix, first, last in groups
    )


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

    Underpowered replaces the outcome rather than annotating it. `held` on eight task-pairs is
    the reading that failed three consecutive nightly runs, and printing both words would leave
    the wrong one first. It prints as the pairs it had against the pairs it needed, so the verdict
    is checkable from the row.
    """
    comparison = _comparison(result)
    if result.lift is not None:
        base, skill = result.pass_rate_baseline, result.pass_rate_skill
        if base == skill == 0:
            return "both arms fail every task"
        if base == skill == 1:
            return "both arms pass every task"
    if (
        result.lift is None
        and _withdrawn_verdict(getattr(result, "outcome_reason", None)) is not None
    ):
        return "not run here"
    outcome = _OUTCOME_TEXT.get(
        getattr(result, "outcome", ""), getattr(result, "outcome", "—")
    )
    verdict = comparison.get("verdict")
    if verdict == "underpowered" or outcome == "underpowered":
        n_pairs, floor = comparison.get("n_pairs"), comparison.get("floor")
        if n_pairs is not None and floor:
            return f"too few runs to tell ({n_pairs} of {floor} pairs needed)"
        return "too few runs to tell"
    if _withdrawn_verdict(getattr(result, "outcome_reason", None)) is not None:
        return "first measurement"
    if verdict in _VERDICT_TEXT:
        return f"{outcome} ({_VERDICT_TEXT[verdict]})"
    return outcome


def _row_notes(result: "SkillResult", withheld, ladder: dict, shared_surface) -> list:
    """The lines under a row, each said once and in words."""
    reason = getattr(result, "outcome_reason", None)
    withdrawn = _withdrawn_verdict(reason)
    underpowered = bool(_comparison(result).get("underpowered")) or (
        getattr(result, "outcome", None) == "underpowered"
    )
    notes = [withheld]
    if withdrawn is not None and result.lift is None:
        # The skill-eval did not run it. Say why, and where it is graded instead.
        notes.append(_WITHDRAWN_TEXT.get(withdrawn, "its task set was withdrawn"))
        tasks = ladder.get(result.skill)
        notes.append(
            f"graded by the ladder: {_task_ranges(tasks)}"
            if tasks
            else "not graded by the ladder either"
        )
    elif withdrawn is not None:
        # About the stored entry, not this measurement: it is why there is no Δ.
        notes.append(
            "first figure that stands: the old baseline figure was withdrawn, so there is no Δ"
        )
    elif reason and not underpowered:
        # The underpowered reason restates the verdict cell.
        notes.append(reason)
    surface = getattr(result, "surface_note", None)
    if surface != shared_surface:
        notes.append(surface)
    notes.append(getattr(result, "driver_note", None))
    return [note for note in notes if note]


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


def print_summary(run: EvalRun, ladder_tasks: Optional[dict] = None) -> None:
    """Print the table and footer of contracts/eval-run.md to stdout.

    `ladder_tasks` is skill → ladder task ids; `None` reads them off the task files.
    """
    ladder = ladder_coverage() if ladder_tasks is None else ladder_tasks
    scored_all, total_all = _item_counts(run.skills)
    validity = (
        f"valid, {total_all - scored_all} of {total_all} items unscored"
        if run.run_valid
        else f"NOT valid, {total_all - scored_all} of {total_all} items unscored"
    )
    header = f"\nSkill Evaluation Results — {run.timestamp} — {validity}"
    print(header)
    print("=" * len(header.strip()))

    measured = [r for r in run.skills if not r.no_task_coverage]
    uncovered = sorted(r.skill for r in run.skills if r.no_task_coverage)
    surfaces = {getattr(r, "surface_note", None) for r in measured}
    shared_surface = (
        surfaces.pop() if len(surfaces) == 1 and len(measured) > 1 else None
    )
    if shared_surface:
        print(f"{shared_surface}, for every skill below")

    width = max([len("skill")] + [len(r.skill) for r in measured]) + 1
    print(
        f"{'skill':<{width}}{'mode':<10}{'scored':<9}{'base':>6}{'skill':>7}"
        f"{'lift':>7}{'pairs':>7}{'mde':>6}{'Δ base':>8}  {'outcome'}"
    )
    print(
        f"{'-' * (width - 1)} {'-' * 9} {'-' * 8} {'-' * 5} {'-' * 6} {'-' * 6} {'-' * 6} "
        f"{'-' * 5} {'-' * 7} {'-' * 20}"
    )

    for r in sorted(
        measured, key=lambda x: x.lift if x.lift is not None else -9, reverse=True
    ):
        base_arm, skill_arm = _arm(r, "baseline"), _arm(r, "skill")
        scored = (base_arm.get("items_scored") or 0) + (
            skill_arm.get("items_scored") or 0
        )
        total = (base_arm.get("items_total") or 0) + (skill_arm.get("items_total") or 0)
        mode = (getattr(r, "provenance", None) or {}).get("scoring_mode") or "—"
        lift, pairs, mde, withheld = _lift_cells(r)
        print(
            f"{r.skill:<{width}}{mode:<10}{f'{scored}/{total}' if total else '—':<9}"
            f"{_fmt_rate(r.pass_rate_baseline):>6}{_fmt_rate(r.pass_rate_skill):>7}"
            f"{lift:>7}{pairs:>7}{mde:>6}{_fmt_signed(r.lift_delta):>8}  {_outcome_cell(r)}"
        )
        for note in _row_notes(r, withheld, ladder, shared_surface):
            print(f"{'':<{width}}↳ {note}")

    print()
    print(
        "pairs = task runs compared across both arms; mde = the smallest lift that many pairs can "
        "detect, so a lift below it is not a finding"
    )
    on_ladder = [s for s in uncovered if ladder.get(s)]
    nowhere = [s for s in uncovered if not ladder.get(s)]
    if on_ladder:
        print(
            f"graded only by the ladder ({len(on_ladder)}): "
            + ", ".join(f"{s} ({', '.join(ladder[s])})" for s in on_ladder)
        )
    if nowhere:
        print(f"not graded anywhere ({len(nowhere)}): {', '.join(nowhere)}")

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
    print(f"regressions: {len(regressions)}", end="")
    print(f"  [{', '.join(regressions)}]" if regressions else "")
    print(f"improvements: {len(improvements)}")


def write_result(run: EvalRun, output_dir: str) -> str:
    """Write EvalRun to JSON. Returns path."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"skill-eval-{run.run_id}.json")
    data = dataclasses.asdict(run)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path
