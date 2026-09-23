# 125 tasks

- [x] T001 Unit tests for `sql_error_hint` and `runtime_error_hint` (`tests/unit/test_error_hints.rs`), failing first
- [x] T002 Unit test: every cited skill section heading exists in its SKILL.md
- [x] T003 Unit test: `iris_execute`'s description names the %SYS-only packages
- [x] T004 Live tests: `iris_query` -12 and `iris_execute` Security.Applications in USER carry `hint`; the same call in %SYS and an unmatched error carry none
- [x] T005 `tools/error_hints.rs` with the two rows
- [x] T006 Wire `hint` into the four `SQL_ERROR` sites in `iris_query` and the three `IRIS_RUNTIME_ERROR` sites in `iris_execute`
- [x] T007 Skill section in `iris-agentic-dev`: system classes live in %SYS
- [x] T008 `iris_execute` description line; `docs/tools.md` documents `hint`. CHANGELOG entry waits: `CHANGELOG.md` exists only on `changelog-136`, not on master
- [ ] T009 Merge order: 125 goes in after `123-demo-gap-fixes`. The SQL row cites `objectscript-sql-patterns` §7, and the `$ZDATETIME` example that makes that citation useful is only on 123. On this branch §7 covers `'=` and `%INLIST` and nothing else. T002 passes because it checks that the heading exists, not what the section says.
- [ ] T010 Tighten T002 so each citation also names a term the section has to contain (`$ZDATETIME` for the SQL row, `<CLASS DOES NOT EXIST>` for the %SYS row). It will fail here until 123 merges, which is the point.
