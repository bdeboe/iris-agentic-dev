# 130 research: live reproductions

Every result below came from `iris-dev-iris` (IRIS Community 2026.2.0L) on 2026-09-26, reached through iad's own tools (`iris_execute`, `iris_query`, `iris_doc`, `iris_test`). The namespace is `USER` unless a line says otherwise. The scratch objects live in package `IadProbe130`, and the live tests recreate their own.

## Blocked: dropped from 130

- **HL7 v2, DTL and routing.** Of the 837 `EnsLib.` classes on this container, none is under `EnsLib.HL7`. `Ens.DataTransformDTL` exists, but an HL7 lesson I cannot run is one I cannot check. This skill waits until an IRIS for Health container is registered for this project.
- **None against `""` in embedded Python.** Embedded Python is not configured on iris-dev-iris, and I do not run it there. Dropped, not deferred: it needs a container that has it.

## R1. The `%SQL.Statement` contract

| Call                                                   | Result                                                                                  |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------- |
| `%Prepare("SELECT * FROM Nope.Such")`                  | returns an error `%Status`, `ERROR #5540: SQLCODE: -30 ... Table 'NOPE.SUCH' not found` |
| `%ExecDirect(, "SELECT * FROM Nope.Such")`             | returns a result with `%SQLCODE = -30` and `%Message` set; nothing is thrown            |
| the same result, `%Next()`                             | returns 0, so the loop looks like an empty result                                       |
| `SELECT` that matches no row                           | `%SQLCODE = 0`, `%Next()` returns 0                                                     |
| `UPDATE` that matches no row                           | `%SQLCODE = 100`, `%ROWCOUNT = 0`                                                       |
| `SELECT Amount/? ... ` with parameter 0, after execute | `%SQLCODE = 0`: the error has not happened yet                                          |
| the same result, `%Next(.sc)`                          | returns 0, `sc` is `ERROR #5540: SQLCODE: -400 ... <DIVIDE>`                            |
| the same result after the loop                         | `%SQLCODE = -400`, `%Message` holds the `<DIVIDE>` text                                 |

So a fetch-time error surfaces only in `%Next`'s status argument or in `%SQLCODE` read after the loop. A method that checks `%SQLCODE` once after `%Execute` and then loops returns the rows it managed to read, often none. `objectscript-sql-patterns` §4 shows that pattern and §5 calls `Do stmt.%Prepare(...)`, which throws the status away.

## R2. `New $NAMESPACE`

In a dot block, `New $NAMESPACE  Set $NAMESPACE = "%SYS"` leaves `$NAMESPACE` at `USER` once the block exits. Without the `New`, it is still `%SYS` after the block. The live test uses a class method, which is how the idiom is used.

## R3. Unit tests that do not run

`IadProbe130.Misnamed` extends `%UnitTest.TestCase` and has `TestOk` (passes) and `CheckAdd` (asserts `1+1 = 3`).

| Call                                                           | Result                                                                           |
| -------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `RunTest(":IadProbe130.Misnamed", "/noload/nodelete")`         | runs `TestOk` only, prints `All PASSED`; `CheckAdd` never runs                   |
| `RunTest(":IadProbe130.OnlyMisnamed", ...)`, only `CheckAdd`   | runs 0 tests, prints `All PASSED`                                                |
| `RunTest("IadProbe130", "/noload/nodelete")`, directory exists | runs 0 classes, prints `All PASSED`                                              |
| `iris_test(pattern=":IadProbe130.Misnamed")`                   | `success: true`, `passed: 1`, `total: 1`                                         |
| `iris_test(pattern="IadProbe130.Misnamed")`, no colon          | `NO_TESTS_FOUND`                                                                 |
| `iris_test(pattern="IadProbe130")`, package                    | `NO_TESTS_FOUND`; `RunTest` wants `^UnitTestRoot/IadProbe130/` and runs 0 anyway |
| `iris_test(pattern="Test.MyApp.*")`                            | `NO_TESTS_FOUND`, hint: bare package name, no wildcard                           |
| `iris_test(pattern=":IadProbe130.OnlyMisnamed")`               | `NO_TESTS_FOUND`; iad at least does not call a run with no tests a pass          |

Only methods whose names start with `Test` run. A run that executes nothing still prints `All PASSED`.

Where the skills are wrong:

- `objectscript-unit-test` calls a tool named `objectscript_iris_test`, which does not exist, with pattern `Test.MyApp.*`. Its compile step passes a local file path.
- `iris-objectscript-eval` shows `iris_test(pattern="MyPackage.Tests.*")` and `iris_test(pattern="MyPackage.Tests.MyClassTest")`. Both return `NO_TESTS_FOUND`.

Two iad bugs came out of this. Both are drafted, not filed, and neither is fixed in 130:

1. For a package pattern, `iris_test` returns `NO_TESTS_FOUND` for compiled `TestCase` classes, and its hint blames the package name.
2. `&sql(INSERT ...)` inside a `For` loop in `iris_execute` fails with `<UNDEFINED> sqlSQLCODE1`.

Side effect to report: `^UnitTestRoot` on iris-dev-iris is now `/tmp/`. Its earlier value was not recorded.

## R4. A clean compile is not a tested method

`IadProbe130.CleanCompile` compiles with `compiled: true` and no errors, then fails at runtime:

- `Quit tSun` (typo for `tSum`): `<UNDEFINED> Total+5^IadProbe130.CleanCompile.1 tSun`
- `Quit $CLASSMETHOD("IadProbe130.CleanCompile", "Nope")`: `<METHOD DOES NOT EXIST>`

A literal `..Nope()` is caught at compile time (`MPP5392: No such method 'Nope'`), so the gap is dynamic dispatch and undefined locals.

