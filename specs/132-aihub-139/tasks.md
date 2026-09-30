# Tasks: 132 AI Hub on EAP build 139

Tests come first in every phase. A phase is done when its gate passes. Paths under `core/` mean `crates/iris-agentic-dev-core/`.

Live runs use `--features testing -- --include-ignored --test-threads=1` against `iad-aihub-iris` on 52781 (quickstart.md). Every new test file gets its `mod` line in `core/tests/unit/main.rs` or `core/tests/integration/main.rs` in the same task that creates it.

## Phase 1: Setup

- [x] T001 Check the instance per `specs/132-aihub-139/quickstart.md`: `iad-aihub-iris` and `iad-aihub-webgateway` running, `curl -u _SYSTEM:SYS http://localhost:52781/api/atelier/` returns 200, `python -m tools.lab_manager.iris_registry_verify` (run from `~/ws/productivity-framework`) exits 0
- [x] T002 [P] Record the upstream file list: `gh api repos/intersystems-community/ai-hub-eap/git/trees/72749d6dbf0b856a60775378fa88d346bb79d4e4?recursive=1`, blobs only, sorted, header `# ai-hub-eap master 72749d6dbf0b856a60775378fa88d346bb79d4e4 2026-09-09`, written to `core/tests/fixtures/aihub139/upstream-files.txt` (expect 56 paths)

## Phase 2: Foundational (test helpers every story uses)

- [x] T003 Unit tests in `core/tests/unit/test_aihub_139.rs` (new, plus `mod` line): `AihubEnv::from_vars` defaults (`iad-aihub-iris`, `localhost`, 52781, `USER`) and overrides from `IAD_AIHUB_CONTAINER`/`IAD_AIHUB_HOST`/`IAD_AIHUB_WEB_PORT`/`IAD_AIHUB_NAMESPACE`; a non-numeric port is an error naming the variable; the unreachable message names `iad-aihub-iris` and the quickstart start command; `clean_mcp_command` removes `OPENAI_API_KEY` from the child env
- [x] T004 Implement `AihubEnv`, `AihubEnv::from_vars`, `aihub_env() -> Option<AihubEnv>` (probe `GET /api/atelier/` on `host:web_port`; panic with the message unless `IAD_ALLOW_SKIP=1`, then print it and return `None`) and `aihub_session(&AihubEnv) -> McpSession` (spawns through `clean_mcp_command` with `IRIS_HOST`/`IRIS_WEB_PORT`/`IRIS_CONTAINER`/`IRIS_NAMESPACE`) in `core/src/testing.rs`, next to `live_env`
- [x] T005 Gate: `cargo test --features testing --test unit test_aihub_139` passes

## Phase 3: US1 — a 139 instance the tests can reach (P1)

Independent test: the instance reports 2026.3.0AI.139, has `%AI`, and the registry verifier accepts iad's entry.

- [x] T006 [US1] Unit test in `core/tests/unit/test_aihub_139.rs`: `aihub_probe` against `localhost:1` returns an error whose text names `iad-aihub-iris` and how to start it (no IRIS needed)
- [x] T007 [US1] Live tests in `core/tests/integration/test_aihub_139_live.rs` (new, plus `mod` line), all `#[ignore = "live iad-aihub-iris"]`: `aihub_version_is_139` (`iris_info` / `$ZVERSION` contains `2026.3.0AI` and `Build 139`), `aihub_has_ai_package` (`%Dictionary.CompiledClass` count under `%AI.` ≥ 60, read from USER), `aihub_http_path` (`iris_doc` put+compile+delete of a throwaway `IadAihub139.Probe` returns `compiled: true`, `iris_execute` reports `execution_path: atelier`)
- [x] T008 [US1] Split `aihub_probe` out of `aihub_env` in `core/src/testing.rs` so T006 can call it without panicking
- [x] T009 [US1] Gate: T006 passes; T007 passes on 139; with the gateway stopped, T007 panics naming the container and `IAD_ALLOW_SKIP=1` turns it into a skip (record both outputs in `specs/132-aihub-139/research.md` R1); `iris-dev-iris` suite untouched (FR-002)

## Phase 4: US2 — one skill that knows where the docs are (P1)

