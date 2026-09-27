"""Unit tests for the train/holdout split — 120 T015, written before `split.py`.

FR-011 in test form, and the reason it is P2 rather than polish: GEPA optimises tool descriptions
against this corpus. A figure measured on tasks the descriptions were fitted to overstates the tools'
value, and after the fact there is no way to claim otherwise — the criticism lands and the number is
gone. So the split is a committed file, and the loader raises rather than repairing.

Two rules run through the file:

- **The file is parsed as text** (the #110 pattern). A test that builds a dict and asserts on the dict
  agrees with a writer that forgot a key.
- **Every failure names the ID.** A split that covers 49 of 50 tasks is wrong in one place, and a
  message that says "coverage mismatch" makes someone diff two lists by hand.
"""

from __future__ import annotations

import os

import pytest

from tests.e2e.skill_eval.graded_task import all_tasks, skill_corpus
from tests.e2e.skill_eval.split import (
    HOLDOUT,
    SPLIT_FILENAME,
    TRAIN,
    Split,
    SplitInvalid,
    SplitLeak,
    assert_holdout_only,
    default_split,
    load_split,
    pilot_split,
)


def write_split(tmp_path, text: str) -> str:
    path = tmp_path / SPLIT_FILENAME
    path.write_text(text, encoding="utf-8")
    return str(path)


def a_split_file(tmp_path, train=("A-01",), holdout=("A-02", "A-03")) -> str:
    lines = ["# a split", f"train = {list(train)!r}".replace("'", '"')]
    lines.append(f"holdout = {list(holdout)!r}".replace("'", '"'))
    return write_split(tmp_path, "\n".join(lines) + "\n")


CORPUS = ("A-01", "A-02", "A-03")


# --- the loader ----------------------------------------------------------------------------------


def test_a_split_file_loads_into_two_disjoint_sides(tmp_path):
    split = load_split(a_split_file(tmp_path), CORPUS)
    assert split.train == ("A-01",)
    assert split.holdout == ("A-02", "A-03")
    assert split.side_of("A-01") == TRAIN
    assert split.side_of("A-03") == HOLDOUT


def test_an_id_in_both_sides_raises_and_names_it(tmp_path):
    """The failure that makes a leak invisible: the ID is in `holdout`, so the publish guard passes,
    and it is also in `train`, so the descriptions were fitted to it."""
    path = a_split_file(tmp_path, train=("A-01", "A-02"), holdout=("A-02", "A-03"))
    with pytest.raises(SplitInvalid) as raised:
        load_split(path, CORPUS)
    assert "A-02" in str(raised.value)
    assert "A-01" not in str(raised.value), (
        "only the offending ID, or nobody reads the message"
    )


def test_an_id_in_neither_side_raises_and_names_it(tmp_path):
    path = a_split_file(tmp_path, train=("A-01",), holdout=("A-02",))
    with pytest.raises(SplitInvalid) as raised:
        load_split(path, CORPUS)
    assert "A-03" in str(raised.value)


def test_an_id_in_the_file_that_is_not_in_the_corpus_raises(tmp_path):
    """A renamed or deleted task leaves a stale ID behind, and a stale ID in `holdout` is a hole the
    publish guard cannot see: nothing is measured under it, so nothing is refused."""
    path = a_split_file(tmp_path, train=("A-01",), holdout=("A-02", "A-03", "A-99"))
    with pytest.raises(SplitInvalid) as raised:
        load_split(path, CORPUS)
    assert "A-99" in str(raised.value)


def test_an_empty_holdout_raises(tmp_path):
    """FR-021 publishes from the holdout. A split with nothing in it there makes every figure
    unpublishable, and the honest time to say so is when the file is written."""
    path = a_split_file(tmp_path, train=CORPUS, holdout=())
    with pytest.raises(SplitInvalid) as raised:
        load_split(path, CORPUS)
    assert "holdout" in str(raised.value)


def test_a_missing_side_is_not_an_empty_side(tmp_path):
    """`train` absent is a file someone half-wrote, not a corpus that is all holdout."""
    path = write_split(tmp_path, 'holdout = ["A-01", "A-02", "A-03"]\n')
    with pytest.raises(SplitInvalid) as raised:
        load_split(path, CORPUS)
    assert "train" in str(raised.value)


def test_a_missing_file_raises_and_names_the_path(tmp_path):
    with pytest.raises(SplitInvalid) as raised:
        load_split(str(tmp_path / "nope.toml"), CORPUS)
    assert "nope.toml" in str(raised.value)


def test_the_loader_reads_the_file_and_not_a_dict(tmp_path):
    """Explicitly: the assertion subject is the text on disk. A `Split` built in Python and compared
    to itself passes against a loader that never opened anything."""
    path = write_split(tmp_path, 'train = ["A-01"]\nholdout = ["A-02", "A-03"]\n')
    with open(path, encoding="utf-8") as handle:
        assert "A-01" in handle.read()
    assert load_split(path, CORPUS).train == ("A-01",)


