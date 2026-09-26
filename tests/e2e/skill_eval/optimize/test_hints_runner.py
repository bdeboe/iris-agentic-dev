"""Tests for `hints_runner.py` and `hints_adapter.py` — 129 T010 (User Story 3, FR-009).

gepa is real; the scorer, the reflection model and the IRIS runner are scripted. The corpus, split,
rules and skills are the committed ones, read-only; `apply` writes to a temp `hints.toml`.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import re
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.e2e.skill_eval.optimize import holdout
from tests.e2e.skill_eval.optimize import hints_proxy as hp
from tests.e2e.skill_eval.optimize import hints_runner as hr
from tests.e2e.skill_eval.optimize import hints_surface as hs
from tests.e2e.skill_eval.optimize.gate import HOLD, SHIP
from tests.e2e.skill_eval.optimize.ledger import Ledger

HAIKU = "anthropic.claude-haiku-4-5-20251001-v1:0"


def _gepa_pinned():
    pin = next(
        ln.split("==")[1].strip()
        for ln in (Path(__file__).parent / "requirements.txt").read_text().splitlines()
        if ln.startswith("gepa==")
    )
    try:
        return importlib.metadata.version("gepa") == pin
    except importlib.metadata.PackageNotFoundError:
        return False


needs_gepa = pytest.mark.skipif(
    not _gepa_pinned() and not os.environ.get("IAD_REQUIRE_GEPA"),
    reason="needs the pinned gepa",
)


class HintFollower:
    """Picks the skill a rule cites when the hint says `%SYS` or `SQL`, and echoes the item's fix."""

    def __init__(self):
        self.messages = self
        self.seen_ids = []

    def create(self, **kw):
        user = kw["messages"][0]["content"]
        item_id = re.search(r"^Item: (\S+)$", user, re.M).group(1)
        self.seen_ids.append(item_id)
        it = hr_items_by_id()[item_id]
        hint = user.split("hint: ", 1)[1]
        pick = it["skill"] if ("%SYS" in hint or "SQL" in hint) else "none"
        text = json.dumps({"skill": pick, "fix": it["fix"]})
        return SimpleNamespace(
            model=HAIKU,
            content=[SimpleNamespace(text=text)],
            usage=SimpleNamespace(input_tokens=3000, output_tokens=60),
        )


_ITEMS = None


def hr_items_by_id():
    global _ITEMS
    if _ITEMS is None:
        _ITEMS = {i["id"]: i for i in hs.load_items()}
    return _ITEMS


def passing_checker():
    return hp.Checker(lambda code, ns: {"success": True, "output": "PREPARED"})


def _scored(i, reach, passed):
    return hp.Scored(i, True, "x", reach, passed, (reach + passed) / 2, HAIKU, "", {})


# ── split ─────────────────────────────────────────────────────────────────────────────────


def test_the_split_file_is_the_hash_rule_over_the_live_positives():
    items, split = hr.load_corpus()
    assert {i["id"] for i in items} == set(split)
    assert hs.SPLIT.read_text() == holdout.render_split(
        [i["id"] for i in items], title="Spec 129 hints split"
    )
    assert {split[i] for i in split} == {holdout.TRAIN, holdout.HOLDOUT}


def test_mined_items_and_negatives_are_not_in_the_loop():
    items, _ = hr.load_corpus()
    raw = [json.loads(ln) for ln in hs.CORPUS.read_text().splitlines() if ln.strip()]
    mined = {i["id"] for i in raw if i["source"] != "live" or i["rule"] == "none"}
    assert mined and not mined & {i["id"] for i in items}


# ── gates ─────────────────────────────────────────────────────────────────────────────────


def test_decide_ships_only_on_all_four_gates():
    ids = [f"i{n}" for n in range(30)]
    seed = {i: _scored(i, False, True) for i in ids}
    cand = {i: _scored(i, True, True) for i in ids}
    v = hr.decide(seed, cand, ladder={"seed": 0.5, "candidate": 0.5})
    assert v.verdict == SHIP, v.failed
    assert v.figures["seed_reach"] == 0.0 and v.figures["cand_reach"] == 1.0

    v = hr.decide(seed, cand, ladder=None)
    assert v.verdict == HOLD and any("ladder" in f for f in v.failed)

    v = hr.decide(seed, cand, ladder={"seed": 0.6, "candidate": 0.5})
    assert v.verdict == HOLD and any("ladder" in f for f in v.failed)

    worse_pass = {i: _scored(i, True, n % 10 != 0) for n, i in enumerate(ids)}
    v = hr.decide(seed, worse_pass, ladder={"seed": 0.5, "candidate": 0.5})
    assert any(f.startswith("pass:") for f in v.failed)

    same = hr.decide(seed, seed, ladder={"seed": 0.5, "candidate": 0.5})
    assert any(f.startswith("score:") for f in same.failed)


def test_decide_holds_when_reach_drops_even_if_score_rises():
    ids = [f"i{n}" for n in range(40)]
    seed = {i: _scored(i, True, False) for i in ids}
    cand = {i: _scored(i, n % 5 != 0, True) for n, i in enumerate(ids)}
    v = hr.decide(seed, cand, ladder={"seed": 0.5, "candidate": 0.5})
    assert any(f.startswith("reach:") for f in v.failed), v.failed


