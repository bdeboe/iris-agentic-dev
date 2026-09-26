"""`optimize run --surface hints`: loop on train items, gate on the holdout (spec 129 FR-009).

Same shape as `runner.run` for 128, with the hint scorer in place of the routing proxy. Four gates,
all on holdout items scored under both the seed and the candidate:

1. score: the paired bootstrap 95% interval for the score difference has its lower bound above 0;
2. reach: the candidate's reach rate is not below the seed's;
3. pass: the candidate's pass rate is not below the seed's;
4. ladder: the live ladder for the candidate is not below the seed's by more than `LADDER_MARGIN`.

A missing ladder is a failure. More than 10% of holdout items unscored makes the run invalid.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

from tests.e2e.skill_eval.optimize import gate, holdout, menu
from tests.e2e.skill_eval.optimize import hints_surface as hs
from tests.e2e.skill_eval.optimize.bootstrap import paired_diff_ci
from tests.e2e.skill_eval.optimize.hints_proxy import MAX_TOKENS, score_items
from tests.e2e.skill_eval.optimize.ledger import BudgetExceeded
from tests.e2e.skill_eval.optimize.runner import (
    PROMPT_OVERHEAD_TOKENS,
    RESERVE_FACTOR,
    RESULTS_ROOT,
    scorer_models,
    side,
)
from tests.e2e.skill_eval.scoring import UNSCORED_LIMIT

SPLIT_TITLE = "Spec 129 hints split"


def load_corpus():
    items = hs.load_items()
    split = holdout.load_split(hs.SPLIT)
    missing = {i["id"] for i in items} ^ set(split)
    if missing:
        raise holdout.SplitInvalid(
            f"{hs.SPLIT.name} and the corpus disagree on {sorted(missing)}; regenerate it "
            "with holdout.render_split"
        )
    return items, split


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def figures(rows) -> dict:
    scored = [r for r in rows if r.scored]
    n = len(rows)
    unscored = n - len(scored)
    f = {
        "n": n,
        "unscored": unscored,
        "valid": bool(n) and unscored / n <= UNSCORED_LIMIT,
    }
    if f["valid"]:
        f.update(
            reach=_mean([float(r.reach) for r in scored]),
            **{"pass": _mean([float(r.passed) for r in scored])},
            score=_mean([r.score for r in scored]),
        )
    return f


def decide(seed: dict, cand: dict, *, ladder: dict | None) -> gate.Verdict:
    ids = sorted(i for i in set(seed) & set(cand) if seed[i].scored and cand[i].scored)
    s = [seed[i] for i in ids]
    c = [cand[i] for i in ids]
    diff, lo, hi = (
        paired_diff_ci([r.score for r in s], [r.score for r in c])
        if ids
        else (0.0,) * 3
    )
    f = {
        "n": len(ids),
        "seed_score": _mean([r.score for r in s]),
        "cand_score": _mean([r.score for r in c]),
        "diff": diff,
        "diff_lo": lo,
        "diff_hi": hi,
        "seed_reach": _mean([float(r.reach) for r in s]),
        "cand_reach": _mean([float(r.reach) for r in c]),
        "seed_pass": _mean([float(r.passed) for r in s]),
        "cand_pass": _mean([float(r.passed) for r in c]),
        "ladder": ladder,
    }
    failed = []
    if not lo > 0:
        failed.append(
            f"score: interval lower bound {lo:+.3f} is not above 0 (diff {diff:+.3f}, n={len(ids)})"
        )
    if f["cand_reach"] < f["seed_reach"]:
        failed.append(
            f"reach: {f['cand_reach']:.3f} is below the seed's {f['seed_reach']:.3f}"
        )
    if f["cand_pass"] < f["seed_pass"]:
        failed.append(
            f"pass: {f['cand_pass']:.3f} is below the seed's {f['seed_pass']:.3f}"
        )
    if ladder is None:
        failed.append("ladder: no live ladder run")
    elif ladder["candidate"] < ladder["seed"] - gate.LADDER_MARGIN - 1e-12:
        failed.append(
            f"ladder: {ladder['candidate']:.3f} is more than {gate.LADDER_MARGIN} below "
            f"the seed's {ladder['seed']:.3f}"
        )
    return gate.Verdict(gate.HOLD if failed else gate.SHIP, failed, f)


def estimate_call_usd(ledger, model: str, skills) -> float:
    rin, rout = ledger._rate(model)
    tokens_in = len(menu.render_menu(skills)) / 4 + PROMPT_OVERHEAD_TOKENS + 200
    return (tokens_in * rin + MAX_TOKENS * rout) / 1e6 * ledger.multiplier


def _fmt(fig):
    if not fig:
        return "not measured"
    if not fig["valid"]:
        return f"invalid: {fig['unscored']} of {fig['n']} unscored"
    return (
        f"score {fig['score']:.3f}, reach {fig['reach']:.3f}, pass {fig['pass']:.3f} "
        f"(n={fig['n']}, unscored {fig['unscored']})"
    )


def render_report(
    *, run_id, verdict, seed_fig, cand_fig, ledger, info, changed, scorer
):
    lines = [
        f"# Hints run {run_id}",
        "",
        f"Verdict: {verdict.verdict}",
        "",
        f"Stopped on {info.get('stopped')}. Spend ${ledger.total_usd:.2f} of "
        f"${ledger.budget_usd:.2f}. Scorer {scorer}.",
        "",
        "## Holdout",
        "",
        f"- Seed: {_fmt(seed_fig)}",
        f"- Candidate: {_fmt(cand_fig)}",
    ]
    if verdict.figures:
        g = verdict.figures
        lines.append(
            f"- Score difference {g['diff']:+.3f}, 95% interval "
            f"[{g['diff_lo']:+.3f}, {g['diff_hi']:+.3f}]"
        )
    lines += ["", "## Failed gates", ""]
    lines += [f"- {f}" for f in verdict.failed] or ["- none"]
    lines += ["", "## Changed hints", ""]
    lines += [f"- `{k}`: {v}" for k, v in sorted(changed.items())] or ["- none"]
    lines += [
        "",
        f"Proposals accepted {len(info.get('proposals', []))}, rejected "
        f"{len(info.get('rejections', []))}.",
    ]
    return "\n".join(lines)


def run(
    *,
    client,
    model,
    reflect,
    ledger,
    checker,
    max_metric_calls=600,
    ladder=None,
    out_root=RESULTS_ROOT,
    root=menu.SKILLS_ROOT,
    workers=8,
    run_id=None,
    max_seconds=None,
) -> Path:
    """Loop on train, score seed and finalist on the holdout, gate, write the run directory."""
    from tests.e2e.skill_eval.optimize.adapter import run_loop  # needs pinned gepa
    from tests.e2e.skill_eval.optimize.hints_adapter import HintsAdapter

    run_id = run_id or f"{_dt.datetime.now(_dt.timezone.utc):%Y%m%dT%H%M%SZ}-hints"
    run_dir = Path(out_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    if ledger.stream_path is None:
        ledger.stream_path = run_dir / "ledger.jsonl"

    items, split = load_corpus()
    rules = hs.load_rules()
    skills = menu.load_skills(root)
    seed = {r.id: r.text for r in rules}
    hold = side(items, split, holdout.HOLDOUT)
    adapter = HintsAdapter(
        rules,
        skills,
        client,
        model,
        ledger,
        reflect=reflect,
        split=split,
        checker=checker,
        workers=workers,
        contexts=hs.contexts(root=root),
    )
    reserve = 2 * len(hold) * estimate_call_usd(ledger, model, skills) * RESERVE_FACTOR
    best, info = run_loop(
        adapter,
        side(items, split, holdout.TRAIN),
        max_metric_calls=max_metric_calls,
        seed=129,
        reserve_usd=reserve,
        max_seconds=max_seconds,
    )

    seed_fig = cand_fig = None
    models: list[str] = []
    try:
        s_rows = score_items(
            hold, skills, seed, client, model, ledger, checker, workers=workers
        )
        c_rows = score_items(
            hold, skills, best, client, model, ledger, checker, workers=workers
        )
        seed_fig, cand_fig = figures(s_rows), figures(c_rows)
        models = scorer_models(s_rows + c_rows)
    except BudgetExceeded:
        info["stopped"] = "budget"
        verdict = gate.Verdict(
            gate.HOLD, ["measurement: budget ran out before the holdout was scored"], {}
        )
    else:
        if not (seed_fig["valid"] and cand_fig["valid"]):
            verdict = gate.Verdict(
                gate.HOLD, ["measurement: more than 10% of holdout items unscored"], {}
            )
        elif len(models) > 1:
            verdict = gate.Verdict(
                gate.HOLD,
                [f"measurement: scorer answered as {models}; arms not comparable"],
                {},
            )
        else:
            verdict = decide(
                {r.id: r for r in s_rows}, {r.id: r for r in c_rows}, ladder=ladder
            )

    changed = {k: v for k, v in best.items() if seed.get(k) != v}
    scorer = ", ".join(models) or model
    (run_dir / "candidate.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "surface": "hints",
                "verdict": verdict.verdict,
                "failed": verdict.failed,
                "gate_figures": verdict.figures,
                "seed_figures": seed_fig,
                "candidate_figures": cand_fig,
                "scorer_model": scorer,
                "stopped": info.get("stopped"),
                "descriptions": changed,
                "proposals": info.get("proposals", []),
                "rejections": info.get("rejections", []),
            },
            indent=2,
        )
        + "\n"
    )
    ledger.write(run_dir / "ledger.jsonl")
    (run_dir / "report.md").write_text(
        render_report(
            run_id=run_id,
            verdict=verdict,
            seed_fig=seed_fig,
            cand_fig=cand_fig,
            ledger=ledger,
            info=info,
            changed=changed,
            scorer=scorer,
        )
        + "\n"
    )
    return run_dir
