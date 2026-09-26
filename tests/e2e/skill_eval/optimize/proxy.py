"""The routing proxy: one scorer call per prompt, one skill name or `none` back (spec 128 FR-004).

The scorer sees the whole menu, every skill's name and (candidate) description, and the prompt. An
exact match to any gold name scores 1, anything else 0. Two failed attempts, whether the call raised
or the answer did not parse, leave the item unscored with a reason; spec 118 keeps it out of every
rate, and `scoring.UNSCORED_LIMIT` decides whether the run counts at all.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from tests.e2e.skill_eval.optimize.ledger import BudgetExceeded
from tests.e2e.skill_eval.optimize.menu import render_menu

ATTEMPTS = 2
MAX_TOKENS = 60

_SYSTEM = """You route requests for an AI coding agent that works on InterSystems IRIS.
The agent can load one skill before it starts. Here are the skills, as name: description.

{menu}

Pick the one skill whose description says it should be used for the request below. If no skill fits, pick none.
Answer with JSON only, exactly {{"skill": "<name>"}} or {{"skill": "none"}}."""


@dataclass(frozen=True)
class Routed:
    id: str
    scored: bool
    pick: str | None
    correct: bool | None
    model: str
    reason: str = ""


def build_messages(menu: str, prompt: str) -> tuple[str, str]:
    return _SYSTEM.format(menu=menu), f"Request:\n{prompt}"


def parse_pick(text: str, names) -> str:
    m = re.search(r"\{[^{}]*\}", text)
    if not m:
        raise ValueError(f"unparseable answer {text[:80]!r}")
    try:
        pick = json.loads(m.group(0))["skill"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ValueError(f"unparseable answer {text[:80]!r}") from e
    if pick != "none" and pick not in names:
        raise ValueError(f"answer names no skill on the menu: {pick!r}")
    return pick


def route(client, model: str, menu: str, item: dict, names, ledger) -> Routed:
    system, user = build_messages(menu, item["prompt"])
    reasons = []
    resolved = ""
    for _ in range(ATTEMPTS):
        ledger.check()
        try:
            msg = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except BudgetExceeded:
            raise
        except Exception as e:  # the SDK raises many types; each is one failed attempt
            reasons.append(f"{type(e).__name__}: {e}"[:160])
            continue
        resolved = getattr(msg, "model", "") or model
        ledger.record(
            "score", resolved, msg.usage.input_tokens, msg.usage.output_tokens
        )
        text = "".join(getattr(b, "text", "") for b in msg.content)
        try:
            pick = parse_pick(text, names)
        except ValueError as e:
            reasons.append(str(e))
            continue
        return Routed(item["id"], True, pick, pick in item["gold"], resolved)
    return Routed(item["id"], False, None, None, resolved, "; ".join(reasons))


def score_items(
    items, skills, descriptions, client, model, ledger, *, workers: int = 8
) -> list[Routed]:
    """Route every item against the menu built from `descriptions` over the shipped ones."""
    menu = render_menu(skills, descriptions)
    names = {s.name for s in skills}
    if workers <= 1:
        return [route(client, model, menu, it, names, ledger) for it in items]
    with ThreadPoolExecutor(workers) as pool:
        return list(
            pool.map(lambda it: route(client, model, menu, it, names, ledger), items)
        )