Independent test: one AI Hub skill ships, its map entries are all on the upstream list, the workflow starts with version then `%AI` classes.

- [x] T010 [US2] Unit tests in `core/tests/unit/test_aihub_139.rs`, red before the rewrite, per `specs/132-aihub-139/contracts/skill-structure.md`: frontmatter `name`/`version: 0.2.0`/`managed_by`/`source:` naming `72749d6dbf0b856a60775378fa88d346bb79d4e4` and `391c3d5` and Gabriel Ing; section order 1–7; section 1 has the repo URL, `master` and the raw URL form; every `Topic | File` path is on `upstream-files.txt` (directory entries match by prefix) and the header commit equals the one in `source:`; workflow step 1 names the version call, step 2 names `%AI`, and the text says installed classes win and the agent reports disagreement; section 7 gives the raw URL of `skills/aihub-eap/SKILL.md` and says `skill_community` cannot install it until upstream ships an `iris-agentic-dev.toml`; the text tells the agent to fall back to the installed `%AI` classes when GitHub is unreachable; every `iris_*`/`docs_*` tool name in the skill is in `testing::tool_names()`
- [x] T011 [P] [US2] Unit test in `core/tests/unit/test_aihub_139.rs`: the bundle (`skills/bundled.rs`) has `iris-ai-hub` and not `aihub-eap`; a walk of the repo (skipping `specs/`, `target/`, `.git/`, `tests/e2e/results/`, and this test file) finds no `aihub-eap` string except the upstream path `skills/aihub-eap/SKILL.md` — allowed inside the raw URL `https://raw.githubusercontent.com/intersystems-community/ai-hub-eap/master/skills/aihub-eap/SKILL.md` and as a line of `upstream-files.txt`; no skill directory, manifest key, lock entry or card header is named `aihub-eap`
- [x] T012 [P] [US2] Change the expected count in `tests/e2e/skill_eval/optimize/test_menu.py:25` from 39 to 38 (red until T015)
- [x] T013 [P] [US2] Live test `aihub_139_upstream_files` in `core/tests/integration/test_aihub_139_live.rs`: one HTTP HEAD per listed path on `https://raw.githubusercontent.com/intersystems-community/ai-hub-eap/master/<path>`, fails naming every path that is not 200
- [x] T013a [P] [US2] Unit test in `core/tests/unit/test_aihub_139.rs`: every `cargo test … <filter>` line in `specs/132-aihub-139/quickstart.md` matches at least one `module::fn` path of an `#[ignore]` test in `test_aihub_139_live.rs` (substring match, as cargo does), and every `#[ignore]` fn there is matched by some quickstart line (constitution XI)
- [x] T014 [US2] Delete the `AIHUB_BUGGY`/`AIHUB_FIXED` constants and `aihub_eap_is_upstream_plus_the_marked_patch` from `core/tests/unit/test_skill_facts_127.rs:337-389`, and delete `core/tests/unit/fixtures/aihub_eap_upstream_72f9046.md` and its directory
- [x] T015 [US2] Remove `aihub-eap` from every file in research.md R6: delete `skills/skills/aihub-eap/`; `core/src/skills/bundled.rs:84`; `iris-agentic-dev.toml:53`; `skills.sh.json:65`; `skills-lock.json:4-8`; `docs/skills.md:107`; `AGENTS.md:70`; `scripts/gates/antipatterns-baseline.txt:166-167`; the `## SKILL aihub-eap` cards in `tests/e2e/tasks/content/cards.txt` and `tests/e2e/tasks/routing/cards.txt`; check `core/tests/unit/test_skill_manifest_sync.rs` still agrees
- [x] T016 [US2] Rewrite `skills/skills/iris-ai-hub/SKILL.md` sections 1–4 and 7 per the contract; sections 5 and 6 are headings only until US3/US4. Section 4 is the short no-gateway fallback (`docker_only`, `%Dictionary.CompiledClass`/`CompiledMethod` via `iris_execute`). Name no `%AI.*` class that has no claim row yet
- [x] T017 [US2] Gate: `cargo test --features testing --test unit`, `pytest tests/e2e/skill_eval/optimize/test_menu.py`, and `aihub_139_upstream_files` live all pass; `docs/skills.md` says 34 skills and there are 34

## Phase 5: US3 — every claim holds on 139 (P1)

