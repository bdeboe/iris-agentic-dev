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

## Out of scope

- Fixing the iad bugs drafted in R3, R6 and R7.
- HL7 and embedded Python (blocked).
