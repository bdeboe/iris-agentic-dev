# Feature Specification: Prove the tools and skills help

**Feature Branch**: `121-benchmark-program`
**Created**: 2026-09-16
**Status**: Draft
**Builds on**: `specs/120-repo2rlenv-rl-env/` (branch
`claude/repo2rlenv-iris-setup-w8xij5`) — that plan supplies the task format, the agent-driver
boundary and the train/holdout split this spec measures with. Spec 120 records "scope is not
agreed" and leaves its decision 2 open, harness optimization against policy training. This spec
takes the first: measure and prove, no GPUs, and leave training open.
**Input**: User description: "we need to know how each of our tools and skills perform, how they
help and PROVE it. We're going to be rolling out with Learning Services a 'learning path' for
agentic coding with IRIS, featuring iris-agentic-dev, and also pushing it in hackathons and user
conferences over next months — IF it really helps!"

## User Scenarios & Testing _(mandatory)_

Learning Services is building a learning path around this tool, and it goes to hackathons and
user conferences over the next few months. The condition on that is that iad actually helps. I
cannot currently show that it does, because I have never measured it.

Four things claim to be benchmarks in this repo. Here is what each one is:

| Where                   | What it varies                        | Corpus   | Last run   | State                    |
| ----------------------- | ------------------------------------- | -------- | ---------- | ------------------------ |
| `tests/e2e/skill_eval/` | one skill's markdown, on or off       | 9 skills | nightly    | red every night on noise |
| `benchmark/021/`        | tool descriptions and system prompt   | 39 tasks | 2026-08-25 | stale, v1.2.6, not in CI |
| `tools/gepa-optimizer/` | tool descriptions, optimization loop  | own      | unknown    | separate, not in CI      |
| `src/benchmark/tasks/`  | named by Constitution IX as canonical | —        | never      | **does not exist**       |

