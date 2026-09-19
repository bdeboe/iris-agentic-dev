# Tasks: Prove the tools and skills help

**Input**: Design documents from `/specs/121-benchmark-program/`
**Prerequisites**: spec.md, plan.md. `research.md`, `data-model.md` and `contracts/` are Phase 0
and Phase 1 outputs.

**Tests**: mandatory, and first within each phase. Constitution IV.

**Organization**: by phase, because the phases gate each other. Story labels map to spec.md's user
stories.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency on an incomplete task
- **[Story]**: US1–US6. Setup, Foundational and Polish tasks carry no story label

## Path conventions

Python harness at `tests/e2e/skill_eval/`, tests beside the module they cover, which is the
existing layout. Corpus at the path Phase 0 settles. Gate scanner at `scripts/gates/`.

---

## Phase 0: Reconcile with spec 120

No code. Two specs currently disagree on the IRIS image, and a pass rate against an unnamed build
is not a result.

- [x] T001 Write `research.md` § image decision: pick one of `iris-community:2026.2` (this
      project's `iris-dev-iris`) or `intersystemsdc/iris-community:2025.3` (spec 120 Slice 1, on
      `ci.yml` known-good grounds) as the grading target, record the licence-expiry consequence,
      and record the digest-pinning rule from spec.md Assumptions
- [x] T002 Write `research.md` § task format: confirm the Harbor directory layout
      (`instruction.md`, `task.toml`, `environment/`, `tests/test.sh`, `solution/solve.sh`) against
      the current Harbor docs, and record the version the golden-file test pins
- [x] T003 Write `research.md` § driver interface: record the signature spec 120 Slice 1 step 4
      declares — prompt in; transcript, tool-call log, scalar reward, `scored` flag, optional
      logprobs out — and confirm the tool-call log carries enough to satisfy FR-011. Settle which
      source supplies it, spec 059's telemetry or the driver's own log, since spec.md names one and
      the plan names the other
- [x] T004 Write `research.md` § split: record the train/holdout mechanism and where the committed
      split file lives, since FR-021 publishes from it
- [x] T005 Write `contracts/arm.md`, `contracts/graded-task.md`, `contracts/comparison.md` and
      `data-model.md` from spec.md's Key Entities

**Gate**: one named image, one confirmed task layout, one driver signature, one split file path.
Disagreements with spec 120 are resolved in writing, not deferred to the implementer.

---

## Phase 1: Honest statistics (US3)

No IRIS, no corpus, no spend. Ships alone and stops the nightly failing on quantization.

- [x] T006 [P] [US3] Unit tests for `stats.py` in `test_stats.py`, every expected value computed
      independently and written into the test as a literal: Wilson interval at n=5, 30, 100 for
      p=0, p=1 and p=0.4; the p=0 and p=1 cases specifically, since a naive interval collapses to
      zero width there and four current skills sit at exactly p=0
- [x] T007 [P] [US3] Unit tests for McNemar in `test_stats.py`: exact test on small discordant
      counts, the continuity-corrected form, a zero-discordance input returning no effect rather
      than dividing by zero, and the paired interval on a known 2×2 table
- [x] T008 [P] [US3] Unit tests for minimum detectable effect in `test_stats.py`, pinning the values
      in spec.md: n=30 per arm at baseline 0.40 gives MDE 0.35; n=100 gives 0.20; detecting +0.20
      unpaired needs 97 per arm; paired at discordance 0.20 needs 37 pairs and at 0.40 needs 77,
      which are FR-008's floor and its recomputed value
- [x] T009 [US3] Implement `tests/e2e/skill_eval/stats.py`: `wilson_interval`, `mcnemar_test`,
      `mcnemar_interval`, `mde_unpaired`, `n_for_effect_paired`. Stdlib only — `math` and a normal
      quantile, no scipy
- [x] T010 [P] [US3] Unit tests for `comparison.py` in `test_comparison.py`: a `Comparison` refuses
      to report a lift without an item count and an MDE (governance detector 1); a comparison below
      FR-008's floor of 37 task-pairs reports `underpowered` and not `passed`; a run whose measured
      discordance is 0.40 recomputes the floor to 77 and reports the recomputed value; a lift whose
      interval contains zero reports `indistinguishable` and not a positive result; the gate
      threshold of 0.20 is clamped up to the reported MDE when the MDE is larger
- [x] T011 [US3] Implement `tests/e2e/skill_eval/comparison.py`: `Comparison` carrying arms, paired
      counts, discordance, lift, interval, p-value, item count, MDE and verdict; the floor
      recomputed per run from measured discordance; pairing that keys on task ID and drops a task
      missing from either arm with a named hole
