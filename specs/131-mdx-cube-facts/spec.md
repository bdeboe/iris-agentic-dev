# Feature Specification: MDX cube facts, measured live

**Feature Branch**: `131-mdx-cube-facts`
**Created**: 2026-09-29
**Status**: Draft
**Input**: Follow-ups from the PR 142 review (iris-mdx skill, author asinay). Fix the `iris_info what=sa_schema` description and make a non-URL name fail legibly; build a small live BI cube fixture; measure every factual claim in the PR's `iris-mdx` SKILL.md against it; update the local review draft with the verdicts. Stacked on 130-content-skills. Test-first. Local commits only.

## Context

PR 142 adds an `iris-mdx` skill. Its HARD GATE tells the agent to call `iris_info with=sa_schema` before writing MDX. iad describes `what=sa_schema` as "returns SQL Analytics schema", and that is wrong. It calls Atelier `/saschema/<url>`, which returns the Studio Assist grammar for an XData namespace URL such as `http://www.intersystems.com/deepsee`. A cube name gets a 404 and an empty result. The skill's gate trusted iad's own mis-description (130 drafts #7).

The rest of the skill makes about twenty claims about MDX on IRIS. Its figures come from Samples-BI, which iris-dev-iris does not have. No claim has been checked against a live cube. 131 builds a cube small enough to reason about by hand, checks each claim against it, and gives each one a verdict. The review then quotes measurements instead of opinions.

## User Scenarios & Testing

### User Story 1 - `sa_schema` says what it is (Priority: P1)

An agent that reads the `iris_info` description or the `name` param doc learns that `sa_schema` takes an XData namespace URL and returns a Studio Assist grammar. An agent that passes a cube name gets an error that says so and points to the real discovery route.

**Independent Test**: `tools/list` over the binary shows the new description. A live `sa_schema` call with `http://www.intersystems.com/deepsee` returns the grammar, and a call with a cube name returns the legible error.

**Acceptance Scenarios**:

1. **Given** `tools/list`, **Then** the `iris_info` description no longer says "SQL Analytics", and it says `sa_schema` takes an XData namespace URL.
2. **Given** `what=sa_schema, name=http://www.intersystems.com/deepsee`, **When** it runs on iris-dev-iris, **Then** the result is a non-empty grammar.
3. **Given** `what=sa_schema, name=<cube name>` (or no name), **Then** the result is an error that names the parameter's form, gives the deepsee URL as an example, and names `%DeepSee.Utils` `%GetCubeList` / `%GetDimensionList` via `iris_execute` for cube discovery.
4. **Given** the error text, **Then** it names no skill (129 rule).

### User Story 2 - A cube anyone can rebuild (Priority: P1)

A test or a contributor can build a small BI cube in USER on iris-dev-iris from hand-written rows, query it, and drop it after, without Samples-BI.

**Independent Test**: The fixture builds, `%GetCubeList` lists it, a known MDX query returns the hand-computed count, and teardown leaves no fixture classes behind.

**Acceptance Scenarios**:

1. **Given** the fixture source (a persistent class and a cube definition, fixed rows), **When** it is loaded and built, **Then** `%GetCubeList` lists the cube and `%GetDimensionList` lists its dimensions.
2. **Given** the built cube, **When** `SELECT FROM <cube>` runs, **Then** the count equals the number of source rows.
3. **Given** teardown, **Then** no class under the fixture package is left in USER.

### User Story 3 - Every PR 142 claim has a measured verdict (Priority: P1)

A reviewer can read, for each factual claim in the PR's SKILL.md, what IRIS did on the fixture cube and a verdict: holds, false, reworded, or unmeasurable.

**Independent Test**: One live `#[ignore]` test per measurable claim asserts what IRIS actually does. `research.md` has one row per claim with its verdict and the test that backs it.

**Acceptance Scenarios**:

1. **Given** each measurable claim in the list under FR-006, **Then** a live test asserts the observed behaviour, whether or not it matches the claim.
2. **Given** the performance claims ("3–15× faster", "%-prefixed perform better") and the Samples-BI figures, **Then** they are marked unmeasurable with "cite or cut", with no test.

### User Story 4 - The review quotes the measurements (Priority: P2)

Tom has a local review draft for PR 142 that quotes each verdict and the test behind it, ready to post on his word.

**Independent Test**: The draft has one line per claim that matches `research.md`, and it is not posted.

**Acceptance Scenarios**:

1. **Given** `research.md`'s verdict table, **Then** the draft carries the same verdicts.
2. **Given** the draft, **Then** nothing is posted, pushed or commented until Tom says "post it".

### Edge Cases

- `sa_schema` with no `name` at all: same legible error as a cube name, not an empty result.
- A `name` that looks like a URL but that Atelier does not know: pass the 404 through with the same guidance, because iad cannot tell a typo in a URL from a URL with no grammar.
- The cube build fails (for example, no BI license on community): the fixture raises with IRIS's status text, and every claim test fails loudly rather than skipping.
- A claim test finds IRIS disagrees with the claim: the test asserts IRIS's behaviour and passes; the verdict is "false". A test never asserts the claim just because the claim says so.
- Leftover fixture from a killed run: setup drops the fixture package first, so a second run starts clean.

## Requirements

### Functional Requirements

- **FR-001**: The `iris_info` tool description MUST describe `what=sa_schema` as the Studio Assist grammar for an XData namespace URL, and MUST NOT say "SQL Analytics".
- **FR-002**: The `name` parameter doc MUST say that for `sa_schema` it is an XData namespace URL, and give `http://www.intersystems.com/deepsee` as the example.
- **FR-003**: A `sa_schema` call whose `name` is empty, or is not an `http://` or `https://` URL, MUST return an error without calling IRIS. The error says what the parameter takes and that cube discovery goes through `%DeepSee.Utils` `%GetCubeList` and `%GetDimensionList` via `iris_execute`.
- **FR-004**: A `sa_schema` call with a URL that IRIS answers with 404 or an empty body MUST return an error with the same guidance instead of an empty success.
- **FR-005**: A reusable fixture MUST build a BI cube in USER on iris-dev-iris from a fixed set of hand-written rows, with no Samples-BI dependency, and drop every class it created on teardown. Setup drops leftovers first.
- **FR-006**: A live `#[ignore]` test MUST exist for each measurable claim: discovery via `%GetCubeList`/`%GetDimensionList`; running MDX through `iris_execute` with `%DeepSee.ResultSet` and reading cells; a wrong hierarchy path; NON EMPTY; WHERE vs `%FILTER`; two `%FILTER` on one level; `WHERE {a,b}` vs `%OR`; `%MDX()` directly on an axis; `MEASURES.MEMBERS` and `%COUNT`; the implicit `%COUNT` column header on axis skipping; caption vs `&[key]` on an integer-keyed level; a duplicate caption; a measure on two axes; a cross-cube dimension reference; the error text for a nonexistent cube and a nonexistent measure; COUNT vs EXCLUDEEMPTY.
- **FR-007**: Each claim test MUST assert what IRIS returned on the fixture. Where that contradicts the claim, the test asserts IRIS and the verdict is "false".
- **FR-008**: `research.md` MUST have one row per claim: the claim as quoted, what IRIS did, the verdict (holds / false / reworded / unmeasurable), and the test name. Performance and Samples-BI claims get "unmeasurable — cite or cut".
- **FR-009**: The local review draft MUST be updated with the verdicts and MUST NOT be posted.
- **FR-010**: Every change MUST pass `cargo fmt --all -- --check`, `cargo clippy -- -D warnings` and the unit suite. The new live tests MUST pass serially against iris-dev-iris.

### Key Entities

- **Fixture cube**: a persistent source class with fixed rows, and a cube definition over it with at least one string-keyed level, one integer-keyed level, a level with two members that share a caption, a sum measure, and a measure with some empty values.
- **Claim**: a quoted line from the PR's SKILL.md, what IRIS did, a verdict, and a backing test.

## Success Criteria

### Measurable Outcomes

- **SC-001**: `tools/list` from the binary has no "SQL Analytics" text in `iris_info`, and a test fails if it comes back.
- **SC-002**: A cube name passed to `sa_schema` produces an error naming `%GetCubeList` in 100% of calls, with no IRIS request made.
- **SC-003**: Every measurable claim in FR-006 has a passing live test, and every claim has a row in `research.md`.
- **SC-004**: After the live suite, the fixture package holds zero classes in USER.
- **SC-005**: The review draft's verdicts match `research.md` row for row. Nothing was posted.

## Assumptions

- iris-dev-iris is `iris-community:2026.2` with `%DeepSee` available in USER. If a cube cannot be built there, that is a blocker and gets reported, not worked around.
- The claims are read from the PR 142 worktree at 7f9b71c. A later push to the PR is out of scope until re-reviewed.
- "Reworded" means the claim is right in substance but wrong in its stated mechanism or wording, and the review proposes the wording.

## Out of Scope

- Editing the `iris-mdx` skill text or anything on the contributor's branch.
- Adding an iad MDX tool. Discovery and queries go through `iris_execute`.
- Pushing, posting the review, commenting on PR 142, or closing anything.
- Performance measurement.
