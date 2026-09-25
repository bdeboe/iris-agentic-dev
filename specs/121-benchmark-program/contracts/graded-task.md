# Contract: GradedTask

What a task must prove about itself before it enters the corpus. Enforced by corpus validation
(T028); the on-disk layout is Harbor's, per research.md § task format.

Four skills currently read 0.00 against 0.00. That is not nine skills measured and four found
useless — it is four task sets that never graded anything, and nothing in the harness noticed. Every
clause below is one of the checks that would have caught it.

## The three facts

A task records all three, and validation fails on any one missing or false. Recorded, not assumed:
the artifact says the check ran and what it said.

**V1 — The precondition fails.** The check, run against the untouched fixture with no agent
involved, returns 0.0 (FR-004). A check that passes before the agent runs measures the fixture. This
catches the "assert the class exists" task where the class shipped in the fixture.

**V2 — The reference solution passes.** `solution/solve.sh`, applied to the untouched fixture, makes
the check return 1.0 (FR-022). Harbor treats `solution/solve.sh` as optional; here it is required,
because it is the only thing that distinguishes a task that is hard from a task that is broken. Four
task sets at 0.00 across both arms could each be either, and without V2 there is no way to tell —
which is the position Phase 2 has to triage its way out of.

**V3 — The check is deterministic.** Two runs over identical output produce identical rewards
(FR-003). Whitespace, timestamps, hash-ordered output and IRIS `$ZTIMESTAMP` are the usual leaks.

V1 and V2 together bracket the task: it must be unsatisfied before and satisfiable after. A task
failing V1 grades the fixture; failing V2 grades nothing.

## Grading

`tests/test.sh` writes `/logs/verifier/reward.txt` — one scalar, 1.0 or 0.0 for a binary check — or
`/logs/verifier/reward.json` for a labelled multi-part check. The reward is a file, not an exit
status.

**No model judges anything.** `Check.mode` is `assertion` or `pattern`, and has no judged member
(FR-003). Both modes already exist in `scoring.py` and predate this spec. A judged reward is not
rejected by a runtime check — there is nowhere in the type to put one.

For Tier 2 tasks the assertion runs against live IRIS: the check queries the state the task was
supposed to produce. Per research.md § IRIS reachability the pilot reaches a shared IRIS over
`allowed_hosts`, and each task gets its own namespace (Constitution VI), with the harness refusing a
namespace it did not create.

## Split

`split` is read from `<corpus-root>/split.toml`, never inferred from a filename, a directory or a
hash. FR-021's publish path raises on a `train` task ID. The guard test asserts the two ID sets are
disjoint and their union is the corpus (T032).

The reason: GEPA optimises tool descriptions against this corpus, and `benchmark/021`'s `merged`
condition is a tuned system prompt. A figure measured on tasks the descriptions were fitted to
overstates the tool, and that is the first thing a hostile reader at conference scale will check.

## Test obligations

`test_graded_task.py`, before the validator exists (Constitution IV):

| Obligation                                                        | Fact   |
| ----------------------------------------------------------------- | ------ |
| A check passing against the untouched fixture fails validation    | V1     |
| A task with no `solution/solve.sh` fails validation               | V2     |
| A reference solution that does not pass its own check fails       | V2     |
| A check giving two different rewards on the same output fails     | V3     |
| A task with unrecorded validation fails — silence is not a pass   | V1–3   |
| A `judge`-mode check is unconstructible                           | FR-003 |
| A task whose `split` is absent from `split.toml` fails validation | FR-021 |

## Deleting is allowed

Phase 2 may delete a task set rather than fix it (T023). A deleted task set costs item count, which
raises the MDE, which is honest. A retained null task set costs nothing visible and reports a number,
which is how this started.