Spec 120 proposes the fifth thing and the one worth converging on: export the corpus to the
[Harbor](https://github.com/laude-institute/harbor) task format, where a task is a directory
holding `instruction.md`, `task.toml`, `environment/`, `tests/test.sh` and `solution/solve.sh`.
That format decides two of this spec's hardest questions for free. `tests/test.sh` is a
deterministic check by construction, which is Story 2's requirement rather than an aspiration.
`solution/solve.sh` is a reference solution, which proves a task's check can pass at all — the
thing four of the nine skills above cannot currently demonstrate.

One correction to spec 120's summary, which says the reward function already exists in
`benchmark/021/runner/judge.py` and `tests/e2e/skill_eval/scoring.py`. Both of those are LLM
judges. A judge is not a reward function I can publish a number from, for the reasons in Story 2,
so the rewards mostly do not exist yet and writing them is the bulk of the corpus work. Harbor's
format is what makes that tractable, not what makes it unnecessary.

**Not one of them has ever removed iad.** The nightly varies a skill document with the tool
surface held constant in both arms — `no_mcp_for_benchmark` is passed to the baseline arm and the
skill arm alike (`lift.py:508` and `:519`). `benchmark/021` varies tool descriptions between
`baseline`, `nostub` and `merged` conditions, which are three shapes of the same present toolset.
So every number I have describes a document or a description string. The claim Learning Services
needs — an agent with iad beats an agent without it on IRIS work — has no measurement behind it
at all.

Constitution IX already requires this. Every new tool is supposed to ship a benchmark task
proving lift of +0.20 or better, recorded in `specs/<feature>/lift-results.md`. Seven such files
exist across about 120 specs and 81 tools, and one of the seven records that no measurement was
possible. The principle points at `src/benchmark/tasks/`, a directory that has never existed.

The measurement I do have is not powered to say anything. From
`tests/e2e/results/skill-baseline.json`:

| Skill                      |   N | no-skill | skill |  lift | mode    |
| -------------------------- | --: | -------: | ----: | ----: | ------- |
| ensemble-production        |  10 |     0.10 |  0.00 | −0.10 | pattern |
| iris-ai-hub                |  30 |     0.40 |  0.30 | −0.10 | pattern |
| iris-connectivity          |   5 |     0.00 |  0.00 |  0.00 | judge   |
| iris-vector-ai             |  10 |     0.10 |  0.30 | +0.20 | pattern |
| objectscript-guardrails    |   5 |     0.80 |  1.00 | +0.20 | judge   |
| objectscript-list-patterns |   5 |     0.00 |  0.00 |  0.00 | judge   |
| objectscript-review        |   5 |     0.60 |  0.80 | +0.20 | judge   |
| objectscript-sql-patterns  |   5 |     0.00 |  0.00 |  0.00 | judge   |
| objectscript-unit-test     |  10 |     0.00 |  0.00 |  0.00 | judge   |

At a baseline pass rate of 0.40, an independent two-proportion comparison needs 97 items per arm
to detect a +0.20 difference at 80% power. Thirty items per arm buys a minimum detectable effect
of 0.35. Five items buys nothing measurable at all. Every +0.20 in that table is one item
flipping, and the nightly gate fires at a threshold of 0.05 on a quantity whose resolution is
0.20.

Four skills read 0.00 against 0.00. A task no arm can pass carries no information, and
`objectscript-guardrails` at 0.80 against 1.00 is close to the same problem from the other end.

Spec 118 wrote two of these problems up as User Stories 3 and 4 and deferred both, on the
correct reasoning that the verdicts were not trustworthy until the scorer worked. The scorer
works now: run 34939912456 scored 170 of 170 items with none unscored. Those two stories become
Stories 4 and 3 here, and the new work in front of them is the arm that has never been run.

Two design corrections drive everything below.

**Breadth beats repetition.** The nightly gets its items from 5 repeat runs of 2 tasks. Five
runs of one task are near-duplicates: a hard task is hard every time, so the repeats inflate the
item count without adding independent information. Fifty distinct tasks run twice carries far
more information than two tasks run five times, and costs about the same.

**Pair the arms.** Running the same task in every arm and comparing within-task, by McNemar,
removes task difficulty from the variance. Detecting +0.20 needs 97 items per arm unpaired
against 37 to 77 task-pairs paired, depending on how often the arms disagree. This is the single
largest power gain available, and it is free.

---

### User Story 1 - I can say what iad is worth, with a confidence interval (Priority: P1)

I want one number I can put on a slide and defend to a skeptic: the share of realistic IRIS
tasks an agent completes without iad, against the share it completes with iad, measured on the
same tasks, graded by machine.

Three arms, same tasks, same model, same container. Each is a configuration of spec 120's
agent-driver interface — prompt in; transcript, tool-call log, scalar reward and `scored` flag out
— so an arm is a driver setting rather than a separate code path:

- **bare** — Claude Code with no iad MCP server and no iad skills installed
- **tools** — iad MCP server registered, no skills installed
- **tools+skills** — iad MCP server registered, the skill pack installed

The tool-call log that interface already returns is what Story 5 joins against, so per-tool
attribution costs no additional runs.

Grading is machine-checkable in every case: the class compiled, the unit test passed, the query
returned the expected rows, the global holds the expected value. No model scores anything.

**Why this priority**: it is the claim the learning path rests on, and it does not exist. Nothing
else here matters if this number comes back flat.

**Independent Test**: run the corpus across the three arms against `iris-dev-iris`, and read a
report giving each arm's pass rate with a 95% Wilson interval, the paired lift between adjacent
arms with a McNemar interval, and the minimum detectable effect the corpus size bought.

**Acceptance Scenarios**:

1. **Given** the bare arm, **When** it runs, **Then** no iad tool call appears in its transcript
   and no iad skill file is readable from its working directory.
2. **Given** a completed run, **When** I read the report, **Then** each arm carries a pass rate
   with a 95% interval, and each adjacent-arm lift carries an interval and a p-value.
3. **Given** a lift whose interval contains zero, **When** the report prints it, **Then** it is
   labelled as not distinguishable from zero rather than shown as a positive result.
4. **Given** any graded task, **When** I ask why it passed, **Then** the report names the
   deterministic check that passed and the IRIS artefact it inspected.
5. **Given** the arm ladder, **When** the tools arm beats bare but tools+skills does not beat
   tools, **Then** the report says so plainly, because that is a publishable finding about the
   skills.
6. **Given** a published figure, **When** I trace which tasks produced it, **Then** every one
   comes from the holdout split, and no task used to tune a tool description, a skill or a prompt
   appears in it.

The last scenario is the one that can invalidate everything else. GEPA optimizes tool
descriptions against this corpus, and `benchmark/021`'s `merged` condition is a tuned system
prompt. A pass rate measured on tasks the descriptions were fitted to overstates the tool's
value, and at conference scale that is the criticism that lands. Spec 120's committed train and
holdout split, with its guard test asserting no task ID appears in both, is a prerequisite for
publishing anything here rather than a later refinement.

---

### User Story 2 - Every graded task is checked by a machine, not a model (Priority: P2)

Six of the nine gated skills grade by LLM judge today. A judge costs money per item, drifts as
the scorer model changes, and gives a skeptic something to argue with. "Sonnet scored it 0.8" is
contestable in a way that "the class compiled and its unit test passed against IRIS 2026.2" is
not.

Every task in the gated corpus asserts against IRIS state or against a command's exit status.
The judge stays available for exploratory work, and its results never enter a published number.

Harbor's `tests/test.sh` is that assertion, and its `solution/solve.sh` is the guard against the
opposite failure: a check nobody can satisfy. A task whose reference solution does not pass its
own check is a broken task, and it fails corpus validation instead of quietly reading as a hard
one. That single rule would have caught all four of the 0.00-against-0.00 skills the night they
were written.

**Why this priority**: it is the difference between a number I can publish and a number I can
only assert, and it takes the per-item scoring cost to zero.

**Independent Test**: run the gated corpus with no scorer credential configured at all and
confirm every task still produces a pass or fail.

**Acceptance Scenarios**:

1. **Given** the gated corpus, **When** corpus validation runs, **Then** it fails on any task
   whose grading is a model judgement.
2. **Given** no scorer credential, **When** the gated corpus runs, **Then** it completes and
   grades every item.
3. **Given** a task's check, **When** it runs twice against the same agent output, **Then** it
   returns the same verdict both times.
4. **Given** a check that passes because IRIS was already in the expected state before the agent
   ran, **When** corpus validation runs, **Then** it fails the task for having no precondition
   that the agent must change.

---

### User Story 3 - The gate fires on effects, not on coin flips (Priority: P3)

Inherits 118's User Story 4, with its acceptance scenarios unchanged, plus what the power
calculation above settles: the harness computes and prints the minimum detectable effect its
item count bought, gates only comparisons that clear an item floor, and sets its threshold at or
above the effect it can actually detect. Paired comparison by McNemar replaces the subtraction of
two point estimates.

**Why this priority**: the nightly has failed three consecutive nights on differences inside its
own noise, so every verdict it currently produces is unreadable.

**Independent Test**: run one gated comparison twice with nothing changed between runs, and
confirm the two lift values fall within the reported minimum detectable effect of each other and
that the gate stays quiet.

---

### User Story 4 - No task set stays in the corpus that measures nothing (Priority: P4)

Inherits 118's User Story 3, with its acceptance scenarios unchanged. The scorer repair has
landed, so the verdicts are now trustworthy, and the four skills still reading 0.00 against 0.00
get one of four recorded verdicts on evidence — broken check, too hard for both arms, too easy
for both arms, or a skill that genuinely does not help — and are then fixed or deleted. Deleting
is an acceptable outcome. A saturated task set such as `objectscript-guardrails` at 0.80 against
1.00 gets the same treatment from the ceiling end.

**Why this priority**: it pays for Story 3's item counts, and a corpus that cannot discriminate
makes Story 1's headline number weaker than it needs to be.

---

### User Story 5 - I know which of the 81 tools earn their place (Priority: P5)

Constitution IX asks for per-tool lift and has been enforced seven times. I want the standing
answer instead of a per-feature ritual: for each tool, how often an agent reaches for it when it
would help, and whether the tasks that use it succeed more often than the tasks that solve the
same problem without it.

This is a join, not a new set of runs. The tool-call records already emitted during Story 1's
sessions carry the tool name and outcome; joining them to each task's graded result gives reach
rate and conditional success per tool for free.

**Why this priority**: it needs Story 1's runs to exist before it can read them, and its finding
— that some tools are never reached for — costs nothing extra to obtain.

**Independent Test**: run the corpus once and read a per-tool table of reach count, reach rate
among tasks where the tool was applicable, and pass rate of tasks that called it against tasks
that did not.

**Acceptance Scenarios**:

1. **Given** a completed corpus run, **When** I read the tool report, **Then** every tool in the
   advertised surface appears, including those with a reach count of zero.
2. **Given** a tool never reached for across the whole corpus, **When** the report prints,
   **Then** it is named as unreached rather than omitted.
3. **Given** Constitution IX's `src/benchmark/tasks/` path, **When** the program lands,
   **Then** either the directory exists and holds the corpus, or the constitution is amended to
   name the path that does.

---

### User Story 6 - Someone else can run this and get my number (Priority: P6)

At a conference, "here is the harness, reproduce it" is a stronger position than "trust my
slide". `light-skills/BENCHMARKING.md` already promised a runnable benchmark and pointed at a
private GitLab URL, which spec 059 recorded as an active broken promise to the community. This
story closes it.

One harness, one corpus, one command, documented, needing only Docker, a model credential and a
clone. The four systems in the table above converge or are deleted.

Harbor carries most of this. A corpus in a published open format runs under a CLI the reader
already has, against a `docker-compose.yaml` that stands up IRIS as a sidecar, so reproducing the
number needs no code of mine at all. That is a stronger claim than a harness only I can run, and
it is why the format decision in spec 120 belongs upstream of this story rather than beside it.

**Why this priority**: it depends on the corpus and the arms being settled, and it is the story
that turns an internal number into an external one.

**Independent Test**: on a machine with no repo-specific state, follow the documented steps and
land within the reported minimum detectable effect of the published pass rates.

**Acceptance Scenarios**:

1. **Given** a fresh clone and a model credential, **When** I follow the documented quickstart,
   **Then** the harness runs and writes a result file without further configuration.
2. **Given** the four benchmark systems, **When** this story lands, **Then** each one is either
   the surviving harness, folded into it, or deleted, and no documentation points at a system
   that no longer exists.
3. **Given** the published number, **When** a reader reruns the corpus at the documented size,
   **Then** the reported minimum detectable effect covers the difference from the published
   value.

---

### Edge Cases

- The bare arm needs a genuinely iad-free environment. A leftover MCP registration, a skill file
  on the search path, or a `CLAUDE.md` naming iad tools all contaminate it. The harness must
  assert absence rather than assume it, and a contaminated bare arm invalidates the run.
- A task the bare arm passes at 100% carries no information about iad and belongs out of the
  gated corpus, though it stays useful as a regression canary.
- Machine checks can pass for the wrong reason: a class that compiles because it was already
  compiled, a query that returns rows the fixture created. Each check needs a precondition
  asserting the pre-run state fails it.
- Wall clock and token count are secondary outcomes worth reporting, and they are not the claim.
  An arm that fails faster is not better.
- The three arms differ in context size, so the bare arm sees a smaller prompt. That is part of
  what is being measured, not a confound to correct for.
- A tool with a reach count of zero may be correct and simply not covered by the corpus. The
  report distinguishes "no task needed it" from "tasks needed it and the agent chose otherwise".
- Paired comparison needs the same task in every arm. A task that only makes sense with iad
  present, such as one whose prompt names a tool, cannot enter the paired corpus.

## Clarifications

### Session 2026-09-16

- Q: How should tasks be graded in the new corpus? → A: Machine-checkable only. Every task graded
  by a deterministic check against live IRIS. No LLM judge in any published number.
- Q: Budget for one full benchmark run? → A: ~$50–80 per run, run at each release and before each
  conference rather than nightly.
- Q: Who needs to be able to run it? → A: Both an internal number and a publicly runnable
  harness, so a reader can reproduce the published figure.

### Session 2026-09-16, second pass — from `/speckit.analyze`

- Q: What is the item floor, and what is the gate threshold? → A: Threshold +0.20, matching
  Constitution IX. Floor 37 task-pairs, being the smallest paired count whose minimum detectable
  effect reaches 0.20 at the expected discordance of 0.20, recomputed per run from the discordance
  actually measured. The existing 0.05 threshold sits below the harness's own resolution and goes.
- Q: Can the eight-task pilot return a go verdict without breaking FR-010? → A: Only because the
  pilot verdict is not a published figure. FR-024 carves it out explicitly and requires it to show
  its discordant-pair counts, since an eight-pair interval will contain zero whatever happens.
- Q: Does the nightly keep reporting lift once it is powered correctly? → A: No. It reports no
  lift at all and guards breakage over a canary set. FR-016 now says so.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: The harness MUST support three arms — bare, tools, tools+skills — selectable per
  run, with the bare arm having no iad MCP registration and no iad skill file reachable.
- **FR-002**: The harness MUST assert the absence of iad in the bare arm before the session
  starts, and MUST fail the run rather than report a contaminated arm.
- **FR-003**: Every task in the gated corpus MUST be graded by a deterministic check against
  IRIS state or a command exit status, and corpus validation MUST reject a task graded by model
  judgement.
- **FR-004**: Every gated task MUST declare a precondition that fails before the agent runs, and
  corpus validation MUST reject a task whose check passes against the untouched fixture.
- **FR-005**: The harness MUST run each task in every arm and compare within-task by McNemar,
  reporting the count of discordant pairs alongside the lift.
- **FR-006**: The harness MUST report each arm's pass rate with a 95% Wilson interval, and each
  adjacent-arm lift with an interval and a p-value.
- **FR-007**: The harness MUST compute and print the minimum detectable effect its item count
  buys, beside every lift it reports.
- **FR-008**: The gate MUST NOT fire on a comparison below the declared item floor of **37
  task-pairs**, and MUST report such a comparison as underpowered rather than as passing. The
  floor is derived rather than chosen: it is the smallest paired item count whose minimum
  detectable effect reaches the 0.20 threshold, at the 0.20 discordance rate the Assumptions
  section expects. The harness MUST recompute the floor from each run's measured discordance and
  report the recomputed value, so a discordance of 0.40 raises the floor to 77 pairs instead of
  passing a comparison that cannot support the verdict.
- **FR-009**: The declared gate threshold is a lift of **+0.20**, matching Constitution IX's
  requirement for a new tool. The effective threshold MUST be at least the reported minimum
  detectable effect, so a corpus that buys less resolution raises the bar rather than lowering it.
  The current 0.05 threshold is below the harness's own resolution and MUST be replaced.
- **FR-010**: A lift whose interval contains zero MUST be reported as not distinguishable from
  zero, and MUST NOT be presented as a positive result.
- **FR-011**: The harness MUST record, per task and per arm, the tool calls made and their
  outcomes, and MUST join them to the graded result to produce a per-tool reach rate and
  conditional pass rate.
- **FR-012**: The per-tool report MUST list every tool in the advertised surface, including
  unreached tools, and MUST distinguish "no task needed it" from "a task needed it and the agent
  chose otherwise".
- **FR-013**: Corpus validation MUST assign every flat task set a recorded verdict of broken
  check, too hard, too easy, or not helped, and MUST fail until each is replaced or removed.
- **FR-014**: Corpus validation MUST reject a task set whose arms are saturated at the ceiling as
  well as at the floor.
- **FR-015**: The full benchmark MUST estimate its cost before the first billable session and
  MUST stop before spending anything if the estimate exceeds the declared cap.
- **FR-016**: The nightly MUST remain a cheap breakage guard over a named canary set — does the
  harness still run, does the binary still advertise its tools, does the canary set still pass —
  and its output MUST carry no lift number at all, not merely no unpowered one. Lift is reported
  by the full benchmark alone, which runs at each release and before each conference.
- **FR-017**: The harness MUST run from a fresh clone with only Docker and a model credential,
  and its quickstart MUST be documented in the repository.
- **FR-018**: Every benchmark system that does not survive MUST be deleted, and no documentation
  may point at a system that no longer exists.
- **FR-019**: Constitution IX's canonical task path MUST either exist and hold the corpus, or the
  constitution MUST be amended to name the path that does.
- **FR-020**: Published results MUST record the tool surface version, model identity, container
  image, corpus commit and item counts, so a reader can tell which software produced them.
- **FR-021**: Every published figure MUST come from the holdout split, and the harness MUST
  refuse to publish a figure computed over any task in the train split.
- **FR-022**: Corpus validation MUST fail a task whose reference solution does not pass that
  task's own check.
- **FR-023**: An arm MUST be expressed as a configuration of the agent-driver interface, so
  adding an arm needs no new code path in the harness.
- **FR-024**: A verdict used only to decide whether to keep building — the pilot's go/no-go — MUST
  be labelled a design decision rather than a result, MUST NOT be published, and MUST NOT be
  counted against FR-008's item floor or FR-010's interval rule, both of which govern reported
  figures. It MUST instead state the raw discordant-pair counts it rests on and the one-sided
  exact p-value those counts give, so the strength of the decision is visible even though the
  comparison is not powered to publish. A pilot that reaches a go verdict has decided to spend
  money, not established a lift.

### Key Entities

- **Arm** — one configuration under test: bare, tools, or tools+skills. Carries its own
  environment assertions.
- **Graded task** — a prompt, a fixture, a precondition that fails before the agent runs, and a
  deterministic check that decides pass or fail.
- **Task-pair** — the same graded task run in two arms, the unit of paired comparison.
- **Comparison** — two arms over one corpus subset, carrying a lift, an interval, a p-value, a
  discordant-pair count and a minimum detectable effect.
- **Tool attribution record** — one tool, its reach count, its applicable-task count, and the
  pass rates of tasks that called it against tasks that did not.

## Assumptions

- Task difficulty correlates strongly between arms, so pairing gains most of the power the
  McNemar figures above suggest. If the arms turn out near-independent, the item floor rises and
  the corpus has to grow; the harness reports discordance so this is visible rather than assumed.
- A corpus of 50 to 60 machine-checkable tasks is reachable. The 39 tasks in `benchmark/021` are
  a starting point, though they grade by judge today and need checks written.
- Local development grades against `iris-dev-iris` on IRIS Community 2026.2, this project's
  exclusive container. Spec 120's sidecar step pins `intersystemsdc/iris-community:2025.3`
  instead, on the grounds that it is `ci.yml`'s last known-good. Those need to be one image before
  a number is published, since a pass rate is only meaningful against a named build. I default to
  the 2026.2 image the project already owns and treat 2025.3 as the CI fallback, and I flag this
  as needing agreement with spec 120 rather than settling it unilaterally.
- Community image licences expire roughly 150 days after publish, which rots any frozen
  environment. Published results name their image digest so an expired-licence rerun is
  diagnosable rather than mysterious.
- Two runs per task per arm is enough once breadth replaces repetition. The harness reports
  within-task variance so this can be checked rather than trusted.

## Cost

Per-item cost from the nightly's own history is about $0.031 — a shard covering 2 tasks × 5 runs
× 2 arms, 20 items, costs roughly $0.62.

**Full benchmark**, at 50 tasks:

| Component                                            | Sessions |    Cost |
| ---------------------------------------------------- | -------: | ------: |
| Arm ladder, 50 tasks × 3 arms × 2 runs               |      300 |   $9.30 |
| Per-skill lift, 9 skills × 6 tasks × 2 arms × 2 runs |      216 |   $6.70 |
| Per-tool attribution (join over the runs above)      |        0 |   $0.00 |
| **Total**                                            |  **516** | **$16** |

That sits well inside the $50–80 cap, which leaves room to double the corpus or add runs if the
reported discordance says the pairing is weaker than assumed. Machine-checkable grading removes
the judge tokens from every item, so the corpus can grow before the cap binds.

The money is not the constraint and never was. Today's nightly spends about $5.47 to learn
nothing from four unpassable task sets, five repeat runs of two tasks, and a gate that fires on
quantization. Most of the fix is a redistribution of spend I am already making.

**Nightly** stays a breakage guard: does the harness still run, does the binary still expose its
tools, does a small canary set still pass. It publishes no lift number.

## Out of Scope

- Optimizing tool descriptions against the harness. That is the GEPA work, and it consumes this
  measurement rather than belonging to it.
- Comparing against Copilot or other assistants. `benchmark/021` has a `copilot` harness and the
  claim here is about iad's contribution, not about a vendor comparison.
- Model selection. One model is held fixed across arms; which model is best is a separate
  question.
- Learning-path content. This spec produces the evidence the path cites, not the path.

## Dependencies

- Live `iris-dev-iris` (IRIS Community 2026.2, 11975 TCP / 52780 web) for every graded check.
- Spec 059's tool-call telemetry as the source for Story 5's join.
- Spec 118's scorer repair, landed, which makes Stories 3 and 4 trustworthy.
- Spec 120 on branch `claude/repo2rlenv-iris-setup-w8xij5`, for three things this spec consumes
  and does not build: the Harbor task format and its `tests/test.sh` reward contract, the
  agent-driver interface the arms are configurations of, and the committed train/holdout split
  FR-021 publishes from. Spec 120's Slice 1 is the prerequisite for Stories 1, 2 and 6 here.
  Nothing in this spec needs its GPU or trainer material, and spec 120 says the same.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: A published pass rate for each of the three arms, each with a 95% interval, on a
  corpus of at least 50 machine-checkable tasks.
- **SC-002**: The bare-to-tools lift reported with an interval and a p-value, and a stated
  minimum detectable effect at or below 0.20.
- **SC-003**: Zero tasks in the gated corpus graded by model judgement.
- **SC-004**: Zero task sets in the gated corpus flat at floor or ceiling in both arms.
- **SC-005**: Every tool in the advertised surface appears in the attribution report, with
  unreached tools named.
- **SC-006**: A full benchmark run costs no more than $80 and refuses to start if its estimate
  exceeds the cap.
- **SC-007**: The nightly reports no lift number at all, runs a named canary set instead, and
  stops failing on differences inside its own noise.
- **SC-008**: A fresh clone reproduces the published pass rates within the reported minimum
  detectable effect.
- **SC-009**: Exactly one benchmark harness remains in the repository, and no documentation
  points at a deleted one.
- **SC-010**: Every published figure traces to holdout tasks only, and the harness refuses to
  compute one over the train split.
- **SC-011**: Every task in the gated corpus has a reference solution that passes its own check.
