"""Unit tests for reporter — T009, extended for 118 T025 and 121 T013.

Every column and footer line asserted below exists because its absence hid something in the
runs of 2026-08/09. That report printed a skill name, a fire rate, and a lift, and nothing
else: no scorer, no denominator, no threshold. `objectscript-review  +0% ✓` was indistinguishable
from a skill that had been measured and held.
"""

import json
import os

import pytest

from tests.e2e.skill_eval.comparison import GATE_THRESHOLD, Comparison, TaskPair
from tests.e2e.skill_eval.evaluator import SkillResult
from tests.e2e.skill_eval.reporter import (
    EvalRun,
    print_summary,
    progress_line,
    write_result,
)


def arm(pass_rate, total=12, unscored=0):
    scored = total - unscored
    return {
        "items_total": total,
        "items_scored": scored,
        "items_unscored": unscored,
        "items_passed": 0 if pass_rate is None else round(pass_rate * scored),
        "pass_rate": pass_rate,
    }


def comparison_over(b, c, both_pass=0, both_fail=0) -> dict:
    """A real `Comparison`, serialized the way `lift.py` writes it into the result JSON."""
    pairs = []
    for cell, (passed_a, passed_b) in (
        (b, (False, True)),
        (c, (True, False)),
        (both_pass, (True, True)),
        (both_fail, (False, False)),
    ):
        for _ in range(cell):
            pairs.append(
                TaskPair(
                    f"t{len(pairs)}",
                    "baseline",
                    "skill",
                    passed_a=passed_a,
                    passed_b=passed_b,
                )
            )
    return Comparison.from_pairs("baseline", "skill", pairs).to_dict()


#: 100 pairs, 32 discordant, lift +0.28: powered, and above the threshold.
POWERED = comparison_over(b=30, c=2, both_pass=30, both_fail=38)
#: 8 pairs. Whatever the lift says, the floor says the number cannot be read.
UNDERPOWERED = comparison_over(b=5, c=1, both_fail=2)


def provenance(**over):
    prov = {
        "run_id": "2026-09-12T040211Z",
        "task_ids": ["DBG-01"],
        "scoring_mode": "judge",
        "scorer_model": "claude-sonnet-4-6",
        "scorer_model_requested": "us.anthropic.claude-sonnet-4-6",
        "tool_surface": "1.4.1+fa0b694f8725",
        "runs": 3,
        "measured_at": "2026-09-12T04:11:07Z",
        "harness_commit": "7d82f7d",
        "driver": "opencode",
        "harness_version": "0.14.3",
    }
    prov.update(over)
    return prov


def make_result(
    skill,
    lift=None,
    fire_rate=1.0,
    regression=False,
    no_coverage=False,
    outcome=None,
    outcome_reason=None,
    delta=None,
    arms=None,
    prov=None,
    surface_note=None,
    driver_note=None,
    comparison="auto",
):
    if outcome is None:
        outcome = (
            "regressed"
            if regression
            else ("held" if lift is not None else "not_comparable")
        )
    return SkillResult(
        skill=skill,
        fire_rate=fire_rate if not no_coverage else None,
        implicit_fire_rate=None,
        isolation_fire_rate=None,
        pass_rate_baseline=0.71 if lift else None,
        pass_rate_skill=(0.71 + lift) if lift else None,
        lift=lift,
        lift_delta=delta,
        regression_flag=outcome == "regressed",
        new_skill=outcome == "new_skill",
        no_task_coverage=no_coverage,
        task_ids_used=["DBG-01"] if lift else [],
        outcome=outcome,
        outcome_reason=outcome_reason,
        arms=(
            arms
            if arms is not None
            else (
                None
                if no_coverage
                else {"baseline": arm(0.71), "skill": arm(0.71 + (lift or 0))}
            )
        ),
        provenance=(
            prov if prov is not None else (None if no_coverage else provenance())
        ),
        threshold_applied=GATE_THRESHOLD,
        surface_note=surface_note,
        driver_note=driver_note,
        comparison=(
            (POWERED if lift is not None else None)
            if comparison == "auto"
            else comparison
        ),
    )


