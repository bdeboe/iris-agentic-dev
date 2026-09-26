"""The nightly drift step — 128 T031 (FR-012).

The nightly re-scores the shipped descriptions and runs no optimiser. The band it compares against
is committed, so a clean checkout can run it.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from tests.e2e.skill_eval.optimize import runner

WORKFLOW = Path(runner.menu.REPO) / ".github" / "workflows" / "skill-regression.yml"


def _runs() -> str:
    wf = yaml.safe_load(WORKFLOW.read_text())
    return "\n".join(
        s.get("run", "") for job in wf["jobs"].values() for s in job["steps"]
    )


def test_nightly_runs_drift_and_no_optimiser():
    runs = _runs()
    assert "python -m tests.e2e.skill_eval.optimize drift" in runs
    assert "optimize run" not in runs and "optimize apply" not in runs


def test_nightly_installs_the_pinned_requirements():
    assert "tests/e2e/skill_eval/optimize/requirements.txt" in _runs()


def test_drift_band_is_committed_and_well_formed():
    band = json.loads(runner.DRIFT_FILE.read_text())
    assert 0.0 <= band["recall_lo"] <= band["recall"] <= band["recall_hi"] <= 1.0
    assert band["n"] >= 30 and band["scorer_models"]
