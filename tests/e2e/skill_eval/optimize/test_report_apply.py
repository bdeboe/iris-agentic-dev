"""Tests for `report.py` and `apply.py` — 128 T023 (FR-004, FR-010, User Stories 1 and 4)."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from tests.e2e.skill_eval.optimize import apply as apply_mod
from tests.e2e.skill_eval.optimize.gate import HOLD, SHIP, Verdict
from tests.e2e.skill_eval.optimize.ledger import Ledger
from tests.e2e.skill_eval.optimize.menu import REPO
from tests.e2e.skill_eval.optimize.proxy import Routed
from tests.e2e.skill_eval.optimize.report import figures, outcomes, write_run

ITEMS = [
    {"id": "a", "gold": ["iris-sql"], "slice": "paraphrase"},
    {"id": "b", "gold": ["iris-sql"], "slice": "exact-name"},
    {"id": "c", "gold": ["none"], "slice": "no-skill"},
    {"id": "d", "gold": ["none"], "slice": "no-skill"},
]


def _r(i, pick, scored=True):
    item = next(x for x in ITEMS if x["id"] == i)
    return Routed(
        i,
        scored,
        pick if scored else None,
        (pick in item["gold"]) if scored else None,
        "haiku",
        "" if scored else "timeout",
    )


def test_figures_from_scored_items_only():
    routed = [
        _r("a", "iris-sql"),
        _r("b", "none"),
        _r("c", "iris-sql"),
        _r("d", "none"),
    ]
    f = figures(ITEMS, routed)
    assert f["valid"] and f["n"] == 4 and f["unscored"] == 0
    assert f["recall"] == 0.5 and f["recall_n"] == 2
    assert 0 <= f["recall_lo"] < 0.5 < f["recall_hi"] <= 1
    assert f["false_hint"] == 0.5 and f["exact"] == 0.0


def test_too_many_unscored_invalidates_and_writes_no_figures():
    routed = [
        _r("a", "iris-sql"),
        _r("b", "none", scored=False),
        _r("c", "none"),
        _r("d", "none"),
    ]
    f = figures(ITEMS, routed)
    assert not f["valid"] and f["unscored"] == 1
    assert "recall" not in f


def test_outcomes_drop_unscored():
    o = outcomes(ITEMS, [_r("a", "iris-sql"), _r("b", "none", scored=False)])
    assert set(o) == {"a"} and o["a"].correct


def _write(tmp_path, verdict):
    led = Ledger(budget_usd=5)
    led.record("score", "claude-haiku-4-5", 100, 1)
    v = Verdict(
        verdict,
        [] if verdict == SHIP else ["recall: tie"],
        {"diff": 0.1, "diff_lo": 0.02, "diff_hi": 0.2},
    )
    return write_run(
        tmp_path / "run1",
        surface="skill-descriptions",
        seed={"iris-sql": "old"},
        candidate={"iris-sql": "USE FOR: a. DO NOT USE FOR: b."},
        verdict=v,
        seed_fig={
            "valid": True,
            "n": 4,
            "recall": 0.5,
            "recall_lo": 0.1,
            "recall_hi": 0.9,
            "recall_n": 2,
            "false_hint": 0.5,
            "exact": 0.0,
            "unscored": 0,
        },
        cand_fig=None,
        ledger=led,
        info={"stopped": "budget", "proposals": [], "rejections": []},
        scorer_model="anthropic.claude-haiku-4-5-20251001-v1:0",
    )


def test_run_writes_three_files_and_only_changed_descriptions(tmp_path):
    d = _write(tmp_path, HOLD)
    assert sorted(os.listdir(d)) == ["candidate.json", "ledger.jsonl", "report.md"]
    c = json.loads((d / "candidate.json").read_text())
    assert c["verdict"] == HOLD and c["descriptions"] == {
        "iris-sql": "USE FOR: a. DO NOT USE FOR: b."
    }
    rep = (d / "report.md").read_text()
    assert "HOLD" in rep and "recall: tie" in rep and "stopped on budget" in rep


def test_apply_refuses_hold(tmp_path):
    d = _write(tmp_path, HOLD)
    with pytest.raises(apply_mod.NotShippable):
        apply_mod.apply_run(d, root=str(tmp_path / "nowhere"))


def test_apply_ship_writes_into_root(tmp_path):
    import shutil

    from tests.e2e.skill_eval.optimize import menu
    from tests.e2e.skill_eval.optimize.menu import split_front_matter

    root = tmp_path / "skills"
    shutil.copytree(menu.SKILLS_ROOT, root)
    d = _write(tmp_path, SHIP)
    changed = apply_mod.apply_run(d, root=str(root))
    assert len(changed) == 1
    assert split_front_matter(open(changed[0]).read())[0]["description"].startswith(
        "USE FOR: a."
    )


def test_cli_apply_on_hold_exits_nonzero(tmp_path):
    d = _write(tmp_path, HOLD)
    p = subprocess.run(
        [sys.executable, "-m", "tests.e2e.skill_eval.optimize", "apply", str(d)],
        cwd=REPO,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": REPO},
    )
    assert p.returncode != 0 and "HOLD" in (p.stdout + p.stderr)


def test_cli_help_lists_commands():
    p = subprocess.run(
        [sys.executable, "-m", "tests.e2e.skill_eval.optimize", "--help"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert p.returncode == 0
    for cmd in ("measure", "run", "apply", "drift"):
        assert cmd in p.stdout
