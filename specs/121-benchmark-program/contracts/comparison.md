# Contract: Comparison

What a `Comparison` guarantees to anything that reads one. Implemented by
`tests/e2e/skill_eval/comparison.py`; the arithmetic lives in `stats.py`.

This is the contract the `unpowered-result` bug class violated at `lift.py:76`, where a lift was two
point estimates subtracted with no item count beside them. Every guarantee below exists because that
line shipped.

## Guarantees

**G1 — A lift never travels alone.** A `Comparison` cannot be constructed without `n_pairs` and
`mde`. Not defaulted, not `None`, not filled in later: construction raises. Anything reading a lift
therefore has what it took to measure it, and no caller has to remember to ask.

**G2 — Below the floor, the verdict is `underpowered`, never `passed`.** The floor is 37 task-pairs
at the expected discordance of 0.20 (FR-008). `passed` is unreachable when `n_pairs < floor`, so a
future caller cannot get a pass out of a small run by passing a flag.

**G3 — The floor is recomputed from measured discordance, not read from a constant.** Discordance
0.40 raises the floor to 77. The direction is one-way by design: weak pairing raises the bar, it
never lowers it. A run that measures discordance better than expected does not get to shrink its own
floor below 37.

**G4 — An interval containing zero reports `indistinguishable`.** Not "small positive lift", not
"trending". FR-010. This is the guarantee that would have stopped three consecutive nightly runs
failing on differences inside their own noise.

**G5 — The effective threshold is `max(0.20, mde)`.** 0.20 is Constitution IX's requirement for a
new tool (FR-009). When the corpus bought less resolution than that, the threshold rises to what the
instrument can actually see. The old 0.05 is deleted, not lowered — a threshold below the
instrument's resolution is a coin flip with a decimal point.

**G6 — Dropped tasks are named.** A task present in one arm and absent from the other goes in
`holes` with the arm it was missing from. Never silently excluded. An arm that crashed on ten tasks
must not look like an arm that passed on the rest.

**G7 — `purpose="design_decision"` is the only exemption, and it costs publication.** Such a
comparison skips G2 and G4 (FR-024) and in exchange: it cannot be published, and it must carry `b`,
`c` and a one-sided exact `p_value`. It states the counts it rests on. The pilot is the only current
user, and a pilot that reaches "go" has decided to spend money, not established a lift.

## Test obligations

`test_comparison.py`, written before `comparison.py` (Constitution IV):

| Obligation                                                    | Guarantee |
| ------------------------------------------------------------- | --------- |
| Construction without `n_pairs` raises; without `mde` raises   | G1        |
| 8 pairs → `underpowered`, and `passed` is not reachable       | G2        |
| Discordance 0.40 → `floor == 77`, and the report says 77      | G3        |
| Interval spanning zero → `indistinguishable`                  | G4        |
| `mde=0.28` → `threshold_applied == 0.28`; `mde=0.11` → `0.20` | G5        |
| Task in arm A only → appears in `holes`, named with its arm   | G6        |
| `design_decision` without `b`/`c`/`p_value` raises            | G7        |
| `design_decision` at 8 pairs does not raise on the floor      | G7        |

Every expected value is computed independently and written into the test as a literal. A confidence
interval that agrees with the implementation because both came from the same wrong formula is not a
test.

## Consumers

`lift.py` delegates here and keeps its `None`-when-unmeasured contract (T012). `reporter.py` reads
`n_pairs`, `mde` and `verdict` for every line it prints (T014). `scripts/gates/antipatterns.py`
checks statically that no formatting call site drops them (T015). The nightly reads none of it — it
carries no lift number at all (FR-016).
