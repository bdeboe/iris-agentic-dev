"""CI guard over every shipped skill description — 128 T030 (FR-011).

Same validator the loop runs on candidates, with the `USE FOR:`/`DO NOT USE FOR:` markers off:
the 38 shipped descriptions predate them. The seed is empty, so every fact a description names
must be in its own skill body.
"""

from __future__ import annotations

import re

import pytest
import yaml

from tests.e2e.skill_eval.optimize import menu, validator

SKILLS = menu.load_skills()
_FM = re.compile(r"\A---\n(.*?\n)---\n", re.S)


class _StrictLoader(yaml.SafeLoader):
    pass


def _no_duplicates(loader, node, deep=False):
    keys = [loader.construct_object(k, deep=deep) for k, _ in node.value]
    dup = {k for k in keys if keys.count(k) > 1}
    if dup:
        raise yaml.constructor.ConstructorError(
            None, None, f"duplicate keys {sorted(dup)}", node.start_mark
        )
    return loader.construct_mapping(node, deep)


_StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicates
)


def test_every_skill_is_loaded():
    assert len(SKILLS) == len(menu._skill_paths()) >= 30


@pytest.mark.parametrize("skill", SKILLS, ids=lambda s: s.name)
def test_shipped_description_passes_validator(skill):
    assert (
        validator.validate(
            skill.description, body=skill.body, seed="", require_markers=False
        )
        == []
    )


@pytest.mark.parametrize("path", menu._skill_paths(), ids=lambda p: p.split("/")[-2])
def test_front_matter_is_strict_yaml(path):
    m = _FM.match(open(path).read())
    assert m, f"{path}: no front matter"
    fm = yaml.load(m.group(1), Loader=_StrictLoader)
    assert isinstance(fm.get("description"), str) and fm["description"].strip()


def test_guard_bites_on_an_invented_fact():
    s = SKILLS[0]
    assert validator.validate(
        s.description + " Call `%Zz.NotInBody`.",
        body=s.body,
        seed="",
        require_markers=False,
    )


def test_strict_loader_rejects_duplicate_keys():
    with pytest.raises(yaml.constructor.ConstructorError):
        yaml.load("name: a\nname: b\n", Loader=_StrictLoader)
