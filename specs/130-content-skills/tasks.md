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

- [X] T011 Billable: loop run, 128 drift re-measure, ladder (capped at $3)
- [X] T012 `docs/skills.md`, CLAUDE.md Recent Changes, markdown lint
- [X] T013 Drop the `IadProbe130` scratch objects
- [X] T014 fmt, clippy, all suites; local commit
