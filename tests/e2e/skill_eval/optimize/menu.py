"""The skill menu: names, descriptions and bodies of every skill iad ships (spec 128).

Two readers. The routing proxy shows name + description, the way an agent's skill list does. The blind
labeller (FR-002) sees name + body headings and never the description, because a label chosen from
the description measures how well the description matches itself.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import yaml

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
SKILLS_ROOT = os.path.join(REPO, "skills")
CARD_BODY_LINES = 25


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    path: str


def split_front_matter(text: str) -> tuple[dict, str]:
    m = re.match(r"---\n(.*?)\n---\n?", text, re.S)
    if not m:
        raise ValueError("no front matter block")
    return yaml.safe_load(m.group(1)) or {}, text[m.end() :]


def _skill_paths(root: str = SKILLS_ROOT) -> list[str]:
    paths = []
    for base in (os.path.join(root, "skills"), root):
        for entry in sorted(os.listdir(base)):
            p = os.path.join(base, entry, "SKILL.md")
            if os.path.isfile(p):
                paths.append(p)
    return paths


def load_skills(root: str = SKILLS_ROOT) -> list[Skill]:
    out = []
    for p in _skill_paths(root):
        meta, body = split_front_matter(open(p, encoding="utf-8").read())
        desc = " ".join(str(meta.get("description", "")).split())
        out.append(Skill(str(meta["name"]), desc, body, p))
    return out


def render_menu(skills: list[Skill], descriptions: dict[str, str] | None = None) -> str:
    descriptions = descriptions or {}
    return "\n".join(
        f"- {s.name}: {descriptions.get(s.name, s.description)}" for s in skills
    )


def blind_card(skill: Skill) -> str:
    """Name, section headings and the opening lines of the body. No front matter."""
    lines = skill.body.strip().splitlines()
    headings = [ln.strip() for ln in lines if ln.startswith("#")]
    opening = [ln for ln in lines[:CARD_BODY_LINES] if ln.strip()]
    return "\n".join(
        [f"## SKILL {skill.name}", "Headings: " + " | ".join(headings), *opening]
    )
