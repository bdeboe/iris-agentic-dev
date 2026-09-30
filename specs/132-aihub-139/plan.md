# Plan: 132 AI Hub on EAP build 139

Stacked on `131-mdx-cube-facts`. Every claim in the skill comes from a live test on 139. Nothing is posted, filed or pushed.

## Technical context

- Rust 2021, `iris-agentic-dev-core`. No new crate dependency. Python 3.11 for the ladder (`tests/e2e/skill_eval/`), no new dependency.
- Live target: `iad-aihub-iris`, image `docker.iscinternal.com/docker-unreleased/intersystems/irishealth:2026.3.0AI.139.0`, arm64, `$ZV` 2026.3.0AI Build 139U. Superserver on host 11976.
- **Licensed, with Atelier through a Web Gateway sidecar.** The image ships no private web server (`WebServer=0`, no httpd). Unlicensed, it has one license unit and every authenticated REST call gets 503, which rules that out. So the container mounts a Sales Engineers ARM64 container key (128 users, expires 2026-11-30) from `~/.config/iris-agentic-dev/aihub139/iris.key`, outside every repo. The sidecar `iad-aihub-webgateway` (`webgateway:2026.2`) serves host 52781 and reaches IRIS at `host.docker.internal:11976`. Measured 2026-09-30, using iad over HTTP on 52781: `iris_doc` put and compile of a `%AI.Agent` subclass, then `iris_execute` (`execution_path: atelier`), then delete. See research.md R1.
- So iad reaches 139 the same way it reaches iris-dev-iris: `IRIS_HOST=localhost IRIS_WEB_PORT=52781 IRIS_CONTAINER=iad-aihub-iris`. The ladder harness runs unchanged apart from the port.
- Namespace: USER. 139 has no BENCHMARK namespace. `%AI` (60 classes) and `%ConfigStore` are visible from USER. `Security.*` is %SYS only.
- Upstream docs: `intersystems-community/ai-hub-eap` master at `72749d6dbf0b856a60775378fa88d346bb79d4e4` (2026-09-09). It describes build 162 and does not mention 139 or 2026.3.
- Hackathon skills: `intersystems-ready-hackathon/ready-hackathon-dev-template` at 391c3d5, `skills/ai-hub-*/`, all from cefcd9e (Gabriel Ing, 2026-04-15). There are eight.
- Container registry: iad's entry `iris-agentic-dev-aihub` (container `iad-aihub-iris`, host_port 11976, web_port 52781, web_container `iad-aihub-webgateway`) verifies clean. It is not committed in productivity-framework.
- The license key and gateway config live outside the repo and are never committed. The recipe to recreate both is in quickstart.md.

## Container (US1)

- Start command and password unexpiry in `quickstart.md`. The container is not recreated by tests.
- `testing.rs`: `aihub_env() -> AihubEnv { container, host, web_port, namespace }`. It reads `IAD_AIHUB_CONTAINER` (default `iad-aihub-iris`), `IAD_AIHUB_HOST` (`localhost`), `IAD_AIHUB_WEB_PORT` (`52781`) and `IAD_AIHUB_NAMESPACE` (`USER`). It probes `GET /api/atelier/` on the web port and panics with the start command unless `IAD_ALLOW_SKIP=1`, in which case it returns `None` and prints the same text. It does not reuse `live_env`, which names iris-dev-iris.
- `aihub_session(env) -> McpSession` spawns iad through `clean_mcp_command` with `IRIS_HOST`/`IRIS_WEB_PORT`/`IRIS_CONTAINER`/`IRIS_NAMESPACE` from `AihubEnv`, over HTTP, like `live_env` does for iris-dev-iris.
- Fixture classes go on with `iris_doc` put+compile through that session, and come off with `iris_doc` delete.

## Skill (US2)

- `skills/skills/iris-ai-hub/SKILL.md` is rewritten. Frontmatter keeps `name`, `author`, `managed_by`, bumps `version` to 0.2.0, and adds `source:` naming ai-hub-eap at `72749d6` and the hackathon template at `391c3d5` (Gabriel Ing).
- The sections are the contract in `contracts/skill-structure.md`:
  1. where the docs are (repo, branch, raw URL form)
  2. topic → file map
  3. workflow: build version, then installed `%AI` classes, where the build wins
  4. if the instance has no web gateway (AI builds ship none), iad runs `docker_only`, where `iris_doc`/`docs_introspect`/`iris_symbols` do not work: read class metadata with `iris_execute` on `%Dictionary.CompiledClass`/`CompiledMethod`. One live test runs that fallback against 139 over the docker path
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
- `ladder.py --web-port` passes through to `IsolatedEnv.with_mcp` and to the check CLI. The AI Hub run uses `--container iad-aihub-iris --web-port 52781`.
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
| III HTTP-first                   | Met: 139 is reached over Atelier through the gateway sidecar. The one docker-path test covers the no-gateway fallback the skill describes.                                                                                 |
| IV test-first                    | Unit and Python tests are written red before the skill rewrite and the harness changes. Each live claim test is written before its claim goes in the skill.                                                                |
| VI no mocks                      | Live claims run on 139. The offline map test reads a recorded list, not a mocked GitHub; the live test checks the list against GitHub.                                                                                     |
| VIII coverage                    | The polish task runs `cargo llvm-cov --features testing` and records the delta. Only `testing.rs` helpers are new Rust.                                                                                                    |
| IX tool lift                     | N/A: no new tool. A US5 tool proposal becomes a follow-up spec.                                                                                                                                                            |
| X ObjectScript coverage          | N/A: the `.cls` files are test fixtures, not shipped code.                                                                                                                                                                 |
| XI loud skips                    | `aihub_env` panics naming the container unless `IAD_ALLOW_SKIP=1`. Every `#[ignore]` test has its command in quickstart.md. FR-011's opt-in is documented. No vacuous asserts: each claim test asserts what IRIS returned. |
| XII hermetic                     | `clean_mcp_command` strips `OPENAI_API_KEY`. The key goes to the container by name only.                                                                                                                                   |
| XIII                             | Skill text names tools that exist, and a unit test checks every `iris_*` name against the registry.                                                                                                                        |
| Issue closure / external actions | Drafts only.                                                                                                                                                                                                               |

Post-design re-check: no violation.

## Out of scope

`iris-mcp-oauth2`. Any new tool. Committing in productivity-framework. Committing the license key or gateway config. Filing upstream. Pushing.
