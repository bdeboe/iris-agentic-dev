# Feature Specification: Hints on tool results, with a skill reference and a loop surface

**Feature Branch**: `129-tool-result-hints`
**Created**: 2026-09-26
**Status**: Draft
**Input**: 127–130 loop design (grill, 2026-09-26): "hints on tool results: rule-based, each hint is a text line plus a `hint_ref {skill, section, why}` field, extending spec 125's `hint`. If the coding pack is off, the text stays and the skill reference is dropped. The replay corpus is generated live from bad snippets on iris-dev-iris, with a regeneration `#[ignore]` test, plus mined errors. The loop gets the `--surface hints` value." Reward: skill reach plus task pass.

## Context

Spec 125 added a `hint` string to two IRIS errors: SQLCODE -12 at a lone `$`, and `<CLASS DOES NOT EXIST>` for a %SYS-only class. Both rules are Rust string literals that end in `Skill X, "heading".` Three things are missing:

1. An agent cannot tell the skill reference from the advice, so it cannot load the skill without parsing prose.
2. Two rules cover a small share of what agents hit. Tom's own Claude Code session logs hold 148 SQLCODE -30 errors. Some are %SYS-only tables queried from USER (`SECURITY.USERS`, `SECURITY.AUDIT`, `CONFIG.NAMESPACES`). Others are three-level class names cut to two (`CLASS.DEFINITION`, `SUB.DEEP`). The logs also show reserved words used as identifiers (`MODULE`, `FOUND`) and SQLite `INSERT OR IGNORE`.
3. The hint wording is fixed by hand, and nothing measures whether an agent follows it.

Two premises from the grill do not match the code:

- **No "coding pack" switch exists.** Bundled skills are compiled into the binary and are always there. 129 adds the switch the design assumed, as the `IAD_CODING_PACK` environment variable, rather than building the opt-in pack.
- **Only 2 rules exist**, so the loop has little to optimise until more rules land. 129 adds five, for seven in all.

## User Scenarios & Testing

### User Story 1 - The hint names its skill in a field (Priority: P1)

An agent's query fails with a known IRIS error. The result carries `hint` (what to do) and `hint_ref {skill, section, why}`, so the agent can call `skill describe` on the named skill without reading the prose.

**Independent Test**: Run a known-bad query through the binary against iris-dev-iris. The response has `hint` and `hint_ref`, and `hint_ref.section` is a heading in `hint_ref.skill`'s SKILL.md.

**Acceptance Scenarios**:

1. **Given** `SELECT TOP 1 Name FROM Security.Users` in USER, **When** `iris_query` runs it, **Then** the error carries a `hint` saying the table lives in %SYS, and a `hint_ref` whose skill is `iris-agentic-dev`.
2. **Given** `IAD_CODING_PACK=off`, **When** the same query runs, **Then** `hint` is unchanged and `hint_ref` is absent.
3. **Given** an error that no rule matches, **When** it is returned, **Then** it carries neither field.
4. **Given** the hint text of any rule, **Then** it names no skill. The reference lives only in `hint_ref`, so turning the pack off really drops it.

### User Story 2 - More of the errors agents actually hit get a hint (Priority: P1)

Each new rule was reproduced on iris-dev-iris first. The mined session logs show that each of these errors really occurs.

**Independent Test**: The replay corpus, a fixture of live-captured errors, runs through the matchers offline. Each positive item gets its rule and each negative gets none.

**Acceptance Scenarios**:

1. SQLCODE -30 for a `Security.`/`Config.`/`SYS.` table outside %SYS → rerun in `%SYS`.
2. SQLCODE -30 where the query names `A.B.C` and IRIS reports `'B.C'` → the table is `A_B.C`.
3. SQLCODE -29 for a field whose name the query wrote in double quotes → double quotes delimit identifiers in IRIS SQL; use single quotes for strings.
4. SQLCODE -1 "reserved word X found" → X is reserved; quote it as `"X"` or rename.
5. SQLCODE -1 at `INSERT OR IGNORE`, or -30 for `SQLUSER.IGNORE` after `INSERT IGNORE` → IRIS has no such form; see the skill's duplicate-handling options.
6. The two spec 125 rules still fire as before.

### User Story 3 - The loop can tune hint wording (Priority: P2)

`python -m tests.e2e.skill_eval.optimize run --surface hints` runs gepa on the wording of each rule's hint. The matchers, the rule set and the cited sections are fixed. The scorer, Haiku 4.5, sees the failed call, the error, the hint and the skill menu. It replies with the skill it would load and a fixed call.

