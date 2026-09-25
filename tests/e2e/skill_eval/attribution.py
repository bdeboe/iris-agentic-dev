"""Per-tool attribution — 121 T040, and Goal 3's deliverable.

A join, not a run. The graded ladder's sessions already recorded which tools they called and what came
back (`ArmRun.calls`), and each task already has a machine verdict. Putting the two together answers
Constitution IX's standing question — which of the 81 tools earn their place — for no additional spend.

What the table is careful about:

- **Every advertised tool has a row.** A table of the tools that were used has no bad news in it, and
  the bad news is the finding: spec 059 already suspected tools nothing ever reaches for.
- **Zero reach has two meanings.** No applicable task is a gap in the corpus. An applicable task the
  agent solved another way is a gap in the tool's description, which is what the GEPA work exists to
  fix. `tool_applicability.toml` is what lets the table tell them apart, and it is committed in
  advance.
- **The pass-rate split is observational and says so.** Which tasks called a tool is the agent's
  choice, not an assignment, so `pass_rate_when_called` is not a lift and is never labelled one.

Failure modes are reported as the text the tool returned, counted. Four reaches that all failed with
`CODE_EDIT_BLOCKED` is one bug in one gate; four different messages is four separate problems, and a
single "83% success" rate hides both.
"""

from __future__ import annotations

import os
from collections import Counter

TABLE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "tool_applicability.toml"
)

#: The MCP server name the tools arm registers, which is the only server whose calls count as reach.
#: A `bash` call named `iris_doc` is not a reach for `iris_doc`.
IAD_SERVER = "iris_agentic_dev"


class Unclassified(KeyError):
    """A tool the applicability table does not place in a domain.

    Raised rather than defaulted. A tool with no declared domain has an applicable count of zero, which
    reads in the report as "no task needed it" — a claim nobody made.
    """


def load_table(path: str = TABLE_PATH) -> dict:
    """The committed applicability declaration."""
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10
        import tomli as tomllib  # type: ignore

    with open(path, "rb") as handle:
        raw = tomllib.load(handle)
    return {
        "tools": raw.get("tools", {}),
        "tags": raw.get("tags", {}),
        "baseline": list(raw.get("baseline", ())),
    }


def task_domains(task, table: dict | None = None) -> set[str]:
    """The domains one task touches: the baseline floor, its tags' domains, and `skills` if it names
    one."""
    table = table or load_table()
    domains = set(table["baseline"])
    for tag in getattr(task, "tags", ()) or ():
        domain = table["tags"].get(tag)
        if domain:
            domains.add(domain)
    if getattr(task, "skill", None):
        domains.add("skills")
    return domains


def tool_domain(tool: str, table: dict) -> str:
    try:
        return table["tools"][tool]
    except KeyError:
        raise Unclassified(
            f"{tool} has no domain in tool_applicability.toml, so nothing can say whether a task "
            "could have used it. Add it to a domain before the next run"
        ) from None


def applicable_tasks(tool: str, tasks, table: dict | None = None) -> tuple[str, ...]:
    """The task IDs whose domains include this tool's — the denominator of its reach rate."""
    table = table or load_table()
    domain = tool_domain(tool, table)
    return tuple(task.id for task in tasks if domain in task_domains(task, table=table))


def _failure_key(record: dict) -> str:
    """How a failed call is labelled in the failure-mode counter.

    The message when there is one, because that is the actionable half. A failed call with no message
    is labelled by its status, so an abandoned call and a refused one stay distinguishable.
    """
    error = (record.get("error") or "").strip()
    if error:
        return error
    return f"{record.get('status') or 'unknown'} (no message)"


