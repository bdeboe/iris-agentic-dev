# Feature Specification: Skill routing optimisation loop

**Feature Branch**: `128-skill-routing-loop`
**Created**: 2026-09-26
**Status**: Draft
**Input**: Put bundled skill descriptions through a train/holdout optimisation loop in the manner of specs 120 and 121: the `gepa` package proposes, a cheap routing proxy scores, a frozen holdout decides, and a human commits. Design settled in the 127–130 grill (2026-09-26).

## Context

An agent picks a skill from a menu of names and one-paragraph descriptions. When a description is vague the agent loads the wrong skill or none, and the skill's content never reaches it. The 2026-09-25 routing spike (`.iad-local/spike-128/`) measured skill Recall@1 at 77% for BM25 over the current descriptions, and 63% on paraphrased prompts. It also showed that labels written by the same hand as the prompts flatter the ranker.

Spec 127 fixed what the skills say. This spec changes only how they are found. A description is behaviour, so a reward can judge it: did the right skill get picked? Facts are not, so the loop is forbidden from adding any (FR-006).

128 builds the loop and applies it to the skill descriptions. 129 (hint rules) and 130 (content-skill descriptions) plug new surfaces into the same loop.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - A maintainer measures routing on a frozen holdout (Priority: P1)

Tom wants to know how often an agent picks the right skill for a real request. He runs one command and gets Recall@1, the false-hint rate and the exact-name slice for the current descriptions. The figures are computed on holdout prompts only, with confidence intervals.

**Why this priority**: Without a trusted measurement the loop has nothing to optimise against, and a result cannot be believed.

**Independent Test**: With the corpus and split committed, `optimize --surface skill-descriptions --measure-only` scores the shipped descriptions on the holdout and writes a report. Unit tests prove the split is the hash rule, a train prompt cannot enter a holdout figure, and an unscored item is excluded rather than counted wrong.

**Acceptance Scenarios**:

1. **Given** the committed corpus and split, **When** the measurement runs, **Then** the report states n, Recall@1 with a 95% interval, false-hint rate and exact-name Recall@1, all from holdout items only.
2. **Given** a scorer call that fails twice, **When** the item is scored, **Then** it is recorded unscored with a reason and left out of every rate. If more than 10% of items are unscored, the run is invalid and writes no figures.
3. **Given** someone moves a prompt from holdout to train, **When** the unit tests run, **Then** they fail.

---

### User Story 2 - The loop proposes better descriptions and cannot cheat (Priority: P1)

Tom runs the optimiser with a budget. It proposes new descriptions for the chosen skills, scores them on train prompts only, and writes the best candidate and a report. It never edits a `SKILL.md`, and it never spends past the budget.

**Why this priority**: This is the feature.

**Independent Test**: An offline run with a scripted proposer and scorer shows that the validator rejects a candidate before it is scored, that the budget stops the run, and that the holdout is never passed to the proposer or the train scorer. One billable smoke run (`--budget 1`) shows the real path end to end.

**Acceptance Scenarios**:

1. **Given** a proposed description over 1024 characters, without `USE FOR:` and `DO NOT USE FOR:`, or naming a fact the skill body does not contain, **When** it is proposed, **Then** it is rejected before scoring and the rejection is logged.
2. **Given** `--budget 20`, **When** the ledger reaches $20, **Then** the run stops, writes what it has, and says it stopped on budget.
3. **Given** a finished run, **When** its output directory is read, **Then** it holds `report.md`, `candidate.json` and `ledger.jsonl`, and no file under `skills/` changed.

---

### User Story 3 - Only a candidate that beats the holdout ships (Priority: P1)

The report gives a verdict, SHIP or HOLD. SHIP means all four gates passed on the holdout. HOLD names the gates that failed.

**Why this priority**: The spike showed how easily a routing figure flatters itself. The gate is what makes a SHIP credible.

**Independent Test**: Unit tests feed the gate paired outcomes with known answers: a clear win gives SHIP, a tie gives HOLD, a win that raises false hints gives HOLD, and a win that drops the exact-name slice gives HOLD.

**Acceptance Scenarios**:

1. **Given** paired holdout outcomes, **When** the paired bootstrap interval for the Recall@1 difference has a lower bound at or below 0, **Then** the verdict is HOLD.
2. **Given** a candidate whose false-hint rate on holdout no-skill prompts is above the seed's, **Then** HOLD.
3. **Given** a candidate whose exact-name Recall@1 is below the seed's, **Then** HOLD.
4. **Given** a live ladder result below the seed by more than 0.05, or no live ladder run at all, **Then** HOLD, and the report says which.

---

### User Story 4 - Tom applies a SHIP candidate and CI keeps it honest (Priority: P2)

With a SHIP verdict, `optimize apply <run>` writes the candidate descriptions into the working tree. Tom reviews the diff and commits. CI runs the same validator over every shipped description.

**Why this priority**: Shipping by hand is the rule (grill), but copying 38 descriptions by hand invites mistakes.

**Independent Test**: `apply` on a HOLD run refuses. `apply` on a SHIP run changes only `description:` values. A CI test fails when any shipped description breaks the validator.

**Acceptance Scenarios**:

