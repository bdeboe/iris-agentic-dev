"""The graded ladder run — 121 T035, T037, T038.

The pilot decided whether to build this. This module runs it: the holdout side of the committed
corpus, every arm, machine-graded, and a figure that arrives with its own power and provenance
attached or does not arrive.

Everything mechanical is already built and reused rather than re-implemented. `pilot.run_one` runs one
task in one arm through the driver boundary and returns an `ArmRun`; `comparison.pair_arms` pairs on
task ID; `split.assert_holdout_only` refuses a leaked figure; `cost_estimator.assert_within_budget`
refuses an over-budget stage before the first session. What is new here is only what the pilot was
allowed to skip:

- **The holdout gate runs before the money.** `holdout_only` filters and `assert_publishable_corpus`
  checks the count against FR-008's floor, both before a session starts. A 20-task run costs real
  dollars and buys a figure the publish gate refuses afterwards.
- **Repeats reduce by a rule stated in advance.** `arm_verdict` is strict-and over the scored runs. An
  arm that solves a task half the time has not solved it, and the alternative — pass if any run passed
  — hands the win to whichever arm is noisier.
- **Time-to-solve is reported separately from pass/fail.** The pilot's bare arm was killed on the
  300 s clock in 5 of its 7 discordant pairs, so part of "bare failed" is "bare ran out of clock".
  `solve_time` measures over the sessions that solved the task and counts the killed ones beside it.

No statistics live here either. `stats.py` computes, `comparison.py` decides what a figure may claim.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from dataclasses import asdict

from tests.e2e.skill_eval import graded_task, provenance
from tests.e2e.skill_eval.arms import ARMS, TOOLS, Arm, installed_skill_names, skill_arm
from tests.e2e.skill_eval.comparison import (
    MINIMUM_FLOOR,
    Comparison,
    assert_publishable_from_holdout,
    pair_arms,
)
from tests.e2e.skill_eval.split import Split, assert_holdout_only, default_split

RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results"
)

#: The model every arm runs, held here rather than passed per arm: the arms are comparable to each
#: other because the model was the same in all of them.
LADDER_MODEL = "openai/gpt-4.1"

#: The same clock in every arm. A killed session counts as a failure — the task was not solved — and
#: `solve_time` records how often that happened so the figure can be read as what it is.
SESSION_TIMEOUT = 300

#: The one caveat the split cannot fix, carried in the artifact because the artifact is what gets
#: quoted. It is in `split.toml` too; a reader of the JSON should not have to find that file.
CAVEATS = (
    "The 42 corpus tasks were written by the author of the tools they measure. No description, prompt "
    "or skill was changed while looking at a result from a holdout task — that is what the split is "
    "for — but a corpus written by the tool's author is weaker evidence than a corpus written by "
    "someone else, and this figure should be read that way.",
    "A killed session counts as a task not solved. The timeout is part of the measurement, not a "
    "nuisance around it, so every arm's solve-time block states how many of its sessions hit it.",
)


class LadderRefused(RuntimeError):
    """The run must not start, or the figure must not be published. Raised before spending, wherever
    the check can be made before spending."""


class LadderAborted(LadderRefused):
    """The environment stopped answering, so the run stopped spending.

    Raised mid-run, which the parent class is not: every session before it is already on disk through
    `on_run`, and `resume.py` picks up from there.
    """


#: Consecutive sessions with no verdict before the run gives up. Three, because one unscored session is
#: a task whose check is wrong and two in a row can still be coincidence, while three consecutive
#: sessions that could not be graded means the thing doing the grading is gone.
UNSCORED_ABORT = 3


# --- before the money ------------------------------------------------------------------------------


def holdout_only(tasks, split: Split | None = None):
    """Keep the holdout-side tasks and refuse on an ID the split does not know.

    Filtering rather than raising on a train ID is deliberate: the corpus loader returns everything,
    and the runner's job is to run the publishable side. An ID in neither side is different — nobody
    decided which side it is on, so nothing vouches for it either way.
    """
    split = split or default_split()
    unknown = [task.id for task in tasks if split.side_of(task.id) is None]
    if unknown:
        assert_holdout_only(split, unknown)  # raises SplitLeak, naming them
    return [task for task in tasks if split.side_of(task.id) == "holdout"]


def assert_publishable_corpus(tasks, floor: int | None = MINIMUM_FLOOR):
    """Refuse a run too small to publish from, before it costs anything.

    `floor=None` exempts a ladder whose stop rule is not an interval. The twelve skill tasks cannot
    reach 37 and were never going to: their rule is `skill_verdict`, a comparison of discordant
    counts, which is a real answer at twelve items even though it is not a publishable lift. The
    exemption is a named argument rather than a lowered floor so the two kinds of figure stay
    distinguishable in the report.
    """
    if floor is None:
        return tasks
    if len(tasks) < floor:
        raise LadderRefused(
            f"{len(tasks)} holdout tasks is below FR-008's floor of {floor} paired items, so this run "
            "would buy a figure the publish gate refuses. Grow the corpus or run it as a design "
            "decision rather than paying for an underpowered result"
        )
    return tasks


# --- reducing the runs ----------------------------------------------------------------------------


def arm_verdict(runs) -> bool | None:
    """Did this arm solve this task? Strict-and over the scored runs; None if none were scored.

    Stated before the data arrived, which is the only time a rule like this is worth anything. The
    alternatives both have a bias: "any run passed" rewards variance, and "majority" needs a tie rule
    that is itself a choice. Strict-and says an arm that cannot do it twice cannot do it.
    """
    scored = [run for run in runs if run.passed is not None]
    if not scored:
        return None
    return all(bool(run.passed) for run in scored)


def arm_results(runs) -> dict[str, bool]:
    """Every task this arm scored, reduced across repeats."""
    by_task: dict[str, list] = {}
    for run in runs:
        by_task.setdefault(run.task_id, []).append(run)
    results = {}
    for task_id, task_runs in by_task.items():
        verdict = arm_verdict(task_runs)
        if verdict is not None:
            results[task_id] = verdict
    return results


def ladder_comparisons(runs, arms=ARMS) -> list[Comparison]:
    """One result comparison per adjacent pair of arms.

    An arm with nothing scored raises rather than pairing. Left alone it pairs as an arm that failed
    every task and the arm above it collects the credit — the 118 failure, one level up from the
    environment.
    """
    by_arm = {
        arm.name: arm_results([run for run in runs if run.arm == arm.name])
        for arm in arms
    }
    empty = [name for name, results in by_arm.items() if not results]
    if empty:
        raise LadderRefused(
            f"the {', '.join(empty)} arm produced no scored run at all, so there is nothing to pair. "
            "An arm of holes is not an arm that failed"
        )
    return [
        pair_arms(
            lower.name,
            upper.name,
            by_arm[lower.name],
            by_arm[upper.name],
            purpose="result",
        )
        for lower, upper in zip(arms, arms[1:])
    ]


def publishable(
    comparisons, split: Split | None = None, *, strict: bool = False
) -> list[Comparison]:
    """The comparisons that may appear in a published table.

    Two different refusals, treated differently on purpose. A leak is a fault in the run and raises
    however it is called when `strict`; an underpowered or zero-discordance comparison is a fact about
    what the corpus bought, and it is dropped from the published table and reported as itself.
    """
    split = split or default_split()
    kept = []
    for comparison in comparisons:
        try:
            kept.append(assert_publishable_from_holdout(comparison, split))
        except ValueError:
            continue  # not a publishable measurement; the report says which and why
        except Exception:
            if strict:
                raise
    return kept


# --- time-to-solve ---------------------------------------------------------------------------------


def arm_rates(runs) -> dict:
    """Per arm: how many tasks it solved out of how many were scored, with a 95% Wilson interval.

    T037's first column. Wilson rather than the normal approximation for one reason: the bare arm
    scored zero, and the normal interval at zero has zero width, which reads as certainty nobody has.

    The denominator is the scored sessions. An ungradeable session is not a failure, and putting it in
    the denominator would make an arm look worse the more often the container fell over.
    """
    from tests.e2e.skill_eval.stats import wilson_interval

    by_arm: dict[str, list] = {}
    for run in runs:
        by_arm.setdefault(run.arm, []).append(run)
    out = {}
    for arm, arm_runs in sorted(by_arm.items()):
        scored = [run for run in arm_runs if run.passed is not None]
        passed = sum(1 for run in scored if run.passed)
        interval = wilson_interval(passed, len(scored)) if scored else None
        out[arm] = {
            "sessions": len(arm_runs),
            "scored": len(scored),
            "unscored": len(arm_runs) - len(scored),
            "passed": passed,
            "rate": (passed / len(scored)) if scored else None,
            "interval": (
                None
                if interval is None
                else [round(interval[0], 4), round(interval[1], 4)]
            ),
            "interval_method": "Wilson score, 95%",
        }
    return out


def failure_modes(runs) -> dict:
    """Per arm, the three different things a failure can be.

    The bare arm's 0-for-30 is not one claim. Some of those sessions made a dozen calls with shell and
    curl and got the answer wrong; some returned in six seconds having called nothing, which is the
    model declining rather than failing; some were killed on the 300 s clock, where the honest reading
    is "not solved in five minutes" and not "cannot solve". Publishing the three as one number invites
    the reading that suits whoever quotes it.

    Unscored sessions are counted and kept out of `failed`, for the same reason they are kept out of a
    comparison: a check that could not run has not failed the task.
    """
    by_arm: dict[str, list] = {}
    for run in runs:
        by_arm.setdefault(run.arm, []).append(run)
    out = {}
    for arm, arm_runs in sorted(by_arm.items()):
        failed = [run for run in arm_runs if run.passed is False]
        killed = [run for run in failed if run.timed_out]
        # No tool call and no timeout: the session ended on its own having tried nothing. In the bare
        # arm that is a refusal, and it is evidence about the model, not about the tools.
        declined = [
            run for run in failed if not run.timed_out and (run.tool_calls or 0) == 0
        ]
        out[arm] = {
            "sessions": len(arm_runs),
            "failed": len(failed),
            "unscored": sum(1 for run in arm_runs if run.passed is None),
            "killed_on_the_clock": len(killed),
            "made_no_attempt": len(declined),
            "tried_and_failed": len(failed) - len(killed) - len(declined),
            "note": (
                f"{len(killed)} of {len(failed)} failures hit the {SESSION_TIMEOUT}s clock and "
                f"{len(declined)} ended with no tool call at all; only "
                f"{len(failed) - len(killed) - len(declined)} were an attempt that came back wrong"
            ),
        }
    return out


def solve_time(runs) -> dict:
    """Per arm: how long the sessions that solved the task took, and how many were killed trying.

    Deliberately not one mean over everything. A timeout is a censored observation — the true solve
    time is "longer than 300 s, unknown" — and averaging 300 into the solve times produces a number
    that is neither a solve time nor a failure rate.
    """
    by_arm: dict[str, list] = {}
    for run in runs:
        by_arm.setdefault(run.arm, []).append(run)
    out = {}
    for arm, arm_runs in sorted(by_arm.items()):
        solved = [run for run in arm_runs if run.passed]
        seconds = sorted(run.session_seconds for run in solved)
        timed_out = sum(1 for run in arm_runs if run.timed_out)
        out[arm] = {
            "sessions": len(arm_runs),
            "solved": len(solved),
            "median_solve_seconds": (
                round(statistics.median(seconds), 1) if seconds else None
            ),
            "mean_solve_seconds": (
                round(statistics.fmean(seconds), 1) if seconds else None
            ),
            "fastest_solve_seconds": round(seconds[0], 1) if seconds else None,
            "slowest_solve_seconds": round(seconds[-1], 1) if seconds else None,
            "timed_out": timed_out,
            "censored_note": (
                f"{timed_out} of {len(arm_runs)} sessions hit the {SESSION_TIMEOUT}s clock and count "
                "as tasks not solved; their true solve time is unknown and is not averaged in"
            ),
        }
    return out


# --- the skills stop rule, declared before the run ------------------------------------------------


def skill_verdict(*, b: int, c: int) -> str:
    """What the per-skill ladder is allowed to conclude from its discordant counts.

    Written down before the run, because the temptation afterwards is to grow the corpus until the
    sign turns. Twelve purpose-built tasks giving `b <= c` is a real negative about the skill
    documents, and this function is where that is said rather than argued.

    `helps` needs a margin, not just a sign: 3-2 over twelve items is noise, and calling it a help is
    the mistake the whole `Comparison` type exists to prevent.
    """
    if b <= c:
        return "harmful" if c > b else "no effect"
    if b >= 4 and c <= 1:
        return "helps"
    return "inconclusive"


#: The one name the twelve skill tasks' skill arms pair under. Four arm names would pair as four
#: comparisons of five, three, three and one, and `helps` needs `b >= 4` — so three of the four rungs
#: could not reach it whatever their skill did. The twelve are the twelve the rule was written for.
POOLED_ARM = "tools+its-own-skill"


def pooled_arm() -> Arm:
    """The pooled rung as an `Arm`, for `ladder_comparisons` and the report's arm list.

    `skill_names` is deliberately empty: no single list describes this arm, because each session
    installed the one skill its own task named. `per_skill` is where that is recorded.
    """
    return Arm(name=POOLED_ARM, tools=True, skills=True)


def pooled_skill_arms(task) -> tuple[Arm, Arm]:
    """The two arms one skill task runs: shared tools, then tools plus that task's own skill."""
    return (TOOLS, skill_arm(task.skill))


