# Feature Specification: One task format, one agent boundary, one split

**Feature Branch**: `121-benchmark-program` (adopted; the material arrived on
`claude/repo2rlenv-iris-setup-w8xij5`)
**Created**: 2026-09-16 | **Scope agreed**: 2026-09-18
**Status**: Draft
**Input**: [research.md](./research.md) and [plan.md](./plan.md), written as a proposal with no
scope. Spec 121 then consumed three of that proposal's decisions as prerequisites — the Harbor task
format, the agent-driver boundary, and the committed train/holdout split — and its Phase 4 stalled
because a dependency on prose is not a dependency on code. This spec gives that prose a scope, so
the three things 121 reads have owners.

## What changed, and why this file exists

`plan.md` opens with "Nothing here is implemented yet... There is no `spec.md` or `tasks.md`
because scope is not agreed." Spec 121's Phase 0 (T001–T005) then recorded four decisions out of it
in writing, its `tasks.md:262` declared "Spec 120 Slice 1 gates T002, T003, T004 and therefore T025
and T032", and nothing anywhere created the code that line depends on. Two of Slice 1's seven steps
— the exporter and the declared driver interface — had no task in either spec.

Two facts narrow the scope from the original proposal:

1. **Spec 121's pilot ran without any of it.** 24 sessions, three arms, eight tasks, graded by
   ObjectScript writing `PASS`/`FAIL`, against one shared `iris-dev-iris` over Atelier REST. No
   `task.toml`, no `/logs/verifier/reward.txt`, no Docker socket in the loop. So the format is not
   what makes a number possible; it is what makes the number **portable to another agent and
   reproducible by someone else**, which is spec 121's Story 6 and SC-008.
2. **The incumbent harness is not the chosen one.** The pilot drove `opencode`, and
   `tests/e2e/skill_eval/arms.py` bakes that in: the bare arm's absence check reads
   `OPENCODE_CONFIG_CONTENT`, and nothing else. Prime Intellect's `prime-agent` is under evaluation
   here as the harness, so the boundary in Slice 1 step 4 stops being a tidiness argument and
   becomes the thing that decides whether swapping harnesses costs a day or a rewrite.

## User Scenarios & Testing _(mandatory)_

### User Story 1 — A task I wrote once runs under a second agent (Priority: P1)

I have a graded task that passes under one harness. I export it, point a different agent at the
same directory, and get a reward from the same verifier without editing the task.

**Why P1**: it is the only story that makes spec 121's SC-008 ("a fresh clone reproduces the
published pass rates") checkable by anyone who is not me, and it is the story the harness change
puts a deadline on.

**Acceptance**:

1. **Given** a source task in `tests/e2e/tasks/benchmark/`, **When** I export it, **Then** I get a
   directory holding `instruction.md`, `task.toml`, `environment/`, `tests/test.sh` and
   `solution/solve.sh`, with `schema_version = "1.3"`.
2. **Given** that directory, **When** the verifier runs, **Then** the reward arrives as a file at
   `/logs/verifier/reward.txt`, not as an exit code.
3. **Given** the same directory, **When** the format drifts upstream, **Then** a golden-file test
   fails with a diff rather than a run silently grading nothing.

### User Story 2 — Swapping the agent does not touch the arms, the checks, or the corpus (Priority: P1)

I change which agent drives a run. The three arms, the checks, the pairing and the statistics are
unchanged, because the agent sits behind one declared interface.

**Why P1**: `arms.py` currently asserts the bare arm's emptiness by reading one opencode
environment variable. Under a second harness that assertion is not weaker, it is **vacuous** — it
would pass on a contaminated arm, which is FR-002's whole failure mode and the 118 bug class.

**Acceptance**:

1. **Given** the declared interface, **When** a driver returns a run, **Then** it carries the
   transcript, a tool-call log, a scalar reward, a `scored` flag, and `logprobs` (None for every
   subprocess driver).
2. **Given** a second driver, **When** the bare arm is asserted absent, **Then** the assertion
   covers that driver's own configuration path and raises when it holds an MCP registration.
3. **Given** a fake driver in a unit test, **When** it returns `scored=False` with a reward,
   **Then** the boundary raises rather than recording a zero.

### User Story 3 — The split exists before the first published number (Priority: P2)

The corpus carries a committed train/holdout split, and the publish path refuses a figure computed
over a train task.

