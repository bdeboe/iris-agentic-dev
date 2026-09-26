"""`optimize apply <run>`: write a SHIP candidate's texts into the working tree (FR-010).

Refuses anything but SHIP. Tom reviews the diff and commits; nothing here commits.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.e2e.skill_eval.optimize.gate import SHIP
from tests.e2e.skill_eval.optimize.surfaces import SURFACES


class NotShippable(RuntimeError):
    pass


def apply_run(run_dir, **where) -> list[str]:
    """`where` goes to the surface's writer: `root=` for skills, `path=` for `hints.toml`."""
    c = json.loads((Path(run_dir) / "candidate.json").read_text())
    if c.get("verdict") != SHIP:
        raise NotShippable(
            f"run {c.get('run_id')} verdict is {c.get('verdict')}; failed gates: {c.get('failed')}"
        )
    return SURFACES[c["surface"]].apply(c["descriptions"], **where)