def pooled_runs(runs, *, pooled_name: str = POOLED_ARM):
    """Relabel every one-skill arm to the pooled name, leaving the shared `tools` arm alone.

    Copies rather than mutates, because the report keeps the real arm names in its `runs` list — the
    attribution join and the per-skill breakdown both need to know which skill was installed.
    """
    return [
        (
            type(run)(**{**asdict(run), "arm": pooled_name})
            if run.arm.startswith("tools+")
            else run
        )
        for run in runs
    ]


def pooled_skill_comparison(runs) -> Comparison:
    """The headline skills comparison: twelve pairs, each task against its own skill."""
    return ladder_comparisons(pooled_runs(runs), arms=(TOOLS, pooled_arm()))[0]


def skill_breakdown(runs, tasks) -> list[dict]:
    """Per-skill discordant counts, each with the item count that bounds what it can say.

    Descriptive, not a verdict on the document. The corpus spreads twelve tasks over four skills as
    5/3/3/1, so `helps_reachable` is False for three of them on item count alone — printing a verdict
    without that beside it would read as a finding about the skill.
    """
    skill_of = {task.id: getattr(task, "skill", None) for task in tasks}
    rows = []
    for skill in sorted({skill for skill in skill_of.values() if skill}):
        ids = {task_id for task_id, named in skill_of.items() if named == skill}
        comparison = ladder_comparisons(
            [run for run in runs if run.task_id in ids],
            arms=(TOOLS, skill_arm(skill)),
        )[0]
        rows.append(
            {
                "skill": skill,
                "pairs": comparison.n_pairs,
                "b": comparison.b,
                "c": comparison.c,
                "verdict": skill_verdict(b=comparison.b, c=comparison.c),
                # `helps` needs b >= 4, so a rung of three cannot reach it however good the skill is.
                "helps_reachable": comparison.n_pairs >= 4,
            }
        )
    return rows