**Why P2**: GEPA optimises tool descriptions against this corpus. A figure measured on tasks the
descriptions were fitted to overstates the tool's value, and after the fact there is no way to
claim otherwise. Spec 121 owns the guard (T032, T033); this spec owns the mechanism and the file's
location.

**Acceptance**:

1. **Given** the corpus, **When** I read `split.toml` beside it, **Then** every task ID appears in
   exactly one of `train` and `holdout`.
2. **Given** a published figure, **When** any task in it is in `train`, **Then** the publish path
   raises.

### User Story 4 — A rollout record says which policy and which driver produced it (Priority: P3)

Every record carries the driver kind and the harness version alongside the tool surface and model
identity already stamped.

**Why P3**: two runs of the same corpus under two harnesses are not the same measurement, and the
only thing that makes them distinguishable six months later is a field. It is cheap now and
unrecoverable later.

**Acceptance**:

1. **Given** any run record, **When** I read its provenance, **Then** it names the driver kind and
   the harness version.
2. **Given** two records differing only in driver kind, **When** a Δ is requested, **Then** it is
   annotated, exactly as a tool-surface difference is annotated today.

### Edge Cases

- **The new harness cannot express an arm.** `prime-agent` treats skills as importable Python
  packages; iad ships 34 `SKILL.md` directories. If the third arm cannot be built as configuration,
  that is a recorded blocker, not a silently different arm.
- **Headless MCP is undocumented.** The `prime-agent` README documents JSON and RPC modes and its
  MCP doc documents interactive setup. Whether a pinned stdio MCP server is honoured in headless
  mode is a probe, and a negative result stops the adoption.
- **An exported task that grades nothing.** A `tests/test.sh` that passes against the untouched
  fixture is the vacuity bug in Harbor clothing. Export must carry the precondition-fails fact, not
  drop it.
- **`repo2rlenv` yields nothing usable on a Rust workspace.** Its own docs call Rust parsers
  experimental. That is a measurement with a cheap negative result, not a dependency.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: A single exporter turns one source task into one Harbor task directory. It is the only
  code that knows the layout.
- **FR-002**: The emitted `task.toml` is asserted by parsing the emitted **string**, not a dict
  literal, and pins `schema_version = "1.3"`.
- **FR-003**: A golden-file test covers one complete exported task directory.
- **FR-004**: The reward reaches the harness as a file (`/logs/verifier/reward.txt` or
  `reward.json`), and the exporter refuses a task whose check has no deterministic verdict.
- **FR-005**: Export refuses a task lacking a reference solution, and refuses one whose check passes
  against the untouched fixture.
- **FR-006**: An agent driver is a declared interface: prompt in; transcript, tool-call log, scalar
  reward, `scored` flag, `logprobs` out. `logprobs` is `None` for every subprocess driver.
- **FR-007**: `opencode_runner.py`, `claude_code.py` and `copilot.py` become implementations of that
  interface without changing their observable behaviour.
- **FR-008**: A second driver implementation exists for `prime-agent`, registering the iad MCP server
  over stdio as configuration.
- **FR-009**: The bare arm's absence assertion is driver-supplied: each driver names the
  configuration paths and environment variables that could carry an MCP registration or a reachable
  skill, and the assertion raises on any of them. A driver that names none fails the arm rather than
  passing it.
- **FR-010**: Unscored trajectories are dropped at the boundary, never zeroed. `scored=False` holding
  a reward, and `scored=True` holding none, both raise.
- **FR-011**: The train/holdout split is a committed file beside the corpus, with every task ID in
  exactly one side.
- **FR-012**: Run provenance records driver kind and harness version. A difference in either
  annotates a Δ; it does not suppress one.
- **FR-013**: The tool-call log used for per-tool attribution comes from the driver, not from IRIS
  telemetry, so a call that failed before reaching IRIS is still counted.

### Key Entities

- **AgentDriver** — the boundary. Name, harness version, `run(prompt, config) -> DriverRun`, and the
  absence facts it can assert.
- **DriverRun** — transcript, tool-call log, reward, `scored`, `logprobs`.
- **HarborTask** — the exported directory, and the `schema_version` it was written against.
- **Split** — `train` and `holdout` ID lists, and the corpus they must exactly cover.

## Decisions

`research.md` § Open decisions left four. Two blocked spec 121 and are closed here; two do not and
are deferred with the event that reopens them.

