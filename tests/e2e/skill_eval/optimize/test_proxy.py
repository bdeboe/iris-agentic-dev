"""Tests for `proxy.py` — 128 T021 (FR-004). The client is a scripted stand-in for the model API.

No IRIS is involved anywhere in the proxy; the stand-in replaces the Anthropic SDK only.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.e2e.skill_eval.optimize.ledger import Ledger
from tests.e2e.skill_eval.optimize.proxy import (
    build_messages,
    parse_pick,
    route,
    score_items,
)

NAMES = {"iris-sql", "objectscript-review"}


class Scripted:
    """Answers `messages.create` from a list; an Exception in the list is raised."""

    def __init__(self, answers, model="anthropic.claude-haiku-4-5-20251001-v1:0"):
        self.answers = list(answers)
        self.calls = []
        self.model = model
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return SimpleNamespace(
            model=self.model,
            content=[SimpleNamespace(type="text", text=a)],
            usage=SimpleNamespace(input_tokens=2500, output_tokens=10),
        )


def _led():
    return Ledger(budget_usd=5)


def test_parse_pick_reads_json_and_none():
    assert parse_pick('{"skill": "iris-sql"}', NAMES) == "iris-sql"
    assert parse_pick('noise {"skill": "none"} noise', NAMES) == "none"


def test_parse_pick_rejects_unknown_names_and_garbage():
    with pytest.raises(ValueError):
        parse_pick('{"skill": "made-up"}', NAMES)
    with pytest.raises(ValueError):
        parse_pick("I think iris-sql", NAMES)


def test_messages_show_the_menu_and_the_prompt():
    system, user = build_messages("- iris-sql: SQL things", "why is my query slow")
    assert "- iris-sql: SQL things" in system and "none" in system
    assert "why is my query slow" in user


def test_route_scores_exact_match_to_any_gold_name():
    c = Scripted(['{"skill": "iris-sql"}'])
    r = route(
        c,
        "m",
        "menu",
        {"id": "a", "prompt": "p", "gold": ["objectscript-review", "iris-sql"]},
        NAMES,
        _led(),
    )
    assert r.scored and r.correct and r.pick == "iris-sql"
    assert r.model.startswith("anthropic.claude-haiku")


def test_route_none_on_no_skill_prompt_is_correct_and_skill_is_false_hint():
    ok = route(
        Scripted(['{"skill": "none"}']),
        "m",
        "menu",
        {"id": "a", "prompt": "p", "gold": ["none"]},
        NAMES,
        _led(),
    )
    bad = route(
        Scripted(['{"skill": "iris-sql"}']),
        "m",
        "menu",
        {"id": "a", "prompt": "p", "gold": ["none"]},
        NAMES,
        _led(),
    )
    assert ok.correct and not bad.correct


def test_one_retry_then_unscored_with_reason():
    c = Scripted([RuntimeError("throttled"), "garbage"])
    led = _led()
    r = route(
        c, "m", "menu", {"id": "a", "prompt": "p", "gold": ["iris-sql"]}, NAMES, led
    )
    assert not r.scored and r.correct is None
    assert "garbage" in r.reason or "unparseable" in r.reason
    assert len(c.calls) == 2
    assert (
        len(led.entries) == 1
    ), "the call that answered was paid for; the one that raised was not"


def test_retry_that_succeeds_is_scored():
    r = route(
        Scripted([RuntimeError("x"), '{"skill": "iris-sql"}']),
        "m",
        "menu",
        {"id": "a", "prompt": "p", "gold": ["iris-sql"]},
        NAMES,
        _led(),
    )
    assert r.scored and r.correct


def test_score_items_uses_the_candidate_descriptions():
    from tests.e2e.skill_eval.optimize.menu import Skill

    skills = [
        Skill("iris-sql", "old sql text", "", None),
        Skill("objectscript-review", "review", "", None),
    ]
    c = Scripted(['{"skill": "iris-sql"}'])
    items = [{"id": "a", "prompt": "p", "gold": ["iris-sql"]}]
    out = score_items(
        items, skills, {"iris-sql": "NEW SQL TEXT"}, c, "m", _led(), workers=1
    )
    assert out[0].correct
    assert (
        "NEW SQL TEXT" in c.calls[0]["system"]
        and "old sql text" not in c.calls[0]["system"]
    )


# anthropic 1.x dropped `temperature` from `messages.create`; the 2026-09-26 smoke run lost all
# 80 holdout items to a TypeError. Every call must use only keywords both SDK lines accept.
SDK_KWARGS = {"model", "max_tokens", "system", "messages"}


def test_route_passes_only_portable_sdk_keywords():
    c = Scripted(['{"skill": "iris-sql"}'])
    route(
        c,
        "m",
        "- iris-sql: x",
        {"id": "a", "prompt": "p", "gold": ["iris-sql"], "slice": "paraphrase"},
        NAMES,
        _led(),
    )
    assert set(c.calls[0]) <= SDK_KWARGS


def test_reflect_passes_only_portable_sdk_keywords():
    from tests.e2e.skill_eval.optimize.runner import make_reflect

    c = Scripted(["<description>x</description>"], model="claude-sonnet-5")
    make_reflect(c, "us.anthropic.claude-sonnet-5", _led())("prompt")
    assert set(c.calls[0]) <= SDK_KWARGS
