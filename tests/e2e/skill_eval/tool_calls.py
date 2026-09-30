"""List the tool calls in a ladder run's transcripts — 132 FR-016.

    python -m tests.e2e.skill_eval.tool_calls list <run_id>

One block per session, `== <task> <arm> repeat=<n> ==`, then one line per call:
`<n>\\t<tool>\\t<ok|err>\\t<text>`, where the text is the first 120 characters of the result or error with
newlines shown as ⏎. A failed repeat's FR-016 decision cites these call numbers, so the numbering is
the session's own order and starts at 1.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

from tests.e2e.skill_eval.ladder import RESULTS_DIR
from tests.e2e.skill_eval.opencode_driver import parse_mcp_tool

TEXT_LIMIT = 120
_NAME = re.compile(r"^(?P<task>.+?)__(?P<arm>.+)__r(?P<repeat>\d+)\.jsonl$")


def _text(value) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = json.dumps(value, default=str)
    return value.replace("\r\n", "⏎").replace("\n", "⏎")[:TEXT_LIMIT]


def session_lines(path: str) -> list[str]:
    lines = []
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            event = json.loads(raw)
            if event.get("type") != "tool_use":
                continue
            part = event.get("part", {}) or {}
            if not part.get("tool"):
                continue
            _server, tool = parse_mcp_tool(part["tool"])
            state = part.get("state", {}) or {}
            ok = state.get("status") == "completed"
            text = state.get("output") if ok else state.get("error")
            lines.append(
                f"{len(lines) + 1}\t{tool}\t{'ok' if ok else 'err'}\t{_text(text)}"
            )
    return lines


def _sessions(directory: str):
    found = []
    for name in os.listdir(directory):
        match = _NAME.match(name)
        if match:
            found.append(
                (
                    match["task"],
                    match["arm"],
                    int(match["repeat"]),
                    os.path.join(directory, name),
                )
            )
    return sorted(found)


def list_run(run_id: str, results: str) -> int:
    directory = os.path.join(results, f"{run_id}.transcripts")
    if not os.path.isdir(directory):
        print(f"no transcripts at {directory}", file=sys.stderr)
        return 2
    for task, arm, repeat, path in _sessions(directory):
        print(f"== {task} {arm} repeat={repeat} ==")
        for line in session_lines(path):
            print(line)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tool_calls")
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser(
        "list", help="the tool calls in each session of one ladder run"
    )
    listing.add_argument("run_id")
    listing.add_argument(
        "--results", default=RESULTS_DIR, help="the ladder results directory"
    )
    args = parser.parse_args(argv)
    return list_run(args.run_id, args.results)


if __name__ == "__main__":
    sys.exit(main())
