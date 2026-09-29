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
- [x] T026 Billable: skill-eval `--update-baseline` on the clean harness; research.md round 3; CLAUDE.md entry; markdown lint; local commit
- [x] T027 SKILL-13 fix in `iris-query-plans` (the `%NOINDEX` loader calls `%BuildIndices`), unit + live test; SKILL-13 to train, SKILL-20 on the holdout, validated live; billable ladder `--task SKILL-20 --repeats 3`
- [x] T028 Tests first in `test_isolated_env.py`: isolated sessions deny `external_directory`, so a baseline grep on `/` no longer runs into the 300 s clock
- [x] T029 Tests first in `test_lift.py`: `_reached_idle` accepts a last `step_finish` with `reason: stop` (opencode never emits `session.status`); d05fb33
- [x] T030 Tests first in `test_reporter.py`: the skill-eval report reads in plain words (no triage jargon, underpowered rows name pairs and floor once, a shared tool-surface note prints once, withdrawn skills name their ladder tasks, uncovered skills split into ladder-only and not graded anywhere); the r5 result file is the fixture
- [x] T031 Tests first in `test_triage.py`/`test_baseline.py`: 402a740 re-measured seven verdicted skills, and three guards still read the 2026-09-12 state; `triage.verdict_superseded` lets a later run with no withdrawn block stand, and the cured verdicts (iris-connectivity, objectscript-list-patterns, now 0.33 → 0.67) move to `triage_records.SUPERSEDED`

## Phase 7: sql-patterns check, judge limits, three iad bugs (US5, grill round 4)

Run 1:

- [x] T032 Tests first in `test_lift.py`: a 7,000-character tool arg and tool result both reach `judge._format_transcript` and `lift.format_transcript`; a runaway one stops at `TRANSCRIPT_TEXT_LIMIT` (FR-013)
- [x] T033 Raise the judge's arg and result caps and lift's result cap to `TRANSCRIPT_TEXT_LIMIT`
- [x] T034 Tests first, Rust unit: `telemetry::flush` waits for a pending durable write and returns at its timeout when one hangs; the telemetry scratch prefix is `IrisDevTmp.IrisDevTel`; bin guard: `std::process::exit` appears only in the flush-then-exit helper (FR-014)
- [x] T035 `telemetry::PendingWrites` (`DURABLE_WRITES.spawn`) + `flush`/`flush_blocking`; `record_call` spawns through it; bin `exit` helper and end-of-`main` flush; `delete_doc` returns its failure and the executor logs it
- [x] T036 Live `#[ignore]`: `iad exec 'Write 1'` exits and leaves no `IrisDevTmp.IrisDevTel*` class in USER
- [x] T037 Tests first, unit: `iris_info` documents drop `result.content`, route `MAC`/`INT`/`INC` to `RTN/<type>` and `ALL` to `*`, hide `IrisDevTmp.*` unless `include_scratch`, and keep a ceiling under `inline=true` with `truncated` and `total_count`; `iris_doc list` routes and hiding; binary: `tools/list` shows `include_scratch` on both (FR-015, FR-016)
- [x] T038 `iris_info` and `iris_doc list` fixes; live `#[ignore]` tests in USER for both
- [x] T039 Cleanup on iris-dev-iris: purge `IrisDevTmp.IrisDevRun*` from USER, `Kill ^Test130Err.Flag, ^Test130Err.Out`; docnames filter confirms 0 (FR-020)
- [x] T040 SKILL-21 on the train side of `split.toml`; shape test and live before/after (fixture fails, solution passes) (FR-017)
- [x] T041 Tests first: an eval with no `benchmark_tasks` is skipped by name; then delete SQLCODE-SILENT and SQLCODE-CHECK, empty sql-patterns' eval, drop its baseline row with a note (FR-018)
- [x] T042 127's fact-fix table gets the §§3/5/9 fixes and the -114 fact
- [x] T040a Harness fixes found on the way, each with a test: `McpSession` drops by closing stdin and waiting up to 5 s before a kill, so a spawned server finishes its telemetry write; the exec leak test compares class names before and after instead of counting; the doc-CLI example test skips `text`/`output` fences; the unit-test skill test forces `^UnitTestRoot` to `/tmp/` and restores it (the container had `"/"`, so RunTest scanned `/`); `ScratchGuard` in `connection.rs` deletes the executor's class when the future is dropped mid-call (runtime shutdown, client cancel), which left 122 `IrisDevTel` and 3 `IrisDevRun` classes after one full run — live test `test_scratch_cancel_130`
- [x] T040b Tests first: `test_mcp_sigterm_130` (bin integration, live) sends SIGTERM to `iad mcp` right after one tool call and asserts an exit code (not death by signal) and no new `IrisDevTmp.IrisDev*` class; then `iad mcp` selects on SIGTERM/Ctrl-C beside the serve loop and returns so `main` flushes, and `main` shuts its runtime down with a 2 s bound so the parked stdin reader cannot hold the exit; `testing::stop_server` (SIGTERM, 10 s, then kill) replaces the bare `Child::kill` in every harness a per-module leak bisect names (`test_gate_enforcement_live` 39 classes, `test_e2e` 5, `test_fresh_container_setup_live` 3, `test_e2e_all_tools` 1, `test_environment_restriction_live` 1, plus any later module); every harness resolves the binary through `testing::iad_binary_path`, which takes `target/llvm-cov-target` only when `CARGO_LLVM_COV` is set (guard `test_one_binary_resolver_130`); a full credentialed run then leaves 0 (FR-014)
- [x] T040c Tests first: unit `macro_include_compile_failure`, live `one_broken_include_does_not_hide_the_others`; then `iris_macro` halves the include list on "Failure to compile include files" and drops the includes that fail, naming them (FR-021)
- [x] T043 fmt, clippy, all suites (unit parallel, integration serial with `--include-ignored`), pytest; local commit
- [x] T043a Tests first: `run_validity` (one thin skill does not void the run; a run-wide share over the limit does; a skill with nothing scored is excluded), `baseline_writes` for the merge path; then wire both (FR-022)
- [x] T044 Billable: tell Tom the cost (~$3), then skill-eval `--update-baseline`
- [x] T044a Triage the re-baseline: supersede the `ensemble-production` and `iris-ai-hub` verdicts; verdicts and withdrawn blocks for `iris-connectivity`, `objectscript-review` (`not_helped`) and `iris-vector-ai` (`too_hard`); `test_triage.py` updated first