- [x] T012 [US3] Modify `lift.py` to delegate to `comparison.py` and delete the bare subtraction at
      `lift.py:76`, keeping `compute_lift_from_scores`'s `None`-when-unmeasured contract intact
- [x] T013 [P] [US3] Unit tests for the reporter in `test_reporter.py`: a formatted lift always
      carries its item count and MDE; an underpowered comparison formats as underpowered and never
      as a pass; the 0.05 threshold no longer appears anywhere in the gate path
- [x] T014 [US3] Modify `reporter.py` so every lift prints with its item count and MDE beside it,
      and an underpowered comparison prints as underpowered rather than as a pass
- [x] T015 [US3] Add the `unpowered-result` scanner check to `scripts/gates/antipatterns.py` with
      canary cases in `test_antipatterns.py`: one formatting call site that omits the MDE and must
      be flagged, one that includes it and must not. Constitution Governance — a gate with no canary
      is not a gate
- [x] T016 [P] [US3] Unit tests for the nightly's canary report in `test_nightly_canary.py`: its
      result object carries no lift field at all, not merely an underpowered one; a canary task
      failing produces a breakage verdict naming the task; a canary failure that still exits 0 is
      itself a test failure
- [x] T017 [US3] Convert the nightly to FR-016's breakage guard: a named canary set, a verdict on
      whether the harness runs and the binary still advertises its tools, and no lift number in the
      output. Name the canary set in `research.md`, and remove the per-skill lift job from
      `.github/workflows/skill-regression.yml`, which the full benchmark now owns
- [x] T018 [US3] Confirm against the three consecutive failing runs (34939912456, 34817991701, 34744344877) that each would now report underpowered rather than failing, then run one gated
      comparison twice with nothing changed and confirm the two lift values fall within the reported
      MDE of each other — spec.md US3's Independent Test

**Gate**: the nightly stops failing on differences inside its own noise, reports no lift number at
all, and every number the full benchmark prints carries what it took to measure it.

---

## Phase 2: Corpus triage (US4)

Reads artifacts already on disk. The item budget for Phases 3 and 4 comes from here.

- [x] T019 [P] [US4] Unit tests for `triage.py` in `test_triage.py`: a task set flat at floor gets a
      verdict, one flat at ceiling gets one too (FR-014, which the current gate misses entirely),
      one with a genuine arm difference gets none, and a task set with no recorded verdict fails
      validation
- [x] T020 [US4] Implement `tests/e2e/skill_eval/triage.py`: the four verdicts — broken check, too
      hard, too easy, not helped — and corpus validation that fails on an unverdicted flat set
- [x] T021 [US4] Assign verdicts on evidence to the four skills reading 0.00 against 0.00:
      `iris-connectivity`, `objectscript-list-patterns`, `objectscript-sql-patterns`,
      `objectscript-unit-test`. Read the per-item scores in the run artifacts rather than re-running
- [x] T022 [US4] Assign a verdict to `objectscript-guardrails` at 0.80 against 1.00, the ceiling
      case, and to `ensemble-production` and `iris-ai-hub` at −0.10, which are either real harm or
      noise and cannot currently be told apart
- [x] T023 [US4] Fix or delete each verdicted task set, and record what happened in `research.md` §
      triage. Deleting is an acceptable outcome; a documented null task set is not

**Gate**: no task set in the gated corpus is flat at floor or ceiling without a recorded verdict,
and every verdict has been acted on.

---

## Phase 3: The pilot, and the go/no-go

Eight tasks, three arms. Sized to see a large effect and not a small one, because the honest
answers to this question are "obviously yes" and "no".

- [x] T024 [P] Unit tests for `arms.py` in `test_arms.py`: the bare arm's absence assertion fails on
      a stale MCP registration, fails on a reachable skill file, fails on a `CLAUDE.md` naming an
      iad tool, and passes on a genuinely clean environment
- [x] T025 Implement `tests/e2e/skill_eval/arms.py`: the three arms as driver configurations per
      T003's signature, and `assert_absent()` raising rather than returning false — a contaminated
      arm must fail the run, not report a number (FR-002). Name which toolset the tools arm
      registers, Baseline or Merged, since it sets the denominator for every Story 5 figure
- [x] T026 [P] [US2] Write the eight pilot tasks, each with a precondition that fails before the
      agent runs and a reference solution that passes after. Draw from `benchmark/021`'s existing
      prompts where they suit, and write the checks, which do not exist yet
