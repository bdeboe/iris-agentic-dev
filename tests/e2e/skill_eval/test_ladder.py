"""Unit tests for the graded ladder run — 121 T035/T037/T038, written before `ladder.py`.

The pilot answered a design question and was allowed to be small and unpublishable. This run answers
the published one, so three things the pilot never had to do are the whole subject here:

- **The holdout side only.** A figure over a train task is a figure over something that was tuned
  while someone looked at it. `split.py` knows the sides; the runner must refuse before spending money,
  not after.
- **Repeats have to be reduced by a stated rule.** Two runs of one task in one arm can disagree, and
  "did this arm pass this task" then needs an answer that was written down before the data arrived.
- **Time-to-solve, not just pass/fail.** The pilot's bare arm was killed on the 300 s clock in 5 of
  its 7 discordant pairs, so "bare failed" partly means "bare ran out of clock". A figure that hides
  that is describing the timeout.

Nothing here starts a session. The subject is the bookkeeping between `pilot.run_one` and a
publishable table.
"""

import pytest

from tests.e2e.skill_eval.arms import BARE, TOOLS, TOOLS_SKILLS, skill_ladder
from tests.e2e.skill_eval.comparison import Verdict
from tests.e2e.skill_eval.pilot import ArmRun
from tests.e2e.skill_eval.split import Split, SplitLeak


def run(
    task_id,
    arm,
    passed,
    *,
    seconds=40.0,
    session_seconds=30.0,
    timed_out=False,
    reason=None,
    run_index=0,
):
    return ArmRun(
        task_id=task_id,
        arm=arm,
        passed=passed,
        reason=reason,
        timed_out=timed_out,
        tool_calls=3,
        seconds=seconds,
        session_seconds=session_seconds,
        run_index=run_index,
    )


def holdout_ids(n, prefix="CORPUS"):
    return [f"{prefix}-{i:02d}" for i in range(1, n + 1)]


def a_split(holdout, train=("CORPUS-99",)):
    return Split(train=tuple(train), holdout=tuple(holdout))


# --- the holdout gate, before any money is spent --------------------------------------------------


def test_the_runner_takes_only_holdout_tasks():
    from tests.e2e.skill_eval import ladder

    split = a_split(["CORPUS-01", "CORPUS-02"], train=["CORPUS-03"])
    kept = ladder.holdout_only(
        [FakeTask("CORPUS-01"), FakeTask("CORPUS-03"), FakeTask("CORPUS-02")],
        split=split,
    )
    assert [task.id for task in kept] == ["CORPUS-01", "CORPUS-02"]


def test_a_task_in_neither_side_of_the_split_stops_the_run():
    """An unknown ID is not a holdout task by default. `split.toml` covers the whole corpus, so a task
    it does not name is a task someone added without deciding which side it is on."""
    from tests.e2e.skill_eval import ladder

    with pytest.raises(SplitLeak) as caught:
        ladder.holdout_only([FakeTask("CORPUS-77")], split=a_split(["CORPUS-01"]))
    assert "CORPUS-77" in str(caught.value)


def test_a_holdout_set_too_small_to_publish_refuses_before_the_first_session():
    """FR-008's floor is 37 paired items. Running 20 tasks costs real money and buys a figure the
    publish gate will refuse afterwards, which is the worst of both."""
    from tests.e2e.skill_eval import ladder

    tasks = [FakeTask(i) for i in holdout_ids(20)]
    with pytest.raises(ladder.LadderRefused) as caught:
        ladder.assert_publishable_corpus(tasks)
    assert "37" in str(caught.value) and "20" in str(caught.value)


def test_a_holdout_set_at_the_floor_is_allowed():
    from tests.e2e.skill_eval import ladder

    tasks = [FakeTask(i) for i in holdout_ids(37)]
    assert ladder.assert_publishable_corpus(tasks) is tasks