def make_eval_run(skills, **over):
    fields = {
        "run_id": "2026-05-31T000000",
        "model": "amazon-bedrock/test",
        "judge_model": "claude-sonnet-4-6",
        "timestamp": "2026-05-31T00:00:00Z",
        "regression_threshold": GATE_THRESHOLD,
        "skills": skills,
        "summary": {
            "regressions": [],
            "improvements": [],
            "uncovered": ["iris-docs"],
            "estimated_cost_usd": 1.50,
        },
        "scorer_model_requested": "us.anthropic.claude-sonnet-4-6",
        "tool_surface": "1.4.1+fa0b694f8725",
        "run_valid": True,
    }
    fields.update(over)
    return EvalRun(**fields)


def test_print_summary_contains_skill_name(capsys):
    run = make_eval_run([make_result("objectscript-review", lift=0.29)])
    print_summary(run)
    captured = capsys.readouterr()
    assert "objectscript-review" in captured.out
    assert "0.29" in captured.out or "29" in captured.out


def test_print_summary_shows_a_regressed_row(capsys):
    run = make_eval_run(
        [make_result("objectscript-review", lift=0.10, regression=True, delta=-0.19)]
    )
    print_summary(run)
    assert "regress" in capsys.readouterr().out.lower()


def test_write_result_creates_json(tmp_path):
    run = make_eval_run([make_result("objectscript-review", lift=0.29)])
    path = write_result(run, str(tmp_path))
    assert os.path.exists(path)
    with open(path) as f:
        data = json.load(f)
    assert data["run_id"] == "2026-05-31T000000"
    assert len(data["skills"]) == 1
    assert data["skills"][0]["skill"] == "objectscript-review"
    assert data["summary"]["estimated_cost_usd"] == pytest.approx(1.50)


def test_write_result_carries_the_outcome_and_its_provenance(tmp_path):
    """The shard file is what the aggregate job reads; a dropped field is a dropped fact."""
    run = make_eval_run([make_result("objectscript-review", lift=0.29, delta=0.02)])
    data = json.loads(open(write_result(run, str(tmp_path))).read())
    entry = data["skills"][0]
    assert entry["outcome"] == "held"
    assert entry["threshold_applied"] == pytest.approx(GATE_THRESHOLD)
    assert entry["provenance"]["scorer_model"] == "claude-sonnet-4-6"
    assert entry["arms"]["skill"]["items_scored"] == 12
    assert entry["regression_flag"] == (entry["outcome"] == "regressed")


# ---------------------------------------------------------------------------
# 118 T025 — the columns and footer of contracts/eval-run.md
# ---------------------------------------------------------------------------


def test_the_table_has_the_mode_scored_and_outcome_columns(capsys):
    run = make_eval_run([make_result("iris-connectivity", lift=0.29, delta=0.04)])
    print_summary(run)
    out = capsys.readouterr().out
    header = next(
        line for line in out.splitlines() if "skill" in line and "mode" in line
    )
    for column in ("mode", "scored", "lift", "outcome"):
        assert column in header, f"{column} missing from the header: {header!r}"
    row = next(
        line for line in out.splitlines() if line.startswith("iris-connectivity")
    )
    assert "judge" in row
    assert "24/24" in row, f"scored is both arms summed: {row!r}"
    assert "held" in row


def test_a_partly_unscored_skill_shows_its_denominator(capsys):
    """`22/24` is a visible fact in the table, not a footnote nobody reads."""
    arms = {"baseline": arm(0.38), "skill": arm(0.50, unscored=2)}
    run = make_eval_run([make_result("objectscript-review", lift=0.12, arms=arms)])
    print_summary(run)
    row = next(
        line
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("objectscript-review")
    )
    assert "22/24" in row


def test_no_comparison_prints_a_dash_and_a_flat_one_prints_a_number(capsys):
    run = make_eval_run(
        [
            make_result(
                "objectscript-review",
                lift=0.12,
                outcome="not_comparable",
                outcome_reason="task_ids differ",
                delta=None,
            ),
            make_result("iris-connectivity", lift=0.29, outcome="held", delta=0.0),
        ]
    )
    print_summary(run)
    lines = capsys.readouterr().out.splitlines()
    refused = next(line for line in lines if line.startswith("objectscript-review"))
    flat = next(line for line in lines if line.startswith("iris-connectivity"))
    assert "—" in refused, f"no comparison must not print a number: {refused!r}"
    assert "0.00" in flat, f"a flat comparison is a measurement: {flat!r}"