## R5. Query plans and indexes

Table `IadProbe130.Orders` (Customer, Status, Amount), 5,000 rows. Status is `OPEN` on 100 rows and `DONE` on the rest. Customer is `C0` to `C499`, 10 rows each.

| Step                                                                    | Plan or result                                                                        |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `iris_query(mode="explain")`, `WHERE Status = 'OPEN'`, no index         | `Read master map IadProbe130.Orders.IDKEY, looping on the subrange of ID`, Cost 33000 |
| after `CREATE INDEX StatusIdx ON IadProbe130.Orders (Status)`           | `Read index map IadProbe130.Orders.StatusIdx`, Cost 13720; DDL built it at once       |
| `Index CustIdx On Customer;` added to the class, compiled, no build     | `SELECT COUNT(*) ... WHERE Customer = 'C1'` returns **0**, `%SQLCODE = 0`             |
| the same count with `WHERE %NOINDEX Customer = 'C1'`                    | 10                                                                                    |
| `##class(IadProbe130.Orders).%BuildIndices($LB("CustIdx"))`, then count | 10                                                                                    |
| `INSERT %NOINDEX INTO ... ('ZNEW', ...)`, then count on `ZNEW`          | 0; with `%NOINDEX` in the WHERE, 1                                                    |
| explain `WHERE Customer = 'C1'`, before and after `TUNE TABLE`          | `Read index map ... CustIdx`; Cost 3272, then 2672                                    |
| explain `WHERE Status = 'DONE'` (98% of rows), index present            | `Read master map ... IDKEY`, Cost 33000, Info "Using the outlier selectivity"         |

An index added in the class source is compiled but empty until `%BuildIndices`, and every query that reads it returns short with no error. A DDL `CREATE INDEX` on a table with rows builds the index itself. For an outlier value the planner reads the master map on purpose, so a plan without the index is not always a missing index.

## R6. Running productions

| Call                                                                    | Result                                                                                       |
| ----------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `Ens.Director.GetProductionStatus(.name, .state)`, nothing running      | `state = 2`, `name = ""`                                                                     |
| `StartProduction("PerfDemo.Production")`                                | OK; status then `state = 1`, `name = PerfDemo.Production`                                    |
| `StartProduction` again while it runs                                   | `ERROR <Ens>ErrProductionAlreadyRunning`                                                     |
| `UpdateProduction(10)` / `StopProduction(10, 0)`                        | OK / OK, then `state = 2`, `name = ""`                                                       |
| `IsProductionRunning("IadProbe130.EmptyProd")` while running            | 1                                                                                            |
| `GetProductionState(.sc)`                                               | `<METHOD DOES NOT EXIST>`                                                                    |
| `GetActiveProductionName()` with `state = 2` in both USER and BENCHMARK | `IadProbe130.EmptyProd`: a production started earlier in BENCHMARK                           |
| `EnsConstants.inc`                                                      | `$$$eProductionStateRunning` 1, `Stopped` 2, `Suspended` 3, `Troubled` 4, `NetworkStopped` 5 |

`ensemble-production`'s ObjectScript section calls `GetProductionState` and compares with `$$$EnsProductionRunning`. Neither exists, so the "verify it started" snippet cannot compile, and `GetActiveProductionName` is shown as the current production. The state table for the Python API lists 1 to 4 and has no 5.

An empty production in BENCHMARK starts and stops in under a second, so a ladder check can drive one.

Also seen: `iris_macro(action="expand", name="eProductionStateRunning")` returns `result: {}`, which is another draft note.

## R7. Loading an XML export

| Attempt                                                                       | Result                                                                                            |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Atelier PUT, name `IadLive130.FromXml.xml`                                    | HTTP 400, `ERROR #16006: Document ... name is invalid`                                            |
| PUT under `IadLive130.FromXml.cls`, `<?xml ...?>` declaration on its own line | `console: "Imported class: IadLive130.FromXml"`; compiles; `GET` returns UDL; `Hello()` runs      |
| the same export on one line                                                   | `result.status: ERROR #16021: Illegal Header Line`, with `status.errors` empty; nothing is stored |
| the one-line export through `iris_doc(mode="put", compile=true)`              | the put reports no error; compile then fails with `#5351: Class ... does not exist`               |
| `$system.OBJ.LoadStream(...)` through `iris_execute`                          | `CODE_EDIT_BLOCKED`, matched `$SYSTEM.OBJ.LOAD`                                                   |

An XML export goes on the server by putting it under its `.cls` name. Atelier imports it and stores UDL, but only when the XML declaration is on a line of its own. I first reproduced this with a one-line export and recorded "XML under `.cls` stores nothing". That was wrong: the cause was the single line, not the XML. The re-check is in the live test.

iad bug, drafted and not filed: `iris_doc put` ignores the error in `result.status`, so #16021 never reaches the agent, and the only error it sees is #5351 from the compile after.

## T011: the billable runs (2026-09-26, SC-004)

Total spend is about $2.47 of the $3 cap: about $0.50 for drift, $1.19 estimated for the ladder, and $0.78 for the loop.

### 128 drift re-measure

`optimize drift` exited 0. Holdout Recall@1 is 0.25 (n=32), inside the committed band of 0.13 to 0.42. The false-hint rate is 0.638. The 130 skill edits did not move 128's routing figure out of its band.

### Ladder, SKILL-13 to SKILL-19

Arms `tools` and `tools+its-own-skill`, one run each, 14 sessions. The per-session record is `tests/e2e/results/ladder-20260926T193103.runs.jsonl`.

