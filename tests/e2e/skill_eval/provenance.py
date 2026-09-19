"""What a measurement was taken under — 118 T005.

Two jobs, and they are here together because the second needs the first:

1. Find the `iris-agentic-dev` binary the agent sessions should run. This used to be a
   string literal in `isolated_env.py` pointing at a Homebrew path, so on a GitHub runner
   every session started with no iad tools at all and the harness recorded the resulting
   zeros as skill measurements for a month.
2. Record the tool surface, scorer model, and task set a number was measured under, so a
   later run can say whether its number is comparable rather than assuming it is.

`tool --list --json` reads the tool router and makes no IRIS connection, so the surface
resolves on a machine with no container.
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import json
import os
import shutil
import subprocess
from typing import Optional

HOMEBREW_FALLBACK = "/opt/homebrew/bin/iris-agentic-dev"

#: What `driver` says when nothing recorded which harness ran. A stated fact, like
#: `tool_surface: "none"` — every provenance block written before 120 FR-012 reads this way, and
#: a run nobody attributed is a run nobody can compare.
DRIVER_UNRECORDED = "unrecorded"

# The binary answers both of these without touching IRIS.
_LIST_ARGS = ("tool", "--list", "--json")
_VERSION_ARGS = ("--version",)

_TIMEOUT_S = 20


@dataclasses.dataclass(frozen=True)
class BinaryCandidate:
    """One place the binary was looked for, and whether it was there."""

    source: str  # "IAD_BINARY" | "PATH" | "fallback"
    path: Optional[str]
    usable: bool

    def describe(self) -> str:
        where = self.path or "(unset)"
        return f"{self.source}: {where} {'ok' if self.usable else '(not found)'}"


def _usable(path: Optional[str]) -> bool:
    return bool(path) and os.path.isfile(path) and os.access(path, os.X_OK)


def binary_candidates() -> list[BinaryCandidate]:
    """The three places, in order, each with its verdict.

    Reported in full rather than short-circuited: the preflight's job is to tell someone
    which of the three to fix, and it cannot do that from a bare `None`.
    """
    explicit = os.environ.get("IAD_BINARY") or None
    on_path = shutil.which("iris-agentic-dev")
    return [
        BinaryCandidate("IAD_BINARY", explicit, _usable(explicit)),
        BinaryCandidate("PATH", on_path, _usable(on_path)),
        BinaryCandidate("fallback", HOMEBREW_FALLBACK, _usable(HOMEBREW_FALLBACK)),
    ]


def resolve_binary() -> Optional[str]:
    """The first usable binary, or None.

    An `IAD_BINARY` that does not resolve stops resolution instead of falling through. CI
    sets it to the release artifact it means to measure; quietly measuring a different
    build would produce a number that answers a question nobody asked.
    """
    candidates = binary_candidates()
    if candidates[0].path is not None:
        return candidates[0].path if candidates[0].usable else None
    for candidate in candidates[1:]:
        if candidate.usable:
            return candidate.path
    return None


def _run(binary: str, args: tuple[str, ...]) -> Optional[str]:
    try:
        proc = subprocess.run(
            [binary, *args],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def binary_version(binary: Optional[str]) -> Optional[str]:
    """The version string alone, e.g. `1.4.1` from `iris-agentic-dev 1.4.1`."""
    if not binary:
        return None
    out = _run(binary, _VERSION_ARGS)
    if not out:
        return None
    parts = out.strip().split()
    return parts[-1] if parts else None


def tool_list(binary: Optional[str]) -> Optional[list[dict]]:
    """The `{name, summary}` records the binary advertises, or None if it would not say."""
    if not binary:
        return None
    out = _run(binary, _LIST_ARGS)
    if not out:
        return None
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return None
    tools = payload.get("tools")
    return tools if isinstance(tools, list) else None


def surface_hash(tools: list[dict]) -> Optional[str]:
    """12 hex over the sorted `name\tsummary` pairs, or None for an empty surface.

    Sorted, because the router's ordering is not part of the contract and two runs must not
    look like two surfaces over a shuffled list. Summaries included, because descriptions
    are what the GEPA optimizer edits — a lift that moved because a description was
    rewritten and one that moved because a skill changed should be distinguishable in the
    record. Nothing gates on the value; a differing surface annotates a comparison.
    """
    if not tools:
        return None
    lines = sorted(f"{t.get('name', '')}\t{t.get('summary', '')}" for t in tools)
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:12]


def tool_surface(binary: Optional[str]) -> str:
    """`<version>+<12 hex>`, or the literal `"none"`.

    `"none"` is a measurement fact, not a missing value: it says the session ran without
    iad tools. That is exactly the state the 2026-08 nightlies were in, and it should be
    legible in the baseline file rather than absent from it.
    """
    tools = tool_list(binary)
    digest = surface_hash(tools or [])
    version = binary_version(binary)
    if digest is None or version is None:
        return "none"
    return f"{version}+{digest}"


def driver_identity(driver) -> dict:
    """`{driver, harness_version}` off an `AgentDriver` — 120 FR-012.

    Read from the driver object rather than passed in as a string at the call site: `opencode`
    drove spec 121's pilot and `prime-agent` is the candidate, and the whole point of the driver
    boundary is that the layer above it does not know which one ran. A call site that knows the
    name well enough to hard-code it has already broken that.

    A driver that cannot say its version records `None`. `harness_version(...)` below is the
    best-effort way to find one; a guess would be worse than the absence.
    """
    if driver is None:
        return {"driver": DRIVER_UNRECORDED, "harness_version": None}
    return {
        "driver": getattr(driver, "name", None) or DRIVER_UNRECORDED,
        "harness_version": getattr(driver, "harness_version", None),
    }


def harness_version(binary: str) -> Optional[str]:
    """`<binary> --version`, last whitespace-separated token, or None.

    Best-effort on purpose. An agent harness that will not report its version still runs
    sessions, and the run is worth having with the field empty — but the field then says empty
    rather than saying something plausible.
    """
    out = _run(binary, _VERSION_ARGS)
    if not out:
        return None
    parts = out.strip().split()
    return parts[-1] if parts else None


def harness_commit() -> Optional[str]:
    """Short SHA of the harness tree, when git can say. A tarball checkout cannot."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _docker(*args: str) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["docker", *args],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    return out or None


