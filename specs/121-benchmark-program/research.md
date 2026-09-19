# Research: Prove the tools and skills help

Phase 0 output. Four decisions this spec consumes from spec 120, settled in writing so no
implementer has to guess, plus what verifying them against the live Harbor docs changed.

Verification method for the Harbor sections: fetched `docs.harborframework.com` on 2026-09-16 —
`core-concepts/tasks/overview.md` and `core-concepts/tasks/configuration.md`. Not inferred from
spec 120's summary, which is where two of the three corrections below come from.

## § Image decision (T001)

**Decision: `intersystemsdc/iris-community:2026.2`, digest
`sha256:5ffbd9af5a3ab685e65496d45c32ed6db455882f9f1d32864d4e4032f395bf42`.**

The conflict was smaller than either spec thought. Spec 121 named "IRIS Community 2026.2" and spec
120 named `intersystemsdc/iris-community:2025.3`, which reads as two different images. Inspecting
the running container shows it is `intersystemsdc/iris-community:2026.2` — the same Docker Hub
repository, one tag apart. There is no registry or edition disagreement to resolve, only a tag.

Verified against the live container rather than the tag string:

```
IRIS for UNIX (Ubuntu Server LTS for ARM64 Containers) 2026.2.0L (Build 208U) Thu May 28 2026
```

2026.2 wins on three grounds. It is the container this project exclusively owns (`iris-dev-iris`,
11975 TCP / 52780 web), so the grading loop and the development loop are the same loop and a task
that grades locally grades in CI. It has PWS on 52780, so Atelier REST works without
`docker_only=true`. And a benchmark measuring a tool against a build two releases behind what the
tool's users run is measuring the wrong thing.

Consequences, both recorded rather than deferred:

- **Digest pinning is mandatory, not advisory.** Community licences expire roughly 150 days after
  publish. A 2026.2 image published 2026-05-28 expires around 2026-10-25, five weeks out. Every
  published figure names the digest above (FR-020) so an expired-licence rerun is diagnosable
  instead of mysterious. When the licence expires the corpus is re-run against the next Community
  build and the figure is re-stamped; results are never merged across digests.
- **2025.3 is not a fallback.** A pass rate is only meaningful against a named build, so a
  2025.3 run is a separate measurement with its own digest stamp, never averaged into a 2026.2
  number. If CI cannot get 2026.2, CI reports no figure rather than a comparable-looking one.

Spec 120's Slice 1 step 2 should take the tag change. Nothing else in that step depends on 2025.3.

## § Task format (T002)

**Confirmed, with one addition.** The layout spec 121 assumed is right:

```
task/
├── instruction.md      REQUIRED  the prompt
├── task.toml           REQUIRED  configuration, schema_version = "1.3"
├── environment/
│   └── Dockerfile      REQUIRED
├── tests/
│   └── test.sh         REQUIRED  the verifier
└── solution/
    └── solve.sh        OPTIONAL  reference implementation
```

Pin `schema_version = "1.3"` in the golden-file test.

Two things the docs settle that spec 120's summary did not:

- **The reward contract is a file, not an exit code.** `tests/test.sh` writes
  `/logs/verifier/reward.txt` (one scalar) or `/logs/verifier/reward.json` (labelled or
  multi-dimensional). This is what makes FR-003 mechanical: a check that writes 1.0 or 0.0 from an
  IRIS assertion is a deterministic reward by construction, and there is nowhere in the contract for
  a model judgement to enter.
- **`solution/solve.sh` is OPTIONAL to Harbor and MANDATORY here.** FR-022 and SC-011 are stricter
  than the format. Corpus validation fails a task without one, because a reference solution is the
  only thing that distinguishes a hard task from a broken check — the failure mode that produced
  four skills reading 0.00 against 0.00.

## § Driver interface, and where the tool-call log comes from (T003)

Spec 120 Slice 1 step 4 declares: prompt in; transcript, tool-call log, scalar reward, `scored`
flag, optional logprobs out. Adopted unchanged. `claude_code.py`, `copilot.py` and
`opencode_runner.py` become implementations of it.

**Correction to spec 121, which named the wrong source.** The Dependencies section said "Spec 059's
tool-call telemetry as the source for Story 5's join". That is the wrong join source. Harbor's
`artifacts` config collects `/logs` out of the container, and the driver's own tool-call log is
inside the same artifact bundle as the reward that grades it — so the join key is already
co-located with what it joins to. Spec 059's telemetry lives in IRIS and describes calls that
reached IRIS, which silently drops every tool call that failed before it got there. Reach rate
computed from it would overstate reach on exactly the tools that are hardest to use.

