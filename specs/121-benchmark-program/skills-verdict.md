# What the skills are worth, measured, and it is not good

Twelve purpose-built tasks, 24 sessions, one skill installed per session. The artifact is
`tests/e2e/results/ladder-121-skills-pooled.json`. The result is a negative, and the rule that calls it
one was written down before the first session ran.

## The rule, declared first

Twelve items cannot reach the publication floor of 37, and an interval over twelve contains zero
whatever happens, so this rung is not decided by an interval. It is decided by the discordant counts:
`helps` needs b >= 4 and c <= 1, and b <= c is a real negative about the documents. That is in
`plan.md` and in `ladder.skill_verdict`, fixed before any skill session ran, and it is also in the
report's own `skill_verdict_rule`.

## The number

```
tools -> tools+its-own-skill  lift -0.250 [-0.587, +0.087]  n=12 pairs
  floor=80  discordance=0.42 (b=1, c=4)  mde=0.472  underpowered  p=0.9688 one-sided
```

One task the skill won, four it lost. `skill_verdict: harmful`. The lift is not publishable and is not
published — at twelve pairs the smallest effect this design could resolve is 0.472, so the interval is
useless in both directions. The counts are what carry the finding.

Arm rates, for the record: tools 10/12 = 0.833 [0.552, 0.953]. The one-skill arms, 7/12 pooled. Every
session in both arms was scored and none hit the 300-second clock, so there is no hole and no censoring
to argue about.

## Per skill

| Skill                        | Pairs | b (skill won) | c (skill lost) | Verdict   | Could reach `helps`? |
| ---------------------------- | ----: | ------------: | -------------: | --------- | -------------------- |
| `objectscript-guardrails`    |     5 |             0 |              1 | harmful   | yes                  |
| `objectscript-list-patterns` |     3 |             1 |              1 | no effect | no                   |
| `objectscript-sql-patterns`  |     3 |             0 |              1 | harmful   | no                   |
| `iris-sql`                   |     1 |             0 |              1 | harmful   | no                   |

The corpus spread twelve tasks over four skills as 5/3/3/1, so only `objectscript-guardrails` had the
item count to show `helps` at all. It is also the one that had five chances and took none of them.
Nothing here is evidence about `iris-sql` as a document — one pair is one pair.

## The five pairs that moved

| Task     | Skill                        | tools           | tools + its skill | Direction  |
| -------- | ---------------------------- | --------------- | ----------------- | ---------- |
| SKILL-04 | `objectscript-guardrails`    | PASS 7c 29.5 s  | FAIL 15c 78.6 s   | skill lost |
| SKILL-07 | `objectscript-list-patterns` | PASS 15c 37.7 s | FAIL 54c 145.5 s  | skill lost |
| SKILL-11 | `iris-sql`                   | PASS 16c 56.4 s | FAIL 2c 11.7 s    | skill lost |
| SKILL-12 | `objectscript-sql-patterns`  | PASS 41c 165.6s | FAIL 30c 102.2 s  | skill lost |
| SKILL-10 | `objectscript-list-patterns` | FAIL 20c 90.3 s | PASS 20c 85.0 s   | skill won  |

Two shapes in the four losses. SKILL-04 and SKILL-07 did much more work and still came back wrong —
SKILL-07 spent 54 calls and nearly four times the clock against a session that solved it in 15. SKILL-11
did the opposite and quit: two calls, 11.7 seconds, no answer. SKILL-09, which both arms failed, is the
same shape in its skill session — zero tool calls in 8.8 seconds, a session that read something and
declined.

This is the pilot's PILOT-03 pattern (3 calls with tools, 41 calls and 206 s with the whole 34-document
pack) reproducing with **one** document installed. So it is not a "too many skills" effect, which is
what I expected going in and what the pooled design was built to rule out.

## The part that argues the other way

Among the six pairs both arms solved, the skill arm was faster in all six: median 28.3 s against 37.5 s,
median 7.5 tool calls against 9.5. SKILL-08 is the clearest — 54.6 s and 17 calls with the document
against 136.3 s and 35 calls without it.

So the document is not inert and it is not uniformly bad. It changes what the session does, and on a task
squarely inside what it covers, it gets there with less work. The failures are cases where it changed
what the session did and the change was wrong. A verdict of "harmful" is the honest summary of the
pass/fail counts and it is not the whole picture of the behaviour.

## What I am not doing about it

Not growing the corpus until the sign turns. Twelve was the declared size, the rule was fixed in advance,
and it came out negative. The next honest move is to read the four failing transcripts and find out
whether the document displaced tool use or sent the session after the wrong convention, then fix the
document or the task — not to add items until b > c.

## What this does not establish

- **Twelve items, MDE 0.472.** Only an effect larger than 47 points was visible. A real 10-point
  improvement in either direction would look exactly like this.
- **Three of four skills could not reach `helps`** on item count alone, whatever they did.
- **One model, one run, one document per session.** `openai/gpt-4.1`, no repeats.
- **The tasks and the skills have the same author.** Each task was written so the discriminating
  convention cannot be inferred from the task text, which is the right design and is still my judgement
  of what is inferable.
- **Nothing about the skills as documentation for a human**, or as context for a model that asks for
  them by name rather than having them installed up front.

## Provenance

| Field           | Value                                                                     |
| --------------- | ------------------------------------------------------------------------- |
| Tool surface    | `1.4.2+fa0b694f8725`                                                      |
| Model           | `openai/gpt-4.1`                                                          |
| Driver          | opencode 1.14.17                                                          |
| Harness commit  | `8d0314b`                                                                 |
| IRIS image      | `intersystemsdc/iris-community:2026.2`                                    |
| Image digest    | `sha256:5ffbd9af5a3ab685e65496d45c32ed6db455882f9f1d32864d4e4032f395bf42` |
| Corpus commit   | `8d0314b`, clean                                                          |
| Session timeout | 300 s                                                                     |
| Item counts     | 12 tasks × 2 arms × 1 run = 24 sessions                                   |

The report this section describes was rebuilt from the run's own `.runs.jsonl`, because the file the run
wrote said `driver: "unrecorded"` — the process had been launched from a tree that predated the driver
fix by six minutes. `harness-gaps.md` has that and the `--pooled` merge bug it exposed.