def container_identity(container: str) -> dict:
    """What IRIS the sessions were graded against — FR-020's container image digest.

    Three facts, because they answer three different questions. `image` is the tag someone would
    type, and a tag moves: `iris-community:2026.2` today and `iris-community:2026.2` after the next
    push are different images with the same name. `image_digest` is the RepoDigest, which is what
    another machine can actually pull. `image_id` is the local config digest, which exists even for
    an image built here and never pushed.

    A container that is not running yields Nones. A benchmark figure measured against nothing is not
    a figure, so the caller refuses — but that refusal belongs to the caller, and this records what is
    true rather than raising inside a provenance block.
    """
    image = _docker("inspect", "-f", "{{.Config.Image}}", container)
    image_id = _docker("inspect", "-f", "{{.Image}}", container)
    digest = None
    if image:
        digest = _docker("image", "inspect", "-f", "{{index .RepoDigests 0}}", image)
    return {
        "container": container,
        "image": image,
        "image_id": image_id,
        "image_digest": digest,
    }


def corpus_identity() -> dict:
    """Which corpus the tasks were read from — FR-020's corpus commit.

    Separate from `harness_commit` even though the two are the same SHA today. They are two claims: a
    corpus can be pinned while the harness moves, and a figure re-measured a year later has to know
    which task files produced it.

    `corpus_dirty` is the honest half. A commit names the corpus only if the files on disk are that
    commit; uncommitted edits mean the SHA identifies something the reader cannot get back.
    """
    from tests.e2e.skill_eval import graded_task

    repo = os.path.dirname(os.path.abspath(__file__))
    commit = _git(repo, "rev-parse", "HEAD")
    status = _git(repo, "status", "--porcelain", graded_task.BENCHMARK_DIR)
    try:
        count = len(graded_task.all_tasks())
    except (
        Exception
    ):  # a corpus that will not load is a count of zero, not a crash here
        count = 0
    return {
        "corpus_commit": commit,
        "corpus_dirty": bool(status),
        "corpus_task_count": count,
    }


def _git(cwd: str, *args: str) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            cwd=cwd,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


@dataclasses.dataclass
class Provenance:
    """data-model.md § 3. What makes an old number comparable, or explains why it is not."""

    run_id: str
    task_ids: list[str]
    scoring_mode: str
    scorer_model: Optional[str]
    scorer_model_requested: Optional[str]
    tool_surface: str
    runs: int
    measured_at: str = dataclasses.field(default_factory=_utc_now)
    harness_commit: Optional[str] = dataclasses.field(default_factory=harness_commit)
    # 120 FR-012. Which agent harness drove the sessions, and at what version. Defaulted rather
    # than required so the entries already in the committed baseline still load — they were
    # measured before anyone recorded it, and `unrecorded` is what happened.
    driver: str = DRIVER_UNRECORDED
    harness_version: Optional[str] = None
    # 121 T038 / FR-020. The five facts a published benchmark figure needs beyond the scorer's: which
    # model drove the sessions, which IRIS they ran against, which corpus they were read from, and how
    # many items the interval was computed over. All optional, because the committed skill-eval
    # baseline predates every one of them and still has to load.
    agent_model: Optional[str] = None
    container: Optional[str] = None
    image: Optional[str] = None
    image_digest: Optional[str] = None
    image_id: Optional[str] = None
    corpus_commit: Optional[str] = None
    corpus_dirty: Optional[bool] = None
    corpus_task_count: Optional[int] = None
    item_counts: dict = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        # Sorted here rather than at every call site: the task set is compared for equality,
        # and two orderings of one corpus are one corpus.
        self.task_ids = sorted(self.task_ids)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Provenance":
        fields = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in fields})