**Story 5 joins the driver's tool-call log. Spec 059's telemetry is a cross-check, not the source.**
FR-011 is satisfiable from the driver log alone, which is the test: tool name, arguments, outcome,
and the task and arm they belong to.

### Amended 2026-09-18: "adopted unchanged" adopted a declaration nobody owned

The interface above was recorded here and given no task, in this spec or in spec 120 — which had no
`tasks.md` at all. Spec 120 now has `spec.md` and `tasks.md` on this branch, and its Phase 1 owns the
boundary. Three things move as a result:

- **Two of its four open decisions are closed.** Shared IRIS over Atelier REST is the primary shape,
  with the compose sidecar retained for Tier 2 and `docker_only=true` off the graded path — which the
  pilot's 24 sessions already demonstrated from the other direction. And the goal is harness
  optimization, not policy training: no GPUs, no trainer, `logprobs: None` on every driver, with the
  field kept so a vLLM-backed driver stays an addition.
- **opencode is the incumbent harness, not the chosen one.** `prime-agent`
  (`PrimeIntellect-ai/prime-agent`) is under evaluation. It takes stdio MCP servers as configuration
  — `~/.prime/agent/settings.json` under `mcpServers`, or `prime-agent mcp add local ... -- <cmd>` —
  so the three arms survive a harness change as configuration, which is the FR-023 argument holding
  for a second reason. Two open questions are probes rather than assumptions: whether a pinned MCP
  server is honoured in its documented headless JSON/RPC modes, and whether the 34 shipped `SKILL.md`
  packs are reachable at all, since its skills are importable Python packages. If the third arm
  cannot be built there, that is a recorded blocker on the harness, not a quietly different arm.
- **`arms.py`'s absence assertion is the concrete debt.** It reads `OPENCODE_CONFIG_CONTENT` and
  nothing else, so under a second harness FR-002's check does not weaken — it goes vacuous, passing
  on a contaminated arm. Spec 120's T004 makes the absence facts driver-supplied and fails an arm
  whose driver names none.

### Closed 2026-09-18: what spec 120 shipped, and where to find it

Spec 120's Phases 1–5 are done, so the debt above is paid rather than tracked. Both decisions are
closed in its `spec.md` § Decisions; the implementations are:

| What                    | Where                                                    | Which task here it unblocks |
| ----------------------- | -------------------------------------------------------- | --------------------------- |
| `AgentDriver` protocol  | `tests/e2e/skill_eval/driver.py`                         | T025, T032, T035            |
| Driver-supplied absence | `arms.py` via `assert_absent()`, per driver              | T035                        |
| Second driver           | `tests/e2e/skill_eval/prime_agent.py`                    | the harness question itself |
| Harbor exporter         | `benchmark/harbor/export.py`                             | T043–T047                   |
| Train/holdout split     | `split.py`, `tests/e2e/tasks/benchmark/pilot/split.toml` | T032, T033                  |
| Driver in provenance    | `provenance.driver_identity`, `baseline.driver_change`   | T039–T041                   |
| Namespace per rollout   | `tests/e2e/skill_eval/rollout_namespace.py`              | finding C4                  |

Two consequences for this spec beyond the dependency list:

- **Finding C4 is closed.** `plan.md`'s Constitution Check row VI claimed per-task namespace creation
  and a refusal to grade in a namespace the run did not create, and marked itself PASS; neither
  existed, because the pilot ran serial in one `BENCHMARK` namespace. `RolloutNamespaces` is both
  now, with `BENCHMARK` refused by name — it is where the serial pilot ran, so it holds the last
  run's answers, and reading them back looks like a pass rather than an error.
- **A run's provenance now records which harness produced it**, and a harness swap annotates a Δ
  instead of suppressing one — `driver` and `harness_version` are deliberately not comparability
  fields. The release that replaces opencode with `prime-agent` is the one a comparison most needs to
  survive.

## § Arms are task.toml, not harness code (T003, continued)

The strongest finding in Phase 0, and it makes FR-023 free.

`task.toml` has a first-class `[[environment.mcp_servers]]` section, with `transport`
(`stdio` / `sse` / `streamable-http`) and `command` or `url`. So the three arms are three
configurations of a published schema, not three code paths of mine:

| Arm          | `[[environment.mcp_servers]]` | skills on disk |
| ------------ | ----------------------------- | -------------- |
| bare         | absent                        | no             |
| tools        | iad, `transport = "stdio"`    | no             |
| tools+skills | iad, `transport = "stdio"`    | yes            |

FR-023 asked that adding an arm need no new code path. Harbor already guarantees it. `arms.py`
therefore shrinks to what Harbor cannot do for me: generating the three `task.toml` variants from
one source task, and asserting absence in the bare arm (FR-002), which no schema can check.

**Toolset for the tools arm: `Merged`.** Constitution III requires `Merged` tools to work without
`IRIS_CONTAINER`, which is the same constraint a Harbor task runs under — the agent container is not
the IRIS container. `Baseline` holds the Docker-dependent tools, which cannot reach IRIS from inside
a task container at all. This sets the denominator for every Story 5 figure: the advertised surface
is the `Merged` toolset, and Docker-only tools are reported as out of scope rather than as unreached.

## § Split mechanism (T004)

Committed file, `train` and `holdout` ID lists, with a guard test asserting the two sets are
disjoint and their union is the whole corpus (spec 120 Slice 1 step 5). Adopted unchanged.

Location: beside the corpus, at `<corpus-root>/split.toml`, so a clone carries the split and cannot
silently re-draw it. FR-021's publish path reads it and raises on a train-split task ID.

The reason this is a prerequisite rather than a refinement: GEPA optimises tool descriptions against
this corpus, and `benchmark/021`'s `merged` condition is a tuned system prompt. Any figure measured
on tasks the descriptions were fitted to overstates the tool's value, and that is the criticism that
lands hardest at conference scale.

## § IRIS reachability — an open conflict with spec 120 (found in T002)

**Harbor documents no Docker Compose or multi-service support.** A task gets one
`environment.docker_image`, plus MCP server sidecars, plus `network_mode` and `allowed_hosts`. Spec
120's Slice 1 step 2 plans "one Tier-2 task with a `docker-compose.yaml` sidecar", and the format
does not appear to offer that.

Three options, and this maps exactly onto spec 120's own open decision 1 (shared remote IRIS versus
compose sidecar):

1. **Shared reachable IRIS**, with the task container allowlisting the host. Harbor supports it
   directly via `network_mode = "allowlist"` and `allowed_hosts`. Cheapest, and it is how
   `iris-dev-iris` already works locally.
2. **IRIS baked into the task image**, one container. Hermetic and slow: a multi-GB image and a
   startup per task, times 300 sessions.
3. **A Harbor extension** for compose. Most work, and it forks the format the public-runnability
   story depends on.

**Leaning 1, not deciding it here.** It is the only option Harbor documents, and Constitution XII
(hermetic test environment) has a real objection to it: 300 sessions sharing one IRIS instance can
contaminate each other, which is what per-task namespaces are for. That objection belongs to spec
120's decision 1 and is not mine to close unilaterally. Option 1 is what the pilot uses.

## § Triage verdicts (T019–T023)

Six of the nine gated skills sat on a saturated task set. Four read 0.00 against 0.00, one 0.80
against 1.00, one 0.10 against 0.00. The gate reported all six as "no lift", which reads as "the
skill does not help" and was not what any of them measured.

**All four floors were the harness's, not the agents'.** That is the finding, and it is not a
judgement call: I probed each check directly with a hand-written reference solution and an untouched
fixture, through the real judge (`benchmark/021/runner/judge.py`, Sonnet 4.6 on Bedrock,
`PASS_THRESHOLD = 2`). Every check scored the reference 3/3/3 and the untouched fixture 0/0/0. The
rubrics discriminate. Then I ran one live baseline session per task, and two of the recorded zeros
came back passes.

| Task                | Reference vs untouched | One live baseline session                                 |
| ------------------- | ---------------------- | --------------------------------------------------------- |
| IRIS-PYTHON-CONNECT | 3/3/3 vs 0/0/0         | score 1, every text turn exactly 500 characters           |
| LIST-ITERATE        | 3/3/3 vs 0/0/0         | score 2 — pass, 32 tool calls                             |
| SQLCODE-SILENT      | 3/3/3 vs 0/0/0         | score 0 — 1 turn, 0 completed tool calls, killed at 300 s |
| GEN-01              | 3/3/3 vs 0/0/0         | score 3 — pass, 4 tool calls                              |
| GEN-02              | 3/3/3 vs 0/0/0         | not run live                                              |