| Task     | Skill                       | tools | tools+skill |
| -------- | --------------------------- | ----- | ----------- |
| SKILL-13 | `iris-query-plans`          | PASS  | FAIL        |
| SKILL-14 | `objectscript-unit-test`    | PASS  | FAIL        |
| SKILL-15 | `objectscript-sql-patterns` | PASS  | PASS        |
| SKILL-16 | `ensemble-production`       | PASS  | FAIL        |
| SKILL-17 | `objectscript-guardrails`   | PASS  | PASS        |
| SKILL-18 | `iris-agentic-dev`          | PASS  | PASS        |
| SKILL-19 | `objectscript-tdd`          | PASS  | PASS        |

Tools alone passed 7 of 7 (Wilson 95% interval 0.65 to 1.00). With the skill, 4 of 7 passed. The paired figures are b=0 and c=3, a lift of −0.43. The minimum detectable effect at n=7 is 0.58, so the harness marks the run underpowered. Each skill has one pair, and one pair cannot show harm or help. Every skill gets **no lift claim**, and all seven ship, as FR-006 says.

The three failures are still a signal. Each was "tried and failed": no timeout, and tool calls were made.

- SKILL-13 with `iris-query-plans` ran 10 calls, including docs, `iris_table_info` and two queries. It never called `%BuildIndices`, so it found the stale index and stopped. The tools arm called `iris_execute_method` and passed.
- SKILL-14 with `objectscript-unit-test` ran 44 calls. It tried `iris_generate_test` (LLM_UNAVAILABLE) and made many `iris_execute_method` attempts.
- SKILL-16 with `ensemble-production` began by calling `iris_add_server` and `iris_reload_pool`, then went through six compile rounds.

The ladder keeps no transcripts, so I cannot tell from these records whether the skill text misled the agent. The next step is at least three runs per arm on these three tasks, with transcripts kept.

### `optimize run --surface content-descriptions`

`--budget 1.0 --max-minutes 40`. Run directory `tests/e2e/results/optimize/20260926T235225Z-content-descriptions/` (git-ignored). Spend $0.78; the run stopped on budget.

| Arm       | Recall@1 [95% Wilson] | False-hint rate | Exact-name Recall@1 |
| --------- | --------------------- | --------------- | ------------------- |
| seed      | 0.500 [0.371, 0.629]  | 0.569 (n=51)    | 1.000 (n=8)         |
| candidate | 0.519 [0.389, 0.646]  | 0.608 (n=51)    | 1.000 (n=8)         |

Verdict HOLD. The recall interval's lower bound is 0, the false-hint rate went up, and there is no ladder run. The budget ran out after the base valset (40 items) and the holdout scoring, so gepa made no proposals and the candidate is the seed. The two rows score the same descriptions, so their difference (+0.019, one item) is scorer noise, and the gate held on it as it should. A run that proposes anything needs about $3 on its own.

## Round 2: triage re-run (2026-09-26, T017)

`--skill all --task SKILL-13 --task SKILL-14 --task SKILL-16 --repeats 3`, 18 sessions, about $1.53. Records are in `tests/e2e/results/ladder-20260926T210712.runs.jsonl`, and transcripts are in the git-ignored `ladder-20260926T210712.transcripts/`.

| Task     | Skill                    | tools (r0 r1 r2) | tools+skill (r0 r1 r2) | Triage |
| -------- | ------------------------ | ---------------- | ---------------------- | ------ |
| SKILL-13 | `iris-query-plans`       | P F F            | P P P                  | keep   |
| SKILL-14 | `objectscript-unit-test` | P P P            | F P P                  | keep   |
| SKILL-16 | `ensemble-production`    | F P P            | F P F                  | fix    |

Pooled across the three tasks: b=1, c=1, lift 0.0, n=3, underpowered. The round-1 losses on SKILL-13 and SKILL-14 did not come back. SKILL-13 went the other way, with the skill arm passing 3 of 3 and tools passing 1 of 3.

### No skill-arm session loaded its skill

None of the 9 skill-arm sessions called the `skill` tool, so none of them read a skill body. Both SKILL-16 failures came from the agent's own reasoning:

- r0 wrote `If (prodName = pName) && (state = 2) { Quit OK }`.
- r2 wrote the comment `$$$eProductionStateRunning = 2` and then tested `state = 2`.
- Both read the `%Status` error return of `iris_execute_method` (`"0 \u0000\u0003"`) as success.

`GetProductionStatus` returns 1 for running and 2 for stopped, and the skill's state table says the same. The skill text could not have misled a session that never read it.

### The harness leaked the operator's Claude Code setup into every session

A one-session probe asked the agent to list its skills. It named about 60 skills from `~/.claude/skills`, the operator's personal set. opencode 1.14.17 reads three Claude Code locations unless it is told not to:

- `~/.claude/CLAUDE.md`, as instructions;
- `~/.claude/skills`;
- `~/.agents/skills`.

`XDG_CONFIG_HOME`, which `IsolatedEnv` sets to block the global opencode config, stops none of them. So every harness session before this fix ran with the operator's global CLAUDE.md in its instructions and about 160 personal skills in its listing. That covers both ladder rounds and the skill-eval baselines. The 128 drift re-measure is not affected: it scores routing with the proxy model over the shipped descriptions and starts no opencode session. The personal set includes a pre-127 copy of `ensemble-production`, so the round-1 and round-2 "tools" arms were never skill-free. A single installed skill in a list of 160 is a likely reason the skill arm never loaded one.

`OPENCODE_DISABLE_CLAUDE_CODE=1` turns off all three. `IsolatedEnv.env_vars()` now sets it. Two tests guard it:

