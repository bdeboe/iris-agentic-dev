# Implementation Plan: fix what the todo-app demo exposed

**Branch**: `123-demo-gap-fixes` | **Date**: 2026-09-22 | **Spec**: [spec.md](spec.md)

## Summary

This branch makes four changes and adds no new tool:

- **Tier claims:** a unit test compares every tier claim in the 81 tool descriptions with
  `write_gate::CLASSIFICATION`. I watch it fail on 18 units, then correct nine descriptions.
- **SQL facts:** two facts reproduced live go into skills, one of which corrects a false belief
  the demo agent wrote down.
- **Worked example:** the demo is published as `docs/examples/todo-app/`, guarded by a scrub test
  and a live round-trip test that drives it through a real MCP session.
- **Follow-ups:** two further findings are drafted in `followups.md`.

## Technical Context

**Language/Version**: Rust 2021 (tests, descriptions in `src/tools/mod.rs`), Markdown (skills,
docs), ObjectScript (the two published example classes, unchanged)
**Primary Dependencies**: existing only: `regex`, `serde_json`, `reqwest` (dev), `tempfile`
**Storage**: N/A
**Testing**: `cargo test --features testing`. The tier and scrub tests go in the `unit` target;
the round-trip test goes in `integration` and runs `#[ignore]` against live `iris-dev-iris`
**Target Platform**: the same as the shipped binary. The tests are host-independent
**Project Type**: single workspace, two crates
**Performance Goals**: N/A
**Constraints**: nothing pushed, merged or tagged (FR-015). The live `/todo` demo must survive
(research R5)
**Scale/Scope**: nine descriptions, two skills, four published files, three test files

## Constitution Check

| Principle                      | Status | Notes                                                                                              |
| ------------------------------ | ------ | -------------------------------------------------------------------------------------------------- |
| I. Zero-Install Binary         | N/A    | No install change                                                                                  |
| II. ObjectScript Sanity        | PASS   | Both SQL facts reproduced live (R1, R2); example classes compile in the round-trip test            |
| III. HTTP-First Execution      | PASS   | No new tool                                                                                        |
| IV. Test-First                 | PASS   | Tier test written and seen failing before any description edit; scrub test before packaging        |
| V. Output Shape Parity         | N/A    | No response shape changes                                                                          |
| VI. Environment Guard          | PASS   | Gate behaviour unchanged; only the text describing it changes, and a test now ties the two         |
| VII. Dependency Minimalism     | PASS   | No new crate                                                                                       |
| VIII. 90% Coverage Gate        | N/A    | No new `src/` logic; test and description text only                                                |
| IX. Tool Lift Requirement      | N/A    | No new MCP tool                                                                                    |
| X. ObjectScript Coverage       | N/A    | The example classes are documentation, exercised end to end by the round-trip test                 |
| XI. No Vacuous Tests           | PASS   | Round-trip panics without IRIS; action sets asserted non-empty; `#[ignore]` run by `quickstart.md` |
| XII. Hermetic Test Environment | PASS   | Round-trip uses `McpSession` (`clean_mcp_command`) and sets its own tiers                          |
| User-Facing Strings Are API    | PASS   | Every IRIS claim in `STEPS.md` checked live (R2, R3); the false one removed                        |

## Project Structure

### Documentation (this feature)

```text
specs/123-demo-gap-fixes/
├── spec.md
├── plan.md
├── research.md      # R1–R8, live reproductions
├── quickstart.md    # the commands that run every test here, including #[ignore]
├── followups.md     # drafts (d) and (e)
├── checklists/requirements.md
└── tasks.md
```

### Source Code

```text
crates/iris-agentic-dev-core/
├── src/tools/mod.rs                          # nine descriptions corrected
└── tests/
    ├── unit/main.rs                          # + two mod lines
    ├── unit/test_description_tiers.rs        # US1: FR-001..FR-005
    ├── unit/test_example_scrub.rs            # US3: FR-009..FR-011
    ├── integration/main.rs                   # + one mod line
    └── integration/test_todo_example_live.rs # US3: FR-012, FR-013
skills/skills/objectscript-sql-patterns/SKILL.md   # §7 third example + pointer
skills/skills/iris-sql/SKILL.md                    # InitialExpression bullet
docs/examples/todo-app/{Demo.Todo.cls,Demo.TodoREST.cls,STEPS.md,transcript.md}
.gitignore                                          # + /.iad-local/
```

**Structure Decision**: tests join the existing aggregate targets and each gets a `mod` line
(`test_test_target_layout.rs` enforces this). No new `[[test]]` block is added.

## Phases

1. **US1**:
   - Write the tier test and save its failing output, which must show 18 units.
   - Correct the descriptions, then rerun: green.
   - Run the full `unit` target.
2. **US2**:
   - R1 and R2 are already reproduced, so write both skill edits and the pointer.
   - Run the skill lint and frontmatter tests if they exist (`cargo test --test skills`).
3. **US3**:
   - Write the scrub test first. With `docs/examples/todo-app/` absent it fails, because the
     published directory must exist.
   - Copy the four files, replace names with roles, drop the false claim, and add the transcript
     note. Scrub goes green.
   - Write the round-trip test and run it live. Green is the phase gate.
4. **US4**: write `followups.md`. The fold-lists task stays open in `tasks.md`.
5. **Polish**:
   - Run `cargo fmt`, `clippy -D warnings`, the `unit` target and the `integration` target (serial).
   - Take the SC-006 payload measurement.
   - Lint the markdown and commit locally.

## Complexity Tracking

None.
