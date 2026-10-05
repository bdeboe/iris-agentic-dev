"""One source task in, one Harbor task directory per arm out — 120 T013/T014.

This module is the only place in the repo that knows Harbor's task format (FR-001). Everything else
speaks `GradedTask`, and an arm is still a configuration rather than a code path: the bare/tools/
tools+skills difference is three values of `[[environment.mcp_servers]]` plus two `[environment]`
keys, which is FR-023 satisfied by the published schema instead of by a branch per harness.

Four decisions worth stating, because each one is a place a plausible alternative produces a number
that grades nothing:

- **The exporter refuses.** `validate_shape` and then the live `validate_live` run before the first
  directory is created, so a task with no reference solution, or a check that only prints one verdict
  word, or a check that already passes against its own untouched fixture, leaves nothing on disk to
  run. That last one is the 118 failure class: every arm clears the task and the report says 0.00
  lift with the tools working perfectly.
- **Fixtures travel as data, not as an image.** `environment/seed.sh` carries each fixture inline in
  a heredoc and applies it through `doc put -f`, so a corpus of 40 tasks is 40 directories against
  one image rather than 40 image builds. Harbor's single-step task has no `setup.sh`, so the seed is
  wired as `[environment.healthcheck] command`, and it holds a marker file: a healthcheck runs again
  while the agent is working, and a second seed would overwrite the agent's answer with the fixture.
- **The reward is a file, and an unreadable check writes no file.** `check_verdict`'s third answer in
  bash. Harbor reads a missing `reward.txt` as a trial with no reward, which is the honest reading of
  a check that said neither PASS nor FAIL; writing `0` there files a harness fault in the arm's
  column, the same mistake as scoring a killed session zero.
- **The image tag is pinned to the workspace version.** The tools are the thing under test, so the
  environment must not go looking for a newer surface halfway through a run.

The one part no run has confirmed is the route out: `network_mode = "allowlist"` with
`allowed_hosts = ["${IRIS_HOST}"]` is what Harbor's docs describe and what spec 121's T002 recorded,
but whether `${VAR}` templating reaches `allowed_hosts` as well as `[environment.env]` is unverified
until `harbor run --env docker` runs here. It matters: a task container with no route to IRIS fails
every arm for the same reason, which is a broken corpus that reads as a broken tool.
"""

from __future__ import annotations

import os
import shutil
import stat
import tomllib
from dataclasses import dataclass

from tests.e2e.skill_eval import graded_task
from tests.e2e.skill_eval.arms import (
    ARMS,
    TOOLS_ARM_TOOLSET,
    Arm,
    task_toml_environment,
)
from tests.e2e.skill_eval.graded_task import CorpusInvalid, Document, GradedTask

#: Harbor's task schema this exporter writes. Pinned, not floating: a schema bump is a code change
#: here plus a golden-file diff, not a corpus that silently stops loading.
SCHEMA_VERSION = "1.3"

IMAGE_REPO = "ghcr.io/intersystems-community/iris-agentic-dev"
TASK_ORG = "intersystems"
AUTHORS = ("Thomas Dyar <thomas.dyar@intersystems.com>",)

#: Where the Dockerfile puts the binary, and therefore what `[[environment.mcp_servers]] command` is.
SANDBOX_BINARY = "/usr/local/bin/iris-agentic-dev"
SANDBOX_SEED = "/usr/local/bin/seed.sh"
SANDBOX_SKILLS = "/skills"
SANDBOX_WORKDIR = "/workspace"

#: Harbor's documented verifier log directory. Overridable through `REWARD_DIR` so the reward
#: contract is testable outside a container at all — see `test_reward_file.py`.
REWARD_DIR = "/logs/verifier"

DEFAULT_AGENT_TIMEOUT_SEC = 600.0
DEFAULT_VERIFIER_TIMEOUT_SEC = 120.0

BASE_IMAGE = "ubuntu:24.04"

#: How the task container reaches IRIS. `allowlist` plus `allowed_hosts` is what Harbor documents for
#: a service outside the container (spec 121 research.md § IRIS reachability), and a shared reachable
#: IRIS is spec 120 decision 1's answer — `iris-agentic-dev` is an Atelier REST client, so IRIS does
#: not have to live in the rollout sandbox.
NETWORK_MODE = "allowlist"
ALLOWED_HOSTS = ("${IRIS_HOST}",)

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


