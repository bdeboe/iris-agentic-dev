"""The recorded triage verdicts — 121 T021, T022, T023.

Six of the nine gated skills read a saturated task set in `tests/e2e/results/skill-baseline.json`:
four flat at 0.00 against 0.00, one at 0.80 against 1.00, one at 0.10 against 0.00. `triage.py`
refuses to let one sit unexplained; this is where the explanations live, and
`test_triage.py::test_every_saturated_set_in_the_committed_baseline_has_a_verdict` checks them
against the committed baseline on every run.

Every verdict here was reached by probing the check itself rather than by re-running the arms:
a hand-written reference solution and an untouched fixture, both through the real judge
(`benchmark/021/runner/judge.py`, Sonnet 4.6 on Bedrock, `PASS_THRESHOLD = 2`). All five probed
checks scored the reference 3/3/3 and the untouched fixture 0/0/0. The checks discriminate. The
recorded floors were the harness's, and two defects account for them:

1. `lift.format_transcript` cut every assistant message to 500 characters before the judge saw it.
   An ObjectScript class does not fit in 500 characters. Fixed: `TRANSCRIPT_TEXT_LIMIT = 8000`.
2. A session killed at `opencode_runner.run_opencode`'s 300 s timeout came back the same shape as a
   finished one and was scored 0. Fixed: `lift.session_evidence_gap` returns unscored instead.

Probe and live-run artifacts are under `/tmp/t021/` and summarised in `research.md` § triage, which
is the durable record — `/tmp` is not.
"""

from __future__ import annotations

from tests.e2e.skill_eval.triage import TriageRecord, TriageVerdict

# T021 — the four floors. All four are `broken_check`: the measurement could not register what the
# agent did. That is a verdict on the harness, not on the rubric; each rubric scores a correct
# answer 3 and an untouched fixture 0.
_FLOORS = [
    TriageRecord(
        skill="iris-connectivity",
        verdict=TriageVerdict.BROKEN_CHECK,
        evidence=(
            "IRIS-PYTHON-CONNECT, 0/5 both arms. Reference solution 3/3/3 and untouched fixture "
            "0/0/0 through the real judge. One live baseline session scored 1, every assistant "
            "text turn exactly 500 characters long, and the judge's own reasoning said why: "
            '"only provided a partial template description before cutting off". A connection '
            "script does not fit in 500 characters, so no agent could have cleared this set."
        ),
        action=(
            "Fixed at source: `lift.TRANSCRIPT_TEXT_LIMIT` 500 → 8000, matching "
            "`runner.judge._format_transcript`'s own per-turn cap so neither side silently decides "
            "what the scorer sees. Three tests in `test_lift.py` hold the bound."
        ),
    ),
    TriageRecord(
        skill="objectscript-list-patterns",
        verdict=TriageVerdict.BROKEN_CHECK,
        evidence=(
            "LIST-ITERATE, 0/5 both arms. Reference solution 3/3/3 once it writes the class back "
            'with `iris_doc(mode="put", compile=true)` — my first reference read and compiled but '
            "never wrote, and the judge said exactly that, which is the transcript's fault and not "
            "the check's. The recorded floor does not reproduce: one live baseline session scored 2, "
            "a pass, over 32 tool calls, against a file recording 0.00 over five runs per arm."
        ),
        action=(
            "Covered by the transcript-limit fix. The set stays in the corpus and is re-measured in "
            "Phase 4; its recorded 0.00 is withdrawn rather than published."
        ),
    ),
    TriageRecord(
        skill="objectscript-sql-patterns",
        verdict=TriageVerdict.BROKEN_CHECK,
        evidence=(
            "SQLCODE-SILENT, 0/5 both arms. Reference solution 3/3/3, untouched fixture 0/0/0. The "
            "live baseline session was killed at `opencode_runner`'s 300 s timeout after one turn "
            '("Let me begin by searching…") with zero completed tool calls, and the harness scored '
            "that 0. A killed session and a finished one came back as the same list of events, so "
            "there was nothing in the result to tell them apart."
        ),
        action=(
            "Fixed at source: `lift.session_evidence_gap` returns `runner.judge.unscored` — "
            "`score: None`, never 0 — when a session neither reached `session.status … idle` nor "
            "completed a single tool call. Six tests in `test_lift.py` hold the rule, including the "
            "conservative half: a session killed *after* real work is still scored."
        ),
    ),
    TriageRecord(
        skill="objectscript-unit-test",
        verdict=TriageVerdict.BROKEN_CHECK,
        evidence=(
            "GEN-01 and GEN-02, 0/10 both arms. Two independent defects. The task set does not "
            "exercise the skill at all: `tests/e2e/tasks/skills/objectscript-unit-test/eval.yaml` "
            "names `benchmark_tasks: [GEN-01, GEN-02]`, which are plain class-generation prompts "
            "with no %UnitTest class in them. And the floor is not real either — GEN-01's reference "
            "scores 3/3/3, and one live baseline session scored 3, a pass, over 4 tool calls."
        ),
        action=(
            "Task set retired. A skill that generates %UnitTest classes needs tasks that ask for "
            "one; GEN-01/GEN-02 measure the class generator. Phase 4's corpus writes the "
            "replacement under FR-004 (a check that fails against the untouched fixture) and "
            "FR-022 (a reference solution that passes it). Until then this skill has no gated "
            "number, which is the honest state — deleting the set is an acceptable outcome, "
            "publishing 0.00 was not."
        ),
    ),
]