# --- the report ------------------------------------------------------------------------------------


def report(
    runs,
    *,
    arms=ARMS,
    split: Split | None = None,
    model: str = LADDER_MODEL,
    container: str = "iris-dev-iris",
    repeats: int = 1,
    driver=None,
    skill_names=None,
    run_id: str | None = None,
    pooled: bool = False,
    tasks=None,
) -> dict:
    """The whole graded run in one shape, with everything a re-measurement needs (FR-020).

    `pooled` switches to the skills rung: the comparison is the twelve tasks against their own skills
    under one arm name, `skill_verdict` decides it instead of an interval, and `per_skill` carries the
    counts per document. `tasks` is only read for that breakdown.
    """
    split = split or default_split()
    if pooled:
        arms = (TOOLS, pooled_arm())
        comparisons = [pooled_skill_comparison(runs)]
    else:
        comparisons = ladder_comparisons(runs, arms=arms)
    # Strict: the runner filtered to the holdout side before spending anything, so a leaked ID here is
    # a bug in the harness and not a fact about the corpus. Raising costs nothing — `run_ladder`'s
    # `on_run` has already written every session to disk, so the report can be rebuilt after the fix.
    published = publishable(comparisons, split=split, strict=True)
    task_ids = sorted({run.task_id for run in runs})
    binary = provenance.resolve_binary()

    record = provenance.Provenance(
        run_id=run_id or f"ladder-{time.strftime('%Y%m%dT%H%M%S')}",
        task_ids=task_ids,
        scoring_mode="machine",
        scorer_model=None,
        scorer_model_requested=None,
        tool_surface=provenance.tool_surface(binary),
        runs=repeats,
        agent_model=model,
        item_counts={
            "tasks": len(task_ids),
            "arms": len(arms),
            "repeats": repeats,
            "sessions": len(task_ids) * len(arms) * repeats,
        },
        **provenance.driver_identity(driver),
        **provenance.container_identity(container),
        **provenance.corpus_identity(),
    )

    return {
        "purpose": "result",
        "scoring_mode": "machine",
        "note": (
            "Every task is graded by an ObjectScript check printing PASS or FAIL against live IRIS. "
            "No model scores anything, and a check whose output is neither leaves the task unscored "
            "rather than failed."
        ),
        "caveats": list(CAVEATS),
        "timeout_seconds": SESSION_TIMEOUT,
        "arms": [arm.name for arm in arms],
        "skills_installed": {
            arm.name: list(installed_skill_names(arm, tuple(skill_names or ())))
            for arm in arms
            if arm.skills
        },
        "provenance": record.to_dict(),
        "arm_rates": arm_rates(runs),
        "solve_time": solve_time(runs),
        "failure_modes": failure_modes(runs),
        "comparisons": [comparison.to_dict() for comparison in comparisons],
        "published": [comparison.summary() for comparison in published],
        "runs": [asdict(run) for run in runs],
        **(
            {
                "skill_verdict": skill_verdict(b=comparisons[0].b, c=comparisons[0].c),
                "skill_verdict_rule": (
                    "Discordant counts, not an interval: twelve items cannot reach the publication "
                    "floor of 37 and an interval over twelve contains zero whatever happens. `helps` "
                    "needs b >= 4 and c <= 1; b <= c is a real negative about the documents. Fixed in "
                    "plan.md and in `skill_verdict` before the first skill session ran."
                ),
                "per_skill": skill_breakdown(runs, tasks or ()),
            }
            if pooled
            else {}
        ),
    }


