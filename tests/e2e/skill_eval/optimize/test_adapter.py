"""Tests for `adapter.py` against the pinned gepa package — 128 T022 (User Story 2, FR-005–FR-008).

The scorer and the reflection model are scripted stand-ins for the model API; gepa itself is real.
No IRIS is involved in routing.
"""

from __future__ import annotations

import importlib.metadata
import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

PIN = next(
    ln.split("==")[1].strip()
    for ln in (Path(__file__).parent / "requirements.txt").read_text().splitlines()
    if ln.startswith("gepa==")
)
try:
    _have = importlib.metadata.version("gepa")
except importlib.metadata.PackageNotFoundError:
    _have = None
if _have != PIN:
    _why = f"gepa {PIN} is pinned; this interpreter has {_have or 'none'} (pip install -r {Path(__file__).parent}/requirements.txt)"
    if os.environ.get("IAD_REQUIRE_GEPA"):
        raise RuntimeError(_why)
    pytest.skip(_why, allow_module_level=True)

from tests.e2e.skill_eval.optimize import holdout  # noqa: E402
from tests.e2e.skill_eval.optimize.adapter import RoutingAdapter, run_loop  # noqa: E402
from tests.e2e.skill_eval.optimize.ledger import Ledger  # noqa: E402
from tests.e2e.skill_eval.optimize.menu import Skill  # noqa: E402

BODY_W = "# Widgets\nWidgets and gadgets. Frobnicate a widget."
BODY_S = "# Sprockets\nSprocket tuning."
SKILLS = [
    Skill("widgets", "Things about widgets.", BODY_W, None),
    Skill("sprockets", "Sprocket help.", BODY_S, None),
]
GOOD = "USE FOR: widgets, gadgets and frobnicate requests. DO NOT USE FOR: sprockets."


class KeywordScorer:
    """Picks the first skill whose menu line shares a word with the prompt."""

    def __init__(self):
        self.messages = self
        self.prompts = []

    def create(self, **kw):
        prompt = kw["messages"][0]["content"].split("Request:\n", 1)[1]
        self.prompts.append(prompt)
        pick = "none"
        for line in kw["system"].splitlines():
            m = re.match(r"- ([\w-]+): (.*)", line)
            if m and set(re.findall(r"\w+", prompt.lower())) & set(
                re.findall(r"\w+", m.group(2).lower())
            ):
                pick = m.group(1)
                break
        return SimpleNamespace(
            model="anthropic.claude-haiku-4-5-20251001-v1:0",
            content=[SimpleNamespace(text='{"skill": "%s"}' % pick)],
            usage=SimpleNamespace(input_tokens=500, output_tokens=8),
        )


def _items():
    out = []
    for k in range(12):
        out.append(
            {
                "id": f"g{k}",
                "prompt": f"gadgets broken {k}",
                "gold": ["widgets"],
                "slice": "paraphrase",
            }
        )
    for k in range(6):
        out.append(
            {
                "id": f"s{k}",
                "prompt": f"sprocket tuning {k}",
                "gold": ["sprockets"],
                "slice": "paraphrase",
            }
        )
    return out


def _split(items, hold=()):
    return {
        i["id"]: (holdout.HOLDOUT if i["id"] in hold else holdout.TRAIN) for i in items
    }


def _reflect_with(text):
    calls = []

    def reflect(prompt):
        calls.append(prompt)
        return f"<description>{text}</description>"

    reflect.calls = calls
    return reflect


def _adapter(reflect, items, ledger=None, hold=()):
    return RoutingAdapter(
        SKILLS,
        KeywordScorer(),
        "haiku",
        ledger or Ledger(budget_usd=5),
        reflect=reflect,
        split=_split(items, hold),
        workers=1,
    )


def test_loop_finds_a_better_description():
    items = _items()
    reflect = _reflect_with(GOOD)
    best, info = run_loop(
        _adapter(reflect, items), items, max_metric_calls=200, seed=128
    )
    assert best["widgets"] == GOOD
    assert info["stopped"] in {"max_metric_calls", "done"}
    assert reflect.calls, "the reflection model was asked"


def test_invalid_proposal_is_rejected_before_scoring():
    items = _items()
    bad = "USE FOR: widgets via `%Library.Widget`. DO NOT USE FOR: sprockets."
    ad = _adapter(_reflect_with(bad), items)
    out = ad.propose_new_texts(
        {s.name: s.description for s in SKILLS},
        {
            "widgets": [
                {
                    "prompt": "gadgets",
                    "gold": ["widgets"],
                    "pick": "none",
                    "kind": "miss",
                }
            ]
        },
        ["widgets"],
    )
    assert out == {}, "gepa skips a proposal with no texts, so nothing is scored"
    assert ad.rejections and "new fact" in ad.rejections[0]["reasons"][0]


