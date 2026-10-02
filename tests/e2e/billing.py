"""The opt-in that stands between `pytest` and a bill.

Every agent session in this tree costs money — about $0.085 of it — and the only thing that used to stop
`pytest tests/e2e/skill_eval` from spending forty dollars was whoever ran it remembering not to. The
alternative fix, a written list of files that are safe to collect, is worse: a file declared safe that
later grows a live test bills real money on the next nightly, and nothing tells anyone it happened.

So the refusal lives at the spawn point instead. `run_opencode` and `PrimeAgentDriver.collect_events`
both call `assert_allowed` before `Popen`, and it raises unless something explicitly asked for a session
by setting `IAD_BILLABLE_SESSIONS=1`. The four CLI entry points that exist to spend money — the ladder,
the pilot, the nightly canary, and `python -m tests.e2e.skill_eval` — ask for it with `allow()`. Nothing
else does, which is the point: a test file that grows a live session starts failing rather than billing.

A test that deliberately runs a real session sets the variable itself, and says so where it sets it.

`spend_cap()` bounds a block by measured cost. `collect_events` charges each session's own
`step_finish.cost` to it, and `assert_allowed` refuses the next session once the total reaches the
cap. The session that crosses the cap runs to its end; it was already billed.
"""

from __future__ import annotations

import contextlib
import os
import sys

#: Set to `1` for the duration of a command that is supposed to spend money.
BILLABLE_ENV = "IAD_BILLABLE_SESSIONS"


class BillingRefused(Exception):
    """A session was about to start that nothing had asked for."""


class SpendCapReached(BillingRefused):
    """A session was about to start after measured spend had reached the cap."""


class _Meter:
    def __init__(self, cap: float | None):
        self.cap = cap
        self.spent = 0.0


_meter: _Meter | None = None


def current_spend() -> float | None:
    """Dollars measured so far inside the open `spend_cap` block, or None outside one."""
    return _meter.spent if _meter is not None else None


def charge(events) -> float:
    """Add one finished session's measured cost to the open block. Returns that session's cost."""
    from tests.e2e.skill_eval.cost_estimator import session_cost

    cost = session_cost(events)
    if _meter is not None:
        _meter.spent += cost
        cap = f" of cap ${_meter.cap:.2f}" if _meter.cap is not None else ""
        print(
            f"    session ${cost:.2f}, total ${_meter.spent:.2f}{cap}",
            file=sys.stderr,
            flush=True,
        )
    return cost


@contextlib.contextmanager
def spend_cap(cap: float | None):
    """Count every session's measured cost for the block; with a cap, stop sessions at it."""
    global _meter
    previous = _meter
    _meter = _Meter(cap)
    try:
        yield _meter
    finally:
        _meter = previous


def allowed() -> bool:
    """Whether a billable session may start. Exactly `1` — no truthiness, no `yes`, no `true`.

    One spelling, because a gate that accepts four spellings is a gate somebody's stale `=0` walks
    through.
    """
    return os.environ.get(BILLABLE_ENV) == "1"


def assert_allowed(what: str) -> None:
    """Raise unless something asked for a billable session. `what` is named in the message."""
    if allowed():
        if _meter is not None and _meter.cap is not None and _meter.spent >= _meter.cap:
            raise SpendCapReached(
                f"refusing to start {what}: ${_meter.spent:.2f} measured, cap ${_meter.cap:.2f}"
            )
        return
    raise BillingRefused(
        f"refusing to start {what}: nothing asked for a billable agent session. "
        f"Set {BILLABLE_ENV}=1 if that is what you want — the ladder, pilot, canary and "
        "`python -m tests.e2e.skill_eval` commands set it themselves. If this came out of a pytest "
        "run, the file you collected spawns real sessions and the gate just saved you the money."
    )


@contextlib.contextmanager
def allow():
    """Permit billable sessions for the duration of the block, then put the environment back."""
    previous = os.environ.get(BILLABLE_ENV)
    os.environ[BILLABLE_ENV] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(BILLABLE_ENV, None)
        else:
            os.environ[BILLABLE_ENV] = previous
