# Data Model: Prove the tools and skills help

Five entities from spec.md's Key Entities. Field lists are the contract the unit tests assert
against, so a field here without a test is a bug in the tests.

The through-line: **no entity can hold a lift without holding what it took to measure it.** That is
the `unpowered-result` bug class expressed as a type, and it is why `Comparison` has no bare `lift`
field.

## Arm

One of the three configurations under test. An arm is data, not a code path (FR-023) — three
`task.toml` variants generated from one source task, per research.md § arms.

| Field            | Type                | Notes                                                                  |
| ---------------- | ------------------- | ---------------------------------------------------------------------- |
| `name`           | `str`               | `bare`, `tools`, `tools+skills`. Ordered; adjacency matters.           |
| `mcp_servers`    | `list[McpServer]`   | Empty for `bare`. One iad entry, `transport="stdio"`, for both others. |
| `skills_enabled` | `bool`              | True for `tools+skills` alone.                                         |
| `toolset`        | `str \| None`       | `Merged` when tools are registered, `None` for `bare`.                 |
| `absence_facts`  | `list[AbsenceFact]` | What `assert_absent()` checked. Non-empty for `bare`.                  |

`assert_absent()` raises rather than returning false (FR-002). A contaminated arm fails the run; it
does not report a number. The four facts it checks, from plan.md's Complexity Tracking: no MCP
registration in any config on the resolution path, no reachable skill file, no `CLAUDE.md` naming an
iad tool, no cached transcript.

**Ordering is a field, not a convention.** `bare < tools < tools+skills`. Comparisons are between
adjacent arms only — `bare`→`tools` is the tool surface's value, `tools`→`tools+skills` is a skill
document's value. A `bare`→`tools+skills` figure attributes both to whichever one is being sold, and
that is the number this whole spec exists to avoid publishing.

## GradedTask

One task, machine-checkable, on the corpus. Harbor's on-disk layout per research.md § task format.

| Field                | Type                   | Notes                                                             |
| -------------------- | ---------------------- | ----------------------------------------------------------------- |
| `task_id`            | `str`                  | Stable. The pairing key, and the split key.                       |
| `instruction`        | `str`                  | `instruction.md`. What the agent is asked.                        |
| `check`              | `Check`                | `tests/test.sh`. Deterministic (FR-003).                          |
| `reference_solution` | `str \| None`          | `solution/solve.sh`. **Required here** though optional to Harbor. |
| `split`              | `"train" \| "holdout"` | Read from `split.toml`, never inferred.                           |
| `tier`               | `int`                  | Spec 120's tiering. Tier 2 needs IRIS.                            |
| `validation`         | `TaskValidation`       | The three facts below, recorded rather than assumed.              |

`TaskValidation` is the anti-vacuity gate, and all three must be recorded before a task enters the
corpus:

- `precondition_fails: bool` — the check fails against the untouched fixture (FR-004). A check that
  passes before the agent runs grades nothing.
- `reference_passes: bool` — the reference solution passes its own check (FR-022). Distinguishes a
  hard task from a broken one.
- `deterministic: bool` — two runs over the same output give the same reward (FR-003).

A `GradedTask` with any of the three false or unrecorded fails corpus validation. Four skills reading
0.00 against 0.00 are what happens without this.

## Check

The verifier, and the reward contract from research.md § task format.

| Field         | Type  | Notes                                         |
| ------------- | ----- | --------------------------------------------- |
| `script`      | `str` | `tests/test.sh`.                              |
| `reward_path` | `str` | `/logs/verifier/reward.txt` or `reward.json`. |
| `mode`        | `str` | `assertion` or `pattern`. Never `judge`.      |

**`mode` has no model-judged member, by construction.** `scoring.py` already ships `verdict_from_assertions`
and `verdict_from_patterns`; both are deterministic and both predate this spec. FR-003 is enforced by
the type having nowhere to put a judgement, not by a runtime check that a judgement is absent.

## TaskPair

One task, two arms, the unit McNemar counts over. Pairing is what buys the floor of 37 instead of 97
per arm, so it is an entity rather than a loop variable.

| Field      | Type   | Notes                                      |
| ---------- | ------ | ------------------------------------------ |
| `task_id`  | `str`  | Present in both arms, or there is no pair. |
| `arm_a`    | `str`  | The lower arm.                             |
| `arm_b`    | `str`  | The upper arm.                             |
| `passed_a` | `bool` | From the reward, thresholded once.         |
| `passed_b` | `bool` | Same.                                      |

Concordance is derived, never stored: `(passed_a, passed_b)` falls in one of four cells. `b` is
`(False, True)` — the upper arm wins — and `c` is `(True, False)`. Those two counts are the whole
pilot decision (FR-024).