class ExportRefused(RuntimeError):
    """This task is not allowed out as a Harbor task, and no directory was written for it."""


@dataclass(frozen=True)
class ExportedTask:
    task_id: str
    arm: str
    directory: str


def workspace_version() -> str:
    """The workspace version, read from `Cargo.toml` — the one source the rest of the repo asserts."""
    with open(os.path.join(_REPO_ROOT, "Cargo.toml"), "rb") as handle:
        return tomllib.load(handle)["workspace"]["package"]["version"]


def arm_slug(arm: Arm) -> str:
    """`tools+skills` is an arm name; `tools-skills` is a directory name."""
    return arm.name.replace("+", "-")


def default_image() -> str:
    return f"{IMAGE_REPO}:v{workspace_version()}"


# --- the export ----------------------------------------------------------------------------------


def export_task(
    task: GradedTask,
    arm: Arm,
    out_root: str,
    *,
    validate=graded_task.validate_live,
    skills_root: str | None = None,
    image: str | None = None,
    agent_timeout_sec: float = DEFAULT_AGENT_TIMEOUT_SEC,
    verifier_timeout_sec: float = DEFAULT_VERIFIER_TIMEOUT_SEC,
) -> ExportedTask:
    """Write one arm of one task, or refuse and write nothing.

    `validate` defaults to the live check because that is the only half that can answer FR-004 and
    FR-022; an export that skips IRIS has to say so at the call site.
    """
    _refuse_ungradable(task, validate)
    return _write(
        task,
        arm,
        out_root,
        skills_root=skills_root,
        image=image or default_image(),
        agent_timeout_sec=agent_timeout_sec,
        verifier_timeout_sec=verifier_timeout_sec,
    )


def export_arms(
    task: GradedTask,
    out_root: str,
    *,
    arms: tuple[Arm, ...] = ARMS,
    validate=graded_task.validate_live,
    skills_root: str | None = None,
    image: str | None = None,
    agent_timeout_sec: float = DEFAULT_AGENT_TIMEOUT_SEC,
    verifier_timeout_sec: float = DEFAULT_VERIFIER_TIMEOUT_SEC,
) -> tuple[ExportedTask, ...]:
    """Every arm of one source task. The validator runs once, not once per arm — it costs a live IRIS
    round trip and the three arms share one source task."""
    _refuse_ungradable(task, validate)
    return tuple(
        _write(
            task,
            arm,
            out_root,
            skills_root=skills_root,
            image=image or default_image(),
            agent_timeout_sec=agent_timeout_sec,
            verifier_timeout_sec=verifier_timeout_sec,
        )
        for arm in arms
    )


def _refuse_ungradable(task: GradedTask, validate) -> None:
    """Both halves of corpus validation, translated into one refusal (FR-005).

    Runs before anything is created, so a refused task leaves no half-written directory for a later
    run to pick up and grade.
    """
    for stage in (graded_task.validate_shape, validate):
        try:
            stage(task)
        except CorpusInvalid as invalid:
            raise ExportRefused(f"refusing to export {task.id}: {invalid}") from invalid


def _write(
    task: GradedTask,
    arm: Arm,
    out_root: str,
    *,
    skills_root: str | None,
    image: str,
    agent_timeout_sec: float,
    verifier_timeout_sec: float,
) -> ExportedTask:
    slug = f"{task.id.lower()}-{arm_slug(arm)}"
    directory = os.path.join(out_root, slug)
    environment = os.path.join(directory, "environment")
    os.makedirs(environment, exist_ok=True)
    os.makedirs(os.path.join(directory, "tests"), exist_ok=True)
    os.makedirs(os.path.join(directory, "solution"), exist_ok=True)

    skills_installed = _copy_skills(arm, environment, skills_root)

    _write_text(os.path.join(directory, "instruction.md"), task.prompt)
    _write_text(
        os.path.join(directory, "task.toml"),
        _render_task_toml(
            task,
            arm,
            slug,
            skills=skills_installed,
            agent_timeout_sec=agent_timeout_sec,
            verifier_timeout_sec=verifier_timeout_sec,
        ),
    )
    _write_text(
        os.path.join(environment, "Dockerfile"),
        _dockerfile(image, skills=skills_installed),
    )
    _write_script(
        os.path.join(environment, "seed.sh"), _seed_script(task, task.fixtures)
    )
    _write_script(
        os.path.join(directory, "solution", "solve.sh"),
        _solve_script(task, task.solution),
    )
    _write_script(os.path.join(directory, "tests", "test.sh"), _test_script(task))
    return ExportedTask(task_id=task.id, arm=arm.name, directory=directory)


