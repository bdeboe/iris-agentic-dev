"""The candidate validator (spec 128 FR-006) and the shipped-description check (FR-011).

One function for both. A candidate must carry `USE FOR:` and `DO NOT USE FOR:`; the 38 descriptions
shipped before 128 do not, so CI calls it with `require_markers=False`.

"No new facts" is checked on identifier-like tokens, the things an agent would act on literally: a
backticked span, a `%Class`, a `$Function`, a `#NNNN` error code, an `<ERROR>`, an iad tool name. Any
such token in the candidate must already appear in the skill body or its seed description. Prose
paraphrase is free; a new identifier is a claim the loop was never allowed to make.
"""

from __future__ import annotations

import re

MAX_CHARS = 1024

_PATTERNS = (
    re.compile(r"`([^`\n]+)`"),
    re.compile(r"(?<![\w%])(%[A-Za-z][\w.]*[A-Za-z0-9])"),
    re.compile(r"(?<![\w$])(\$\$?\$?[A-Za-z]\w*)"),
    re.compile(r"(?<![\w#])(#\d{3,5})\b"),
    re.compile(r"(<[A-Z][A-Z0-9 ]*>)"),
    re.compile(
        r"\b((?:iris|skill|kb|docs|global|agent|telemetry|mermaid|journal|compare|check"
        r"|capability|my|query|resolve|stream|find|extract|hl7)_[a-z_]*[a-z])\b"
    ),
)
# `$` functions are case-insensitive in ObjectScript: `$LISTBUILD` is `$ListBuild`.
_CASE_FOLDED = 2


def _fact_map(text: str) -> dict[str, str]:
    """Normalised token -> the spelling it first had in `text`."""
    out: dict[str, str] = {}
    for i, pat in enumerate(_PATTERNS):
        for m in pat.finditer(text):
            tok = m.group(1).strip()
            out.setdefault(tok.lower() if i == _CASE_FOLDED else tok, tok)
    return out


def facts(text: str) -> set[str]:
    return set(_fact_map(text))


def validate(text: str, *, body: str, seed: str, require_markers: bool) -> list[str]:
    """Return the reasons `text` is rejected; empty means it passes."""
    reasons = []
    if not text.strip():
        return ["description is empty"]
    if len(text) > MAX_CHARS:
        reasons.append(f"{len(text)} characters, over the {MAX_CHARS} cap (1024)")
    if require_markers:
        if not re.search(r"(?<!NOT )USE FOR:", text):
            reasons.append("missing USE FOR:")
        if "DO NOT USE FOR:" not in text:
            reasons.append("missing DO NOT USE FOR:")
    known = facts(body) | facts(seed)
    found = _fact_map(text)
    for key in sorted(set(found) - known):
        reasons.append(
            f"new fact {found[key]!r} is in neither the body nor the seed description"
        )
    return reasons