- [x] T027 [P] [US2] Unit tests for the check contract in `test_graded_task.py`: a check that passes
      against the untouched fixture fails validation (FR-004); a task whose reference solution does
      not pass its own check fails validation (FR-022); a check is deterministic across two runs on
      the same output
- [x] T028 [US2] Implement corpus validation enforcing FR-003, FR-004 and FR-022, and confirm it
      rejects a judged task and accepts a machine-checked one
- [x] T029 Run the eight pilot tasks across the three arms against live IRIS, paired,
      `--test-threads=1` equivalent for the IRIS-touching legs, and record the result
- [x] T030 **Go/no-go**, on the raw discordant-pair counts per FR-024 rather than on a lift with an
      interval — eight pairs cannot clear FR-008's floor and the interval will contain zero either
      way. With `b` the pairs where tools passes and bare fails, `c` the reverse: `c ≤ 1` and
      `b ≥ 5` and one-sided exact p ≤ 0.07 → go, build the corpus (the p-value is binding, not
      decorative — `(5, 1)` gives 0.109 and does not qualify); `b ≤ c` → stop, write the finding up and take it to Learning
      Services before they build a path on it; anything else → run eight more tasks and decide once.
      Record the counts, the one-sided exact p-value and the decision in `research.md` § pilot,
      labelled a design decision and not a result

**Gate**: a real bare-to-tools measurement exists, for the first time in this project, and the
decision to build the corpus is made on it rather than on expectation.

---

## Phase 4: The corpus and the number (US1, US2)

Only runs if T030 said go. This is the phase the $50–80 cap is for.

- [ ] T031 [P] [US2] Grow the corpus to 50 machine-checkable tasks, each satisfying FR-004 and
      FR-022. ObjectScript fixtures and reference solutions go through `objectscript-guardrails` and
      `objectscript-review` first, per the Constitution Check
- [ ] T032 [US1] Commit the train/holdout split per T004, with the guard test asserting the two ID
      sets are disjoint and their union is the corpus (governance detector 2)
- [ ] T033 [US1] Add the publish path's leakage guard: computing a published figure over a
      train-split task ID raises, with a unit test that it does
- [x] T034 [US1] Cost estimate before the first billable session, checked against the $80 cap, and
      the run refuses to start if the estimate exceeds it (FR-015), with a unit test for the refusal
- [x] T035 [US1] Run the full arm ladder from the holdout split: 41 holdout tasks × 3 arms × 1 run
      = 123 sessions. 50 was the target corpus; 41 is its holdout side, above FR-008's floor of 37.
      One repeat, not two, because the budget bought one and the strict-and rule needs no second to
      be correct — `tests/e2e/results/ladder-121-tools-holdout.json`
- [ ] T036 [US4] Run the per-skill ladder the Cost table budgets: 9 skills × 6 tasks × 2 arms × 2
      runs, tools against tools+skills, which is the only comparison that says whether a given
      skill document earns its place. Skills whose task sets Phase 2 deleted drop out, and the
      estimate shrinks with them
- [x] T037 [US1] Write the report: each arm's pass rate with a 95% Wilson interval, each
      adjacent-arm lift with a McNemar interval and p-value, the discordance count, and the MDE the
      corpus bought. If the measured discordance puts the MDE above SC-002's 0.20, extend the corpus
      to the recomputed floor before publishing rather than publishing the weaker figure
- [x] T038 [US1] Record provenance on the published figure per FR-020: tool surface version, model
      identity, container image digest, corpus commit, item counts

**Gate**: a defensible number with an interval, from holdout tasks, graded by machine, reproducible
from recorded provenance.

---

## Phase 5: Per-tool attribution (US5) — release gate

Constitution IX puts the lift-evidence phase before Polish and labels it a release gate. This is
that phase. It is a join over Phase 4's runs, so no new sessions and no new spend.

- [x] T039 [P] [US5] Unit tests for `attribution.py` in `test_attribution.py`: every advertised tool
      appears including unreached ones (FR-012); "no task needed it" is distinguished from "a task
      needed it and the agent chose otherwise"; reach rate is computed over applicable tasks rather
      than all tasks
- [x] T040 [US5] Implement `tests/e2e/skill_eval/attribution.py` joining the tool-call log to the
      graded outcome per task and arm
- [x] T041 [US5] Generate `lift-results.md` as the standing per-tool table, and name the tools with
      a reach count of zero
