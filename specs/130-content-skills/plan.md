# Plan: 130 content skills

Every fact comes from `research.md`. Nothing goes into a skill without a row there.

## Skill edits

| Skill                       | Change                                                                                                                                                                                                                                                                             | Research |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| `objectscript-sql-patterns` | §4: check `%SQLCODE` after execute, loop on `%Next(.tSC)`, check `tSC`, then read `%SQLCODE` after the loop. §5: `Set tSC = stmt.%Prepare(...)` and check it                                                                                                                       | R1       |
| `objectscript-unit-test`    | Tool is `iris_test`, and the pattern is `:Package.Class`. Only `Test*` methods run, and an empty run reports passed. Compile goes through `iris_doc put`, not a local path                                                                                                         | R3       |
| `iris-objectscript-eval`    | Lines 39–40 get the `:Package.Class` pattern                                                                                                                                                                                                                                       | R3       |
| `objectscript-tdd`          | A clean compile does not prove anything: an undefined local or dynamic dispatch fails only at runtime                                                                                                                                                                              | R4       |
| `ensemble-production`       | State table gets 0, 5 and 6. The ObjectScript API uses `GetProductionStatus(.name,.state)` and `IsProductionRunning`. The already-running error is explained. `GetActiveProductionName` is described as the last-started production, not a running check                           | R6       |
| `objectscript-guardrails`   | Adds a "Namespace" rule: `New $NAMESPACE` before `Set $NAMESPACE`                                                                                                                                                                                                                  | R2       |
| `iris-agentic-dev`          | Adds a section on loading an XML export: `iris_doc put` it under the `.cls` name with the XML declaration on its own line. A `.xml` name is #16006; a one-line export is #16021                                                                                                    | R7       |
| `iris-query-plans` (new)    | Reading `mode=explain`: master map vs index map, and Cost. A class-added index is empty until `%BuildIndices`. `INSERT %NOINDEX` leaves it stale. `WHERE %NOINDEX` is the check. DDL `CREATE INDEX` builds at once. `TUNE TABLE`. An outlier value reads the master map on purpose | R5       |

The new skill is registered in `bundled.rs`, `skills.sh.json`, `iris-agentic-dev.toml`, `cmd/skill.rs`, `skills/iris-dev.toml`, `skills/README.md` and `docs/skills.md`.

## Tests

- **Unit**, in `crates/iris-agentic-dev-core/tests/unit/test_content_skills_130.rs`: forbidden strings and required strings per skill, plus the frontmatter and registration of `iris-query-plans`. Add a `mod` line.
- **Live**, in `crates/iris-agentic-dev-core/tests/integration/test_content_skills_130_live.rs`: one `#[ignore]` test per research row. Each test creates its own `IadLive130.*` objects through the Atelier helpers the 127 live tests use, and drops them afterwards. Add a `mod` line.
- **Ladder**: SKILL-13 to SKILL-19 go on the holdout side of `split.toml`. The existing live test checks each task before and after, and the shape test checks their form.

## Ladder tasks

| Task     | Skill                       | The agent must                                                                                            | Check                                                                                     |
| -------- | --------------------------- | --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| SKILL-13 | `iris-query-plans`          | make `Bench.Plan.Orders` counts right after the fixture's class-added index and `%NOINDEX` load           | count via the index equals the `%NOINDEX` count                                           |
| SKILL-14 | `objectscript-unit-test`    | find why the test class reports passed while `Bench.Calc.Sub` is wrong, and fix both                      | `Sub(5,3)=2`, and the test class has a `Test*` method that asserts `Sub`                  |
| SKILL-15 | `objectscript-sql-patterns` | make `Bench.Ratio.Of` return ERR when the fetch fails                                                     | a zero divisor returns `ERR`, a missing code returns `NONE`, a good row returns the value |
| SKILL-16 | `ensemble-production`       | write `Bench.Prod.Ensure(pName)` so it starts the production if it is stopped and is a no-op when it runs | called twice, both return OK, then status is 1; the check stops the production            |
| SKILL-17 | `objectscript-guardrails`   | make `Bench.Ns.SysCount()` read `%SYS` without leaving the caller there                                   | returns a count > 0 and `$NAMESPACE` is still BENCHMARK                                   |
| SKILL-18 | `iris-agentic-dev`          | load the class in a prompt-supplied XML export onto the server                                            | `Bench.Xml.Greeter.Hello()` returns the exported string                                   |
| SKILL-19 | `objectscript-tdd`          | fix `Bench.Tdd.Total`, which compiles clean and fails at runtime                                          | `Total(2,3)=5`                                                                            |

