# Implementation Plan: Prove the tools and skills help

**Branch**: `121-benchmark-program` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)
**Depends on**: [`specs/120-repo2rlenv-rl-env/`](../120-repo2rlenv-rl-env/plan.md) Slice 1

## Summary

Build the measurement that says what iad is worth, and make the nightly readable again. Six
stories, ordered so the cheap ones land first and the expensive one has a stop condition in front
of it.

The order matters more than usual here, because one phase can end the project. Story 1's headline
number is the reason to do any of this, and it is also the one thing that might come back flat. So
a pilot on eight tasks runs before the 50-task corpus is written, and it is a declared go/no-go: if
an agent with the tool surface does not beat an agent without it on eight tasks that a competent
IRIS developer can do, then the corpus is not the problem and building 42 more tasks will not fix
it. That finding would cost about $2 to reach and would change what I tell Learning Services.

Everything before the pilot is work I want regardless of how the pilot turns out: honest
statistics, and a corpus that discriminates.

## Technical Context

**Language/Version**: Python 3.11, matching `tests/e2e/` and `benchmark/021/runner`. No Rust
change in either crate.
**Primary Dependencies**: stdlib `statistics` and `math` for the intervals — no scipy. The
`harbor` CLI for running exported tasks, per spec 120. No new runtime dependency in the shipped
binary.
**Storage**: task directories on disk; results as JSON under `tests/e2e/results/`.
**Testing**: `python -m pytest tests/e2e/`, plus `cargo test --features testing` unaffected.
**Target Platform**: Linux and macOS for generation and grading. Live IRIS for every graded check.
**Constraints**: the bare arm must be provably iad-free, which is an environment problem rather
than a code problem and is where the subtle bugs will be. Published figures come from the holdout
split only.
**Scale/Scope**: ~6 new Python modules, the 9 existing skill task sets triaged, a corpus growing
from 8 pilot tasks to 50.

## Constitution Check

_GATE: must pass before Phase 0. Re-check after the pilot._

| Principle                             | Status | Notes                                                                                                                                                                                                                                                                              |
| ------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| I. Zero-Install Binary                | N/A    | No change to the shipped binary. The harness installs the binary it measures, which is test infrastructure.                                                                                                                                                                        |
| II. ObjectScript Sanity               | PASS   | Task fixtures and reference solutions contain ObjectScript. Each goes through `objectscript-guardrails` and `objectscript-review` before it enters the corpus, same as any other ObjectScript in this repo.                                                                        |
| III. HTTP-First Execution             | N/A    | No new tools.                                                                                                                                                                                                                                                                      |
| IV. Test-First, Fixture-Driven        | PASS   | Every statistics function gets its unit test first, against values computed independently. A wrong confidence interval is invisible without one.                                                                                                                                   |
| V. Output Shape Parity                | PASS   | The result JSON is a consumed contract — the merge step and the report both read it. Fields are added, never renamed.                                                                                                                                                              |
| VI. Environment Guard                 | PASS   | Graded tasks write to IRIS. Each runs in its own namespace and the harness refuses a namespace it did not create. Was a claim with no code behind it until 120 T019/T020 — now `tests/e2e/skill_eval/rollout_namespace.py`, proven concurrent in `test_rollout_namespace_live.py`. |
| VII. Dependency Minimalism            | PASS   | The intervals are stdlib arithmetic. Adding scipy for two closed-form formulas would be the wrong trade.                                                                                                                                                                           |
| VIII. 90% Coverage Gate               | N/A    | `cargo llvm-cov` measures Rust. No Rust changes, so the number cannot move. The new Python modules are covered by the unit target the nightly already runs.                                                                                                                        |
| IX. Tool Lift Requirement             | PASS   | No new MCP tool, so no lift owed. This spec is the instrument the principle has been asking for since it was written, and Story 5 plus FR-019 close the gap between the principle's named path and what exists.                                                                    |
| X. ObjectScript Coverage              | N/A    | The corpus's ObjectScript is fixture material, not shipped product code.                                                                                                                                                                                                           |
| XI. No Vacuous Tests                  | PASS   | Live-agent and live-IRIS tests skip loudly on a missing credential or container. FR-022 is the anti-vacuity rule for the corpus itself: a task whose reference solution cannot pass its own check is not a test.                                                                   |
| XII. Hermetic Test Environment        | PASS   | The bare arm is the whole difficulty. FR-002 makes absence an assertion rather than an assumption, and a contaminated arm fails the run instead of reporting a number.                                                                                                             |
| XIII. Single-Source Failure Detection | PASS   | One place computes an interval, one place decides a comparison is underpowered, one place decides a task is gated. No second copy of any of the three.                                                                                                                             |

