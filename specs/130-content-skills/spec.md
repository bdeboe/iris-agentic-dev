# Feature Specification: Content skills, checked live and measured on the ladder

**Feature Branch**: `130-content-skills`
**Created**: 2026-09-26
**Status**: Draft
**Input**: 127–130 loop design (grill, 2026-09-26): "content skills: clean-room, generic IRIS, nothing HealthShare-specific and no text from Pierre's pack. Every claim reproduced live. Bodies are hand-written; gepa edits descriptions only. The holdout ladder measures lift. A correctness gap ships without lift, labelled no lift claim."

## Context

127 fixed skill text that was wrong. 128 tuned descriptions for routing, and 129 tuned hint wording. None of the three added content an agent was missing. 130 does that for the gaps the live probes in `research.md` found:

- **Query plans and indexes.** No skill explains reading a plan, why a class-added index returns short counts until `%BuildIndices`, or why an outlier value reads the master map on purpose (R5).
- **Five skills are wrong or thin on something an agent hits:**
  - `objectscript-sql-patterns` checks `%SQLCODE` only after execute, and a fetch-time error then reads as an empty result (R1).
  - `objectscript-unit-test` and `iris-objectscript-eval` give `iris_test` patterns that find nothing, and neither says a method not named `Test*` never runs (R3).
  - `objectscript-tdd` treats a clean compile as progress, but a typo'd local compiles clean (R4).
  - `ensemble-production` calls a method that does not exist (R6).
  - `iris-agentic-dev` does not say how to load an XML export. It can go on under its `.cls` name, but only with the XML declaration on its own line, and iad hides the error when it is not (R7).
  - `objectscript-guardrails` has no namespace rule, and `New $NAMESPACE` is the idiom (R2).

HL7 and embedded Python `None` were in the grill list. Both are blocked on iris-dev-iris and dropped (research.md, "Blocked").

## User Scenarios & Testing

### User Story 1 - Skill text matches what IRIS does (Priority: P1)

An agent that follows a content skill writes code that works on IRIS the first time.

**Independent Test**: For every claim, a live `#[ignore]` test runs the skill's pattern on iris-dev-iris and asserts the stated behaviour. A unit test fails if the old wrong text comes back.

**Acceptance Scenarios**:

1. **Given** `objectscript-sql-patterns` §4, **Then** it checks the status from `%Next(.sc)` and `%SQLCODE` after the loop, and §5 checks `%Prepare`'s status.
2. **Given** `objectscript-unit-test` and `iris-objectscript-eval`, **Then** every `iris_test` pattern they show is `:Package.Class` or a documented form, the tool is `iris_test`, and both say only `Test*` methods run and a run of nothing reports passed.
3. **Given** `ensemble-production`, **Then** it names neither `GetProductionState` nor `$$$EnsProductionRunning`, it checks state with `GetProductionStatus`, and its state table has 5.
4. **Given** the new skill `iris-query-plans`, **Then** each plan line and count it quotes matches a live test.
5. **Given** `objectscript-guardrails`, `objectscript-tdd` and `iris-agentic-dev`, **Then** they carry the namespace, clean-compile and XML-export rules.

### User Story 2 - The ladder measures whether the content helps (Priority: P1)

Each content gap gets a graded ladder task, SKILL-13 to SKILL-19, on the holdout side of `split.toml`. The task fails before the fix and passes after, both checked live. The ladder runs with and without the skill.

**Independent Test**: `test_every_committed_task_is_false_before_and_true_after` passes for every new task.

**Acceptance Scenarios**:

1. **Given** a new task, **Then** its check contains no clock or random call, its solution names only fixture documents, and it sits in the holdout.
2. **Given** a ladder run with no lift for a skill, **Then** the change still ships, and its report line says "no lift claim".

### User Story 3 - The loop can tune the new descriptions without touching the rest (Priority: P2)

`optimize run --surface content-descriptions` runs 128's routing loop, but gepa may edit only the descriptions of skills 130 touched. The corpus is the routing corpus plus new content items with a frozen split.

**Independent Test**: Offline tests with a scripted scorer show that a proposal for an untouched skill is never made, the apply step refuses one, and no holdout item reaches the train scorer.