def attribute(*, runs, tasks, surface, table: dict | None = None) -> list[dict]:
    """One row per advertised tool, in the order the surface advertises them.

    `runs` is every `ArmRun` from the graded ladder, bare arm included: the bare arm's sessions are
    dropped here rather than at the call site, because a bare session that could not have called
    anything must not enlarge a denominator.
    """
    table = table or load_table()
    tool_runs = [run for run in runs if _had_tools(run)]
    verdicts = {
        run.task_id: run.passed
        for run in tool_runs
        if getattr(run, "passed", None) is not None
    }

    rows = []
    for tool in surface:
        applicable = set(applicable_tasks(tool, tasks, table=table))
        calls = [
            record
            for run in tool_runs
            for record in (run.calls or ())
            if record.get("name") == tool and record.get("server") == IAD_SERVER
        ]
        reached = {
            run.task_id
            for run in tool_runs
            if any(
                record.get("name") == tool and record.get("server") == IAD_SERVER
                for record in (run.calls or ())
            )
        }
        failed = [record for record in calls if not record.get("completed")]
        rows.append(
            {
                "tool": tool,
                "domain": tool_domain(tool, table),
                "applicable_tasks": len(applicable),
                "reached_tasks": len(reached),
                # 0 of 0 is not 0%. A tool no task could have used has no reach rate, and printing one
                # invites a reader to compare it with a tool that was passed over.
                "reach_rate": (len(reached) / len(applicable)) if applicable else None,
                "calls": len(calls),
                "failed_calls": len(failed),
                "failure_modes": dict(
                    Counter(_failure_key(record) for record in failed)
                ),
                "sessions_with_tools": len(tool_runs),
                "verdict": _verdict(len(reached), len(applicable)),
                "pass_rate_when_called": _rate(
                    [verdicts[t] for t in reached if t in verdicts]
                ),
                "pass_rate_when_not_called": _rate(
                    [verdicts[t] for t in applicable - reached if t in verdicts]
                ),
                # Which tasks called a tool is the agent's choice. This split is not an assignment and
                # the two rates are not a lift, whatever their difference looks like.
                "observational": True,
            }
        )
    return rows


class ReportRun:
    """One run read back off disk, in the shape `attribute` reads.

    The written report is the input to the join, not the live `ArmRun` objects: a table that can only
    be produced while the four-hour run's Python process is still alive is not a standing answer.
    """

    __slots__ = ("task_id", "arm", "passed", "calls")

    def __init__(self, record: dict):
        self.task_id = record["task_id"]
        self.arm = record["arm"]
        self.passed = record.get("passed")
        self.calls = tuple(record.get("calls") or ())


def runs_from_report(report: dict) -> list[ReportRun]:
    return [ReportRun(record) for record in report.get("runs", ())]


def render_document(report: dict, rows) -> str:
    """`lift-results.md` — T041. The standing per-tool answer, with the run behind it named."""
    provenance = report.get("provenance", {})
    passed_over = unreached(rows)
    reached = [row for row in rows if row["verdict"] == "reached"]
    no_task = [row for row in rows if row["verdict"] == "no task needed it"]

    lines = [
        "# Per-tool attribution",
        "",
        f"Run `{provenance.get('run_id', 'unknown')}`, tool surface "
        f"`{provenance.get('tool_surface', 'unknown')}`. This is a join over that run's sessions and "
        "cost no extra ones: every session recorded which tools it called and what came back, and "
        "every task already had a machine verdict.",
        "",
        f"{len(reached)} of {len(rows)} advertised tools were reached for. "
        f"{len(passed_over)} had an applicable task and were passed over: "
        + (
            ", ".join(f"`{row['tool']}`" for row in passed_over)
            if passed_over
            else "none"
        )
        + ".",
        "",
        f"{len(no_task)} had no applicable task in this corpus, which is a statement about the corpus "
        "and not about the tool.",
        "",
        "Applicability is declared in `tests/e2e/skill_eval/tool_applicability.toml`, committed before "
        "the run. `pass_rate_when_called` is observational — which tasks called a tool was the agent's "
        "choice, not an assignment — so it is not a lift and the two rates below are not comparable as "
        "one.",
        "",
        "## Reach",
        "",
        format_table(rows),
        "",
        "## What came back when a call failed",
        "",
        format_failure_modes(rows),
        "",
    ]
    return "\n".join(lines)


DOCUMENT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(TABLE_PATH)))),
    "specs",
    "121-benchmark-program",
    "lift-results.md",
)


