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

### Edge Cases

- A ladder check that starts a production must stop it, even when the check fails.
- If `%BuildIndices` has already run, the index-backfill fixture must reset its state, or "before" passes.
- Content prompts are author-written, and the README says so. Two blind labelling passes decide each item's expected skill.

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

## Success Criteria

- **SC-001**: Every wrong claim listed in research.md is gone from the skills, and a test guards each one.
- **SC-002**: Every new ladder task goes from fail to pass on iris-dev-iris.
- **SC-003**: The unit, Rust live and Python offline suites pass.
- **SC-004**: One billable content-descriptions run and one 128 drift re-measure together cost $3 or less.
- **SC-005**: Round 2 costs $3 or less: $1.50 for the 18-session re-run and about $0.50 per replacement holdout task.

## Assumptions

- The ladder is small: one to two tasks per skill. Lift figures come with wide intervals, and the report shows the interval.
- iad bugs found here (research.md R3, R6, R7) are drafted as notes, not fixed in 130 and not filed.
