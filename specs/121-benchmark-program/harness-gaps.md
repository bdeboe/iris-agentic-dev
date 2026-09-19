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

**Done, after both graded runs landed** — deliberately not while they were in flight, since the spawn
point is the module they depend on. `tests/e2e/billing.py` holds `IAD_BILLABLE_SESSIONS`;
`assert_allowed` runs immediately before `Popen` in both spawn points, `opencode_runner.run_opencode`
and `PrimeAgentDriver.collect_events`; the four commands whose job is to spend — ladder, pilot, nightly
canary, and `python -m tests.e2e.skill_eval` — wrap their bodies in `billing.allow()`, which restores
the environment on the way out so one CLI call cannot leave the gate open behind it.

Running the directory found more than expected. Thirteen tests across nine files spawn real sessions, and
every one of them was guarded by nothing but `skipif(not os.environ.get("OPENAI_API_KEY"))` — which on
this laptop is always set. `pytest tests/e2e/skill_eval` was not a hypothetical forty dollars. A
`billable` marker now names them and `conftest.pytest_collection_modifyitems` skips them unless the env
var is set, so the sweep is green and silent rather than red. Two files drive the spawn path with a fake
`Popen` and opt in explicitly, in a fixture that says why.

What the gate cannot do is tell a fake subprocess from a real one, so the opt-in in those two files is a
statement of intent and not a measurement. The wallet is protected by the `Popen` call sites being the
only two, which `test_billing.py` asserts by patching them to raise.

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

## Two provenance fields described a run that did not happen

The finished report said `driver: "unrecorded"` and `skills_installed: {"tools+skills": []}`. Both are
false about the run they describe: opencode drove all 123 sessions, and the skills arm installed all 34
shipped documents. Nothing was wrong with the code that writes either field.

The cause is the same twice. A default was resolved in one module and read in another:

- `pilot.run_one` defaulted `driver` to `OpencodeDriver()`. `ladder.report` was handed `None`, and
  `provenance.driver_identity(None)` correctly answers `unrecorded` — it is documented as a stated fact
  for a run nobody attributed. This run was attributed; the report just did not ask.
- `run_one` reads an empty skill list as "install the whole pack" (`shipped_skills()`). `ladder.report`
  read the same empty list as "no skills". `pilot.report` had it right, which is why nobody caught it.

Fixed by removing the second opinion in each case. `opencode_driver.default_driver()` is now the one
place the harness builds a driver — `arms._default_driver` had a third copy, and since the arm
assertions decide what "the tools are absent" means, two that can drift is an arm checked under one
driver and run under another. `ladder.report` resolves the installed list the same way `run_one` does,
except on the pooled rung, where the empty list is the truth and `per_skill` carries the detail.

Five tests, written first. The provenance block on the published figure is restamped: opencode 1.14.17,
34 skills named.

Worth stating plainly, because the whole program rests on it: a provenance field cannot be trusted
because the function that formats it is correct. It can be trusted when something asserts it against
the run. The tests that now do this assert on `report`'s output, not on `driver_identity`'s.

## The fix landed six minutes after the run that needed it started

The pooled skills run was launched at 02:35:37. The driver fix was committed at 02:41:35. Python had
already imported `ladder.py`, so the skills report wrote `driver: "unrecorded"` out of code that no longer
existed on disk — and stamped `harness_commit: 8d0314b`, read by `git rev-parse` at report time, which
names a tree that would have got it right. A commit SHA in a provenance block says when the report was
written, not what code wrote it.

Rebuilding the report from `<run_id>.runs.jsonl` is exactly what `resume --merge` is for, and it could not
do it: it hard-coded the tools ladder. A pooled run merged through it reports a bare arm that never ran,
no `skill_verdict`, and no per-skill breakdown. Worse than a crash, because it produces a report.

`--pooled` now exists, tested first, seven tests. One of them is a refusal: `pooled_runs` relabels every
arm whose name starts with `tools+`, so merging the tools ladder under `--pooled` would fold its
34-document arm into the pooled rung and report it as twelve tasks against their own single skill.
`pooled_tasks_for` rejects any session whose task is not a skill task instead.

Same defect class as the two above, third instance: a mode declared in one place (`ladder.main` knows
what `--ladder skill --skill all` means) and not in the other that has to reproduce its output.
