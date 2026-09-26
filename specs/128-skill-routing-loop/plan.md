# 128 plan: skill routing optimisation loop

Spec: `spec.md`. Design source: the 127–130 grill (2026-09-26).

## Shape

A Python package `tests/e2e/skill_eval/optimize/` beside the spec 118/121 harness, reusing its scorer client, unscored rules (`scoring.py`) and comparability rule. Data under `tests/e2e/tasks/routing/`. No Rust change; the CI description check is a pytest file.

| Module         | Holds                                                                                        |
| -------------- | -------------------------------------------------------------------------------------------- |
| `corpus.py`    | Load and check `corpus.jsonl`: ids unique, gold names exist, slices known                    |
| `holdout.py`   | Hash rule, `routing-split.toml` load, freeze check, `HoldoutLeak` guard                      |
| `validator.py` | FR-006 / FR-011: length, markers (flag), no new facts                                        |
| `menu.py`      | Read skill names, descriptions, bodies from `skills/`; build the routing menu                |
| `proxy.py`     | One scorer call per item → `ScoredItem`; parse `{"skill": ...}`                              |
| `ledger.py`    | Price table, per-call entries, `BudgetExceeded` at the cap                                   |
| `bootstrap.py` | Paired bootstrap interval, seed 128, 10,000 resamples                                        |
| `gate.py`      | Four gates → SHIP / HOLD with reasons                                                        |
| `adapter.py`   | `GEPAAdapter`: `evaluate`, `make_reflective_dataset`, `propose_new_texts` (validator inside) |
| `surfaces.py`  | Registry; `skill-descriptions` in 128                                                        |
| `report.py`    | `report.md`, `candidate.json`, `ledger.jsonl`                                                |
| `apply.py`     | Write a SHIP candidate's descriptions into front matter                                      |
| `__main__.py`  | `measure`, `run`, `apply`                                                                    |

Tests are `test_*.py` beside each module, collected by the existing CI line (`pytest tests/e2e -m "not billable ..."`). The one real-model smoke is marked `billable`.

## Decisions

- **Scorer model.** `scorer_client.haiku_model()`: Haiku 4.5 on the direct API, Sonnet 4.6 on this account's Bedrock. The model the response reports is recorded; comparability follows spec 118.
- **Reflection model.** Sonnet 5 through the same client factory, as a plain callable so every call hits the ledger.
- **gepa pin.** `gepa==0.1.4` in `tests/e2e/skill_eval/optimize/requirements.txt`, installed by the nightly and by the `optimize` docs. Offline tests that import `adapter.py` skip loudly when gepa is absent unless `IAD_REQUIRE_GEPA=1` (CI sets it).
- **Validator placement.** Inside `propose_new_texts`: a rejected text is logged and dropped, so it is never scored (FR-006).
- **Markers.** Required of candidates, not of the 38 shipped descriptions (FR-011).
- **Labelling.** Two Claude subagent passes, each given prompt + skill name + body with the `description:` line removed. Recorded per item as `labels: [pass1, pass2]`.
- **Live ladder.** The finalist is written into a temporary copy of `skills/`; the existing ladder runs against it on holdout benchmark tasks. Billable; `run --live` only. Without it the verdict is HOLD ("live ladder not run").

## Test layers

1. Unit (offline, no credential): every module, fake scorer and fake proposer injected as callables. This is not IRIS mocking; no IRIS is involved.
2. Corpus/split data tests: run in CI against the committed files.
3. Billable smoke: `run --budget 1` on two skills, marked `billable`.

## Order

1. Corpus mining + blind labels + split (data first; the rest is measured on it).
2. validator, holdout, ledger, bootstrap, gate (pure logic, test-first).
3. menu, proxy, adapter, surfaces, report, apply, CLI.
4. CI description check; nightly drift step.
5. First measurement of the shipped descriptions; first real run with the default budget if credentials allow. Report whatever verdict comes out.

## Deviations found in implementation (2026-09-26)

- **No `corpus.py`.** The corpus checks live in `test_corpus.py`; `runner.load_corpus` reads the files. Added `runner.py`, which holds `measure`, `run` and `drift` so the offline tests drive the real path with a scripted client, and `__main__.py` is argument parsing only.
- **Transcripts excluded from the corpus.** The repo is public and a transcript cannot be scrubbed with confidence. FR-001 lists them as a source; `tests/e2e/tasks/routing/README.md` records the exclusion.
- **Scorer is Haiku 4.5 by id, not `haiku_model()`.** On Bedrock `haiku_model()` still returns Sonnet 4.6, from a comment saying Haiku 4.5 is unavailable on this account. That is no longer true: `us.anthropic.claude-haiku-4-5-20251001-v1:0` answers. The loop asks for Haiku by id; the shared helper is left alone so the spec 118 baselines stay comparable. Reflection is `us.anthropic.claude-sonnet-5` on Bedrock.
- **Bedrock price multiplier.** US cross-region endpoints cost 10% over list; the ledger prices Bedrock calls at 1.1×.
- **Budget reserve.** The loop stops when spend reaches the budget minus a reserve for the final holdout measurement: two arms of about 80 calls each, priced at 1.5× the estimate. Without it a run could spend the whole cap in the loop and have nothing left to judge the finalist.
- **gepa's validation set is carved from train.** gepa needs a trainset and a valset. Both come from the train side (35% of train, by a second hash), so the holdout stays untouched.
- **Unscored items score 0 inside gepa.** gepa needs a number per item. The final holdout figures exclude unscored items as FR-004 says.
- **A rejected proposal is skipped, not replaced.** The adapter drops it from gepa's update, so gepa sees no change for that iteration and nothing is scored.
- **No `temperature`.** anthropic 1.x removed it from `messages.create`, and the first smoke run lost all 80 holdout items to a `TypeError`. Calls now pass only `model`, `max_tokens`, `system` and `messages`. The scorer is therefore not deterministic: the same descriptions measured three times gave false-hint rates of 0.660, 0.617 and 0.596.
- **Live ladder is an input, not a flag.** `run --ladder <file>` takes `{"seed": x, "candidate": y}` from a ladder run done separately. Without it the gate returns HOLD with "no live ladder run".
- **Drift band.** `tests/e2e/tasks/routing/drift-interval.json` holds the 95% Wilson interval from the first `measure --write-interval`. The nightly fails when a re-measurement falls outside it.
- **One retry per rejected draft.** Sonnet's rewrites of the long seed descriptions landed just over 1,024 characters and every proposal of the first default run was rejected. The prompt asks for 900 or fewer, and a rejected draft is sent back once with the validator's reasons (`RETRY_PROMPT`, `PROPOSE_ATTEMPTS = 2`). Both attempts are logged as rejections when they fail.
- **Runs survive being stopped.** The ledger streams to `<run_dir>/ledger.jsonl` on every call; SIGTERM and Ctrl-C end the loop with `stopped: interrupted` and the holdout is still scored; `run --max-minutes` (default 75) is a wall-clock stop. Added after I killed a working run and lost its figures.
