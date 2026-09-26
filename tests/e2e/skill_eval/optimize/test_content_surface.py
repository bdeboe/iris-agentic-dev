"""Tests for the `content-descriptions` surface — 130 T008 (User Story 3, FR-005).

The loop may rewrite only the descriptions of the skills 130 touched. Everything else on the menu
is scored but never proposed for, never written, and never changed in the finalist. The content
corpus joins the frozen routing corpus; its items obey the same hash split.

The scorer and reflection model are scripted stand-ins, as in `test_adapter.py`; gepa is real.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.e2e.skill_eval.optimize import holdout, menu, runner, surfaces
from tests.e2e.skill_eval.optimize.ledger import Ledger
from tests.e2e.skill_eval.optimize.menu import Skill

CONTENT = Path(menu.REPO) / "tests" / "e2e" / "tasks" / "content"
EIGHT = {
    "iris-query-plans",
    "objectscript-sql-patterns",
    "objectscript-unit-test",
    "iris-objectscript-eval",
    "objectscript-tdd",
    "ensemble-production",
    "objectscript-guardrails",
    "iris-agentic-dev",
}


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


needs_gepa = pytest.mark.skipif(
    not _gepa_pinned() and not os.environ.get("IAD_REQUIRE_GEPA"),
    reason="pinned gepa not installed",
)


def _content_items():
    return [
        json.loads(x)
        for x in (CONTENT / "corpus.jsonl").read_text().splitlines()
        if x.strip()
    ]


# --- the surface ---------------------------------------------------------------------------------


def test_content_skills_are_the_eight_130_touched():
    assert surfaces.CONTENT_SKILLS == frozenset(EIGHT)
    names = {s.name for s in menu.load_skills()}
    assert EIGHT <= names


def test_content_surface_is_registered_with_its_editable_set():
    s = surfaces.SURFACES["content-descriptions"]
    assert s.editable == surfaces.CONTENT_SKILLS
    assert surfaces.SURFACES["skill-descriptions"].editable is None
    assert s.extra_corpus == CONTENT


def test_apply_refuses_a_skill_outside_the_set(tmp_path):
    root = tmp_path / "skills"
    shutil.copytree(menu.SKILLS_ROOT, root)
    apply = surfaces.SURFACES["content-descriptions"].apply
    with pytest.raises(surfaces.NotEditable, match="iris-sql"):
        apply({"iris-sql": "USE FOR: x. DO NOT USE FOR: y."}, root=str(root))
    # Nothing was written, not even the permitted half of a mixed candidate.
    with pytest.raises(surfaces.NotEditable):
        apply(
            {
                "iris-query-plans": "USE FOR: plans. DO NOT USE FOR: other.",
                "iris-sql": "USE FOR: x. DO NOT USE FOR: y.",
            },
            root=str(root),
        )
    assert (root / "skills" / "iris-query-plans" / "SKILL.md").read_text() == (
        Path(menu.SKILLS_ROOT) / "skills" / "iris-query-plans" / "SKILL.md"
    ).read_text()


def test_apply_accepts_a_full_candidate_whose_locked_skills_are_unchanged(tmp_path):
    """candidate.json carries every description; only the changed ones must be editable."""
    root = tmp_path / "skills"
    shutil.copytree(menu.SKILLS_ROOT, root)
    full = {s.name: s.description for s in menu.load_skills(str(root))}
    full["objectscript-tdd"] = (
        "USE FOR: test-first ObjectScript. DO NOT USE FOR: other."
    )
    changed = surfaces.SURFACES["content-descriptions"].apply(full, root=str(root))
    assert [Path(p).parent.name for p in changed] == ["objectscript-tdd"]


def test_apply_writes_a_content_skill(tmp_path):
    root = tmp_path / "skills"
    shutil.copytree(menu.SKILLS_ROOT, root)
    new = "USE FOR: query plans. DO NOT USE FOR: other SQL."
    changed = surfaces.SURFACES["content-descriptions"].apply(
        {"iris-query-plans": new}, root=str(root)
    )
    assert [Path(p).parent.name for p in changed] == ["iris-query-plans"]
    by = {s.name: s for s in menu.load_skills(str(root))}
    assert by["iris-query-plans"].description == new


# --- the adapter ---------------------------------------------------------------------------------

SKILLS = [
    Skill("widgets", "Things about widgets.", "# Widgets\nWidgets and gadgets.", None),
    Skill("sprockets", "Sprocket help.", "# Sprockets\nSprocket tuning.", None),
]
GOOD = "USE FOR: widgets, gadgets and sprocket requests. DO NOT USE FOR: other."


def _adapter(reflect, split, editable):
    from tests.e2e.skill_eval.optimize.adapter import RoutingAdapter

    class Scorer:
        messages = None

        def __init__(self):
            self.messages = self

        def create(self, **kw):
            return SimpleNamespace(
                model="anthropic.claude-haiku-4-5-20251001-v1:0",
                content=[SimpleNamespace(text='{"skill": "none"}')],
                usage=SimpleNamespace(input_tokens=500, output_tokens=8),
            )

    return RoutingAdapter(
        SKILLS,
        Scorer(),
        "haiku",
        Ledger(budget_usd=5),
        reflect=reflect,
        split=split,
        workers=1,
        editable=editable,
    )


def _reflect(text):
    calls = []

    def reflect(prompt):
        calls.append(prompt)
        return f"<description>{text}</description>"

    reflect.calls = calls
    return reflect


@needs_gepa
def test_blame_on_a_locked_skill_goes_to_an_editable_one():
    ad = _adapter(_reflect(GOOD), {}, editable={"widgets"})
    traj = [
        {"scored": True, "gold": ["sprockets"], "pick": "none"},
        {"scored": True, "gold": ["sprockets"], "pick": "none"},
        {"scored": True, "gold": ["widgets"], "pick": "none"},
    ]
    cand = {s.name: s.description for s in SKILLS}
    assert ad.select_component(SimpleNamespace(i=0), traj, [], 0, cand) == ["widgets"]
    # No blame at all: the round-robin runs over the editable set only.
    for i in range(4):
        assert ad.select_component(SimpleNamespace(i=i), [], [], 0, cand) == ["widgets"]


@needs_gepa
def test_no_proposal_is_made_for_a_locked_skill():
    reflect = _reflect(GOOD)
    ad = _adapter(reflect, {}, editable={"widgets"})
    rows = [{"prompt": "p", "gold": ["sprockets"], "pick": "none", "kind": "miss"}]
    out = ad.propose_new_texts(
        {s.name: s.description for s in SKILLS}, {"sprockets": rows}, ["sprockets"]
    )
    assert out == {}
    assert (
        reflect.calls == []
    ), "the reflection model is never asked about a locked skill"


@needs_gepa
def test_editable_none_keeps_128_behaviour():
    ad = _adapter(_reflect(GOOD), {}, editable=None)
    traj = [{"scored": True, "gold": ["sprockets"], "pick": "none"}]
    cand = {s.name: s.description for s in SKILLS}
    assert ad.select_component(SimpleNamespace(i=0), traj, [], 0, cand) == ["sprockets"]


@needs_gepa
def test_loop_changes_only_editable_descriptions():
    from tests.e2e.skill_eval.optimize.adapter import run_loop

    items = [
        {
            "id": f"g{k}",
            "prompt": f"gadgets {k}",
            "gold": ["widgets"],
            "slice": "paraphrase",
        }
        for k in range(8)
    ] + [
        {
            "id": f"s{k}",
            "prompt": f"sprocket {k}",
            "gold": ["sprockets"],
            "slice": "paraphrase",
        }
        for k in range(8)
    ]
    split = {i["id"]: holdout.TRAIN for i in items}
    ad = _adapter(_reflect(GOOD), split, editable={"widgets"})
    best, _ = run_loop(ad, items, max_metric_calls=120, seed=130)
    assert best["sprockets"] == "Sprocket help."
    assert all(p["skill"] == "widgets" for p in ad.proposals)


# --- the content corpus --------------------------------------------------------------------------


def test_content_items_have_fields_and_two_agreeing_labels():
    items = _content_items()
    ids = [i["id"] for i in items]
    assert len(ids) == len(set(ids))
    names = {s.name for s in menu.load_skills()}
    for i in items:
        assert i["id"].startswith("c-"), i["id"]
        assert {"id", "prompt", "gold", "slice", "source", "labels"} <= i.keys(), i[
            "id"
        ]
        assert i["source"] == "author:130"
        assert [lab["pass"] for lab in i["labels"]] == [1, 2], i["id"]
        for lab in i["labels"]:
            assert set(lab["gold"]) <= set(i["gold"]), i["id"]
        if i["gold"] == ["none"]:
            assert i["slice"] == "no-skill", i["id"]
        else:
            assert set(i["gold"]) <= names, i["id"]


def test_every_content_skill_has_a_prompt_and_negatives_exist():
    items = _content_items()
    golds = {g for i in items for g in i["gold"]}
    assert EIGHT <= golds, EIGHT - golds
    assert any(i["gold"] == ["none"] for i in items)


def test_content_split_is_frozen_and_covers_the_corpus():
    split = holdout.load_split(CONTENT / "routing-split.toml")
    assert set(split) == {i["id"] for i in _content_items()}


def test_content_ids_do_not_collide_with_routing_ids():
    routing, _ = runner.load_corpus()
    assert not {i["id"] for i in routing} & {i["id"] for i in _content_items()}


def test_content_surface_corpus_is_routing_plus_content():
    items, split = runner.corpus_for("content-descriptions")
    routing, rsplit = runner.load_corpus()
    content = _content_items()
    assert len(items) == len(routing) + len(content)
    assert {
        k: split[k] for k in rsplit
    } == rsplit, "routing items keep their frozen side"
    items128, split128 = runner.corpus_for("skill-descriptions")
    assert (items128, split128) == (routing, rsplit)


# --- the CLI and an offline run ------------------------------------------------------------------


def test_cli_accepts_the_content_surface():
    from tests.e2e.skill_eval.optimize import __main__ as cli

    parser = cli.build_parser()
    assert "content-descriptions" in cli.SURFACES
    args = parser.parse_args(["run", "--surface", "content-descriptions"])
    assert args.surface == "content-descriptions"


@needs_gepa
def test_offline_content_run_changes_only_content_skills(tmp_path):
    from tests.e2e.skill_eval.optimize.test_runner import FakeClient, _tree_hash

    before = _tree_hash(menu.SKILLS_ROOT)

    def reflect(prompt):
        return "<description>USE FOR: query plans. DO NOT USE FOR: other SQL.</description>"

    run_dir = runner.run(
        client=FakeClient(),
        model=runner.BEDROCK_SCORER,
        reflect=reflect,
        ledger=Ledger(20),
        surface="content-descriptions",
        max_metric_calls=60,
        ladder=None,
        out_root=tmp_path,
        workers=1,
    )
    assert _tree_hash(menu.SKILLS_ROOT) == before
    c = json.loads((Path(run_dir) / "candidate.json").read_text())
    assert c["surface"] == "content-descriptions"
    routing, rsplit = runner.load_corpus()
    csplit = holdout.load_split(CONTENT / "routing-split.toml")
    n_hold = sum(v == holdout.HOLDOUT for v in rsplit.values()) + sum(
        v == holdout.HOLDOUT for v in csplit.values()
    )
    assert (
        c["seed_figures"]["n"] == n_hold
    ), "content holdout items join the routing holdout"
    seed = {s.name: s.description for s in menu.load_skills()}
    changed = {n for n, d in c["descriptions"].items() if d != seed.get(n)}
    assert changed <= EIGHT, changed - EIGHT
