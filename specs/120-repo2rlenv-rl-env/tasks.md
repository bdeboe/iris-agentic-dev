# Tasks: One task format, one agent boundary, one split

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**:
[research.md](./research.md)
**Branch**: `121-benchmark-program` (adopted; no separate branch — spec 121's Phase 4 is what these
unblock)

Slice 1 of `plan.md`, scoped by the two decisions closed in spec.md § Decisions and reordered so the
harness boundary comes first. `plan.md`'s step order put the exporter first; that was written before
the harness was in question. The boundary is now the thing with a deadline, and the exporter is the
thing that is portable once the boundary exists.

Python only. No change to either Rust crate, so `cargo test` is unaffected and no aggregator gains a
`mod` line.

Test-first within every phase, phase gate at the end of every phase. `[P]` marks tasks that can run
in parallel with their siblings.

---

## Phase 1: The agent boundary (US2) — the harness swap depends on it

Today `tests/e2e/skill_eval/arms.py` reads `OPENCODE_CONFIG_CONTENT` and nothing else. Under a
second harness that assertion does not weaken, it goes vacuous: it would pass on a contaminated arm,
which is FR-002 of spec 121 inverted and the exact shape of the 118 bug.

- [x] T001 [P] [US2] Unit tests for the driver contract in `tests/e2e/skill_eval/test_driver.py`,
      against a fake driver: a run carries transcript, tool-call log, reward, `scored` and
      `logprobs`; `scored=False` holding a reward raises; `scored=True` holding no reward raises;
      `logprobs is None` is valid and is what every subprocess driver returns; a driver that names
      no absence paths fails the arm rather than passing it
- [x] T002 [US2] Implement `tests/e2e/skill_eval/driver.py`: the `AgentDriver` protocol and the
      `DriverRun` dataclass per FR-006, with the two refusals of FR-010 enforced at construction so
      no caller can record an unscored run as a zero
- [x] T003 [US2] Make `tests/e2e/opencode_runner.py` an implementation of it with no observable
      behaviour change, and assert that in a test: the pilot's own event-stream reading
      (`completed_tool_calls`, `hit_the_clock`) produces the same numbers through the boundary as it
      does today
- [x] T004 [US2] Move the bare arm's absence assertion behind the driver per FR-009: each driver
      names its configuration paths, environment variables and skill locations, and
      `assert_absent()` raises on any of them. Unit tests: the opencode driver still catches
      `OPENCODE_CONFIG_CONTENT`, a driver naming nothing fails the arm, and a driver naming a path
      that holds an MCP registration raises with the path in the message
- [x] T005 [US2] Adapt `claude_code.py` and `copilot.py` to the interface, returning
      `logprobs: None`, with a test per driver that the contract holds. Neither is on the graded
      path today; they are here because an interface with one implementation is a guess

**Gate**: one pilot task across all three arms through the boundary, under the opencode driver,
matching the verdict `tests/e2e/results/pilot-121.json` recorded for it. Three live sessions, ~$0.25.

---

## Phase 2: `prime-agent` as a second driver (US2, FR-008)

Decision 5. Three facts are verified from its docs; the rest is a probe, and a negative result here
is a result, not a failure.

- [x] T006 [US2] Probe `prime-agent` and write `research.md` § prime-agent probe: does a headless
      run (JSON or RPC mode) honour a stdio MCP server pinned in `~/.prime/agent/settings.json` or
      added by `prime-agent mcp add local ... -- <cmd>`; does it emit a machine-readable tool-call
      log; what identifies a completed call. Capture one real event/log sample as a fixture for
      T007. A missing headless MCP path stops the adoption and is recorded as a blocker with the
      exact command tried
- [x] T007 [P] [US2] Unit tests for `tests/e2e/skill_eval/prime_agent.py` against the T006 fixture:
      the three arms generate three settings files, the tools arm registers exactly one iad server
      over stdio, the bare arm's absence facts include `~/.prime/agent/settings.json`, and the
      tool-call log parses to the same shape the opencode driver returns
