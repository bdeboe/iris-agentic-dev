"""gepa adapter for routing surfaces (spec 128 FR-005–FR-008).

The candidate is `{skill name: description}`. `evaluate` routes each prompt through the proxy with
the candidate's menu. `make_reflective_dataset` collects, for the component being changed, the
prompts it missed and the ones it took from another skill. `propose_new_texts` asks the reflection
model for a new description and runs the validator on it; a rejected text is logged and the method
returns `{}`, which gepa 0.1.4 treats as "no proposal" and never scores.

Holdout ids never get here: `evaluate` refuses any item the frozen split puts on the holdout side.
"""

from __future__ import annotations

import hashlib
import re
import time
from collections import Counter

from gepa import EvaluationBatch
from gepa import optimize as gepa_optimize

from tests.e2e.skill_eval.optimize import holdout, validator
from tests.e2e.skill_eval.optimize.ledger import BudgetExceeded
from tests.e2e.skill_eval.optimize.proxy import score_items

VAL_PERCENT = 35
MINIBATCH = 10
BODY_CHARS = 6000

REFLECT_PROMPT = """You are improving the one-paragraph description an AI coding agent reads when it picks a skill.
The agent sees every skill's name and description and loads the one whose description fits the request.

Skill: {name}
Current description:
{current}

The skill's content (truncated):
{body}

Requests this description handled badly:
{examples}

Write a new description for {name}. Rules:
- 900 characters or fewer (the hard cap is 1024; leave room).
- Contain the literal markers "USE FOR:" and "DO NOT USE FOR:".
- Describe only what the content above covers. Do not name any class, function, tool, error code or
  backticked term that does not already appear in the content or the current description.
- Say plainly which requests belong to this skill and which belong elsewhere.

Reply with the new description only, between <description> and </description>."""

RETRY_PROMPT = """{prompt}

Your previous draft was rejected:
{draft}

Reasons:
{reasons}

Fix every reason and reply again, between <description> and </description>."""
# One retry per proposal: most rejections are a draft a few characters over the cap.
PROPOSE_ATTEMPTS = 2


def _val(item_id: str) -> bool:
    return (
        int(hashlib.sha256(f"val:{item_id}".encode()).hexdigest(), 16) % 100
        < VAL_PERCENT
    )


class RoutingAdapter:
    propose_new_texts = None  # replaced per instance; gepa checks the attribute

    def __init__(
        self,
        skills,
        client,
        model,
        ledger,
        *,
        reflect,
        split,
        workers: int = 8,
        editable=None,
    ):
        self.skills = skills
        # None: every skill may change (128). A set: the rest are scored but never proposed for.
        self.editable = None if editable is None else frozenset(editable)
        self.by_name = {s.name: s for s in skills}
        self.seed = {s.name: s.description for s in skills}
        self.client = client
        self.model = model
        self.ledger = ledger
        self.reflect = reflect
        self.split = split
        self.workers = workers
        self.rejections: list[dict] = []
        self.proposals: list[dict] = []
        self.propose_new_texts = self._propose
        self.val_ids: frozenset = frozenset()
        self.best_val = (-1.0, dict(self.seed))

    # gepa: evaluate --------------------------------------------------------------------------
    def evaluate(self, batch, candidate, capture_traces: bool = False):
        batch = holdout.train_only(batch, self.split)
        routed = score_items(
            batch,
            self.skills,
            candidate,
            self.client,
            self.model,
            self.ledger,
            workers=self.workers,
        )
        scores = [1.0 if r.correct else 0.0 for r in routed]
        if self.val_ids and {i["id"] for i in batch} == self.val_ids:
            mean = sum(scores) / len(scores)
            if mean > self.best_val[0]:
                self.best_val = (mean, dict(candidate))
        traj = [
            {
                "id": it["id"],
                "prompt": it["prompt"],
                "gold": it["gold"],
                "pick": r.pick,
                "scored": r.scored,
                "reason": r.reason,
            }
            for it, r in zip(batch, routed)
        ]
        return EvaluationBatch(
            outputs=traj, scores=scores, trajectories=traj if capture_traces else None
        )

    # gepa: reflective dataset ----------------------------------------------------------------
    def make_reflective_dataset(self, candidate, eval_batch, components_to_update):
        out = {}
        for name in components_to_update:
            rows = []
            for t in eval_batch.trajectories or []:
                if not t["scored"]:
                    continue
                if name in t["gold"] and t["pick"] not in t["gold"]:
                    rows.append(
                        {
                            "kind": "miss",
                            "prompt": t["prompt"],
                            "gold": t["gold"],
                            "pick": t["pick"],
                        }
                    )
                elif t["pick"] == name and name not in t["gold"]:
                    rows.append(
                        {
                            "kind": "steal",
                            "prompt": t["prompt"],
                            "gold": t["gold"],
                            "pick": t["pick"],
                        }
                    )
            out[name] = rows
        return out

    def select_component(
        self, state, trajectories, subsample_scores, candidate_idx, candidate
    ):
        """The editable skill most involved in this minibatch's errors; ties broken by name."""
        pool = sorted(
            n for n in candidate if self.editable is None or n in self.editable
        )
        blame = Counter()
        for t in trajectories:
            if not t["scored"] or t["pick"] in t["gold"]:
                continue
            for g in t["gold"]:
                if g in pool:
                    blame[g] += 1
            if t["pick"] in pool:
                blame[t["pick"]] += 1
        if blame:
            top = max(blame.values())
            return [sorted(n for n, c in blame.items() if c == top)[0]]
        return [pool[state.i % len(pool)]]

    # gepa: proposal --------------------------------------------------------------------------
    def _propose(self, candidate, reflective_dataset, components_to_update):
        out = {}
        for name in components_to_update:
            if self.editable is not None and name not in self.editable:
                continue
            rows = reflective_dataset.get(name) or []
            if not rows:
                continue
            skill = self.by_name[name]
            examples = "\n".join(
                f"- [{r['kind']}] {r['prompt'][:300]!r} -> should be {', '.join(r['gold'])}, agent picked {r['pick']}"
                for r in rows[:12]
            )
            prompt = REFLECT_PROMPT.format(
                name=name,
                current=candidate[name],
                body=skill.body[:BODY_CHARS],
                examples=examples,
            )
            ask = prompt
            for _ in range(PROPOSE_ATTEMPTS):
                reply = self.reflect(ask)
                m = re.search(r"<description>(.*?)</description>", reply, re.S)
                text = " ".join((m.group(1) if m else reply).split())
                reasons = validator.validate(
                    text, body=skill.body, seed=self.seed[name], require_markers=True
                )
                if not reasons:
                    self.proposals.append({"skill": name, "text": text})
                    out[name] = text
                    break
                self.rejections.append(
                    {"skill": name, "text": text, "reasons": reasons}
                )
                ask = RETRY_PROMPT.format(
                    prompt=prompt,
                    draft=text,
                    reasons="\n".join(f"- {r}" for r in reasons),
                )
        return out