def test_a_side_is_sorted_however_the_file_ordered_it(tmp_path):
    """Two orderings of one split are one split; a diff between them is noise in a review."""
    path = a_split_file(tmp_path, train=("A-01",), holdout=("A-03", "A-02"))
    assert load_split(path, CORPUS).holdout == ("A-02", "A-03")


# --- the publish mechanism (FR-011; spec 121's T033 is the guard over it) -------------------------


def test_a_train_task_in_a_published_set_raises_and_names_it():
    split = Split(train=("A-01",), holdout=("A-02", "A-03"))
    with pytest.raises(SplitLeak) as raised:
        assert_holdout_only(split, ["A-02", "A-01"])
    assert "A-01" in str(raised.value)


def test_a_holdout_only_set_passes():
    split = Split(train=("A-01",), holdout=("A-02", "A-03"))
    assert_holdout_only(split, ["A-02", "A-03"])


def test_an_unknown_task_id_in_a_published_set_raises():
    """Not silently allowed. An ID the split has never heard of is a figure measured over something
    the split cannot vouch for, which is the same problem as a leak with a better disguise."""
    split = Split(train=("A-01",), holdout=("A-02",))
    with pytest.raises(SplitLeak) as raised:
        assert_holdout_only(split, ["A-02", "A-77"])
    assert "A-77" in str(raised.value)


# --- the committed file (121 T032's guard) --------------------------------------------------------


def test_the_committed_split_covers_the_whole_corpus_exactly():
    """The guard the gate asks for: this goes red when a task ID is duplicated or dropped.

    Corpus-wide, not pilot-wide. The pilot's split file stays on disk as the record of what the
    go/no-go was measured under, and `test_the_corpus_split_agrees_with_the_pilots` below is what
    stops the two disagreeing."""
    split = default_split()
    corpus = {task.id for task in all_tasks()}
    assert set(split.train) | set(split.holdout) == corpus
    assert not set(split.train) & set(split.holdout)


def test_the_committed_split_lives_beside_the_corpus():
    """A clone carries the split, so it cannot be silently re-drawn per checkout. One file above the
    three task directories, because one corpus gets one split."""
    from tests.e2e.skill_eval.graded_task import BENCHMARK_DIR
    from tests.e2e.skill_eval.split import split_path

    assert split_path() == os.path.join(BENCHMARK_DIR, SPLIT_FILENAME)
    assert os.path.isfile(split_path())


def test_the_corpus_split_agrees_with_the_pilots():
    """Moving a pilot task from train to holdout would make the pilot's own figures publishable after
    the fact, which is the leak this file exists to prevent — and it would be a one-word diff in a
    file nobody re-reads. So the two files are compared."""
    corpus = default_split()
    pilot = pilot_split()
    for task_id in pilot.train:
        assert corpus.side_of(task_id) == TRAIN, f"{task_id} changed sides"
    for task_id in pilot.holdout:
        assert corpus.side_of(task_id) == HOLDOUT, f"{task_id} changed sides"


def test_every_skill_ladder_task_is_on_the_holdout_side():
    """The skills tasks are purpose-built for one question and nothing is tuned against them, so
    there is no reason for any of them to be un-publishable. If one ever needs tuning it moves, and
    this test is what forces that to be a deliberate commit."""
    split = default_split()
    skill_ids = [task.id for task in skill_corpus()]
    assert skill_ids, (
        "no skill tasks yet — this test is vacuous until Goal 2 writes them"
    )
    assert_holdout_only(
        split, [task_id for task_id in skill_ids if task_id not in TUNED_SKILL_TASKS]
    )


#: Skill tasks moved to train because a skill was edited while reading their transcripts. Each one
#: has a replacement on the holdout for the same skill.
TUNED_SKILL_TASKS = {"SKILL-13": "SKILL-20"}


def test_a_tuned_skill_task_is_on_train_and_its_replacement_on_the_holdout():
    """130 round 3 rewrote `iris-query-plans` from the SKILL-13 transcripts. A figure from SKILL-13
    after that is measured on the task the skill was fitted to."""
    split = default_split()
    tasks = {task.id: task for task in skill_corpus()}
    for tuned, replacement in TUNED_SKILL_TASKS.items():
        assert tuned in split.train, f"{tuned} was tuned against and must be on train"
        assert replacement in split.holdout, f"{replacement} must be on the holdout"
        assert tasks[replacement].skill == tasks[tuned].skill, (
            f"{replacement} must measure the same skill as {tuned}"
        )


def test_the_gate_task_is_on_the_train_side():
    """PILOT-01 is the task every phase gate ran, and I have read its transcripts. That is tuning,
    whatever it was called at the time, so a figure published off it would be measured on a task the
    harness was fitted to."""
    assert "PILOT-01" in default_split().train
