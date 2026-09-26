"""Tests for `validator.py` — 128 T010, written before it (FR-006, FR-011, SC-003).

Each rejection rule gets a text that breaks it and nothing else, so a failure names the rule.
"""

from __future__ import annotations

from tests.e2e.skill_eval.optimize.validator import MAX_CHARS, facts, validate

BODY = "Use `%SQL.Statement` and `$ListBuild`. Error #1054 means a bad expression. Call iris_query."
SEED = "ObjectScript SQL patterns."
GOOD = "USE FOR: embedded SQL and %SQL.Statement in ObjectScript. DO NOT USE FOR: DDL design."


def test_good_candidate_passes():
    assert validate(GOOD, body=BODY, seed=SEED, require_markers=True) == []


def test_over_length_rejected():
    text = GOOD + " x" * MAX_CHARS
    assert any(
        "1024" in r for r in validate(text, body=BODY, seed=SEED, require_markers=True)
    )


def test_exactly_at_cap_passes():
    text = (GOOD + " " + "a" * MAX_CHARS)[:MAX_CHARS]
    assert not any(
        "1024" in r for r in validate(text, body=BODY, seed=SEED, require_markers=True)
    )


def test_empty_rejected():
    assert validate("  ", body=BODY, seed=SEED, require_markers=False)


def test_missing_markers_rejected_only_when_required():
    text = "Embedded SQL and %SQL.Statement in ObjectScript."
    assert any(
        "USE FOR" in r
        for r in validate(text, body=BODY, seed=SEED, require_markers=True)
    )
    assert validate(text, body=BODY, seed=SEED, require_markers=False) == []


def test_do_not_use_for_alone_does_not_satisfy_use_for():
    text = "DO NOT USE FOR: DDL design."
    assert any(
        "USE FOR:" in r
        for r in validate(text, body=BODY, seed=SEED, require_markers=True)
    )


def test_new_class_name_rejected():
    text = GOOD + " Covers %Library.ResultSet too."
    rs = validate(text, body=BODY, seed=SEED, require_markers=True)
    assert any("%Library.ResultSet" in r for r in rs)


def test_new_error_code_rejected():
    rs = validate(GOOD + " Fixes #5559.", body=BODY, seed=SEED, require_markers=True)
    assert any("#5559" in r for r in rs)


def test_new_function_and_error_token_rejected():
    rs = validate(
        GOOD + " $Piece gives <UNDEFINED>.", body=BODY, seed=SEED, require_markers=True
    )
    assert any("$Piece" in r for r in rs) and any("<UNDEFINED>" in r for r in rs)


def test_new_backticked_span_rejected():
    rs = validate(GOOD + " Use `Quit:x`.", body=BODY, seed=SEED, require_markers=True)
    assert any("Quit:x" in r for r in rs)


def test_new_tool_name_rejected():
    rs = validate(
        GOOD + " Pairs with iris_compile.", body=BODY, seed=SEED, require_markers=True
    )
    assert any("iris_compile" in r for r in rs)


def test_facts_from_body_or_seed_allowed():
    text = GOOD + " Covers $ListBuild, #1054 and iris_query."
    assert validate(text, body=BODY, seed=SEED, require_markers=True) == []


def test_fact_match_ignores_case_for_functions():
    assert (
        validate(GOOD + " $LISTBUILD", body=BODY, seed=SEED, require_markers=True) == []
    )


def test_facts_extracts_each_kind():
    got = facts("`a b` %Foo.Bar $Get #123 <DIVIDE> iris_doc skill_describe")
    assert {
        "a b",
        "%Foo.Bar",
        "$get",
        "#123",
        "<DIVIDE>",
        "iris_doc",
        "skill_describe",
    } <= got