The checks run through `iad exec`, so they may use no `%Dictionary.*Definition` and no `$system.OBJ.Load`. `%Dictionary.CompiledMethod` over SQL is allowed. SKILL-16's check stops the production in a `Try`/`Catch` either way.

## Loop surface `content-descriptions`

- `surfaces.py` gets a `content-descriptions` entry. It loads all skills and applies descriptions only for `CONTENT_SKILLS` (the eight above).
- `RoutingAdapter` gains `editable: set | None`. `select_component` filters blamed skills to it, and falls back to round-robin over it. `_propose` skips everything else.
- Corpus: `tests/e2e/tasks/content/corpus.jsonl` holds author-written prompts, one or more per content skill, plus negatives. Labels come from two blind subagent passes over `cards.txt`, as in 128, and any disagreement drops the item. `routing-split.toml` is generated with `holdout.render_split`.
- `runner.run(surface="content-descriptions", corpus_dir=tests/e2e/tasks/content)` merges the content corpus with the routing corpus. The routing items keep their frozen split.

## Billable steps

1. One `content-descriptions` loop run, `--budget 2`.
2. The 128 drift re-measure, about $0.25.
3. The ladder: estimate first with `cost_estimator`. Run it only for the new tasks, tools arm versus tools+skill, one repeat.

Anything over $3 in total is skipped and reported.

## Round 2: skill-arm triage (US4)

Grilled 2026-09-26 after the first ladder run.

- **Transcripts.** `run_ladder` gains `on_events(task, arm, repeat, events)`, passed through to `run_one`, which calls it after `collect_events`. `ladder._main` writes each stream as JSONL to `RESULTS_DIR/<run_id>.transcripts/<task>__<arm>__r<repeat>.jsonl`. `tests/e2e/results/.gitignore` gets `*.transcripts/`. The report records the directory under `transcripts`.
- **Triage rule.** `ladder.needs_fix(runs) -> dict[skill, list[task]]`: for each task, the skill arm is flagged when the tools arm passed at least 2 of its scored runs and the skill arm failed at least 2 of its scored runs (majority against majority, grill Q6). Unscored runs (`passed=None`) count for neither side; a task with fewer than 2 scored runs on either arm is reported `unmeasured` and never flagged. Unit-tested on scripted `ArmRun` records.
- **Re-run.** `--ladder skill --skill all --task SKILL-13 --task SKILL-14 --task SKILL-16 --repeats 3 --spent 2.47`: 18 sessions, about $1.53.
- **Fix, per flagged skill.** Quote the misleading lines from a transcript in research.md, reproduce the fact live, edit the skill by hand, and add a forbidden-string test to `test_content_skills_130.rs` plus a live test. Move the task to train in `split.toml`. Write a replacement holdout task (SKILL-20 and up) with the before/after live check, and run the ladder on it: 2 arms, 3 repeats, about $0.51.
- **Nothing flagged.** Record the re-run in research.md and keep "no lift claim". Nothing moves.

## Round 4: sql-patterns check, judge limits, three iad bugs (US5)

Grilled 2026-09-28 on `sql-patterns-review.md`. Clarifications are in spec.md.

### What the probes found after the grill

