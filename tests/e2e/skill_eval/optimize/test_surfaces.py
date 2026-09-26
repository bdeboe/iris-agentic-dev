"""Tests for `surfaces.py` — 128 T022/T023 (FR-005, User Story 4)."""

from __future__ import annotations

import pytest

from tests.e2e.skill_eval.optimize.menu import split_front_matter
from tests.e2e.skill_eval.optimize.surfaces import SURFACES, set_description

DOC = """---
author: tdyar
description:
  "ObjectScript embedded SQL, date filtering. Use when writing SQL queries in
  ObjectScript classes.

  "
iris_version: ">=2024.1"
name: objectscript-sql-patterns
tags:
  - sql
---

# Body

description: this line is body text and must not change
"""


def test_only_the_description_value_changes():
    new = set_description(
        DOC, 'USE FOR: SQL "quoted" things: yes. DO NOT USE FOR: none.'
    )
    meta, body = split_front_matter(new)
    old_meta, old_body = split_front_matter(DOC)
    assert (
        meta["description"]
        == 'USE FOR: SQL "quoted" things: yes. DO NOT USE FOR: none.'
    )
    assert {k: v for k, v in meta.items() if k != "description"} == {
        k: v for k, v in old_meta.items() if k != "description"
    }
    assert body == old_body


def test_single_line_description_is_replaced():
    doc = "---\nname: x\ndescription: old one\ntags: [a]\n---\nbody\n"
    meta, _ = split_front_matter(set_description(doc, "new one"))
    assert meta == {"name": "x", "description": "new one", "tags": ["a"]}


def test_missing_description_key_raises():
    with pytest.raises(ValueError):
        set_description("---\nname: x\n---\nbody\n", "new")


def test_skill_descriptions_surface_is_registered():
    s = SURFACES["skill-descriptions"]
    skills = s.load()
    assert len(skills) >= 38


def test_apply_writes_into_a_given_root(tmp_path):
    import shutil

    from tests.e2e.skill_eval.optimize import menu

    src = tmp_path / "skills"
    shutil.copytree(menu.SKILLS_ROOT, src)
    changed = SURFACES["skill-descriptions"].apply(
        {"iris-sql": "USE FOR: a. DO NOT USE FOR: b."}, root=str(src)
    )
    assert len(changed) == 1 and changed[0].endswith("iris-sql/SKILL.md")
    meta, _ = split_front_matter(open(changed[0]).read())
    assert meta["description"] == "USE FOR: a. DO NOT USE FOR: b."