Two defects account for the table, and both are fixed.

**Defect 1 — the judge was shown 500 characters.** `lift.format_transcript` cut every assistant
message to `part.get("text", "")[:500]`. An ObjectScript class does not fit in 500 characters, and
neither does a `iris.connect` script, so on every judged code-writing task the judge graded a
fragment that stopped mid-sentence and scored it 1, "partial", exactly as the rubric tells it to. The
judge said so itself, verbatim: _"only provided a partial template description before cutting off."_
Fixed to `TRANSCRIPT_TEXT_LIMIT = 8000`, which is `runner.judge._format_transcript`'s own per-turn
cap — the two agree now, so neither side silently decides what the scorer sees. It stays a cap
because the judge call is billed per token. Three tests in `test_lift.py` hold the bound, including
one asserting it is not below the judge's.

**Defect 2 — a killed session was scored as a failing agent.** `opencode_runner.run_opencode` arms a
300 s timer, kills the process tree when it fires, and then yields whatever it collected. A killed
session and a finished one are the same shape, so the harness scored the fragment. SQLCODE-SILENT's
live baseline run was one turn — "Let me begin by searching…", no completed tool calls — and went
into the baseline as a 0. This is the same class 118 fixed for a missing credential: no model read a
whole answer, so there is nothing to score. `lift.session_evidence_gap` now returns
`runner.judge.unscored` (`score: None`, never `0`) when a session neither reached
`session.status … idle` nor completed a single tool call, and the guard runs before all three scoring
paths — the judge would have called it a 1, the pattern path a 0, the assertions a 0. The rule is
deliberately conservative: a session killed _after_ real work left real evidence and is still scored,
because discarding it would cost more items than the guard saves.

**Defect 3, in the corpus rather than the harness.**
`tests/e2e/tasks/skills/objectscript-unit-test/eval.yaml` names `benchmark_tasks: [GEN-01, GEN-02]`,
which are plain class-generation prompts with no %UnitTest class in them. A skill that generates
%UnitTest classes was being measured on tasks that never ask for one. That set is retired rather than
repaired; Phase 4 writes replacements under FR-004 and FR-022.

### The recorded verdicts

They live in `tests/e2e/skill_eval/triage_records.py` as `TriageRecord`s, each with its evidence and
what was done about it, and `test_triage.py` validates them against the committed baseline on every
run. The Phase 2 gate is therefore a test and not this paragraph: a skill that drifts into saturation
later fails `test_every_saturated_set_in_the_committed_baseline_has_a_verdict` rather than passing
quietly.

| Skill                      | base | skill | Pairs | Saturation       | Verdict      |
| -------------------------- | ---- | ----- | ----: | ---------------- | ------------ |
| ensemble-production        | 0.10 | 0.00  |    10 | floor_censored   | not_helped   |
| iris-ai-hub                | 0.40 | 0.30  |    30 | —                | not_helped   |
| iris-connectivity          | 0.00 | 0.00  |     5 | floor            | broken_check |
| iris-vector-ai             | 0.10 | 0.30  |    10 | —                | —            |
| objectscript-guardrails    | 0.80 | 1.00  |     5 | ceiling_censored | too_easy     |
| objectscript-list-patterns | 0.00 | 0.00  |     5 | floor            | broken_check |
| objectscript-review        | 0.60 | 0.80  |     5 | —                | —            |
| objectscript-sql-patterns  | 0.00 | 0.00  |     5 | floor            | broken_check |
| objectscript-unit-test     | 0.00 | 0.00  |    10 | floor            | broken_check |

**The two negative lifts are noise, and the evidence says against what.** `ensemble-production` reads
−0.10 off one discordant pair in ten, against `mde_paired(10, 0.10) = 0.2482`; Wilson gives
[0.018, 0.404] against [0.000, 0.278]. `iris-ai-hub` reads −0.10 off three pairs in thirty, against
`mde_paired(30, 0.10) = 0.1555`. Neither is distinguishable from zero and neither is published as a
regression. `n_for_effect_paired(0.20, 0.10) = 18` is what resolving the gate threshold costs at the
measured discordance, so `iris-ai-hub` is already past it on item count and is the cheapest of the
nine to turn into a real measurement — every one of its 30 items was scored through the
500-character judge, so it is re-measured in Phase 4 rather than believed now.