def test_the_skills_ladder_is_exempt_from_the_publication_floor():
    """Twelve purpose-built tasks cannot reach 37, and the stop rule for them is a count comparison
    rather than an interval — `b <= c` is a real negative whatever the MDE says. The exemption is
    explicit and the figure it produces is labelled, rather than the floor being quietly lowered."""
    from tests.e2e.skill_eval import ladder

    tasks = [FakeTask(i) for i in holdout_ids(12, prefix="SKILL")]
    assert ladder.assert_publishable_corpus(tasks, floor=None) is tasks


# --- repeats reduce by a rule that was stated first -----------------------------------------------


def test_one_run_per_arm_reduces_to_that_run():
    from tests.e2e.skill_eval import ladder

    assert ladder.arm_verdict([run("CORPUS-01", "tools", True)]) is True
    assert ladder.arm_verdict([run("CORPUS-01", "tools", False)]) is False


def test_a_task_an_arm_passed_twice_passed():
    from tests.e2e.skill_eval import ladder

    runs = [
        run("CORPUS-01", "tools", True, run_index=0),
        run("CORPUS-01", "tools", True, run_index=1),
    ]
    assert ladder.arm_verdict(runs) is True


def test_a_split_decision_counts_as_a_failure_and_says_why():
    """Strict-and, not majority. An arm that solves a task half the time has not solved it, and the
    alternative rule — pass if any run passed — turns the noisier arm into the better one."""
    from tests.e2e.skill_eval import ladder

    runs = [
        run("CORPUS-01", "tools", True, run_index=0),
        run("CORPUS-01", "tools", False, run_index=1),
    ]
    assert ladder.arm_verdict(runs) is False


def test_an_arm_with_nothing_scored_is_a_hole_not_a_failure():
    from tests.e2e.skill_eval import ladder

    runs = [run("CORPUS-01", "bare", None, reason="the session did not run")]
    assert ladder.arm_verdict(runs) is None


def test_an_unscored_repeat_does_not_drag_down_a_scored_one():
    """A harness fault in run 2 must not convert a pass into a fail. The rule is over scored runs."""
    from tests.e2e.skill_eval import ladder

    runs = [
        run("CORPUS-01", "tools", True, run_index=0),
        run("CORPUS-01", "tools", None, reason="the daemon died", run_index=1),
    ]
    assert ladder.arm_verdict(runs) is True


# --- the comparisons -------------------------------------------------------------------------------


def three_arm_runs(n=40, bare_passes=0, tools_passes=None, skills_passes=None):
    """`n` tasks in three arms. `bare` fails everything by default, tools pass the first
    `tools_passes`, tools+skills the first `skills_passes`."""
    tools_passes = n if tools_passes is None else tools_passes
    skills_passes = tools_passes if skills_passes is None else skills_passes
    runs = []
    for index, task_id in enumerate(holdout_ids(n)):
        runs.append(run(task_id, BARE.name, index < bare_passes, session_seconds=210.0))
        runs.append(
            run(task_id, TOOLS.name, index < tools_passes, session_seconds=60.0)
        )
        runs.append(
            run(task_id, TOOLS_SKILLS.name, index < skills_passes, session_seconds=55.0)
        )
    return runs


def test_each_adjacent_pair_is_one_result_comparison():
    from tests.e2e.skill_eval import ladder

    comparisons = ladder.ladder_comparisons(
        three_arm_runs(), arms=(BARE, TOOLS, TOOLS_SKILLS)
    )
    assert [(c.arm_a, c.arm_b) for c in comparisons] == [
        ("bare", "tools"),
        ("tools", "tools+skills"),
    ]
    assert all(c.purpose == "result" for c in comparisons), (
        "the pilot's comparisons were design decisions; these are the published figures"
    )


def test_a_ladder_figure_goes_through_the_holdout_publish_gate():
    from tests.e2e.skill_eval import ladder

    # 8 of 40 discordant: discordance 0.20, which is the rate FR-008's floor of 37 was derived at, so
    # the figure is exactly powered rather than accidentally so.
    runs = three_arm_runs(n=40, tools_passes=8)
    comparisons = ladder.ladder_comparisons(runs, arms=(BARE, TOOLS, TOOLS_SKILLS))
    split = a_split(holdout_ids(40))
    published = ladder.publishable(comparisons, split=split)
    assert published[0].verdict is Verdict.PASSED
    # tools -> tools+skills has no discordant pair here, so it bought no resolution and is not
    # publishable. It appears in the report as that, not as a lift of 0.00.
    assert [c.arm_a for c in published] == ["bare"]