def split_train(items):
    """Deterministic gepa train/val partition of the train side only."""
    tr = [i for i in items if not _val(i["id"])]
    va = [i for i in items if _val(i["id"])]
    return tr, va


def run_loop(
    adapter,
    train_items,
    *,
    max_metric_calls: int,
    seed: int = 128,
    reserve_usd: float = 0.0,
    max_seconds: float | None = None,
):
    """Run gepa over train items. Returns (best candidate, info). Never touches the holdout."""
    tr, va = split_train(holdout.train_only(train_items, adapter.split))
    adapter.val_ids = frozenset(i["id"] for i in va)
    ledger = adapter.ledger
    stopped = {"why": "done"}

    deadline = None if max_seconds is None else time.monotonic() + max_seconds

    def budget_stop(_state):
        if ledger.total_usd >= ledger.budget_usd - reserve_usd:
            stopped["why"] = "budget"
            return True
        if deadline is not None and time.monotonic() >= deadline:
            stopped["why"] = "time"
            return True
        return False

    try:
        result = gepa_optimize(
            seed_candidate=dict(adapter.seed),
            trainset=tr,
            valset=va,
            adapter=adapter,
            reflection_lm=lambda _p: "",  # unused: the adapter proposes
            module_selector=adapter.select_component,
            reflection_minibatch_size=min(MINIBATCH, len(tr)),
            max_metric_calls=max_metric_calls,
            stop_callbacks=[budget_stop],
            seed=seed,
            display_progress_bar=False,
            raise_on_exception=True,
        )
        best = dict(result.best_candidate)
        info = {
            "val_scores": list(result.val_aggregate_scores),
            "n_candidates": len(result.candidates),
        }
        if (
            stopped["why"] == "done"
            and result.total_metric_calls
            and result.total_metric_calls >= max_metric_calls
        ):
            stopped["why"] = "max_metric_calls"
    except BudgetExceeded:
        stopped["why"] = "budget"
        best = adapter.best_val[1]  # best full-val candidate scored before the cap hit
        info = {}
    except KeyboardInterrupt:
        # SIGINT, or SIGTERM mapped to it by the CLI: keep what the loop found and let the caller
        # still judge it on the holdout.
        stopped["why"] = "interrupted"
        best = adapter.best_val[1]
        info = {}
    info.update(
        stopped=stopped["why"],
        train_n=len(tr),
        val_n=len(va),
        proposals=adapter.proposals,
        rejections=adapter.rejections,
        spend_usd=ledger.total_usd,
    )
    return best, info
