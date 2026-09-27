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

- [x] T015 Offline tests in `tests/e2e/skill_eval/test_ladder_transcripts.py`: one transcript file per session named by task/arm/repeat; `needs_fix` flags a skill only when its arm fails ≥2 scored runs and tools pass ≥2, unscored runs count for neither; report names the transcript dir; `.gitignore` covers `*.transcripts/`
- [x] T016 `on_events` through `run_ladder` and `run_one`; `ladder._main` writes transcripts; `needs_fix`; ignore rule
- [x] T017 Billable: re-run SKILL-13/14/16, 3 repeats per arm (cap $1.53; `--spent` makes `assert_within_budget` refuse past the cap, which guards SC-005), and print `needs_fix`
- [x] T017a Harness isolation: `IsolatedEnv` sets `OPENCODE_DISABLE_CLAUDE_CODE=1` (opencode read `~/.claude/CLAUDE.md` and `~/.claude/skills` into every session); unit + billable live test in `tests/e2e/test_isolated_env.py`; clean re-run of flagged SKILL-16 → keep
- [x] T018 Per flagged skill (none flagged after T017a; no fix): transcript quote and live reproduction in research.md; hand fix; unit and live guard tests
- [x] T019 Per flagged skill (none flagged; SKILL-16 stays on holdout, no SKILL-20): move the task to train, write a replacement holdout task, live before/after test, ladder it (3 repeats, with `--spent`)
- [x] T020 research.md round 2 results and per-skill verdicts; CLAUDE.md entry; fmt, clippy, all suites; local commit

## Phase 6: skill arm loads its skill, re-baseline (grill round 3)

- [x] T021 Tests first in `tests/e2e/skill_eval/test_skill_preload.py`: a skill arm's prompt asks for its skill; a skill arm that never loads it is unscored; three in a row stop the ladder; every arm gets the same autonomy line, which names no tool and no skill
- [x] T022 Same for the 118 skill-eval in `test_lift_preload.py`; `session_prompt`, `unloaded_skill_verdict`
- [x] T023 `iris_macro` on the real `getmacro*` routes and `/docnames/RTN/INC`; `MACRO_NOT_FOUND` instead of `{}`; unit shapes in `test_macro_130.rs`, live handler tests (drafts #3)
- [x] T024 `resume --merge` keys on the repeat; `ladder --start-repeat`; tests in `test_resume.py`, `test_ladder.py`
- [x] T025 Billable: ladder `--skill all --repeats 3` over SKILL-01 to SKILL-19, resumed after the host slept; merge to `ladder-r3-merged.json`; `needs_fix` flags SKILL-13 and SKILL-09
- [ ] T026 Billable: skill-eval `--update-baseline` on the clean harness; research.md round 3; CLAUDE.md entry; markdown lint; local commit
- [x] T027 SKILL-13 fix in `iris-query-plans` (the `%NOINDEX` loader calls `%BuildIndices`), unit + live test; SKILL-13 to train, SKILL-20 on the holdout, validated live; billable ladder `--task SKILL-20 --repeats 3`
- [x] T028 Tests first in `test_isolated_env.py`: isolated sessions deny `external_directory`, so a baseline grep on `/` no longer runs into the 300 s clock
