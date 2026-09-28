"""Corpus triage — FR-013 and FR-014.

A task set whose two arms are pinned at the same end of the scale did not measure a skill; it
measured its own construction. Four of the nine gated skills read 0.00 against 0.00, and the gate
reported that as "no lift" — indistinguishable from a skill that genuinely does not help. One reads
0.80 against 1.00, where the skill arm has run out of room and the largest lift the set can ever
report is 0.20.

This module names those cases and refuses to let one sit in the corpus unexplained. It reads the
arm rates and item counts already recorded in a baseline file; it never runs a session and never
needs a credential.

The verdict vocabulary is FR-013's:

- `broken_check` — the check cannot pass, so nothing the agent does can register.
- `too_hard` — the check is right and the task is beyond both arms.
- `too_easy` — both arms already pass, so the skill has nothing to add.
- `not_helped` — the measurement works and the skill does not change the outcome.

`broken_check` and `too_hard` are the two readings of a floor; `too_easy` and `not_helped` are the
two readings of a ceiling. Telling them apart is what a reference solution is for (research.md
§ task format: `solution/solve.sh` is optional to Harbor and mandatory here).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping

from tests.e2e.skill_eval.comparison import GATE_THRESHOLD

FLOOR_RATE = 0.0
CEILING_RATE = 1.0


class Saturation(str, Enum):
    """Why a task set could not have measured what it was asked to measure."""

    FLOOR = "floor"
    CEILING = "ceiling"
    CEILING_CENSORED = "ceiling_censored"
    FLOOR_CENSORED = "floor_censored"
    NO_ITEMS = "no_items"


class TriageVerdict(str, Enum):
    """FR-013's four verdicts."""

    BROKEN_CHECK = "broken_check"
    TOO_HARD = "too_hard"
    TOO_EASY = "too_easy"
    NOT_HELPED = "not_helped"


_PERMITTED: dict[Saturation | None, frozenset[TriageVerdict]] = {
    Saturation.FLOOR: frozenset(
        {TriageVerdict.BROKEN_CHECK, TriageVerdict.TOO_HARD, TriageVerdict.NOT_HELPED}
    ),
    Saturation.CEILING: frozenset({TriageVerdict.TOO_EASY, TriageVerdict.NOT_HELPED}),
    # A censored ceiling reads the same way as a flat one: the arm at 1.00 has nowhere to go, so
    # either the tasks are too easy for it or the remaining gap is not the skill's doing.
    Saturation.CEILING_CENSORED: frozenset(
        {TriageVerdict.TOO_EASY, TriageVerdict.NOT_HELPED}
    ),
    # And a censored floor reads like a flat one, symmetrically: the arm at 0.00 has nowhere to
    # drop, so a regression larger than the gap is unreportable.
    Saturation.FLOOR_CENSORED: frozenset(
        {TriageVerdict.BROKEN_CHECK, TriageVerdict.TOO_HARD, TriageVerdict.NOT_HELPED}
    ),
    # Nothing scored. That is not a hard task set, it is a run that did not happen.
    Saturation.NO_ITEMS: frozenset({TriageVerdict.BROKEN_CHECK}),
    # Not saturated, and showing no effect the gate would call an effect. `not_helped` is the
    # honest label and the only one available: nothing here suggests the check is broken.
    None: frozenset({TriageVerdict.NOT_HELPED}),
}


def permitted_verdicts(saturation: Saturation | None) -> frozenset[TriageVerdict]:
    """Which verdicts are consistent with a given saturation.

    Calling a floor set `too_easy` is not a judgement call, it is a contradiction — and a triage
    record that contradicts the numbers it triages is worse than no record, because it looks
    settled.
    """
    return _PERMITTED[saturation]


@dataclass(frozen=True)
class TaskSet:
    """One skill's task set, as a baseline file recorded it.

    `pairs` is task-pairs, not scored items: the two arms pair up per task and run, so a set with
    five items per arm is five pairs. `comparison.py` gates on pairs and so does everything here.
    """

    skill: str
    base_rate: float
    skill_rate: float
    pairs: int
    task_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def saturation(self) -> Saturation | None:
        """The end of the scale this set is stuck against, or `None` if it is free to move.

        Equal arms in the middle — 0.40 against 0.40 — are deliberately not saturated. The check
        discriminates and the skill did not help, which is a result rather than a broken
        measurement. FR-013 is about the ends.
        """
        if self.pairs <= 0:
            return Saturation.NO_ITEMS
        if self.base_rate <= FLOOR_RATE and self.skill_rate <= FLOOR_RATE:
            return Saturation.FLOOR
        if self.base_rate >= CEILING_RATE and self.skill_rate >= CEILING_RATE:
            return Saturation.CEILING
        if self.base_rate >= CEILING_RATE or self.skill_rate >= CEILING_RATE:
            return Saturation.CEILING_CENSORED
        if self.base_rate <= FLOOR_RATE or self.skill_rate <= FLOOR_RATE:
            return Saturation.FLOOR_CENSORED
        return None

    @property
    def needs_verdict(self) -> bool:
        return self.saturation is not None

    @property
    def lift(self) -> float:
        return self.skill_rate - self.base_rate


