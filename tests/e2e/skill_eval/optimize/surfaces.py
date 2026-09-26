"""Surfaces the loop can optimise, by `--surface` name (spec 128 FR-005).

A surface says how to load its seed texts and how to write a candidate back. 128 registers
`skill-descriptions`; 129 adds `hints`, the `text` of each rule in `hints.toml`. 130 adds
`content-descriptions`: the whole menu is scored, but only the skills 130 wrote or corrected may
change (`editable`), and its own author-written corpus joins the routing one (`extra_corpus`).

`set_description` rewrites only the front matter `description:` value, as a JSON-quoted string
(valid YAML double-quoted scalar), and leaves every other byte of the file alone.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from tests.e2e.skill_eval.optimize import hints_surface, menu

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


CONTENT_SKILLS = frozenset(
    {
        "iris-query-plans",
        "objectscript-sql-patterns",
        "objectscript-unit-test",
        "iris-objectscript-eval",
        "objectscript-tdd",
        "ensemble-production",
        "objectscript-guardrails",
        "iris-agentic-dev",
    }
)
CONTENT_CORPUS = Path(menu.REPO) / "tests" / "e2e" / "tasks" / "content"


class NotEditable(ValueError):
    pass


def _apply_content(
    descriptions: dict[str, str], root: str = menu.SKILLS_ROOT
) -> list[str]:
    """Write only CONTENT_SKILLS. A locked skill may appear, unchanged; changed, nothing is written."""
    current = {s.name: s.description for s in menu.load_skills(root)}
    locked = sorted(
        n
        for n, d in descriptions.items()
        if n not in CONTENT_SKILLS and d != current.get(n)
    )
    if locked:
        raise NotEditable(
            f"content-descriptions may not change {', '.join(locked)}; "
            f"editable: {', '.join(sorted(CONTENT_SKILLS))}"
        )
    # Unchanged values are skipped: rewriting one would still re-quote its front matter.
    return _apply_descriptions(
        {
            n: d
            for n, d in descriptions.items()
            if n in CONTENT_SKILLS and d != current.get(n)
        },
        root,
    )


@dataclass(frozen=True)
class Surface:
    name: str
    load: Callable
    apply: Callable
    editable: frozenset | None = None
    extra_corpus: Path | None = None


SURFACES = {
    "skill-descriptions": Surface(
        "skill-descriptions", menu.load_skills, _apply_descriptions
    ),
    "content-descriptions": Surface(
        "content-descriptions",
        menu.load_skills,
        _apply_content,
        editable=CONTENT_SKILLS,
        extra_corpus=CONTENT_CORPUS,
    ),
    "hints": Surface("hints", hints_surface.load_rules, hints_surface.apply_texts),
}