def test_a_train_task_in_the_pairs_stops_the_publish_step():
    from tests.e2e.skill_eval import ladder

    # 8 of 40 discordant: discordance 0.20, which is the rate FR-008's floor of 37 was derived at, so
    # the figure is exactly powered rather than accidentally so.
    runs = three_arm_runs(n=40, tools_passes=8)
    comparisons = ladder.ladder_comparisons(runs, arms=(BARE, TOOLS))
    split = a_split(holdout_ids(39), train=["CORPUS-40"])
    with pytest.raises(SplitLeak) as caught:
        ladder.publishable(comparisons, split=split, strict=True)
    assert "CORPUS-40" in str(caught.value)


def test_an_arm_that_scored_nothing_raises_rather_than_pairing_as_a_failure():
    from tests.e2e.skill_eval import ladder

    runs = [run(task_id, TOOLS.name, True) for task_id in holdout_ids(40)]
    runs += [
        run(task_id, BARE.name, None, reason="contaminated")
        for task_id in holdout_ids(40)
    ]
    with pytest.raises(ladder.LadderRefused) as caught:
        ladder.ladder_comparisons(runs, arms=(BARE, TOOLS))
    assert "bare" in str(caught.value)


# --- time-to-solve ---------------------------------------------------------------------------------


def test_time_to_solve_is_measured_over_the_sessions_that_solved_it():
    """Averaging a timeout into a solve time produces a number that is neither. The killed sessions
    are counted separately, which is the fact the pilot's bare arm needed: 5 of its 7 discordant pairs
    were sessions that ran out of clock rather than sessions that answered wrongly."""
    from tests.e2e.skill_eval import ladder

    runs = [
        run("CORPUS-01", "tools", True, session_seconds=30.0),
        run("CORPUS-02", "tools", True, session_seconds=50.0),
        run("CORPUS-03", "tools", False, session_seconds=300.0, timed_out=True),
    ]
    stats = ladder.solve_time(runs)["tools"]
    assert stats["solved"] == 2
    assert stats["median_solve_seconds"] == pytest.approx(40.0)
    assert stats["timed_out"] == 1
    assert stats["censored_note"]


def test_an_arm_that_solved_nothing_reports_no_solve_time_rather_than_zero():
    from tests.e2e.skill_eval import ladder

    stats = ladder.solve_time([run("CORPUS-01", "bare", False, timed_out=True)])["bare"]
    assert stats["solved"] == 0
    assert stats["median_solve_seconds"] is None


def test_solve_time_is_reported_per_arm():
    from tests.e2e.skill_eval import ladder

    stats = ladder.solve_time(three_arm_runs(n=4))
    assert set(stats) == {"bare", "tools", "tools+skills"}
    assert stats["tools"]["median_solve_seconds"] == pytest.approx(60.0)


# --- the report ------------------------------------------------------------------------------------


def test_the_report_carries_provenance_and_the_item_counts():
    from tests.e2e.skill_eval import ladder

    # 8 of 40 discordant: discordance 0.20, which is the rate FR-008's floor of 37 was derived at, so
    # the figure is exactly powered rather than accidentally so.
    runs = three_arm_runs(n=40, tools_passes=8)
    written = ladder.report(
        runs,
        arms=(BARE, TOOLS, TOOLS_SKILLS),
        split=a_split(holdout_ids(40)),
        model="openai/gpt-4.1",
        container="iris-dev-iris",
        repeats=1,
    )
    assert written["purpose"] == "result"
    assert written["scoring_mode"] == "machine"
    assert written["provenance"]["agent_model"] == "openai/gpt-4.1"
    assert written["provenance"]["item_counts"] == {
        "tasks": 40,
        "arms": 3,
        "repeats": 1,
        "sessions": 120,
    }
    assert written["provenance"]["container"] == "iris-dev-iris"
    assert "corpus_commit" in written["provenance"]