1. **Given** a HOLD run, **When** `apply` is called, **Then** nothing changes and it exits non-zero.
2. **Given** a SHIP run, **When** `apply` is called, **Then** only front matter `description:` values change, and the files still parse.

### Edge Cases

- A prompt no skill covers: its gold label is `none`. The proxy picking any skill is a false hint.
- A prompt two skills answer equally: its gold holds both names, and either counts as correct.
- The corpus grows after the split is frozen: new items go to train or holdout by the hash rule, and existing assignments never move.
- The configured scorer model is unavailable (on this account's Bedrock, `haiku_model()` resolves to Sonnet 4.6): the model the response reports is recorded, and a report whose scorer differs from the seed measurement's cannot be compared (baseline comparability rule, spec 118).
- The gepa package changes its API: it is pinned, and a unit test imports the adapter against the pinned version.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: A routing corpus of about 200 prompts mined from existing sources: benchmark and targeted tasks, `eval.yaml` prompts, GitHub issue titles, and session transcripts with private data removed. No prompt is written for this corpus. Each item records its source.
- **FR-002**: Labels are assigned blind. The labeller sees the prompt and each skill's name and body, never its description. Two independent passes; where they disagree, both names are accepted if both are defensible, otherwise the item is dropped and recorded. The agreement rate goes in the corpus README.
- **FR-003**: The split is 60/40 by `sha256(id) mod 100 < 60` → train, recorded in `routing-split.toml`. The holdout is frozen: an existing assignment never changes, and a unit test enforces it.
- **FR-004**: The inner score is a routing proxy. One scorer call per prompt shows the whole skill menu (name and candidate description for every skill) and asks for one skill name or `none`. Exact match to gold scores 1, anything else 0. Unscored items follow spec 118: excluded from rates, and a run with more than 10% unscored is invalid.
- **FR-005**: The proposer is the pinned upstream `gepa` package behind an adapter in `tests/e2e/skill_eval/optimize/`. The candidate is `{skill name: description}`. The reflection model is Sonnet 5. The adapter selects the surface with `--surface`; 128 registers `skill-descriptions`.
- **FR-006**: Every proposed text passes the validator before it is scored: 1024 characters or fewer, contains `USE FOR:` and `DO NOT USE FOR:`, and introduces no fact. A fact is an identifier-like token (backticked span, `%Class`, `$Function`, `#NNNN` error code, `<ERROR>`, iad tool name) that appears in neither the skill body nor its seed description. A rejected proposal never reaches the scorer.
- **FR-007**: Train prompts only reach the proposer and the train scorer. Holdout prompts only reach the final measurement. A guard raises if a holdout id is passed to either.
- **FR-008**: `--budget` in dollars, default 20, is a hard cap across scorer and reflection calls, priced from a table in code. The ledger records every call's model, tokens and cost.
- **FR-009**: The ship gate, on the holdout: the paired bootstrap (10,000 resamples, seed 128) 95% interval for the candidate-minus-seed Recall@1 difference has its lower bound above 0; the false-hint rate is not above the seed's; exact-name Recall@1 is not below the seed's; and the live `claude -p` ladder for the finalist is not below the seed by more than 0.05. All four pass → SHIP, else HOLD with the failed gates named.
- **FR-010**: `optimize` writes `report.md`, `candidate.json` and `ledger.jsonl` under `tests/e2e/results/optimize/<run_id>/` and edits nothing else. `optimize apply <run_id>` writes candidate descriptions into the working tree only when the verdict is SHIP.
- **FR-011**: CI runs the validator over every shipped description: the length cap, a strict-YAML parse and no new facts. The `USE FOR:`/`DO NOT USE FOR:` markers are required of candidates only, because the current 38 descriptions predate them. Same function, one flag.
- **FR-012**: The nightly drift check re-scores the shipped descriptions on the holdout with the proxy and fails when Recall@1 falls outside the committed interval. It runs no optimiser.

### Out of scope

- Server instruction and tool descriptions (grill Q12; follow-up).
- Skill content and facts (spec 127, live tests only).
- Any change to how iad serves skills.

### Key Entities

- **Routing item**: id, prompt, gold (skill names or `none`), slice (`paraphrase`, `exact-name`, `no-skill`), source, labeller passes.
- **Split**: id → train or holdout, frozen.
- **Candidate**: skill name → description.
- **Ledger entry**: call kind, model, input/output tokens, cost, running total.
- **Report**: run id, surface, seed and candidate figures on holdout, bootstrap interval, gate results, verdict, scorer model, spend.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: The measurement of the shipped descriptions reports holdout Recall@1 with a 95% interval, over at least 70 holdout items.
- **SC-002**: No optimiser run exceeds its budget by more than one call's cost.
- **SC-003**: Every rejection rule in FR-006 has a unit test that feeds it a violating text and sees it rejected unscored.
- **SC-004**: The gate returns HOLD for all four failure cases in User Story 3 and SHIP for the clear win.
- **SC-005**: A first real run with the default budget produces a verdict. If it is HOLD, it is reported as HOLD; no gate is loosened to make it SHIP.

## Assumptions

- The Anthropic API or Bedrock credentials the skill-eval harness uses are available for billable runs. Offline tests need none.
- Labelling is done by Claude sessions following FR-002, recorded as such.
- The live ladder reuses `tests/e2e/skill_eval/ladder.py`.
