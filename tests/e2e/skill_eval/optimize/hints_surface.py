"""The `hints` surface: the `text` of each rule in `hints.toml` (spec 129 FR-008).

`load_rules` reads the rules; `set_texts` rewrites `text = ...` lines and no other byte, so `id`,
`skill`, `section`, `why` and every comment stay as a human wrote them. The matchers live in Rust
and the loop cannot reach them.

`validate` is the 129 counterpart of `validator.validate`. A hint is shown on every matching error,
so its rules are tighter than a description's:

- the same `{placeholders}` as the seed, and no stray brace (Rust fills them by plain replace);
- no skill name and no "Skill " (the reference is `hint_ref`, which `IAD_CODING_PACK=off` drops);
- 400 characters or fewer, not empty;
- no new facts: any identifier-like token (128's patterns, plus negative SQLCODE numbers,
  CAPS_WITH_UNDERSCORE names and `$` functions) must already appear in the cited section or the
  seed text. A substring match counts, so a phrase inside a code block is a known fact.
"""

from __future__ import annotations

import json
import re
import string
import tomllib
from dataclasses import dataclass
from pathlib import Path

from tests.e2e.skill_eval.optimize import menu, validator

HINTS_TOML = (
    Path(menu.REPO)
    / "crates"
    / "iris-agentic-dev-core"
    / "src"
    / "tools"
    / "hints.toml"
)
HINTS_DIR = Path(menu.REPO) / "tests" / "e2e" / "tasks" / "hints"
CORPUS = HINTS_DIR / "replay.jsonl"
SPLIT = HINTS_DIR / "hints-split.toml"
MAX_CHARS = 400

_EXTRA = (
    re.compile(r"(?<![\w-])(-\d{1,4})\b"),
    re.compile(r"\b([A-Z][A-Z0-9]*_[A-Z0-9_]*[A-Z0-9])\b"),
)
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")


@dataclass(frozen=True)
class Rule:
    id: str
    skill: str
    section: str
    why: str
    text: str


def load_rules(path=HINTS_TOML) -> list[Rule]:
    doc = tomllib.loads(Path(path).read_text())
    return [Rule(**r) for r in doc["rule"]]


def placeholders(text: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(text) if f is not None}


def render(template: str, vars: dict) -> str:
    """Fill `{name}` the way `Hint::new` does: plain replace, nothing else touched."""
    for k, v in vars.items():
        template = template.replace("{" + k + "}", str(v))
    return template


def section_text(body: str, heading: str) -> str:
    """The section under `heading`, up to the next heading of the same or a higher level."""
    lines = body.splitlines()
    fenced = False
    start = level = None
    for n, ln in enumerate(lines):
        if _FENCE.match(ln):
            fenced = not fenced
            continue
        m = None if fenced else _HEADING.match(ln)
        if not m:
            continue
        if start is None:
            if m.group(2) == heading:
                start, level = n, len(m.group(1))
        elif len(m.group(1)) <= level:
            return "\n".join(lines[start:n])
    if start is None:
        raise KeyError(f"no heading {heading!r}")
    return "\n".join(lines[start:])


def contexts(path=HINTS_TOML, root: str = menu.SKILLS_ROOT) -> dict[str, dict]:
    """`validate` kwargs per rule: the cited section, the seed text, the skill names."""
    skills = menu.load_skills(root)
    by_name = {s.name: s for s in skills}
    names = tuple(sorted(by_name))
    return {
        r.id: {
            "section": section_text(by_name[r.skill].body, r.section),
            "seed": r.text,
            "skill_names": names,
        }
        for r in load_rules(path)
    }


def _tokens(text: str) -> dict[str, str]:
    out = dict(validator._fact_map(text))
    for pat in _EXTRA:
        for m in pat.finditer(text):
            out.setdefault(m.group(1), m.group(1))
    return out


def validate(text: str, *, section: str, seed: str, skill_names) -> list[str]:
    """Return the reasons `text` is rejected; empty means it passes."""
    if not text.strip():
        return ["hint is empty"]
    reasons = []
    if len(text) > MAX_CHARS:
        reasons.append(f"{len(text)} characters, over the {MAX_CHARS} cap")
    try:
        got = placeholders(text)
    except ValueError as e:
        reasons.append(f"stray brace: {e}")
    else:
        want = placeholders(seed)
        if got != want:
            reasons.append(
                f"placeholders {sorted(got)} differ from the seed's {sorted(want)}"
            )
    for name in skill_names:
        if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text, re.I):
            reasons.append(
                f"names the skill {name!r}; the reference belongs in hint_ref"
            )
    if "Skill " in text:
        reasons.append('says "Skill ": a skill reference belongs in hint_ref')
    known = section + "\n" + seed
    folded = known.lower()
    for key, tok in sorted(_tokens(text).items()):
        if tok in known or (tok.startswith("$") and tok.lower() in folded):
            continue
        reasons.append(f"new fact {tok!r} is in neither the cited section nor the seed")
    return reasons


_BLOCK = re.compile(r"^\s*\[\[rule\]\]\s*$")
_ID = re.compile(r'^\s*id\s*=\s*"([^"]+)"\s*$')
_TEXT = re.compile(r"^\s*text\s*=")


def set_texts(toml_text: str, texts: dict[str, str]) -> str:
    """Rewrite the `text = ...` line of each named rule; every other line stays byte for byte."""
    known = {r["id"] for r in tomllib.loads(toml_text)["rule"]}
    missing = set(texts) - known
    if missing:
        raise KeyError(f"hints.toml has no rule {sorted(missing)}")
    out = []
    current = None
    for ln in toml_text.splitlines(keepends=True):
        if _BLOCK.match(ln):
            current = None
        elif m := _ID.match(ln):
            current = m.group(1)
        elif current in texts and _TEXT.match(ln):
            end = "\n" if ln.endswith("\n") else ""
            ln = f"text = {json.dumps(texts[current], ensure_ascii=False)}{end}"
        out.append(ln)
    new = "".join(out)
    got = {r["id"]: r["text"] for r in tomllib.loads(new)["rule"]}
    for rid, t in texts.items():
        if got[rid] != t:
            raise ValueError(f"{rid}: text did not round-trip through TOML")
    return new


def apply_texts(texts: dict[str, str], *, path=HINTS_TOML, root=None) -> list[str]:
    """Write changed texts into `path`. Returns `[path]` if anything changed, else `[]`."""
    path = Path(path)
    current = {r.id: r.text for r in load_rules(path)}
    changed = {k: v for k, v in texts.items() if current.get(k) != v}
    if not changed:
        return []
    path.write_text(set_texts(path.read_text(), changed))
    return [str(path)]


def load_items(corpus=CORPUS, path=HINTS_TOML) -> list[dict]:
    """The live positives, each with the skill its rule cites. Mined items and negatives stay out."""
    rules = {r.id: r for r in load_rules(path)}
    items = []
    for ln in Path(corpus).read_text().splitlines():
        if not ln.strip():
            continue
        it = json.loads(ln)
        if it["source"] != "live" or it["rule"] == "none":
            continue
        items.append({**it, "skill": rules[it["rule"]].skill})
    return items