- **Skill reach**: the picked skill is the `hint_ref` skill.
- **Task pass**: the fixed SQL prepares cleanly on iris-dev-iris through `%SQL.Statement.%Prepare`, which parses and plans without executing. A fixed runtime call runs cleanly through `iris_execute`.

The item score is the mean of the two. Holdout, validator, budget and verdict work as in 128.

**Independent Test**: Offline tests drive the real loop with a scripted scorer and a scripted live runner. A candidate that adds a fact absent from the cited section is rejected before scoring. A holdout item cannot reach the train scorer.

**Acceptance Scenarios**:

1. **Given** a candidate hint that drops a `{placeholder}` or names a skill, **Then** the validator rejects it.
2. **Given** a finished run, **Then** the run directory has the seed and candidate holdout figures for reach, pass and score, plus the verdict and the ledger.
3. **Given** a SHIP verdict, **When** `apply` runs, **Then** only the `text` values in `hints.toml` change.

### Edge Cases

- A query in `%SYS` that fails with -30 on `Security.X` gets no %SYS hint. The table really is missing.
- `%SYS.*` and `%Dictionary.*` names resolve everywhere and get no %SYS hint.
- A -29 whose field is not double-quoted in the query gets no hint. Most -29s are real typos.
- EXPLAIN wraps errors as `SQLCODE: -482 ... SQLCODE = -30 : ...`. The matchers read the inner code.
- A fixed runtime call that contains a write verb (`Kill`, `Set ^`, `%Save`, `%Delete`, `Delete`, `Create`, `Modify`) is not run. It counts as a fail.

## Requirements

### Functional Requirements

- **FR-001**: A matched error MUST carry `hint` (string) and `hint_ref` (`{skill, section, why}`). `section` MUST be an exact heading of `skill`'s SKILL.md, checked by a test.
- **FR-002**: `IAD_CODING_PACK=off` (also `0`, `false`, `no`) MUST drop `hint_ref` and leave `hint` unchanged.
- **FR-003**: Hint text MUST NOT name a bundled skill.
- **FR-004**: Rule wording (`text`, `why`, `skill`, `section`) MUST live in one data file, `hints.toml`, compiled in with `include_str!`. Matching MUST stay in Rust. A rule id in the file without a matcher, or a matcher without a row, MUST fail a test.
- **FR-005**: Every rule MUST be reproduced live on iris-dev-iris, with evidence in `research.md`. Its error text MUST come from a live capture.
- **FR-006**: The replay corpus MUST be a committed fixture of live-captured tool results, positives and negatives, each labelled with its expected rule or none. An `#[ignore]` test MUST regenerate it from its bad snippets and fail if any capture no longer matches its label. A unit test MUST run every fixture through the matchers offline.
- **FR-007**: Mined errors from past sessions MAY be added as matcher fixtures, labelled `source = "mined"`. They count for matcher tests only, never for loop scoring, because their original calls cannot be replayed.
- **FR-008**: `--surface hints` MUST exist. Its components are the rule `text` values. Its validator MUST require the same `{placeholders}` as the seed, forbid skill names, cap text at 400 characters, and allow no identifier-like fact absent from the cited section and the seed text.
- **FR-009**: The hints loop MUST use a frozen 60/40 hash split of the replay corpus's positive items, the ledger and budget, and the 128 verdict shape. The gates are: the paired score difference's lower bound above 0, reach not down, pass not down, and the live ladder within 0.05. With no ladder run, the verdict is HOLD.
- **FR-010**: Task pass MUST never execute a fixed SQL statement. It prepares it only. A fixed runtime call MUST NOT run if it contains a write verb.

### Key Entities

- **Rule**: an id, the skill and section it cites, `why` (one line on why that section applies), and a `text` template with `{placeholders}` filled from the match.
- **Replay item**: an id, the tool, the arguments, the namespace, the captured error, the expected rule or `none`, and a source (`live` or `mined`).

## Success Criteria

- **SC-001**: All 7 rules fire on their live captures, and no rule fires on any negative capture.
- **SC-002**: Turning the pack off drops `hint_ref` on every rule.
- **SC-003**: One budgeted `--surface hints` run completes and writes a verdict. Its figures come from holdout items only.

## Assumptions

- The live ladder for hints is out of scope, as it was for 128. A missing ladder is a HOLD, not a pass.
- `IAD_CODING_PACK` is read per call, like other `IAD_*` switches. A TOML key can follow once an opt-in pack exists.
- iris-dev-iris USER is the only namespace used, apart from %SYS for the sys-only rules.
- Out of scope: BM25 skill search, the exact-name shortcut, potion (follow-ups from the grill), hints on `iris_compile`, and F1 (the docker exec path reports runtime errors as success).
