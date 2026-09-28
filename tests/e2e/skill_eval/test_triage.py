"""Unit tests for corpus triage — T019, written before `triage.py`.

FR-013 and FR-014 in test form. A task set whose two arms are pinned at the same end of the scale
measured nothing, and the gate has to say so: flat at the floor, flat at the ceiling, or one arm
already at the ceiling with no room left for the other to improve. The current gate misses the
ceiling cases entirely — `objectscript-guardrails` reads 0.80 against 1.00 and passes.

Nothing here reads a live service, and nothing re-runs a session: the input is the arm rates and
item counts already sitting in `tests/e2e/results/skill-baseline.json`.
"""

import pytest

from tests.e2e.skill_eval.triage import (
    Saturation,
    TaskSet,
    TriageRecord,
    TriageVerdict,
    permitted_verdicts,
    task_sets_from_baseline,
    validate_corpus,
)


def task_set(base, skill, pairs=5, name="a-skill"):
    return TaskSet(skill=name, base_rate=base, skill_rate=skill, pairs=pairs)


# --- what counts as measuring nothing ---------------------------------------------------------


def test_both_arms_at_zero_is_flat_at_the_floor():
    assert task_set(0.00, 0.00).saturation is Saturation.FLOOR


def test_both_arms_at_one_is_flat_at_the_ceiling():
    assert task_set(1.00, 1.00).saturation is Saturation.CEILING


def test_one_arm_at_the_ceiling_is_censored_not_flat():
    """FR-014's case, and the one the old gate let through.

    0.80 against 1.00 is not flat — the arms differ — but the skill arm has nowhere left to go, so
    the largest lift this task set can ever report is 0.20 and any real effect above that is
    invisible. That needs a verdict for the same reason the floor does.
    """
    assert task_set(0.80, 1.00).saturation is Saturation.CEILING_CENSORED
    assert task_set(1.00, 0.80).saturation is Saturation.CEILING_CENSORED


def test_one_arm_at_the_floor_is_censored_too():
    """The floor is censored the same way the ceiling is, and T022 asks about both.

    `ensemble-production` reads 0.10 against 0.00. The skill arm is on the floor, so the largest
    drop this task set can ever report is 0.10 — a real regression bigger than that is invisible,
    for the same reason a real gain above 0.20 is invisible at 0.80 against 1.00.
    """
    assert task_set(0.10, 0.00).saturation is Saturation.FLOOR_CENSORED
    assert task_set(0.00, 0.10).saturation is Saturation.FLOOR_CENSORED
    assert task_set(0.10, 0.00).needs_verdict


def test_a_censored_floor_takes_the_same_verdicts_as_a_flat_floor():
    assert permitted_verdicts(Saturation.FLOOR_CENSORED) == permitted_verdicts(
        Saturation.FLOOR
    )


def test_a_genuine_arm_difference_needs_no_verdict():
    subject = task_set(0.60, 0.80)
    assert subject.saturation is None
    assert not subject.needs_verdict


@pytest.mark.parametrize(
    "base,skill",
    [(0.00, 0.00), (1.00, 1.00), (0.80, 1.00)],
    ids=["floor", "ceiling", "censored"],
)
def test_every_saturated_set_needs_a_verdict(base, skill):
    assert task_set(base, skill).needs_verdict


def test_a_flat_set_in_the_middle_is_not_saturated():
    """Equal arms at 0.40 are not the same failure. The check discriminates; the skill did nothing.

    That is `not_helped`, and it is a result rather than a broken measurement — so it is reportable
    without a triage verdict, and FR-013's list is about the ends of the scale only.
    """
    assert task_set(0.40, 0.40).saturation is None


# --- which verdicts a saturated set may be given -----------------------------------------------


def test_a_floor_set_may_not_be_called_too_easy():
    assert TriageVerdict.TOO_EASY not in permitted_verdicts(Saturation.FLOOR)
    assert TriageVerdict.BROKEN_CHECK in permitted_verdicts(Saturation.FLOOR)
    assert TriageVerdict.TOO_HARD in permitted_verdicts(Saturation.FLOOR)