**The ceiling case is `too_easy`, not `not_helped`.** `objectscript-guardrails` passes 4 of 5 without
the skill. The largest lift the set can ever report is 0.20, exactly `comparison.GATE_THRESHOLD`,
while `mde_paired(5, 0.20)` is 0.4334 — the set cannot resolve its own maximum possible effect, so
"the skill did not help" is not a claim it can support. The task is a valid check; it is not a
measurement of this skill.

**Every recorded 0.00 in `skill-baseline.json` is withdrawn.** Not corrected — withdrawn. The runs
that produced them were graded on truncated transcripts, and re-grading is not available because the
result files never persisted per-item transcripts (see § below on the Story 5 join). The four floor
skills and the two negative-lift skills have no gated number until Phase 4 re-measures them, which is
the honest state. Deleting a set is an acceptable outcome under T023; publishing 0.00 was not.

### What "acted on" means mechanically

Four changes, each with a test, because a verdict acted on in prose is a verdict not acted on.

| Verdict                          | Action                                                                     | What holds it                            |
| -------------------------------- | -------------------------------------------------------------------------- | ---------------------------------------- |
| iris-connectivity, list-patterns | `TRANSCRIPT_TEXT_LIMIT` 500 → 8000                                         | 3 tests in `test_lift.py`                |
| sql-patterns                     | `session_evidence_gap` returns unscored for a killed session               | 6 tests in `test_lift.py`                |
| unit-test, guardrails            | `benchmark_tasks: []` in each `eval.yaml`, with the verdict in the comment | `RETIRED_TASK_SETS` cross-file test      |
| all six, plus iris-ai-hub        | a `withdrawn` block on the baseline entry                                  | `comparability()` + two cross-file tests |

**Withdrawal is a `withdrawn` block on the baseline entry, not a deletion.** `baseline.withdrawal()`
reads it and `comparability()` returns it first, so a Δ against a withdrawn figure is refused with
the reason attached, and `compute_diff` treats a withdrawn entry as no prior measurement at all —
the same shape as a skill measured for the first time, and for the same reason: there is nothing to
subtract from. The entry itself stays, because it is the provenance of a run that really happened and
`coverage_census` still needs the skill accounted for. A real re-measurement replaces the whole
entry, so the withdrawal disappears when the number it withdrew does.

Two cross-file tests keep the verdicts and the artifact from drifting apart: every skill in `RECORDS`
must be withdrawn in the committed baseline with a matching verdict, and no skill outside `RECORDS`
may be withdrawn — an unexplained withdrawal is data loss with no reason recorded.

**`objectscript-guardrails` and `objectscript-unit-test` now have `benchmark_tasks: []`.** The
harness already handles that: `__main__.py` skips `measure_lift` and the result carries
`lift: None`, so the two appear with no number rather than with a zero. `coverage_census` still
passes because both keep their (withdrawn) baseline entry.

**Not done here, and deliberately: the four floor sets are not re-measured.** One live session each
was enough to show the recorded floors do not reproduce, which is what the verdicts needed. A real
re-measurement is 2 arms × 5 runs per task of billable sessions and belongs to Phase 4's ladder,
after Phase 3's go/no-go decides whether the corpus is worth building at all. Spending it now would
buy numbers from a corpus Phase 2 has just established is the wrong corpus.

## § Nightly canary set (T017)

**The set is `MCP-01`, `SKILL-01`, `FULL-01`**, declared in
`tests/e2e/skill_eval/nightly_canary.py` as `CANARY_TASKS` and named nowhere else. The workflow
invokes the module rather than listing the tasks, so adding a canary is a Python edit and not a YAML
edit that can disagree with it.

Three tasks, one per layer the night can break at:

| Task       | What it proves               | Assertions                                     |
| ---------- | ---------------------------- | ---------------------------------------------- |
| `MCP-01`   | a tool call reaches IRIS     | `tool_called: iris_compile`                    |
| `SKILL-01` | a skill is found and invoked | `skill_invoked: objectscript-review`           |
| `FULL-01`  | a two-tool chain in order    | `tool_called: docs_introspect`, `iris_compile` |

**Assertion-scored, not judged.** Every assertion is `tool_called`, `skill_invoked` or
`output_contains` against the event stream — no model reads the transcript, so a night needs three
agent sessions, no scorer credential and no grading spend. That is the property that makes the
nightly affordable to keep: the old shape spent ~$3.70 and about two hours of runner time to publish
a lift it could not measure, and half of that was the judge.