def test_a_not_comparable_row_prints_its_reason(capsys):
    run = make_eval_run(
        [
            make_result(
                "objectscript-review",
                lift=0.12,
                outcome="not_comparable",
                outcome_reason="scorer_model differs: claude-haiku-4-5 → claude-sonnet-4-6",
            )
        ]
    )
    print_summary(run)
    out = capsys.readouterr().out
    assert "not comparable" in out, "the enum is read as English in the table"
    assert "scorer_model differs" in out


def test_a_changed_tool_surface_prints_beside_the_delta(capsys):
    run = make_eval_run(
        [
            make_result(
                "objectscript-review",
                lift=0.12,
                delta=0.02,
                surface_note="tool surface 1.3.0+000000000000 → 1.4.1+fa0b694f8725",
            )
        ]
    )
    print_summary(run)
    out = capsys.readouterr().out
    assert "1.3.0+000000000000 → 1.4.1+fa0b694f8725" in out
    assert "held" in out, "the annotation must not suppress the comparison"


def test_a_changed_driver_prints_beside_the_delta(capsys):
    """120 FR-012. The Δ across a harness swap is readable only if the swap is on the page."""
    run = make_eval_run(
        [
            make_result(
                "objectscript-review",
                lift=0.12,
                delta=0.02,
                driver_note="driver opencode 0.14.3 → prime-agent 0.4.1",
            )
        ]
    )
    print_summary(run)
    out = capsys.readouterr().out
    assert "opencode 0.14.3 → prime-agent 0.4.1" in out
    assert "held" in out


def test_the_footer_prints_on_a_green_run_too(capsys):
    """The broken run printed none of these four lines, which is why it looked normal."""
    run = make_eval_run([make_result("iris-connectivity", lift=0.29, delta=0.01)])
    print_summary(run)
    out = capsys.readouterr().out
    assert "scorer: claude-sonnet-4-6" in out
    assert "requested us.anthropic.claude-sonnet-4-6" in out
    assert "tool surface: 1.4.1+fa0b694f8725" in out
    assert "threshold: 0.20" in out
    assert "unscored: 0/24" in out
    assert "run valid: yes" in out


def test_the_footer_reports_the_unscored_share_over_all_items(capsys):
    run = make_eval_run(
        [
            make_result(
                "objectscript-review",
                lift=0.12,
                arms={"baseline": arm(0.38), "skill": arm(0.50, unscored=2)},
            ),
            make_result("iris-connectivity", lift=0.29),
        ]
    )
    print_summary(run)
    out = capsys.readouterr().out
    assert "unscored: 2/48" in out
    assert "4.2%" in out


def test_an_invalid_run_says_so_in_the_footer(capsys):
    run = make_eval_run(
        [make_result("objectscript-review", lift=None, outcome="not_comparable")],
        run_valid=False,
    )
    print_summary(run)
    assert "run valid: no" in capsys.readouterr().out


def test_the_reruns_line_prints_only_when_there_was_a_rerun(capsys):
    clean = make_eval_run([make_result("iris-connectivity", lift=0.29)])
    print_summary(clean)
    assert "re-runs merged" not in capsys.readouterr().out

    merged = make_eval_run(
        [make_result("iris-connectivity", lift=0.29)],
        reruns={"iris-connectivity": "2026-09-12T034002Z"},
    )
    print_summary(merged)
    out = capsys.readouterr().out
    assert "re-runs merged: iris-connectivity" in out
    assert "2026-09-12T034002Z" in out, "the discarded run_id is the point of the line"


def test_a_skill_with_no_coverage_is_still_named(capsys):
    """It moved from a row of dashes to the footer list, but it is never dropped."""
    run = make_eval_run([make_result("iris-docs", no_coverage=True)])
    print_summary(run, ladder_tasks={})
    out = capsys.readouterr().out
    assert "not graded anywhere (1): iris-docs" in out


# ---------------------------------------------------------------------------
# 121 T013 — every printed lift carries what it took to measure it
# ---------------------------------------------------------------------------


def row_for(out: str, skill: str) -> str:
    return next(line for line in out.splitlines() if line.startswith(skill))


def test_the_header_names_the_pairs_and_mde_columns(capsys):
    """The columns exist in the header, so a reader knows what the numbers beside a lift are."""
    print_summary(make_eval_run([make_result("iris-connectivity", lift=0.28)]))
    out = capsys.readouterr().out
    header = next(
        line for line in out.splitlines() if "lift" in line and "mode" in line
    )
    for column in ("lift", "pairs", "mde"):
        assert column in header, f"{column} missing from the header: {header!r}"


