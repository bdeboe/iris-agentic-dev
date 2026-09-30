# Plan: 132 AI Hub on EAP build 139

Stacked on `131-mdx-cube-facts`. Every claim in the skill comes from a live test on 139. Nothing is posted, filed or pushed.

## Technical context

- Rust 2021, `iris-agentic-dev-core`. No new crate dependency. Python 3.11 for the ladder (`tests/e2e/skill_eval/`), no new dependency.
- Live target: `iad-aihub-iris`, image `docker.iscinternal.com/docker-unreleased/intersystems/irishealth:2026.3.0AI.139.0`, arm64, `$ZV` 2026.3.0AI Build 139U. Superserver on host 11976. 52781 is mapped but nothing answers.
- **No private web server and no license key.** `WebServer=0`, and the instance has one license unit (`LUAvailable=0 LUConsumed=1` with one terminal session open). A Web Gateway sidecar reached IRIS (the portal login page returned 200) but every authenticated REST call (`/api/atelier`, `/api/mgmnt`) returned 503. So iad reaches 139 with `docker_only = true` only: `iris_execute` and `iris_compile` go through `docker exec … iris session`, and `iris_doc`, `docs_introspect` and `iris_symbols` do not work (research.md R1).
- Namespace: USER. 139 has no BENCHMARK namespace. `%AI` (60 classes) and `%ConfigStore` are visible from USER. `Security.*` is %SYS only.
- Upstream docs: `intersystems-community/ai-hub-eap` master at `72749d6dbf0b856a60775378fa88d346bb79d4e4` (2026-09-09). It describes build 162 and does not mention 139 or 2026.3.
- Hackathon skills: `intersystems-ready-hackathon/ready-hackathon-dev-template` at 391c3d5, `skills/ai-hub-*/`, all from cefcd9e (Gabriel Ing, 2026-04-15). There are eight.
- Container registry: iad's second entry `iris-agentic-dev-aihub` (container `iad-aihub-iris`, host_port 11976, web_port null) was added 2026-09-30, and the verifier no longer flags the container. It is not committed in productivity-framework.

## What blocks what

| Story                  | Runs on 139 today               | Why                                                                                                                                                                                                                        |
| ---------------------- | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| US1 container          | yes                             | docker exec                                                                                                                                                                                                                |
| US2 skill + map        | yes                             | offline unit test, one GitHub test                                                                                                                                                                                         |
| US3 claims             | yes, over docker                | fixtures are loaded with `docker cp` + `$system.OBJ.Load`; claims are read through iad `iris_execute` under `docker_only`                                                                                                  |
| US3 real turn (FR-011) | unknown                         | whether an unlicensed instance makes an outbound provider call is not measured yet; the test measures it                                                                                                                   |
| US4 mismatches         | yes                             | falls out of US3                                                                                                                                                                                                           |
| US5 ladder             | **no, until a key is supplied** | the harness loads fixtures, snapshots and deletes classes through `iris_doc`, and an agent writes a class through `iris_doc`. Under `docker_only` none of that works. With a key, the sidecar in R1 gives Atelier on 52781 |

US5 work that needs no instance (tasks, `--side train`, teardown field, cleanup tests) goes ahead. The ladder run waits for a key. research.md records the recipe.

## Container (US1)

- Start command and password unexpiry in `quickstart.md`. The container is not recreated by tests.
- `testing.rs`: `aihub_env() -> AihubEnv { container, host, superserver_port, namespace }`. It reads `IAD_AIHUB_CONTAINER` (default `iad-aihub-iris`), `IAD_AIHUB_HOST` (`localhost`), `IAD_AIHUB_PORT` (`11976`) and `IAD_AIHUB_NAMESPACE` (`USER`). It checks the container with `docker inspect -f {{.State.Running}}` and panics with the start command unless `IAD_ALLOW_SKIP=1`, in which case it returns `None` and prints the same text. It does not reuse `live_env`, which names iris-dev-iris.
- `aihub_session(env) -> McpSession` writes a temp `.iris-agentic-dev.toml` with `docker_only = true`, `container`, `namespace`, spawned through `clean_mcp_command`. This is the same shape as `docker_exec` in `test_exec_sql_131_live.rs`, moved into `testing.rs` so it can be shared.
- `aihub_load(env, cls_files)` copies fixture `.cls` files into the container and runs `$system.OBJ.Load(path,"ck")` through `docker exec`. This is test setup, not the thing under test, and it does not go through the write gate. It returns the compile status text.

## Skill (US2)

