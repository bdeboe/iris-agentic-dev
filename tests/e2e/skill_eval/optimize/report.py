"""Holdout figures, the run report and the run directory (spec 128 FR-004, FR-010).

A figure is computed from scored items only. More than `scoring.UNSCORED_LIMIT` unscored and the run
is invalid: `figures` returns the counts and no rates, so nothing downstream can quote one.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.e2e.skill_eval.optimize.gate import SKILL_SLICES, Outcome
from tests.e2e.skill_eval.scoring import UNSCORED_LIMIT
from tests.e2e.skill_eval.stats import wilson_interval


def outcomes(items, routed) -> dict:
    by_id = {i["id"]: i for i in items}
    return {
        r.id: Outcome(by_id[r.id]["slice"], bool(r.correct)) for r in routed if r.scored
    }


def figures(items, routed) -> dict:
    by_id = {i["id"]: i for i in items}
    unscored = [r for r in routed if not r.scored]
    f = {
        "n": len(routed),
        "unscored": len(unscored),
        "valid": len(unscored) <= UNSCORED_LIMIT * len(routed),
    }
    if not f["valid"]:
        f["unscored_reasons"] = sorted({r.reason for r in unscored})[:5]
        return f
    scored = [r for r in routed if r.scored]
    skill = [r for r in scored if by_id[r.id]["slice"] in SKILL_SLICES]
    exact = [r for r in scored if by_id[r.id]["slice"] == "exact-name"]
    none = [r for r in scored if by_id[r.id]["slice"] == "no-skill"]
    hits = sum(r.correct for r in skill)
    lo, hi = wilson_interval(hits, len(skill)) if skill else (0.0, 1.0)
    f.update(
        recall_n=len(skill),
        recall=hits / len(skill) if skill else 0.0,
        recall_lo=lo,
        recall_hi=hi,
        exact_n=len(exact),
        exact=sum(r.correct for r in exact) / len(exact) if exact else 0.0,
        false_hint_n=len(none),
        false_hint=sum(not r.correct for r in none) / len(none) if none else 0.0,
    )
    return f


def _fig_line(label, f):
    if not f:
        return f"| {label} | not measured | | | |"
    if not f.get("valid"):
        return f"| {label} | invalid: {f['unscored']} of {f['n']} unscored | | | |"
    return (
        f"| {label} | {f['recall']:.3f} [{f['recall_lo']:.3f}, {f['recall_hi']:.3f}] (n={f['recall_n']}) "
        f"| {f['false_hint']:.3f} (n={f.get('false_hint_n', '?')}) | {f['exact']:.3f} (n={f.get('exact_n', '?')}) | {f['unscored']} |"
    )


def render(
    *, run_id, surface, verdict, seed_fig, cand_fig, ledger, info, scorer_model, changed
) -> str:
    v = verdict
    lines = [
        f"# Routing run {run_id}",
        "",
        f"Surface `{surface}`. Scorer `{scorer_model}`. Spend ${ledger.total_usd:.2f} of ${ledger.budget_usd:.2f}; stopped on {info.get('stopped', 'n/a')}.",
        "",
        f"## Verdict: {v.verdict}" if v else "## Verdict: none (measurement only)",
        "",
    ]
    if v and v.failed:
        lines += ["Failed gates:", ""] + [f"- {x}" for x in v.failed] + [""]
    if v and "diff" in v.figures:
        g = v.figures
        lines += [
            f"Paired Recall@1 difference, candidate minus seed: {g['diff']:+.3f}, 95% bootstrap interval [{g['diff_lo']:+.3f}, {g['diff_hi']:+.3f}].",
            "",
        ]
    lines += [
        "## Holdout figures",
        "",
        "| Arm | Recall@1 [95% Wilson] | False-hint rate | Exact-name Recall@1 | Unscored |",
        "| --- | --- | --- | --- | --- |",
        _fig_line("seed", seed_fig),
        _fig_line("candidate", cand_fig),
        "",
    ]
    if info.get("proposals") is not None:
        lines += [
            "## Loop",
            "",
            f"{len(info.get('proposals', []))} proposals passed the validator; {len(info.get('rejections', []))} were rejected before scoring. "
            f"Train {info.get('train_n', '?')}, val {info.get('val_n', '?')}.",
            "",
        ]
        if changed:
            lines += [
                "Changed descriptions: "
                + ", ".join(f"`{n}`" for n in sorted(changed))
                + ".",
                "",
            ]
    return "\n".join(lines)


def write_run(
    out_dir,
    *,
    surface,
    seed,
    candidate,
    verdict,
    seed_fig,
    cand_fig,
    ledger,
    info,
    scorer_model,
) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    changed = {k: v for k, v in candidate.items() if seed.get(k) != v}
    (out / "candidate.json").write_text(
        json.dumps(
            {
                "run_id": out.name,
                "surface": surface,
                "verdict": verdict.verdict if verdict else None,
                "failed": verdict.failed if verdict else [],
                "gate_figures": verdict.figures if verdict else {},
                "seed_figures": seed_fig,
                "candidate_figures": cand_fig,
                "scorer_model": scorer_model,
                "stopped": info.get("stopped"),
                "descriptions": changed,
                "rejections": info.get("rejections", []),
            },
            indent=2,
        )
        + "\n"
    )
    ledger.write(out / "ledger.jsonl")
    (out / "report.md").write_text(
        render(
            run_id=out.name,
            surface=surface,
            verdict=verdict,
            seed_fig=seed_fig,
            cand_fig=cand_fig,
            ledger=ledger,
            info=info,
            scorer_model=scorer_model,
            changed=changed,
        )
        + "\n"
    )
    return out
