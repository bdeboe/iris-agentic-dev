"""The spend ledger and its hard cap (spec 128 FR-008).

Every scorer and reflection call is recorded with the model the response reported, its tokens and
its cost. Rates come from `cost_estimator.SCORER_RATES`, which records where each price was checked.
A model with no rate raises `Unpriced`: a budget computed from a guessed price is not a cap.

`check()` before a call refuses once the cap is reached; `record()` after a call raises when that call
crossed it. So a run overshoots by at most the calls in flight (SC-002; one per worker).

Sonnet 5 is $2 / MTok input and $10 / MTok output, confirmed 2026-09-26 against
https://platform.claude.com/docs/en/about-claude/pricing § Model pricing (footnote 3: the launch
price became the standard price; the planned rise to $3/$15 did not happen). Bedrock `us.` endpoints
are regional and carry a 10% premium over global, which `multiplier=1.1` prices in.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from tests.e2e.skill_eval import cost_estimator

SONNET_5_RATES = {"claude-sonnet-5": (2.00, 10.00)}


class BudgetExceeded(RuntimeError):
    pass


class Unpriced(RuntimeError):
    pass


class Ledger:
    def __init__(
        self,
        budget_usd: float,
        extra_rates: dict | None = None,
        multiplier: float = 1.0,
        stream_path=None,
    ):
        self.budget_usd = budget_usd
        # Appended per call, so spend survives a killed run and can be tailed while it runs.
        self.stream_path = Path(stream_path) if stream_path else None
        self.multiplier = multiplier
        self.rates = {
            **cost_estimator.SCORER_RATES,
            **SONNET_5_RATES,
            **(extra_rates or {}),
        }
        self._lock = threading.Lock()
        self.entries: list[dict] = []
        self.total_usd = 0.0

    def _rate(self, model: str):
        for key in sorted(self.rates, key=len, reverse=True):
            if model and (model.startswith(key) or key in model):
                return self.rates[key]
        raise Unpriced(
            f"no verified rate for {model!r}; add one with its source before spending"
        )

    def check(self) -> None:
        if self.total_usd >= self.budget_usd:
            raise BudgetExceeded(
                f"spent ${self.total_usd:.4f} of ${self.budget_usd:.2f}"
            )

    def record(
        self, kind: str, model: str, input_tokens: int, output_tokens: int
    ) -> dict:
        rin, rout = self._rate(model)
        cost = (input_tokens * rin + output_tokens * rout) / 1_000_000 * self.multiplier
        with self._lock:
            self.total_usd += cost
            entry = {
                "kind": kind,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": round(cost, 8),
                "total_usd": round(self.total_usd, 8),
            }
            self.entries.append(entry)
            if self.stream_path:
                with self.stream_path.open("a") as f:
                    f.write(json.dumps(entry) + "\n")
        self.check()
        return entry

    def write(self, path) -> None:
        if self.stream_path and Path(path).resolve() == self.stream_path.resolve():
            return  # already on disk, entry by entry
        Path(path).write_text("".join(json.dumps(e) + "\n" for e in self.entries))
