# 128 tasks

Tests before code, per module.

## Phase 1: data

- [x] T001 Mine candidate prompts into `tests/e2e/tasks/routing/mined.jsonl` with sources (benchmark, targeted, eval.yaml, issue titles, transcripts)
- [x] T002 Two blind label passes; merge into `corpus.jsonl`; drops recorded in `dropped.jsonl`; README with agreement rate
- [x] T003 Test: corpus ids unique, gold names exist, slices known; `routing-split.toml` matches hash rule, holdout ≥ 70
- [x] T004 Write `routing-split.toml` and its freeze test

## Phase 2: pure logic

- [x] T010 validator tests, then `validator.py`
- [x] T011 holdout tests, then `holdout.py`
- [x] T012 ledger tests, then `ledger.py`
- [x] T013 bootstrap tests, then `bootstrap.py`
- [x] T014 gate tests, then `gate.py`

## Phase 3: loop

- [x] T020 menu tests, then `menu.py`
- [x] T021 proxy tests (fake client), then `proxy.py`
- [x] T022 adapter tests (gepa pinned; fake scorer and reflection), then `adapter.py`, `surfaces.py`
- [x] T023 report + apply tests, then `report.py`, `apply.py`
- [x] T024 CLI tests, then `__main__.py`

## Phase 4: CI

- [x] T030 `test_shipped_descriptions.py`: validator over every shipped description
- [x] T031 Nightly drift step in `skill-regression.yml`; `requirements.txt` pin

## Phase 5: first runs

- [x] T040 Billable smoke `run --budget 1`
- [x] T041 `measure` on shipped descriptions; record in `specs/128-skill-routing-loop/results.md`
- [x] T042 Default-budget run; verdict in `results.md`

## Phase 6: gate

- [X] T050 Full offline pytest, cargo unit target, markdown lint, `/no-ai-slop` on results