- **The scratch-class leak is telemetry.** The 78,183 `IrisDevTmp.IrisDevRun*` classes in USER hold `set ^IRISDEV("telemetry",<sid>,seq)=$LB(...)`, not user code. `IrisServer::record_call` (`tools/mod.rs:3317`) `tokio::spawn`s `telemetry::write_durable`, which runs the whole put/compile/query/delete cycle, and nothing waits for it. A CLI process (`exec`, `tool`, every ladder `run_check`) exits, the runtime drops the task between compile and delete, and the class stays. Eight `exec` calls on 2026-09-28 left their own user-code classes deleted and their eight telemetry classes behind. User code on the error path does not leak.
- **`iris_info what=documents` returns the list twice.** It copies `result.content` into `documents` and truncates only `documents`, so the full list stays under `result.content` on every path. `inline=true` also skips truncation. USER's list is 10.7 MB, so the response was about 20 MB.
- **`/docnames/MAC`, `/INT` and `/INC` answer 400.** The routes are `/docnames/RTN/MAC` and so on. `iris_doc list` (`doc.rs:1755`) and `iris_info doc_type=MAC` both use the bare form. `iris_info doc_type=ALL` sends `/docnames/CLS`.
- `lift.format_transcript` cuts `tool_result` to 300 characters before the judge's own 200.
- **Signals kill the flush.** After the flush and `ScratchGuard` landed, one credentialed full run still left 178 `IrisDevTel` and 1,118 `IrisDevRun` classes. A per-module bisect (count `IrisDevTmp.IrisDev%` before and after each integration module) put them on harnesses that end `iad mcp` with `Child::kill`, which is SIGKILL: `test_gate_enforcement_live` 39, `test_e2e` 5 (it closes stdin but kills after 3 s, the same length as the exit flush), and three more. `iad mcp` has no signal handler either, so an MCP host's SIGTERM also ends it before `main` flushes. With a handler in place the process still hung after SIGTERM: `#[tokio::main]` drops its runtime with no deadline, and the drop waits for the blocking thread tokio's stdin reader parks in `read` until the host closes the pipe. `main` now builds the runtime itself and ends with `shutdown_timeout(2 s)` after the flush. The core run still leaked 33 after that, 32 of them from `interop_e2e_tests`. Six harnesses tried `target/llvm-cov-target/debug` first, and a coverage run on 14 Sep had left a binary there with no signal handler, so plain `cargo test` was also testing two-week-old code. Twenty test files each had their own lookup; they now all call `testing::iad_binary_path`, which takes the coverage build only when `CARGO_LLVM_COV` is set.
- **One broken include fails every macro lookup.** With no `includes`, `iris_macro` hands `getmacrolocation` every include in the namespace, and Atelier compiles them all: one that does not compile fails the call with "Failure to compile include files", whichever include the macro is in. IRIS fails only the first lookup after the broken include is saved, which is why `an_unknown_macro_is_an_error_not_an_empty_success` failed in one full run and passed alone. The handler now halves the list on that error until each broken include stands alone, drops it, and names it; one broken include in 265 costs about 16 calls.
- **One unscored item voided the re-baseline.** Run `2026-09-29T031029` measured six skills (about $2.78), and one unscored item out of six in `objectscript-list-patterns` refused the whole baseline write: `__main__` read `run_valid = not invalid_skills`, a per-skill rule, where 118's contract is run-wide. The run-wide share was well under 10%. `scoring.run_validity` now returns the run-wide verdict plus the skills too thin to write; the main path writes the rest. The shard-merge path wrote every measured result with no check; `shard.baseline_writes` applies the same rule there.

### Changes