def test_a_printed_lift_carries_its_item_count_and_its_mde(capsys):
    """Governance detector 1, at the one place a lift reaches a human."""
    print_summary(
        make_eval_run([make_result("iris-connectivity", lift=0.28, delta=0.04)])
    )
    row = row_for(capsys.readouterr().out, "iris-connectivity")
    assert "+0.28" in row
    assert str(POWERED["n_pairs"]) in row, f"the item count is missing: {row!r}"
    assert f"{POWERED['mde']:.2f}" in row, f"the MDE is missing: {row!r}"


def test_a_lift_with_no_comparison_recorded_is_withheld_and_the_reason_printed(capsys):
    """Refusing to format it is the refusal. A lift with no resolution beside it is the bug."""
    run = make_eval_run([make_result("iris-connectivity", lift=0.28, comparison=None)])
    print_summary(run)
    out = capsys.readouterr().out
    row = row_for(out, "iris-connectivity")
    assert "0.28" not in row, f"an unaccompanied lift must not print: {row!r}"
    assert "no comparison recorded" in out


def test_an_underpowered_comparison_prints_as_underpowered_and_never_as_a_pass(capsys):
    """FR-008 in the table. `held` on eight pairs is the reading that failed three nightlies."""
    run = make_eval_run(
        [
            make_result(
                "iris-connectivity",
                lift=0.50,
                delta=0.30,
                outcome="held",
                comparison=UNDERPOWERED,
            )
        ]
    )
    print_summary(run)
    row = row_for(capsys.readouterr().out, "iris-connectivity")
    assert "too few runs to tell" in row
    assert (
        "held" not in row
    ), f"underpowered replaces the pass, it does not annotate it: {row!r}"


def test_an_underpowered_row_still_shows_the_pairs_it_had(capsys):
    """The verdict is checkable from the row: 8 pairs against the floor it names."""
    run = make_eval_run(
        [make_result("iris-connectivity", lift=0.50, comparison=UNDERPOWERED)]
    )
    print_summary(run)
    out = capsys.readouterr().out
    row = row_for(out, "iris-connectivity")
    assert str(UNDERPOWERED["n_pairs"]) in row
    assert str(UNDERPOWERED["floor"]) in out


def test_an_underpowered_regression_is_not_counted_as_a_regression(capsys):
    """A drop the harness cannot see is not a regression, and the row must not call it one."""
    run = make_eval_run(
        [
            make_result(
                "iris-connectivity",
                lift=0.10,
                delta=-0.40,
                outcome="underpowered",
                comparison=UNDERPOWERED,
            )
        ]
    )
    print_summary(run)
    row = row_for(capsys.readouterr().out, "iris-connectivity")
    assert "too few runs to tell" in row
    assert "regress" not in row.lower()


def test_an_indistinguishable_comparison_says_so_beside_the_outcome(capsys):
    """Powered, and the interval contains zero. `held` alone would overstate it."""
    flat = comparison_over(b=8, c=8, both_pass=20, both_fail=44)
    assert flat["verdict"] == "indistinguishable"
    run = make_eval_run(
        [make_result("iris-connectivity", lift=0.0, delta=0.0, comparison=flat)]
    )
    print_summary(run)
    row = row_for(capsys.readouterr().out, "iris-connectivity")
    assert "indistinguishable" in row


def test_zero_discordance_prints_no_mde_rather_than_a_perfect_one(capsys):
    """`0.00` would claim the arms bought perfect resolution. They bought none."""
    agreed = comparison_over(b=0, c=0, both_pass=20, both_fail=20)
    assert agreed["mde"] is None
    run = make_eval_run([make_result("iris-connectivity", lift=0.0, comparison=agreed)])
    print_summary(run)
    row = row_for(capsys.readouterr().out, "iris-connectivity")
    assert "n/a" in row, f"a missing MDE is not a zero MDE: {row!r}"


def test_the_footer_threshold_is_the_declared_gate_threshold(capsys):
    print_summary(make_eval_run([make_result("iris-connectivity", lift=0.28)]))
    out = capsys.readouterr().out
    assert f"threshold: {GATE_THRESHOLD:.2f}" in out
    assert "threshold: 0.05" not in out