def test_figures_drop_unscored_and_go_invalid_past_the_limit():
    rows = [_scored(f"i{n}", True, n % 2 == 0) for n in range(10)]
    f = hr.figures(rows)
    assert f["valid"] and f["reach"] == 1.0 and f["pass"] == 0.5 and f["score"] == 0.75
    rows += [hp.Scored("u", False, None, None, None, None, HAIKU, "outage", {})] * 5
    f = hr.figures(rows)
    assert not f["valid"] and "score" not in f


# ── the loop, end to end ──────────────────────────────────────────────────────────────────


@needs_gepa
def test_evaluate_refuses_a_holdout_item():
    from tests.e2e.skill_eval.optimize.hints_adapter import HintsAdapter

    items, split = hr.load_corpus()
    ad = HintsAdapter(
        hs.load_rules(),
        hr.menu.load_skills(),
        HintFollower(),
        "m",
        Ledger(5),
        reflect=lambda p: "",
        split=split,
        checker=passing_checker(),
    )
    hold = [i for i in items if split[i["id"]] == holdout.HOLDOUT][:1]
    with pytest.raises(holdout.HoldoutLeak):
        ad.evaluate(hold, ad.seed)


@needs_gepa
def test_a_proposal_that_breaks_the_validator_is_never_scored():
    from tests.e2e.skill_eval.optimize.hints_adapter import HintsAdapter

    _, split = hr.load_corpus()
    asks = []

    def reflect(prompt):
        asks.append(prompt)
        return "<hint>See iris-agentic-dev for {table}.</hint>"

    ad = HintsAdapter(
        hs.load_rules(),
        hr.menu.load_skills(),
        HintFollower(),
        "m",
        Ledger(5),
        reflect=reflect,
        split=split,
        checker=passing_checker(),
    )
    rows = [
        {
            "id": "x",
            "error": "e",
            "hint": "h",
            "pick": "none",
            "fix": {},
            "reach": False,
            "passed": True,
        }
    ]
    out = ad.propose_new_texts(ad.seed, {"sys_only_table": rows}, ["sys_only_table"])
    assert out == {}
    assert len(asks) == 2 and len(ad.rejections) == 2
    assert (
        "Security and Config" in asks[0] or "%SYS" in asks[0]
    )  # section and seed are shown


@needs_gepa
def test_run_writes_a_hold_verdict_and_never_shows_the_holdout_to_the_loop(tmp_path):
    items, split = hr.load_corpus()
    hold_ids = {i for i in split if split[i] == holdout.HOLDOUT}
    client = HintFollower()
    proposals = iter(
        [
            '<hint>{table} is %SYS only; {namespace} cannot see it. Rerun with namespace: "%SYS".</hint>',
        ]
        * 50
    )

    def reflect(_p):
        return next(proposals)

    run_dir = hr.run(
        client=client,
        model=HAIKU,
        reflect=reflect,
        ledger=Ledger(5),
        checker=passing_checker(),
        max_metric_calls=120,
        ladder=None,
        out_root=tmp_path,
        workers=1,
        run_id="t",
    )
    n_hold = len(hold_ids)
    loop_ids = client.seen_ids[: len(client.seen_ids) - 2 * n_hold]
    assert not hold_ids & set(loop_ids)
    assert set(client.seen_ids[-2 * n_hold :]) == hold_ids

    c = json.loads((run_dir / "candidate.json").read_text())
    assert c["surface"] == "hints" and c["verdict"] == HOLD
    assert any("ladder" in f for f in c["failed"])
    for arm in ("seed_figures", "candidate_figures"):
        assert c[arm]["n"] == n_hold and {"reach", "pass", "score"} <= set(c[arm])
    assert (run_dir / "ledger.jsonl").exists() and (run_dir / "report.md").exists()
    assert "Verdict: HOLD" in (run_dir / "report.md").read_text()


def test_apply_refuses_hold_and_writes_only_text_on_ship(tmp_path):
    from tests.e2e.skill_eval.optimize.apply import NotShippable, apply_run

    path = tmp_path / "hints.toml"
    shutil.copy(hs.HINTS_TOML, path)
    run = tmp_path / "run"
    run.mkdir()
    new = '{word} is reserved. Quote it as "{word}".'
    body = {
        "run_id": "r",
        "surface": "hints",
        "verdict": HOLD,
        "failed": ["ladder"],
        "descriptions": {"reserved_word": new},
    }
    (run / "candidate.json").write_text(json.dumps(body))
    with pytest.raises(NotShippable):
        apply_run(run, path=path)
    body["verdict"] = SHIP
    (run / "candidate.json").write_text(json.dumps(body))
    assert apply_run(run, path=path) == [str(path)]
    assert {r.id: r.text for r in hs.load_rules(path)}["reserved_word"] == new


def test_cli_accepts_the_hints_surface():
    from tests.e2e.skill_eval.optimize.surfaces import SURFACES

    assert "hints" in SURFACES
    assert SURFACES["hints"].load().__class__ is list
