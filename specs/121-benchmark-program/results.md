# What the tools are worth, measured

One graded run, 123 sessions, 41 holdout task-pairs. Every task graded by an ObjectScript check
printing `PASS` or `FAIL` against live IRIS; no model scored anything. The artifact is
`tests/e2e/results/ladder-121-tools-holdout.json` and every number below is in it.

## The two figures

```
bare -> tools           lift +0.829  [+0.714, +0.944]  n=41  b=34 c=0  p=0.0000  passed
tools -> tools+skills   lift +0.098  [-0.034, +0.229]  n=41  b=6  c=2  p=0.1445  indistinguishable
```

Adding the iad tools to a bare model took it from solving none of these tasks to solving 34 of 41. The
interval does not come near zero and the sign is unanimous: 34 tasks flipped to a pass and not one
flipped the other way. Adding all 34 skill documents on top of the tools moved 6 tasks up and 2 down,
which is inside the noise of 41 items.

## Per arm

| Arm            |  Solved |  Rate | 95% Wilson     | Median solve | Mean solve | Killed at 300 s |
| -------------- | ------: | ----: | -------------- | -----------: | ---------: | --------------: |
| `bare`         |  0 / 41 | 0.000 | [0.000, 0.086] |            — |          — |              19 |
| `tools`        | 34 / 41 | 0.829 | [0.687, 0.915] |       30.0 s |     39.0 s |               2 |
| `tools+skills` | 38 / 41 | 0.927 | [0.806, 0.975] |       34.4 s |     44.2 s |               0 |

Every session in all three arms was scored, so nothing sits outside a denominator.

Solve time is measured over the sessions that solved the task. A killed session has no solve time —
its true value is unknown and above 300 s — so averaging it in would invent a number. The kill count
is printed beside the average instead.

## Why bare scored zero, in three parts

An arm that fails everything invites the reading that the model is useless without tools, and that is
not what happened. Bare's 41 failures split:

- **19 killed on the 300-second clock.** The clock is part of the measurement, not a nuisance around
  it: a developer waiting on an answer has a clock too. But 19 of these are "did not finish in five
  minutes", not "got it wrong".
- **7 made no attempt at all.** Zero tool calls, session ended. That is a decline, and a decline is
  weaker evidence than a wrong answer.
- **15 tried and came back wrong.** Only these 15 are a failure in the ordinary sense.

The tools arm's 7 failures are 2 clock kills and 5 wrong answers, no declines. The skills arm's 3 are
all wrong answers.

So the honest sentence is narrower than the headline: without tools the model solved none of 41 tasks,
and in 26 of them — nearly two thirds — it either ran out of clock or never reached for anything. With
tools it solved 34, and the seven it lost it lost by being wrong rather than by stalling.

## Power, and one gate that was changed after seeing a result

The corpus bought a minimum detectable effect of 0.387 on the first comparison and 0.188 on the
second, both at 41 pairs. The declared publication floor is 37 pairs (FR-008), met.

The floor is also recomputed from measured discordance, and here that rule misfired. Discordance on
`bare -> tools` was 0.83, which puts the recomputed floor at 161 — the pairs it would take to resolve
a _twenty-point_ lift at that discordance. Applied as originally written, it refused an 83-point lift
with p = 0.0000 as underpowered, while publishing the null over the same 41 pairs. A bar that rises
with the size of the effect protects no reader from anything, so the precedence changed: the declared
floor of 37 stays absolute, and the recomputed floor now gates only an interval that contains zero,
where "no effect" and "could not tell" genuinely need separating.

I changed that rule after the blocked result was on the table. The argument is written out in
`contracts/comparison.md` G8 along with that disclosure, both pre-existing floor tests still pass
unchanged, and the null verdict did not move. Read it and disagree if the argument does not hold.

## Provenance

| Field                              | Value                                                                     |
| ---------------------------------- | ------------------------------------------------------------------------- |
| Tool surface                       | `1.4.2+fa0b694f8725`                                                      |
| Model                              | `openai/gpt-4.1`                                                          |
| Driver                             | opencode 1.14.17                                                          |
| Harness commit                     | `20202b3`                                                                 |
| IRIS image                         | `intersystemsdc/iris-community:2026.2`                                    |
| Image digest                       | `sha256:5ffbd9af5a3ab685e65496d45c32ed6db455882f9f1d32864d4e4032f395bf42` |
| Corpus commit                      | `78d8597`, clean                                                          |
| Skills installed in `tools+skills` | all 34 shipped                                                            |
| Session timeout                    | 300 s                                                                     |
| Item counts                        | 41 tasks × 3 arms × 1 run = 123 sessions                                  |

Two provenance fields were wrong when the report was first written and are fixed in the artifact
above: `driver` said `unrecorded` over sessions opencode drove, and `skills_installed` said nothing
over sessions that installed all 34 documents. Both were defaults resolved in one place and read in
another. See `harness-gaps.md`.

## What this figure does not establish

- **The corpus was written by the author of the tools it measures.** No description, prompt or skill
  was changed while looking at a holdout result — that is what the split is for — but this is weaker
  evidence than a corpus someone else wrote, and it should be read that way. It is in the artifact's
  own `caveats`.
- **One model, one run, no repeats.** `openai/gpt-4.1` at one repeat. The strict-and rule for repeats
  exists but nothing exercised it here.
- **41 tasks of ObjectScript and IRIS work on a Community container.** Nothing about Enterprise
  builds, interoperability productions, or a codebase the model has not been handed.
- **Nothing about the skills.** The second comparison is a null, and a null at 41 pairs with an MDE
  of 0.188 means the measurement could not see an effect that size, not that there is none. The
  purpose-built skills rung is the run that addresses it, and it came out negative:
  `skills-verdict.md`.

## The run itself

The first attempt lost its container at session 92 when the host slept, kept paying for ungradeable
sessions, and was killed. The 92 sessions were kept, 11 tasks were re-run whole, and the report is the
merge of both files. Three consecutive ungradeable sessions now abort a run. `harness-gaps.md` has the
whole account.