It also removes a failure mode 118 spent a spec on. A missing scorer credential used to arrive as
`score: 0`, indistinguishable from an agent that genuinely failed; the canary has no scorer to be
missing.

**Credentials are checked per task, on the model the task itself declares.** All three canary
tasks name `amazon-bedrock/us.anthropic.claude-sonnet-4-5`, and `run_task` lets a task's own
`model:` override the caller's default — so `missing_credentials()` resolves each task's model to
the env var that would authenticate it and exits 2 if none is present. Gating on `OPENAI_API_KEY`,
which is what the old job passed, would have refused a night holding a working Bedrock token and
started a night holding a key none of its sessions use.

**The tool-surface floor is `MINIMUM_TOOL_COUNT = 75` against the 81 that 1.4.2 advertises.** A
floor and not an equality, on purpose: adding a tool must not fail the nightly, while "no tools at
all" and "half the surface vanished" both have to. `tool --list --json` needs no IRIS connection
(spec 114), so the check costs a process spawn. This is the check that would have caught the bug
that ran for weeks — `isolated_env.py` held a literal Homebrew path no runner has, so every session
was a bare model and the judge scored it as the skill failing. `probe_tool_surface()` returns `None`
for "could not ask" and the report counts `None` as breakage, never as a pass.

**No lift number of any kind**, not an underpowered one and not a withheld one. `lift_mentions()`
walks the report's keys and string values for `lift`, `pass_rate` and `delta`, and
`CanaryReport.assert_no_lift()` raises rather than publish one — a claim smuggled into a detail
string is the one way FR-016 fails silently. Lift is reported by the full benchmark, at a release
and before a conference, over a corpus large enough to support it.

**Exit code is part of the guard.** `exit_code()` is 1 on any breakage, 2 on a misconfiguration that
started no session (so nothing was spent), 0 only when all five checks pass. A guard that reports
breakage and exits 0 is not a guard, which is why that is a test rather than a comment.

## § The three failing nights, re-read (T018)

Runs `34744344877`, `34817991701` and `34939912456` failed on three consecutive nights. Between them
they reported five regressed rows. Every row's arm rates and item count is transcribed from that
shard's own summary table into `NIGHTS` in `tests/e2e/skill_eval/test_nightly_history.py`, so the
claim below is a test rather than a paragraph:

| Run         | Skill                   | Scored | Pairs | base | arm  | lift  | Δ base | Discordant | MDE  | New verdict  |
| ----------- | ----------------------- | -----: | ----: | ---- | ---- | ----- | -----: | ---------: | ---- | ------------ |
| 34744344877 | objectscript-guardrails |     10 |     5 | 0.40 | 0.40 | 0.00  |  -0.20 |          0 | none | underpowered |
| 34817991701 | iris-vector-ai          |     20 |    10 | 0.00 | 0.10 | +0.10 |  -0.10 |          1 | 0.25 | underpowered |
| 34817991701 | objectscript-review     |     10 |     5 | 0.80 | 0.60 | -0.20 |  -0.40 |          1 | 0.43 | underpowered |
| 34939912456 | iris-vector-ai          |     20 |    10 | 0.10 | 0.00 | -0.10 |  -0.30 |          1 | 0.25 | underpowered |
| 34939912456 | objectscript-review     |     10 |     5 | 0.80 | 0.80 | 0.00  |  -0.20 |          0 | none | underpowered |

The `scored` column is what the shard printed and it sums both arms (`_item_counts` in
`reporter.py`), so ten scored items is five per arm and five task-pairs. All five rows are
`Verdict.UNDERPOWERED` against FR-008's floor of 37, so `passed` is False and no regression is
asserted either. The reconstruction is checked against each row's printed lift before anything is
concluded from it, and it builds the _fewest_ discordant pairs the two rates allow — the pairing most
favourable to the old gate. If a row is underpowered under its own best case, it was underpowered.

Two things are worth stating precisely, because the first draft of that test file got both wrong:

- **It is not true that every Δ was inside the new threshold.** `iris-vector-ai`'s -0.30 over ten
  pairs exceeds its 0.25, and the two zero-discordance rows sit exactly on the 0.20 fallback rather
  than inside it. That makes none of them a regression — the verdict is underpowered before any Δ is
  weighed. The fix for a red nightly was never "raise the threshold until the Δs fit under it".
