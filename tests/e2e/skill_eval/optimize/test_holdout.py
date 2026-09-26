"""Tests for `holdout.py` — 128 T011, written before it (FR-003, FR-007).

The split file is parsed as text, and every failure names the id.
"""

from __future__ import annotations

import pytest

from tests.e2e.skill_eval.optimize.holdout import (
    HOLDOUT,
    TRAIN,
    HoldoutLeak,
    SplitInvalid,
    assign,
    holdout_only,
    load_split,
    render_split,
    train_only,
)

IDS = [f"r-{i:04d}" for i in range(200)]


def test_assign_is_the_hash_rule_and_near_60_40():
    sides = [assign(i) for i in IDS]
    assert set(sides) == {TRAIN, HOLDOUT}
    assert 0.5 < sides.count(TRAIN) / len(sides) < 0.7
    assert assign("r-0001") == assign("r-0001")


def test_round_trip(tmp_path):
    p = tmp_path / "split.toml"
    p.write_text(render_split(IDS))
    split = load_split(p)
    assert all(split[i] == assign(i) for i in IDS)


def test_moved_id_is_named(tmp_path):
    victim = next(i for i in IDS if assign(i) == HOLDOUT)
    text = render_split(IDS)
    text = text.replace(f'"{victim}",\n', "").replace(
        "[train]\nids = [\n", f'[train]\nids = [\n  "{victim}",\n'
    )
    p = tmp_path / "split.toml"
    p.write_text(text)
    with pytest.raises(SplitInvalid, match=victim):
        load_split(p)


def test_id_on_both_sides_is_named(tmp_path):
    victim = next(i for i in IDS if assign(i) == TRAIN)
    text = render_split(IDS).replace(
        "[holdout]\nids = [\n", f'[holdout]\nids = [\n  "{victim}",\n'
    )
    p = tmp_path / "split.toml"
    p.write_text(text)
    with pytest.raises(SplitInvalid, match=victim):
        load_split(p)


def test_train_only_raises_on_holdout_id():
    split = {i: assign(i) for i in IDS}
    h = next(i for i in IDS if split[i] == HOLDOUT)
    with pytest.raises(HoldoutLeak, match=h):
        train_only([{"id": h}], split)


def test_holdout_only_raises_on_train_id():
    split = {i: assign(i) for i in IDS}
    t = next(i for i in IDS if split[i] == TRAIN)
    with pytest.raises(HoldoutLeak, match=t):
        holdout_only([{"id": t}], split)


def test_unknown_id_raises():
    with pytest.raises(HoldoutLeak, match="r-nope"):
        train_only([{"id": "r-nope"}], {})