def test_a_ceiling_set_may_not_be_called_too_hard():
    assert TriageVerdict.TOO_HARD not in permitted_verdicts(Saturation.CEILING)
    assert TriageVerdict.TOO_EASY in permitted_verdicts(Saturation.CEILING)


def test_a_censored_set_takes_the_same_verdicts_as_a_ceiling_set():
    assert permitted_verdicts(Saturation.CEILING_CENSORED) == permitted_verdicts(
        Saturation.CEILING
    )


# --- corpus validation --------------------------------------------------------------------------


def test_a_saturated_set_with_no_recorded_verdict_fails_validation():
    failures = validate_corpus(
        [task_set(0.00, 0.00, name="objectscript-sql-patterns")], {}
    )
    assert len(failures) == 1
    assert "objectscript-sql-patterns" in failures[0]
    assert "floor" in failures[0]


def test_a_recorded_verdict_clears_validation():
    sets = [task_set(0.00, 0.00, name="iris-connectivity")]
    records = {
        "iris-connectivity": TriageRecord(
            skill="iris-connectivity",
            verdict=TriageVerdict.BROKEN_CHECK,
            evidence="all ten items scored 0 with an unreachable IRIS in both arms",
        )
    }
    assert validate_corpus(sets, records) == []


def test_a_verdict_with_no_evidence_is_not_a_verdict():
    """The rule that stops triage becoming a checkbox.

    "too hard" with nothing behind it is indistinguishable from not having looked, which is the
    state FR-013 exists to end.
    """
    with pytest.raises(ValueError, match="evidence"):
        TriageRecord(
            skill="objectscript-unit-test",
            verdict=TriageVerdict.TOO_HARD,
            evidence="  ",
        )


def test_a_verdict_that_contradicts_the_saturation_fails_validation():
    sets = [task_set(0.80, 1.00, name="objectscript-guardrails")]
    records = {
        "objectscript-guardrails": TriageRecord(
            skill="objectscript-guardrails",
            verdict=TriageVerdict.TOO_HARD,
            evidence="both arms failed every item",
        )
    }
    failures = validate_corpus(sets, records)
    assert len(failures) == 1
    assert "too_hard" in failures[0]
    assert "ceiling_censored" in failures[0]


def test_a_middling_flat_set_may_be_recorded_as_not_helped():
    """0.40 against 0.40 is not saturated, and `not_helped` is still the honest label for it.

    T022 has to say something about the skills that read a small difference and nothing more.
    `not_helped` is allowed anywhere the set shows no effect the gate would call an effect — under
    `comparison.GATE_THRESHOLD` — and is the only verdict allowed there.
    """
    sets = [task_set(0.40, 0.40, name="iris-ai-hub")]
    records = {
        "iris-ai-hub": TriageRecord(
            skill="iris-ai-hub",
            verdict=TriageVerdict.NOT_HELPED,
            evidence="lift -0.10 over 15 pairs, inside the resolution the corpus bought",
        )
    }
    assert validate_corpus(sets, records) == []


def test_a_middling_set_may_not_be_called_broken():
    sets = [task_set(0.40, 0.40, name="iris-ai-hub")]
    records = {
        "iris-ai-hub": TriageRecord(
            skill="iris-ai-hub",
            verdict=TriageVerdict.BROKEN_CHECK,
            evidence="guessing",
        )
    }
    failures = validate_corpus(sets, records)
    assert len(failures) == 1
    assert "broken_check" in failures[0]


def test_a_verdict_for_a_set_that_is_not_saturated_fails_validation():
    """A verdict on a set showing a real difference is a stale verdict, and stale rots quietly."""
    sets = [task_set(0.60, 0.80, name="objectscript-review")]
    records = {
        "objectscript-review": TriageRecord(
            skill="objectscript-review",
            verdict=TriageVerdict.NOT_HELPED,
            evidence="left over from an earlier run",
        )
    }
    failures = validate_corpus(sets, records)
    assert len(failures) == 1
    assert "objectscript-review" in failures[0]
    assert "not saturated" in failures[0]


