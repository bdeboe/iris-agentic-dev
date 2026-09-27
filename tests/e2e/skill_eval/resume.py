"""Resume a graded ladder run, and merge what the pieces wrote into one report.

A 123-session run takes about four hours, and the laptop it runs on sleeps. The first attempt at the
tools ladder lost its environment at session 92 — the host slept, OrbStack's docker daemon came back
wedged, and the remaining sessions recorded a legible "the check did not answer" instead of a
verdict. Nothing about that is a reason to pay for the first 92 again.

`run_ladder`'s `on_run` already writes every session to `<run_id>.runs.jsonl` as it lands, so the
sessions are the durable artifact and the report is derived. This module closes the loop: it reads
those files, says which tasks still owe a session, and merges several files into the one report
`ladder.report` would have written had the run gone straight through.

Two rules, because both of them change a number:

- **A session with no verdict is a session that did not happen.** `passed is None` means the check
  could not answer, which is not a failure and must not be scored as one. `remaining` treats it as
  work still owed and `unscored` names it.
- **A scored session is never displaced by an unscored one.** Later files win in general — a re-run
  is the more recent measurement — but a re-run that could not grade would otherwise erase a verdict
  that was already earned, and the pair would silently leave the denominator.
"""

from __future__ import annotations

import json
import os

#: Every field `pilot.ArmRun` carries. A line missing any of them is not a session, and guessing a
#: default here would put a fabricated verdict or duration into a published figure.
SESSION_FIELDS = (
    "task_id",
    "arm",
    "passed",
    "reason",
    "run_index",
    "seconds",
    "session_seconds",
    "calls",
    "tool_calls",
    "timed_out",
)

#: The tools ladder's arms, in the order a report reads them.
LADDER_ARMS = ("bare", "tools", "tools+skills")


class ResumeRefused(Exception):
    """A merge or resume that would have produced a misleading report."""


def read_sessions(path: str) -> list[dict]:
    """One `.runs.jsonl` file as a list of session dicts, in the order they were written."""
    rows = []
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ResumeRefused(f"{path}:{number} is not JSON: {exc}") from None
            missing = [field for field in SESSION_FIELDS if field not in row]
            if missing:
                raise ResumeRefused(
                    f"{path}:{number} is missing {', '.join(missing)}, so it is not a session "
                    "record and merging it would invent the fields it lacks"
                )
            rows.append(row)
    return rows


def scored(record: dict) -> bool:
    return record.get("passed") is not None


def merge_sessions(paths, *, arms=LADDER_ARMS) -> list[dict]:
    """Every session from every file, one per (task, arm, repeat), sorted task-major.

    Later paths win, except that an unscored record never displaces a scored one — see the module
    docstring.
    """
    if not paths:
        raise ResumeRefused(
            "no session files to merge, and an empty report renders exactly like a run in which "
            "every arm failed every task"
        )
    keep: dict[tuple[str, str, int], dict] = {}
    for path in paths:
        for record in read_sessions(path):
            key = (record["task_id"], record["arm"], record["run_index"])
            held = keep.get(key)
            if held is not None and scored(held) and not scored(record):
                continue
            keep[key] = record

    order = {name: index for index, name in enumerate(arms)}
    return sorted(
        keep.values(),
        key=lambda row: (
            row["task_id"],
            order.get(row["arm"], len(order)),
            row["arm"],
            row["run_index"],
        ),
    )


def remaining(task_ids, paths, *, arms=LADDER_ARMS) -> list[str]:
    """The task IDs that still owe a scored session in at least one arm.

    A task partly run is re-run whole rather than per arm. The arms of one task are compared with
    each other, and half a pair measured before the environment broke and half after is a pair whose
    difference has two explanations.
    """
    have = {
        (record["task_id"], record["arm"])
        for path in paths
        for record in read_sessions(path)
        if scored(record)
    }
    return [
        task_id
        for task_id in task_ids
        if any((task_id, arm) not in have for arm in arms)
    ]


def unscored(records) -> list[dict]:
    """The sessions that carry no verdict, so a report can name its holes instead of hiding them."""
    return [record for record in records if not scored(record)]


def arm_runs(records, *, scored_only: bool = False):
    """Session dicts back as `ArmRun` objects, which is what `ladder.report` reads."""
    from tests.e2e.skill_eval.pilot import ArmRun

    rows = [record for record in records if scored(record) or not scored_only]
    return [
        ArmRun(**{field: record[field] for field in SESSION_FIELDS}) for record in rows
    ]