def test_every_comparison_in_the_report_states_its_own_power():
    """G1 again, one level up: a reader of the JSON must not be able to find a lift without the item
    count, the MDE and the verdict beside it."""
    from tests.e2e.skill_eval import ladder

    written = ladder.report(
        three_arm_runs(n=40, tools_passes=32),
        arms=(BARE, TOOLS, TOOLS_SKILLS),
        split=a_split(holdout_ids(40)),
        model="m",
        container="c",
        repeats=1,
    )
    for record in written["comparisons"]:
        assert {"lift", "n_pairs", "mde", "verdict", "publishable"} <= set(record)


def test_the_report_keeps_the_unscored_runs_with_their_reasons():
    from tests.e2e.skill_eval import ladder

    # 8 of 40 discordant: discordance 0.20, which is the rate FR-008's floor of 37 was derived at, so
    # the figure is exactly powered rather than accidentally so.
    runs = three_arm_runs(n=40, tools_passes=8)
    runs.append(run("CORPUS-41", "bare", None, reason="the arm was contaminated"))
    written = ladder.report(
        runs,
        arms=(BARE, TOOLS, TOOLS_SKILLS),
        split=a_split(holdout_ids(41)),
        model="m",
        container="c",
        repeats=1,
    )
    assert len(written["runs"]) == 121
    assert "the arm was contaminated" in [
        r["reason"] for r in written["runs"] if r["reason"]
    ]


def test_the_report_states_the_authorship_caveat_the_split_cannot_fix():
    """The corpus was written by the author of the tools it measures. The split file says so; the
    published artifact has to say so too, because the JSON is what gets quoted."""
    from tests.e2e.skill_eval import ladder

    written = ladder.report(
        three_arm_runs(n=40, tools_passes=32),
        arms=(BARE, TOOLS),
        split=a_split(holdout_ids(40)),
        model="m",
        container="c",
        repeats=1,
    )
    assert "author" in written["caveats"][0].lower()


# --- the per-skill ladder's stop rule, stated before the run --------------------------------------


def test_the_skills_stop_rule_is_declared_in_code_not_decided_afterwards():
    """ "If 12 purpose-built tasks give b <= c, that is a real negative about the skills." The rule is a
    function so that the answer cannot be renegotiated once the counts are in."""
    from tests.e2e.skill_eval import ladder

    assert ladder.skill_verdict(b=0, c=0) == "no effect"
    assert ladder.skill_verdict(b=1, c=3) == "harmful"
    assert ladder.skill_verdict(b=2, c=2) == "no effect"
    assert ladder.skill_verdict(b=5, c=0) == "helps"
    assert ladder.skill_verdict(b=3, c=2) == "inconclusive"


def test_the_per_skill_ladder_pairs_tools_against_tools_plus_one_skill():
    from tests.e2e.skill_eval import ladder

    lower, upper = skill_ladder("iris-sql")
    runs = []
    for index, task_id in enumerate(holdout_ids(6, prefix="SKILL")):
        runs.append(run(task_id, lower.name, False))
        runs.append(run(task_id, upper.name, index < 4))
    comparison = ladder.ladder_comparisons(runs, arms=(lower, upper))[0]
    assert (comparison.arm_a, comparison.arm_b) == ("tools", "tools+iris-sql")
    assert (comparison.b, comparison.c) == (4, 0)
    assert ladder.skill_verdict(b=comparison.b, c=comparison.c) == "helps"


class FakeTask:
    """Just an id. `holdout_only` and the floor check read nothing else, and building 40 real
    `GradedTask`s here would be testing the loader."""

    def __init__(self, task_id):
        self.id = task_id


def test_the_report_refuses_a_leaked_task_rather_than_dropping_it_quietly():
    """The runner filters to holdout before spending, so a train ID reaching the report is a harness
    bug. Dropping that comparison silently would publish the rest of the table as though the run were
    clean."""
    from tests.e2e.skill_eval import ladder

    runs = three_arm_runs(n=40, tools_passes=8)
    with pytest.raises(SplitLeak):
        ladder.report(
            runs,
            arms=(BARE, TOOLS),
            split=a_split(holdout_ids(39), train=["CORPUS-40"]),
            model="m",
            container="c",
            repeats=1,
        )


