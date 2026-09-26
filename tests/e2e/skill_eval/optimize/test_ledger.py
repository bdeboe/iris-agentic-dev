"""Tests for `ledger.py` — 128 T012, written before it (FR-008, SC-002)."""

from __future__ import annotations

import json

import pytest

from tests.e2e.skill_eval.optimize.ledger import BudgetExceeded, Ledger, Unpriced

HAIKU = "claude-haiku-4-5-20251001"


def test_cost_from_table():
    led = Ledger(budget_usd=10.0)
    e = led.record("score", HAIKU, 1_000_000, 100_000)
    assert e["cost_usd"] == pytest.approx(1.5)


def test_stops_at_cap_and_overshoots_by_at_most_one_call():
    led = Ledger(budget_usd=0.01)
    calls = 0
    with pytest.raises(BudgetExceeded):
        while True:
            led.check()
            led.record("score", HAIKU, 2000, 100)
            calls += 1
    one_call = (2000 * 1.0 + 100 * 5.0) / 1_000_000
    assert led.total_usd < 0.01 + one_call + 1e-12
    assert calls > 1


def test_record_that_crosses_cap_is_kept():
    led = Ledger(budget_usd=0.000001)
    with pytest.raises(BudgetExceeded):
        led.record("score", HAIKU, 1000, 0)
    assert (
        len(led.entries) == 1
    ), "the call happened and was paid for; the ledger must show it"


def test_unpriced_model_refuses_rather_than_guessing():
    led = Ledger(budget_usd=5)
    with pytest.raises(Unpriced, match="mystery-model"):
        led.record("reflect", "mystery-model", 10, 10)


def test_extra_rates_price_a_model():
    led = Ledger(budget_usd=5, extra_rates={"claude-sonnet-5": (3.0, 15.0)})
    assert led.record("reflect", "claude-sonnet-5", 1000, 1000)[
        "cost_usd"
    ] == pytest.approx(0.018)


def test_jsonl_has_running_total(tmp_path):
    led = Ledger(budget_usd=5)
    led.record("score", HAIKU, 1000, 0)
    led.record("score", HAIKU, 1000, 0)
    p = tmp_path / "ledger.jsonl"
    led.write(p)
    rows = [json.loads(x) for x in p.read_text().splitlines()]
    assert [r["kind"] for r in rows] == ["score", "score"]
    assert rows[-1]["total_usd"] == pytest.approx(0.002)


def test_multiplier_prices_regional_premium():
    led = Ledger(budget_usd=5, multiplier=1.1)
    assert led.record("score", HAIKU, 1_000_000, 0)["cost_usd"] == pytest.approx(1.1)


def test_sonnet_5_is_priced():
    led = Ledger(budget_usd=5)
    assert led.record("reflect", "claude-sonnet-5", 1_000_000, 100_000)[
        "cost_usd"
    ] == pytest.approx(3.0)


def test_concurrent_records_keep_the_total():
    from concurrent.futures import ThreadPoolExecutor

    led = Ledger(budget_usd=100)
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(lambda _: led.record("score", HAIKU, 1000, 0), range(400)))
    assert led.total_usd == pytest.approx(0.4)
    assert led.entries[-1]["total_usd"] == pytest.approx(0.4)


def test_stream_path_appends_every_entry_as_it_is_recorded(tmp_path):
    # 2026-09-26: a run killed at iteration 164 left no ledger at all; spend was unrecoverable.
    p = tmp_path / "ledger.jsonl"
    led = Ledger(budget_usd=10, stream_path=p)
    led.record("score", "claude-haiku-4-5", 1000, 10)
    assert len(p.read_text().splitlines()) == 1
    led.record("reflect", "claude-sonnet-5", 1000, 10)
    lines = [json.loads(x) for x in p.read_text().splitlines()]
    assert [e["kind"] for e in lines] == ["score", "reflect"]
