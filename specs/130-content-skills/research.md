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
