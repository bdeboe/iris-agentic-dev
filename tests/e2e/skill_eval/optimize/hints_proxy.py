"""The hints proxy: can an agent that reads the hint pick the right skill and fix the call? (129 FR-010)

The scorer sees the failed call, the error IRIS gave and the rendered hint, plus the skill menu. It
never sees `hint_ref` or the skill the rule cites. It answers with one skill (or `none`) and a fix:
a `query` or ObjectScript `code`, with a namespace.

reach  the pick equals the skill the rule cites
pass   the fix works on live IRIS, judged by `Checker`
score  (reach + pass) / 2

`Checker` prepares SQL, never executes it, and runs ObjectScript only when no write verb appears in
it; a fix with one counts as a fail without running. A transport failure, or two scorer attempts
that raise or do not parse, leave the item unscored with a reason (spec 118).
"""

from __future__ import annotations

import json
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from tests.e2e.skill_eval.optimize.hints_surface import render
from tests.e2e.skill_eval.optimize.ledger import BudgetExceeded
from tests.e2e.skill_eval.optimize.menu import render_menu

ATTEMPTS = 2
MAX_TOKENS = 300
RUN_TIMEOUT_S = 60

_SYSTEM = """You are an AI coding agent working on InterSystems IRIS through iad tools. One of your tool calls just failed.
Before you retry you can load one skill. Here are the skills, as name: description.

{menu}

Read the call, the error and the hint. Pick the one skill that documents this error, or none if no
skill does, and write the corrected call. Answer with JSON only:
{{"skill": "<name or none>", "fix": {{"query": "<SQL>"}} or {{"code": "<ObjectScript>"}}, "namespace": "<namespace>"}}
Use "query" when the failed call was iris_query and "code" when it was iris_execute."""


def build_messages(menu: str, item: dict, hint_text: str) -> tuple[str, str]:
    user = "\n".join(
        [
            f"Item: {item['id']}",
            f"tool: {item['tool']}",
            f"args: {json.dumps(item['args'], sort_keys=True)}",
            f"error: {item['captured']}",
            f"hint: {hint_text}",
        ]
    )
    return _SYSTEM.format(menu=menu), user


def parse_answer(text: str, names, default_namespace: str | None = None):
    """Return `(skill, fix)`, where fix is `{"query"|"code": str, "namespace": str}`."""
    start = text.find("{")
    if start < 0:
        raise ValueError(f"unparseable answer {text[:80]!r}")
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as e:
        raise ValueError(f"unparseable answer {text[:80]!r}") from e
    if not isinstance(obj, dict):
        raise ValueError(f"answer is not an object: {text[:80]!r}")
    skill = obj.get("skill")
    if skill != "none" and skill not in names:
        raise ValueError(f"answer names no skill on the menu: {skill!r}")
    fix = obj.get("fix")
    if not isinstance(fix, dict):
        raise ValueError("answer has no fix object")
    kinds = [k for k in ("query", "code") if k in fix]
    if len(kinds) != 1 or not isinstance(fix[kinds[0]], str) or not fix[kinds[0]]:
        raise ValueError(f"fix needs one non-empty query or code string: {fix!r}")
    ns = fix.get("namespace") or obj.get("namespace") or default_namespace
    if not isinstance(ns, str) or not ns:
        raise ValueError("answer has no namespace")
    return skill, {kinds[0]: fix[kinds[0]], "namespace": ns}


# A write anywhere in a runtime fix means it is never run. `^` covers globals and routine calls;
# the rest are the commands and methods that change or delete state, or run arbitrary code.
_WRITE = re.compile(
    r"\^"
    r"|(?:^|[\s{])(?:k|kill|x|xecute|j|job|zn|znspace)(?=[\s:]|$)"
    r"|%Save|%Delete|\bDelete\w*|\bCreate\w*|\bModify\w*"
    r"|Python|Exec"
    r"|\$ZF\b|\$ZU\b",
    re.I | re.M,
)


