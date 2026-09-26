"""gepa adapter for the `hints` surface (spec 129 FR-008–FR-010).

The candidate is `{rule id: hint template}`. `evaluate` renders each train item's hint from the
candidate and scores it through `hints_proxy`. The reflective dataset for a rule is its items that
missed the skill or whose fix failed. `propose_new_texts` shows the reflection model the cited
section, the current text and its placeholders, validates the reply, and retries once; a rejected
text is logged and never scored. `adapter.run_loop` drives it, so the holdout guard and the budget
stop are the ones 128 already tests.
"""

from __future__ import annotations

import re
from collections import defaultdict

from gepa import EvaluationBatch

from tests.e2e.skill_eval.optimize import hints_surface as hs
from tests.e2e.skill_eval.optimize import holdout
from tests.e2e.skill_eval.optimize.hints_proxy import score_items

SECTION_CHARS = 4000

REFLECT_PROMPT = """You are improving a hint iad adds to an IRIS error. An AI coding agent reads the error and the
hint, decides which skill documents it, and retries the call. A good hint makes the fix obvious.

Rule: {rule}
Current hint template:
{current}

Placeholders it must keep, each exactly once or more: {placeholders}

The section of the documentation the hint points to:
{section}

Calls where an agent reading this hint went wrong:
{examples}

Write a new template. Rules:
- 400 characters or fewer.
- Keep every placeholder above, spelled with its braces; add no others and no other braces.
- Do not name a skill or say "skill"; the reference travels separately.
- State only what the section above or the current template already says. Do not add a class,
  function, error code, tool name or backticked term that is in neither.

Reply with the new template only, between <hint> and </hint>."""

RETRY_PROMPT = """{prompt}

Your previous draft was rejected:
{draft}

Reasons:
{reasons}

Fix every reason and reply again, between <hint> and </hint>."""
PROPOSE_ATTEMPTS = 2


class HintsAdapter:
    propose_new_texts = None  # replaced per instance; gepa checks the attribute

    def __init__(
        self,
        rules,
        skills,
        client,
        model,
        ledger,
        *,
        reflect,
        split,
        checker,
        workers: int = 8,
        contexts: dict | None = None,
    ):
        self.rules = {r.id: r for r in rules}
        self.skills = skills
        self.seed = {r.id: r.text for r in rules}
        self.client = client
        self.model = model
        self.ledger = ledger
        self.reflect = reflect
        self.split = split
        self.checker = checker
        self.workers = workers
        self.contexts = contexts or hs.contexts()
        self.rejections: list[dict] = []
        self.proposals: list[dict] = []
        self.propose_new_texts = self._propose
        self.val_ids: frozenset = frozenset()
        self.best_val = (-1.0, dict(self.seed))

    def evaluate(self, batch, candidate, capture_traces: bool = False):
        batch = holdout.train_only(batch, self.split)
        rows = score_items(
            batch,
            self.skills,
            candidate,
            self.client,
            self.model,
            self.ledger,
            self.checker,
            workers=self.workers,
        )
        scores = [r.score if r.scored else 0.0 for r in rows]
        if self.val_ids and {i["id"] for i in batch} == self.val_ids:
            mean = sum(scores) / len(scores)
            if mean > self.best_val[0]:
                self.best_val = (mean, dict(candidate))
        traj = [
            {
                "id": it["id"],
                "rule": it["rule"],
                "error": it["captured"],
                "hint": hs.render(candidate[it["rule"]], it.get("vars", {})),
                "pick": r.pick,
                "fix": r.fix,
                "reach": r.reach,
                "passed": r.passed,
                "scored": r.scored,
                "score": r.score,
                "reason": r.reason,
            }
            for it, r in zip(batch, rows)
        ]
        return EvaluationBatch(
            outputs=traj, scores=scores, trajectories=traj if capture_traces else None
        )

    def make_reflective_dataset(self, candidate, eval_batch, components_to_update):
        out = {}
        for rid in components_to_update:
            out[rid] = [
                t
                for t in eval_batch.trajectories or []
                if t["rule"] == rid and t["scored"] and not (t["reach"] and t["passed"])
            ]
        return out

    def select_component(
        self, state, trajectories, subsample_scores, candidate_idx, candidate
    ):
        """The rule with the lowest mean score in this minibatch; ties broken by id."""
        by_rule = defaultdict(list)
        for t in trajectories:
            if t["scored"] and t["rule"] in candidate:
                by_rule[t["rule"]].append(t["score"])
        worst = [
            (sum(v) / len(v), rid) for rid, v in by_rule.items() if sum(v) < len(v)
        ]
        if worst:
            return [min(worst)[1]]
        return [sorted(candidate)[state.i % len(candidate)]]

    def _propose(self, candidate, reflective_dataset, components_to_update):
        out = {}
        for rid in components_to_update:
            rows = reflective_dataset.get(rid) or []
            if not rows:
                continue
            ctx = self.contexts[rid]
            examples = "\n".join(
                f"- error {r['error'][:240]!r}\n  hint shown {r['hint'][:240]!r}\n"
                f"  agent picked {r['pick']}, fix {r['fix']} "
                f"({'right' if r['reach'] else 'wrong'} skill, fix "
                f"{'worked' if r['passed'] else 'failed'})"
                for r in rows[:8]
            )
            prompt = REFLECT_PROMPT.format(
                rule=rid,
                current=candidate[rid],
                placeholders=", ".join(
                    "{" + p + "}" for p in sorted(hs.placeholders(self.seed[rid]))
                )
                or "(none)",
                section=ctx["section"][:SECTION_CHARS],
                examples=examples,
            )
            ask = prompt
            for _ in range(PROPOSE_ATTEMPTS):
                reply = self.reflect(ask)
                m = re.search(r"<hint>(.*?)</hint>", reply, re.S)
                text = " ".join((m.group(1) if m else reply).split())
                reasons = hs.validate(text, **ctx)
                if not reasons:
                    self.proposals.append({"rule": rid, "text": text})
                    out[rid] = text
                    break
                self.rejections.append({"rule": rid, "text": text, "reasons": reasons})
                ask = RETRY_PROMPT.format(
                    prompt=prompt,
                    draft=text,
                    reasons="\n".join(f"- {r}" for r in reasons),
                )
        return out
