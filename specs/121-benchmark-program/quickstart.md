# Running the benchmark

This is the harness behind [`results.md`](results.md): 62 ObjectScript tasks, three arms
(bare model, model + iad tools, model + tools + skills), and a paired comparison over the
holdout split. Every task is graded by an ObjectScript check that prints `PASS` or `FAIL`
against a live IRIS container. No model scores anything.

The 62 are 42 `CORPUS`, 12 `SKILL` and 8 `PILOT`. The tools rung runs the 41 that are on
the holdout side and are not skill-specific, which is where the published figures come
from.

A full graded run spawns 123 real agent sessions and costs about $10. Most of what you
need to check costs nothing, so start there.

## Prerequisites

The IRIS container the tasks run against:

```bash
docker ps --filter name=iris-dev-iris
```

If it is not up, start it — every check is a fixture that talks to it. Then:

```bash
cd iris-agentic-dev
export PYTHONPATH=.
export IRIS_HOST=localhost IRIS_WEB_PORT=52780
export IRIS_USERNAME=_SYSTEM IRIS_PASSWORD=SYS
```

Python 3.11+, plus `pytest`, `pyyaml` and `requests`. The `anthropic` SDK is only needed
to spawn sessions; everything below this line runs without it.

## What you can check for free

The whole harness under test:

```bash
python3 -m pytest tests/e2e/skill_eval benchmark/harbor -q
```

Budget 5–10 minutes with the container up. `test_graded_task_live.py` runs every committed
task against real IRIS twice — once against the fixture to prove the check fails, once
against the reference solution to prove it passes — and 62 tasks of that is most of the
wall clock. With the container down those tests skip and the run finishes in under a
minute, which looks like the same green and is not: nothing checked whether a single task
still discriminates. Add `-v` if you want to watch it move.

CI runs the same tests with `-m "not requires_iris and not network_curl and not billable"`.
The live task validation is not in that filter — it excuses itself, with a module-level
`skipif` that shells out to `docker ps`. So CI genuinely does not check task
discrimination, and the only place that happens is a developer machine or the nightly.
Which is the reason to run it here with the container up.

The corpus and the split, which is the check that refuses to load a corpus where any task
ID is missing from both sides of `tests/e2e/tasks/benchmark/split.toml`:

```bash
python3 -c "
from tests.e2e.skill_eval.graded_task import all_tasks
from tests.e2e.skill_eval.split import default_split
tasks, split = all_tasks(), default_split()
print(len(tasks), 'tasks;', len(split.train), 'train', len(split.holdout), 'holdout')
"
# 62 tasks; 9 train 53 holdout
```

What a graded run would cost and which tasks it would touch, with no session started:

```bash
python3 -m tests.e2e.skill_eval.ladder --dry-run --spent 13.10
```

`--spent` is dollars already spent in this program; the estimate projects against the cap
so you can see the answer before committing to it, not after.

Regenerate the published per-tool table from the committed run artifact. It rewrites
`lift-results.md` in place, so `git diff` is the assertion — a clean diff means the
document still matches its data:

```bash
python3 -m tests.e2e.skill_eval.attribution \
  tests/e2e/results/ladder-121-tools-holdout.json
git diff --stat specs/121-benchmark-program/lift-results.md
```

## A graded run

This spends money. The gate is an env var, not a flag, so no stray `pytest` invocation
can start a session:

```bash
export IAD_BILLABLE_SESSIONS=1
python3 -m tests.e2e.skill_eval.ladder \
  --ladder tools \
  --out tests/e2e/results/ladder-$(date +%Y%m%d)-tools-holdout.json
```

It writes `<run_id>.runs.jsonl` as it goes, one line per session, before it writes any
report. That file is the run; the report is a view of it.

The skills rung is a separate invocation, and it answers a different question — whether
the bundled skills add anything on top of the tools:

```bash
python3 -m tests.e2e.skill_eval.ladder --ladder skill --skill all
```

### When a run dies halfway

4.25 hours serial is long enough that something will. Nothing is lost — ask what is still
owed, then run only that:

```bash
python3 -m tests.e2e.skill_eval.resume <run_id>.runs.jsonl --remaining
python3 -m tests.e2e.skill_eval.ladder --task CORPUS-17 --task CORPUS-23 ...
python3 -m tests.e2e.skill_eval.resume *.runs.jsonl --merge --out report.json
```

`--merge` builds the report from every session file you hand it, so a run assembled from
four fragments and a run that finished in one sitting produce the same document.

## Reading the result

```
bare -> tools           lift +0.829  [+0.714, +0.944]  n=41  b=34 c=0  p=0.0000  passed
```

`n` is paired items, not sessions. `b` and `c` are the discordant pairs — `b` tasks the
right arm solved and the left did not, `c` the reverse — and they are the whole test;
concordant pairs carry no information about which arm is better. The interval is Wilson.

A comparison publishes only if it comes from the holdout split and clears 37 pairs
(FR-008). Below that the interval is wide enough to contain lifts you would act on
differently, so the number is not worth printing. `assert_publishable_from_holdout`
enforces both and raises rather than degrading, which is why a leaked train task is a
crash and not a footnote.

For skills specifically the bar is higher: `b >= 4` and `c <= 1`. The skills rung returned
`b=6 c=2`, so the verdict is indistinguishable, not positive. See
[`skills-verdict.md`](skills-verdict.md).

## Adding a task

Tasks live in `tests/e2e/tasks/benchmark/corpus/`. Each needs three things:

1. A check that prints exactly `PASS` or `FAIL` against live IRIS.
2. A reference solution that passes it.
3. A fixture that fails it before the agent touches anything.

The third is the one people skip, and without it a task that passes in all three arms
tells you nothing — it may have been passing before the agent arrived.

Add the ID to the `holdout` side of `split.toml`. New tasks belong there: the train side
exists for the GEPA optimizer to fit against, and a task that has been tuned against
cannot also be evidence.