# --- the run ---------------------------------------------------------------------------------------


def run_ladder(
    tasks,
    arms=ARMS,
    *,
    repeats: int = 1,
    openai_api_key: str | None = None,
    model: str = LADDER_MODEL,
    timeout: int = SESSION_TIMEOUT,
    skill_names=None,
    iris_host: str | None = None,
    iris_web_port: str | None = None,
    iris_container: str = "iris-dev-iris",
    binary: str | None = None,
    driver=None,
    on_run=None,
) -> list:
    """Every task in every arm, `repeats` times, one session at a time.

    Serial for the same reason the pilot is: every session shares one BENCHMARK namespace, so two at
    once grade each other's work. Task-major, so an interrupted run leaves whole comparable pairs.

    `on_run` is called with each `ArmRun` as it completes, which is how a long run gets written down
    incrementally instead of existing only in memory for ten hours.
    """
    from tests.e2e.skill_eval.pilot import run_one

    key = openai_api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise LadderRefused(
            "OPENAI_API_KEY is not set, so every session would fail to start and every arm would "
            "score as an arm that failed every task"
        )
    host = iris_host or os.environ.get("IRIS_HOST", "localhost")
    port = iris_web_port or os.environ.get("IRIS_WEB_PORT", "52780")

    runs = []
    # A session that could not be graded is not a failure, so it does not end up in a comparison — it
    # ends up as a hole, and the run keeps paying for more of them. Three in a row is the environment.
    unscored_streak: list = []
    for repeat in range(repeats):
        for task in tasks:
            for arm in arms_for_task(arms, task):
                run = run_one(
                    task,
                    arm,
                    openai_api_key=key,
                    model=model,
                    timeout=timeout,
                    skill_names=skill_names,
                    iris_host=host,
                    iris_web_port=port,
                    iris_container=iris_container,
                    binary=binary,
                    driver=driver,
                )
                run = type(run)(**{**asdict(run), "run_index": repeat})
                runs.append(run)
                print(
                    f"{run.task_id:<12} {run.arm:<34} "
                    f"{'—' if run.passed is None else ('PASS' if run.passed else 'FAIL'):<5} "
                    f"{run.tool_calls:>3} calls {run.session_seconds:6.1f}s"
                    + ("  TIMEOUT" if run.timed_out else "")
                    + (f"  [{run.reason}]" if run.reason else ""),
                    flush=True,
                )
                if on_run is not None:
                    on_run(run)
                if run.passed is None:
                    unscored_streak.append(run)
                    if len(unscored_streak) >= UNSCORED_ABORT:
                        raise LadderAborted(
                            f"{len(unscored_streak)} sessions in a row could not be graded, so the "
                            "run stopped rather than spending the rest of the ladder on sessions "
                            "nothing can score. Fix the environment and resume from the sessions "
                            "already written:\n"
                            + "\n".join(
                                f"  {other.task_id} {other.arm}: {other.reason}"
                                for other in unscored_streak
                            )
                        )
                else:
                    unscored_streak.clear()
    return runs


