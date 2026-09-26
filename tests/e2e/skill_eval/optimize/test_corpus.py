"""Data tests for the routing corpus and its frozen split — 128 T003/T004 (FR-001–FR-003, SC-001)."""

from __future__ import annotations

import json
from pathlib import Path

from tests.e2e.skill_eval.optimize import holdout, menu

ROUTING = Path(menu.REPO) / "tests" / "e2e" / "tasks" / "routing"
SLICES = {"paraphrase", "exact-name", "no-skill"}


def _items():
    return [
        json.loads(x)
        for x in (ROUTING / "corpus.jsonl").read_text().splitlines()
        if x.strip()
    ]


def test_ids_unique_and_fields_present():
    items = _items()
    ids = [i["id"] for i in items]
    assert len(ids) == len(set(ids))
    for i in items:
        assert {"id", "prompt", "gold", "slice", "source", "labels"} <= i.keys(), i[
            "id"
        ]


def test_gold_names_exist_and_slice_matches():
    names = {s.name for s in menu.load_skills()}
    for i in _items():
        assert i["slice"] in SLICES, i["id"]
        if i["gold"] == ["none"]:
            assert i["slice"] == "no-skill", i["id"]
        else:
            assert "none" not in i["gold"], i["id"]
            assert set(i["gold"]) <= names, (i["id"], i["gold"])
            assert i["slice"] != "no-skill", i["id"]


def test_dropped_items_are_not_in_corpus():
    corpus = {i["id"] for i in _items()}
    dropped = [
        json.loads(x)
        for x in (ROUTING / "dropped.jsonl").read_text().splitlines()
        if x.strip()
    ]
    for d in dropped:
        assert d["id"] not in corpus
        assert d["reason"]


def test_split_is_frozen_and_covers_the_corpus():
    split = holdout.load_split(ROUTING / "routing-split.toml")
    corpus = {i["id"] for i in _items()}
    assert set(split) == corpus, "every corpus item is assigned, and nothing else is"


def test_holdout_has_at_least_70_items():
    split = holdout.load_split(ROUTING / "routing-split.toml")
    n = sum(1 for side in split.values() if side == holdout.HOLDOUT)
    assert n >= 70, n
