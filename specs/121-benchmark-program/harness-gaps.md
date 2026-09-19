# Things the harness says that are not true, and one it did not say at all

Recorded here because each was found by relying on it, and none belongs in the tool-defect list: a
document that does not exist, a rule that this build does not have, and a run that kept spending
after the thing it was measuring had gone away.

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

## The run kept paying after the container died

The graded tools run reached session 92 of 123 and then stopped producing verdicts. The host slept at
00:37 (`vmgr.log`: `level=info msg=sleep`), OrbStack's docker daemon came back at 00:55 answering
`docker info` with `containers=0 images=0` and an empty server version, and `iris-dev-iris` was gone
with it. Restarting OrbStack brought back 63 containers and 189 images — nothing was lost, the daemon
was wedged — and `docker start iris-dev-iris` was enough after that.

The harness handled the outage correctly one session at a time and wrongly in aggregate. Each
session recorded what happened instead of guessing:

```
CORPUS-36 tools+skills  the check did not answer: `iris-agentic-dev exec -n …` exited 1:
  Code contains block-syntax ({...}) that is not supported in terminal (docker exec) mode
CORPUS-37 bare          the task did not validate against IRIS before the session:
  could not determine source-control state for Bench.Avg.cls in BENCHMARK
```

`passed` is `None` on all four, which is right — a check that could not run has not failed the task.
But nothing was watching the sequence, so the run spent another 300-second session, and another, and
would have spent the remaining 31 the same way: about $2.60 of the cap buying a report with 31 holes
in it.

Fixed, with the tests first: `ladder.UNSCORED_ABORT = 3` and `LadderAborted`. Three consecutive
ungradeable sessions end the run, because one is a task whose check is wrong and two can still be
coincidence, while three in a row means the thing doing the grading is gone. The abort raises rather
than reporting, since a report over a run that stopped early prints a lift whose denominator is an
accident of when the container died.

The other half is `tests/e2e/skill_eval/resume.py`, which is what makes aborting cheap. Sessions were
always written to `<run_id>.runs.jsonl` as they landed; now `--remaining` reads them and names the
tasks that still owe a scored session, and `--merge` assembles several files into the one report the
straight-through run would have written. Two rules in it both move a number: an unscored session
counts as work still owed, and a later unscored session never displaces a verdict already earned.

The 92 sessions cost nothing to keep. The resume was 11 tasks — the three arms of any task with a
hole in it, re-run whole, because half a pair measured before the outage and half after is a pair
whose difference has two explanations.

One finding inside the finding: the grading call reached IRIS over `docker exec` rather than Atelier
REST, and `exec` in that mode cannot run `try {…}`. That is the documented `NoPWS` fallback working as
designed, and it means a check written in block syntax silently loses the ability to run when REST
goes away. Worth knowing before anyone points this corpus at an Enterprise 2026.2.0AI build, where
`docker_only=true` is the normal configuration rather than the degraded one.