Governance, prompt 9 — a detector for the class. Two bug classes are new here and both get one:

- **Unpowered number published as a result.** A report that prints a lift without the item count
  and minimum detectable effect beside it. Detector: unit test asserting the reporter refuses to
  format a lift without both, plus a scanner check that no result-formatting call site omits them.
- **Split leakage.** A published figure computed over a train-split task. Detector: guard test
  asserting the train and holdout ID sets are disjoint and their union is the corpus, and a
  publish path that raises on a train-split task ID.

Both classes have shipped instances, so both owe a Bug Class Registry row as well as a detector —
`lift.py:76` subtracting two point estimates with no item count beside them, and GEPA tuning tool
descriptions against the same corpus the numbers are read from. The registry lives in the
constitution, which is edit-protected, so the amendment is a Polish task written through Bash, the
way 118 did it.

_No FAIL gates._

## Project Structure

### Documentation (this feature)

```
specs/121-benchmark-program/
├── spec.md            # written
├── plan.md            # this file
├── research.md        # Phase 0 output: reconciliation with 120, image decision
├── data-model.md      # Arm, GradedTask, TaskPair, Comparison, ToolAttribution
├── contracts/
│   ├── comparison.md  # the statistics contract: what a Comparison guarantees
│   ├── graded-task.md # precondition, check, reference solution
│   └── arm.md         # driver configuration and absence assertions
├── tasks.md
└── lift-results.md    # Story 5's standing per-tool table, Constitution IX
```

### Source Code (repository root)

```
tests/e2e/skill_eval/
├── stats.py            # NEW: Wilson, McNemar, MDE. Pure, no I/O. Not `statistics.py`,
│                       #      which would shadow the stdlib module it imports
├── comparison.py       # NEW: Comparison, arm pairing, underpowered verdict
├── arms.py             # NEW: arm definitions and absence assertions
├── attribution.py      # NEW: tool-call log joined to graded outcome
├── triage.py           # NEW: flat and saturated task-set verdicts
├── lift.py             # MODIFIED: delegate to comparison.py, drop bare subtraction
├── reporter.py         # MODIFIED: item count and MDE beside every lift
└── scoring.py          # MODIFIED: machine-check verdicts alongside judged ones

benchmark/harbor/
└── export.py           # from spec 120 Slice 1; consumed here, not built here

scripts/gates/
└── antipatterns.py     # MODIFIED: two new checks per the governance section
```

## Phasing

**Phase 0 — reconcile with 120.** Settle the container image, confirm the Harbor task layout and
the driver interface signature, and agree the train/holdout split mechanism. Output is
`research.md`. No code. This exists because two specs currently name different IRIS images and a
pass rate against an unnamed build means nothing.

**Phase 1 — honest statistics (Story 3).** `stats.py` and `comparison.py`, unit-tested
against independently computed values. Wire `lift.py` and `reporter.py` to them, and take the
nightly down to what it can actually support: a canary set and a breakage verdict, with no lift
number in its output at all (FR-016). This phase alone stops the nightly failing on quantization,
and it needs no IRIS, no corpus work and no spend. It ships first because it is the cheapest useful
thing in the plan.

**Phase 2 — corpus triage (Story 4).** Read the artifacts already on disk, assign each flat and
saturated task set its recorded verdict, then fix or delete. This is where the item budget for
everything after it comes from.

**Phase 3 — the pilot, and the go/no-go.** Eight machine-checkable tasks, three arms, paired.
Enough to see a large effect and not enough to see a small one, which is the correct instrument
for a question whose honest answers are "obviously yes" and "no".

Eight pairs cannot clear FR-008's floor of 37, and an eight-pair interval will contain zero
whatever happens, so the verdict cannot be a lift with an interval — FR-010 would forbid calling
it positive. FR-024 carves the pilot out as a design decision rather than a result, and it is
decided on raw discordant-pair counts instead. Let `b` be the pairs where the tools arm passes and
bare fails, and `c` the reverse:

| Counts                                 | Verdict                                          | One-sided exact p |
| -------------------------------------- | ------------------------------------------------ | ----------------: |
| `c ≤ 1` and `b ≥ 5` and exact p ≤ 0.07 | **go** — build the corpus                        |          ≤ 0.0625 |
| `b ≤ c`                                | **stop** — the tools did not help these tasks    |                 — |
| anything else                          | **inconclusive** — run 8 more tasks, decide once |                 — |

