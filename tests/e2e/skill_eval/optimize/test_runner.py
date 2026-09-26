"""Tests for `runner.py` — 128 T024 (User Stories 1, 2 and 3 end to end, offline).

The scorer and reflection model are scripted stand-ins for the model API. The corpus, the split
and the shipped skills are the real committed ones, read-only.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.e2e.skill_eval.optimize import menu, runner
from tests.e2e.skill_eval.optimize.ledger import Ledger

HAIKU = "anthropic.claude-haiku-4-5-20251001-v1:0"


class FakeClient:
    """Picks the gold-agnostic first skill sharing a word with the prompt; `fail` ids go unscored."""

    def __init__(self, fail=()):
        self.messages = self
        self.fail = set(fail)
        self.prompts = []

    def create(self, **kw):
        prompt = kw["messages"][0]["content"].split("Request:\n", 1)[1]
        self.prompts.append(prompt)
        if prompt in self.fail:
            raise RuntimeError("scripted outage")
        pick = "none"
        words = set(re.findall(r"[a-z]{5,}", prompt.lower()))
        for line in kw["system"].splitlines():
            m = re.match(r"- ([\w-]+): (.*)", line)
            if m and words & set(re.findall(r"[a-z]{5,}", m.group(2).lower())):
                pick = m.group(1)
                break
        return SimpleNamespace(
            model=HAIKU,
            content=[SimpleNamespace(text='{"skill": "%s"}' % pick)],
            usage=SimpleNamespace(input_tokens=2500, output_tokens=8),
        )


def _tree_hash(root) -> str:
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def test_load_corpus_is_the_committed_split():
    items, split = runner.load_corpus()
    assert len(items) == len(split) and {i["id"] for i in items} == set(split)


def test_measure_scores_holdout_only():
    client = FakeClient()
    items, split = runner.load_corpus()
    hold_prompts = {i["prompt"] for i in items if split[i["id"]] == "holdout"}
    fig, routed = runner.measure(client=client, model="m", ledger=Ledger(5), workers=1)
    assert set(client.prompts) == hold_prompts
    assert fig["valid"] and fig["n"] == len(hold_prompts) >= 70
    assert {"recall", "recall_lo", "recall_hi", "false_hint", "exact"} <= set(fig)


def test_measure_invalid_when_too_many_unscored():
    items, split = runner.load_corpus()
    hold = [i["prompt"] for i in items if split[i["id"]] == "holdout"]
    fig, _ = runner.measure(
        client=FakeClient(fail=hold[:20]), model="m", ledger=Ledger(5), workers=1
    )
    assert fig["valid"] is False and "recall" not in fig


def test_drift_passes_inside_interval_and_fails_outside(tmp_path):
    fig, _ = runner.measure(client=FakeClient(), model="m", ledger=Ledger(5), workers=1)
    inside = tmp_path / "in.json"
    inside.write_text(
        json.dumps(
            {"recall_lo": fig["recall"] - 0.01, "recall_hi": fig["recall"] + 0.01}
        )
    )
    ok, _, _ = runner.drift(
        client=FakeClient(),
        model="m",
        ledger=Ledger(5),
        interval_path=inside,
        workers=1,
    )
    assert ok
    outside = tmp_path / "out.json"
    outside.write_text(json.dumps({"recall_lo": fig["recall"] + 0.1, "recall_hi": 1.0}))
    ok, _, _ = runner.drift(
        client=FakeClient(),
        model="m",
        ledger=Ledger(5),
        interval_path=outside,
        workers=1,
    )
    assert not ok


def test_reserve_covers_two_holdout_arms():
    items, split = runner.load_corpus()
    n = sum(1 for i in items if split[i["id"]] == "holdout")
    led = Ledger(20)
    per_call = runner.estimate_call_usd(
        led, "us.anthropic.claude-haiku-4-5-20251001-v1:0", menu.load_skills()
    )
    assert (
        runner.reserve_usd(
            led, "us.anthropic.claude-haiku-4-5-20251001-v1:0", menu.load_skills(), n
        )
        >= 2 * n * per_call
    )


def _gepa_pinned() -> bool:
    pin = next(
        ln.split("==")[1].strip()
        for ln in (Path(runner.__file__).parent / "requirements.txt")
        .read_text()
        .splitlines()
        if ln.startswith("gepa==")
    )
    try:
        return importlib.metadata.version("gepa") == pin
    except importlib.metadata.PackageNotFoundError:
        return False


@pytest.mark.skipif(
    not _gepa_pinned() and not os.environ.get("IAD_REQUIRE_GEPA"),
    reason="pinned gepa not installed",
)
def test_offline_run_writes_run_dir_and_leaves_skills_alone(tmp_path):
    before = _tree_hash(menu.SKILLS_ROOT)

    def reflect(prompt):
        return "<description>USE FOR: widgets. DO NOT USE FOR: sprockets.</description>"

    run_dir = runner.run(
        client=FakeClient(),
        model=runner.BEDROCK_SCORER,
        reflect=reflect,
        ledger=Ledger(20),
        surface="skill-descriptions",
        max_metric_calls=60,
        ladder=None,
        out_root=tmp_path,
        workers=1,
    )
    assert _tree_hash(menu.SKILLS_ROOT) == before
    assert sorted(p.name for p in Path(run_dir).iterdir()) == [
        "candidate.json",
        "ledger.jsonl",
        "report.md",
    ]
    c = json.loads((Path(run_dir) / "candidate.json").read_text())
    assert c["verdict"] == "HOLD"
    assert "ladder: no live ladder run" in c["failed"]
    assert c["seed_figures"]["valid"] and c["candidate_figures"]["valid"]


@pytest.mark.skipif(
    not _gepa_pinned() and not os.environ.get("IAD_REQUIRE_GEPA"),
    reason="pinned gepa not installed",
)
def test_interrupted_run_streams_ledger_and_still_gates(tmp_path):
    def reflect(prompt):
        raise KeyboardInterrupt  # what SIGTERM becomes in the CLI

    run_dir = runner.run(
        client=FakeClient(),
        model=runner.BEDROCK_SCORER,
        reflect=reflect,
        ledger=Ledger(20),
        surface="skill-descriptions",
        max_metric_calls=200,
        out_root=tmp_path,
        workers=1,
    )
    c = json.loads((Path(run_dir) / "candidate.json").read_text())
    assert c["stopped"] == "interrupted"
    assert c["seed_figures"]["valid"]
    lines = (Path(run_dir) / "ledger.jsonl").read_text().splitlines()
    assert (
        len(lines) > 2 * c["seed_figures"]["n"]
    )  # loop calls plus both holdout arms, no duplicates