# --- the CLI ---------------------------------------------------------------------------------------


def test_the_cli_defaults_to_the_tools_ladder_and_one_repeat():
    from tests.e2e.skill_eval import ladder

    args = ladder.parse_args([])
    assert args.ladder == "tools"
    assert args.repeats == 1
    assert args.container == "iris-dev-iris"
    assert args.dry_run is False


def test_the_cli_takes_a_skill_for_the_per_skill_ladder():
    from tests.e2e.skill_eval import ladder

    args = ladder.parse_args(["--ladder", "skill", "--skill", "iris-sql"])
    assert (args.ladder, args.skill) == ("skill", "iris-sql")


def test_the_skill_ladder_without_a_skill_is_refused():
    """A per-skill run with no skill named would install the whole pack and report it as one skill's."""
    from tests.e2e.skill_eval import ladder

    with pytest.raises(SystemExit):
        ladder.parse_args(["--ladder", "skill"])


def test_the_cli_can_be_asked_for_the_estimate_without_spending_anything():
    from tests.e2e.skill_eval import ladder

    assert ladder.parse_args(["--dry-run"]).dry_run is True


# --- the pooled skills rung ------------------------------------------------------------------------
#
# The stop rule's `b >= 4` was written for twelve items, and the corpus has twelve skill tasks — but
# spread over four skills, 5/3/3/1. So `helps` is unreachable for three of the four rungs by item
# count alone, and a per-skill table is the wrong place to put the verdict. The twelve pair as twelve:
# every task runs against the arm holding its own skill, the pooled comparison is the headline, and the
# per-skill counts sit beside it as description with their item counts showing.


class FakeSkillTask:
    def __init__(self, task_id, skill):
        self.id = task_id
        self.skill = skill


SKILL_SPREAD = (
    [FakeSkillTask(f"SKILL-{i:02d}", "objectscript-guardrails") for i in range(1, 6)]
    + [
        FakeSkillTask(f"SKILL-{i:02d}", "objectscript-list-patterns")
        for i in range(6, 9)
    ]
    + [FakeSkillTask(f"SKILL-{i:02d}", "objectscript-sql-patterns") for i in range(9, 12)]
    + [FakeSkillTask("SKILL-12", "iris-sql")]
)


def spread_runs(passes):
    """One `tools` run and one own-skill run per task. `passes` names the task IDs the skill arm
    passed; the tools arm fails everything, so every task is a discordant pair for the skill."""
    runs = []
    for task in SKILL_SPREAD:
        runs.append(run(task.id, "tools", False))
        runs.append(run(task.id, f"tools+{task.skill}", task.id in passes))
    return runs


def test_the_pooled_rung_gives_each_task_the_arm_holding_its_own_skill():
    from tests.e2e.skill_eval import ladder

    lower, upper = ladder.pooled_skill_arms(FakeSkillTask("SKILL-12", "iris-sql"))
    assert lower is TOOLS
    assert (upper.skills, upper.skill_names) == (True, ("iris-sql",))


def test_the_pooled_comparison_pairs_all_twelve_across_four_skills():
    """Four arm names would pair as four thin comparisons. Under one name they are the twelve items
    the rule was written for."""
    from tests.e2e.skill_eval import ladder

    runs = spread_runs({f"SKILL-{i:02d}" for i in range(1, 6)})
    comparison = ladder.pooled_skill_comparison(runs)
    assert comparison.n_pairs == 12
    assert (comparison.b, comparison.c) == (5, 0)
    assert ladder.skill_verdict(b=comparison.b, c=comparison.c) == "helps"


def test_relabelling_for_the_pool_leaves_the_shared_tools_arm_alone():
    from tests.e2e.skill_eval import ladder

    relabelled = ladder.pooled_runs(spread_runs(set()))
    names = {r.arm for r in relabelled}
    assert names == {"tools", ladder.POOLED_ARM}