Independent test: every claim row names a live test that passes on 139; a claim with no passing test is not in the skill.

- [x] T018 [US3] Unit test in `core/tests/unit/test_aihub_139.rs`: parse the claim table in `specs/132-aihub-139/research.md`; ids unique; verdict in {holds, false, reworded, not taken}; every non-`not taken` row names a `fn` that exists in `test_aihub_139_live.rs`; every `hackathon:*` row credits `Gabriel Ing`; every `%AI.*`/`%ConfigStore.*` name in the skill has a `holds` or `reworded` row
- [x] T019 [US3] Load `objectscript-guardrails` and `objectscript-review` (skill describe), then write fixtures in `core/tests/fixtures/aihub139/`: `IadAihub139.Agent.cls` (`%AI.Agent`, one tool), `IadAihub139.Tool.cls` (`%AI.Tool`), `IadAihub139.ToolSet.cls` (XData `Definition`), `IadAihub139.MCP.cls` (`%AI.MCP.Service` with `SPECIFICATION`), `IadAihub139.BrokenInit.cls` (`%OnInit` setting a bad provider)
- [x] T020 [US3] Live structure tests in `core/tests/integration/test_aihub_139_live.rs`, each with a `Drop` guard that deletes what it made: one per R4 inventory claim (class/method/parameter exists via `%Dictionary.Compiled*`), `fixtures_compile` (put+compile all five over `iris_doc`), `configstore_roundtrip` (Create/Get/GetDetails/Delete under `IadAihub139`, from USER; record whether USER works or %SYS is needed), `wallet_roundtrip` (collection `IadAihub139`), `mcp_webapp_registers` (`/mcp/iadaihub139` via `Security.Applications` in %SYS, listed, then removed), `mcp_service_urlmap` (read the `%AI.MCP.Service` UrlMap), `superserver_login` (TCP login on 11976), `docker_only_metadata_fallback` (iad spawned with `docker_only = true` against `iad-aihub-iris` reads `%AI.Agent` methods through `iris_execute` on `%Dictionary.CompiledMethod`, the path skill section 4 describes; the only docker-path test, backing the plan's constitution III row) Done as the 13 `aihub_139_*` fns: the per-claim tests are folded into topic fns (`aihub_139_class_inventory`, `aihub_139_tool_and_query_tools`, `aihub_139_policies`, `aihub_139_agent_providerconfig`, `aihub_139_rag_fastembed`, `aihub_139_mcp_bridge`).
- [x] T021 [US3] Live test `aihub_139_real_turn` in `core/tests/integration/test_aihub_139_live.rs`: runs only with `IAD_AIHUB_LLM=1` and `OPENAI_API_KEY`, otherwise prints a skip naming both; key passed by name (`docker exec -e OPENAI_API_KEY`), stored in Wallet `IadAihub139.OpenAI`, ConfigStore LLM entry references `secret://IadAihub139.OpenAI#api_key`, model `gpt-4.1-mini`; asserts the transcript records a call to `IadAihub139.Tool`; asserts no output contains the key's first 8 characters; teardown deletes Wallet and ConfigStore entries pass or fail Passed 2026-09-30 with `IAD_AIHUB_LLM=1` (3.6 s); without it the test prints its skip line.
- [x] T022 [US3] Mine the eight hackathon skills in `~/ws/ready-hackathon-dev-template/skills/ai-hub-*/` (SKILL.md and `references/`): one claim-table row per claim in `specs/132-aihub-139/research.md`, source `hackathon:<skill>:<line>`, credit Gabriel Ing; a row marked taken gets its live test in `test_aihub_139_live.rs` written before the verdict is filled
- [x] T023 [US3] Add claim rows for the upstream-doc and own claims the skill will make, each with its live test first
- [x] T024 [US3] Write skill section 5 (ConfigStore, Wallet, provider, agent, tools and toolsets, MCP server, policies, RAG) in `skills/skills/iris-ai-hub/SKILL.md` from `holds`/`reworded` rows only, with "(from Gabriel Ing's hackathon skills)" on taken hackathon claims
- [x] T025 [US3] Gate: T018 unit passes; the full `test_aihub_139_live` suite passes on 139 (real turn with `IAD_AIHUB_LLM=1` if Tom's key is in env, else its skip line recorded); no `IadAihub139*` class, ConfigStore, Wallet or web-app entry is left on 139 Passed 2026-09-30: 13/13 live, real turn included; old probe classes deleted with `DeletePackage`; no tables, global, ConfigStore entry or `/mcp*` app left.

## Phase 6: US4 — doc mismatches recorded, ready for upstream (P2)

Independent test: one `drafts.md` entry per reproduced mismatch, each with doc file:line, 139 behaviour, test name; the skill states each correction.

- [x] T026 [US4] Unit test in `core/tests/unit/test_aihub_139.rs`: parse `specs/132-aihub-139/drafts.md`; every entry has a doc `file:line`, what the doc says, what 139 does, a test name that exists in `test_aihub_139_live.rs`, draft upstream text, and `Status: drafted`; every entry has a matching "the guide says X; on 2026.3 it is Y" line in skill section 6; the FR-008 `iris-agentic-dev.toml` draft is present
- [x] T027 [US4] Live tests for R5 candidates in `core/tests/integration/test_aihub_139_live.rs`: `configstore_get_signature` (M1), `configstore_delete_signature` (M2), `providerconfig_forms` (M3), `agent_new_without_init` (M4), `console_audit_with_mcp` (M5); each asserts what 139 does, not what the doc says Done inside the existing fns, not as separately named ones: M1, M2, M3, M4 and M6 in `aihub_139_agent_providerconfig`, M5 and M7 in `aihub_139_mcp_bridge`, M8 in `aihub_139_policies`.
- [x] T028 [US4] Write `specs/132-aihub-139/drafts.md`: one entry per reproduced mismatch plus the FR-008 draft; a candidate the test does not reproduce is dropped with a note in research.md R5 and no drafts entry D1–D7 (M1–M4, M6–M8), D8 (FR-008), B1 (iad license leak). M5 is dropped: not reproduced.
- [x] T029 [US4] Write skill section 6 in `skills/skills/iris-ai-hub/SKILL.md`, one line per drafts entry
- [x] T030 [US4] Gate: T026 unit and T027 live pass; nothing filed, pushed or commented Passed 2026-09-30: 23/23 unit; the four live tests pass; nothing filed.

## Phase 7: US5 — ladder evidence decides skill vs tool (P2)

Independent test: a ladder run over SKILL-22..25 gives per-arm results, `needs_fix`, and a per-task decision in research.md citing `tool_calls.py` lines.

- [x] T031 [P] [US5] Python tests in `tests/e2e/skill_eval/test_ladder.py`, red first: `--side train` selects only train tasks and writes `side: train` into each record; default `holdout`; `--task` naming a task on the other side prints `no <side> task matches …` and exits 2; `--web-port` reaches `IsolatedEnv.with_mcp(iris_web_port=…)` and the check CLI env; default is `IRIS_WEB_PORT` then 52780
- [x] T032 [P] [US5] Python test in `tests/e2e/skill_eval/test_split.py`: a `side: train` result is refused by `split.assert_holdout_only`; `TUNED_SKILL_TASKS` has `SKILL-22 → SKILL-25` and `SKILL-23 → SKILL-24`; `split.toml` has all four with the right sides
- [x] T033 [P] [US5] Python tests in `tests/e2e/skill_eval/test_pilot.py`: task YAML `teardown` is parsed; it runs once before the session and once after the check, next to FR-023 class cleanup; a non-zero exit raises `CheckBroken` naming the task and `teardown`, and the run is unscored; absent field changes nothing
- [x] T034 [P] [US5] Python test `tests/e2e/skill_eval/test_tool_calls.py` with a recorded transcript fixture in `tests/e2e/skill_eval/fixtures/`: output blocks `== <task> <arm> repeat=<n> ==`, one `<n>\t<tool>\t<ok|err>\t<first 120 chars, newlines as ⏎>` line per call; missing transcripts dir exits 2 naming the path
- [x] T035 [P] [US5] Task shape test in `tests/e2e/skill_eval/test_task_corpus.py`: SKILL-22..25 have `skill: iris-ai-hub`, `namespace: USER`, prompts naming `iad-aihub-iris`, a structural `check` with no LLM call, a `solution`, and a `teardown` covering ConfigStore, Wallet and web-app entries under `IadAihub139`
- [x] T036 [US5] Implement `--side` and `--web-port` in `tests/e2e/skill_eval/ladder.py`, `side` in the run record, the refusal in `tests/e2e/skill_eval/split.py`
- [x] T037 [US5] Implement `teardown` in `tests/e2e/skill_eval/graded_task.py` (parse) and `tests/e2e/skill_eval/pilot.py` (run before/after, `CheckBroken` on error)
- [x] T038 [US5] Implement `tests/e2e/skill_eval/tool_calls.py` (`list <run_id>`)
- [x] T039 [US5] Write `tests/e2e/tasks/benchmark/skills/SKILL-22.yaml` (train, agent with one tool), `SKILL-23.yaml` (train, ConfigStore provider), `SKILL-24.yaml` (holdout, MCP server definition), `SKILL-25.yaml` (holdout, broken `%OnInit` provider); add them to `tests/e2e/tasks/benchmark/split.toml`; add the pairs to `TUNED_SKILL_TASKS` in `tests/e2e/skill_eval/test_split.py` with a comment that they are train from the day written, as SKILL-21 is
- [x] T040 [US5] Live before/after test in `tests/e2e/skill_eval/test_graded_task_live.py`: for each of SKILL-22..25 on `iad-aihub-iris`/52781, the check fails on the empty state, passes after `solution`, and teardown leaves no `IadAihub139*` state
- [x] T041 [US5] Billable ladder, cap $3 with `--spent`: holdout `--container iad-aihub-iris --web-port 52781 --repeats 3`, then `--side train` with the same flags (commands in quickstart.md)
- [x] T042 [US5] `python -m tests.e2e.skill_eval.tool_calls list <run_id>` for both runs; per task in `specs/132-aihub-139/research.md`: arm results, `needs_fix`, and the FR-016 decision (skill edit / tool proposal / none) citing transcript lines, with each failed repeat's tool calls assigned by hand to a step (call-number ranges from `tool_calls.py`); a skill edit draws only on train failures and gets a unit guard test in `test_aihub_139.rs`; a tool proposal goes to a follow-up spec note, not code
- [x] T043 [US5] Gate: all Python tests pass (`pytest tests/e2e/skill_eval`); each task has 3 scored repeats per arm (re-run unscored repeats with `--start-repeat` inside the $3 cap; if the cap stops it, record SC-006 as unmet with the count and reasons, not as met); 139 left clean

## Phase 8: Polish

- [x] T044 [P] `cargo llvm-cov --features testing -- --include-ignored` against both containers; confirm core line coverage is ≥ 88% (the enforced number) or record the shortfall against the 85.00% baseline with the reason; record the delta in `specs/132-aihub-139/research.md`
- [x] T045 [P] CLAUDE.md Recent Changes entry for 132; `docs/skills.md` entry for `iris-ai-hub` 0.2.0; `markdownlint-cli2 --fix` and `prettier --write` on every edited `.md`
- [x] T046 `cargo fmt --all -- --check`, `cargo clippy -- -D warnings`, `cargo test --features testing`, the full serial live suite on iris-dev-iris (SC-007) and on 139, `pytest tests/e2e/skill_eval`
- [ ] T047 Local commit (`git -c user.email=tdyar@intersystems.com`); no push; `iris.key`, `CSP.ini`, `CSP.conf` and `OPENAI_API_KEY` never staged

## Dependencies

- Phase 1 → Phase 2 → US1 → (US2, US3). US2 and US3 can run side by side once US1 passes; the skill file is shared, so section writes (T016, T024) go in order.
- US4 needs US3's fixtures and live file (T019, T020). T029 comes after T024.
- US5 needs the finished skill (T024, T029) for the skill arm; T031–T038 can start any time after Phase 2.
- Polish last.

## Parallel examples

- Setup: T002 alongside T001.
- US2: T011, T012, T013 together (three files).
- US5: T031–T035 together (five test files), then T036–T038.
- Polish: T044 and T045 together.

## Strategy

MVP is US1 + US2: a reachable 139 and a skill that sends agents to the right docs, with the vendored copy gone. US3 then makes every claim in it true on 139; US4 records where the docs are wrong; US5 spends money last, on a finished skill.