def test_validation_names_every_failing_set_not_just_the_first():
    sets = [
        task_set(0.00, 0.00, name="a"),
        task_set(1.00, 1.00, name="b"),
        task_set(0.60, 0.80, name="c"),
    ]
    failures = validate_corpus(sets, {})
    assert len(failures) == 2
    assert {"a", "b"} == {f.split()[0] for f in failures}


# --- reading the artifact rather than re-running -----------------------------------------------


def test_task_sets_come_out_of_a_baseline_file():
    baseline = {
        "schema": 2,
        "skills": {
            "iris-connectivity": {
                "items": {
                    "baseline": {"items_scored": 5, "pass_rate": 0.0},
                    "skill": {"items_scored": 5, "pass_rate": 0.0},
                }
            }
        },
    }
    sets = task_sets_from_baseline(baseline)
    assert len(sets) == 1
    assert sets[0].skill == "iris-connectivity"
    assert sets[0].pairs == 5
    assert sets[0].saturation is Saturation.FLOOR


def test_an_arm_with_a_different_item_count_takes_the_smaller_one():
    """Pairs are what both arms scored. The larger count is not available for pairing."""
    baseline = {
        "skills": {
            "half-crashed": {
                "items": {
                    "baseline": {"items_scored": 10, "pass_rate": 0.0},
                    "skill": {"items_scored": 4, "pass_rate": 0.0},
                }
            }
        }
    }
    assert task_sets_from_baseline(baseline)[0].pairs == 4


def test_a_skill_with_no_items_block_is_reported_not_skipped():
    """An entry that records no items is not a healthy entry, and dropping it hides that."""
    baseline = {"skills": {"mystery": {"lift": None}}}
    sets = task_sets_from_baseline(baseline)
    assert len(sets) == 1
    assert sets[0].pairs == 0
    assert sets[0].saturation is Saturation.NO_ITEMS
    assert sets[0].needs_verdict


# --- the recorded verdicts, and the Phase 2 gate — T021, T022, T023 ---------------------------
#
# The gate is "no task set in the gated corpus is flat at floor or ceiling without a recorded
# verdict, and every verdict has been acted on". That is a test, not a paragraph: the records live in
# `triage_records.py` and this file checks them against the committed baseline every run. A skill
# that drifts into saturation later fails here rather than passing quietly.


def real_baseline():
    import json
    import os

    path = os.path.join(
        os.path.dirname(__file__), "..", "results", "skill-baseline.json"
    )
    with open(path) as handle:
        return json.load(handle)


def test_every_saturated_set_in_the_committed_baseline_has_a_verdict():
    """The Phase 2 gate itself."""
    from tests.e2e.skill_eval.triage_records import RECORDS

    failures = validate_corpus(task_sets_from_baseline(real_baseline()), RECORDS)
    assert failures == [], "\n".join(failures)


def test_every_recorded_verdict_says_what_was_done_about_it():
    """T023: a verdict with no action is a documented null task set, which the gate refuses."""
    from tests.e2e.skill_eval.triage_records import RECORDS

    missing = [name for name, record in RECORDS.items() if not record.action.strip()]
    assert missing == []


def eval_config(skill):
    import os

    import yaml

    path = os.path.join(
        os.path.dirname(__file__), "..", "tasks", "skills", skill, "eval.yaml"
    )
    with open(path) as handle:
        return yaml.safe_load(handle)


def test_a_retired_task_set_really_has_no_benchmark_tasks():
    """The action, checked against the corpus rather than believed.

    "Task set retired" in a `TriageRecord` and `benchmark_tasks: [GEN-01, GEN-02]` still sitting in
    the eval config is the failure mode T023 exists to prevent — the verdict reads as acted on and
    the next run spends money re-measuring the set it retired.
    """
    from tests.e2e.skill_eval.triage_records import RETIRED_TASK_SETS

    assert RETIRED_TASK_SETS
    for skill in RETIRED_TASK_SETS:
        assert eval_config(skill).get("benchmark_tasks") in (None, []), skill


