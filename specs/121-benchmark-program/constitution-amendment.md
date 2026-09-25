# Staged constitution amendment: 1.5.3 → 1.5.4

**Feature**: 121-benchmark-program
**Status**: **drafted, not applied.** `.specify/memory/constitution.md` is in
`protected_files.extra` and `.claude/hooks/gates/protect-files.sh` blocks Edit and Write on it.
Applying this is the file owner's call, through `/speckit.constitution` or an explicit instruction.

Bump 1.5.3 → 1.5.4. PATCH — six rows added to the Bug Class Registry, no principle changed.

Five of the six were found by spec 121 while measuring something else, and the sixth is the one the
spec set out to prevent. None of them made a test fail; every one of them made a test, a document or
a CI run say something that was not so.

## Add to the Bug Class Registry table

| Class                                  | First shipped instance                                                                                                                                                    | Detector                                                  |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| Unpowered number published as a result | A lift reported from an item count whose MDE could not reach the gate threshold, so the figure could not have detected the effect it claimed                              | `test_a_comparison_below_the_floor_reports_underpowered`  |
| Figure outlives its harness            | The README advertised +27% for `objectscript-review` after the model-judged harness and 22-task corpus that measured it were both gone                                    | `tests/e2e/test_published_figures.py`                     |
| Test depends on an untracked artifact  | Three `test_pilot.py` tests opened `tests/e2e/results/pilot-121.json`, which the directory's `*.json` rule kept out of the repo; green locally, red on any clean checkout | `test_every_result_artifact_a_test_depends_on_is_tracked` |
| Suite named by file list               | CI ran three named Python files against a `tests/e2e` tree of ~1000 tests, so a new test file was covered only if someone remembered to add a step                        | `test_ci_runs_the_harness_as_a_directory_not_a_file_list` |
| Two systems answer one question        | Two benchmark harnesses over overlapping tasks, each with its own scorer and results layout, so a pass rate could not be traced to one of them                            | `tests/e2e/test_one_harness.py`                           |
| Hollow marker in a live filter         | `requires_iris` was registered in `conftest.py` and named in CI's `-m` filter while no test carried it; `pytest -m requires_iris` collected zero of 70 live-IRIS tests    | `test_iris_markers.py`                                    |

## Why each is a class and not an incident

**Unpowered number published as a result.** This is the class spec 121 exists for. A pass rate is
not a result unless the item count could have detected the effect being claimed; below that, an
interval containing zero has two readings — no effect, or not enough pairs to tell — and printing
the point estimate silently picks one. The registry row is the general statement of FR-008.

**Figure outlives its harness.** Nobody published a false number. The +27% was true when measured.
Then the corpus changed, the judge was replaced by an ObjectScript `PASS`/`FAIL` check, the harness
was retired, and the sentence stayed on the front page reading as current. The class is a claim
whose supporting apparatus is gone, and the detector is the general fix: every published figure ties
to an artifact in the repo, and drifts loudly when the artifact moves.

**Test depends on an untracked artifact.** The sharpest of the six, because it is invisible to the
machine that has the file. It was found by `git worktree add` and 40 seconds, and by nothing in
weeks before that. The general rule: a test that opens a file without guarding the open is asserting
that file is part of the repo.

**Suite named by file list.** A named-file step is correct on the day it is written and decays with
every file added after. Nothing announces the decay — the run still passes, over less. The rule is
that a suite is named by directory and narrowed by markers, because a marker travels with the test
and a file list does not.

**Two systems answer one question.** Two harnesses over overlapping tasks produce two pass rates
with no way to say which one a number came from, and the cost is paid at the moment somebody cites
one. Retiring the second is easy to undo by accident, which is why the decision is asserted by a
test rather than recorded in a document.

**Hollow marker in a live filter.** The marker was registered, documented and filtered on. It
selected nothing. CI was not wrong as a result — a module-level `skipif` on `docker ps` kept those
tests off a container-less runner — but the filter clause was decoration, and anyone typing
`pytest -m requires_iris` to run exactly the container tests got an empty run and a clean exit. The
class is a selector that names a set nothing belongs to.

## What this does not change

No principle, mandated section or quality gate moves. `plan-template.md`, `spec-template.md` and
`tasks-template.md` still agree with the constitution.

Two existing items are worth re-reading against these rows, but neither needs amending:

- **Principle XI, No Vacuous Tests** already covers "every skip is loud or opt-in". The skips here
  were loud. What was quiet was the absence of a file and the narrowness of a CI step, which XI does
  not reach — hence new rows rather than a broadened principle.
- **Principle IX, Tool Lift Requirement** requires lift ≥ +0.20 recorded in `lift-results.md` before
  merge. Spec 121 measured +0.829 for the tools, so the bar is met, and it measured +0.098 for the
  skills, which is not a tool. Nothing in IX needs to change, but it is worth noting that IX's bar
  was written before there was a harness that could tell +0.20 from noise at this corpus size; the
  floor in FR-008 is what makes the bar checkable rather than quotable.
