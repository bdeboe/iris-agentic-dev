# Feature Specification: Skill fact fixes

**Feature Branch**: `127-skill-fact-fixes`
**Created**: 2026-09-26
**Status**: Draft
**Input**: Fix the confirmed factual errors and self-contradictions in the bundled skills, each reproduced live on iris-dev-iris before the edit. Anything that does not reproduce is dropped and recorded. No optimiser touches this spec.

## Context

The 2026-09-25 skills review (peer repos, Open Exchange, and a comparison with an internal skill pack) found twelve claims in iad's bundled skills that IRIS contradicts and three places where the skills contradict iad itself. One of them is dangerous: `iris-objectscript-eval` says flag `e` means "display errors only", but `e` is "delete extent". On IRIS 2026.2 it has no effect on `Load`, `LoadDir` or `Compile`, and wipes the rows when passed to `$system.OBJ.Delete` (reproduced live, see `research.md`). An agent that believes the skill and adds `e` to a delete-and-reload loses the data.

This spec is the first of four (127–130). The later three put skill descriptions and hint rules through a train/holdout optimisation loop in the manner of specs 120 and 121. This one does not. A fact is not something a reward can justify, so every change here is gated by a live test against IRIS and nothing else.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - An agent following a skill does not destroy data (Priority: P1)

A developer asks the agent to compile a class. The agent reads `iris-objectscript-eval` and picks compile flags from it. Today it is told `e` is harmless, and on a delete-and-reload the rows go. After this change the skill describes `e` correctly and warns against it.

**Why this priority**: This is the only item that loses data. It ships first even if the rest slips.

**Independent Test**: A live test loads and compiles a throwaway class with stored rows using the flags the skill recommends and asserts the rows survive. A second live test shows `$system.OBJ.Delete` with `e` deletes the extent and without `e` does not, so the warning stays true. A text test fails if the old "display errors only" wording returns.

**Acceptance Scenarios**:

1. **Given** a class with saved rows on iris-dev-iris, **When** it is compiled with the flag set the skill recommends, **Then** the row count is unchanged.
2. **Given** the skill text, **When** it is searched for the phrase that describes `e` as harmless, **Then** there is no match.

---

### User Story 2 - Skill claims about ObjectScript behaviour match IRIS (Priority: P1)

An agent writing ObjectScript follows the skills' WRONG/CORRECT examples. Today several of them are backwards: valid code is called an error, and code that fails at runtime is called a compile error or harmless. After this change every corrected claim is backed by a live test showing what IRIS actually does.

**Why this priority**: The skills are iad's teaching surface, and the project's north star is that every error is legible. A wrong claim teaches the wrong model of IRIS.

**Independent Test**: For each item, one live `#[ignore]` test runs the snippet on iris-dev-iris and asserts the corrected behaviour: compiles, fails with a named runtime error, or returns a named value. One unit test per item fails if the old wrong wording returns.

**Acceptance Scenarios**, one per error. Each is reproduced before its edit.

