# Tasks: 130 content skills

Tests come first in every phase.

## Phase 1: skill text (US1)

- [x] T001 Unit wording tests, forbidden and required strings (`tests/unit/test_content_skills_130.rs`)
- [x] T002 Live tests, one per research row (`tests/integration/test_content_skills_130_live.rs`)
- [x] T003 Edits: sql-patterns, unit-test, eval, tdd, ensemble-production, guardrails, iris-agentic-dev
- [x] T004 New skill `iris-query-plans` and its registration in seven places
- [x] T005 Unit and live suites pass

## Phase 2: ladder (US2)

- [x] T006 SKILL-13 to SKILL-19 plus the `split.toml` holdout entries
- [x] T007 Shape test and live before/after test pass for the new tasks

## Phase 3: loop surface (US3)

- [x] T008 Offline tests: `editable` filter, the apply step refuses an untouched skill, corpus/split agree, CLI
- [x] T009 `editable` in `RoutingAdapter`, the `content-descriptions` surface, runner wiring
- [x] T010 Content corpus, two blind label passes, frozen split

## Phase 4: runs, docs, cleanup

- [x] T011 Billable: loop run, 128 drift re-measure, ladder (capped at $3)
- [x] T012 `docs/skills.md`, CLAUDE.md Recent Changes, markdown lint
- [x] T013 Drop the `IadProbe130` scratch objects
- [x] T014 fmt, clippy, all suites; local commit

## Phase 5: skill-arm triage (US4, grill round 2)

- [X] T015 Offline tests in `tests/e2e/skill_eval/test_ladder_transcripts.py`: one transcript file per session named by task/arm/repeat; `needs_fix` flags a skill only when its arm fails ≥2 scored runs and tools pass ≥2, unscored runs count for neither; report names the transcript dir; `.gitignore` covers `*.transcripts/`
- [X] T016 `on_events` through `run_ladder` and `run_one`; `ladder._main` writes transcripts; `needs_fix`; ignore rule
- [ ] T017 Billable: re-run SKILL-13/14/16, 3 repeats per arm (cap $1.53; `--spent` makes `assert_within_budget` refuse past the cap, which guards SC-005), and print `needs_fix`
- [ ] T018 Per flagged skill: transcript quote and live reproduction in research.md; hand fix; unit and live guard tests
- [ ] T019 Per flagged skill: move the task to train, write a replacement holdout task, live before/after test, ladder it (3 repeats, with `--spent`)
- [ ] T020 research.md round 2 results and per-skill verdicts; CLAUDE.md entry; fmt, clippy, all suites; local commit
