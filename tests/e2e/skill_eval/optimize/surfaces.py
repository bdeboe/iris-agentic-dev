"""Surfaces the loop can optimise, by `--surface` name (spec 128 FR-005).

A surface says how to load its seed texts and how to write a candidate back. 128 registers
`skill-descriptions`; 129 and 130 add theirs here.

`set_description` rewrites only the front matter `description:` value, as a JSON-quoted string
(valid YAML double-quoted scalar), and leaves every other byte of the file alone.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable

from tests.e2e.skill_eval.optimize import menu

_FM = re.compile(r"\A---\n(.*?\n)---\n", re.S)
_KEY = re.compile(r"^[A-Za-z_][\w-]*:")


def set_description(text: str, description: str) -> str:
    m = _FM.match(text)
    if not m:
        raise ValueError("no front matter block")
    lines = m.group(1).splitlines(keepends=True)
    start = next(
        (k for k, ln in enumerate(lines) if ln.startswith("description:")), None
    )
    if start is None:
        raise ValueError("front matter has no description key")
    end = start + 1
    while end < len(lines) and not _KEY.match(lines[end]):
        end += 1
    lines[start:end] = [f"description: {json.dumps(description, ensure_ascii=False)}\n"]
    new = "---\n" + "".join(lines) + "---\n" + text[m.end() :]
    meta, _ = menu.split_front_matter(new)
    if meta.get("description") != description:
        raise ValueError("description did not round-trip through YAML")
    return new


def _apply_descriptions(
    descriptions: dict[str, str], root: str = menu.SKILLS_ROOT
) -> list[str]:
    by_name = {s.name: s.path for s in menu.load_skills(root)}
    changed = []
    for name, desc in sorted(descriptions.items()):
        path = by_name[name]
        old = open(path, encoding="utf-8").read()
        new = set_description(old, desc)
        if new != old:
            open(path, "w", encoding="utf-8").write(new)
            changed.append(path)
    return changed


@dataclass(frozen=True)
class Surface:
    name: str
    load: Callable
    apply: Callable


SURFACES = {
    "skill-descriptions": Surface(
        "skill-descriptions", menu.load_skills, _apply_descriptions
    ),
}