- **Two of the five have no MDE at all.** `mde_paired` is undefined at zero discordance: with no
  task-pair disagreeing there is no variance to invert. Those rows resolve nothing, which is not the
  same as resolving 0.00, and `threshold_applied` falls back to `GATE_THRESHOLD`.

The scale claim is held apart from the rows, in
`test_more_pairs_resolve_more_at_a_fixed_discordance`, because the ten-pair rows also ran at half the
discordance of the five-pair ones — comparing their MDEs directly conflates count with disagreement.
What the three defined MDEs do show is the size of the old gate's error: 0.25 and 0.43, against the
0.05 it was gated on. Every difference that gate could see was one the harness could not.

### The pairing bug the repeat run found

Running a gated comparison for real (`--skill objectscript-review --runs 5`) produced a result file
claiming `items_total: 5` per arm beside `n_pairs: 1`. `_pair_key` in `lift.py` keys an item on
`(task_id, run_index)` and its docstring says why — "item count is what buys resolution" — but
`measure_lift` looped `for _ in range(n_runs)` and never stamped `run_index`. All five items keyed
`("STATUS-CHECK", None)`, and `_arm_outcomes` assigned them into a dict, so four were overwritten in
silence. The floor FR-008 gates on counts pairs, so the collapse cost 5× resolution with nothing on
screen to say it had happened.

Two fixes, tests first: `measure_lift` stamps `task_id` and `run_index` on every item, and
`_arm_outcomes` records a key collision as a named hole instead of overwriting. The second is the one
that matters for next time — the first bug was invisible precisely because a dict assignment is
silent. There were no tests over `_pair_key`, `_arm_outcomes` or `_paired_comparison` before this;
there are five now.

This is also why the table above reads pairs as `scored / 2`: with the stamp in place, five runs of
one task are five pairs, which is what the nightly's item counts always implied.

### The repeat measurement

US3's Independent Test: run one gated comparison twice with nothing changed and check that the two
lifts fall within the reported MDE of each other. Two runs of
`python -m tests.e2e.skill_eval --skill objectscript-review --runs 5 --model openai/gpt-4.1` against
`iris-dev-iris`, ~55 minutes and about $0.40 of judge and agent spend each:

| Run              | base | skill | lift  | Pairs | b   | c   | Discordance |  MDE | Interval       | Verdict      |
| ---------------- | ---- | ----- | ----- | ----: | --- | --- | ----------: | ---: | -------------- | ------------ |
| 2026-09-16T17:30 | 0.40 | 0.20  | -0.20 |     5 | 0   | 1   |        0.20 | 0.43 | [-0.55, +0.15] | underpowered |
| 2026-09-16T18:14 | 0.00 | 0.40  | +0.40 |     5 | 2   | 0   |        0.40 | 0.61 | [-0.03, +0.83] | underpowered |

**The test passes, for an uncomfortable reason.** The two lifts are 0.60 apart with opposite signs,
and 0.60 is inside the wider run's own reported resolution of 0.613. The harness never claimed to
tell those two runs apart, so it was not caught contradicting itself — and both runs are marked
`publishable: false`, so neither number may be quoted.

That is the case for FR-008 stated in measurements rather than in theory. Same command, same
container, same model, one hour apart: one run reads -0.20 and the next reads +0.40. Against the old
0.05 gate the first is a regression and the second a large improvement. Both are coin flips. The
three red nights this section opens with were the gate reporting exactly that.

It also confirms the reconstruction used for those nights. `pairs_for` builds the fewest discordant
pairs two rates allow, and for both of these runs — where the real split is on file — that is the
split the harness actually recorded (0/1 and 2/0). The MDE it derives for the first run, 0.4334, is
the same value the 34817991701 `objectscript-review` row reconstructs to, because it is the same
shape of measurement.

Both runs and the five nights are transcribed into `test_nightly_history.py` as `REPEATS` and
`NIGHTS` and checked there, so nothing in this section is asserted only in prose. Twenty-eight tests,
no live service.

One thing this leaves open: per-item scores are not persisted in the result file, only the arm
aggregates and the derived comparison. That is why the pre-fix run could not be re-paired after the
fact and had to be re-run. Story 5's join needs the per-item rows anyway, so the fix belongs with it,
not here.

## § Pilot result and go/no-go (T030)

**This is a design decision, not a result (FR-024).** Nothing in this section may be published as a
measurement of the tools. Eight tasks is a fifth of FR-008's floor of 37, both comparisons carry
`purpose="design_decision"`, and `Comparison.publishable` is False for both. What the pilot buys is
one decision: whether the full corpus is worth building.