### User Story 4 - A skill arm that loses is triaged, not guessed at (Priority: P1)

The first ladder run found tools alone passing 7 of 7 and tools+skill 4 of 7, with SKILL-13, SKILL-14 and SKILL-16 lost with the skill loaded. One run per arm cannot tell a misleading skill from noise, and the ladder kept no transcripts to look at. Round 2 of the grill (2026-09-26) settled what happens next.

**Independent Test**: An offline test drives `run_ladder` with a scripted driver and asserts one transcript file per session, named by task, arm and repeat. A unit test applies the triage rule to scripted run records.

**Acceptance Scenarios**:

1. **Given** any ladder run, **Then** every session's raw event stream is written under `tests/e2e/results/<run_id>.transcripts/`, which git ignores.
2. **Given** SKILL-13, SKILL-14 and SKILL-16 at three runs per arm, **When** a skill arm fails at least 2 of its scored runs on a task where the tools arm passed at least 2 (unscored runs count for neither), **Then** that skill is marked for a fix. Any other outcome keeps "no lift claim".
3. **Given** a skill marked for a fix, **Then** the sentence that misled the agent is quoted from a transcript in research.md, reproduced live, rewritten by hand, and guarded by a unit test that fails if the old wording returns.
4. **Given** a task whose transcript drove a fix, **Then** it moves to the train side of `split.toml`, and a new holdout task tests the same fact another way, failing before the fix and passing after, live. Only the new task's ladder result can carry a lift claim.

### User Story 5 - sql-patterns is measured by a check that is true about IRIS (Priority: P1)

