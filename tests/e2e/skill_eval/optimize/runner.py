"""The three jobs behind the CLI: measure, run and drift (spec 128 FR-004, FR-009, FR-010, FR-012).

Every function takes its model client as an argument, so the offline tests drive the real path
with a scripted client. Nothing here writes under `skills/`; `apply.py` is the only writer.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

from tests.e2e.skill_eval.optimize import gate, holdout, menu
from tests.e2e.skill_eval.optimize.ledger import BudgetExceeded
from tests.e2e.skill_eval.optimize.proxy import MAX_TOKENS, score_items
from tests.e2e.skill_eval.optimize.report import figures, outcomes, write_run
from tests.e2e.skill_eval.optimize.surfaces import SURFACES

CORPUS_DIR = Path(menu.REPO) / "tests" / "e2e" / "tasks" / "routing"
RESULTS_ROOT = Path(menu.REPO) / "tests" / "e2e" / "results" / "optimize"
DRIFT_FILE = CORPUS_DIR / "drift-interval.json"

# Bedrock cross-region ids. `scorer_client.haiku_model()` still resolves to Sonnet 4.6 on
# Bedrock; the loop asks for Haiku 4.5 by name, and the ledger records what answered.
BEDROCK_SCORER = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
BEDROCK_REFLECT = "us.anthropic.claude-sonnet-5"
DIRECT_SCORER = "claude-haiku-4-5-20251001"
DIRECT_REFLECT = "claude-sonnet-5"
# US regional Bedrock endpoints cost 10% over the list price.
BEDROCK_MULTIPLIER = 1.1
# Room for the final holdout measurement: two arms, priced at 1.5x the estimate.
RESERVE_FACTOR = 1.5
REFLECT_MAX_TOKENS = 800
PROMPT_OVERHEAD_TOKENS = 400


def load_corpus(corpus_dir: Path = CORPUS_DIR):
    items = [
        json.loads(ln)
        for ln in (Path(corpus_dir) / "corpus.jsonl").read_text().splitlines()
        if ln.strip()
    ]
    split = holdout.load_split(Path(corpus_dir) / "routing-split.toml")
    return items, split


def side(items, split, which):
    """The items on one side of the frozen split, passed through that side's leak guard."""
    picked = [i for i in items if split.get(i["id"]) == which]
    return (
        holdout.holdout_only(picked, split)
        if which == holdout.HOLDOUT
        else holdout.train_only(picked, split)
    )


def estimate_call_usd(ledger, model: str, skills) -> float:
    rin, rout = ledger._rate(model)
    tokens_in = len(menu.render_menu(skills)) / 4 + PROMPT_OVERHEAD_TOKENS
    return (tokens_in * rin + MAX_TOKENS * rout) / 1e6 * ledger.multiplier


def reserve_usd(ledger, model: str, skills, n_holdout: int) -> float:
    return 2 * n_holdout * estimate_call_usd(ledger, model, skills) * RESERVE_FACTOR


def scorer_models(routed) -> list[str]:
    return sorted({r.model for r in routed if r.model})


def measure(
    *,
    client,
    model,
    ledger,
    descriptions=None,
    corpus_dir=CORPUS_DIR,
    root=menu.SKILLS_ROOT,
    workers=8,
):
    """Score one set of descriptions (default: the shipped ones) on the holdout only."""
    items, split = load_corpus(corpus_dir)
    hold = side(items, split, holdout.HOLDOUT)
    skills = menu.load_skills(root)
    routed = score_items(
        hold, skills, descriptions or {}, client, model, ledger, workers=workers
    )
    return figures(hold, routed), routed


def make_reflect(client, model, ledger):
    def reflect(prompt: str) -> str:
        ledger.check()
        msg = client.messages.create(
            model=model,
            max_tokens=REFLECT_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        ledger.record(
            "reflect",
            getattr(msg, "model", None) or model,
            msg.usage.input_tokens,
            msg.usage.output_tokens,
        )
        return "".join(getattr(b, "text", "") for b in msg.content)

    return reflect


def run(
    *,
    client,
    model,
    reflect,
    ledger,
    surface="skill-descriptions",
    max_metric_calls=4000,
    ladder=None,
    out_root=RESULTS_ROOT,
    corpus_dir=CORPUS_DIR,
    root=menu.SKILLS_ROOT,
    workers=8,
    run_id=None,
    max_seconds=None,
) -> Path:
    """Loop on train, score seed and finalist on the holdout, gate, write the run directory."""
    from tests.e2e.skill_eval.optimize.adapter import (
        RoutingAdapter,
        run_loop,
    )  # needs pinned gepa

    run_id = run_id or f"{_dt.datetime.now(_dt.timezone.utc):%Y%m%dT%H%M%SZ}-{surface}"
    run_dir = Path(out_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    # Spend lands on disk call by call, so a killed run still leaves its ledger to tail and audit.
    if ledger.stream_path is None:
        ledger.stream_path = run_dir / "ledger.jsonl"

    items, split = load_corpus(corpus_dir)
    skills = SURFACES[surface].load(root)
    seed = {s.name: s.description for s in skills}
    hold = side(items, split, holdout.HOLDOUT)
    adapter = RoutingAdapter(
        skills, client, model, ledger, reflect=reflect, split=split, workers=workers
    )
    best, info = run_loop(
        adapter,
        side(items, split, holdout.TRAIN),
        max_metric_calls=max_metric_calls,
        reserve_usd=reserve_usd(ledger, model, skills, len(hold)),
        max_seconds=max_seconds,
    )

    seed_fig = cand_fig = None
    models: list[str] = []
    try:
        seed_routed = score_items(
            hold, skills, seed, client, model, ledger, workers=workers
        )
        cand_routed = score_items(
            hold, skills, best, client, model, ledger, workers=workers
        )
        seed_fig, cand_fig = figures(hold, seed_routed), figures(hold, cand_routed)
        models = scorer_models(seed_routed + cand_routed)
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
            verdict = gate.decide(
                outcomes(hold, seed_routed), outcomes(hold, cand_routed), ladder=ladder
            )

    return write_run(
        run_dir,
        surface=surface,
        seed=seed,
        candidate=best,
        verdict=verdict,
        seed_fig=seed_fig,
        cand_fig=cand_fig,
        ledger=ledger,
        info=info,
        scorer_model=", ".join(models) or model,
    )


def drift(
    *,
    client,
    model,
    ledger,
    interval_path=DRIFT_FILE,
    corpus_dir=CORPUS_DIR,
    root=menu.SKILLS_ROOT,
    workers=8,
):
    """Re-score the shipped descriptions; ok when holdout Recall@1 sits inside the committed interval."""
    interval = json.loads(Path(interval_path).read_text())
    fig, _ = measure(
        client=client,
        model=model,
        ledger=ledger,
        corpus_dir=corpus_dir,
        root=root,
        workers=workers,
    )
    ok = (
        bool(fig["valid"])
        and interval["recall_lo"] <= fig["recall"] <= interval["recall_hi"]
    )
    return ok, fig, interval
