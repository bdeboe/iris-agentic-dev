"""The nightly breakage guard — 121 T017, FR-016.

What this replaces: nine skills × five opencode sessions a night, ~$3.70 and about two hours of
runner time, to publish a lift the corpus could not support. Six of nine skills printed 0.00
against 0.00 and the job reported success; then runs 34744344877, 34817991701 and 34939912456
failed three nights in a row on Δs smaller than the harness's own resolution.

What it does instead, and all it does: three questions with cheap answers.

1. Does the harness still run — every `eval.yaml` loads and every module imports.
2. Does the binary still advertise its tools — `tool --list --json` returns a surface at least
   `MINIMUM_TOOL_COUNT` wide. It ran for weeks with no iad tools in any session, measuring a bare
   model and scoring it as the skill failing.
3. Does the named canary set still pass — three assertion-scored tasks, no judge, no scorer
   credential, no spend on grading.

It publishes no lift. Not an underpowered one, not a withheld one, none: `lift_mentions()` scans
the report for the word and `assert_no_lift()` refuses to emit one that carries it. Lift belongs
to the full benchmark, which runs at a release and before a conference.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import os
import subprocess
import sys
from typing import Optional

from tests.e2e import billing

#: The named canary set of FR-016. Assertion-scored on purpose — `tool_called`, `skill_invoked`
#: and a two-tool chain — so a night costs three agent sessions and no grading call at all.
#: MCP-01: a tool call reaches IRIS. SKILL-01: a skill is invoked. FULL-01: both, in order.
CANARY_TASKS = ("MCP-01", "SKILL-01", "FULL-01")

#: A floor, not an equality. 1.4.2 advertises 81 tools; adding one must not fail the nightly,
#: while "no tools at all" and "half the surface vanished" both have to.
MINIMUM_TOOL_COUNT = 75

#: Any of these in the report is the old behaviour coming back.
_LIFT_WORDS = ("lift", "pass_rate", "delta")


@dataclasses.dataclass(frozen=True)
class CanaryCheck:
    name: str
    ok: bool
    detail: str

    def to_dict(self) -> dict:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


@dataclasses.dataclass
class CanaryReport:
    """One night's answer: healthy, or broken and what broke.

    Deliberately holds no rate, no Δ and no lift. The fields are the three questions and the
    names of whatever failed to answer one.
    """

    run_id: str
    timestamp: str
    canary_tasks: list
    tool_count: Optional[int]
    checks: list

    @property
    def broken(self) -> list:
        return [check.name for check in self.checks if not check.ok]

    @property
    def verdict(self) -> str:
        return "broken" if self.broken else "healthy"

    def exit_code(self) -> int:
        """1 on breakage. A guard that reports breakage and exits 0 is not a guard."""
        return 1 if self.broken else 0

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "kind": "nightly-canary",
            "canary_tasks": list(self.canary_tasks),
            "tool_count": self.tool_count,
            "verdict": self.verdict,
            "broken": self.broken,
            "checks": [check.to_dict() for check in self.checks],
        }

    def assert_no_lift(self) -> None:
        """Raise rather than publish a report carrying a lift (FR-016).

        A raise and not a warning: the nightly's whole remaining job is to be the cheap check
        that makes no claim about effect, and a claim smuggled into a detail string is the one
        way that fails silently.
        """
        found = lift_mentions(self.to_dict())
        if found:
            raise ValueError(
                "the nightly canary report carries a lift: "
                + "; ".join(found)
                + ". FR-016 — the nightly reports breakage, and the full benchmark reports lift."
            )

    def render(self) -> str:
        lines = [
            f"nightly canary — {self.timestamp} ({self.run_id})",
            f"canary set: {', '.join(self.canary_tasks) or 'empty'}",
        ]
        for check in self.checks:
            mark = "ok  " if check.ok else "FAIL"
            lines.append(f"  [{mark}] {check.name}: {check.detail}")
        lines.append(f"verdict: {self.verdict}")
        if self.broken:
            lines.append(f"broken: {', '.join(self.broken)}")
        return "\n".join(lines)


def lift_mentions(payload) -> list:
    """Every place a lift-ish word appears in the report, as `path: text`.

    Used by the report's own guard and by its tests. Keys and string values both, because
    `{"lift": 0.28}` and `{"detail": "lift=+0.28"}` are the same mistake.
    """
    found: list = []

    def walk(node, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                here = f"{path}.{key}" if path else str(key)
                if any(word in str(key).lower() for word in _LIFT_WORDS):
                    found.append(f"{here}: key names a lift")
                walk(value, here)
        elif isinstance(node, (list, tuple)):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")
        elif isinstance(node, str):
            lowered = node.lower()
            for word in _LIFT_WORDS:
                if word in lowered:
                    found.append(f"{path}: {node!r}")
                    break

    walk(payload, "")
    return found


def build_report(
    run_id: str,
    timestamp: str,
    harness_ok: bool,
    harness_detail: str,
    tool_count: Optional[int],
    task_outcomes: dict,
    canary_tasks=CANARY_TASKS,
) -> CanaryReport:
    """Assemble the report from three already-taken measurements.

    Pure: every probe is passed in, so the tests need no binary, no container and no session.
    `task_outcomes[task]` is `True`, `False`, or `None`/absent for a task that never ran — and
    `None` counts as breakage, because a task the runner could not reach is exactly the failure
    the old nightly reported as a pass rate.
    """
    checks = [CanaryCheck("harness runs", bool(harness_ok), harness_detail)]

    if tool_count is None:
        checks.append(
            CanaryCheck(
                "tool surface",
                False,
                "could not read the advertised surface from the binary",
            )
        )
    else:
        checks.append(
            CanaryCheck(
                "tool surface",
                tool_count >= MINIMUM_TOOL_COUNT,
                f"{tool_count} tools advertised, floor {MINIMUM_TOOL_COUNT}",
            )
        )

    if not canary_tasks:
        checks.append(
            CanaryCheck(
                "canary set",
                False,
                "no canary tasks declared — a guard over nothing passes every night",
            )
        )

    for task in canary_tasks:
        outcome = task_outcomes.get(task)
        if outcome is None:
            checks.append(CanaryCheck(task, False, "did not run"))
        else:
            checks.append(
                CanaryCheck(
                    task,
                    bool(outcome),
                    "assertions passed" if outcome else "assertions failed",
                )
            )

    return CanaryReport(
        run_id=run_id,
        timestamp=timestamp,
        canary_tasks=list(canary_tasks),
        tool_count=tool_count,
        checks=checks,
    )


# ---------------------------------------------------------------------------
# The probes. Everything below talks to the world; everything above is pure.
# ---------------------------------------------------------------------------


def probe_harness() -> tuple:
    """`(ok, detail)` — does the harness still load its own corpus and configs.

    Cheapest possible answer to "does it run": every `eval.yaml` parses and every canary task
    loads. It catches the class of breakage that used to show up as a night of zero pass rates.
    """
    try:
        from tests.e2e.skill_eval.evaluator import discover_skills, load_eval_config
        from tests.e2e.task_loader import TASKS_DIR, load_task

        # Four levels: skill_eval → e2e → tests → repo root. Three of them land on
        # `tests/skills/skills`, which does not exist, and the probe then reports the harness
        # broken on every machine — the same off-by-one-directory class as the Homebrew path
        # that left the nightly running with no iad tools for weeks.
        repo_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        skills_dir = os.path.join(repo_root, "skills", "skills")
        tasks_skills_dir = os.path.join(TASKS_DIR, "skills")
        configured = 0
        for skill in discover_skills(skills_dir):
            if load_eval_config(skill, tasks_skills_dir) is not None:
                configured += 1
        for task in CANARY_TASKS:
            load_task(os.path.join(TASKS_DIR, f"{task}.yaml"))
        return (
            True,
            f"{configured} eval configs and {len(CANARY_TASKS)} canary tasks loaded",
        )
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def probe_tool_surface(binary: Optional[str] = None) -> Optional[int]:
    """How many tools the binary advertises, or `None` when it could not be asked.

    `tool --list --json` needs no IRIS connection (spec 114), so this costs a process spawn.
    """
    binary = binary or os.environ.get("IAD_BINARY")
    if not binary or not os.path.exists(binary):
        return None
    try:
        out = subprocess.run(
            [binary, "tool", "--list", "--json"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if out.returncode != 0:
            return None
        return len(json.loads(out.stdout)["tools"])
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        return None


#: Which environment variable authenticates each provider prefix an opencode model can name.
#: Any one of the listed names is enough.
_PROVIDER_CREDENTIALS = {
    "openai": ("OPENAI_API_KEY",),
    "amazon-bedrock": ("AWS_BEARER_TOKEN_BEDROCK", "AWS_ACCESS_KEY_ID"),
    "anthropic": ("ANTHROPIC_API_KEY",),
}


def credential_for(model: str) -> Optional[tuple]:
    """The env vars that would authenticate `model`, or `None` for a provider not listed here.

    `None` is "could not say", the same convention `probe_tool_surface` uses — never "nothing
    needed". A provider this table has not been taught about must stop the run, not slip past it.
    """
    provider = (model or "").split("/")[0]
    return _PROVIDER_CREDENTIALS.get(provider)


def canary_models(canary_tasks=CANARY_TASKS) -> dict:
    """`{task_id: the model that task will actually run on}`.

    `run_task` lets a task's own `model:` override the caller's default, so the task file is the
    authority here and `CANARY_MODEL` is only the fallback.
    """
    from tests.e2e.task_loader import TASKS_DIR, load_task

    fallback = os.environ.get("CANARY_MODEL", "openai/gpt-4.1")
    models = {}
    for task_id in canary_tasks:
        task = load_task(os.path.join(TASKS_DIR, f"{task_id}.yaml"))
        models[task_id] = getattr(task, "model", None) or fallback
    return models


def missing_credentials(env=None, models=None) -> list:
    """`[(task_id, what it needs)]` for every canary task nothing in `env` can authenticate.

    All three canary tasks declare a Bedrock model, so a run gated on `OPENAI_API_KEY` would
    refuse a night holding a working Bedrock token and start a night holding a key none of its
    sessions use. The gate is per task, on the model the task itself names.
    """
    env = os.environ if env is None else env
    models = canary_models() if models is None else models
    missing = []
    for task_id, model in models.items():
        accepted = credential_for(model)
        if accepted is None:
            missing.append(
                (
                    task_id,
                    f"{model} names a provider this canary has no credential rule for",
                )
            )
        elif not any(env.get(name) for name in accepted):
            missing.append((task_id, " or ".join(accepted)))
    return missing


def run_canary_tasks(
    openai_api_key: str,
    model: str,
    iris_host: Optional[str] = None,
    iris_web_port: Optional[str] = None,
    iris_container: Optional[str] = None,
) -> dict:
    """Run the canary set through the real harness. `{task_id: True/False/None}`.

    `None` on a task that raised, because a task that could not run is not a task that failed
    its assertions and the report says so differently.
    """
    from tests.e2e.harness import run_task
    from tests.e2e.task_loader import TASKS_DIR, load_task

    outcomes: dict = {}
    for task_id in CANARY_TASKS:
        try:
            task = load_task(os.path.join(TASKS_DIR, f"{task_id}.yaml"))
            result = run_task(
                task,
                openai_api_key=openai_api_key,
                model=model,
                iris_host=iris_host,
                iris_web_port=iris_web_port,
                iris_container=iris_container,
            )
            outcomes[task_id] = bool(result.passed)
        except Exception as e:  # a wedged session must not take the other two with it
            print(f"  [{task_id}] did not run: {type(e).__name__}: {e}", flush=True)
            outcomes[task_id] = None
    return outcomes


def _main(argv=None) -> int:
    """`python -m tests.e2e.skill_eval.nightly_canary` — the whole nightly.

    Exit 0 healthy, 1 broken, 2 misconfigured. `--dry-run` answers the two cheap questions and
    skips the sessions, which is what CI uses to check the guard itself without spending.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    dry_run = "--dry-run" in argv
    output = None
    if "--output" in argv:
        output = argv[argv.index("--output") + 1]

    run_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"
    )

    harness_ok, harness_detail = probe_harness()
    tool_count = probe_tool_surface()

    if dry_run:
        outcomes = {task: True for task in CANARY_TASKS}
        print("dry run: the canary sessions were not started", flush=True)
    else:
        # Per task, on the model the task itself names — all three canary tasks declare a
        # Bedrock model, and `run_task` lets that override `CANARY_MODEL`.
        unauthenticated = missing_credentials()
        if unauthenticated:
            for task_id, need in unauthenticated:
                print(f"  [{task_id}] needs {need}", flush=True)
            print(
                "No canary session can authenticate. Exiting 2 rather than reporting a night "
                "nobody measured.",
                flush=True,
            )
            return 2
        outcomes = run_canary_tasks(
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
            model=os.environ.get("CANARY_MODEL", "openai/gpt-4.1"),
            iris_host=os.environ.get("IRIS_HOST"),
            iris_web_port=os.environ.get("IRIS_WEB_PORT"),
            iris_container=os.environ.get("IRIS_CONTAINER"),
        )

    report = build_report(
        run_id=run_id,
        timestamp=timestamp,
        harness_ok=harness_ok,
        harness_detail=harness_detail,
        tool_count=tool_count,
        task_outcomes=outcomes,
    )
    report.assert_no_lift()
    print(report.render(), flush=True)

    if output:
        os.makedirs(output, exist_ok=True)
        path = os.path.join(output, f"nightly-canary-{run_id}.json")
        with open(path, "w") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"written: {path}", flush=True)

    return report.exit_code()


def main(argv=None) -> int:
    """The nightly, with billable sessions permitted for the duration — see `tests/e2e/billing.py`."""
    with billing.allow():
        return _main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