def test_missing_markers_and_overlength_rejected():
    items = _items()
    for text in ("widgets and gadgets", "USE FOR: x. DO NOT USE FOR: y. " + "w" * 1100):
        ad = _adapter(_reflect_with(text), items)
        assert (
            ad.propose_new_texts(
                {"widgets": "a", "sprockets": "b"},
                {
                    "widgets": [
                        {
                            "prompt": "p",
                            "gold": ["widgets"],
                            "pick": "none",
                            "kind": "miss",
                        }
                    ]
                },
                ["widgets"],
            )
            == {}
        )
        assert ad.rejections


def test_holdout_item_cannot_reach_the_train_scorer():
    items = _items()
    ad = _adapter(_reflect_with(GOOD), items, hold={"g0"})
    with pytest.raises(holdout.HoldoutLeak, match="g0"):
        ad.evaluate([items[0]], {s.name: s.description for s in SKILLS})


def test_budget_stops_the_loop_and_says_so():
    items = _items()
    led = Ledger(budget_usd=0.02)
    best, info = run_loop(
        _adapter(_reflect_with(GOOD), items, ledger=led),
        items,
        max_metric_calls=10_000,
        seed=128,
    )
    assert info["stopped"] == "budget"
    one_call = (500 * 1 + 8 * 5) / 1e6
    assert led.total_usd <= 0.02 + one_call + 1e-9
    assert set(best) == {"widgets", "sprockets"}


def test_reflective_dataset_names_misses_and_steals():
    items = _items()
    ad = _adapter(_reflect_with(GOOD), items)
    cand = {"widgets": "sprocket widgets", "sprockets": "Sprocket help."}
    ev = ad.evaluate(items[:1] + items[12:13], cand, capture_traces=True)
    ds = ad.make_reflective_dataset(cand, ev, ["widgets"])
    kinds = {r["kind"] for r in ds["widgets"]}
    assert "steal" in kinds, ds


def test_budget_hit_mid_iteration_keeps_best_val_candidate():
    items = _items()
    ad = _adapter(_reflect_with(GOOD), items, ledger=Ledger(budget_usd=0.03))
    best, info = run_loop(ad, items, max_metric_calls=10_000, seed=128)
    assert info["stopped"] == "budget"
    assert set(best) == {"widgets", "sprockets"}
    assert (
        best in (ad.best_val[1], {s.name: s.description for s in SKILLS})
        or best["widgets"] == GOOD
    )


def test_wall_clock_stops_the_loop_and_says_so():
    items = _items()
    ad = _adapter(_reflect_with(GOOD), items)
    best, info = run_loop(ad, items, max_metric_calls=10_000, seed=128, max_seconds=0)
    assert info["stopped"] == "time"
    assert set(best) == {"widgets", "sprockets"}


def test_interrupt_keeps_best_val_candidate_and_says_so():
    items = _items()
    ad = _adapter(_reflect_with(GOOD), items)
    calls = {"n": 0}
    real = ad.evaluate

    def interrupting(batch, candidate, capture_traces=False):
        calls["n"] += 1
        if calls["n"] > 3:
            raise KeyboardInterrupt
        return real(batch, candidate, capture_traces)

    ad.evaluate = interrupting
    best, info = run_loop(ad, items, max_metric_calls=10_000, seed=128)
    assert info["stopped"] == "interrupted"
    assert best == ad.best_val[1]


def test_rejected_draft_gets_one_retry_with_the_reasons():
    items = _items()
    replies = iter(
        ["USE FOR: x. DO NOT USE FOR: y. " + "w" * 1100, GOOD, "never asked"]
    )
    prompts = []

    def reflect(prompt):
        prompts.append(prompt)
        return f"<description>{next(replies)}</description>"

    ad = _adapter(reflect, items)
    miss = {"prompt": "gadgets", "gold": ["widgets"], "pick": "none", "kind": "miss"}
    out = ad.propose_new_texts(
        {s.name: s.description for s in SKILLS}, {"widgets": [miss]}, ["widgets"]
    )
    assert out == {"widgets": GOOD}
    assert len(prompts) == 2
    assert "over the 1024 cap" in prompts[1], "the retry is told why the draft failed"
    assert len(ad.rejections) == 1


def test_second_rejection_gives_up():
    items = _items()
    reflect = _reflect_with("widgets and gadgets")
    ad = _adapter(reflect, items)
    miss = {"prompt": "gadgets", "gold": ["widgets"], "pick": "none", "kind": "miss"}
    out = ad.propose_new_texts(
        {s.name: s.description for s in SKILLS}, {"widgets": [miss]}, ["widgets"]
    )
    assert out == {} and len(reflect.calls) == 2 and len(ad.rejections) == 2


def test_prompt_asks_for_headroom_under_the_cap():
    from tests.e2e.skill_eval.optimize import adapter

    assert "900 characters or fewer" in adapter.REFLECT_PROMPT
