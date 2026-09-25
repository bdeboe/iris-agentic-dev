"""The committed train/holdout split — 120 T016, FR-011.

Two ID lists in one file beside the corpus, and a loader that raises rather than repairing.

The split is a prerequisite and not a refinement, for one reason: GEPA optimises tool descriptions
against this corpus, and `benchmark/021`'s `merged` condition is already a tuned system prompt. A
figure measured on tasks the descriptions were fitted to overstates the tools' value, and there is no
way to establish otherwise after the fact — the number is simply gone. Drawing the line before the
first published figure is the only time it costs nothing.

Every failure names the offending ID. A split that covers 49 of 50 tasks is wrong in one place, and a
message that says "coverage mismatch" hands someone two lists to diff by hand.

Spec 121 owns the guard (its T032) and the publish refusal (its T033). This module owns the mechanism
and the file's location, so those two are a call each rather than a re-implementation.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass

from tests.e2e.skill_eval.graded_task import (
    BENCHMARK_DIR,
    PILOT_DIR,
    all_tasks,
    pilot_tasks,
)

TRAIN = "train"
HOLDOUT = "holdout"

#: Beside the corpus, so a clone carries the split and cannot silently re-draw it per checkout.
SPLIT_FILENAME = "split.toml"


class SplitInvalid(ValueError):
    """The split file does not describe this corpus. Nothing may be measured under it."""


class SplitLeak(RuntimeError):
    """A figure was computed over a task the split does not allow it to be published from."""


@dataclass(frozen=True)
class Split:
    train: tuple[str, ...]
    holdout: tuple[str, ...]

    def side_of(self, task_id: str) -> str | None:
        if task_id in self.train:
            return TRAIN
        if task_id in self.holdout:
            return HOLDOUT
        return None


def split_path() -> str:
    """One file above the three task directories. One corpus gets one split."""
    return os.path.join(BENCHMARK_DIR, SPLIT_FILENAME)


def pilot_split_path() -> str:
    """The pilot's own split, kept as the record of what the go/no-go was measured under.

    It is not the split anything publishes from — `split_path()` is. It stays because
    `tests/e2e/results/pilot-121.json` was taken under it, and a test compares the two so a pilot
    task cannot change sides in the corpus-wide file without that being a visible failure.
    """
    return os.path.join(PILOT_DIR, SPLIT_FILENAME)


def default_split() -> Split:
    """The committed split, checked against the whole committed corpus."""
    return load_split(split_path(), [task.id for task in all_tasks()])


def pilot_split() -> Split:
    """The pilot's split, checked against the pilot corpus."""
    return load_split(pilot_split_path(), [task.id for task in pilot_tasks()])


def load_split(path: str, corpus_ids) -> Split:
    """Parse the split file and check it covers `corpus_ids` exactly, or raise.

    Coverage is checked at load, not at use. A split that is wrong is wrong for every figure taken
    under it, and the cheap moment to find that out is before the first session starts.
    """
    if not os.path.isfile(path):
        raise SplitInvalid(
            f"no split file at {path} — FR-011 wants it committed beside the corpus, because a "
            "split drawn per run is not a split"
        )
    with open(path, "rb") as handle:
        try:
            raw = tomllib.load(handle)
        except tomllib.TOMLDecodeError as broken:
            raise SplitInvalid(f"{path} is not valid TOML: {broken}") from broken

    for side in (TRAIN, HOLDOUT):
        if side not in raw:
            raise SplitInvalid(
                f"{path} declares no {side} side. An absent side is a file someone half-wrote, not "
                "a corpus that is all of the other one"
            )
        if not isinstance(raw[side], list):
            raise SplitInvalid(f"{path}: {side} must be a list of task IDs")

    train = tuple(sorted(str(item) for item in raw[TRAIN]))
    holdout = tuple(sorted(str(item) for item in raw[HOLDOUT]))
    corpus = set(corpus_ids)

    both = sorted(set(train) & set(holdout))
    if both:
        raise SplitInvalid(
            f"{path}: {', '.join(both)} is in both sides. The publish guard reads holdout and would "
            "pass it, and the optimizer reads train and would fit to it — a leak that looks clean"
        )

    covered = set(train) | set(holdout)
    strangers = sorted(covered - corpus)
    if strangers:
        raise SplitInvalid(
            f"{path}: {', '.join(strangers)} is not in the corpus. A stale ID on the holdout side is "
            "a hole the publish guard cannot see, because nothing is ever measured under it"
        )
    missing = sorted(corpus - covered)
    if missing:
        raise SplitInvalid(
            f"{path}: {', '.join(missing)} is in neither side. FR-011 wants every task ID in exactly "
            "one, so a task cannot be measured without the split having an opinion about it"
        )
    if not holdout:
        raise SplitInvalid(
            f"{path}: the holdout side is empty, so FR-021 has nothing to publish from and every "
            "figure taken under this split is unpublishable"
        )
    if not train:
        raise SplitInvalid(
            f"{path}: the train side is empty. Tuning then has nowhere to go except the holdout, "
            "which is how a holdout stops being one"
        )
    return Split(train=train, holdout=holdout)


def assert_holdout_only(split: Split, task_ids) -> None:
    """Raise unless every task in `task_ids` is on the holdout side (the FR-011 half of FR-021).

    An ID the split has never heard of raises too. It is a figure over something the split cannot
    vouch for, which is the same problem as a leak wearing a better disguise.
    """
    leaked = sorted({task for task in task_ids if split.side_of(task) == TRAIN})
    unknown = sorted({task for task in task_ids if split.side_of(task) is None})
    problems = []
    if leaked:
        problems.append(
            f"{', '.join(leaked)} is on the train side, and tool descriptions, skills and prompts "
            "are tuned against that side"
        )
    if unknown:
        problems.append(
            f"{', '.join(unknown)} is in neither side of the split, so nothing vouches for it"
        )
    if problems:
        raise SplitLeak(
            "refusing to publish a figure computed over these tasks: "
            + "; ".join(problems)
        )
