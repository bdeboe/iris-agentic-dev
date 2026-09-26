# Tasks: 129 tool-result hints

Tests come first in every phase.

## Phase 1: hint_ref and the data file (US1)

- [x] T001 Unit tests: `hint_ref` fields, pack-off drop, no skill name in text, TOML rows equal matchers, cited sections exist (`tests/unit/test_error_hints.rs`)
- [x] T002 `hints.toml` and the `error_hints.rs` refactor
- [x] T003 `sql_err` takes query and namespace at its four call sites; runtime sites use `Hint::apply`
- [x] T004 Live tests for `hint_ref` and pack-off (`tests/integration/test_handlers_live.rs`)

## Phase 2: five new rules (US2)

- [x] T005 Unit tests for `sys_only_table`, `deep_package_table`, `double_quoted_string`, `reserved_word`, `nonstandard_insert`, with negatives
- [x] T006 Matchers for the five rules
- [x] T007 Replay corpus `tests/e2e/tasks/hints/replay.jsonl`, offline fixture test, live regeneration test
- [x] T008 Skill edits: sql-patterns §7 double quotes, iris-agentic-dev %SYS tables sentence; wording unit tests
- [x] T009 Binary test with `IAD_CODING_PACK=off`

## Phase 3: the loop surface (US3)

- [x] T010 Offline tests: surface load/apply, validator, adapter, gates, holdout, CLI
- [x] T011 `hints_surface.py`, `hints_proxy.py`, `hints_adapter.py`, `hints_runner.py`, `surfaces.py`, `__main__.py`
- [x] T012 Frozen split file

## Phase 4: docs and checks

- [x] T013 `docs/tools.md`, `docs/troubleshooting.md`, CLAUDE.md Recent Changes
- [X] T014 fmt, clippy, unit, live, Python suites; local commit
