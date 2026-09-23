# Tasks: fix what the todo-app demo exposed

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md)
**Tests**: required, and written first in every phase.

## Phase 1: US1 — tier claims match the gate table (P1)

- [x] T001 [US1] Write `crates/iris-agentic-dev-core/tests/unit/test_description_tiers.rs` to the
      grammar in research R6 and add its `mod` line to `tests/unit/main.rs`.
- [x] T002 [US1] Run it on unchanged descriptions and confirm it fails on exactly 18 units (FR-003).
      Save the failure list to `specs/123-demo-gap-fixes/evidence/tiers-before.txt`.
- [x] T003 [US1] Correct the descriptions in `src/tools/mod.rs` for `iris_admin`, `global_kill`,
      `iris_namespace_create`, `iris_credential_manage`, `iris_lookup_manage`, `iris_global`,
      `skill`, `iris_remove_server` and `skill_forget` (FR-004). Change only the text.
- [x] T004 [US1] Gate: the tier test passes, and so does the whole `unit` target.

## Phase 2: US2 — SQL facts in skills (P2)

- [x] T005 [US2] Reproduce both facts live and record them (research R1, R2; FR-008).
- [x] T006 [US2] Add the `$ZDATETIME` example to `objectscript-sql-patterns` §7 (FR-006).
- [x] T007 [US2] Add the `InitialExpression` bullet to `iris-sql` "Key IRIS INSERT constraints",
      plus the one-line pointer from `objectscript-sql-patterns` (FR-007).
- [x] T008 [US2] Gate: the skill-content tests in `unit` pass (there is no separate `skills` target in core).

## Phase 3: US3 — the published example (P2)

- [x] T009 [US3] Write `tests/unit/test_example_scrub.rs` and add its `mod` line. It covers
      FR-009, FR-010 and FR-011, and must fail while the directory is absent.
- [x] T010 [US3] Add `/.iad-local/` to `.gitignore`. Create a local denylist holding the names.
- [x] T011 [US3] Build `docs/examples/todo-app/` from `demos/todo-app/`:
  - copy the two classes;
  - replace names with roles in `STEPS.md` and `transcript.md`;
  - remove the false `InitialExpression` claim and add the transcript note (FR-016);
  - strip home paths.
- [x] T012 [US3] Scrub test green, with the denylist present and with it absent.
- [x] T013 [US3] Write `tests/integration/test_todo_example_live.rs` to research R4 and R5, and
      add its `mod` line (FR-012, FR-013).
- [x] T014 [US3] Gate: the round-trip test passes live and leaves no `IADEx123` classes, rows,
      globals or `/iadex123-todo` app behind.

## Phase 4: US4 — follow-ups (P3)

- [x] T015 [US4] Write `followups.md` with drafts (d) and (e) (FR-014). File neither. Also holds
      (f) the `IRIS_ADMIN_TOOLS` gate and (g) the ai-core NoPWS findings with cross-repo drafts.
- [ ] T016 [US4] Once spec 121 merges, fold the drafted defects from specs 121, 122 and 123 into
      one list. This stays open until then.

## Phase 5: Polish

- [x] T017 Run `cargo fmt --all`, `cargo clippy --all-targets --features testing -- -D warnings`
      and the full `unit` target.
- [x] T018 Record the SC-006 `tools/list` byte count before and after in `quickstart.md`.
- [x] T019 Run markdownlint and prettier on every changed `.md`, then make local commits. No push
      (FR-015).

## Phase 7: Gate purpose, from the follow-ups grilling (2026-09-22)

Tom approved (d) as an accident guard, (f) as documentation only, and (g2) as text only. Each is on
this branch. (e) and (g1) get their own specs after the freeze.

- [x] T020 Write `tests/unit/test_gate_purpose_wording.rs` first: the `IRIS_ADMIN_TOOLS` sentence
      in `iris_admin` names exactly the handlers that call `admin_write_allowed()`,
      `docs/connecting.md` names the variable, `iris_execute` names the destructive gate and the
      hard limit, and `NOPWS_ATELIER_REQUIRED` names `iris_execute`, `iris_compile` and `.mac`. All
      four failed before the text changed. Principle VI is not checked: `.specify/` is untracked.
- [x] T021 (f) List the ten `IRIS_ADMIN_TOOLS` actions in `iris_admin`'s description and add
      "What the tiers guard, and what they don't" to `docs/connecting.md`.
- [x] T022 (d) Amend Principle VI locally (1.5.3 → 1.6.0, MINOR; untracked) and add the matching sentence to
      `iris_execute`. The same description now says the `.mac` escape hatch needs Atelier REST.
- [x] T023 (g2) `NOPWS_ATELIER_REQUIRED` says `iris_execute` and `iris_compile` still work under
      `docker_only`, and where `{}` blocks can go.
- [x] T024 Rerun unit (2394), binary (70), clippy and fmt. Re-measure SC-006.
