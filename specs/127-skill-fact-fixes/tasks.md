# 127 tasks

Tests before text, per item. Live command in `plan.md`.

## Phase 1: harness

- [X] T001 Create `tests/unit/test_skill_facts_127.rs` and its `mod` line in `tests/unit/main.rs`
- [X] T002 Create `tests/integration/test_skill_facts_127_live.rs` with the loud-skip connection helper, `put_class`, `compile`, `run`, `cleanup`, and its `mod` line

## Phase 2: US1, compile flag `e` (own commit)

- [X] T010 Unit: `iris-objectscript-eval` never calls `e` harmless and never recommends it
- [X] T011 Live: rows survive `Compile`/`Load` with `cuk`; `Delete(,"e-d")` empties the extent
- [X] T012 Edit `iris-objectscript-eval` line 140; commit

## Phase 3: US2

- [X] T020 US2.1 tests + edit (loop-patterns, fewshot-fixes, iris-sql)
- [X] T021 US2.2 tests + edit (tdd, loop-patterns)
- [X] T022 US2.3 tests + edit (mac-routines)
- [X] T023 US2.4 tests + edit (list-patterns §1)
- [X] T024 US2.5 tests + edit (sql-patterns §§2, 4, 5, 9)
- [X] T025 US2.6 tests + edit (iris-sql `%Execute`, drop the IN-list concatenation workaround)
- [X] T026 US2.7 tests + edit (review `New`)
- [X] T027 US2.8 tests + edit (guardrails, review `TROLLBACK`)
- [X] T028 US2.9 unit test + edit (embedded-python quoting; no live call)
- [X] T029 US2.10 reproduce production restart live; edit or record in `dropped.md`

## Phase 4: US3

- [X] T030 FR-005 unit scan over all skills; edit tdd, repair, eval, mac-routines
- [X] T031 US3.2 live #5477 + long-name tests; edit ensemble-production Storage, 31-char claim, `iris_execute` workaround
- [X] T032 US3.3 unit test; edit iris-docs DocBook rule
- [X] T033 Note in `specs/123-demo-gap-fixes/followups.md` (d); server-instruction follow-up line

## Phase 5: US4

- [ ] T040 Unit: vendored aihub-eap hash equals fixture; line-148 patch marked
- [ ] T041 Re-sync from upstream `72f9046`, apply the marked patch, write the fixture
- [ ] T042 Draft `.iad-local/127-aihub-owner-note.txt` (not sent)

## Phase 6: gate

- [ ] T050 `cargo fmt --all`, `cargo clippy -- -D warnings`, full `unit` target, live 127 file against iris-dev-iris