- `test_env_vars_turn_off_claude_code_compat` (unit);
- `test_isolated_env_offers_only_installed_skills` (billable live). It failed before the fix with `grill-me leaked into the session` and passes after it.

Every skill-arm and tools-arm figure recorded before this fix measured a contaminated session, and I treat them all as void. That includes 130's round-1 ladder and the triage table above.

### SKILL-16 on clean isolation (T017a)

After the fix I re-ran only the flagged task, SKILL-16, at 3 runs per arm: 6 sessions, about $0.51. The record is `tests/e2e/results/ladder-20260926T214358.runs.jsonl`.

| Task     | Skill                 | tools (r0 r1 r2) | tools+skill (r0 r1 r2) | Triage |
| -------- | --------------------- | ---------------- | ---------------------- | ------ |
| SKILL-16 | `ensemble-production` | F F F            | P F P                  | keep   |

Nothing is flagged, so T018 and T019 do not run. No skill text changes, SKILL-16 stays on the holdout, and there is no SKILL-20. `ensemble-production` keeps "no lift claim": one task at n=3 cannot carry one.

The skill arm still made 0 `skill` calls in 3 sessions, now with one skill listed instead of 160. gpt-4.1 does not load a skill for this task on its own. So on this harness the skill arm measures the one listing line, and a skill body cannot help or hurt until something makes the agent load it.

"State 2 = running" turned up in both arms: tools r1 and r2, and skill r1. It is not from skill text. Every lookup the agents tried came back empty:

- `iris_macro(action="definition", name="eProductionStateRunning")` answered `result: {}` in BENCHMARK and `result: null` in ENSLIB (drafts #3).
- `iris_macro(action="list")` answered "No include files found in this namespace".
- `iris_search(category="INC", query="eProductionStateRunning")` found 0 hits, in BENCHMARK and in %SYS.
- webfetch of the Documatic class page got the "JavaScript is disabled" shell.

With nothing to read, the agent guessed, and guessed 2. The fix that would move SKILL-16 is in iad's `iris_macro`, not in the skill.

The tools arm fell from 2 of 3 under contamination to 0 of 3 clean. One clean run (r0) announced its next step after one call and stopped. The operator's CLAUDE.md, which says to execute every step to completion, may have kept earlier sessions going. n=3 cannot separate that from noise.

### Round 2 spend

About $2.07 of the $3 cap: $1.53 for the 18-session re-run, $0.51 for the clean SKILL-16 re-run, and about $0.03 for the probe and the live isolation tests.

## Round 3: skill arm loads its skill, full re-baseline (2026-09-26 to 27, T021–T026)

### What changed before the run

- **The skill arm loads its skill.** A skill-arm prompt now opens with one line telling the agent to load its skill with the skill tool before it starts. A skill-arm session that never loads it is unscored, not failed, and three in a row stop the ladder (`test_skill_preload.py`). The 118 skill-eval asks the same way and unscores a with-skill run that never loaded (`test_lift_preload.py`).
- **Every arm gets the same autonomy line.** It says to work until the task is done and names no tool and no skill. It stands in for the operator CLAUDE.md rule that the isolation fix removed, so the tools arm is not the only arm that lost it.
- **`iris_macro` calls real routes.** Every action had posted to a route Atelier does not have and returned `{}` on the 404 (drafts #3). It now uses `getmacrolocation`/`getmacrodefinition`/`getmacroexpansion`/`getmacrosignature` and `/docnames/RTN/INC`, finds the defining include when none is named, and returns `MACRO_NOT_FOUND` instead of `{}` (`test_macro_130.rs` plus the live handler tests).
- **Drift correction.** The 128 drift re-measure uses the routing proxy and starts no opencode session, so the isolation leak never touched it (see the leak section above).

### The run

`--ladder skill --skill all --repeats 3` over SKILL-01 to SKILL-19: 114 sessions in three files, because the host slept.

- `ladder-20260926T230228.runs.jsonl`: r0, SKILL-01 to SKILL-16 plus three unscored runs on SKILL-17 and SKILL-18; aborted at 00:41 (exit 3).
- `ladder-20260927T093806.runs.jsonl`: r0, SKILL-17 to SKILL-19.
- `ladder-20260927T094542.runs.jsonl`: r1 and r2, all 19 tasks, run with the new `--start-repeat 1`.
- Merged report: `ladder-r3-merged.json`, 0 unscored sessions. It is git-ignored like the other dumps; `resume --merge --pooled` over the three files rebuilds it.

The merge needed a fix first. `resume` keyed sessions on (task, arm), so three repeats merged as one, and a rerun with `--repeats 2` would have labelled its runs 0 and 1. It now keys on the repeat too and stamps the repeat count on the report, and the ladder takes `--start-repeat` (`test_resume.py`, `test_ladder.py`).

All 57 skill-arm sessions loaded their skill.

| Task     | Skill                        | tools (r0 r1 r2) | tools+skill (r0 r1 r2) | Pair  | Triage |
| -------- | ---------------------------- | ---------------- | ---------------------- | ----- | ------ |
| SKILL-01 | `objectscript-guardrails`    | P P P            | P P P                  |       | keep   |
| SKILL-02 | `objectscript-guardrails`    | P P P            | P P P                  |       | keep   |
| SKILL-03 | `objectscript-guardrails`    | P P P            | P P P                  |       | keep   |
| SKILL-04 | `objectscript-guardrails`    | P P P            | P P P                  |       | keep   |
| SKILL-05 | `objectscript-guardrails`    | P P P            | P P P                  |       | keep   |
| SKILL-06 | `objectscript-list-patterns` | P F P            | P P P                  | skill | keep   |
| SKILL-07 | `objectscript-list-patterns` | F F P            | P F P                  |       | keep   |
| SKILL-08 | `objectscript-sql-patterns`  | F F P            | P P P                  | skill | keep   |
| SKILL-09 | `objectscript-sql-patterns`  | P F P            | P F F                  |       | fix    |
| SKILL-10 | `objectscript-list-patterns` | F F F            | F F(T) F               |       | keep   |
| SKILL-11 | `iris-sql`                   | F(T) F P         | P P P                  | skill | keep   |
| SKILL-12 | `objectscript-sql-patterns`  | F F P            | P F(T) F               |       | keep   |
| SKILL-13 | `iris-query-plans`           | P P P            | F F F                  | tools | fix    |
| SKILL-14 | `objectscript-unit-test`     | F P P            | P P F                  |       | keep   |
| SKILL-15 | `objectscript-sql-patterns`  | P P P            | P P P                  |       | keep   |
| SKILL-16 | `ensemble-production`        | P P P(T)         | F(T) P(T) P            | tools | keep   |
| SKILL-17 | `objectscript-guardrails`    | P P P            | P P P                  |       | keep   |
| SKILL-18 | `iris-agentic-dev`           | P P P            | P P P                  |       | keep   |
| SKILL-19 | `objectscript-tdd`           | P P P            | P P P                  |       | keep   |

(T) marks a session that hit the 300 s clock. A timed-out session counts as a fail unless the check passed anyway, which it did for SKILL-16 tools r2 and skill r1.

Strict-and over three repeats: tools passes 11 of 19, tools+skill 12 of 19. Pooled, b=3 (skill wins SKILL-06, 08, 11) and c=2 (tools wins SKILL-13, 16), lift +0.053, n=19, mde 0.310: underpowered, and the skills verdict is inconclusive. No single skill reaches `helps`. `objectscript-guardrails` (6 pairs) is "no effect" because both arms pass all six.

### Pairs that hinge on the clock

- **SKILL-16 (tools win).** Skill r0 timed out after 6 calls. Its last event is a `step_start` at 23:56:43. The host went into clamshell sleep at 00:00:53 and woke at 00:17:42, and the clock fired on wake. Without that session the skill arm passes 2 of 2 and the pair is a tie, so the pooled count is b=3, c=1.
- **SKILL-11 (skill win).** Tools r0 timed out after 4 calls, again silent for about 290 s after a `step_start`: a provider stall, not the agent working. Tools r1 failed on its own, so the pair stands without it.
- SKILL-10 and SKILL-12 have a timed-out skill session, but both arms fail those tasks anyway.

### SKILL-13: `iris-query-plans` says the right thing in a way the agent reads as a one-off

All three skill-arm sessions loaded the skill, found the stale index with `WHERE %NOINDEX`, and rebuilt it by hand with `%BuildIndices` through `iris_execute_method`. None edited the class. The check calls `Run()` again, which kills the extent and reloads it with `INSERT %NOINDEX`, so the index is empty again and the count is 0. All three tools-arm sessions edited the loader's source (`iris_doc` put, then compile) and passed.

The skill says to run `%BuildIndices` after a `%NOINDEX` bulk load. That reads as an admin step. What the task needs is for the loader to call it, so the fix survives the next load. That is a wording fix in the skill, with a unit test for the new line and the SKILL-13 ladder task as its live check. Not made in round 3, because it would have changed the text between repeats.

Two smaller things from the same transcripts. r0 first called `%BuildIndices("CustIdx")` and got `<LIST>`, because the argument is a `$ListBuild`; the skill shows that form on line 34, but the agent passed a string. And `TUNE TABLE` through an `iris_query` write returned `DDL_NOT_ALLOWED`, after which the agent tried `%SYSTEM.SQL.TUNE`, which does not exist. A hint on `DDL_NOT_ALLOWED` for `TUNE TABLE` that names `$SYSTEM.SQL.Stats.Table.GatherTableStats` is a candidate for the 129 hint surface.

### SKILL-09: flagged, but the skill already says it

The skill arm failed 2 of 3 and tools passed 2 of 3, so `needs_fix` flags `objectscript-sql-patterns`. Both failing sessions loaded the skill and still queried `Bench.Sub.Item`. The SQL table is `Bench_Sub.Item`, and §1 of the skill states the rule and gives a three-level example, and §10 repeats it. So this is the agent not applying text it read, not a wrong or missing line. r1's method returns -1 when the prepare fails, so the SQLCODE never reaches a tool result and the 129 `deep_package_table` hint cannot fire. I am not editing the skill for this. The one change worth trying is to lead §1 with a class name in the task's shape (`A.B.C` → `A_B.C`), and only if a second round flags it again.

### The host slept

The laptop went into clamshell sleep at 00:00:53 on 2026-09-27. After the 00:17 wake, OrbStack and the IRIS web port stopped answering, so the next tasks failed validation before their sessions started: `iad exec` fell back to docker-exec mode and refused block syntax (SKILL-17 tools), and writes failed `SCM_PROBE_FAILED` (SKILL-17 skill, SKILL-18 tools). Three unscored in a row stopped the run at 00:41 with exit 3, as designed. None of the three started a session, so none cost anything. The host stayed asleep until 09:34. The later runs held `caffeinate -s` on the ladder's pid.

### The SKILL-13 fix, and SKILL-20 (T027)

Commit `e2224f8` changes the `INSERT %NOINDEX` section of `iris-query-plans`. It now says the method doing the `%NOINDEX` insert has to call `%BuildIndices` when its inserts are done, and that a rebuild by hand lasts only until the next load. The unit test `query_plans_puts_the_rebuild_in_the_loader` guards the line. The live test `a_rebuild_by_hand_lasts_until_the_next_noindex_load` runs the sequence on IRIS: load 0, build by hand 10, reload 0, and a loader that builds gives 10 twice.

The live test reads the index global (`^IadLive130.SalesI("RegionIdx"," R1",id)`), not a `COUNT(*)`. Once a build has left statistics behind, the planner can choose the master map. Then `COUNT(*)` and a row fetch both report 10 over an empty index. A count test would pass on a broken loader. The SKILL-20 check reads the global for the same reason.

I wrote the fix while reading SKILL-13's transcripts, so SKILL-13 is fitted to it. It moves to train in `split.toml`. SKILL-20 takes its holdout slot for the same skill with a fresh fixture: `Bench.Plan2.Feed.Append` adds rows with `INSERT %NOINDEX`, and the check calls it three times and counts the `RegionIdx` entries per region. `TUNED_SKILL_TASKS` in `test_split.py` records the swap. SKILL-20 validated live on iris-dev-iris: the check fails on the fixture and passes on the reference solution, twice.

Ladder on SKILL-20 alone, 3 repeats (`ladder-20260927T153202.runs.jsonl`): tools passes 3 of 3 and tools+`iris-query-plans` passes 3 of 3, with the skill loaded in all three. b=0, c=0, so on pass/fail there is no effect, and one pair can never reach `helps`. The difference shows in the work each arm did. The skill arm used 6, 8 and 8 tool calls in 20 to 26 s. The tools arm used 18, 25 and 34 calls in 47 to 82 s. After the fix the skill arm puts the build in the loader first time, which SKILL-13's skill arm never did. This is one task, so I read it as the fix working, not as a lift claim. Cost about $0.51.

### The 14:48 re-baseline was invalid: baseline sessions grepped the whole disk

The first round-3 skill-eval run (`skill-eval-2026-09-27T155250.json`) came back `run_valid: false`. Four skills went over the 10% unscored limit (`UNSCORED_LIMIT`, `scoring.py:20`): `iris-ai-hub` 7 of 36 unscored, `objectscript-list-patterns` 2 of 6, `objectscript-review` 1 of 6, `objectscript-sql-patterns` 3 of 6. An invalid skill gets no comparison and no baseline write, so the run wrote none.

Every unscored item was on the baseline arm, and every one had the same reason, `session_evidence_gap`: the session never went idle and made no completed tool call. The skill arm had none. I re-ran one baseline item with the event stream and the opencode log kept. The agent's first call was opencode's built-in `grep` with path `/`. opencode asks for `external_directory` on a path outside the working directory, `--dangerously-skip-permissions` approves the ask, and the grep walks the whole disk until the 300 s clock kills the session. The skill arm opens by loading its skill, so it never starts with a blind grep.

The same walk is a contamination risk. A grep over `/` can read this repo's `SKILL.md` files and anything under `~/.claude`, so a baseline session could read the skill it is measured without.

Commit `50a0804` sets `permission.external_directory = "deny"` in the isolated opencode config. A deny is a rule, not an ask, so skip-permissions leaves it in place. The same probe now gets a grep error in 9 s and the session carries on. opencode's own tool-output directory stays allowed.

Separately, three probe sessions in a row at 15:11, 15:19 and 15:21 produced no events at all. Their opencode logs stop after the server-proxy start line. The next probes ran normally. I have not found the cause and I am not fixing it here; a session like that is unscored by the same evidence-gap rule.

That run's scored figures do not stand: its baseline arm is the arm that changed. For the record, `objectscript-guardrails` had no lift line because it was withdrawn as `too_easy` (skill arm at the ceiling, 0.20 against an MDE of 0.4334), not because it failed.

### The 15:47 re-baseline was invalid too: no session ever read as idle

The second run (`skill-eval-2026-09-27T193913.json`, on the `external_directory` deny) came back `run_valid: false` as well: 14 of 84 unscored. Two skills were over the limit, `iris-ai-hub` with 11 of 36 and `iris-vector-ai` with 2 of 12, so again no baseline was written. The other seven do not get written either, because an invalid run writes nothing. All 14 unscored items were on the baseline arm. The results file gives only counts and holes per skill, no per-item reason, so I re-ran one baseline item, AI-HUB-WORKFLOW-SUSPEND (3 of 3 unscored), with its events kept.

The deny works: the agent's globs on `/` failed at once, it tried to write `/EHR/Workflow/PatientUnwellProcessBPL.cls`, that failed too, and it gave the class as text. The session ended on its own in 32 s, and `session_evidence_gap` still called it "never reached idle". `_reached_idle` looks for a `session.status` event with `type: idle`. `opencode run --format json` (1.14.17) never emits one. Its stream is only `step_start`, `text`, `tool_use` and `step_finish`, and a session that ends on its own closes with a `step_finish` whose `reason` is `stop`. The unit test for the rule built the idle event by hand, so it passed while no real session had ever reached idle.

So the rule has, since 121 T021, unscored every session with no completed tool call, whether it was killed or answered in text. The skill arm always completes its `skill` call, so it is never caught; the baseline arm is, whenever its tool calls all fail or it answers from memory. Those sessions mostly fail, so dropping them made the baseline look better than it is, and lift figures since 121 T021 are biased down by an unknown amount. Before the deny, the grep on `/` hid this: those sessions really were killed.

Commit `d05fb33` counts a last `step_finish` with `reason: stop` as the end, and keeps the `session.status` check in case a later opencode sends it. A session cut after a tool step, or one that starts a new step after a `stop`, is still a gap. The four new unit tests use the event shapes from the captured session. The ladder is not affected: `pilot.py` infers a timeout from the clock, not from an idle event.

Scored figures from this run, for the record only (the baseline arm is the arm the fix changes):

| Skill                      | Scored | Lift  | Pairs | Note                                |
| -------------------------- | ------ | ----- | ----- | ----------------------------------- |
| ensemble-production        | 11/12  | +0.40 | 5     | underpowered                        |
| iris-ai-hub                | 25/36  | +0.14 | 7     | invalid, 11 baseline items unscored |
| iris-connectivity          | 6/6    | 0.00  | 3     | underpowered                        |
| iris-vector-ai             | 10/12  | +0.75 | 4     | invalid, 2 baseline items unscored  |
| objectscript-list-patterns | 6/6    | −0.33 | 3     | underpowered                        |
| objectscript-review        | 6/6    | +0.33 | 3     | underpowered                        |
| objectscript-sql-patterns  | 6/6    | 0.00  | 3     | underpowered                        |

`objectscript-guardrails` and `objectscript-unit-test` are withdrawn (`too_easy`, `broken_check`) and give no lift line, as in the first run. Cost about $2.90 for sessions and $0.38 for the scorer.

### Skill-eval re-baseline, valid

The third run (`skill-eval-2026-09-27T204612.json`, on both fixes) is valid: 0 of 84 unscored, and it wrote the baseline. Nine skills ran; seven give a lift line.

| Skill                      | Mode    | Scored | Base → skill | Lift  | Pairs | Outcome      |
| -------------------------- | ------- | ------ | ------------ | ----- | ----- | ------------ |
| iris-vector-ai             | pattern | 12/12  | 0.17 → 0.67  | +0.50 | 6     | underpowered |
| iris-connectivity          | judge   | 6/6    | 0.33 → 0.67  | +0.33 | 3     | underpowered |
| objectscript-list-patterns | judge   | 6/6    | 0.33 → 0.67  | +0.33 | 3     | underpowered |
| ensemble-production        | pattern | 12/12  | 0.33 → 0.50  | +0.17 | 6     | underpowered |
| iris-ai-hub                | pattern | 36/36  | 0.44 → 0.61  | +0.17 | 18    | underpowered |
| objectscript-review        | judge   | 6/6    | 0.67 → 0.67  | 0.00  | 3     | underpowered |
| objectscript-sql-patterns  | judge   | 6/6    | 0.00 → 0.00  | 0.00  | 3     | underpowered |

`objectscript-guardrails` is withdrawn as `too_easy` and `objectscript-unit-test` as `broken_check` (GEN-01 and GEN-02 are retired), so neither has a lift line. Every lift is below its MDE, so nothing here is a lift claim: at 3 to 18 pairs per skill the run cannot tell +0.17 from zero. No skill regressed. Sessions cost $2.90 and the scorer $0.32.

Against the committed baseline (re-baselined 2026-09-12 from run 34707534110), `iris-vector-ai` goes from +0.20 to +0.50 and `objectscript-review` from +0.20 to 0.00. `ensemble-production` (−0.10 before), `iris-ai-hub` (−0.10), `iris-connectivity`, `objectscript-list-patterns` and `objectscript-sql-patterns` (all 0 before) now carry this run's figures and its provenance. The old figures predate both harness fixes: that baseline arm dropped every text-answer session and every session killed by a disk-wide grep, so they are not comparable, and the deltas above are not changes in the skills. The two withdrawn skills keep their old entries.

### Round 3 spend

About $9.70 for the ladder: 114 sessions at about $0.085 each (32 + 6 + 76 across the three files; the r1–r2 run's 76 cost $6.46). The skill-eval took three runs: $2.90 for the invalid 14:48 run, $3.28 for the invalid 15:47 run and about $3.22 for the valid one. Diagnostic probes came to about $0.60 and the SKILL-20 ladder to $0.51. Round 3 total: about $20.20, against the $80 cap.

## Round 4

### Skill-eval re-baseline (T044)

Run `2026-09-29T031029`, after the SQLCODE sets were retired and SKILL-21 moved to train. It cost about $2.78: sessions about $2.03, the scorer $0.75. The run wrote nothing at first. One item out of six in `objectscript-list-patterns` went unscored (in the baseline arm), and `__main__` refused the whole write because it treated any thin skill as voiding the run. Across the run, 1 item of 78 was unscored (1.3%), inside 118's 10% limit. FR-022 fixed the rule, and I wrote the baseline from the saved results file with `shard.baseline_writes`, with no rerun. `objectscript-list-patterns` (1 of 6 unscored, 17%) is left out and keeps its old entry.

| Skill                      | Scored | Pass rate   | Lift  | Pairs | Verdict      |
| -------------------------- | ------ | ----------- | ----- | ----- | ------------ |
| iris-vector-ai             | 12/12  | 0.00 → 0.67 | +0.67 | 6     | underpowered |
| ensemble-production        | 12/12  | 0.17 → 0.50 | +0.33 | 6     | underpowered |
| iris-ai-hub                | 36/36  | 0.39 → 0.61 | +0.22 | 18    | underpowered |
| iris-connectivity          | 6/6    | 1.00 → 0.67 | −0.33 | 3     | underpowered |
| objectscript-review        | 6/6    | 1.00 → 0.67 | −0.33 | 3     | underpowered |
| objectscript-list-patterns | 5/6    | 0.00 → 0.67 | +1.00 | 2     | not written  |

No lift claim, and no regression either: every skill is far below its MDE (floors of 63 and 129 pairs). The two negative lifts are one session each at 3 pairs. The run record gives no reason for the unscored item, since the results JSON keeps no per-item reason; that is a legibility gap for the drafts list.

The write tripped the Phase 2 triage gate (`test_triage.py`) five times. `ensemble-production` (+0.33) and `iris-ai-hub` (+0.22) carried `not_helped` verdicts from 2026-09-12 and now read over the gate, so both verdicts are superseded by this run. Three sets now have one arm at an end of the scale, which at 3 and 6 pairs takes one session. `iris-connectivity` (3/3 against 2/3, the reverse of the 2026-09-27 reading) and `objectscript-review` (3/3 against 2/3) are `not_helped`; `iris-vector-ai` (0/6 against 4/6) is `too_hard` for the bare arm. All three entries are withdrawn in the baseline, so none of the three is a comparison basis. The records are in `triage_records._ROUND_4`.

### sql-patterns ladder (T046)

Run `ladder-20260929T004750`, SKILL-09 only, 3 repeats per arm, about $0.51. SKILL-21 is train and the ladder takes holdout tasks only, so it was not on the run; it is the task the §§3/5/9 fix was fitted to.

| Arm         | r0            | r1            | r2            | Passed |
| ----------- | ------------- | ------------- | ------------- | ------ |
| tools       | FAIL 27 calls | PASS 85 calls | PASS 57 calls | 2/3    |
| tools+skill | PASS 25 calls | FAIL 3 calls  | PASS 53 calls | 2/3    |

`b=0 c=0`, underpowered, no lift claim. The skill arm loaded its skill in all three sessions.

The 3-call FAIL is not the skill's. The session read `Bench.Q2.CountOther(pCode)` as a class name, opened `Bench.Q2.CountOther.cls`, found a finished-looking class there, compiled it and stopped. That class was written on 2026-09-27 by ladder session `SKILL-09__tools+objectscript-sql-patterns__r1`, which made the same misreading, and nothing deleted it: `reset_documents` only resets the fixture's own names. It also ended the 2026-09-27 r2 session after 3 calls. So two SKILL-09 skill-arm FAILs across the two runs came from a leftover, and the 2026-09-27 full ladder (tools+skill 12/19) counts one of them. That run's `needs_fix` flag on `objectscript-sql-patterns` (skill arm failing 2 of 3 where tools passed 2) rests on that FAIL; without it the skill arm fails 1 and the flag does not fire.

FR-023 fixes this. After the fixture goes on, `pilot.run_one` lists the classes under the fixture's top-level packages, lists them again after the check, and deletes the difference. The six leftovers no task names (`Bench.Calc.Tests.MathTest`, `Bench.Patient.Test`, `Bench.Probe`, `Bench.Q2.CountOther`, `Bench.Stor`, `Bench.Validator`) are deleted from BENCHMARK. `iris_doc list` refuses a bare wildcard, so a class a session writes outside the fixture's packages is still not seen.

The misreading itself happened in both arms: tools r0 on this run asked for `Bench.Q2.CountOther` too and got a 400. SKILL-09's prompt names the method `Bench.Q2.CountOther(pCode)`, which reads as a class path. The prompt is left as it is, because changing a holdout task after looking at its results is what the split forbids. A new holdout task should name the class and the method separately.

Triage: sql-patterns gets a round-4 `broken_check` record (the rubric's false `If SQLCODE` claim, and a judge that saw 120 characters of tool args and 200 of results), and it replaces T021's killed-session record.

### sql-patterns ladder after FR-023 (T048)

Run `ladder-20260929T023344`, SKILL-09 only, 3 repeats per arm, about $0.51, with FR-023's cleanup on.

| Arm         | r0            | r1            | r2            | Passed |
| ----------- | ------------- | ------------- | ------------- | ------ |
| tools       | FAIL 5 calls  | PASS 35 calls | FAIL 32 calls | 1/3    |
| tools+skill | FAIL 20 calls | PASS 8 calls  | FAIL 24 calls | 1/3    |

`b=0 c=0`, underpowered, no lift claim, and `needs_fix` does not fire because tools passed 1 of 3. The skill arm loaded its skill in all three sessions.

FR-023 held. No session found a class left by an earlier one, and `iris_generate_class` returned `LLM_UNAVAILABLE` in the two sessions that tried it, so no session wrote a stray class. Two skill-arm sessions opened with `Bench.Q2.CountOther.cls` or `Bench.Q2.*` and found nothing, then edited the real `Bench.Q2`.

All four FAILs have the same cause, the SQL table name. The check needs `Bench_Sub.Item`.

- tools r0 wrote `&sql(... FROM Bench_Sub_Item ...)`. It compiled, because embedded SQL is resolved late, and returned -1 at runtime (SQLCODE -30). The session never ran the method.
- tools r2 used the same name, ran the method, got -1, and spent about 20 calls on data and `INSERT` without trying `Bench_Sub.Item`.
- skill r0 prepared `FROM Bench_Sub_Item` "due to underscore rule", which misapplies the skill: §1 keeps the last dot as the schema/table separator.
- skill r2 used the class name `Bench.Sub.Item`, which IRIS reads as schema `Bench`, table `Sub.Item`. SQLCODE -30.

None of the four ran a query against the table that succeeded. Both passes did. skill r1 used `Bench_Sub.Item` from the start, citing the skill, and checked it with `iris_query`. tools r1 got the name from the tool's hint and from `Bench.Look`, SKILL-12's fixture class, which queries `Bench_Sub.Item`. Fixture classes from other tasks stay in BENCHMARK between tasks, so a task can find another task's answer there. FR-023 covers classes a session writes, not other tasks' fixtures.

The skill's text is right, so the verdict does not move. §1 gives two-level and four-level examples but no three-level one, which is the case SKILL-09 tests (`Bench.Sub.Item` → `Bench_Sub.Item`). A three-level example is the one edit this points to, and it is left for a round with a new holdout task to measure it on.
