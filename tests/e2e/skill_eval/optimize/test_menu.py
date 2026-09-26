"""Tests for `menu.py` — 128 T020, written before it.

The menu is what the routing proxy shows and what the labeller must never see, so both halves are
pinned against the real `skills/` tree rather than a fixture: a fixture agrees with a reader that
skips the four plugin skills.
"""

from __future__ import annotations

import pytest

from tests.e2e.skill_eval.optimize.menu import (
    Skill,
    blind_card,
    load_skills,
    render_menu,
    split_front_matter,
)


def test_loads_bundled_and_plugin_skills():
    names = {s.name for s in load_skills()}
    assert "objectscript-sql-patterns" in names
    assert "pyprod" in names, "plugin skills at the top of skills/ are on the menu too"
    assert len(names) == 38


def test_every_skill_has_description_and_body():
    for s in load_skills():
        assert s.description.strip(), s.name
        assert s.body.strip(), s.name
        assert "description:" not in s.body.split("\n", 3)[0], s.name


def test_folded_description_is_one_line():
    for s in load_skills():
        assert "\n" not in s.description, f"{s.name} description kept a newline"


def test_split_front_matter_rejects_missing_block():
    with pytest.raises(ValueError, match="front matter"):
        split_front_matter("# no front matter\n")


def test_render_menu_lists_every_name_once_with_given_descriptions():
    skills = [Skill("a", "desc a", "body", "p"), Skill("b", "desc b", "body", "p")]
    menu = render_menu(skills, {"b": "NEW b"})
    assert menu.count("- a:") == 1 and "desc a" in menu
    assert "NEW b" in menu and "desc b" not in menu


def test_blind_card_never_contains_the_description():
    for s in load_skills():
        card = blind_card(s)
        assert s.name in card
        # a long description would leak whole; the first 60 chars are enough to catch it
        assert s.description[:60] not in card, f"{s.name} card leaks its description"