### Decision 1 — Shared IRIS over Atelier REST is primary. CLOSED.

The compose sidecar is retained for Tier 2 only and is not on the publish path.

Evidence: spec 121's pilot ran 24 graded sessions against one shared `iris-dev-iris` over Atelier
REST on 52780, resetting fixtures per task rather than booting a container per rollout, and no
session needed a Docker socket. Consequence, stated so nobody re-derives it: `docker_only=true`
— the NoPWS workaround for Enterprise 2026.2.0AI (DPP-1192) — is **out of the graded path**, because
it needs a local socket and therefore co-located IRIS. The grading target is a Community image with
PWS, which is the same conclusion spec 121 reached in its § Image decision from the other direction.

Unproven and therefore a task: namespace-per-rollout. The pilot ran serial in one `BENCHMARK`
namespace. Spec 121's Constitution Check claims per-task namespace creation and refusal, which is
its open finding C4; the isolation primitive lands here, where the concurrency it exists for lives.

### Decision 2 — Harness optimization, not policy training. CLOSED.

No GPUs, no trainer, no behaviour logprobs. Every driver returns `logprobs: None` and the interface
keeps the field so a vLLM-backed driver is an addition rather than a rewrite.

The FlashREINFORCE material in `research.md` stays as research. One of its findings survives the
decision and is promoted to FR-010 because it is correctness either way: an unscorable item admitted
as `0` is a misleading nightly under an eval harness and a biased gradient under a batch-centred
trainer, and the same rule fixes both.

### Decision 3 — Terraform or CDK for a rig. DEFERRED.

Nothing needs a rig. Reopens when a run needs more than one concurrent worker or exceeds spec 121's
$80 cap.

### Decision 4 — Publishing the corpus to the Hub. DEFERRED.

Reopens after the first published number. Publishing a corpus that carries its train split makes
leakage permanent and public, so FR-011's split and spec 121's FR-021 leakage guard are
prerequisites, not companions.

### Decision 5 — The harness. `prime-agent` is the target; `opencode` is the incumbent. NEW.

`opencode` drove the pilot and stays until a replacement is proven. `prime-agent`
(`PrimeIntellect-ai/prime-agent`) is under evaluation, and three things about it are verified from
its own docs rather than assumed:

| Fact                                                                                                                             | Consequence                                                        |
| -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| stdio MCP servers declared in `~/.prime/agent/settings.json` under `mcpServers`, or via `prime-agent mcp add local ... -- <cmd>` | the arms stay configuration, so FR-023 of spec 121 survives        |
| skills are importable Python packages                                                                                            | the `tools+skills` arm may not port; probe before adopting         |
| JSON and RPC headless modes documented; MCP inside them is not                                                                   | a headless run with a pinned MCP server is the go/no-go for FR-008 |

The interface (FR-006) is what makes this a decision rather than a rewrite, which is why it is P1
here and why it was the hole in spec 121.

## Out of Scope

- Any change to the MCP server, its tools, or either Rust crate.
- GPU provisioning, trainer configuration, RL runs, behaviour logprobs.
- `repo2rlenv push` to the Hugging Face Hub (Decision 4).
- EKS, Batch fan-out, and any multi-node topology (Decision 3).
- Growing the corpus. That is spec 121's T031.

## Dependencies

- Spec 121's `graded_task.py` for the check contract and its validation, and `arms.py` for the arm
  definitions the exporter emits as `task.toml` variants. Both landed in its Phase 3.
- Live `iris-dev-iris` for every task that grades against IRIS.
- `harbor` CLI, for running an exported task. Development dependency, not a runtime one.

## Success Criteria _(mandatory)_

- **SC-001**: One source task exports to a Harbor directory that a second agent runs to a reward,
  with no edit to the task.
- **SC-002**: A format drift upstream fails a golden-file test rather than grading nothing.
- **SC-003**: Every agent driver in the repo satisfies the declared interface, with a fake driver
  covering the `scored=False` and `logprobs=None` paths.
- **SC-004**: The bare arm's absence assertion raises for each driver's own configuration path, and
  a driver naming no paths fails the arm.
- **SC-005**: `split.toml` covers the corpus exactly, with the two sides disjoint.
- **SC-006**: Provenance on every run names driver kind and harness version.
- **SC-007**: A `prime-agent` headless run with the iad MCP server registered either produces a
  tool-call log and a reward, or produces a recorded blocker naming what is missing.