**A task missing from either arm is a named hole, not a dropped row.** `Comparison` carries the hole
list. A silently-dropped task is how an arm crash becomes a lift.

## Comparison

The central entity, and the one the `unpowered-result` detector guards. Two adjacent arms over a set
of pairs.

| Field               | Type                            | Notes                                                 |
| ------------------- | ------------------------------- | ----------------------------------------------------- |
| `arm_a`, `arm_b`    | `str`                           | Adjacent, per Arm ordering.                           |
| `pairs`             | `list[TaskPair]`                | Complete pairs only.                                  |
| `holes`             | `list[str]`                     | Task IDs dropped, and from which arm.                 |
| `n_pairs`           | `int`                           | `len(pairs)`. Never optional.                         |
| `b`, `c`            | `int`                           | Discordant counts.                                    |
| `discordance`       | `float`                         | `(b + c) / n_pairs`. Measured, not assumed.           |
| `lift`              | `float \| None`                 | `None` when either arm scored nothing.                |
| `interval`          | `tuple[float, float] \| None`   | McNemar. Two-sided 95%.                               |
| `p_value`           | `float \| None`                 | One-sided exact.                                      |
| `mde`               | `float`                         | Recomputed from measured discordance. Never optional. |
| `floor`             | `int`                           | 37 at discordance 0.20, recomputed per run (FR-008).  |
| `threshold_applied` | `float`                         | `max(0.20, mde)` (FR-009).                            |
| `verdict`           | `Verdict`                       | Below.                                                |
| `purpose`           | `"result" \| "design_decision"` | FR-024's carve-out.                                   |

`Verdict` is a closed set of six, and `passed` is not reachable from an underpowered comparison. The
order is the precedence order `Comparison._verdict_for` applies, which is part of the contract:

| Verdict             | When                                                                    |
| ------------------- | ----------------------------------------------------------------------- |
| `not_comparable`    | An arm scored nothing, or provenance differs.                           |
| `underpowered`      | `n_pairs < floor`. Reported instead of a pass (FR-008).                 |
| `indistinguishable` | Interval contains zero (FR-010).                                        |
| `regressed`         | Lift negative.                                                          |
| `passed`            | Powered, interval excludes zero, lift ≥ `threshold_applied`.            |
| `below_threshold`   | Powered, interval excludes zero, lift positive but under the threshold. |

`below_threshold` is the sixth, and it is not decoration: a real, measurable improvement that does not
reach the gate is a different fact from one the instrument cannot see. Folding it into
`indistinguishable` would report a difference the run did resolve as a difference it could not, and
folding it into `passed` is the mistake the 0.05 threshold made.

Three invariants the tests assert directly:

1. **Constructing a `Comparison` without `n_pairs` and `mde` raises.** This is governance detector 1
   as a type, not as a scanner. The scanner covers call sites; this covers construction.
2. **`purpose="design_decision"` is the only way past the floor and interval rules.** It cannot be
   published (FR-021), and it must carry `b`, `c` and `p_value` (FR-024). The pilot is the only
   current user.
3. **`threshold_applied` is `max(0.20, mde)`.** A threshold below the instrument's resolution is not
   a threshold. The existing 0.05 is that mistake, and it is deleted rather than lowered.

## ToolAttribution

Story 5's join. One row per advertised tool, from the driver's tool-call log per research.md § driver
interface.

| Field              | Type            | Notes                                                                     |
| ------------------ | --------------- | ------------------------------------------------------------------------- |
| `tool_name`        | `str`           | From `tool_catalogue()`, so unreached tools appear (FR-012).              |
| `applicable_tasks` | `int`           | Tasks where the tool could plausibly have helped.                         |
| `calls`            | `int`           | Zero is a reportable value, not a missing row.                            |
| `tasks_reached`    | `int`           | Distinct tasks with ≥1 call.                                              |
| `reach_rate`       | `float \| None` | Over `applicable_tasks`, not over all tasks. `None` when zero applicable. |
| `pass_with`        | `int`           | Passed and called it.                                                     |
| `pass_without`     | `int`           | Passed without calling it.                                                |
| `unreached_reason` | `str \| None`   | `no_applicable_task` or `agent_chose_otherwise`.                          |

**The two zero-reach reasons are different facts and must not share a row shape.**
`no_applicable_task` means the corpus does not test the tool — a corpus gap. `agent_chose_otherwise`
means a task needed it and the agent did not reach for it — a description or discoverability problem,
which is exactly what GEPA optimises. Collapsing them into "0 calls" loses the only signal that says
which of the two to fix.

Tools in `Baseline` but not `Merged` are reported as **out of scope** rather than unreached, per
research.md § arms: a Docker-dependent tool cannot reach IRIS from inside a task container, so
counting it as unreached would be measuring the harness, not the tool.
