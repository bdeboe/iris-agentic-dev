# Feature Specification: AI Hub support for EAP build 139

**Feature Branch**: `132-aihub-139`
**Created**: 2026-09-30
**Status**: Draft
**Input**: Beef up iad's AI Hub support for the current EAP build IRISHealth-2026.3.0AI.139.0. The skill must know where the ai-hub-eap repository is and how to read its docs; the build decides names and signatures; the skill-vs-tool mix is decided by ladder evidence. Decisions Q1–Q10 from the 2026-09-29 design interview. Stacked on 131-mdx-cube-facts. Test-first. Local commits only.

## Context

iad ships two AI Hub skills. `aihub-eap` (711 lines) is a vendored copy of the skill in the public repo `github.com/intersystems-community/ai-hub-eap`, pinned by a test to upstream commit `72f9046` plus one local patch. It says the current build is 2026.2.0AI.162.0. `iris-ai-hub` (255 lines) is iad's own. Neither tells an agent where the upstream docs live or how to read them, and neither has been checked against the 2026.3 line.

The EAP build is now 2026.3.0AI.139.0. The upstream repo still describes the 2026.2 line, so some class names, signatures or parameters may have moved. iad already has the tools to read the truth off an instance (`iris_info`, `docs_introspect`, `iris_symbols`). What is missing is a skill that sends the agent to the docs for concepts and to the build for facts, a 139 instance that tests can reach, and evidence about whether any step needs a tool rather than more skill text.

## Decisions (design interview, 2026-09-29)

| #   | Decision                                                                                                                                                                                                                     |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Q1  | The skill names `github.com/intersystems-community/ai-hub-eap` (branch `master`) as the doc source and tells the agent to check its current state.                                                                           |
| Q2  | The skill carries a topic → file map. The agent fetches the raw file itself. No new iad code for docs.                                                                                                                       |
| Q3  | The build wins. Workflow: build version first, then the installed `%AI` classes. Docs give concepts; installed classes decide names and signatures; the agent reports disagreement.                                          |
| Q4  | A new iad-owned container `iad-aihub-iris` from the 139 image, with its own ports and its own registry entry. `iris-dev-iris` stays on 2026.2.                                                                               |
| Q5  | One skill. `iris-ai-hub` is rewritten as iad's single AI Hub skill. The vendored `aihub-eap` and its pin test go. Upstream's own skill stays installable through `skill_community`.                                          |
| Q6  | Structure tests on every live run. One real agent turn only when `IAD_AIHUB_LLM=1` and `OPENAI_API_KEY` are set, on a cheap OpenAI model, asserting a tool was called.                                                       |
| Q7  | About four AI Hub ladder tasks, tools vs tools+skill arms, 3 repeats, train/holdout split. Skill fails, tools passes → skill edit. Both fail the same step on ≥2 of 3 repeats and the failure is mechanical (FR-016) → tool. |
| Q8  | Each doc mismatch with 139 goes into `drafts.md` with doc file and line, what 139 does, and the test that shows it. The skill carries the correction. Upstream text is drafted, never filed without Tom's words.             |
| Q9  | Mine the five `ready-hackathon-dev-template` ai-hub skills (Gabriel Ing). A claim enters the skill only if a live test on 139 holds it; Gabriel is credited. OAuth2 is a later spec.                                         |
| Q10 | Spec 132, stacked on 131-mdx-cube-facts, so the ladder runs on the 130 harness fixes.                                                                                                                                        |

## Clarifications

### Session 2026-09-30

- Q: Where does the real-turn test get its provider key? → A: From `OPENAI_API_KEY` in the environment; the test writes it into ConfigStore, runs the turn, and deletes the entry after.
- Q: Where does the topic-map check look for upstream files? → A: A recorded upstream file list in the repo; a unit test checks the map against it offline, an `#[ignore]` test checks the list against GitHub.
- Q: What counts as a "mechanical" failure in FR-016? → A: The agent chose the right approach and the tools stopped it: more than 10 tool calls on the step without finishing, or a tool error no call argument could avoid. A wrong class, method or signature is a knowledge failure and goes to the skill.
- Q: How do the four ladder tasks split between train and holdout? → A: 2/2. Train: agent with one tool, ConfigStore provider. Holdout: MCP server definition, broken `%OnInit` provider. Skill edits draw only on train failures; holdout labels are frozen.
- Q: How is the "agent with one tool" ladder task graded? → A: Structurally, with no LLM call: the class compiles on 139, subclasses the right `%AI` agent class, and registers exactly one tool, read from installed class metadata.