def _copy_skills(arm: Arm, environment: str, skills_root: str | None) -> bool:
    """Copy the pack into the build context, skills arm only.

    Harbor does not upload skills separately: they live in the environment build context, go into the
    image, and `environment.skills_dir` points at them. A skills arm with no pack to copy is worth an
    exception rather than an image without them — that is 118 exactly, nine skills reporting 0% from
    sessions that never had them.
    """
    if not arm.skills:
        return False
    if not skills_root:
        return False
    if not os.path.isdir(skills_root):
        raise ExportRefused(
            f"the {arm.name} arm names a skills pack at {skills_root}, which does not exist — an "
            "arm missing what it is named for reports its number as the skills'"
        )
    shutil.copytree(
        skills_root, os.path.join(environment, "skills"), dirs_exist_ok=True
    )
    return True


# --- task.toml -----------------------------------------------------------------------------------


def _render_task_toml(
    task: GradedTask,
    arm: Arm,
    slug: str,
    *,
    skills: bool,
    agent_timeout_sec: float,
    verifier_timeout_sec: float,
) -> str:
    lines = [
        f"schema_version = {_value(SCHEMA_VERSION)}",
        "",
        "[task]",
        f"name = {_value(f'{TASK_ORG}/{slug}')}",
        f"authors = {_value(list(AUTHORS))}",
        f"description = {_value(_description(task, arm))}",
        f"keywords = {_value(['iris', 'objectscript', 'iris-agentic-dev', arm.name])}",
        "",
        "[metadata]",
        f"source_task = {_value(task.id)}",
        f"arm = {_value(arm.name)}",
        f"tools = {_value(arm.tools)}",
        f"skills = {_value(arm.skills)}",
        "",
        "[agent]",
        f"timeout_sec = {_value(float(agent_timeout_sec))}",
        "",
        "[verifier]",
        f"timeout_sec = {_value(float(verifier_timeout_sec))}",
        "",
        "[environment]",
        "# A shared reachable IRIS, allowlisted — decision 1's answer, and what Harbor documents for a",
        "# task container that has to reach a service outside it. Every arm needs this route equally: a",
        "# task with no route to IRIS fails all three for the same reason and reads as a broken tool.",
        f"network_mode = {_value(NETWORK_MODE)}",
        f"allowed_hosts = {_value(list(ALLOWED_HOSTS))}",
        f"workdir = {_value(SANDBOX_WORKDIR)}",
    ]
    if skills:
        lines.append(f"skills_dir = {_value(SANDBOX_SKILLS)}")
    lines += [
        "",
        "[environment.env]",
    ]
    for key, item in _environment_env(task, arm).items():
        lines.append(f"{key} = {_value(item)}")
    lines += [
        "",
        "# Harbor's single-step task has no setup hook, so the fixture is applied by the healthcheck.",
        "# `seed.sh` holds a marker file: this command runs again during the session, and a second",
        "# seed would overwrite the agent's answer with the fixture it was asked to fix.",
        "[environment.healthcheck]",
        f"command = {_value(SANDBOX_SEED)}",
        "interval_sec = 30",
        "timeout_sec = 120",
        "start_period_sec = 5",
        "retries = 3",
    ]
    for server in task_toml_environment(arm, binary=SANDBOX_BINARY).get(
        "mcp_servers", ()
    ):
        lines += [
            "",
            "[[environment.mcp_servers]]",
            f"name = {_value(server['name'])}",
            f"transport = {_value(server['transport'])}",
            f"command = {_value(server['command'])}",
            f"args = {_value(list(server['args']))}",
        ]
    return "\n".join(lines) + "\n"


