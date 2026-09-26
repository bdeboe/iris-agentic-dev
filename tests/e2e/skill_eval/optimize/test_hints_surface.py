"""Tests for `hints_surface.py` — 129 T010 (User Story 3, FR-008).

The rules file, the corpus and the skills are the real committed ones, read-only; `apply` writes
only to a temp copy of `hints.toml`.
"""

from __future__ import annotations

import shutil
import tomllib

import pytest

from tests.e2e.skill_eval.optimize import hints_surface as hs
from tests.e2e.skill_eval.optimize import menu


def _rule(rid):
    return next(r for r in hs.load_rules() if r.id == rid)


def test_load_rules_reads_the_seven_shipped_rules():
    rules = hs.load_rules()
    assert len(rules) == 7
    assert {r.id for r in rules} >= {"sys_only_table", "nonstandard_insert"}
    assert all(r.text and r.skill and r.section for r in rules)


def test_placeholders_and_render_match_the_rust_substitution():
    r = _rule("deep_package_table")
    assert hs.placeholders(r.text) == {"name", "reported", "fixed"}
    out = hs.render(
        r.text,
        {"name": "A.B.C", "reported": "B.C", "fixed": "A_B.C"},
    )
    assert "A_B.C" in out and "{" not in out


def test_section_text_stops_at_the_next_heading_of_the_same_level():
    body = "# Top\nintro\n## 1. One\nalpha `x`\n### sub\nbeta\n## 2. Two\ngamma\n"
    got = hs.section_text(body, "1. One")
    assert "alpha" in got and "beta" in got and "gamma" not in got
    with pytest.raises(KeyError):
        hs.section_text(body, "Nope")


def test_every_rule_section_resolves_in_its_skill():
    by_name = {s.name: s for s in menu.load_skills()}
    for r in hs.load_rules():
        assert hs.section_text(by_name[r.skill].body, r.section).strip()


def test_the_seed_texts_pass_their_own_validator():
    ctx = hs.contexts()
    for r in hs.load_rules():
        assert hs.validate(r.text, **ctx[r.id]) == [], r.id


@pytest.mark.parametrize(
    "mutate, reason",
    [
        (lambda t: t.replace("{table}", "the table"), "placeholder"),
        (lambda t: t + " {extra}", "placeholder"),
        (lambda t: t + " See iris-agentic-dev.", "skill"),
        (lambda t: t + " Skill X.", "skill"),
        (lambda t: t + " x" * 300, "400"),
        (lambda t: t + " Or call $ZSTRIP first.", "new fact"),
        (lambda t: t + " Catch SQLCODE -400.", "new fact"),
        (lambda t: t + " Use `iris_admin`.", "new fact"),
        (lambda t: t + " {", "brace"),
        (lambda t: "", "empty"),
    ],
)
def test_the_validator_rejects(mutate, reason):
    r = _rule("sys_only_table")
    got = hs.validate(mutate(r.text), **hs.contexts()[r.id])
    assert got, "expected a rejection"
    assert any(reason in g for g in got), got


def test_a_fact_from_the_cited_section_is_allowed():
    r = _rule("nonstandard_insert")
    ctx = hs.contexts()[r.id]
    # The section has INSERT OR IGNORE inside a code block, not backticked; it still counts.
    assert "INSERT OR IGNORE" in ctx["section"]
    assert hs.validate(r.text + " `INSERT OR IGNORE` too.", **ctx) == []


def test_set_texts_changes_only_text_values(tmp_path):
    src = hs.HINTS_TOML.read_text()
    new = hs.set_texts(src, {"reserved_word": 'Reserved: {word}. Quote it "{word}".'})
    before = {r["id"]: r for r in tomllib.loads(src)["rule"]}
    after = {r["id"]: r for r in tomllib.loads(new)["rule"]}
    assert after["reserved_word"]["text"] == 'Reserved: {word}. Quote it "{word}".'
    for rid in before:
        for k in ("skill", "section", "why"):
            assert before[rid][k] == after[rid][k]
        if rid != "reserved_word":
            assert before[rid]["text"] == after[rid]["text"]
    # Comments and every other line survive byte for byte.
    changed = [(a, b) for a, b in zip(src.splitlines(), new.splitlines()) if a != b]
    assert len(changed) == 1 and changed[0][0].startswith("text = ")


def test_set_texts_refuses_an_unknown_rule():
    with pytest.raises(KeyError):
        hs.set_texts(hs.HINTS_TOML.read_text(), {"nope": "x"})


def test_apply_texts_writes_the_given_file_only(tmp_path):
    path = tmp_path / "hints.toml"
    shutil.copy(hs.HINTS_TOML, path)
    shipped = hs.HINTS_TOML.read_text()
    seed = _rule("sys_only_class").text
    assert hs.apply_texts({"sys_only_class": seed}, path=path) == []
    assert hs.apply_texts({"sys_only_class": "{class} is %SYS only."}, path=path) == [
        str(path)
    ]
    assert "{class} is %SYS only." in path.read_text()
    assert hs.HINTS_TOML.read_text() == shipped


def test_load_items_takes_live_positives_with_their_skill():
    items = hs.load_items()
    assert len(items) >= 20
    rules = {r.id: r for r in hs.load_rules()}
    for it in items:
        assert it["rule"] in rules
        assert it["skill"] == rules[it["rule"]].skill
        assert set(it["vars"]) == hs.placeholders(rules[it["rule"]].text)
    assert {it["rule"] for it in items} == set(rules)
