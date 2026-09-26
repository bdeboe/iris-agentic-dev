# 128 results: first runs of the skill-routing loop

All figures are on the frozen 80-item holdout unless marked "val" (the loop's own validation slice, carved from train). Scorer Haiku 4.5 on Bedrock, reflection Sonnet 5. Run directories are under `tests/e2e/results/optimize/` (gitignored).

## Verdict: HOLD

Run `20260926T204613Z-skill-descriptions`, default `--budget 20`, spent $16.92. I stopped it with SIGTERM at iteration 165 after 45 minutes, when val gains had shrunk to one or two items of 37 per step. The interrupt path kept the best val candidate and scored both arms on the holdout.

| Arm       | Recall@1 [95% Wilson]       | False-hint rate | Exact-name Recall@1 | Unscored |
| --------- | --------------------------- | --------------- | ------------------- | -------- |
| shipped   | 0.242 [0.128, 0.410] (n=33) | 0.660 (n=47)    | 1.000 (n=7)         | 0        |
| candidate | 0.606 [0.437, 0.753] (n=33) | 0.319 (n=47)    | 0.857 (n=7)         | 0        |

Paired Recall@1 difference: +0.364, 95% bootstrap interval [+0.182, +0.545].

Gates:

- Recall lower bound above 0: passed (+0.182).
- False-hint rate not up: passed, 0.660 to 0.319.
- Exact-name not down: failed. The candidate missed one of 7 exact-name items. I have not looked at which one; finding it means reading holdout outcomes, and any edit made from that would leak the holdout into the next run.
- Live ladder within 0.05: failed, no ladder run. A ladder run is needed before any SHIP.

Seven descriptions changed: `iris-agentic-dev`, `iris-coverage-run`, `iris-objectscript-eval`, `iris-vscode-objectscript`, `objectscript-guardrails`, `objectscript-list-patterns`, `objectscript-tdd`. Nothing was written to `skills/`; `apply` refuses a HOLD run.

## Loop behaviour

- Val rose from 0.297 (shipped) to 0.811 over 165 iterations.
- 60 proposals passed the validator and 241 were rejected before scoring. The main reasons: a fact missing from the skill body (`%List` 14, `$IO` 11, `%OnAfterSave` 9), no `DO NOT USE FOR:` marker (15), an empty reply (11), and length over 1,024 (6).
- My first attempt at this run rejected every proposal (15 of 15). Sonnet's rewrites of the already-long seed descriptions came in at 1,031 to 1,172 characters. The fix: the prompt now asks for 900 characters or fewer, and a rejected draft gets one retry with the validator's reasons. After the fix, 60 proposals got through. That attempt cost about $0.40 and I killed it.

## Earlier runs

- **Smoke run** (`--budget 1`): $0.68, stopped on budget, HOLD. 222 score calls, 2 reflections, 0 proposals accepted. It found the anthropic 1.x `temperature` break: with the SDK pin at `>=0.96`, pip installed 1.8.0, which rejects the argument, so every holdout item went unscored.
- **Shipped-description measure**: $0.25. Recall@1 0.25 [0.13, 0.42] (n=32), exact-name 1.0, false-hint 0.66, 1 unscored. This set the drift band in `tests/e2e/tasks/routing/drift-interval.json`.
- **Killed run**: I stopped an earlier $20 run at iteration 164 (val 0.405 against the seed's 0.270) because I took idle keep-alive sockets for a hang. The ledger and report were written only at the end, so the results were lost, about $5. The ledger now streams to disk on every call, SIGTERM and Ctrl-C stop the loop and still gate, and `--max-minutes` (default 75) caps wall time.

## Caveats

- **Scorer noise.** anthropic 1.x dropped `temperature`, so the scorer is not deterministic. Three scorings of the same shipped descriptions gave false-hint rates of 0.660, 0.617 and 0.596. The paired interval above is wider than that spread, but a gap of 0.05 or less between runs means nothing.
- **Corpus labels.** Most of the no-skill slice is iad GitHub issue titles labelled `none`, and Haiku picks a topically close skill for many of them, which is defensible. Many paraphrase prompts about fixing a method carry one gold skill (often guardrails) where tdd, repair and eval also fit. A fresh, blind relabel would fix both, but I have now seen holdout misses, so I should not do it myself. That is Tom's call.
- **Small slices.** Exact-name has 7 holdout items, so one miss decides that gate.

## Next

1. Run the live ladder on the candidate.
2. Decide on the corpus relabel before any further runs.
3. Re-run with the ladder figure supplied (`--ladder`). The verdict can only move to SHIP if exact-name holds.
