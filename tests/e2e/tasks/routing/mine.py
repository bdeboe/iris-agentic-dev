"""Mine routing prompts from sources that already exist (spec 128 FR-001).

Run from the repo root: `python tests/e2e/tasks/routing/mine.py > tests/e2e/tasks/routing/mined.jsonl`.
Issue titles come from `issues.json`, a snapshot of `gh issue list --state all --json number,title`
taken when the corpus was built, so a rerun gives the same output without network access.

Nothing here is labelled. Labels are assigned blind in a separate pass (FR-002).
"""

import glob
import hashlib
import json
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS = os.path.dirname(HERE)
MAX_CHARS = 300


def _first_paragraph(text: str) -> str:
    first = text.strip().split("\n\n")[0].replace("\n", " ")
    return " ".join(first.split())[:MAX_CHARS]


def _item(source: str, prompt: str) -> dict:
    digest = hashlib.sha256(prompt.encode()).hexdigest()[:10]
    return {"id": f"r-{digest}", "prompt": prompt, "source": source}


def mine() -> list[dict]:
    items = []
    for path in sorted(glob.glob(os.path.join(TASKS, "**", "*.yaml"), recursive=True)):
        rel = os.path.relpath(path, TASKS)
        if rel.startswith("routing"):
            continue
        try:
            doc = yaml.safe_load(open(path))
        except yaml.YAMLError:
            continue
        if not isinstance(doc, dict):
            continue
        if os.path.basename(path) == "eval.yaml":
            for key in ("fire_rate_prompt", "implicit_fire_rate_prompt"):
                if isinstance(doc.get(key), str):
                    items.append(_item(f"eval:{rel}:{key}", _first_paragraph(doc[key])))
            continue
        prompt = doc.get("prompt") or doc.get("task")
        if isinstance(prompt, str) and prompt.strip():
            items.append(_item(f"task:{rel}", _first_paragraph(prompt)))
    for issue in json.load(open(os.path.join(HERE, "issues.json"))):
        items.append(_item(f"issue:{issue['number']}", issue["title"].strip()))

    seen, out = set(), []
    for it in items:
        if it["id"] not in seen:
            seen.add(it["id"])
            out.append(it)
    return out


if __name__ == "__main__":
    for it in mine():
        sys.stdout.write(json.dumps(it, ensure_ascii=False) + "\n")