# T022 — the ceiling and the two negative lifts.
_CEILING_AND_NOISE = [
    TriageRecord(
        skill="objectscript-guardrails",
        verdict=TriageVerdict.TOO_EASY,
        evidence=(
            "TIMESTAMP-FORMAT, 4/5 baseline against 5/5 with the skill. The skill arm is at the "
            "ceiling, so the largest lift this set can ever report is 0.20 — exactly "
            "`comparison.GATE_THRESHOLD`, while `mde_paired(5, 0.20)` is 0.4334. The set cannot "
            "resolve its own maximum possible effect. Wilson at 4/5 is [0.376, 0.964] and at 5/5 is "
            "[0.566, 1.000]: the two arms' intervals overlap over two thirds of the scale. The "
            "baseline already passes this task four times in five without the skill."
        ),
        action=(
            "One-task set retired from the gate. FR-014's rule holds — a set with an arm at the "
            "ceiling reports no lift — and the guardrails skill gets items in Phase 4's corpus that "
            "a bare arm fails, or it gets no number. It is not deleted from the corpus: the task is "
            "a valid check, it is just not a measurement of this skill."
        ),
    ),
    TriageRecord(
        skill="ensemble-production",
        verdict=TriageVerdict.NOT_HELPED,
        evidence=(
            "ENSEMBLE-APPROACH-CHOICE and ENSEMBLE-PYPROD, 1/10 baseline against 0/10 with the "
            "skill — one discordant pair in ten. `mde_paired(10, 0.10)` is 0.2482, so the "
            "reported −0.10 is well inside the noise this set can produce, and Wilson gives "
            "[0.018, 0.404] against [0.000, 0.278]. Not harm: a single item. Not help either. The "
            "floor is censored — the skill arm is at 0.00, so a real regression larger than 0.10 "
            "would be invisible here — which is why this needs a verdict rather than a shrug."
        ),
        action=(
            "Recorded as no measured effect and explicitly not as harm. Ten pairs cannot resolve "
            "0.20: `n_for_effect_paired(0.20, 0.10)` is 18 pairs and 37 at discordance 0.20. Phase "
            "4's per-skill ladder runs this set at the recomputed floor or drops it; either way the "
            "−0.10 is withdrawn and never published as a regression."
        ),
    ),
    TriageRecord(
        skill="iris-ai-hub",
        verdict=TriageVerdict.NOT_HELPED,
        evidence=(
            "Six tasks, 12/30 baseline against 9/30 with the skill. Not saturated — the check "
            "discriminates in both arms — and the −0.10 is under the 0.20 the gate calls an effect. "
            "`mde_paired(30, 0.10)` is 0.1555, so this is the one set of the three whose lift is "
            "close to its own resolution: three discordant pairs would have to become five before "
            "the number meant anything."
        ),
        action=(
            "Recorded as no measured effect. This set is the closest of the nine to a real "
            "measurement and the cheapest to make one: 30 pairs already, and 18 suffice at the "
            "measured discordance. It stays in the gate and is re-measured in Phase 4 with the "
            "transcript-limit fix in place, since all 30 items were scored through the 500-character "
            "judge."
        ),
    ),
]