def has_write_verb(code: str) -> bool:
    return bool(_WRITE.search(code))


def prepare_code(query: str) -> str:
    q = " ".join(query.splitlines()).replace('"', '""')
    return (
        f'Set st=##class(%SQL.Statement).%New() Set sc=st.%Prepare("{q}") '
        'If $$$ISERR(sc) { Write "PREPARE_FAILED:",$System.Status.GetErrorText(sc) } '
        'Else { Write "PREPARED" }'
    )


class Checker:
    """`fix -> True | False | None`, cached by fix. `runner(code, namespace)` returns iad's JSON."""

    def __init__(self, runner):
        self.runner = runner
        self._cache: dict = {}
        self._lock = threading.Lock()

    def __call__(self, fix: dict):
        key = json.dumps(fix, sort_keys=True)
        with self._lock:
            if key in self._cache:
                return self._cache[key]
        got = self._check(fix)
        with self._lock:
            self._cache[key] = got
        return got

    def _check(self, fix):
        ns = fix.get("namespace") or "USER"
        if "query" in fix:
            code, sql = prepare_code(fix["query"]), True
        else:
            code, sql = fix["code"], False
            if has_write_verb(code):
                return False
        ans = self.runner(code, ns)
        if not isinstance(ans, dict):
            return None
        if ans.get("success") is True:
            out = str(ans.get("output", ""))
            return ("PREPARED" in out and "PREPARE_FAILED" not in out) if sql else True
        if ans.get("error_code") == "IRIS_RUNTIME_ERROR":
            return False
        return None


class IadRunner:
    """Runs `iris_execute` through `iris-agentic-dev tool`, with IRIS_* taken from the environment."""

    def __init__(self, binary: str, env: dict | None = None):
        self.binary = binary
        self.env = env

    def __call__(self, code: str, namespace: str):
        args = json.dumps({"code": code, "namespace": namespace})
        try:
            p = subprocess.run(
                [self.binary, "tool", "iris_execute", "-a", args],
                capture_output=True,
                text=True,
                timeout=RUN_TIMEOUT_S,
                env=self.env,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        for ln in reversed(p.stdout.strip().splitlines()):
            try:
                return json.loads(ln)
            except json.JSONDecodeError:
                continue
        return None


@dataclass(frozen=True)
class Scored:
    id: str
    scored: bool
    pick: str | None
    reach: bool | None
    passed: bool | None
    score: float | None
    model: str
    reason: str = ""
    fix: dict = field(default_factory=dict)


def score_item(client, model, menu, item, hint, names, ledger, checker) -> Scored:
    system, user = build_messages(menu, item, hint)
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
            pick, fix = parse_answer(text, names, item.get("namespace"))
        except ValueError as e:
            reasons.append(str(e))
            continue
        passed = checker(fix)
        if passed is None:
            return Scored(
                item["id"],
                False,
                pick,
                None,
                None,
                None,
                resolved,
                "checker: IRIS gave no usable answer",
                fix,
            )
        reach = pick == item["skill"]
        return Scored(
            item["id"],
            True,
            pick,
            reach,
            passed,
            (reach + passed) / 2,
            resolved,
            "",
            fix,
        )
    return Scored(
        item["id"], False, None, None, None, None, resolved, "; ".join(reasons)
    )


def score_items(
    items, skills, candidate, client, model, ledger, checker, *, workers: int = 8
) -> list[Scored]:
    """Score every item with its hint rendered from `candidate[rule]` and the item's own values."""
    menu = render_menu(skills)
    names = {s.name for s in skills}

    def one(it):
        hint = render(candidate[it["rule"]], it.get("vars", {}))
        return score_item(client, model, menu, it, hint, names, ledger, checker)

    if workers <= 1:
        return [one(it) for it in items]
    with ThreadPoolExecutor(workers) as pool:
        return list(pool.map(one, items))