def _description(task: GradedTask, arm: Arm) -> str:
    """The prompt's first sentence, unwrapped. Harbor shows this in listings.

    Sentence and not first line: the corpus wraps its prompts, so a line-based cut lands mid-clause.
    """
    collapsed = " ".join(task.prompt.split())
    head, separator, _rest = collapsed.partition(". ")
    sentence = (head + separator).strip() if separator else collapsed
    if len(sentence) > 160:
        sentence = sentence[:157].rstrip() + "…"
    return f"{task.id} ({arm.name}): {sentence or task.id}"


def _environment_env(task: GradedTask, arm: Arm) -> dict:
    """The connection, as Harbor template syntax — resolved from the host at run time.

    `${VAR}` and not a literal: a committed corpus with a password in it is a credential leak, and
    one with a hostname in it only runs on my laptop.
    """
    env = {
        "IRIS_HOST": "${IRIS_HOST}",
        "IRIS_WEB_PORT": "${IRIS_WEB_PORT}",
        "IRIS_USERNAME": "${IRIS_USERNAME}",
        "IRIS_PASSWORD": "${IRIS_PASSWORD}",
        "IRIS_NAMESPACE": task.namespace,
    }
    if arm.tools:
        # The reach denominator (contracts/arm.md). The bare arm names no toolset, because it has no
        # tools to name — an env var here would be a registration the arm claims not to have.
        env["IRIS_TOOLSET"] = TOOLS_ARM_TOOLSET
    return env


def _value(value) -> str:
    """The three TOML types this file emits. Hand-rendered so the exporter adds no dependency."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_value(item) for item in value) + "]"
    escaped = (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


# --- the build context and the scripts -----------------------------------------------------------


def _dockerfile(image: str, *, skills: bool) -> str:
    lines = [
        "# The task image for one arm of the iris-agentic-dev benchmark.",
        "#",
        "# The iad binary is copied out of the published release image at a pinned tag. The tools are",
        "# what this benchmark measures, so the environment must not resolve a newer surface than the",
        "# run it is part of. A floating tag is not allowed here, ever.",
        f"FROM {image} AS iad",
        "",
        f"FROM {BASE_IMAGE}",
        "RUN apt-get update \\",
        " && apt-get install -y --no-install-recommends ca-certificates curl \\",
        " && rm -rf /var/lib/apt/lists/*",
        f"COPY --from=iad /iris-agentic-dev {SANDBOX_BINARY}",
        f"COPY seed.sh {SANDBOX_SEED}",
        f"RUN chmod +x {SANDBOX_BINARY} {SANDBOX_SEED}",
    ]
    if skills:
        lines.append(f"COPY skills/ {SANDBOX_SKILLS}/")
    lines += [
        f"WORKDIR {SANDBOX_WORKDIR}",
        "",
    ]
    return "\n".join(lines)


def _apply_documents(documents: tuple[Document, ...], *, tolerate_compile: bool) -> str:
    """Write each document to disk, then push it through `doc put -f`, then compile it.

    `-f <file>` and not `doc put -` reading stdin: `-` is taken as the document name (a CLI defect
    worth its own issue), and a heredoc keeps the ObjectScript exactly as the corpus has it with no
    JSON escaping in between.
    """
    lines: list[str] = []
    for index, doc in enumerate(documents, start=1):
        marker = f"IAD_DOC_{index}_EOF"
        lines += [
            f"cat > \"$work/{doc.name}.cls\" <<'{marker}'",
            doc.content.rstrip("\n"),
            marker,
            f'"$IAD" doc -n "$NS" put {doc.name} -f "$work/{doc.name}.cls"',
        ]
    lines.append("")
    for doc in documents:
        compile_call = (
            f'"$IAD" tool iris_compile -a '
            f'\'{{"target": "{doc.name}.cls", "namespace": "\'"$NS"\'"}}\''
        )
        lines.append(compile_call + (" || true" if tolerate_compile else ""))
    return "\n".join(lines)


def _seed_script(task: GradedTask, fixtures: tuple[Document, ...]) -> str:
    return f"""#!/usr/bin/env bash
# Seed {task.id}'s fixture into {task.namespace}. Wired as `[environment.healthcheck] command`,
# because a single-step Harbor task has no setup hook.
#
# The marker file is the whole reason this is safe to run from a healthcheck: the command fires again
# every interval, and a second seed would put the broken fixture back over whatever the agent fixed.
#
# The compile is allowed to fail. A fixture that does not compile is the task in most of this corpus,
# and a non-zero exit here would mean the fixture never landed at all.
set -uo pipefail