@dataclass(frozen=True)
class TriageRecord:
    """A verdict with the evidence it was reached on.

    Evidence is required and is checked at construction. A verdict with nothing behind it is
    indistinguishable from not having looked, which is the state FR-013 exists to end.
    """

    skill: str
    verdict: TriageVerdict
    evidence: str
    action: str = ""

    def __post_init__(self) -> None:
        if not self.evidence or not self.evidence.strip():
            raise ValueError(
                f"{self.skill}: verdict {self.verdict.value} has no evidence — a verdict with "
                f"nothing behind it is not a verdict"
            )


def verdict_superseded(entry: Mapping, reached_on: str) -> bool:
    """True when a run after the verdict re-measured the skill and kept the figure.

    A verdict withdraws a figure until the harness can measure it again. Once a later run has, and
    its entry carries no withdrawn block, the verdict has done its job. Run ids are ISO timestamps,
    so string order is time order. No run id means unknown age, which is not newer.
    """
    if entry.get("withdrawn"):
        return False
    run_id = (entry.get("provenance") or {}).get("run_id")
    return bool(run_id) and run_id > reached_on


def validate_corpus(
    task_sets: Iterable[TaskSet],
    records: Mapping[str, TriageRecord],
) -> list[str]:
    """Every failure, not just the first — one string per offending task set.

    Three ways to fail, and the third is the one that rots quietly: a verdict left behind on a set
    that has since started discriminating still reads as settled.

    A set that is not saturated needs no record, and may carry only `not_helped`, and only while it
    shows no effect the gate would call an effect. The moment it shows one, the record contradicts
    the numbers and has to go.
    """
    failures: list[str] = []
    for task_set in task_sets:
        saturation = task_set.saturation
        record = records.get(task_set.skill)
        if saturation is None:
            if record is None:
                continue
            if record.verdict not in permitted_verdicts(None):
                failures.append(
                    f"{task_set.skill} verdict {record.verdict.value} is not available to a set "
                    f"that is not saturated ({task_set.base_rate:.2f} against "
                    f"{task_set.skill_rate:.2f}) — permitted: "
                    f"{', '.join(sorted(v.value for v in permitted_verdicts(None)))}"
                )
            elif abs(task_set.lift) >= GATE_THRESHOLD:
                failures.append(
                    f"{task_set.skill} has verdict {record.verdict.value} but is not saturated "
                    f"and reads a lift of {task_set.lift:+.2f}, at or over the gate's "
                    f"{GATE_THRESHOLD:.2f} — stale verdict"
                )
            continue
        if record is None:
            failures.append(
                f"{task_set.skill} is flat at the {saturation.value} "
                f"({task_set.base_rate:.2f} against {task_set.skill_rate:.2f}, "
                f"{task_set.pairs} pairs) with no recorded verdict"
            )
            continue
        if record.verdict not in permitted_verdicts(saturation):
            failures.append(
                f"{task_set.skill} verdict {record.verdict.value} contradicts saturation "
                f"{saturation.value} — permitted: "
                f"{', '.join(sorted(v.value for v in permitted_verdicts(saturation)))}"
            )
    return failures


def task_sets_from_baseline(baseline: Mapping) -> list[TaskSet]:
    """Read task sets out of a `skill-baseline.json` payload.

    An entry with no `items` block comes back with zero pairs and `NO_ITEMS` rather than being
    skipped: an entry that recorded no items is not a healthy entry, and dropping it hides that.
    """
    task_sets: list[TaskSet] = []
    for skill, entry in (baseline.get("skills") or {}).items():
        items = entry.get("items") or {}
        base = items.get("baseline") or {}
        arm = items.get("skill") or {}
        # Pairs are what *both* arms scored. A larger count on one side is not available for
        # pairing, so the smaller one is the resolution this set bought.
        pairs = min(
            int(base.get("items_scored") or 0),
            int(arm.get("items_scored") or 0),
        )
        provenance = entry.get("provenance") or {}
        task_sets.append(
            TaskSet(
                skill=skill,
                base_rate=_rate(base, entry, "pass_rate_baseline"),
                skill_rate=_rate(arm, entry, "pass_rate_skill"),
                pairs=pairs,
                task_ids=tuple(provenance.get("task_ids") or ()),
            )
        )
    return task_sets


def _rate(arm: Mapping, entry: Mapping, fallback_key: str) -> float:
    """Prefer the arm's own recorded rate, fall back to the entry's top-level copy."""
    value = arm.get("pass_rate")
    if value is None:
        value = entry.get(fallback_key)
    return float(value or 0.0)


def report(task_sets: Iterable[TaskSet], records: Mapping[str, TriageRecord]) -> str:
    """A one-line-per-set table for `research.md` § triage."""
    lines = [
        "| Skill | base | skill | Pairs | Saturation | Verdict |",
        "| ----- | ---- | ----- | ----: | ---------- | ------- |",
    ]
    for task_set in sorted(task_sets, key=lambda s: s.skill):
        saturation = task_set.saturation
        record = records.get(task_set.skill)
        lines.append(
            f"| {task_set.skill} | {task_set.base_rate:.2f} | {task_set.skill_rate:.2f} "
            f"| {task_set.pairs} | {saturation.value if saturation else '—'} "
            f"| {record.verdict.value if record else '—'} |"
        )
    return "\n".join(lines)