| Area                  | Change                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Judge limits          | `judge._format_transcript` cuts args and result at `lift.TRANSCRIPT_TEXT_LIMIT`, and `lift.format_transcript` keeps `tool_result` to the same limit                                                                                                                                                                                                                                                                                                                                    |
| Telemetry flush       | `telemetry::spawn_durable` counts in-flight writes. `telemetry::flush(timeout)` waits for them; `flush_blocking` does the same from sync code. `record_call` spawns through it. The CLI calls `flush_blocking` before every exit through one `exit` helper and at the end of `main`, 3 s at most. The telemetry write uses its own class prefix, `IrisDevTmp.IrisDevTel`, so a leak is attributable                                                                                    |
| Delete result         | `delete_doc` checks the HTTP status and `status.errors` and returns an error; the executor logs it at `warn` instead of `let _ =`                                                                                                                                                                                                                                                                                                                                                      |
| `iris_info documents` | Drop `result.content` after flattening. `doc_type` `MAC`/`INT`/`INC` go to `RTN/<type>`, `ALL` to `*`. Hide `IrisDevTmp.*` unless `include_scratch=true`. A ceiling of `IRIS_INFO_MAX_DOCUMENTS` (default 500) applies with `inline=true`: `truncated`, `total_count`, and a hint to filter by `doc_type`. Without `inline` the log-store path is unchanged                                                                                                                            |
| `iris_doc list`       | Categories map to `CLS`, `RTN/MAC`, `RTN/INT`, `RTN/INC`. `IrisDevTmp.*` is hidden unless `include_scratch=true` or the pattern starts with `IrisDevTmp`                                                                                                                                                                                                                                                                                                                               |
| SKILL-21              | `tests/e2e/tasks/benchmark/skills/SKILL-21.yaml`, fixture and check as in the clarifications, train side of `split.toml`                                                                                                                                                                                                                                                                                                                                                               |
| Retirement            | Delete `targeted/SQLCODE-SILENT.yaml` and `SQLCODE-CHECK.yaml`; `objectscript-sql-patterns/eval.yaml` gets no `benchmark_tasks` and the skill-eval skips it by name; drop its row from `skill-baseline.json`                                                                                                                                                                                                                                                                           |
| Signals               | `iad mcp` selects on SIGTERM and Ctrl-C beside the serve loop (stdio and http) and returns, so `main` flushes and the dropped runtime runs `ScratchGuard`. `testing::stop_server` sends SIGTERM, waits 10 s, and kills only then; every harness the bisect names uses it                                                                                                                                                                                                               |
| Run validity          | `scoring.run_validity(per_skill)` gives the run-wide verdict and the excluded skills; `__main__` writes all but those. `shard.item_counts` and `shard.baseline_writes` do the same for `--merge-results --update-baseline` (FR-022)                                                                                                                                                                                                                                                    |
| Session leftovers     | `graded_task.package_prefixes(fixtures)`, `list_classes(prefixes, ns)` (raises on a truncated list) and `created_classes(before, after)`; `pilot.run_one` snapshots after the fixture and deletes the difference after the check. `iris_doc list` needs a non-wildcard prefix, so a class outside the fixture's packages is not caught (FR-023). A listing that fails before the session leaves the run unscored; one that fails after the check keeps the verdict and warns on stderr |
| Cleanup               | After the telemetry fix lands: delete `IrisDevTmp.IrisDevRun*` in USER with `$System.OBJ.Delete` over `^oddDEF`, and `Kill ^Test130Err.Flag, ^Test130Err.Out`                                                                                                                                                                                                                                                                                                                          |

### Tests (first, at every layer)

- **Python:** `test_lift.py` asserts a tool arg and a tool result of 7,000 characters both reach `judge._format_transcript`'s output, and a runaway one stops at the limit. `test_graded_task.py`'s existing live before/after test covers SKILL-21. A skill-eval test asserts an eval with no `benchmark_tasks` is skipped by name.
- **Rust unit:** `flush` returns once pending writes finish and returns at the timeout when one hangs; the `iris_info` document filter hides `IrisDevTmp.*`, keeps the ceiling under `inline=true` and drops `result.content`; the docnames route mapping; a guard that `crates/iris-agentic-dev-bin/src` calls `std::process::exit` only inside the helper.
- **Binary:** `tools/list` shows `include_scratch` on `iris_info` and `iris_doc`.
- **Live (`#[ignore]`):** `test_mcp_sigterm_130`: one tool call, SIGTERM, an exit code rather than death by signal, and no new `IrisDevTmp.IrisDev*` class. `iad exec 'Write 1'` exits and leaves no `IrisDevTmp.IrisDevTel*` class; `iris_info what=documents inline=true` in USER stays under the ceiling and lists no `IrisDevTmp.*`; `iris_doc list` with no category and with `MAC` succeeds.

### Billable

Run 1: the SQLCODE judge probe again (cents), then the full re-baseline, about $3, said to Tom before it starts. Run 2, after the §§3/5/9 fixes: the ladder on SKILL-09, 2 arms × 3 repeats, about $0.50. SKILL-21 is train and the ladder filters to the holdout, so it is not on the run; it is the task the fix is fitted to.

Run 3 (T048), only on Tom's go: the SKILL-09 ladder again with FR-023 in place, about $0.51. T046's run is contaminated by `Bench.Q2.CountOther`, so it gives no clean figure. This is outside SC-007's budget.

Constitution check for round 4: no new MCP tool (IX does not apply) and no Rust change (VIII does not apply). IV holds, because T046a's tests came before the wiring and SC-008 maps to `test_a_session_leftover_is_deleted`.

## Out of scope

- Fixing the iad bugs drafted in R3, R6 and R7. Round 4 fixes three others, listed above.
- A content-descriptions loop in round 2 (waits for mined prompts).
- HL7 and embedded Python (blocked).