- `skills/skills/iris-ai-hub/SKILL.md` is rewritten. Frontmatter keeps `name`, `author`, `managed_by`, bumps `version` to 0.2.0, and adds `source:` naming ai-hub-eap at `72749d6` and the hackathon template at `391c3d5` (Gabriel Ing).
- The sections are the contract in `contracts/skill-structure.md`:
  1. where the docs are (repo, branch, raw URL form)
  2. topic → file map
  3. workflow: build version, then installed `%AI` classes, where the build wins
  4. under `docker_only`, how to read classes with `iris_execute` (`%Dictionary.CompiledClass`/`CompiledMethod` queries), because `docs_introspect`/`iris_symbols` need Atelier
  5. then ConfigStore, Wallet, provider, agent, tools and toolsets, MCP server, policies, and RAG, with tested claims only
  6. "the guide says X; on 2026.3 it is Y" corrections
  7. upstream's own skill by raw URL, without `skill_community`
- `aihub-eap` is removed from every file in research.md R6. After removal the count is 34, which makes `docs/skills.md` "All 34 skills" true again, and `test_menu.py` goes from 39 to 38.
- `tests/fixtures/aihub139/upstream-files.txt`: the 56 blob paths at `72749d6`, with a header line `# ai-hub-eap master 72749d6dbf0b856a60775378fa88d346bb79d4e4 2026-09-09`.

## Claims (US3, US4)

- Fixture classes in `crates/iris-agentic-dev-core/tests/fixtures/aihub139/`, package `IadAihub139`:
  - `IadAihub139.Agent`: `%AI.Agent`, one tool.
  - `IadAihub139.Tool`: `%AI.Tool`.
  - `IadAihub139.ToolSet`: XData Definition.
  - `IadAihub139.MCP`: `%AI.MCP.Service` with SPECIFICATION.
  - `IadAihub139.BrokenInit`: `%OnInit` that sets a bad provider, for the holdout task.
- ConfigStore names are under `IadAihub139`. Wallet collection `IadAihub139`. MCP web app `/mcp/iadaihub139`. Every test deletes what it made in a `Drop` guard, so a panic still cleans up.
- `research.md` holds one row per claim: source (upstream file:line, hackathon skill:line, or own), verdict, test name. A claim enters the skill only with a passing test.
- Each mismatch goes into `drafts.md` (doc file:line, 139 behaviour, test) and into the skill's corrections section.

## Real turn (FR-011)

- `#[ignore]`, and it runs only when `IAD_AIHUB_LLM=1` and `OPENAI_API_KEY` are set. Otherwise it prints a skip naming both and returns. This is a documented opt-in, the same as `IAD_ALLOW_SKIP`, not a silent skip.
- The key reaches IRIS by environment variable name only: `docker exec -e OPENAI_API_KEY iad-aihub-iris iris session …`, so the value is never in argv. ObjectScript reads it with `$SYSTEM.Util.GetEnviron`, writes it to Wallet `IadAihub139.OpenAI`, and a ConfigStore LLM entry references `secret://IadAihub139.OpenAI#api_key`. The key never passes through iad, so it is never in `agent_history` or test output. The test asserts that the output does not contain the key's first 8 characters.
- Model `gpt-4.1-mini`. The assertion is that the session transcript records a tool call to `IadAihub139.Tool`, not what the text says.
- Teardown deletes the Wallet secret and the ConfigStore entry, pass or fail.

## Ladder (US5)

- Tasks `tests/e2e/tasks/benchmark/skills/SKILL-22..25.yaml`, `skill: iris-ai-hub`, `namespace: USER`, and prompts naming `iad-aihub-iris`:
  - SKILL-22 (train): agent with one tool.
  - SKILL-23 (train): ConfigStore provider.
  - SKILL-24 (holdout): MCP server definition.
  - SKILL-25 (holdout): broken `%OnInit` provider.
- `split.toml` gains all four. `TUNED_SKILL_TASKS` gains `SKILL-22 → SKILL-25` and `SKILL-23 → SKILL-24`, with a comment saying they are train from the day they were written, as SKILL-21 is.
- Checks are structural ObjectScript that prints PASS/FAIL and makes no LLM call (FR-015):
  - compile status
  - `%Dictionary.CompiledClass` super and parameters
  - `%ConfigStore.Configuration.Get`
  - `Security.Applications.Exists` in %SYS
