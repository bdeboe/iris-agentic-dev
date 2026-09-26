# Implementation plan: 129 tool-result hints

**Spec**: [spec.md](spec.md) · **Research**: [research.md](research.md)

## Shape

- `crates/iris-agentic-dev-core/src/tools/hints.toml`: one `[[rule]]` per rule with `id`, `skill`, `section`, `why`, `text`. Compiled in with `include_str!` and parsed once in a `OnceLock`. Its `text` is the only thing the loop rewrites.
- `crates/iris-agentic-dev-core/src/tools/error_hints.rs`: the matchers. Each returns a rule id and the placeholder values; `Hint::render` fills the template. Public API:
  - `sql_error_hint(msg, query, namespace) -> Option<Hint>`
  - `runtime_error_hint(output, namespace) -> Option<Hint>`
  - `Hint::apply(&self, &mut Value)` sets `hint`, and `hint_ref` unless `coding_pack_on()` is false.
  - `rules()`, `matcher_ids()`, `cited_sections()` for the tests.
- `tools/mod.rs`: `sql_err(msg)` becomes `sql_err(msg, query, namespace)` at its four call sites (explain, count, write, read). The three `runtime_error_hint` call sites switch to `Hint::apply`.
- `IAD_CODING_PACK=off|0|false|no` drops `hint_ref`. Read per call.

## Replay corpus

- `tests/e2e/tasks/hints/replay.jsonl`: one JSON object per line with `id`, `tool`, `args`, `namespace`, `captured`, `rule` (or `"none"`), `source` (`live` or `mined`).
- `tests/integration/test_hints_replay_129_live.rs` (`#[ignore]`): runs each live item through `call_for_test`, normalises `IrisDevRun<hash>`, and checks the result still carries the labelled rule. With `IAD_REGEN_HINTS=1` it rewrites the captures.
- `tests/unit/test_hints_replay_129.rs`: runs every item's `captured` error through the matchers offline.

## Loop surface (`--surface hints`)

New modules under `tests/e2e/skill_eval/optimize/`: `hints_surface.py` (load, validate, apply `hints.toml`), `hints_proxy.py` (scorer prompt, answer parser, the live pass checker), `hints_adapter.py` (gepa adapter; `adapter.run_loop` drives it), `hints_runner.py` (split, holdout scoring, gates, report). `surfaces.py` gains a `hints` entry and `__main__.py` accepts `--surface hints`. The checker runs `iris_execute` through the `iris-agentic-dev tool` CLI, so a run needs the binary (`IAD_BINARY` or `target/debug`) and `IRIS_*` for iris-dev-iris.

- Scorer: Haiku sees the tool, arguments, error, hint and the skill menu, and answers `{"skill": ..., "fix": {"query" | "code": ..., "namespace": ...}}`.
- Reach = pick equals `hint_ref.skill`. Pass = the fix prepares cleanly (SQL, `%SQL.Statement.%Prepare` through `iris_execute`) or runs cleanly (runtime, only with no write verb). Score = mean.
- Split: sha256 of the item id, mod 100, below 60 is train; frozen in `tests/e2e/tasks/hints/hints-split.toml` (the 128 format, rendered by `holdout.render_split`). Only live positives are in it: 16 train, 10 holdout. `nonstandard_insert` has no holdout item, so a change to its text is judged only by the rules it does not touch.
- Gates: paired score difference lower bound above 0; reach not down; pass not down; ladder within 0.05, missing ladder is HOLD.

## Skill edits

- objectscript-sql-patterns §7: a WRONG/CORRECT pair for double quotes (-29) that the `double_quoted_string` rule cites.
- iris-agentic-dev, "`<CLASS DOES NOT EXIST>` for a system class": one sentence that their SQL tables fail the same way with SQLCODE -30.

## Tests by layer

1. Unit: each rule on its live capture, negatives, `hint_ref` fields, pack-off drop, no skill name in any text, TOML rows = matchers, cited sections exist, the replay fixture.
2. Binary: spawn `iris-agentic-dev` with `IAD_CODING_PACK=off` and check `tools/list` still works and the env var is honoured in a live call (`#[ignore]`).
3. Live: each rule through `call_for_test` against `iris-dev-iris`, plus the regeneration test.
4. Python: offline tests for surface load/apply, validator, adapter, gates, CLI wiring.