def test_the_gate_path_holds_no_005_threshold():
    """T013's third clause, as a scan of the code rather than the prose.

    The literal is what matters: the modules are free to explain in a comment what 0.05 used to
    do, and `stats.py` is excluded because its 0.05 is a confidence level rather than a gate.
    """
    import ast

    import tests.e2e.skill_eval.evaluator as evaluator
    import tests.e2e.skill_eval.lift as lift
    import tests.e2e.skill_eval.reporter as reporter
    from tests.e2e.skill_eval import __main__ as cli
    from tests.e2e.skill_eval import comparison as comparison_module

    for module in (reporter, evaluator, lift, cli, comparison_module):
        tree = ast.parse(open(module.__file__).read())
        literals = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and node.value == 0.05
        ]
        assert not literals, (
            f"{os.path.basename(module.__file__)} still carries a 0.05 threshold literal; "
            "the gate threshold is GATE_THRESHOLD and the item floor is FR-008's"
        )


def test_the_progress_line_carries_the_pairs_and_mde_of_the_lift_it_prints():
    """The per-skill line the nightly log is read from, which used to print a bare lift.

    `[iris-connectivity] lift=0.5 (16/16 scored)` was the first number a reader saw, and 16
    scored items is 8 task-pairs — a fifth of the floor. The line said nothing about that.
    """
    line = progress_line(
        "iris-connectivity",
        {"lift": 0.28, "items_scored": 200, "items_unscored": 0, "comparison": POWERED},
    )
    assert "iris-connectivity" in line
    assert "0.28" in line
    assert f"{POWERED['n_pairs']} pairs" in line
    assert f"{POWERED['mde']:.2f}" in line
    assert "200/200 scored" in line


def test_the_progress_line_of_an_underpowered_run_says_so():
    line = progress_line(
        "iris-connectivity",
        {
            "lift": 0.50,
            "items_scored": 16,
            "items_unscored": 0,
            "comparison": UNDERPOWERED,
        },
    )
    assert "underpowered" in line
    assert str(UNDERPOWERED["floor"]) in line


def test_the_progress_line_withholds_a_lift_it_cannot_qualify():
    """No comparison, no number: the same refusal the table makes, at the earlier call site."""
    line = progress_line(
        "iris-connectivity", {"lift": 0.28, "items_scored": 16, "items_unscored": 0}
    )
    assert "0.28" not in line
    assert "no comparison" in line


def test_the_progress_line_of_a_skill_that_measured_nothing_says_that():
    line = progress_line(
        "iris-docs", {"lift": None, "items_scored": 0, "items_unscored": 12}
    )
    assert "no lift" in line
    assert "0/12 scored" in line


def test_the_json_result_carries_the_comparison(tmp_path):
    """`shard.py` merges these files and the report reads them; the MDE must survive the trip."""
    run = make_eval_run([make_result("iris-connectivity", lift=0.28, delta=0.04)])
    data = json.loads(open(write_result(run, str(tmp_path))).read())
    comparison = data["skills"][0]["comparison"]
    assert comparison["n_pairs"] == POWERED["n_pairs"]
    assert comparison["mde"] == pytest.approx(POWERED["mde"])
    assert comparison["verdict"] == POWERED["verdict"]


# ---------------------------------------------------------------------------
# 130 round 3 — a report a person can read
# ---------------------------------------------------------------------------
#
# The first valid re-baseline (2026-09-27T204612) printed "withdrawn (broken_check): graded through
# lift.format_transcript's 500-character cap" under five skills that had just been measured cleanly.
# The note was about the old baseline entry, which is why there was no Δ, but it sat under a fresh
# figure and read as a verdict on it. The same table said "FR-008" twice on some rows, printed one
# tool-surface line nine times, and listed 26 skills as "no coverage" when some are graded by the
# ladder. The fixture is that run's result file, unedited.

FIXTURE_RUN = os.path.join(
    os.path.dirname(__file__), "fixtures", "skill-eval-2026-09-27T204612.json"
)

#: What `ladder_coverage()` read off `tests/e2e/tasks/benchmark/skills` on 2026-09-28.
LADDER = {
    "objectscript-guardrails": [
        "SKILL-01",
        "SKILL-02",
        "SKILL-03",
        "SKILL-04",
        "SKILL-05",
        "SKILL-17",
    ],
    "objectscript-unit-test": ["SKILL-14"],
    "iris-query-plans": ["SKILL-13", "SKILL-20"],
    "objectscript-list-patterns": ["SKILL-06", "SKILL-07", "SKILL-10"],
}