# 130 round 4 — the 2026-09-29T031029 re-baseline. Three sets of 3 and 6 pairs each came back with one
# arm at an end of the scale. At these sizes one session moves an arm by 0.17 or 0.33, so a flat arm
# is what small sets do, and the verdicts say that rather than read an effect into it. Each entry is
# withdrawn in the baseline, so none of these figures is a comparison basis.
_ROUND_4 = [
    TriageRecord(
        skill="iris-connectivity",
        verdict=TriageVerdict.NOT_HELPED,
        evidence=(
            "IRIS-PYTHON-CONNECT, 3/3 baseline against 2/3 with the skill, one discordant pair. "
            "The 2026-09-27 run read 1/3 against 2/3, the other way round. The floor for this set is "
            "63 pairs; three cannot tell -0.33 from +0.33, and the two runs did not."
        ),
        action=(
            "No measured effect, and not harm: the -0.33 is withdrawn and never published as a "
            "regression. The set needs more tasks before it can gate anything."
        ),
    ),
    TriageRecord(
        skill="objectscript-review",
        verdict=TriageVerdict.NOT_HELPED,
        evidence=(
            "3/3 baseline against 2/3 with the skill, one discordant pair; the 2026-09-27 run read "
            "2/3 against 2/3. Three pairs against a floor of 63."
        ),
        action=(
            "No measured effect, and not harm: the -0.33 is withdrawn. The set needs more tasks "
            "before it can gate anything."
        ),
    ),
    TriageRecord(
        skill="iris-vector-ai",
        verdict=TriageVerdict.TOO_HARD,
        evidence=(
            "Pattern-scored, 0/6 baseline against 4/6 with the skill; the 2026-09-27 run read 1/6 "
            "against 4/6. The bare arm passes one task in twelve over the two runs, so it sits at "
            "the floor and a regression in the skill arm below it could not be reported. Too hard "
            "for the bare arm, not for the skill arm."
        ),
        action=(
            "The +0.67 is withdrawn as a lift claim: six pairs against a floor of 129. The set stays "
            "in the corpus; it needs tasks the bare arm can sometimes pass before a lift from it "
            "means anything."
        ),
    ),
    # Not from the re-baseline: the 2026-09-28 review of the sql-patterns floor. It replaces T021's
    # record, which found only the killed-session half.
    TriageRecord(
        skill="objectscript-sql-patterns",
        verdict=TriageVerdict.BROKEN_CHECK,
        evidence=(
            "SQLCODE-SILENT and SQLCODE-CHECK, 0.00 both arms after every harness fix. The rubric "
            "said `If SQLCODE` fires on success; 0 is falsy, so it does not, and the `If SQLCODE "
            "'= 0` it asked for fires on the same values. The judge took up the rubric's claim and "
            "could not check it against the code: tool args were cut to 120 characters and results "
            "to 200. The skill's §3 made the same false claim "
            "(specs/130-content-skills/sql-patterns-review.md)."
        ),
        action=(
            "Both task files deleted and the baseline row dropped (FR-018). The judge reads tool "
            "args and results up to 8000 characters (FR-013). §§3, 5, 9 fixed with live tests "
            "(T045). SKILL-21 (train) is the task the fix was fitted to; SKILL-09 (holdout) is the "
            "ladder measure."
        ),
    ),
]

# The baseline run every verdict above was reached on. An entry measured by a later run with no
# withdrawn block supersedes its verdict — `triage.verdict_superseded`.
VERDICTS_REACHED_ON = "2026-09-12T171550"

ALL_RECORDS: dict[str, TriageRecord] = {
    record.skill: record for record in (*_FLOORS, *_CEILING_AND_NOISE, *_ROUND_4)
}

# Verdicts a later run cured, with the run that did it. Both sets read 0.00 against 0.00 before the
# transcript fix and 0.33 against 0.67 on the 2026-09-27 re-baseline, so the check registers the
# agent now. They stay above as history and leave the live records: a verdict on a set that
# discriminates is stale, and `validate_corpus` says so.
#
# The 2026-09-29 re-baseline read ensemble-production at +0.33 and iris-ai-hub at +0.22, both over the
# gate, so their not_helped verdicts are stale and go the same way. Neither figure is a lift claim
# (6 and 18 pairs against floors of 63 and 129). iris-connectivity's 2026-09-27 cure did not hold; it
# has a round-4 verdict and is live again. A round-4 record replaces its T021 one in ALL_RECORDS.
SUPERSEDED: dict[str, str] = {
    "objectscript-list-patterns": "2026-09-27T204612",
    "ensemble-production": "2026-09-29T031029",
    "iris-ai-hub": "2026-09-29T031029",
}

RECORDS: dict[str, TriageRecord] = {
    name: record for name, record in ALL_RECORDS.items() if name not in SUPERSEDED
}

# The two verdicts whose action was to take the task set out of the gate rather than fix the harness
# around it: one set measures the wrong thing, the other cannot resolve its own maximum effect.
# `test_triage.py` checks each one's `eval.yaml` really has no `benchmark_tasks` left, because
# "retired" written here and `benchmark_tasks: [GEN-01, GEN-02]` still in the config is exactly the
# state that reads as acted on and is not.
#
# 130 round 4 (FR-018) adds sql-patterns: SQLCODE-SILENT and SQLCODE-CHECK assert a false IRIS fact
# (`If SQLCODE` firing on success), so both task files are gone and the skill is measured on the
# ladder instead, SKILL-21 on train and SKILL-09 on the holdout.
RETIRED_TASK_SETS: frozenset[str] = frozenset(
    {"objectscript-unit-test", "objectscript-guardrails", "objectscript-sql-patterns"}
)