def pooled_tasks_for(records):
    """The skill tasks these sessions ran, which is what the per-skill breakdown reads.

    Refuses a file whose tasks are not skill tasks. `pooled_runs` relabels every arm whose name starts
    with `tools+`, so merging the tools ladder under `--pooled` would fold its 34-skill arm into the
    pooled rung and report it as twelve tasks against their own one document.
    """
    from tests.e2e.skill_eval import ladder

    ids = {record["task_id"] for record in records}
    tasks = [task for task in ladder.pooled_skill_tasks() if task.id in ids]
    strangers = sorted(ids - {task.id for task in tasks})
    if strangers:
        raise ResumeRefused(
            f"{', '.join(strangers)} is not a skill task, so these sessions are not the pooled rung. "
            "Merge them without --pooled."
        )
    return tasks


def main(argv=None) -> int:
    """Two commands in one: what is left to run, and the report over what has been run.

    python3 -m tests.e2e.skill_eval.resume --remaining results/ladder-*.runs.jsonl
    python3 -m tests.e2e.skill_eval.resume --merge   results/ladder-*.runs.jsonl --out r.json
    """
    import argparse

    from tests.e2e.skill_eval import ladder

    parser = argparse.ArgumentParser(description="resume or merge a graded ladder run")
    parser.add_argument(
        "sessions", nargs="+", help="one or more <run_id>.runs.jsonl files"
    )
    parser.add_argument(
        "--remaining",
        action="store_true",
        help="print the task ids that still owe a scored session, space separated",
    )
    parser.add_argument(
        "--merge", action="store_true", help="write the report over every session file"
    )
    parser.add_argument("--out", default=None)
    parser.add_argument(
        "--run-id", default=None, help="run id to stamp on the merged report"
    )
    parser.add_argument("--model", default=ladder.LADDER_MODEL)
    parser.add_argument("--container", default="iris-dev-iris")
    parser.add_argument(
        "--pooled",
        action="store_true",
        help="the sessions came from the skills rung (--ladder skill --skill all)",
    )
    args = parser.parse_args(argv)

    if args.remaining == args.merge:
        parser.error("pass exactly one of --remaining and --merge")

    if args.remaining:
        ids = [task.id for task in ladder.tools_ladder_tasks()]
        left = remaining(ids, args.sessions)
        print(" ".join(left))
        print(
            f"{len(ids) - len(left)} of {len(ids)} tasks have a scored session in every arm",
            flush=True,
        )
        return 0

    # The pooled rung's arms are one per skill, so the ladder's three names order nothing here. Naming
    # only the shared arm puts it first and leaves the skill arms after it, alphabetically.
    records = merge_sessions(
        args.sessions, arms=(ladder.TOOLS.name,) if args.pooled else LADDER_ARMS
    )
    runs = arm_runs(records)
    holes = unscored(records)
    written = ladder.report(
        runs,
        model=args.model,
        container=args.container,
        run_id=args.run_id or _run_id_from(args.sessions[-1]),
        repeats=max(record["run_index"] for record in records) + 1,
        pooled=args.pooled,
        # Only read for the per-skill breakdown, and only the tasks that were actually merged: the
        # full corpus here would print a row of zero pairs for a skill this run never touched.
        tasks=pooled_tasks_for(records) if args.pooled else None,
    )
    written["merged_from"] = [os.path.basename(path) for path in args.sessions]
    written["unscored_sessions"] = [
        {"task_id": row["task_id"], "arm": row["arm"], "reason": row.get("reason")}
        for row in holes
    ]
    path = ladder.write_report(written, out=args.out)
    print(f"{len(runs)} sessions from {len(args.sessions)} file(s) -> {path}")
    if holes:
        print(f"{len(holes)} session(s) carry no verdict:")
        for row in holes:
            print(
                f"  {row['task_id']:<12} {row['arm']:<14} {(row.get('reason') or '')[:90]}"
            )
    for record in written["comparisons"]:
        print(
            f"{record['arm_a']} -> {record['arm_b']}: b={record['b']} c={record['c']} "
            f"lift={record['lift']} n={record['n_pairs']} mde={record['mde']} "
            f"{record['verdict']}"
        )
    return 0


def _run_id_from(path: str) -> str:
    """`ladder-20260918T221725.runs.jsonl` -> `ladder-20260918T221725`, so a merged report keeps the
    run's own id rather than inventing the time it was assembled."""
    return os.path.basename(path).split(".runs.jsonl")[0]


if __name__ == "__main__":
    raise SystemExit(main())
