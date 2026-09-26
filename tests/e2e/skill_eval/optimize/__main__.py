"""`python -m tests.e2e.skill_eval.optimize {measure,run,apply,drift}` (spec 128).

measure  score the shipped descriptions on the holdout; `--write-interval` records the drift band
run      optimise on train, gate on the holdout, write tests/e2e/results/optimize/<run_id>/
         (`--surface hints` needs iris-dev-iris: IRIS_HOST, IRIS_WEB_PORT, IRIS_USERNAME, IRIS_PASSWORD)
apply    write a SHIP run's texts into skills/ or hints.toml (refuses HOLD)
drift    nightly: fail when holdout Recall@1 leaves the committed band
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import signal
import sys
from pathlib import Path

from tests.e2e.skill_eval.optimize import runner
from tests.e2e.skill_eval.optimize.surfaces import SURFACES


def _billable(args):
    from tests.e2e.skill_eval import scorer_client
    from tests.e2e.skill_eval.optimize.ledger import Ledger

    bedrock = scorer_client._use_bedrock()
    client = scorer_client.make_client()
    scorer = args.scorer or (runner.BEDROCK_SCORER if bedrock else runner.DIRECT_SCORER)
    ledger = Ledger(
        args.budget, multiplier=runner.BEDROCK_MULTIPLIER if bedrock else 1.0
    )
    return client, scorer, ledger, bedrock


def _measure(args) -> int:
    client, scorer, ledger, _ = _billable(args)
    fig, routed = runner.measure(
        client=client, model=scorer, ledger=ledger, workers=args.workers
    )
    models = runner.scorer_models(routed)
    out = {
        "figures": fig,
        "scorer_models": models,
        "spend_usd": round(ledger.total_usd, 4),
    }
    print(json.dumps(out, indent=2))
    run_dir = (
        runner.RESULTS_ROOT
        / f"{_dt.datetime.now(_dt.timezone.utc):%Y%m%dT%H%M%SZ}-measure"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "measure.json").write_text(json.dumps(out, indent=2) + "\n")
    ledger.write(run_dir / "ledger.jsonl")
    if not fig["valid"]:
        print("invalid measurement: more than 10% unscored", file=sys.stderr)
        return 1
    if args.write_interval:
        band = {
            "recall_lo": fig["recall_lo"],
            "recall_hi": fig["recall_hi"],
            "recall": fig["recall"],
            "n": fig["recall_n"],
            "scorer_models": models,
            "measured": f"{_dt.date.today():%Y-%m-%d}",
            "source": str(run_dir.relative_to(runner.menu.REPO)),
        }
        runner.DRIFT_FILE.write_text(json.dumps(band, indent=2) + "\n")
        print(f"wrote {runner.DRIFT_FILE}")
    return 0


def _run(args) -> int:
    client, scorer, ledger, bedrock = _billable(args)
    reflect_model = args.reflect_model or (
        runner.BEDROCK_REFLECT if bedrock else runner.DIRECT_REFLECT
    )
    ladder = json.loads(Path(args.ladder).read_text()) if args.ladder else None

    def _term(*_):
        raise KeyboardInterrupt  # run_loop stops cleanly and the holdout is still scored

    signal.signal(signal.SIGTERM, _term)
    common = dict(
        client=client,
        model=scorer,
        reflect=runner.make_reflect(client, reflect_model, ledger),
        ledger=ledger,
        max_metric_calls=args.max_metric_calls,
        ladder=ladder,
        workers=args.workers,
        max_seconds=args.max_minutes * 60 if args.max_minutes else None,
    )
    if args.surface == "hints":
        from tests.e2e.skill_eval.optimize import hints_proxy, hints_runner

        binary = _iad_binary()
        if not binary:
            print(
                "no iris-agentic-dev binary: set IAD_BINARY or cargo build",
                file=sys.stderr,
            )
            return 1
        checker = hints_proxy.Checker(hints_proxy.IadRunner(binary))
        run_dir = hints_runner.run(checker=checker, **common)
    else:
        run_dir = runner.run(surface=args.surface, **common)
    c = json.loads((run_dir / "candidate.json").read_text())
    print(
        f"{c['verdict']}  spend ${ledger.total_usd:.2f}  stopped on {c['stopped']}  {run_dir}"
    )
    for f in c["failed"]:
        print(f"  failed {f}")
    return 0


def _iad_binary():
    """The binary the hints checker runs `iris_execute` through; IRIS_* come from the environment."""
    import os
    import shutil

    for p in [
        os.environ.get("IAD_BINARY"),
        Path(runner.menu.REPO) / "target/debug/iris-agentic-dev",
    ]:
        if p and Path(p).exists():
            return str(p)
    return shutil.which("iris-agentic-dev")


def _apply(args) -> int:
    from tests.e2e.skill_eval.optimize.apply import NotShippable, apply_run

    try:
        changed = apply_run(args.run_dir)
    except NotShippable as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1
    for p in changed:
        print(p)
    return 0


def _drift(args) -> int:
    client, scorer, ledger, _ = _billable(args)
    ok, fig, band = runner.drift(
        client=client, model=scorer, ledger=ledger, workers=args.workers
    )
    print(
        json.dumps(
            {
                "ok": ok,
                "figures": fig,
                "band": band,
                "spend_usd": round(ledger.total_usd, 4),
            },
            indent=2,
        )
    )
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m tests.e2e.skill_eval.optimize",
        description=__doc__.split("\n\n")[0],
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def billable(sp, budget):
        sp.add_argument(
            "--budget",
            type=float,
            default=budget,
            help=f"hard cap in dollars (default {budget})",
        )
        sp.add_argument("--scorer", help="scorer model id (default Haiku 4.5)")
        sp.add_argument("--workers", type=int, default=8)

    m = sub.add_parser("measure", help="score shipped descriptions on the holdout")
    billable(m, 2.0)
    m.add_argument(
        "--write-interval",
        action="store_true",
        help=f"record the band in {runner.DRIFT_FILE.name}",
    )
    m.set_defaults(fn=_measure)

    r = sub.add_parser("run", help="optimise on train, gate on the holdout")
    billable(r, 20.0)
    r.add_argument("--surface", choices=sorted(SURFACES), default="skill-descriptions")
    r.add_argument("--max-metric-calls", type=int, default=4000)
    r.add_argument("--reflect-model", help="reflection model id (default Sonnet 5)")
    r.add_argument(
        "--max-minutes",
        type=float,
        default=75.0,
        help="stop the loop after this long and gate what it found (default 75; 0 = no limit)",
    )
    r.add_argument(
        "--ladder", help='JSON file {"seed": x, "candidate": y} from a live ladder run'
    )
    r.set_defaults(fn=_run)

    a = sub.add_parser("apply", help="write a SHIP run's descriptions into skills/")
    a.add_argument("run_dir")
    a.set_defaults(fn=_apply)

    d = sub.add_parser(
        "drift", help="fail when holdout Recall@1 leaves the committed band"
    )
    billable(d, 2.0)
    d.set_defaults(fn=_drift)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