1. **Postconditional #5559** (`objectscript-loop-patterns`:82-86, `objectscript-fewshot-fixes`:196-207, `iris-sql`:170). **Given** `Quit:key=""` sharing a line with another command, **When** compiled and run, **Then** it compiles and runs. The skill states exactly which form does produce #5559 (the fewshot root cause blames the space before `=`, so the reproduction must separate the space from the line sharing) and drops the line-sharing claim.
2. **`Quit value` inside a loop** (`objectscript-tdd`, `objectscript-loop-patterns`). **Given** a method with `Quit 5` inside a `For` loop, **When** compiled and called, **Then** it compiles and fails at runtime with `<COMMAND>`. Inside `Try` it is a compile error. The skills say both.
3. **Routines** (`objectscript-mac-routines`:18,21). **Given** a `.mac` routine using `Try/Catch` and `Return`, **When** compiled and called, **Then** it compiles and runs correctly. Neither is listed as wrong.
4. **List patterns §1** (`objectscript-list-patterns`). **Given** the section's WRONG and CORRECT blocks, **When** compared, **Then** they differ, and each behaves on IRIS as labelled. Timed live, the label is backwards: `Set lst=lst_$LB(x)` is linear and `Set $LIST(lst,*+1)=x` is quadratic. The fix says so.
5. **SQL naming** (`objectscript-sql-patterns` §§2, 4, 5, 9). **Given** the skill's own table-naming rule, **When** every SQL example is checked against it, **Then** none breaks it, and the corrected examples run.
6. **`%Execute` arguments** (`iris-sql`:405-450). **Given** `stmt.%Execute(args...)` with a multi-value array, **When** run, **Then** it returns rows and raises no `<STACK>`. The IN-list string concatenation workaround is removed because it invites SQL injection.
7. **`New`** (`objectscript-review`:25). **Given** `new $namespace` in a method, **When** compiled, **Then** it compiles and restores the namespace on exit, while `new x` fails with #1038. The rule is narrowed to plain variables.
8. **`TROLLBACK`** (`objectscript-guardrails`:58, `objectscript-review`:24). **Given** a caller inside `TSTART` calling a method that runs bare `TROLLBACK`, **When** it returns, **Then** `$TLEVEL` is 0 and the caller's transaction is gone. The skills recommend recording `$TLEVEL` on entry and rolling back only to it.
9. **Embedded Python method names** (`iris-embedded-python`:31). **Given** `pyobj.my_function(42)`, **When** run, **Then** it fails because `_` is the concatenation operator: IRIS asks Python for attribute `my`, and the error is `<NOLINE>` wrapping `AttributeError`. The skill shows the quoted form `pyobj."my_function"(42)`. Embedded Python on iris-dev-iris is broken (wrong results, then a segfault that poisons the routine cache), so the quoted form is stated as documented, not verified, and the live test covers the unquoted failure only, parsed without calling Python if possible.
10. **Production restart** (`ensemble-production`:82, 347, and "Restarting a production" at 244). **Given** a running production with a recompiled business host, **When** the skill's advice is followed, **Then** it chooses between a hot update, restarting the one host, and a controlled stop, and says a stop re-delivers in-flight messages. The blanket "never restart" is gone.

---

### User Story 3 - The skills stop contradicting the server (Priority: P2)

An agent reads the server instruction ("`iris_compile` never reads local files") and then a skill that passes `iris_compile` a local path. It follows one and the change never reaches IRIS. After this change the skills agree with the server and with each other.

**Why this priority**: Contradictions make the agent choose, and it chooses wrong about half the time. They are text-only fixes, so they are cheap.

**Independent Test**: A unit test scans every bundled skill for `iris_compile` calls with a local file path and fails on any. The same test checks that `ensemble-production` has no Storage-block edit and no `iris_execute` step presented as a way around a tool refusal, and that `iris-docs` no longer both forbids and uses a DocBook curl.

**Acceptance Scenarios**:

