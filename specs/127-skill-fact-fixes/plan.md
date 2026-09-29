# 127 plan: skill fact fixes

Spec: `spec.md`. Reproductions: `research.md`.

## Shape

Text edits to bundled skills under `skills/skills/`, each guarded by two tests:

- a live `#[ignore]` test in the core `integration` aggregate that shows IRIS doing what the corrected text says;
- a unit test in the core `unit` aggregate that fails if the old wrong wording comes back.

No Rust source changes. No tool, server instruction or benchmark field changes (FR-011, grill Q12).

## Test files

| File                                                | Target        | Holds                                                          |
| --------------------------------------------------- | ------------- | -------------------------------------------------------------- |
| `tests/integration/test_skill_facts_127_live.rs`    | `integration` | One live test per item, package `Test127`, cleanup at the end  |
| `tests/unit/test_skill_facts_127.rs`                | `unit`        | Wording guards, FR-005 scan, aihub-eap hash check              |
| `tests/unit/fixtures/aihub_eap_upstream_72f9046.md` | fixture       | Upstream `aihub-eap/SKILL.md` at blob `72f9046`, byte for byte |

Both files get a `mod` line in their aggregator's `main.rs`.

### Live test rules

- Loud skip: with `IRIS_HOST` unset the helper panics, unless `IAD_ALLOW_SKIP=1` (constitution XI).
- Classes go up by Atelier `PUT /doc`, compile through `compile_document`, and run through `execute_via_generator`. No terminal session, so no `ShowFlags` paging hazard.
- Nothing calls `%SYS.Python`. On iris-dev-iris a Python call can segfault the process and poison the routine cache (research, item 9). Item 9's live test asserts only on compile output.
- Every class is `Test127.*`; each test deletes its own classes with `$system.OBJ.Delete(name,"-d")` (no `e`, except the one test that asserts what `e` does).
- Run command, documented in the file header:

```bash
IRIS_HOST=localhost IRIS_WEB_PORT=52780 IRIS_USERNAME=_SYSTEM IRIS_PASSWORD=SYS \
  cargo test --features testing --test integration test_skill_facts_127_live -- --ignored --test-threads=1
```

## Item map

Research row numbers follow the original item list. Spec numbering:

| Research | Spec       | Skill(s)                                                                                         | Live assertion                                                                                       |
| -------- | ---------- | ------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| 1        | US1        | `iris-objectscript-eval`                                                                         | Compile/Load with recommended flags keeps rows; `Delete` with `e` empties the extent                 |
| 2        | US2.1      | `objectscript-loop-patterns`, `objectscript-fewshot-fixes`, `iris-sql`                           | Shared-line `Quit:key=""` compiles and runs; `Quit:key = ""` gives #1054                             |
| 3        | US2.2      | `objectscript-tdd`, `objectscript-loop-patterns`                                                 | `Quit 5` in `For` compiles, runtime `<COMMAND>`; inside `Try` compile error #1043                    |
| 4        | US2.3      | `objectscript-mac-routines`                                                                      | `.mac` with Try/Catch + Return compiles and returns `caught:<DIVIDE>`                                |
| list     | US2.4      | `objectscript-list-patterns`                                                                     | Both forms build the same list; concat is faster than `$LIST(*+1)` at 20k items                      |
| sql      | US2.5      | `objectscript-sql-patterns`                                                                      | Two-level class queries by dotted name; underscore gives -30                                         |
| 6        | US2.6      | `iris-sql`                                                                                       | `%Execute(args...)` with 3 args returns 3 rows                                                       |
| 7        | US2.7      | `objectscript-review`                                                                            | `New $Namespace` compiles and restores; `New x` in a procedure block gives #1038                     |
| 8        | US2.8      | `objectscript-guardrails`, `objectscript-review`                                                 | Callee bare `TROLLBACK` leaves caller at `$TLEVEL` 0; level-recording pattern keeps 1                |
| 9        | US2.9      | `iris-embedded-python`                                                                           | Unit guard only for wording; live test: none (Python is unsafe on iris-dev-iris)                     |
| prod     | US2.10     | `ensemble-production`                                                                            | Reproduced at implementation time; dropped to `dropped.md` if it will not reproduce                  |
| —        | US3.1      | `objectscript-tdd`, `objectscript-repair`, `iris-objectscript-eval`, `objectscript-mac-routines` | Unit: no skill passes a path to `iris_compile` (FR-005)                                              |
| —        | US3.2      | `ensemble-production`                                                                            | #5477 at compile time for a hand-written Storage; long package name compiles and saves               |
| —        | US3.3      | `iris-docs`                                                                                      | Unit: one DocBook rule, no "never curl" beside a curl recipe                                         |
| —        | US4        | `aihub-eap`                                                                                      | Unit: vendored hash equals fixture; upstream-diff limited to the marked patch                        |
| sql-3    | 130 FR-019 | `objectscript-sql-patterns` §3                                                                   | `If SQLCODE` is false on 0 and fires on 100 and on <0; the defect is treating 100 and <0 alike       |
| sql-5    | 130 FR-019 | `objectscript-sql-patterns` §5                                                                   | A forced -400 is surfaced (throw or status), not returned as `""`                                    |
| sql-9    | 130 FR-019 | `objectscript-sql-patterns` §9                                                                   | `COUNT(*) INTO :n` with an undefined `n` leaves `n` defined and 0                                    |
| sql-114  | 130 FR-019 | `objectscript-sql-patterns` §5                                                                   | Under READ COMMITTED a row lock times out with -114 and the INTO variable still holds the row's data |

The four `sql-*` rows come from the 130 round 4 review (`specs/130-content-skills/sql-patterns-review.md`) and are tracked as 130 T045. They land after 130's run 1 is measured, so the skill is not edited mid-measurement, and each gets a live `#[ignore]` test on `Test130.SqlCode` plus a wording test. The -114 probe sets `ProcessLockTimeout` (1 s) and `SET TRANSACTION ISOLATION LEVEL READ COMMITTED` for its own process only, so nothing instance-wide changes and nothing needs restoring. Measured: the locked read returns SQLCODE -114 with the INTO variable holding `Alpha`, the row's value; the same read after release returns 0. Embedded SQL against the missing `Test130_SqlCode` compiles and gives -30 at run time.

US4 uses an upstream copy as the fixture instead of a sha256: the core crate has no hash crate in its dev-dependencies, and comparing against the upstream text also proves the diff is limited to the marked patch, which a hash cannot.

Item 9 deviates from FR-004: its live half cannot run safely on this instance. That is recorded here and in the test file, not silently skipped.

## Order

1. `e` flag, its own commit (FR-002).
2. US2 items, one commit each or grouped by skill.
3. US3.
4. US4: re-sync from `/tmp/aihub-up.md` (upstream blob `72f9046`), apply the line-148 patch between `<!-- iad-local-patch -->` markers, record the hash in the fixture, draft the owner note in `.iad-local/127-aihub-owner-note.txt`.
5. `specs/123-demo-gap-fixes/followups.md` item (d) note; a follow-up line for the server instruction's "never reads local files".

## Constitution check

- XI: loud skips, documented run command, assertions reached unconditionally. Item 9 exception stated.
- XII: no env mutation in the unit file; the live file reads env only.
- Test-first: each item's tests are written and seen failing (unit) or passing against IRIS (live) before its text edit.