`objectscript-sql-patterns` scored 0 in both arms after every harness fix. The 2026-09-28 review (`sql-patterns-review.md`) found the check was at fault. SQLCODE-SILENT's rubric says `If SQLCODE` fires on success. It does not: 0 is falsy. The rubric also asks for `If SQLCODE '= 0`, which fires on the same values. The judge takes up the rubric's claim, and it cannot see the code at all, because tool args are cut to 120 characters and results to 200. The skill's §3 makes the same false claim. The real session also ran into three iad bugs. Telemetry writes run through a detached task that a CLI process drops at exit, between compile and delete, so its scratch class stays (78,183 in USER). `iris_info what=documents` returns the list twice and `inline=true` skips truncation, so that call returned about 20 MB. And `iris_doc list` with no category asks Atelier for `/docnames/MAC`, which answers 400. Round 4 of the grill (2026-09-28) settled the fix.

**Independent Test**: SKILL-21 fails on its fixture and passes on its solution, live. The judge-limit test fails at a cap under 8000. A live test runs `iad exec` and finds no telemetry scratch class left after the process exits.

**Acceptance Scenarios**:

1. **Given** the judge reads a transcript, **Then** every tool call's args and result reach it up to 8000 characters, the same limit as assistant text.
2. **Given** a CLI call that records telemetry, **When** the process exits, **Then** no `IrisDevTmp.IrisDevTel*` class is left behind, and a delete that fails is logged, not dropped.
3. **Given** `iris_info what=documents` with `inline=true`, **Then** the response stays under a fixed ceiling and says `truncated` with the total when it cuts; `IrisDevTmp.*` classes are not listed unless asked for.
4. **Given** `iris_doc mode=list` with no category or with `MAC`, `INT` or `INC`, **Then** it lists routines through `/docnames/RTN/<type>` and does not fail.
5. **Given** SKILL-21, **Then** its check passes only when a known MRN returns its name, an unknown MRN returns `""`, and an MRN whose row is corrupt makes `FindPatient` throw. The prompt states that contract and does not mention SQLCODE.
6. **Given** SQLCODE-SILENT and SQLCODE-CHECK, **Then** both are gone, sql-patterns has no targeted eval, and the report shows its ladder result instead.
7. **Given** sql-patterns §§3, 5 and 9, **Then** each false claim is gone, a unit test fails if it returns, and a live test shows what IRIS does.

### Edge Cases

- A ladder check that starts a production must stop it, even when the check fails.
- If `%BuildIndices` has already run, the index-backfill fixture must reset its state, or "before" passes.
- Content prompts are author-written, and the README says so. Two blind labelling passes decide each item's expected skill.
- SKILL-21's forced SQL error must not depend on a lock or on `LockTimeout`, which is instance-wide. The corrupt-row recipe (a non-`$LIST` data node plus an index entry that points at it) gives SQLCODE -400 in every process.
- An eval with no targeted tasks left for a skill skips it by name instead of scoring nothing.

## Requirements

- **FR-001**: Every content claim has a live test on iris-dev-iris, and a claim with no reproduction is not written.
- **FR-002**: Every removed wrong string has a unit test that fails if it returns.
- **FR-003**: `iris-query-plans` is registered in every place a bundled skill is listed, and the manifest sync test passes.
- **FR-004**: Tasks SKILL-13 to SKILL-19 pass the shape validator and the live before/after test, and sit on the holdout side.
- **FR-005**: gepa never edits a skill body. The `content-descriptions` surface edits only the descriptions of skills 130 touched.
- **FR-006**: The ladder figure is reported per skill, and a skill without lift is labelled "no lift claim", not dropped.
- **FR-007**: No text from Pierre Abdelsayed's pack, and nothing HealthShare-specific.
- **FR-008**: Scratch objects from the probes are removed from iris-dev-iris.
- **FR-009**: The ladder writes each session's event stream to a transcript file, and the run's report names the directory.
- **FR-010**: The triage rule (skill arm fails at least 2 scored runs where tools passes at least 2; unscored runs count for neither) is code with a unit test, applied to the re-run's records, not judged by hand.
- **FR-011**: A task used to fix a skill leaves the holdout. The `split.toml` change and the replacement holdout task land in the same commit as the fix.
- **FR-012**: Round 2 runs no content-descriptions loop. That waits for mined prompts in the content corpus.
- **FR-013**: The judge reads each tool call's args and result up to the same 8000-character limit as assistant text, and a test fails if either cap is lower.
- **FR-014**: A process that writes telemetry through a scratch class waits (bounded) for that write, delete included, before it exits, so no `IrisDevTmp.*` class outlives the call that made it; a failed removal is logged. Telemetry scratch classes use their own prefix, `IrisDevTmp.IrisDevTel`. This holds when the process is stopped by SIGTERM or Ctrl-C, the way MCP hosts stop a server: `iad mcp` treats either signal as end of input and exits through the same flush. Test harnesses stop a spawned server the same way (SIGTERM, bounded wait, kill only as fallback). Every harness finds the binary through one resolver, which takes the coverage build only under `cargo llvm-cov`, so a plain run never spawns a stale binary that lacks the handler.
- **FR-015**: `iris_info what=documents` returns the list once (not also under `result.content`), maps `MAC`/`INT`/`INC` to the `RTN/` routes, has a ceiling that `inline=true` does not lift, reports `truncated` and the total when it cuts, and hides `IrisDevTmp.*` by default. `iris_doc mode=list` hides `IrisDevTmp.*` the same way.
- **FR-016**: `iris_doc mode=list` reads routines from `/docnames/RTN/MAC`, `RTN/INT` and `RTN/INC`.
- **FR-017**: SKILL-21 is on the train side of `split.toml` and passes the shape and live before/after tests. SKILL-09 stays on the holdout, unchanged.
- **FR-018**: SQLCODE-SILENT and SQLCODE-CHECK are deleted; sql-patterns leaves the targeted eval and its stale baseline row goes.
- **FR-019**: The sql-patterns §§3, 5, 9 fixes and the -114 fact land after run 1 is measured, each with a live test and a wording test, and are listed in 127's fact-fix table.
- **FR-020**: The leftover `IrisDevTmp.IrisDevRun*` classes and `^Test130Err.*` globals are removed from iris-dev-iris after the leak fix lands.
- **FR-021**: `iris_macro` with no `includes` still answers when an include in the namespace does not compile. Atelier fails the whole lookup for one such include, so the handler drops the includes that fail and names them: `skipped_includes` on a hit, and the `MACRO_NOT_FOUND` text on a miss.
- **FR-022**: A skill-eval run is valid when no more than one item in ten went unscored across the whole run, as 118's scoring contract states. A skill over that share on its own, or with nothing scored, gets no comparison and is left out of the baseline write; it does not void the other skills. The shard-merge `--update-baseline` applies the same rule, and it used to write every measured result with no check at all.
- **FR-023**: A graded session leaves no class behind. After the fixture goes on, the runner lists the classes under each fixture's top-level package; after the check it lists them again and deletes every class the session or the check created. Classes that earlier sessions left in BENCHMARK under those packages are deleted once. A leftover class had misled two SKILL-09 skill-arm sessions: `Bench.Q2.CountOther`, written on 2026-09-27 by a session that read the method name as a class name, was read as a finished answer by 2026-09-27 r2 and 2026-09-29 r1, and each stopped after 3 calls. The listing is per package, because `iris_doc list` refuses a bare wildcard, so a class a session writes outside the fixture's top-level packages is not deleted.

## Success Criteria

- **SC-001**: Every wrong claim listed in research.md is gone from the skills, and a test guards each one.
- **SC-002**: Every new ladder task goes from fail to pass on iris-dev-iris.
- **SC-003**: The unit, Rust live and Python offline suites pass.
- **SC-004**: One billable content-descriptions run and one 128 drift re-measure together cost $3 or less.
- **SC-005**: Round 2 costs $3 or less: $1.50 for the 18-session re-run and about $0.50 per replacement holdout task.
- **SC-006**: After round 4, USER on iris-dev-iris holds no `IrisDevTmp.IrisDevRun*` class, and `iris_info what=documents inline=true` there returns under the ceiling.
- **SC-007**: Round 4 costs about $3.50: $3 for the re-baseline after the judge fix, cents for the probe re-run, and about $0.50 for the sql-patterns ladder run.
- **SC-008**: After a graded session, BENCHMARK holds no class under a fixture's top-level package that the session or the check created (FR-023).

## Assumptions

- The ladder is small: one to two tasks per skill. Lift figures come with wide intervals, and the report shows the interval.
- iad bugs found here (research.md R3, R6, R7) are drafted as notes, not fixed in 130 and not filed. Round 4 is the exception: the scratch-class leak, the `iris_info` size and the `iris_doc list` route are fixed here, because the re-baseline measures sessions that hit them.

## Clarifications

### Session 2026-09-28 (grill round 4, on `sql-patterns-review.md`)

- Q: Keep the missing table as the task's bug? → A: No. Real table; plant only the conflation of 100 with <0. SQLCODE-CHECK is retired.
- Q: Judge or deterministic check? → A: A deterministic live check, no judge.
- Q: How far do the judge caps go? → A: 8000 for every tool call's args and result, test first.
- Q: Order of runs? → A: Run 1 is the judge cap plus the task rewrite, then a full re-baseline (cost told first). Run 2 is the skill fix, then a sql-patterns ladder run.
- Q: Where does the task live? → A: On the ladder as SKILL-21, namespace BENCHMARK, with check and solution; the SQLCODE-SILENT id goes.
- Q: Train or holdout? → A: Train. SKILL-09 stays on the holdout as the test of whether the fix generalises.
- Q: What does the prompt say? → A: The caller contract (unknown MRN gives `""`, any SQL failure throws), never SQLCODE. Forced error by the -400 corrupt-row recipe.
- Q: Where are the tasks tracked? → A: Judge cap and SKILL-21 in 130's tasks; the §§3/5/9 fixes and the -114 fact in 127's table.
- Q: Fix the iad bugs the session hit? → A: Yes, now, test first, before the re-baseline.
- Q: How is `iris_info documents` bounded? → A: A ceiling `inline=true` does not lift, with `truncated`, the total and a filter hint.
- Q: The 78,183 leaked scratch classes? → A: Fix the leak, hide `IrisDevTmp.*` by default, keep the ceiling, purge the leftovers once the fix lands.
- Q: SKILL-21 fixture? → A: `Bench.Q21.Patient` (MRN, Name, index `MRNIdx`) and `Bench.Q21.Lookup.FindPatient`; seeded MRN001/MRN002, corrupt row 3 as MRN666.
- Q: The retired tasks' references? → A: Delete the two task files, drop sql-patterns from the targeted eval and its baseline row; test comments that tell the history stay.
- Q: Cleanup on iris-dev-iris? → A: Purge `IrisDevTmp.IrisDevRun*`, kill `^Test130Err.*`, keep `Test130.SqlCode`.