1. **Given** `objectscript-tdd`, `objectscript-repair`, `iris-objectscript-eval` and `objectscript-mac-routines`, **When** they compile, **Then** they push with `iris_doc(mode="put", compile=true)` or compile a server-side name, never a local path. (`iris_compile` does upload a local path over HTTP but not on `docker_only`, so the path form is not portable. The server instruction's "never reads local files" is itself wrong for HTTP; that is a follow-up outside 127–130.) `iris_compile(target="*.cls")` is described as a namespace-wide server wildcard, not a workspace compile.
2. **Given** `ensemble-production`:377-407 and :448-457, **When** read, **Then** there is no Storage edit (guardrails:59 forbids it), #5477 is described as the compile error it is, the false 31-character global-name limit is gone, and no step routes around a refusal through `iris_execute`. `specs/123-demo-gap-fixes/followups.md` item (d) gets a line pointing at this case.
3. **Given** `iris-docs`, **When** read, **Then** its DocBook guidance is one consistent rule that matches what the re-scrape recipe does and what was verified live.

---

### User Story 4 - The vendored aihub-eap skill matches upstream (Priority: P3)

`aihub-eap` is vendored. The copy has drifted (`@{env.}` against `@{env:}`, `grok` against `xai`), its lock hash matches neither version, and line 145 has an operator-precedence bug.

**Why this priority**: It is vendored content with an owner outside this repo. The fix is re-syncing, not rewriting.

**Independent Test**: A unit test recomputes the lock hash from the vendored file and compares it with the lock entry.

**Acceptance Scenarios**:

1. **Given** the upstream source, **When** the vendored copy is re-synced, **Then** its content equals upstream and the lock hash matches it.
2. **Given** upstream still has the line-145 bug, **When** re-synced, **Then** iad carries a marked local patch recorded in the lock, and a note to the AI Hub owner is drafted under `.iad-local/`, not sent. If upstream has fixed it, no patch is made.

### Edge Cases

- **A claim does not reproduce.** It is not edited. The item goes in `specs/127-skill-fact-fixes/dropped.md` with the snippet, IRIS version and observed result.
- **Behaviour differs across IRIS versions.** The corrected text names the version it was verified on (`IRIS 2026.2`, iris-dev-iris). A claim that is only true on some versions says so.
- **Doc-only claims.** TROLLBACK and production restart were taken from documentation, not tested. They get a live test here, and if a live test is impractical (restart needs a production), the test sets up a minimal production and tears it down.
- **Live test cleanup.** Every live test uses throwaway class/global/production names under a `Test127` package and removes them in a finally-equivalent. The extent test never runs outside that package.
- **Same error in more than one skill.** One test per claim covers every file that makes it. The wording test lists every file.
- **The old wrong wording in a WRONG example.** The unit test matches the claim, not the snippet. A WRONG block that shows `Quit:key=""` is fine if it no longer says line sharing is the cause.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Before any skill text changes for an item, a live test MUST reproduce the corrected behaviour on iris-dev-iris. An item whose correction does not reproduce MUST NOT be edited and MUST be recorded in `dropped.md`.
- **FR-002**: `iris-objectscript-eval` MUST describe compile flag `e` as deleting the extent and MUST NOT recommend it. This item MUST land in its own commit, before the rest.
- **FR-003**: Each of the ten claims in User Story 2 MUST be corrected in every bundled skill that makes it.
- **FR-004**: Every correction MUST have one live `#[ignore]` test against iris-dev-iris asserting the corrected behaviour, and one unit test that fails if the old wrong wording returns.
- **FR-005**: No bundled skill MUST pass a local file path to `iris_compile`. A unit test MUST enforce this across all skills.
- **FR-006**: `ensemble-production` MUST NOT edit a Storage block or present `iris_execute` as a way around a tool refusal. `specs/123-demo-gap-fixes/followups.md` item (d) MUST reference it.
- **FR-007**: `iris-docs` MUST give one DocBook rule that agrees with its own recipe.
- **FR-008**: The vendored `aihub-eap` MUST equal upstream plus at most one recorded local patch, and its lock hash MUST match the vendored file. A unit test MUST recompute the hash.
- **FR-009**: Corrected claims MUST name the IRIS version they were verified on.
- **FR-010**: No text from the internal Server Manager skill pack MAY be copied. All wording MUST be iad's own. Nothing HealthShare-specific MAY be added.
- **FR-011**: The skills' pass rates and benchmark fields MUST NOT be touched. That is spec 128's job.
- **FR-012**: The changes MUST land as local commits on `127-skill-fact-fixes`. Nothing is pushed, tagged or posted.

### Key Entities

- **Claim**: a statement in a skill about IRIS behaviour. It has the files and lines that make it, the snippet that tests it, the observed result, and a status of fixed or dropped.
- **Dropped item**: a claim whose correction did not reproduce, with snippet, IRIS version and observed output.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: All 16 items (13 errors, 3 contradictions; the 13th, ensemble-production's false 31-character global limit, was found during reproduction) end as either fixed with a passing live test or dropped with a recorded reproduction. None is unaccounted for.
- **SC-002**: Following any bundled skill's compile advice on a class with data leaves the row count unchanged.
- **SC-003**: No bundled skill passes a local path to `iris_compile`, checked across every skill file.
- **SC-004**: Reintroducing any removed wrong claim fails at least one test.
- **SC-005**: The full unit suite and the 127 live tests pass with `--test-threads=1` against iris-dev-iris.

## Assumptions

- iris-dev-iris (IRIS community 2026.2, Atelier on 52780) is the only test target. Live tests use an explicit `.iris-agentic-dev.toml` pointing at it.
- Live tests go in the core `integration` aggregate and text tests in `unit`, each with its `mod` line.
- The aihub-eap upstream is reachable read-only. If it is not, User Story 4 is recorded as blocked and the rest ships.
- Line numbers are from master at `b780ac0` and may shift. Each fix is found by content, not line.
- This ships in the next release with 122–126.
