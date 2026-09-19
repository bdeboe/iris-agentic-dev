# Two things the harness says that are not true

Recorded here because both were found by relying on them, and neither belongs in the tool-defect
list: one is a document that does not exist and one is a rule that this build does not have.

## The "safe file list" is not written down anywhere

Working practice for this program has been: never run `pytest tests/e2e/skill_eval` as a directory,
because files in it spawn billable agent sessions. The list of files that are safe to run is
supposed to live in `specs/120-repo2rlenv-rl-env/tasks.md`. It does not. There is no list in that
file, and there never was one.

What has actually happened every time is that the safe set was re-derived by grep — looking for
`run_one`, `collect_events`, `run_ladder` — and then only explicit file paths were passed to
pytest. That works because it is conservative, and it is fragile for the same reason: it depends on
whoever runs the tests remembering to do it, and the grep over-reports. `test_ladder.py` and
`test_pilot.py` both mention `run_one` and neither spends a cent, so a list built from that grep
would name two safe files as dangerous, and the next person to notice that would relax the rule.

I did not write the list, because a list is the weaker fix and the wrong shape of one is worse than
none: a file declared safe that later grows a live test bills real money on the next nightly.

The fix I want is an opt-in at the spawn point. Make the driver refuse to start a session unless
something explicitly asks for one — an env var the ladder and pilot commands set and pytest does
not — so `pytest tests/e2e/skill_eval` as a directory cannot spend money whatever it collects, and
the rule stops depending on anyone's memory. Then the list is documentation instead of a control.

Not done yet, and deliberately not done while the 123-session graded run was in flight: the spawn
point is the module that run depends on. It is the next harness change after the run lands.

## `SELECT TOP` with `ORDER BY` works on this build

`CLAUDE.md` says, under ObjectScript SQL rules: no `ORDER BY` with `SELECT TOP`. On
`intersystemsdc/iris-community:2026.2` it is fine:

```
$ iris-agentic-dev query "SELECT TOP 3 Name FROM %Dictionary.ClassDefinition ORDER BY Name"
Name
%ASQ.AST
%ASQ.ArraySequence
%ASQ.Engine
```

Three rows, ordered, no error. The corpus was written around the prohibition before I checked, so
some tasks avoid a construction they did not need to avoid.

One positive result on one Community build is not grounds for deleting the rule — it may hold on
older builds, and the reason it was written down is not recorded. What it is grounds for is looking
it up: check the InterSystems SQL reference for the version range, then either scope the rule to
those versions or drop it. Until then it stands, because a rule that costs a rewritten query is
cheaper than a wrong query on a customer's instance.