Run 2:

- [x] T045 Tests first: wording tests for sql-patterns §§3/5/9 and the -114 fact, and live `#[ignore]` tests on `Test130.SqlCode`; then the skill edits (FR-019)
- [x] T046 Billable: ladder on SKILL-09, 3 repeats per arm (~$0.50). SKILL-21 is train, and the ladder runs holdout tasks only, so it is not on this run
- [x] T046a Tests first: unit `package_prefixes`, `created_classes`, and a `run_one` test that a class created during the session is deleted after the check; live `test_a_session_leftover_is_deleted`; then wire it (FR-023)
- [x] T046b Purge the leftovers from BENCHMARK: `Bench.Calc.Tests.MathTest`, `Bench.Patient.Test`, `Bench.Probe`, `Bench.Q2.CountOther`, `Bench.Stor`, `Bench.Validator`; no task names any of them (FR-023)
- [x] T047 Triage record for sql-patterns: `broken_check`, rubric asserted a false IRIS fact and the judge could not see code; research.md round 4; CLAUDE.md entry; markdown lint; local commit
- [x] T048 Billable, needs Tom's go: re-run the SKILL-09 ladder with FR-023 in place, 3 repeats per arm (~$0.51, outside SC-007). The T046 run is contaminated by the leftover class, so the sql-patterns ladder has no clean figure until this runs. Command: `python -m tests.e2e.skill_eval.ladder --ladder skill --skill objectscript-sql-patterns --repeats 3 --task SKILL-09`; commit `tests/e2e/results/ladder-<ts>.runs.jsonl`, add the result to `research.md` § sql-patterns ladder and update the T047 record in `tests/e2e/skill_eval/triage_records.py` if the verdict moves. Gate: `test_a_session_leftover_is_deleted` passes live first (SC-008). Done: `ladder-20260929T023344`, tools 1/3, tools+skill 1/3, all four FAILs are the table name, verdict unchanged, no triage edit