- [x] T008 [US2] Implement the `prime-agent` driver
- [x] T009 [US2] Settle the third arm and record it in `research.md` § prime-agent probe:
      `prime-agent` treats skills as importable Python packages, iad ships 34 `SKILL.md`
      directories. Either the pack is reachable as configuration — in which case say how — or the
      `tools+skills` arm cannot be built on this harness, which is a blocker on Decision 5 and not a
      quietly different arm

**Gate**: the same one task × three arms under the `prime-agent` driver, or a recorded blocker in
`research.md` naming what is missing. Either outcome unblocks the next phase; a silent partial arm
does not.

**Gate met 2026-09-18.** PILOT-01 × three arms, `tests/e2e/results/pilot-120-phase2-gate.json`:
`bare` FAIL 0 cells, `tools` FAIL 2 cells, `tools+skills` PASS 8 cells, none unscored. Both failures
are the model ending its turn with a question to the user, quoted in `research.md` § Phase 2 gate
along with the three harness rules the run turned up (socket-path length, the leaked daemon, and
cleanup that cannot fail a run).

---

## Phase 3: The exporter (US1)

- [x] T010 [P] [US1] Unit tests for `benchmark/harbor/export.py`: parse the emitted `task.toml`
      **string** and assert its fields (the #110 pattern — never a dict literal),
      `schema_version = "1.3"`, and that the three arms come out as three
      `[[environment.mcp_servers]]` variants of one source task
- [x] T011 [P] [US1] Golden-file test over one complete exported task directory, so an upstream
      format drift is a diff and not a run that grades nothing
- [x] T012 [P] [US1] Unit tests for the refusals of FR-005: a task with no reference solution is
      refused, and a task whose check passes against the untouched fixture is refused with the task
      ID in the message
- [x] T013 [US1] Implement `benchmark/harbor/export.py`. One source task in, one Harbor directory
      out: `instruction.md`, `task.toml`, `environment/`, `tests/test.sh`, `solution/solve.sh`.
      Fixtures stay inline data written into `environment/` at build time; no per-task image
- [x] T014 [US1] The reward contract per FR-004: `tests/test.sh` wraps the ObjectScript `PASS`/`FAIL`
      check and writes `/logs/verifier/reward.txt`. Unit test that a `PASS` writes `1.0`, a `FAIL`
      writes `0.0`, and unreadable check output writes no reward file at all rather than a zero

**Gate**: `harbor run --env docker` green on one exported task locally, end to end, reward read from
the file. Skipped with a named reason when Docker is absent, never silently.

**Gate met 2026-09-18, one part skipped with a reason.** The exported `GOLDEN-01`/`tools` directory
was driven end to end against `iris-dev-iris`: `seed.sh` applied the fixture, a second `seed.sh` was
a no-op (the marker held), `tests/test.sh` wrote `reward.txt` = `0.0`, `solution/solve.sh` applied
the reference, and the same `tests/test.sh` wrote `1.0`. Reward read from the file both times, never
from an exit code. **Skipped:** `harbor run --env docker` itself — the harbor CLI is not installed
here (`which harbor` → not found), so Harbor's own orchestration of the directory is still unverified
and `[environment] network_mode` is the value most likely to need a change when it is. Docker is up;
harbor is the missing piece. See `research.md` § Phase 3 gate.

---

## Phase 4: The split, and provenance that names the harness (US3, US4)

- [x] T015 [P] [US3] Unit tests for the split loader: every corpus task ID in exactly one side, an
      ID in both raises, an ID in neither raises, and the error names the ID
- [x] T016 [US3] Implement the loader and write `split.toml` beside the corpus for the tasks that
      exist today. Spec 121's T031 grows the corpus; this file is what it grows into, and spec 121's
      T032 and T033 are the guard and the publish refusal over it
- [x] T017 [P] [US4] Unit tests for provenance per FR-012: driver kind and harness version are
      recorded, and a difference in either annotates a Δ rather than suppressing it — the same rule
      `tool_surface` already follows
- [x] T018 [US4] Extend `tests/e2e/skill_eval/provenance.py` accordingly

**Gate**: the guard test goes red when a task ID is duplicated across sides or dropped from both, and
green otherwise.

**Gate met 2026-09-18.** Both directions were driven against the committed
`tests/e2e/tasks/benchmark/pilot/split.toml`, by editing it and running `test_split.py`:

| Mutation                           | Result                                                                               |
| ---------------------------------- | ------------------------------------------------------------------------------------ |
| `PILOT-04` added to the train side | red — `PILOT-04 is in both sides. The publish guard reads holdout and would pass it` |
| `PILOT-08` removed from holdout    | red — `PILOT-08 is in neither side`                                                  |
| file restored                      | green — 15 passed                                                                    |

Both messages name the offending ID, which is the half of FR-011 that makes the failure fixable
rather than a coverage count to diff by hand. FR-012 landed alongside: `Provenance` now carries
`driver` and `harness_version`, `baseline.driver_change` annotates a Δ across a harness swap, and
neither field is in `COMPARABILITY_FIELDS` — the release that replaces `opencode` with
`prime-agent` is the one a Δ most needs to survive. 596 unit tests pass.

---

## Phase 5: Isolation at concurrency (Decision 1's one unproven part)

The pilot ran serial in one `BENCHMARK` namespace, so namespace-per-rollout is asserted nowhere. This
is also where spec 121's open finding C4 lands — its Constitution Check claims per-task namespace
creation and refusal that no task implements.

- [x] T019 [P] Unit tests for the rollout namespace: the name is derived from the task and rollout so
      two rollouts cannot collide, and a driver asked to grade in a namespace it did not create
      refuses
- [x] T020 Implement create/reset/drop per rollout on top of the existing tools, and a live-IRIS test
      that two concurrent rollouts cannot see each other's documents. Free — live IRIS, no model
      tokens

**Gate**: the concurrency test passes against `iris-dev-iris` with `--test-threads=1` discipline for
anything that shares env vars.

**Gate met 2026-09-18.** `tests/e2e/skill_eval/test_rollout_namespace_live.py` — 4 live tests, 14.8 s,
no model tokens. Two rollouts of one task write a class of the same name with different bodies, both
writes complete before either read (a `threading.Barrier` between the write and the read), and each
reads its own. Driven red the way that matters: pointed at one shared namespace instead of two, the
verdicts come back `['PASS', 'FAIL:ROLLOUT-ZERO']` — one rollout grading the other's document, which
is the failure the namespace-per-rollout design exists to prevent. The container is left with the
three namespaces it started with.

"On top of the existing tools" turned out not to be possible, and that is the finding. Three defects
in the namespace surface, all found by running it:

| What                                                                              | Consequence                                                    |
| --------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `iris_namespace_create` needs the database to exist and no tool creates one       | `ERROR #420: Database IADB… does not exist`                    |
| `Config.Namespaces.CreateOne` edits the CPF only; the tool reports success anyway | `{"created": true}`, then `<NAMESPACE>` on first use           |
| No `iris_namespace_delete`                                                        | a rollout namespace can only be removed through `iris_execute` |

So `create_namespace` makes the database, creates the namespace, activates it, and then asks
`iris_namespace_list` whether it is really there — the list is the authority, the create's own verdict
is not. `drop` clears the documents and keeps the namespace for the next run of that index; `purge`
and `delete_namespace` remove namespace, database and directory, and refuse any name this module did
not derive. 632 unit tests pass (36 of them here).

One unrelated repair on the way through: `benchmark/harbor/test_reward_file.py` stubs the CLI on
`PATH`, and `test.sh` reads `IAD_BINARY` first — so with that variable exported, five of its six
cases silently ran the real binary against live IRIS and read `1.0` for every reward. It now drops
`IAD_BINARY` from the child's environment.

---

## Phase 6: Hand back to spec 121

- [x] T021 Update spec 121: replace `tasks.md:262` ("Spec 120 Slice 1 gates T002, T003, T004 and
      therefore T025 and T032") with the tasks here that actually gate it, and record in its
      `research.md` § Driver interface that Decisions 1 and 2 are closed and where
- [x] T022 [P] Measurement, cheap negative allowed: run
      `repo2rlenv generate --pipeline commit_runtime` over the `fix:` history and record what it does
      with a Rust workspace. `research.md` measured 58 candidates, 26 needing no IRIS. Its own docs
      call Rust parsers experimental, so an unusable result is the expected one and is worth
      recording once rather than assuming twice
- [x] T023 Full safe suite, `python scripts/gates/antipatterns.py`, and
      `markdownlint-cli2 --fix` + `prettier --write` on every `.md` touched

**T022 measured 2026-09-18: 50 candidates, 0 tasks emitted.** `repo2rlenv` 0.9.1, $0.012 of LLM
spend, eight minutes. The predicted blocker — experimental Rust parsers — never came up; the
bootstrap agent installed rustup and got `cargo test --no-run` to compile on its own. What blocks it
is `f2p=0` on every commit it validated: `pre=2373 post=2373`, no test flipped across the fix,
because the tests that discriminate here are `#[ignore]`d and need live IRIS and `--features
testing`, and the sandbox image has neither. 31 of the 50 were rejected as `non_bugfix_type` before
that even mattered. Mining is downstream of the Tier 1 image, not a shortcut past it. Full numbers
and the exact command in `research.md` § _What `commit_runtime` actually does with this repo_.

**T023 run 2026-09-18.** 632 Python tests pass — the safe skill-eval list plus `benchmark/harbor`,
including the 4 live namespace tests against `iris-dev-iris`, 18.5 s. `antipatterns.py` clean across
all 16 detectors. `markdownlint-cli2 --fix` and `prettier --write` on all five spec files touched;
`prettier --check` clean across both spec directories afterwards. One file is deliberately left
unformatted: `benchmark/harbor/golden/golden-01-tools/instruction.md` is exporter output compared
byte for byte by `test_golden.py`, so reformatting it would break the test it exists to be — a golden
file is not prose. The container ends with the three namespaces it started with.

**Slice 1 is complete.** Six phases, 23 tasks, every gate met and recorded above. Spec 121 is
unblocked in all five places its `tasks.md` named.

---

## Dependencies

- **Phase 1 gates Phase 2.** A second driver before a declared interface is two harnesses hard-coded
  instead of one.
- **Phase 2 gates nothing else here.** A `prime-agent` blocker leaves opencode driving; the exporter,
  the split and provenance do not care which driver runs.
- Phase 3 needs spec 121's `graded_task.py` and `arms.py`, both landed.
- Phase 4's T016 needs the corpus to exist; it does, at pilot size.
- Phase 5 is independent and free to run. Do it whenever IRIS is up.

## What this unblocks in spec 121

| Spec 121 task                              | Needs                        |
| ------------------------------------------ | ---------------------------- |
| T031 grow the corpus to 50 tasks           | nothing here — start anytime |
| T032 commit the split, with the guard test | T016                         |
| T033 publish-path leakage guard            | T016                         |
| T035 the full arm ladder                   | Phase 1 (T004 especially)    |
| T039–T041 per-tool attribution             | T002's tool-call log, FR-013 |
| T043–T047 one publicly runnable harness    | Phase 3                      |

Spec 121's T031 was never blocked. That is worth stating plainly: the corpus could have grown while
this spec had no scope, and the dependency line in its `tasks.md` implied otherwise.

## Cost

Phase 1's gate and Phase 2's gate are three live sessions each, about $0.25 apiece at the pilot's
measured rate. Everything else in this spec is unit tests, live-IRIS tests that cost nothing, and one
`harbor run` locally. Spec 121's $80 cap is untouched by this work.