def write_report(written: dict, out: str | None = None) -> str:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = out or os.path.join(RESULTS_DIR, f"{written['provenance']['run_id']}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(written, handle, indent=2)
    return path


def tools_ladder_tasks(split: Split | None = None):
    """The holdout side of the tools corpus, checked against the publication floor."""
    return assert_publishable_corpus(
        holdout_only(list(graded_task.tools_corpus()), split=split)
    )


def skill_ladder_tasks(skill: str, split: Split | None = None):
    """The holdout-side tasks that name one skill. Exempt from the floor — see
    `assert_publishable_corpus`."""
    tasks = [task for task in graded_task.skill_corpus() if task.skill == skill]
    return assert_publishable_corpus(holdout_only(tasks, split=split), floor=None)


def pooled_skill_tasks(split: Split | None = None):
    """Every holdout skill task, for the pooled rung. Each runs against its own skill's arm.

    A task here with no skill named would run against an arm holding nothing and still be counted as a
    pair, so it is refused rather than skipped.
    """
    tasks = holdout_only(list(graded_task.skill_corpus()), split=split)
    unnamed = [task.id for task in tasks if not getattr(task, "skill", None)]
    if unnamed:
        raise LadderRefused(
            f"{', '.join(unnamed)} name no skill, so the pooled rung would install nothing for them "
            "and count the pair anyway"
        )
    return assert_publishable_corpus(tasks, floor=None)


def arms_for_task(arms, task) -> tuple:
    """Either the fixed arm tuple or, for the pooled rung, the arms this one task runs.

    A callable is how the pooled rung gives every task the arm holding its own skill without
    `run_ladder` needing to know what a skill is.
    """
    return tuple(arms(task)) if callable(arms) else tuple(arms)


# --- the command -----------------------------------------------------------------------------------


def parse_args(argv=None):
    """The run as a command, because a run this long has to be repeatable from a shell line.

    `--ladder skill` without `--skill` is refused by the parser rather than defaulted. A per-skill
    rung with no skill named installs the whole pack and reports the result under one skill's name,
    which is the one mistake this whole stage exists to avoid.
    """
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ladder", choices=("tools", "skill"), default="tools")
    parser.add_argument("--skill", default=None, help="required when --ladder skill")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--model", default=LADDER_MODEL)
    parser.add_argument("--timeout", type=int, default=SESSION_TIMEOUT)
    parser.add_argument("--container", default="iris-dev-iris")
    parser.add_argument(
        "--task",
        action="append",
        default=None,
        help="run only these task ids (repeatable); the holdout filter still applies",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the estimate and the task list, start no session",
    )
    parser.add_argument(
        "--spent",
        type=float,
        default=0.0,
        help="dollars already spent in this program, so the estimate projects against the cap",
    )
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    if args.ladder == "skill" and not args.skill:
        parser.error(
            "--ladder skill needs --skill NAME: an unnamed skill rung installs the whole pack and "
            "publishes the result as that skill's own"
        )
    return args


def main(argv=None) -> int:
    from tests.e2e.skill_eval.arms import skill_ladder
    from tests.e2e.skill_eval.cost_estimator import (
        assert_within_budget,
        estimate_ladder,
        format_ladder_estimate,
    )

    args = parse_args(argv)
    run_id = f"ladder-{time.strftime('%Y%m%dT%H%M%S')}"

    # `--skill all` is the pooled rung, and it is the one that answers the skills question: the corpus
    # spreads twelve skill tasks over four skills as 5/3/3/1, and `helps` needs b >= 4, so three of the
    # four single-skill rungs cannot reach it on item count alone. Pooled, the twelve pair as the
    # twelve the rule was written for, and `per_skill` carries each document's counts beside it.
    pooled = args.ladder == "skill" and args.skill == "all"
    if pooled:
        arms = pooled_skill_arms
        tasks = pooled_skill_tasks()
        arm_names = [TOOLS.name, POOLED_ARM]
    elif args.ladder == "skill":
        arms = skill_ladder(args.skill)
        tasks = skill_ladder_tasks(args.skill)
        arm_names = [arm.name for arm in arms]
    else:
        arms = ARMS
        tasks = tools_ladder_tasks()
        arm_names = [arm.name for arm in arms]

    if args.task:
        wanted = set(args.task)
        tasks = [task for task in tasks if task.id in wanted]
        if not tasks:
            print(f"no holdout task matches {sorted(wanted)}")
            return 2

    estimate = estimate_ladder(len(tasks), arm_names, runs=args.repeats)
    print(format_ladder_estimate(estimate, already_spent=args.spent))
    assert_within_budget(estimate, already_spent=args.spent)
    if args.dry_run:
        for task in tasks:
            print(f"  {task.id}")
        return 0

    # Written as they land. A four-hour run that exists only in memory is a four-hour run that a
    # laptop sleeping loses whole.
    incremental = os.path.join(RESULTS_DIR, f"{run_id}.runs.jsonl")
    os.makedirs(RESULTS_DIR, exist_ok=True)

    def record(run):
        with open(incremental, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(run)) + "\n")

    driver = None
    try:
        runs = run_ladder(
            tasks,
            arms,
            repeats=args.repeats,
            model=args.model,
            timeout=args.timeout,
            iris_container=args.container,
            binary=os.environ.get("IAD_BINARY"),
            driver=driver,
            on_run=record,
        )
    except LadderAborted as aborted:
        # No report. A report over a run that stopped early would print a lift whose denominator is an
        # accident of when the container died.
        print(f"\n{aborted}", flush=True)
        print(f"\nsessions so far: {incremental}")
        print(
            "resume with:\n"
            f"  python3 -m tests.e2e.skill_eval.resume --remaining {incremental}\n"
            "then pass the ids back as --task arguments, and merge with --merge"
        )
        return 3

    written = report(
        runs,
        arms=(TOOLS,) if pooled else arms,
        model=args.model,
        container=args.container,
        repeats=args.repeats,
        run_id=run_id,
        pooled=pooled,
        tasks=tasks,
    )
    for record_ in written["comparisons"]:
        print(
            f"{record_['arm_a']} -> {record_['arm_b']}: b={record_['b']} c={record_['c']} "
            f"lift={record_['lift']} n={record_['n_pairs']} mde={record_['mde']} "
            f"{record_['verdict']}"
        )
    if pooled:
        print(f"skills verdict over {len(tasks)} pairs: {written['skill_verdict']}")
        for row in written["per_skill"]:
            reach = (
                "" if row["helps_reachable"] else "  (too few items to reach `helps`)"
            )
            print(
                f"  {row['skill']:<30} {row['pairs']:>2} pairs  b={row['b']} c={row['c']}  "
                f"{row['verdict']}{reach}"
            )
    path = write_report(written, out=args.out)
    print(f"written to {path}")
    print(f"sessions written incrementally to {incremental}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