def load_fixture_run() -> EvalRun:
    with open(FIXTURE_RUN) as f:
        data = json.load(f)
    skills = [SkillResult(**entry) for entry in data.pop("skills")]
    return EvalRun(skills=skills, **data)


def fixture_report(capsys, ladder=LADDER) -> str:
    print_summary(load_fixture_run(), ladder_tasks=ladder)
    return capsys.readouterr().out


def test_the_real_run_prints_no_triage_jargon(capsys):
    out = fixture_report(capsys)
    for word in (
        "FR-008",
        "broken_check",
        "too_easy",
        "not_helped",
        "mde_paired",
        "discordant",
        "harness's own resolution",
    ):
        assert word not in out, f"{word!r} is in the report:\n{out}"


def test_a_measured_row_does_not_carry_the_old_entrys_withdrawal(capsys):
    """The five measured rows get one plain line saying why there is no Δ, not the old verdict."""
    out = fixture_report(capsys)
    assert "withdrawn (" not in out
    assert "graded through" not in out
    assert "first figure that stands: the old baseline figure was withdrawn" in out


def test_an_underpowered_row_names_its_pairs_and_floor_once_in_words(capsys):
    out = fixture_report(capsys)
    row = row_for(out, "iris-vector-ai")
    assert "too few runs to tell (6 of 96 pairs needed)" in row, row
    assert out.count("floor of 96") == 0
    assert out.count("6 of 96") == 1


def test_a_tool_surface_change_shared_by_every_row_prints_once(capsys):
    out = fixture_report(capsys)
    assert out.count("1.4.1+fa0b694f8725 → 1.4.2+fa0b694f8725") == 1, out


def test_both_arms_at_zero_says_so(capsys):
    row = row_for(fixture_report(capsys), "objectscript-sql-patterns")
    assert "both arms fail every task" in row, row


def test_a_withdrawn_skill_that_did_not_run_names_its_ladder_tasks(capsys):
    out = fixture_report(capsys)
    row = row_for(out, "objectscript-guardrails")
    assert "not run here" in row, row
    assert "tasks too easy: the agent passes them without the skill" in out
    assert "graded by the ladder: SKILL-01–05, SKILL-17" in out
    assert "graded by the ladder: SKILL-14" in out
    assert "no working tasks here" in out


def test_a_withdrawn_skill_with_no_ladder_task_says_so(capsys):
    out = fixture_report(capsys, ladder={})
    assert "not graded by the ladder either" in out


def test_uncovered_skills_are_split_by_ladder_coverage(capsys):
    out = fixture_report(capsys)
    assert not any(line.startswith("iris-docs") for line in out.splitlines())
    ladder_line = next(
        line
        for line in out.splitlines()
        if line.startswith("graded only by the ladder")
    )
    assert "iris-query-plans (SKILL-13, SKILL-20)" in ladder_line
    nowhere = next(
        line for line in out.splitlines() if line.startswith("not graded anywhere")
    )
    assert "iris-docs" in nowhere and "iris-query-plans" not in nowhere


def test_a_long_skill_name_does_not_run_into_the_next_column(capsys):
    name = "iris-container-graceful-shutdown-and-more"
    print_summary(make_eval_run([make_result(name, lift=0.28)]), ladder_tasks={})
    row = row_for(capsys.readouterr().out, name)
    assert row.startswith(name + " "), row


def test_the_header_says_whether_the_run_is_valid(capsys):
    out = fixture_report(capsys)
    header = out.strip().splitlines()[0]
    assert "valid, 0 of 84 items unscored" in header, header


def test_the_report_explains_pairs_and_mde(capsys):
    out = fixture_report(capsys)
    assert "pairs = task runs compared across both arms" in out
    assert "mde = the smallest lift that many pairs can detect" in out


def test_ladder_coverage_reads_the_skill_field_of_the_ladder_tasks():
    from tests.e2e.skill_eval.reporter import ladder_coverage

    coverage = ladder_coverage()
    assert "SKILL-14" in coverage["objectscript-unit-test"]
    assert {"SKILL-01", "SKILL-17"} <= set(coverage["objectscript-guardrails"])
    assert all(ids == sorted(ids) for ids in coverage.values())
