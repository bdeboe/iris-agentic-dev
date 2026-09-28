# objectscript-sql-patterns: why both arms score 0

Date: 2026-09-28. Evidence: r5 re-baseline (`2026-09-27T204612`), a captured skill-arm session, and three judge probes on SQLCODE-SILENT through the real `judge.score_result` (claude-sonnet-4-6, 3 samples each, about 30 judge calls in total).

## Verdict

The check is broken, not the agent, and the skill carries the same false claim the check does. The triage record's cause ("harness fixes will cure it") was wrong. I left the record unchanged.

## What the task claims

`tests/e2e/tasks/skills/targeted/SQLCODE-SILENT.yaml` says `If SQLCODE` fires on success and asks for `If SQLCODE '= 0`. Both halves are false on IRIS:

- SQLCODE 0 is falsy, so `If SQLCODE` fires on 100 and on negative codes, never on 0.
- `If SQLCODE '= 0` fires on exactly the same values. The fix the rubric asks for changes nothing.

The fixture's real silent bug is a different one. `EvalDemo_PatientLookup` is not a table, so `&sql` gets SQLCODE -30 at runtime and the method returns `""` for every MRN, the same value it returns for "no such patient". The class still compiles, because embedded SQL compiles deferred.

`SQLCODE-CHECK.yaml` has the same premise, and its fixture comments contradict each other.

## Judge probes

| Probe | Answer                                                                              | Scores |
| ----- | ----------------------------------------------------------------------------------- | ------ |
| P1    | No change: "`If SQLCODE` is false on 0"                                             | 0 0 0  |
| P2    | The rubric's own fix, `If SQLCODE '= 0` plus a 100 branch                           | 1 1 1  |
| P3    | Correct diagnosis (0 is fine, -30 is swallowed), splits 100 from <0, throws on <0   | 1 1 1  |
| P4    | The same split as P3 with a one-line explanation, returns `"ERROR: "_SQLCODE` on <0 | 3 3 3  |

- P1: the judge repeats the rubric's false premise in its reasoning, for example "misunderstanding that `If SQLCODE` fires on SQLCODE=0".
- P3 against P4: the code is the same fix and both put calls are cut identically. P3 fails because it says the rubric's premise is wrong and it checks the table first. P4 passes because it does neither. The judge gives "put call truncated" as its reason for P3 but not for P4, so the truncation is an excuse, not the cause.

The judge rewards an answer that agrees with the rubric and marks down the one that is right about IRIS.

## Second defect: the judge cannot see the code

`tests/e2e/skill_eval/judge.py:198` cuts tool args to 120 characters of JSON and `:201` cuts tool results to 200. For any `iris_doc put` the judge sees `{"mode": "put", "name": "EvalDemo.PatientLookup.cls", ...` and none of the class body. It also never sees the fixture from the `get`. 121 T021 fixed the same class of bug for assistant text (500 characters raised to 8000). Args and results were never raised. This touches every judged code-writing task, not just this one.

## What a real agent did

This is the captured skill-arm session, 171 events:

1. It loaded `objectscript-sql-patterns` and read the class.
2. `iris_table_info` showed that `EvalDemo_PatientLookup`, `EvalDemo.PatientLookup` and `EvalDemo.Patient` do not exist.
3. It searched USER, found an unrelated leftover table `PatientAPI.Record` with MRN data, and pointed the query at it.
4. It compiled, then ran `FindPatient` on five MRNs and got the right names.
5. It left `If SQLCODE` alone.

The agent found the real silent bug and verified its fix live. It also swallowed errors, as before, and borrowed a table that belongs to another test. Two other problems showed up:

- Shared USER state leaks into the task. `PatientAPI.Record` exists only because another test left it there.
- Two `iris_info what=documents inline=true` calls returned about 20 MB each. That is an iad output-size bug to draft separately.

## Skill defects (checked live on iris-dev-iris, `Test130.SqlCode`)

- §3, lines 95-96: WRONG says `If SQLCODE` "returns NOT FOUND when row EXISTS!". That is false. The real defect is treating 100 and <0 the same.
- §5, lines 130-131: `If SQLCODE < 0 { Return "" } // error` swallows the error. That is the pattern the task is about.
- §9, lines 203-205 and 220-222: says COUNT(\*) INTO leaves an undefined host variable empty. In fact it is 0 and defined.
- True and worth keeping: on SQLCODE 100 the INTO host variable is set to `""`.
- The frontmatter metadata is stale.

## Fix options

1. **Rewrite SQLCODE-SILENT (recommended, do first).** Keep the missing table, because it is the real silent failure. The rubric then asks for:
   - 100 and <0 split into separate branches;
   - a negative SQLCODE surfaced through `%msg`, a throw, or a status;
   - the correct table name, from a persistent class that the fixture creates, so the agent does not have to hunt through USER.

   Drop the `'= 0` requirement. Retire SQLCODE-CHECK or rewrite it the same way. Before any billable run, re-probe P1 to P4. The pass condition is that P3 and P4 both reach 2 or more and P1 and P2 score under 2. That costs cents.

2. **Raise the judge's arg and result caps.** Args should get at least the text limit (8000), at least for `content` and `code`. Results should get enough to show a fixture. Write the test first, the same way as `test_the_text_limit_is_not_below_what_the_judge_reads`. This changes what every judged skill measures, so the numbers need a re-baseline (about $3) before they are compared.
3. **Fix skill §§3, 5 and 9 using the 127 pattern.** Each fix needs a live `#[ignore]` test on `Test130.SqlCode` and a wording test that fails if the old claim comes back. Do this after option 1 has been measured, so the skill is not edited in the middle of a measurement.
4. **Triage record.** Once option 1 has been measured, replace the sql-patterns cause with "broken_check: rubric asserts a false IRIS fact; judge truncation". Leave the record alone until then.
5. **Isolate the fixture namespace or clean up leftovers**, so a task cannot be solved by borrowing another test's table.

Order: 1, then 2, then one sql-patterns-only measure (6 sessions), then 3 and 4. Run the full re-baseline only after 2 lands.