Run on 2026-09-16 against `iris-dev-iris`, `openai/gpt-4.1`, 300 s per session, 24 sessions, 53
minutes wall clock. All 24 were scored — no holes, no unscored runs, no `CheckBroken`. Every task was
re-validated live against IRIS before each of its three sessions, so FR-004 and FR-022 held 24 times
over and not once. Raw runs in `tests/e2e/results/pilot-121.json`.

| Comparison           | n   | b   | c   | one-sided exact p | verdict  |
| -------------------- | --- | --- | --- | ----------------- | -------- |
| bare → tools         | 8   | 7   | 0   | 0.0078            | **go**   |
| tools → tools+skills | 8   | 1   | 1   | 0.7500            | **stop** |

`b` is the upper arm passing where the lower failed. Both verdicts come from
`Comparison.pilot_verdict`, which is the FR-024 rule and not a second copy of it.

### bare → tools: go

7 of 8 tasks flipped, none flipped back. The rule wants `c ≤ 1`, `b ≥ 5` and p ≤ 0.07; this is
(7, 0) at p = 0.0078. **Phase 4 proceeds.**

Two things about that number that a reader should not have to reconstruct:

- **The 300 s clock did some of the work.** The bare arm was killed on the timer in 5 of the 7
  discordant pairs (PILOT-01, 04, 05, 07, 08). In four of those five it had completed 0–2 tool calls
  when the clock ran out, so it was not close; but "did not finish in five minutes" is a weaker claim
  than "could not do it", and the full run should record time-to-solve rather than only pass/fail. The
  clock is not tilted: it is the same 300 s in all three arms, and the tools arm was killed on it too
  (PILOT-06). The tools arm solved these same eight tasks in 20–125 s.
- **The interval reads `[+0.646, +1.104]`, which is impossible.** McNemar's Wald interval is not
  clamped to [-1, 1] and at `c = 0` over 8 pairs it runs off the end. Another reason this is a
  decision and not a figure: the MDE is 0.795 against a floor of 170 pairs at this discordance rate.

### tools → tools+skills: stop, and what it is a stop about

One flip each way, and they cancel. On the rule (`b ≤ c` → stop) this leg does not justify spending
on a skills comparison — but the honest reading is narrower than "the skills do not help", because
**no pilot task names a skill**. That is asserted, not incidental:
`test_no_pilot_task_names_a_skill`. All eight were written to discriminate tools from no tools, the
skills arm installs the whole 34-skill pack rather than the skill that suits the task, and a corpus
that does not vary the thing under test cannot see it. The two discordant cells are worth reading
individually:

- PILOT-03 (`$List` loop): tools passed in 3 calls; tools+skills failed after 41 calls and 206 s. The
  skill index sent it down a longer path on a task it had already solved without one.
- PILOT-06 (`%Status`): tools was killed on the clock after 7 calls; tools+skills passed in 4.

So the decision is: **build the tools corpus, and do not build a skills corpus out of these tasks.**
Story 4's question needs tasks where a skill is the discriminator — a documented convention the model
cannot infer from the task text — and writing those is a corpus-design job that this pilot has now
shown cannot be skipped. Reporting a tools→tools+skills figure off tool-discriminating tasks would
produce exactly the 0.00-against-0.00 shape spec 118 was cleaning up.

### What the pilot also establishes

- **The eight checks work.** 24 sessions, 24 readable PASS/FAIL verdicts, no `CheckBroken`. The
  fixture/reference validation caught nothing this run because it had already caught PILOT-05 during
  T028.
- **FR-002 held both ways in every session.** `assert_absent` and `assert_present` ran on the exact
  environment each session received, and no run was voided for contamination.
- **The bare arm is a real arm, not a strawman.** It made 12 and 18 completed tool calls on PILOT-03
  and PILOT-06 through `bash` alone, and on PILOT-06 it got as far as the tools arm did. The prompt
  gives every arm the same connection details and the same container name; what the bare arm lacks is
  the tools.
- **Cost is not recorded.** The pilot runner reads tool calls and wall clock out of the event stream
  but not token usage, so the ~$2 estimate stands unverified. Story 5's cost work needs per-session
  usage anyway, and this is the second place — after the per-item scores noted above — where the
  event stream is not being mined for something a later story requires.