def test_a_skill_whose_set_was_not_retired_keeps_its_tasks():
    """The other direction: three of the four floors were harness defects, not corpus defects."""
    from tests.e2e.skill_eval.triage_records import RETIRED_TASK_SETS

    for skill in ("iris-connectivity", "objectscript-list-patterns"):
        assert skill not in RETIRED_TASK_SETS
        assert eval_config(skill).get("benchmark_tasks"), skill


def test_the_four_floor_skills_are_all_verdicted_broken_check():
    """T021's answer. None of the four floors reproduced; all four were the harness's.

    Reference solutions score 3/3/3 through the real judge on every one of these checks, and two of
    the recorded 0.00 items scored a pass on a single live re-run.
    """
    from tests.e2e.skill_eval.triage_records import ALL_RECORDS as RECORDS

    for skill in (
        "iris-connectivity",
        "objectscript-list-patterns",
        "objectscript-sql-patterns",
        "objectscript-unit-test",
    ):
        assert RECORDS[skill].verdict is TriageVerdict.BROKEN_CHECK, skill


def test_the_ceiling_case_is_verdicted_too_easy():
    """T022's first half: 0.80 against 1.00 over five pairs."""
    from tests.e2e.skill_eval.triage_records import RECORDS

    assert RECORDS["objectscript-guardrails"].verdict is TriageVerdict.TOO_EASY


def test_the_two_negative_lifts_are_verdicted_not_helped_with_their_mde():
    """T022's second half: −0.10 is noise, and the evidence has to say against what.

    Both sets read a lift smaller than the MDE their own item count bought, so neither is
    distinguishable from zero. A verdict that just says "noise" is the state FR-013 exists to end.
    """
    from tests.e2e.skill_eval.triage_records import RECORDS

    for skill in ("ensemble-production", "iris-ai-hub"):
        record = RECORDS[skill]
        assert record.verdict is TriageVerdict.NOT_HELPED, skill
        # Naming the call is a stronger claim than the word "MDE": it says which n and which
        # discordance the number came from, so a reader can recompute it.
        assert "mde_paired(" in record.evidence, skill


def test_the_numbers_the_verdicts_argue_from_still_hold():
    """The evidence quotes computed values. If `stats.py` moves, the evidence goes stale silently.

    These four are the ones T022's two verdicts turn on: at ten pairs a −0.10 is inside the noise,
    at thirty it is close to the edge of it, and eighteen pairs is what resolving 0.20 costs.
    """
    from tests.e2e.skill_eval.stats import mde_paired, n_for_effect_paired

    assert round(mde_paired(5, 0.20), 4) == 0.4334
    assert round(mde_paired(10, 0.10), 4) == 0.2482
    assert round(mde_paired(30, 0.10), 4) == 0.1555
    assert n_for_effect_paired(0.20, 0.10) == 18


def test_the_records_carry_no_verdict_for_a_healthy_set():
    """A record on a set that is discriminating is a stale record. Don't pre-emptively file one."""
    from tests.e2e.skill_eval.triage_records import RECORDS

    assert "objectscript-review" not in RECORDS
    assert "iris-vector-ai" not in RECORDS


def test_the_real_baseline_file_triages_without_crashing():
    """Reads the committed artifact — the same input T021 and T022 argue from."""
    import json
    import os

    path = os.path.join(
        os.path.dirname(__file__), "..", "results", "skill-baseline.json"
    )
    with open(path) as handle:
        baseline = json.load(handle)
    sets = task_sets_from_baseline(baseline)
    assert len(sets) == 9
    saturated = {s.skill: s.saturation for s in sets if s.needs_verdict}
    # The 2026-09-27 re-baseline, both harness fixes in. Three sets are still saturated: the two
    # retired ones keep their 2026-09-12 entries, and SQLCODE-SILENT floors again with every item
    # scored.
    assert set(saturated) == {
        "objectscript-sql-patterns",
        "objectscript-unit-test",
        "objectscript-guardrails",
    }
    assert saturated["objectscript-guardrails"] is Saturation.CEILING_CENSORED
    assert saturated["objectscript-sql-patterns"] is Saturation.FLOOR


