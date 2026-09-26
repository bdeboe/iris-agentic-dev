"""Tests for `hints_proxy.py` — 129 T010 (User Story 3, FR-010).

The scorer is a scripted stand-in for the model API. The checker's IRIS side is a scripted runner;
the real one is exercised by `test_iad_checker_against_live_iris`, which needs iris-dev-iris.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.e2e.skill_eval.optimize import hints_proxy as hp
from tests.e2e.skill_eval.optimize import hints_surface as hs
from tests.e2e.skill_eval.optimize import menu
from tests.e2e.skill_eval.optimize.ledger import Ledger

HAIKU = "anthropic.claude-haiku-4-5-20251001-v1:0"


def reply(text):
    return SimpleNamespace(
        model=HAIKU,
        content=[SimpleNamespace(text=text)],
        usage=SimpleNamespace(input_tokens=3000, output_tokens=60),
    )


class Scripted:
    def __init__(self, texts):
        self.messages = self
        self.texts = list(texts)
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        t = self.texts.pop(0)
        if isinstance(t, Exception):
            raise t
        return reply(t)


class FakeRunner:
    """Stands in for `iris_execute` through the iad CLI: returns the parsed JSON answer."""

    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def __call__(self, code, namespace):
        self.calls.append((code, namespace))
        return self.answer(code, namespace) if callable(self.answer) else self.answer


def _item(rule="sys_only_table"):
    return next(i for i in hs.load_items() if i["rule"] == rule)


# ── the scorer prompt and its answer ──────────────────────────────────────────────────────


def test_the_prompt_shows_the_call_error_and_hint_but_not_hint_ref():
    it = _item()
    system, user = hp.build_messages("- a: b", it, "HINT TEXT")
    assert "- a: b" in system
    assert it["captured"] in user and "HINT TEXT" in user
    assert json.dumps(it["args"], sort_keys=True) in user
    assert "hint_ref" not in user and it["skill"] not in user


def test_parse_answer_reads_nested_json_and_checks_the_skill():
    names = {"iris-sql", "iris-agentic-dev"}
    got = hp.parse_answer(
        'Sure. {"skill": "iris-sql", "fix": {"query": "SELECT 1"}, "namespace": "USER"}',
        names,
    )
    assert got == ("iris-sql", {"query": "SELECT 1", "namespace": "USER"})
    got = hp.parse_answer(
        '{"skill": "none", "fix": {"code": "Write 1", "namespace": "%SYS"}}', names
    )
    assert got == ("none", {"code": "Write 1", "namespace": "%SYS"})
    for bad in [
        "no json",
        '{"skill": "made-up", "fix": {"query": "x"}}',
        '{"skill": "iris-sql"}',
        '{"skill": "iris-sql", "fix": {"query": 3}}',
    ]:
        with pytest.raises(ValueError):
            hp.parse_answer(bad, names)


# ── the pass checker ──────────────────────────────────────────────────────────────────────


def test_sql_fixes_are_prepared_never_executed():
    run = FakeRunner({"success": True, "output": "PREPARED"})
    chk = hp.Checker(run)
    assert chk({"query": 'SELECT "a"\nFROM T', "namespace": "%SYS"}) is True
    code, ns = run.calls[0]
    assert ns == "%SYS"
    assert "%Prepare(" in code and "%Execute" not in code and "ExecDirect" not in code
    assert '""a""' in code and "\n" not in code


def test_a_failed_prepare_is_a_fail_and_a_runtime_error_is_a_fail():
    chk = hp.Checker(FakeRunner({"success": True, "output": "PREPARE_FAILED: -30"}))
    assert chk({"query": "SELECT 1", "namespace": "USER"}) is False
    chk = hp.Checker(
        FakeRunner(
            {"success": False, "error_code": "IRIS_RUNTIME_ERROR", "output": "<SYNTAX>"}
        )
    )
    assert chk({"code": "Wrte 1", "namespace": "USER"}) is False


def test_a_transport_failure_leaves_the_item_unscored():
    chk = hp.Checker(
        FakeRunner({"success": False, "error_code": "HTTP_EXECUTION_FAILED"})
    )
    assert chk({"query": "SELECT 1", "namespace": "USER"}) is None
    chk = hp.Checker(FakeRunner(None))
    assert chk({"code": "Write 1", "namespace": "USER"}) is None


@pytest.mark.parametrize(
    "code",
    [
        "Kill ^X",
        "K ^X",
        "Set ^X=1",
        "s ^X(1)=2",
        "Do obj.%Save()",
        "Do ##class(A.B).%DeleteId(1)",
        'Do ##class(Security.Users).Delete("x")',
        'Do ##class(Security.Users).Create("x")',
        'Do ##class(Security.Users).Modify("x",.p)',
        'Xecute "w 1"',
        'Do ##class(%SYS.Python).Import("os")',
        'Do ##class(%SQL.Statement).%ExecDirect(,"DELETE FROM T")',
        "Job ^R",
        'Write $ZF(-1,"ls")',
        "Do ^ROUTINE",
    ],
)
def test_runtime_fixes_with_a_write_verb_are_not_run(code):
    run = FakeRunner({"success": True})
    assert hp.Checker(run)({"code": code, "namespace": "%SYS"}) is False
    assert run.calls == []


def test_a_clean_runtime_fix_runs_and_passes():
    run = FakeRunner({"success": True, "output": "1"})
    fix = {
        "code": 'Write ##class(Security.Users).Exists("_SYSTEM")',
        "namespace": "%SYS",
    }
    assert hp.Checker(run)(fix) is True
    assert run.calls == [(fix["code"], "%SYS")]


def test_the_checker_caches_by_fix():
    run = FakeRunner({"success": True, "output": "PREPARED"})
    chk = hp.Checker(run)
    for _ in range(3):
        chk({"query": "SELECT 1", "namespace": "USER"})
    assert len(run.calls) == 1


# ── one item scored ───────────────────────────────────────────────────────────────────────


def _skills():
    return menu.load_skills()


def test_reach_and_pass_make_the_score():
    it = _item()
    names = {s.name for s in _skills()}
    ok = FakeRunner({"success": True, "output": "PREPARED"})
    ans = '{"skill": "%s", "fix": {"query": "SELECT Name FROM Security.Users"}, "namespace": "%%SYS"}'
    r = hp.score_item(
        Scripted([ans % it["skill"]]),
        "m",
        "menu",
        it,
        "hint",
        names,
        Ledger(5),
        hp.Checker(ok),
    )
    assert (r.scored, r.reach, r.passed, r.score) == (True, True, True, 1.0)
    r = hp.score_item(
        Scripted([ans % "iris-sql"]),
        "m",
        "menu",
        it,
        "hint",
        names,
        Ledger(5),
        hp.Checker(ok),
    )
    assert (r.reach, r.passed, r.score) == (False, True, 0.5)


def test_two_bad_answers_leave_the_item_unscored():
    it = _item()
    names = {s.name for s in _skills()}
    r = hp.score_item(
        Scripted([RuntimeError("outage"), "not json"]),
        "m",
        "menu",
        it,
        "hint",
        names,
        Ledger(5),
        hp.Checker(FakeRunner(None)),
    )
    assert not r.scored and r.score is None and "outage" in r.reason


def test_score_items_renders_each_items_hint_from_the_candidate():
    items = [_item("sys_only_table"), _item("reserved_word")]
    client = Scripted(['{"skill": "none", "fix": {"query": "SELECT 1"}}'] * 2)
    cand = {"sys_only_table": "T={table} NS={namespace}", "reserved_word": "W={word}"}
    hp.score_items(
        items,
        _skills(),
        cand,
        client,
        "m",
        Ledger(5),
        hp.Checker(FakeRunner({"success": True, "output": "PREPARED"})),
        workers=1,
    )
    users = [c["messages"][0]["content"] for c in client.calls]
    v0, v1 = items[0]["vars"], items[1]["vars"]
    assert f"T={v0['table']} NS={v0['namespace']}" in users[0]
    assert f"W={v1['word']}" in users[1]


# ── the real checker, live ────────────────────────────────────────────────────────────────


def _iad_binary():
    repo = Path(menu.REPO)
    for p in [os.environ.get("IAD_BINARY"), repo / "target/debug/iris-agentic-dev"]:
        if p and Path(p).exists():
            return str(p)
    return shutil.which("iris-agentic-dev")


@pytest.mark.skipif(
    not os.environ.get("IRIS_HOST"), reason="needs iris-dev-iris (IRIS_HOST etc.)"
)
def test_iad_checker_against_live_iris():
    chk = hp.Checker(hp.IadRunner(_iad_binary()))
    assert (
        chk({"query": "SELECT TOP 1 Name FROM Security.Users", "namespace": "%SYS"})
        is True
    )
    assert (
        chk({"query": "SELECT TOP 1 Name FROM Security.Users", "namespace": "USER"})
        is False
    )
    fix = {
        "code": 'Write ##class(Security.Users).Exists("_SYSTEM")',
        "namespace": "%SYS",
    }
    assert chk(fix) is True
    assert chk({**fix, "namespace": "USER"}) is False
    # Every committed fix in the corpus passes the real checker.
    for it in hs.load_items():
        assert chk(it["fix"]) is True, it["id"]