## User Scenarios & Testing

### User Story 1 - A 139 instance the tests can reach (Priority: P1)

A test or a contributor can start `iad-aihub-iris` from the 139 image, reach it on fixed ports, and know from the container registry that it belongs to iad. `iris-dev-iris` is untouched.

**Independent Test**: The container starts, reports version 2026.3.0AI.139.0, and the registry verifier accepts iad's entry.

**Acceptance Scenarios**:

1. **Given** the 139 image, **When** the container starts, **Then** the instance reports build 2026.3.0AI.139.0 and has the `%AI` package.
2. **Given** the registry file, **Then** it has an entry for `iad-aihub-iris` whose project is this repo, with ports that no other entry claims, and the verifier passes.
3. **Given** the container is not running, **Then** every AI Hub live test skips with a message naming the container, and none fails.

### User Story 2 - One skill that knows where the docs are (Priority: P1)

An agent loading iad's AI Hub skill learns where the upstream docs are, which file covers which topic, and that the installed build decides names and signatures. It checks the build before writing any AI Hub code.

**Independent Test**: The bundled skill set has one AI Hub skill. Its text has the repo URL, every map entry names a file that exists upstream, and the workflow starts with the build version and the `%AI` classes.

**Acceptance Scenarios**:

1. **Given** the bundled skills, **Then** `iris-ai-hub` is present and `aihub-eap` is not, and every place that listed `aihub-eap` (manifest, docs, catalogue, tests) agrees.
2. **Given** the skill text, **Then** it names the repo and branch, and maps ConfigStore, MCP, SDK (guide, advanced, examples), LangChain and samples to their files.
3. **Given** each file in the map, **Then** a unit test finds it on the recorded upstream file list, and an `#[ignore]` test finds each listed file on GitHub.
4. **Given** the skill text, **Then** its first workflow step reads the build version, the second reads the installed `%AI` classes, and it tells the agent to trust the classes over the docs and say so when they differ.
5. **Given** a user who wants upstream's own skill, **Then** the skill says it can be installed with `skill_community`.

### User Story 3 - Every claim in the skill holds on 139 (Priority: P1)

Every factual claim in the rewritten skill (class names, method names, signatures, ConfigStore behaviour, MCP server registration, pitfalls) is backed by a live test on `iad-aihub-iris`. This includes claims taken from the upstream docs and from Gabriel Ing's hackathon skills.

**Independent Test**: Each claim row in `research.md` names a live test; each test passes on 139; a claim with no passing test is not in the skill.

**Acceptance Scenarios**:

1. **Given** each `%AI` class and method the skill names, **Then** a live test finds it on 139.
2. **Given** the skill's sample agent class, **When** it is loaded and compiled on 139, **Then** it compiles clean.
3. **Given** a ConfigStore entry written the way the skill says, **Then** it reads back with the same values, and the test removes it after.
4. **Given** an MCP server definition registered the way the skill says, **Then** it is listed afterwards, and the test removes it after.
5. **Given** `IAD_AIHUB_LLM=1` and `OPENAI_API_KEY` in the environment, **When** the test writes the key into ConfigStore and the sample agent runs one turn on a cheap OpenAI model, **Then** the transcript shows a tool call, and afterwards the ConfigStore entry is gone. Without either variable, the test skips.
6. **Given** each claim mined from the five hackathon skills, **Then** it is either in the skill with a passing test and credit to Gabriel, or listed in `research.md` as not taken with the reason.

### User Story 4 - Doc mismatches are recorded and ready for upstream (Priority: P2)

When 139 disagrees with the ai-hub-eap docs, Tom has a record of each mismatch and draft text for upstream, and agents already get the correction.

**Independent Test**: `drafts.md` has one entry per mismatch, each with the doc file and line, what 139 does, and the test that shows it; the skill states the correction.

**Acceptance Scenarios**:

1. **Given** a live test that shows 139 behaving differently from a doc, **Then** `drafts.md` has an entry with the doc file and line, the observed behaviour and the test name.
2. **Given** that entry, **Then** the skill says "the guide says X; on 2026.3 it is Y".
3. **Given** the drafts, **Then** nothing is filed, pushed or commented upstream until Tom says "file it".

### User Story 5 - Ladder evidence decides skill vs tool (Priority: P2)

Tom can see, for each AI Hub ladder task, how the tools arm and the tools+skill arm did on 139, and whether any step calls for a new tool.

**Independent Test**: A ladder run over the AI Hub tasks produces per-arm results, the `needs_fix` flag, and a per-step failure tally; `research.md` records the decision for each task.

**Acceptance Scenarios**:

1. **Given** the four tasks (agent with one tool; ConfigStore provider; MCP server definition; broken `%OnInit` provider), **Then** each has a checkable end state on 139; the agent and ConfigStore tasks are labelled train and the MCP and `%OnInit` tasks holdout.
2. **Given** 3 repeats per arm, **When** the skill arm fails and the tools arm passes on ≥2 scored repeats, **Then** the skill is flagged for an edit.
3. **Given** both arms fail at the same step on ≥2 of 3 repeats, **When** in each failed repeat the agent chose the right approach and either spent more than 10 tool calls on the step without finishing or hit a tool error no call argument could avoid, **Then** `research.md` records a tool proposal for that step. A failure from a wrong class, method or signature is a knowledge failure: it goes to the skill, and no tool is proposed.
4. **Given** the run, **Then** each graded session removes the classes and ConfigStore entries it created.

### Edge Cases

- The 139 image needs a license key and will not start: work stops and Tom is told; no workaround with another project's container.
- The pulled image is x64 only: record it; run under emulation only if the instance starts and tests pass, and note it in `research.md`.
- The upstream repo moves a file in the map: the existence test fails and names the file.
- The upstream repo is unreachable from an agent session: the skill tells the agent to fall back to the installed classes, which need no network.
- A `%AI` class exists but a method the docs name does not: that is a mismatch (US4), not a test failure to hide.
- The real agent turn returns text with no tool call: the test fails; the skill does not claim the pattern works.
- A ladder session leaves classes or ConfigStore entries behind: the next session's result is void until cleanup runs (130 FR-023 pattern).

## Requirements

### Functional Requirements

- **FR-001**: An iad-owned instance `iad-aihub-iris` MUST run the 2026.3.0AI.139.0 image on ports no other registered container claims, with its own entry in the machine-wide container registry.
- **FR-002**: `iris-dev-iris` MUST stay on its current build; no existing test changes target.
- **FR-003**: Every AI Hub live test MUST skip, not fail, when `iad-aihub-iris` is not reachable, and say which container it wanted.
- **FR-004**: iad MUST bundle exactly one AI Hub skill, `iris-ai-hub`; `aihub-eap` MUST be removed from the bundle, manifest, docs, catalogue and tests, including the upstream pin check.
- **FR-005**: The skill MUST name the upstream repo URL and branch and carry a topic → file map covering ConfigStore, MCP (guide and examples), SDK (guide, advanced, examples), LangChain and the samples directory.
- **FR-006**: The repo MUST hold a recorded list of upstream files with the upstream commit it was taken at. A unit test (no network, runs in CI) MUST fail if any file in the skill's map is missing from that list; an `#[ignore]` live test MUST fail if any file on the list is missing from the upstream repo on GitHub.
- **FR-007**: The skill's workflow MUST start by reading the build version, then the installed `%AI` classes, and MUST tell the agent that installed classes win over the docs and that it should report any disagreement.
- **FR-008**: The skill MUST say that upstream's own skill can be installed with `skill_community`.
- **FR-009**: Every factual claim in the skill MUST have a live test on 139 recorded in `research.md`; a claim without a passing test MUST NOT be in the skill.
- **FR-010**: Structure tests MUST cover: the named `%AI` classes and methods exist; the sample agent class compiles; a ConfigStore entry saves and reads back; an MCP server definition registers. Each test MUST remove what it created.
- **FR-011**: A real-turn test MUST run only when `IAD_AIHUB_LLM=1` and `OPENAI_API_KEY` are set. It MUST write the key into ConfigStore from the environment, use a cheap OpenAI model, assert that a tool was called rather than on response text, and delete the ConfigStore entry afterwards, pass or fail. The key MUST NOT be written to the repo, test output or logs.
- **FR-012**: Each mismatch between the ai-hub-eap docs and 139 MUST be recorded in `drafts.md` with doc file and line, observed behaviour and the test name, and the skill MUST state the correction.
- **FR-013**: Upstream issue or PR text MAY be drafted; nothing MUST be filed, pushed or commented without Tom's explicit words.
- **FR-014**: Every claim in the five hackathon ai-hub skills MUST be listed in `research.md` as taken (with test) or not taken (with reason); taken claims MUST credit Gabriel Ing.
- **FR-015**: Four AI Hub ladder tasks MUST exist with checkable end states on 139, runnable on both arms with 3 repeats. Train: agent with one tool, ConfigStore provider. Holdout: MCP server definition, broken `%OnInit` provider. Holdout labels MUST NOT change during the spec, and a skill edit MUST cite only train-task failures. Every end-state check MUST be structural (compile status, class metadata, ConfigStore or MCP registry contents) and MUST NOT call an LLM; a graded session needs no provider key.
- **FR-016**: A new tool MUST be proposed only for a step both arms fail on ≥2 of 3 repeats where the failure is mechanical in each failed repeat. Mechanical means the agent chose the right approach and then either spent more than 10 tool calls on the step without finishing or hit a tool error no call argument could avoid. A wrong class, method or signature is a knowledge failure and MUST go to the skill instead. `research.md` MUST record the decision per task, citing the transcript lines.
- **FR-017**: Each graded ladder session MUST remove the classes and ConfigStore entries it created.