The p-value is a binding condition, not a description of the counts. An earlier draft of this table
read `b ≥ 5 and c ≤ 1 → p ≤ 0.06`, and that is false at the corner: `(5, 1)` gives 0.109, nearly
double. The three conditions together admit exactly six outcomes — `(5,0)`, `(6,0)`, `(6,1)`,
`(7,0)`, `(7,1)`, `(8,0)` — and the weakest of them is `(6,1)` at 0.0625. `(5,1)` now falls through
to inconclusive on the p-value, and `(4,0)` falls through on `b` despite reaching p = 0.0625, since
four discordant pairs of eight is thin evidence whatever its tail probability.

`test_stats.py` asserts this rule against the arithmetic rather than restating it in prose, so the
table cannot drift from the numbers again.

The go row does not reach p ≤ 0.05, and it is not meant to. It is the strength of evidence eight
tasks can buy, and it is being used to decide whether to spend $16, not to make a claim. The exact
test depends only on `b` and `c`, never on the number of pairs, so a second round of eight tasks
reuses this table unchanged rather than needing one of its own. The stop row needs no p-value: if
the tool surface does not win more pairs than it loses on eight tasks a competent IRIS developer can
do, the corpus is not the problem.

On stop: write up the finding, take it to Learning Services before they build a path on it, and
reopen the question of what the tools are for. Neither outcome is a failure of this plan. Only
skipping the pilot would be.

**Phase 4 — the corpus and the number (Stories 1 and 2).** Grow to 50 machine-checkable tasks,
every one with a precondition that fails and a reference solution that passes. Run the full arm
ladder from the holdout split, then the per-skill ladder the Cost table budgets 216 sessions for —
tools against tools+skills, per skill, which is the only thing that says whether a given skill
document earns its place. This is the phase the $50–80 cap is for.

### The per-skill stop rule, written before the sessions run

The tools ladder publishes a lift with an interval. The skills ladder cannot: twelve purpose-built
tasks per skill will never reach FR-008's floor of 37, and an interval over twelve items contains
zero whatever happens. So the skills question is decided on discordant counts, like the pilot's
go/no-go, and the rule is fixed here and in `ladder.skill_verdict` before any skill session runs.

With `b` = pairs the skill arm passes and the tools arm fails, and `c` the reverse:

| Counts              | Verdict                                                          |
| ------------------- | ---------------------------------------------------------------- |
| `c > b`             | **harmful** — the skill cost more tasks than it won              |
| `b == c`            | **no effect**                                                    |
| `b ≥ 4` and `c ≤ 1` | **helps**                                                        |
| anything else       | **inconclusive** — say so, do not grow the corpus until it turns |

`helps` needs a margin and not just a sign, because 3-2 over twelve items is noise and publishing it
as a help is exactly the mistake `Comparison` exists to prevent.

The reason the rule is written down first: the tempting move after a flat result is to add tasks
until the sign changes. If twelve tasks built specifically to need a documented convention — storage
blocks, `$LIST` traps, `%Status` propagation, `$$$OK`/`$$$ISERR`, the SQL restrictions — give
`b ≤ c`, that is a real finding about the skill documents and it gets written up as one. Each rung
installs exactly one skill (`arms.skill_arm`), because PILOT-03 passed in 3 tool calls with tools
alone and failed after 41 calls and 206 seconds with all 34 skills installed: a rung carrying the
whole pack measures the pack's bulk and the skill's content together and reports the sum.

**Phase 5 — per-tool attribution (Story 5).** Join the tool-call logs from Phase 4's runs to the
graded outcomes. No new sessions. Write `lift-results.md` as the standing table Constitution IX
has been asking for.

**Phase 6 — one harness, publicly runnable (Story 6).** Converge or delete the other benchmark
systems, document the quickstart, and close the `BENCHMARKING.md` promise spec 059 recorded as
broken.

## Complexity Tracking

Two things here are harder than they look, and both are environment rather than arithmetic.

**The bare arm.** Proving an agent had no access to iad is harder than giving it access. A stale
MCP registration in a user-level config, a skill file on a search path, a `CLAUDE.md` mentioning a
tool by name, or a cached transcript all contaminate it, and every one of those failure modes
produces a plausible-looking number rather than an error. This is the same class as the
`clean_command` problem the Rust tests already have, and it gets the same treatment: assert the
absence, do not arrange it and hope.

**Preconditions that actually fail.** A check can pass because the fixture already satisfied it.
FR-004 and FR-022 are the two halves of the guard — the precondition must fail before the agent
runs, and the reference solution must pass after. A task missing either one is a task that grades
noise, and four of the nine current skills are the evidence that this happens without a gate.

The statistics are the easy part. Wilson and McNemar are closed-form and testable against values
computed by hand.