# --- a verdict a later run has re-measured past — 130 round 3 --------------------------------
#
# The verdicts here were reached on the 2026-09-12 baseline. The 2026-09-27 re-baseline ran seven
# of those skills again with both harness fixes in place and wrote fresh entries with no withdrawn
# block, which is correct: the withdrawn figure is gone and a figure that stands replaced it. The
# baseline guard still demanded the withdrawn block, so it failed on the one run that did what the
# verdicts asked for.


def test_an_entry_re_measured_after_the_verdict_supersedes_it():
    from tests.e2e.skill_eval.triage import verdict_superseded

    entry = {"provenance": {"run_id": "2026-09-27T204612"}}
    assert verdict_superseded(entry, "2026-09-12T171550")


def test_an_entry_from_the_verdicts_own_run_does_not_supersede_it():
    from tests.e2e.skill_eval.triage import verdict_superseded

    entry = {"provenance": {"run_id": "2026-09-12T171550"}}
    assert not verdict_superseded(entry, "2026-09-12T171550")


def test_an_entry_with_no_provenance_does_not_supersede_a_verdict():
    """Unknown age is not newer. Schema 1 entries carry no run id."""
    from tests.e2e.skill_eval.triage import verdict_superseded

    assert not verdict_superseded({}, "2026-09-12T171550")
    assert not verdict_superseded({"provenance": {}}, "2026-09-12T171550")


def test_a_withdrawn_entry_is_never_superseded():
    """A later run that still withdrew the figure has not replaced it with one that stands."""
    from tests.e2e.skill_eval.triage import verdict_superseded

    entry = {
        "provenance": {"run_id": "2026-09-27T204612"},
        "withdrawn": {"verdict": "too_easy", "reason": "x"},
    }
    assert not verdict_superseded(entry, "2026-09-12T171550")


def test_the_verdicts_name_the_run_they_were_reached_on():
    from tests.e2e.skill_eval.triage_records import VERDICTS_REACHED_ON

    assert VERDICTS_REACHED_ON == "2026-09-12T171550"


def test_a_verdict_the_re_baseline_cured_leaves_the_live_records():
    """A cured set that still carried its verdict would trip the stale-verdict rule, and rightly.

    iris-connectivity and objectscript-list-patterns read 0.00 against 0.00 before the transcript
    fix. The 2026-09-27 run reads both at 0.33 against 0.67, so the check registers the agent now.
    """
    from tests.e2e.skill_eval.triage_records import ALL_RECORDS, RECORDS, SUPERSEDED

    assert set(SUPERSEDED) == {"iris-connectivity", "objectscript-list-patterns"}
    for skill, run_id in SUPERSEDED.items():
        assert skill not in RECORDS, skill
        assert skill in ALL_RECORDS, skill
        assert run_id == "2026-09-27T204612", skill


def test_every_superseded_verdict_was_superseded_by_the_committed_baseline():
    """The history has to match the artifact: the named run wrote the entry, and it discriminates."""
    import json
    import os

    from tests.e2e.skill_eval.triage import verdict_superseded
    from tests.e2e.skill_eval.triage_records import SUPERSEDED, VERDICTS_REACHED_ON

    path = os.path.join(
        os.path.dirname(__file__), "..", "results", "skill-baseline.json"
    )
    with open(path) as handle:
        baseline = json.load(handle)
    sets = {s.skill: s for s in task_sets_from_baseline(baseline)}
    for skill, run_id in SUPERSEDED.items():
        entry = baseline["skills"][skill]
        assert entry["provenance"]["run_id"] == run_id, skill
        assert verdict_superseded(entry, VERDICTS_REACHED_ON), skill
        assert sets[skill].saturation is None, skill