def test_the_pooled_rung_reports_no_effect_when_the_skill_wins_nothing():
    """The stop rule's whole point: twelve purpose-built tasks giving b <= c is the finding, not a
    reason to write more tasks."""
    from tests.e2e.skill_eval import ladder

    comparison = ladder.pooled_skill_comparison(spread_runs(set()))
    assert (comparison.b, comparison.c) == (0, 0)
    assert ladder.skill_verdict(b=comparison.b, c=comparison.c) == "no effect"


def test_the_per_skill_breakdown_shows_its_item_count_and_whether_helps_is_reachable():
    """A three-item rung cannot reach `helps` whatever the skill does. Printing its verdict without
    its item count would read as a finding about the document."""
    from tests.e2e.skill_eval import ladder

    rows = {
        row["skill"]: row
        for row in ladder.skill_breakdown(
            spread_runs({f"SKILL-{i:02d}" for i in range(1, 6)}), SKILL_SPREAD
        )
    }
    assert rows["objectscript-guardrails"]["pairs"] == 5
    assert rows["objectscript-guardrails"]["helps_reachable"] is True
    assert rows["objectscript-guardrails"]["verdict"] == "helps"
    assert rows["objectscript-list-patterns"]["pairs"] == 3
    assert rows["objectscript-list-patterns"]["helps_reachable"] is False
    assert rows["iris-sql"]["pairs"] == 1


def test_the_report_carries_the_pooled_comparison_and_the_breakdown_beside_it():
    from tests.e2e.skill_eval import ladder

    written = ladder.report(
        spread_runs({f"SKILL-{i:02d}" for i in range(1, 6)}),
        arms=(TOOLS,),
        pooled=True,
        tasks=SKILL_SPREAD,
        split=a_split(holdout_ids(12, prefix="SKILL")),
        model="m",
        container="c",
        repeats=1,
    )
    assert written["comparisons"][0]["arm_b"] == ladder.POOLED_ARM
    assert written["comparisons"][0]["n_pairs"] == 12
    assert written["skill_verdict"] == "helps"
    assert len(written["per_skill"]) == 4
    # The real arm names survive in the runs, or attribution cannot tell which skill was installed.
    assert "tools+iris-sql" in {r["arm"] for r in written["runs"]}


def test_a_pooled_report_is_not_held_to_the_publication_floor():
    """Twelve items will never reach 37 and were never meant to — `skill_verdict` is the rule, and the
    floor check exists to stop a lift being published, not a discordant count."""
    from tests.e2e.skill_eval import ladder

    written = ladder.report(
        spread_runs(set()),
        arms=(TOOLS,),
        pooled=True,
        tasks=SKILL_SPREAD,
        split=a_split(holdout_ids(12, prefix="SKILL")),
        model="m",
        container="c",
        repeats=1,
    )
    assert written["published"] == []


def test_the_cli_takes_skill_all_for_the_pooled_rung():
    from tests.e2e.skill_eval import ladder

    args = ladder.parse_args(["--ladder", "skill", "--skill", "all"])
    assert args.skill == "all"


def test_the_runner_resolves_a_per_task_arm_list_from_a_callable():
    """The pooled rung needs a different upper arm per task, so `run_ladder` takes either a fixed
    tuple or a function of the task. Tested here rather than through `run_ladder`, which would have to
    start twenty-four sessions to say the same thing."""
    from tests.e2e.skill_eval import ladder

    assert ladder.arms_for_task((BARE, TOOLS), FakeSkillTask("SKILL-01", "iris-sql")) == (
        BARE,
        TOOLS,
    )
    lower, upper = ladder.arms_for_task(
        ladder.pooled_skill_arms, FakeSkillTask("SKILL-01", "iris-sql")
    )
    assert upper.skill_names == ("iris-sql",)


def test_the_pooled_task_set_is_every_holdout_skill_task_and_each_one_names_a_skill():
    """A task in this set with no skill would run against an arm holding nothing and be counted as a
    pair anyway."""
    from tests.e2e.skill_eval import ladder

    tasks = ladder.pooled_skill_tasks()
    assert len(tasks) == 12
    assert all(task.skill for task in tasks)
    assert len({task.skill for task in tasks}) == 4