def main(argv=None) -> int:
    """Regenerate `lift-results.md` from a written ladder report — T041.

    A command rather than a function called once from a transcript: the standing table has to be
    re-derivable from the artifact months later, by someone who was not here.
    """
    import argparse
    import json

    from tests.e2e.skill_eval import graded_task, provenance

    parser = argparse.ArgumentParser(
        description="per-tool attribution from a ladder report"
    )
    parser.add_argument("report", help="path to a ladder report JSON")
    parser.add_argument("--out", default=DOCUMENT_PATH)
    args = parser.parse_args(argv)

    with open(args.report, encoding="utf-8") as handle:
        report = json.load(handle)

    runs = runs_from_report(report)
    if not runs:
        # 81 rows of zero render exactly like a real result, and the zeros would be the report's,
        # not the tools'.
        print(f"{args.report} has no runs, so there is nothing to attribute")
        return 2

    binary = provenance.resolve_binary()
    if not binary:
        print("no iris-agentic-dev binary resolved; set IAD_BINARY")
        return 2
    surface = [tool["name"] for tool in provenance.tool_list(binary)]

    rows = attribute(runs=runs, tasks=graded_task.all_tasks(), surface=surface)
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(render_document(report, rows))

    passed_over = unreached(rows)
    print(f"{args.out}: {len(rows)} tools, {len(passed_over)} passed over")
    for row in passed_over:
        print(f"  {row['tool']:<32} {row['applicable_tasks']} applicable, 0 reached")
    return 0


def _had_tools(run) -> bool:
    """Whether this run's arm could call an iad tool at all.

    Read off the arm name rather than a flag on the run, because `ArmRun` records the arm as a string.
    `bare` is the only arm in either ladder without tools, and `arms.assert_absent` has already proved
    it had none.
    """
    return run.arm != "bare"


def _rate(values) -> float | None:
    return (sum(1 for value in values if value) / len(values)) if values else None


def _verdict(reached: int, applicable: int) -> str:
    if reached:
        return "reached"
    if not applicable:
        return "no task needed it"
    return "a task needed it and the agent chose otherwise"


def unreached(rows) -> list[dict]:
    """The rows worth acting on: advertised, applicable, and never reached for."""
    return [
        row
        for row in rows
        if row["verdict"] == "a task needed it and the agent chose otherwise"
    ]


def format_table(rows) -> str:
    """The standing per-tool table for `lift-results.md` — T041.

    Sorted by verdict and then by reach, so the tools nobody reached for are at the top. A table sorted
    by name buries the finding in the middle of 81 rows.
    """
    order = {
        "a task needed it and the agent chose otherwise": 0,
        "reached": 1,
        "no task needed it": 2,
    }
    ranked = sorted(
        rows,
        key=lambda row: (order[row["verdict"]], -row["reached_tasks"], row["tool"]),
    )
    lines = [
        "| Tool | Domain | Applicable | Reached | Reach rate | Calls | Failed | Verdict |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in ranked:
        rate = "—" if row["reach_rate"] is None else f"{row['reach_rate'] * 100:.0f}%"
        lines.append(
            f"| `{row['tool']}` | {row['domain']} | {row['applicable_tasks']} | "
            f"{row['reached_tasks']} | {rate} | {row['calls']} | {row['failed_calls']} | "
            f"{row['verdict']} |"
        )
    return "\n".join(lines)


def format_failure_modes(rows) -> str:
    """Every error a tool returned, counted, with the tool that returned it.

    Goal 3's other half. A tool the agent reaches for and cannot use is the most actionable row in the
    report, and the message is the part a reader can act on.
    """
    lines = ["| Tool | Failed calls | What came back |", "| --- | ---: | --- |"]
    any_row = False
    for row in sorted(rows, key=lambda row: -row["failed_calls"]):
        if not row["failed_calls"]:
            continue
        any_row = True
        modes = "; ".join(
            f"{count}x {message}"
            for message, count in sorted(row["failure_modes"].items())
        )
        lines.append(f"| `{row['tool']}` | {row['failed_calls']} | {modes} |")
    if not any_row:
        return "No tool call failed in this run."
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