- New optional task field `teardown` (ObjectScript). `pilot.py` runs it before the session and after the check, next to the FR-023 class cleanup. It removes the ConfigStore, Wallet and web-app entries under `IadAihub139`. A teardown that errors makes the run unscored, not failed. This closes FR-017 for non-class state.
- `ladder.py --side {holdout,train}`, default `holdout`. A train run writes `side: train` into the result, and `split.assert_holdout_only` refuses to publish it.
- `ladder.py --web-port` passes through to `IsolatedEnv.with_mcp`. The run waits on a license key (above).
- Mechanical-failure evidence: `skill_eval/tool_calls.py list <run_id>` prints each session's tool calls, one per line (`n tool ok/err first-120-chars`), from the `<run_id>.transcripts/` files. research.md cites those lines per FR-016. No classifier.

## Tests

- **Unit** `tests/unit/test_aihub_139.rs`:
  - The skill parses, and its frontmatter has `source:` naming both repos.
  - Every map path is in `upstream-files.txt`, and the header commit matches the one the skill names.
  - The skill names the repo URL, `master` and the raw URL form.
  - Workflow step 1 names the version call and step 2 names `%AI`.
  - The skill does not say `skill_community` installs upstream's skill.
  - The bundle has `iris-ai-hub` and no `aihub-eap`, and no file in the repo mentions `aihub-eap` outside `specs/` and history.
  - Every `%AI`/`%ConfigStore` class name in the skill has a row in research.md's claim table (parsed).
  - `aihub_env` env-var parsing (pure part).
- **Unit** `test_skill_facts_127.rs`: the AIHUB section and its fixture are deleted, and the file still compiles.
- **Binary**: no new CLI flag or tool, so no binary test. The `tools/list` count is unchanged, asserted by the existing test.
- **Live** `tests/integration/test_aihub_139_live.rs`, all `#[ignore = "live iad-aihub-iris"]`:
  - version is 2026.3.0AI.139
  - one test per claim row
  - fixture classes compile
  - ConfigStore create/get/delete
  - Wallet secret round trip
  - MCP web app registers and is removed
  - the FR-011 real turn
  - the upstream file list against GitHub raw (one HEAD per file)
- **Python** `tests/e2e/skill_eval/test_*.py`, written before the code:
  - `--side train` selects train tasks and marks the result
  - a train result is refused by the publish gate
  - `teardown` is parsed and run in order, and one that errors leaves the run unscored
  - `tool_calls.py` output on a recorded transcript fixture
  - `TUNED_SKILL_TASKS` pairs
  - `test_menu.py` count 38
- `mod` lines in `tests/unit/main.rs` and `tests/integration/main.rs` (`test_test_target_layout.rs` guard).

## Constitution check

| Principle                        | Status                                                                                                                                                                                                                     |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| III HTTP-first                   | Deviation, justified: 139 cannot serve Atelier (no PWS, one license unit). Tests use the docker path iad already supports (`docker_only`), and the skill says so. iris-dev-iris tests stay HTTP.                           |
| IV test-first                    | Unit and Python tests are written red before the skill rewrite and the harness changes. Each live claim test is written before its claim goes in the skill.                                                                |
| VI no mocks                      | Live claims run on 139. The offline map test reads a recorded list, not a mocked GitHub; the live test checks the list against GitHub.                                                                                     |
| VIII coverage                    | The polish task runs `cargo llvm-cov --features testing` and records the delta. Only `testing.rs` helpers are new Rust.                                                                                                    |
| IX tool lift                     | N/A: no new tool. A US5 tool proposal becomes a follow-up spec.                                                                                                                                                            |
| X ObjectScript coverage          | N/A: the `.cls` files are test fixtures, not shipped code.                                                                                                                                                                 |
| XI loud skips                    | `aihub_env` panics naming the container unless `IAD_ALLOW_SKIP=1`. Every `#[ignore]` test has its command in quickstart.md. FR-011's opt-in is documented. No vacuous asserts: each claim test asserts what IRIS returned. |
| XII hermetic                     | `clean_mcp_command` strips `OPENAI_API_KEY`. The key goes to the container by name only.                                                                                                                                   |
| XIII                             | Skill text names tools that exist, and a unit test checks every `iris_*` name against the registry.                                                                                                                        |
| Issue closure / external actions | Drafts only.                                                                                                                                                                                                               |

Post-design re-check: no new violation. The III deviation is forced by the build and is recorded here and in research.md R1.

## Out of scope

`iris-mcp-oauth2`. Any new tool. Running the ladder before a license key is supplied. Committing in productivity-framework. Filing upstream. Pushing.
