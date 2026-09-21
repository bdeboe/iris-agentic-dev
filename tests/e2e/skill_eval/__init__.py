"""Skill regression and lift measurement suite (040), and the graded benchmark harness (121).

This package used to begin by inserting `benchmark/021` into `sys.path` so that
`from runner.judge import score_result` would work. Spec 121 T043/T044 retired that tree and moved
the two modules anyone actually imported — the scorer's Anthropic client and the judge — in here as
`scorer_client` and `judge`. Import them by name.

The shim is worth one sentence of warning rather than silent deletion: an import that only resolves
because a package's `__init__` mutated `sys.path` works everywhere until someone runs a single file
directly, and then fails with a `ModuleNotFoundError` naming a module that is right there on disk.
"""