- [ ] T042 [US5] Resolve FR-019: either create Constitution IX's `src/benchmark/tasks/` and hold the
      corpus there, or amend the constitution to name the path that exists. An amendment goes
      through the Amendment Procedure

**Gate**: release gate. The standing answer to "which tools earn their place" exists, and
Constitution IX points at a directory that is really there.

---

## Phase 6: One harness, publicly runnable (US6)

- [ ] T043 [US6] Decide per system — `tests/e2e/skill_eval/`, `benchmark/021/`,
      `tools/gepa-optimizer/` — survive, fold in, or delete. Record the decision and act on it
- [ ] T044 [US6] Delete every system that does not survive, and fix every document pointing at one
      (FR-018)
- [ ] T045 [US6] Close the `light-skills/BENCHMARKING.md` promise spec 059 recorded as broken: it
      points at the real harness or it goes
- [ ] T046 [US6] Write `specs/121-benchmark-program/quickstart.md` and link it from the README:
      fresh clone, Docker, a model credential, one command (FR-017)
- [ ] T047 [US6] Verify on a machine with no repo-specific state that the documented steps reproduce
      the published pass rates within the reported MDE (SC-008)

**Gate**: one harness, one corpus, one command, and a reader who can check the number.

---

## Polish

- [ ] T048 Amend the Bug Class Registry with a row per new class: **unpowered number published as a
      result**, first instance `lift.py:76` subtracting two point estimates with no item count
      beside them, detector `unpowered-result`; and **split leakage**, first instance GEPA tuning
      tool descriptions against the same corpus the figures are read from, detector the
      train/holdout disjointness guard. `.specify/memory/constitution.md` is edit-protected, so the
      write goes through Bash, and the sync impact report and `Last Amended` footer move with it
- [ ] T049 Stage a `specs/next-release-notes.md` entry. The user-observable part is the nightly's
      report shape and the published figures, not the internal modules
- [ ] T050 Run `/no-ai-slop` detect on anything written for external consumption — the published
      report, the quickstart, the release-notes entry — and fix every finding
- [ ] T051 Re-run the Constitution Check's post-design pass and record any row that moved, then the
      full suite: `pytest tests/e2e/`, `python scripts/gates/antipatterns.py`, and
      `markdownlint-cli2 --fix` + `prettier --write` on every `.md` touched

## Dependencies

- Phase 0 gates everything: no image decision, no comparable results.
- Phase 1 is independent of the corpus and can ship on its own. Do it first.
- Phase 2 funds Phases 3 and 4.
- **T030 gates Phase 4 entirely.** A stop verdict means Phase 4 does not happen.
- T034's cost gate covers Phase 4. The pilot's own ~$2 precedes it, which is the one deliberate
  exception and is why the pilot is eight tasks rather than fifty.
- Phase 5 needs Phase 4's runs to exist, and is a release gate ahead of Polish.
- Spec 120's Slice 1 gates T002, T003, T004 and therefore T025 and T032 — **as written that was a
  dependency on prose.** Spec 120 was research and plan only, with its own first line reading
  "Nothing here is implemented yet... There is no `spec.md` or `tasks.md` because scope is not
  agreed", and two of its seven Slice 1 steps — the exporter and the declared driver interface — had
  no task in either spec. It now has both files, on this branch, and the real dependencies are:
  - **T031 was never blocked.** Growing the corpus needs nothing from spec 120.
  - **T032, T033** need spec 120's T016, which writes `split.toml` and its loader.
  - **T035** needs spec 120's Phase 1, the declared driver boundary, and T004 in particular: today
    `arms.py` asserts the bare arm empty by reading `OPENCODE_CONFIG_CONTENT` alone, which goes
    vacuous rather than weaker under a second harness.
  - **T039–T041** need the driver's tool-call log (spec 120 FR-013), not spec 059's IRIS telemetry.
  - **T043–T047** need spec 120's Phase 3, the exporter.
  - **All five are satisfied as of 2026-09-18.** Spec 120's Phases 1–5 are done and gated; see its
    `tasks.md` for each gate and this `research.md` § Driver interface → _Closed 2026-09-18_ for the
    file each one landed in. Nothing in this spec is blocked on spec 120 any more.
- **The harness is not settled, and the pilot's opencode is the incumbent, not the choice.**
  `prime-agent` is under evaluation; spec 120's Decision 5 and Phase 2 own the probe. Nothing in
  Phase 4 here should grow a second dependency on opencode's event stream.
- Spec 120's Decisions 1 and 2 are now closed — shared IRIS over Atelier REST as the primary shape,
  and harness optimization rather than policy training — so no task here waits on either.