### Key Entities

- **iad-aihub-iris**: the 139 instance iad owns for AI Hub tests; build, ports, registry entry.
- **Topic map**: topic → upstream file path.
- **Upstream file list**: the upstream files and the commit they were recorded at; kept in the repo; the map is checked against it offline, and it is checked against GitHub live.
- **Claim**: a factual statement in the skill; source (upstream doc, hackathon skill, own measurement), verdict, backing test, credit.
- **Mismatch**: doc file and line, what 139 does, test name, draft upstream text.
- **Ladder task**: prompt, fixture, end-state check, train/holdout label, per-arm results, decision (skill edit, tool, none).

## Success Criteria

### Measurable Outcomes

- **SC-001**: One AI Hub skill ships; a search of the repo finds no remaining reference to `aihub-eap` outside history and this spec.
- **SC-002**: 100% of map entries point at files that exist upstream at the recorded commit.
- **SC-003**: 100% of factual claims in the skill have a passing live test on 139.
- **SC-004**: Every doc mismatch found by the tests appears in both `drafts.md` and the skill.
- **SC-005**: All five hackathon skills are fully accounted for in `research.md` (every claim taken or not taken).
- **SC-006**: Each of the four ladder tasks has 3 scored repeats per arm and a recorded decision.
- **SC-007**: The existing suite on `iris-dev-iris` passes unchanged.
- **SC-008**: With `iad-aihub-iris` stopped, the AI Hub tests report skipped, zero failed.

## Assumptions

- The image `docker.iscinternal.com/docker-unreleased/intersystems/irishealth:2026.3.0AI.139.0` is already pulled locally and is the EAP build Tom named.
- Agents running the skill can fetch raw files from GitHub; when they cannot, the installed classes are the fallback.
- The real turn uses OpenAI; Tom supplies `OPENAI_API_KEY` in the environment. Without it US3 scenario 5 stays skipped and the skill says the turn was not measured.
- Ladder grading makes no LLM call; the live tool-call behaviour is measured only by the FR-011 test.
- The ladder remains underpowered for lift claims; SC-006 measures gross mechanical failures, not skill lift.
- The 130 harness fixes (isolation, FR-022, FR-023, `needs_fix`) are present because 132 is stacked on 131.

## Out of Scope

- The `iris-mcp-oauth2` skill and any auth setup on the container.
- Filing issues or PRs on ai-hub-eap or ready-hackathon-dev-template.
- Any new iad tool, unless US5 evidence calls for it (then a follow-up spec).
- Pushing any branch.