MARKER="${{SEED_MARKER:-/tmp/.iad-seeded-{task.id.lower()}}}"
if [ -f "$MARKER" ]; then
  exit 0
fi

NS="${{IRIS_NAMESPACE:-{task.namespace}}}"
IAD="${{IAD_BINARY:-iris-agentic-dev}}"
work="$(mktemp -d)"

{_apply_documents(fixtures, tolerate_compile=True)}

# Named files and `rmdir`, not `rm -rf` on a variable. This runs as the container's healthcheck, and
# a recursive delete rooted on an expansion is not something to leave in a script that runs on a loop.
rm -f "$work"/*.cls
rmdir "$work" 2>/dev/null || true

# Last, and deliberately: the marker means "the fixture is in place", so nothing may set it earlier.
touch "$MARKER"
"""


def _solve_script(task: GradedTask, solution: tuple[Document, ...]) -> str:
    return f"""#!/usr/bin/env bash
# The reference solution for {task.id}, applied the same way the fixture was.
#
# This is what tells a hard task from a check that cannot grade (FR-022). Harbor runs it in place of the agent,
# and the verifier must then report a reward of 1.0; if it does not, the task grades nothing and no
# arm's score from it means anything.
set -euo pipefail

NS="${{IRIS_NAMESPACE:-{task.namespace}}}"
IAD="${{IAD_BINARY:-iris-agentic-dev}}"
work="$(mktemp -d)"

{_apply_documents(solution, tolerate_compile=False)}

rm -f "$work"/*.cls
rmdir "$work" 2>/dev/null || true
"""


def _test_script(task: GradedTask) -> str:
    """The verifier. Three outcomes and not two — see the module docstring."""
    return f"""#!/usr/bin/env bash
# The verifier for {task.id}. Runs this task's own deterministic check and writes Harbor's reward
# file. No model, no rubric, no judge: the check prints PASS or FAIL from IRIS state (FR-003).
#
# Three outcomes, not two. A check that printed neither word, or both, or that could not run at all
# has graded nothing, and this writes no reward file for it — Harbor reads a missing reward as a
# trial with no reward, which is honest, where a `0` would file a harness fault in the arm's column.
set -uo pipefail

REWARD_DIR="${{REWARD_DIR:-{REWARD_DIR}}}"
NS="${{IRIS_NAMESPACE:-{task.namespace}}}"
IAD="${{IAD_BINARY:-iris-agentic-dev}}"

# shellcheck disable=SC2016  # the quoted text is ObjectScript; $classmethod is not a shell expansion
output="$("$IAD" exec -n "$NS" {_shell_single_quote(task.check)} 2>&1)"
status=$?
if [ "$status" -ne 0 ]; then
  printf 'the check exited %s, so it answered neither PASS nor FAIL and no reward was written:\\n%s\\n' \\
    "$status" "$output" >&2
  exit 1
fi

has_pass=0
has_fail=0
case "$output" in *PASS*) has_pass=1 ;; esac
case "$output" in *FAIL*) has_fail=1 ;; esac

if [ "$has_pass" -eq 1 ] && [ "$has_fail" -eq 0 ]; then
  reward=1.0
elif [ "$has_fail" -eq 1 ] && [ "$has_pass" -eq 0 ]; then
  reward=0.0
else
  printf 'check output is neither PASS nor FAIL, so it graded nothing and no reward was written: %s\\n' \\
    "$output" >&2
  exit 1
fi

mkdir -p "$REWARD_DIR"
printf '%s\\n' "$reward" > "$REWARD_DIR/reward.txt"
"""


def _shell_single_quote(text: str) -> str:
    """Single-quote for `sh`, the only way to hand ObjectScript to a shell unchanged.

    `$select`, `$$$OK` and `"PASS"` all mean something to bash and nothing good.
    """
    return "'" + text.strip("\n").replace("'", "'\\''") + "'"


def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text if text.endswith("\n") else text + "\n")


def _write_script(path: str, text: str) -> None:
    _write_text(path, text)
    mode = os.stat(path).st_mode
    os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
