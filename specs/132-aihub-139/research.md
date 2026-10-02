# Research: 132 AI Hub on EAP build 139

Measured 2026-09-30 on `iad-aihub-iris` unless marked otherwise. Anything not measured is labelled that way.

## R1: How iad reaches 139

**Decision**: run 139 licensed, with a Web Gateway sidecar, and reach it over HTTP like any other instance. The container mounts a Sales Engineers ARM64 container key from `~/.config/iris-agentic-dev/aihub139/iris.key` (copied from the fhir-arno checkout, read only; 128 users, expires 2026-11-30). The sidecar `iad-aihub-webgateway` serves host 52781 and reaches IRIS at `host.docker.internal:11976`. Its `CSP.ini`/`CSP.conf` live in the same directory. Nothing under `~/.config/iris-agentic-dev/aihub139/` enters the repo.

**Measured unlicensed** (why the key is needed; EAP images ship without one):

- `WebServer=0` and no `/usr/irissys/httpd`, so there is no private web server to map.
- messages.log at startup: `LMF Error: No valid license key. No valid local file found and LicenseID not defined.` and `Not licensed for Interoperability, auto-start skipped.`
- `$SYSTEM.License.LUAvailable()=0` and `LUConsumed()=1` with one `iris session` open. The instance has one license unit.
- Through the sidecar, `/csp/sys/UtilHome.csp` returned 200 but `/api/atelier/` and `/api/mgmnt/` with `_SYSTEM:SYS` returned 503 on every try. The authenticated login needs a license unit and none is free.

**Measured licensed** (2026-09-30):

- `LUAvailable()=127`.
- `iris-agentic-dev tool iris_doc` with `IRIS_HOST=localhost IRIS_WEB_PORT=52781 IRIS_CONTAINER=iad-aihub-iris`: put and compile of `IadAihub139.Smoke Extends %AI.Agent` returned `compiled: true`; `iris_execute` returned `execution_path: atelier`; delete succeeded.
- IRIS logs `Web Gateway version 2602.1863 has connected … You should upgrade the Web Gateway`. A warning only.
- `docker network create` fails on this host (`all predefined address pools have been fully subnetted`), so the sidecar reaches IRIS through `host.docker.internal` rather than a shared network.
- After recreating the container, `_SYSTEM` gets 401 until `Security.Users.UnExpireUserPasswords("*")` runs; the first try right after "Enabling logons" can be early, so retry.

**Loud skip, measured** (T009, gateway stopped with `docker stop iad-aihub-webgateway`):

```text
thread 'test_aihub_139_live::aihub_version_is_139' panicked at crates/iris-agentic-dev-core/src/testing.rs:1507:21:
AI Hub 139 instance not reachable at localhost:52781/api/atelier/ (localhost:52781: Connection refused (os error 61)).
These tests measure AI Hub claims on iad-aihub-iris; without it they assert nothing, so they fail instead of passing quietly.
Start it:  docker start iad-aihub-iris iad-aihub-webgateway
First time: the docker run recipes are in specs/132-aihub-139/quickstart.md
Or opt into skipping deliberately: IAD_ALLOW_SKIP=1
```

With `IAD_ALLOW_SKIP=1`, the same run prints `SKIP (IAD_ALLOW_SKIP set): AI Hub 139 instance not reachable …` and the test reports ok. With the gateway back up, all three US1 tests pass. None of this touches the iris-dev-iris suite: `live_env` and its tests are unchanged.

- `iris_execute` refuses code that names `%Dictionary.ClassDefinition` (`CODE_EDIT_BLOCKED`, the non-configurable code-edit gate), reads included. `%Dictionary.CompiledClass` through `iris_query` works, and the US1 tests use that.

**Alternatives**:

- `docker_only`. Rejected: `apply_documents`, `list_classes` and `reset_documents` in `graded_task.py` call `iris_doc`, which the docker path lacks. The skill still covers this path, because Enterprise AI builds may ship with no gateway (DPP-1192).
- Unlicensed with the sidecar. Rejected: 503 on every REST login.
- Another project's 2026.3 container (irispython-dx runs build 154). Rejected: containers are project-exclusive.

## R2: Upstream docs

- Repo `intersystems-community/ai-hub-eap`, default branch `master`, HEAD `72749d6dbf0b856a60775378fa88d346bb79d4e4` (2026-09-09), 56 blobs.
- Raw form `https://raw.githubusercontent.com/intersystems-community/ai-hub-eap/master/<path>` returns 200.
- Map files (all at the repo root) and their line counts:

  | Topic                | File                           | Lines           |
  | -------------------- | ------------------------------ | --------------- |
  | ConfigStore          | `Config_Store_Guide.md`        | 321             |
  | MCP                  | `MCP_Server_Guide.md`          | 1588            |
  | MCP                  | `MCP_Server_Examples.md`       | 241             |
  | SDK                  | `ObjectScript_SDK_Guide.md`    | 3094            |
  | SDK                  | `ObjectScript_SDK_Advanced.md` | 1415            |
  | SDK                  | `ObjectScript_SDK_Examples.md` | 289             |
  | LangChain            | `langchain_SDK.md`             | 115             |
  | Samples              | `objectscript/cls/`            | 40 `.cls` files |
  | Upstream's own skill | `skills/aihub-eap/SKILL.md`    | 707             |

- The docs describe an older 2026.2 build. Nothing mentions 139 or 2026.3.
- `72f9046`, the id the old pin test used, is a **blob** sha, not a commit. It is the blob of `skills/aihub-eap/SKILL.md`, last changed in commit b716ddb, and unchanged at HEAD.

## R3: `skill_community` cannot install upstream's skill

- `skill_community install` copies only skills loaded at startup by `mcp --subscribe owner/repo`.
- `--subscribe` reads `iris-agentic-dev.toml` from the repo root. ai-hub-eap has none (404).
- `skill_community_install` is a `NOT_IMPLEMENTED` stub (`tools/mod.rs:6295`), and the family needs `OBJECTSCRIPT_LEARNING=true`.
- **Decision**: the skill gives the raw URL. drafts.md carries a draft asking upstream to add `iris-agentic-dev.toml` (FR-008).

## R4: What 139 has (inventory by docker exec)

- `%AI` has 60 classes, visible in USER.
- `%AI.Agent`
  - Parameters: `PROVIDER`, `MODEL`, `APIKEY`, `PROVIDERCONFIG`, `TOOLSETS`, `SKILLS`. XData `INSTRUCTIONS`.
  - `%Init(context)` runs, in order: `RegisterDefaults` → `%CreateProvider` → `%BuildTemplateContext` → `%LoadInstructions` → `%LoadToolSets` → `%LoadSkills` → `%OnInit()`.
  - Methods: `CreateSession`, `OpenSession`, `Chat`, `StreamChat`, `Run`, `UseToolSet`, `UseSkill`, `CreateSubAgent`.
- `%AI.Tool`
  - Parameters: `REQUIRESAUTH`, `STATEFUL`, `TIMEOUT`, `DISCOVERYLIMIT`, `QUERYMAXROWS`.
  - Methods: `%Discover`, `%Invoke`.
- `%AI.ToolSet`: XData `Definition` of the form `<ToolSet><Tool Name= Ref=/><Include Class=/></ToolSet>`.
- `%AI.ToolMgr`: `AddTool`, `RegisterToolSet`, `ExecuteTool`, `FindTools`, `GetOrCreate`, and `Set*Policy`.
- `%AI.Provider`: `Create(name, settings)`, `%GetProviders`, `ChatComplete`, `ListModels`.
- `%ConfigStore.Configuration`
  - `Create(area, type, subtype, name, details, displayName, description, readRes, editRes, enabled=1, validate=1)`
  - `Get(fqn, *config)`
  - `GetDetails(fqn, *details, checkValid, resolveSecrets)`
  - `Modify`, `Delete(fqn)`, `BuildFQN`, `ParseFQN`
- `%AI.ConfigStore.LLMDescriptor`: `model_provider` (required), `model`, `api_key`, `base_url`, `org_id`.
- `%AI.ConfigStore.MCPDescriptor`: `transport` (stdio/remote), `command`, `args`, `env`, `url`, `auth`.
- Placeholders `@{config:X}`, `@{wallet:X}` and `@{env:X}` are expanded by `%AI.Utils.SettingStore.Expand`. `%AI.Utils.ConfigStore.Lookup` also exists.
- `%AI.MCP.Service` extends `%CSP.REST` and `%CSP.WebSocket`. It has a `SPECIFICATION` parameter, and `VERSION` is `"IRIS MCP Gateway v1.0.1"`. The `iris-mcp-server` binary is in `/usr/irissys/bin`.
- Other packages:
  - `%AI.Policy.*`: `Audit`, `Authorization`, `Discovery`, `ConsoleAudit`, `ConsoleAuth`.
  - `%AI.RAG.*`, `%AI.System`, `%AI.Catalog`.
- Namespaces: %SYS, HSCUSTOM, HSLIB, HSSYS, HSSYSLOCALTEMP, USER. There is no BENCHMARK namespace, no sample package, and no predefined `/mcp` web app.
- **Measured since** (live tests in `test_aihub_139_live.rs`):
  - ConfigStore and Wallet writes work from USER; only `Security.Resources` needs %SYS (`aihub_139_agent_providerconfig`).
  - The bridge logs in on the superserver port 1972 from inside the container (`aihub_139_mcp_bridge`).
  - An MCP web app needs Type 18 (CSP + MCP). Type 16 is refused with "CSP bit", and a Type 2 app is accepted but serves no tools (`aihub_139_mcp_bridge`).
  - A licensed instance makes the outbound provider call (`aihub_139_real_turn`, with `IAD_AIHUB_LLM=1`).
- **Not measured**: a host TCP login on 11976. The tests reach IRIS over HTTP on 52781 and the bridge over 1972 in the container, so nothing needs it.

## R5: Mismatch candidates (to prove or drop by live test)

| #   | Doc                                       | Doc says                                                 | 139 does                                                                                                      | Test                             |
| --- | ----------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| M1  | `Config_Store_Guide.md:154`               | `Get(area,type,subtype,name)` returns the object         | `Get(fqn, .config)` returns %Status; four args raise `<PARAMETER>`                                            | `aihub_139_agent_providerconfig` |
| M2  | `Config_Store_Guide.md:175`               | `Delete` also takes four args                            | four args raise `<PARAMETER>` and the entry stays; `Delete(fqn)` works                                        | `aihub_139_agent_providerconfig` |
| M3  | `ObjectScript_SDK_Guide.md:250`, `:670`   | `PROVIDERCONFIG` as a bare name, or with `@{prefix.key}` | both give `ProviderConfigError: PROVIDERCONFIG is invalid`; `@{config:Name}` and `@{config:AI.LLM.Name}` work | `aihub_139_agent_providerconfig` |
| M4  | `ObjectScript_SDK_Guide.md:713` vs `:657` | `%New()` alone is enough                                 | `Provider` is empty until `%Init()`                                                                           | `aihub_139_agent_providerconfig` |
| M5  | `MCP_Server_Guide.md:959`                 | `ConsoleAudit` in a ToolSet breaks MCP `tools/call`      | a `ConsoleAudit` subclass audits and the bridged call succeeds; dropped, not drafted                          | `aihub_139_mcp_bridge`           |
| M6  | `skills/aihub-eap/SKILL.md:148`           | `If ..Provider = "" && ..#MODELCONFIGNAME '= ""`         | left to right, the guard is always true and replaces the caller's provider                                    | `aihub_139_agent_providerconfig` |
| M7  | `MCP_Server_Guide.md:136`                 | a web app with the service as dispatch class             | Type 18 needed; 16 refused, 2 serves nothing                                                                  | `aihub_139_mcp_bridge`           |
| M8  | `ObjectScript_SDK_Advanced.md:364`        | policy properties from `<Authorization>` children        | a one-item list loads empty, so a single `<Blocked>` denies nothing; `%XML.Reader` reads it as one            | `aihub_139_policies`             |

A candidate the test does not reproduce is dropped and noted here. It does not go into drafts.md.

## R6: Files that name `aihub-eap` (all to change)

- `skills/skills/aihub-eap/SKILL.md` (delete)
- `crates/iris-agentic-dev-core/src/skills/bundled.rs:84` (`embedded_skill!("aihub-eap")`)
- `iris-agentic-dev.toml:53`
- `skills.sh.json:65`
- `skills-lock.json:4-8`
- `docs/skills.md:107`. Line 100 says "All 34 skills" while 35 are on disk; it is right again after the removal.
- `AGENTS.md:70`
- `crates/iris-agentic-dev-core/tests/unit/test_skill_facts_127.rs:337-389` (`AIHUB_BUGGY`, `AIHUB_FIXED`, `aihub_eap_is_upstream_plus_the_marked_patch`)
- `crates/iris-agentic-dev-core/tests/unit/fixtures/aihub_eap_upstream_72f9046.md`, the only file in that dir, so the dir goes too
- `scripts/gates/antipatterns-baseline.txt:166-167`
- `tests/e2e/tasks/content/cards.txt:1-20` and `tests/e2e/tasks/routing/cards.txt`, the `## SKILL aihub-eap` cards
- `tests/e2e/skill_eval/optimize/test_menu.py:25` (39 → 38)
- `crates/iris-agentic-dev-core/tests/unit/test_skill_manifest_sync.rs` follows the manifest

## R7: Hackathon skills (Gabriel Ing)

- Source: `intersystems-ready-hackathon/ready-hackathon-dev-template` at 391c3d5. A mirror is at `intersystems-community/ai-hub-dev-template` 5b18875, and there is a local clone at `~/ws/ready-hackathon-dev-template`.
- Every file comes from commit cefcd9e by Gabriel Ing <ging@intersystems.com>, 2026-04-15.
- Layout: `skills/ai-hub-<x>/SKILL.md` + `references/<x>-reference.md`.
- The eight skills: `ai-hub-rag`, `ai-hub-objectscript-sdk`, `ai-hub-policies`, `ai-hub-langchain`, `ai-hub-config-store`, `ai-hub-mcp-server`, `ai-hub-toolsets`, `ai-hub-subagents-and-skills`.
- Credit: the skill's frontmatter `source:` and an inline "(from Gabriel Ing's hackathon skills)" on each claim taken, following the grongierisc precedent.
- The claim table below gets one row per claim from all eight during implementation (FR-014, SC-005).

## R8: Ladder decisions

- **`--side train`**: `holdout_only` drops train tasks, so SKILL-22 and SKILL-23 would never run. The flag adds them, the result says `side: train`, and `assert_holdout_only` refuses to publish it.
- **Replacement pairs**: `TUNED_SKILL_TASKS` gets `SKILL-22 → SKILL-25` and `SKILL-23 → SKILL-24`, so each train task has a holdout task for the same skill. test_split requires this.
- **Teardown field**: FR-023 cleanup deletes classes only (`pilot.py:282-292`). The new `teardown` ObjectScript runs before and after each session and removes ConfigStore, Wallet and `Security.Applications` entries under `IadAihub139`.
- **Mechanical evidence**: `tool_calls.py` lists tool calls per session from the saved transcripts. FR-016 decisions cite those lines. I am not building a classifier: four tasks do not justify one.
- **Model**: keep `openai/gpt-4.1` so results compare with 130. The skill-arm prompt asks for the skill (130 round 3), and a session that never loads it is unscored.
- **Namespace**: USER. Creating BENCHMARK on 139 is possible but adds state for no gain. The tasks name USER.

## R9: Real-turn key path

**Decision**: pass the variable by name (`docker exec -e OPENAI_API_KEY`), have ObjectScript read `$SYSTEM.Util.GetEnviron("OPENAI_API_KEY")`, store it in Wallet, and have the ConfigStore entry reference `secret://IadAihub139.OpenAI#api_key`.

**Why**: the value is never in argv, never in iad's request log or `agent_history`, and never in test output. The test asserts that its output does not contain the key's first 8 characters.

**Alternatives**:

- Pass the key in the `iris_execute` code. Rejected: it would be logged in `agent_history`.
- `@{env:OPENAI_API_KEY}` in ConfigStore. Rejected unless tested: the variable must be in the IRIS process environment, and `docker exec -e` sets it only for that session, not for the instance.

## R10: Ladder results (T041–T043)

Both runs used the pre-fix binary (B2 and B3 were still in it). Model `openai/gpt-4.1`, container `iad-aihub-iris`, web port 52781. Per-session costs are opencode's own `step_finish.cost`.

### Cost: the $3 cap was blown

Tom's cap was $3. Actual spend was **$12.40**: $12.29 for the holdout run and $0.11 for the one train session before I stopped it.

- The estimate used `COST_PER_SESSION_USD = 0.085` from the 121 pilot, which put the 12 holdout sessions at $1.02. Measured costs ran from $0.24 to $2.99 a session, with a mean of $1.02. The skill arm on SKILL-24 was the most expensive, at 54 to 94 steps.
- `--spent` only projected that estimate against the $80 programme budget. Nothing in the ladder measured cost or knew about a $3 cap.
- Fix: `cost_estimator.session_cost` sums `step_finish.cost`. `run_ladder(cap=, spent=)` adds each session's measured cost and raises `LadderAborted` once the total reaches the cap. `--cap` is a new flag, and the estimate must also fit under it. Tests are in `tests/e2e/skill_eval/test_ladder_cap.py`.

### Holdout run `ladder-20260930T143937`

| task     | arm               | r0   | r1   | r2   | cost r0/r1/r2     |
| -------- | ----------------- | ---- | ---- | ---- | ----------------- |
| SKILL-24 | tools             | FAIL | FAIL | FAIL | $0.56/$0.57/$0.68 |
| SKILL-24 | tools+iris-ai-hub | FAIL | PASS | PASS | $2.99/$2.85/$1.15 |
| SKILL-25 | tools             | FAIL | FAIL | FAIL | $0.32/$0.24/$0.27 |
| SKILL-25 | tools+iris-ai-hub | PASS | PASS | PASS | $0.77/$0.24/$1.65 |

Every skill-arm session loaded its skill, and all 12 sessions were scored. The report gives b=1, c=0, lift 0.5, n=2, underpowered. `needs_fix` flags nothing: the skill arm never failed 2 or more repeats where the tools arm passed.

**SKILL-24** (register the MCP web app `/mcp/iadaihub139`). Call numbers come from `tool_calls list ladder-20260930T143937`.

- tools r0, calls 6–26: stuck on the registration step. `iris_execute_method` returned the raw `%Status` bytes of the error (B2). Mechanical failure.
- tools r1, calls 12–28: `iris_doc_search` found 0 hits, and calls 22–28 got the same raw status. Mechanical failure: more than 10 calls on one step.
- tools r2: registered the app with `Type=2` instead of 18 (D6). Knowledge failure.
- tools+skill r0, calls 13–90: calls 51–68 hit B3, where a multi-line `iris_ws_exec` ran only its first line. `iris_execute_method` cannot pass an array by reference, so `Modify` gave `<PARAMETER>`. The session ended with an empty `DispatchClass`. Mechanical failure.
- FR-016 decision: **none**. Only one skill-arm repeat failed, so no step failed in both arms on 2 or more repeats, and no new tool is proposed. The mechanical causes were bugs in existing tools. B2 and B3 are fixed in `a636694` (drafts.md).

**SKILL-25** (fix the `%OnInit` precedence). All three tools-arm sessions wrote `If '$ISOBJECT(..Provider) && ..#MODELCONFIGNAME '= ""`, which ObjectScript evaluates strictly left to right. Knowledge failure, and the skill already states the rule. The skill arm passed 3/3. FR-016 decision: **none**.

### Train run `ladder-20260930T150504`

One session finished before I stopped the run for the cap: SKILL-22 tools r0, FAIL in 3 calls with a wrong answer (knowledge failure), $0.11. SKILL-23 did not run. A skill edit may draw only on train failures, and one knowledge failure in the tools arm does not show a gap in the skill, so **the skill is not edited**.

### Gate (T043)

SC-006 is **unmet**. The holdout has 3 scored repeats per arm on both tasks. The train side has 1 of 12 sessions, because the run was stopped after the cap overrun ($12.40 against $3). I did not start more billable sessions. `teardown` ran for SKILL-22 to SKILL-25, and `_ai_hub_leftovers` returns `[]`, so 139 is clean.

`pytest tests/e2e/skill_eval` gave 1295 passed, 22 skipped and 1 failed. The failure was SKILL-22's live check finding two `IadAihub139.Q23` classes left by an earlier run. That run had no `IAD_BINARY`, so the checks ran the Homebrew 1.4.2 binary from PATH, which predates B1. It leaked a license unit per call (LU 1 to 2 over 3 calls, measured) and put 139 into `<LICENSE LIMIT EXCEEDED>`. SKILL-23's teardown then fell back to docker exec, which refuses `{}`, and left its classes behind. After a restart, the four AI Hub checks passed on the rebuilt binary, and 139 stayed at LU=2. The 139 fixture now skips when `IAD_BINARY` is unset or missing (`test_the_139_tests_refuse_a_binary_from_path`).

## R11: Coverage (T044)

`scripts/coverage.sh` ran the instrumented suite with `--include-ignored`, serial, against iris-dev-iris and 139 (19 of the 139 CSP and tool-fix tests ran and passed). Result: 5516 passed, 1 failed.

- Core line coverage is 88.17% by raw lcov and 89.15% by `check-coverage-floors.py`, above the enforced 88%. The 85.00% baseline (2026-07-17) is up 3.2 points by raw lcov.
- New files: `csp_session.rs` 94.4%, floor set at 91. `error_hints.rs` got a floor of 97. `ws_session.rs` is at 78.4%, and `doc.rs` at 88.4%.
- The failure is `test_skill_facts_127_live::a_read_committed_read_of_a_locked_row_is_minus_114`. It saw `SQLCODE=-114 value=[]` under instrumentation and passed when run alone. It is a timing flake in a 130 test that 132 does not touch, so I changed nothing.

## Claim table

Filled during implementation. Columns: id, claim, source, verdict (holds / false / reworded / not taken), test, credit. The unit test parses this table.

| id  | claim                                                                                                                                                                                                                   | source                                                                                 | verdict   | test                                         | credit      |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | --------- | -------------------------------------------- | ----------- |
| H01 | `%ConfigStore.Configuration` `Create(area,type,subtype,name,details)` returns %Status; 139 adds six optional args after `details`                                                                                       | hackathon:ai-hub-config-store:references/config-store-reference.md:61                  | holds     | `aihub_139_class_inventory`                  | Gabriel Ing |
| H02 | `%ConfigStore.Configuration` `Get(area,type,subtype,name)` returns the config object; on 139 it is `Get(fqn, .config)` returning %Status, and four args raise `<PARAMETER>`                                             | hackathon:ai-hub-config-store:references/config-store-reference.md:89                  | false     | `aihub_139_agent_providerconfig`             | Gabriel Ing |
| H03 | `%ConfigStore.Configuration` `Delete` takes one dotted name, e.g. `AI.LLM.openai`                                                                                                                                       | hackathon:ai-hub-config-store:references/config-store-reference.md:96                  | holds     | `aihub_139_agent_providerconfig`             | Gabriel Ing |
| H04 | An empty subtype collapses: `("AI","LLM","","X")` is read back as `AI.LLM.X`                                                                                                                                            | hackathon:ai-hub-config-store:references/config-store-reference.md:22                  | holds     | `aihub_139_agent_providerconfig`             | Gabriel Ing |
| H05 | A config is named by area, type, optional subtype and name, joined with dots                                                                                                                                            | hackathon:ai-hub-config-store:references/config-store-reference.md:14                  | holds     | `aihub_139_agent_providerconfig`             | Gabriel Ing |
| H06 | Provisioning runs in %SYS; on 139 wallet and ConfigStore writes work from USER (only `Security.Resources` needs %SYS)                                                                                                   | hackathon:ai-hub-config-store:references/config-store-reference.md:34                  | reworded  | `aihub_139_agent_providerconfig`             | Gabriel Ing |
| H07 | `Security.Resources.Create` is called with one argument                                                                                                                                                                 | hackathon:ai-hub-config-store:references/config-store-reference.md:39                  | not taken | —                                            | Gabriel Ing |
| H08 | `%Wallet.Collection` `Create(name, {UseResource, EditResource})` returns %Status                                                                                                                                        | hackathon:ai-hub-config-store:references/config-store-reference.md:43                  | holds     | `aihub_139_agent_providerconfig`             | Gabriel Ing |
| H09 | `%Wallet.KeyValue` `Create("Collection.Key", {Usage:"CUSTOM", Secret:{...}})` returns %Status                                                                                                                           | hackathon:ai-hub-config-store:references/config-store-reference.md:53                  | holds     | `aihub_139_agent_providerconfig`             | Gabriel Ing |
| H10 | `secret://<Collection>.<Key>#<field>` in a config resolves from the wallet (`GetDetails(fqn,.d,1,1)`)                                                                                                                   | hackathon:ai-hub-config-store:references/config-store-reference.md:59                  | holds     | `aihub_139_agent_providerconfig`             | Gabriel Ing |
| H11 | A user without the collection's UseResource gets "Access denied" on resolve                                                                                                                                             | hackathon:ai-hub-config-store:references/config-store-reference.md:128                 | not taken | —                                            | Gabriel Ing |
| H12 | An LLM config holds `model_provider`, `model`, `api_key`; `temperature` not measured                                                                                                                                    | hackathon:ai-hub-config-store:references/config-store-reference.md:57                  | reworded  | `aihub_139_agent_providerconfig`             | Gabriel Ing |
| H13 | An MCP config holds `command`, `args`, `transport="stdio"`                                                                                                                                                              | hackathon:ai-hub-config-store:references/config-store-reference.md:67                  | not taken | —                                            | Gabriel Ing |
| H14 | LangChain `init_chat_model` loads configs by logical name from the connected namespace                                                                                                                                  | hackathon:ai-hub-langchain:references/langchain-reference.md:32                        | not taken | —                                            | Gabriel Ing |
| H15 | `%AI.Provider` `Create(name, settings)` is a class method returning a provider; `"openai"` is valid                                                                                                                     | hackathon:ai-hub-objectscript-sdk:references/objectscript-sdk-reference.md:16          | holds     | `aihub_139_agent_providerconfig`             | Gabriel Ing |
| H16 | `%AI.Agent` `%New(provider)` sets `Provider`                                                                                                                                                                            | hackathon:ai-hub-objectscript-sdk:references/objectscript-sdk-reference.md:18          | holds     | `aihub_139_agent_providerconfig`             | Gabriel Ing |
| H17 | `%AI.Agent` has properties `Model`, `SystemPrompt`, `Provider`, `ToolManager`                                                                                                                                           | hackathon:ai-hub-objectscript-sdk:references/objectscript-sdk-reference.md:19          | holds     | `aihub_139_class_inventory`                  | Gabriel Ing |
| H18 | The tool registry is `%AI.ToolMgr`, reached as `agent.ToolManager`                                                                                                                                                      | hackathon:ai-hub-objectscript-sdk:references/objectscript-sdk-reference.md:10          | holds     | `aihub_139_class_inventory`                  | Gabriel Ing |
| H19 | `CreateSession()` returns `%AI.Agent.Session`; 139 has one optional `config` arg                                                                                                                                        | hackathon:ai-hub-objectscript-sdk:references/objectscript-sdk-reference.md:22          | reworded  | `aihub_139_class_inventory`                  | Gabriel Ing |
| H20 | `Chat(session, input)` returns `%AI.LLM.Response`, which has `Content`                                                                                                                                                  | hackathon:ai-hub-objectscript-sdk:references/objectscript-sdk-reference.md:23          | holds     | `aihub_139_class_inventory`                  | Gabriel Ing |
| H21 | `Chat()` can be called without a session; on 139 `session` has no default                                                                                                                                               | hackathon:ai-hub-objectscript-sdk:SKILL.md:31                                          | false     | `aihub_139_class_inventory`                  | Gabriel Ing |
| H22 | Tools must be attached before `CreateSession()`                                                                                                                                                                         | hackathon:ai-hub-objectscript-sdk:references/objectscript-sdk-reference.md:149         | not taken | —                                            | Gabriel Ing |
| H23 | An agent subclass loads tools with `Parameter TOOLSETS` at `%Init()`                                                                                                                                                    | hackathon:ai-hub-objectscript-sdk:references/objectscript-sdk-reference.md:56          | holds     | `aihub_139_agent_providerconfig`             | Gabriel Ing |
| H24 | `XData INSTRUCTIONS` supplies the system prompt                                                                                                                                                                         | hackathon:ai-hub-objectscript-sdk:references/objectscript-sdk-reference.md:58          | not taken | —                                            | Gabriel Ing |
| H25 | `%OnInit()` is the subclass hook and `%Init()` calls it                                                                                                                                                                 | hackathon:ai-hub-objectscript-sdk:references/objectscript-sdk-reference.md:64          | holds     | `aihub_139_agent_providerconfig`             | Gabriel Ing |
| H26 | `Include %AI` compiles                                                                                                                                                                                                  | hackathon:ai-hub-objectscript-sdk:references/objectscript-sdk-reference.md:51          | holds     | `aihub_139_policies`                         | Gabriel Ing |
| H27 | `$$$AICoreToolAccessDenied` is defined in `%AI.inc`                                                                                                                                                                     | hackathon:ai-hub-policies:references/policies-reference.md:58                          | holds     | `aihub_139_policies`                         | Gabriel Ing |
| H28 | `%AI.System.StreamRenderer` exists; on 139 the class is `%AI.Shell.StreamRenderer`                                                                                                                                      | hackathon:ai-hub-objectscript-sdk:references/objectscript-sdk-reference.md:92          | false     | `aihub_139_class_inventory`                  | Gabriel Ing |
| H29 | `StreamChat(session, input, callbackObj, callbackMethod)` returns a Response; on 154 `callbackMethod` is gone and the callback extends `%AI.Shell.StreamRenderer`                                                       | hackathon:ai-hub-objectscript-sdk:references/objectscript-sdk-reference.md:95          | reworded  | `aihub_139_class_inventory`                  | Gabriel Ing |
| H30 | `ChatWithContent(session, content As %DynamicArray)`; the OpenAI part shapes are not measured                                                                                                                           | hackathon:ai-hub-objectscript-sdk:references/objectscript-sdk-reference.md:118         | reworded  | `aihub_139_class_inventory`                  | Gabriel Ing |
| H31 | `session.GetStats()` keys are `total_prompt_tokens`, `total_completion_tokens`, `total_tool_calls`                                                                                                                      | hackathon:ai-hub-objectscript-sdk:references/objectscript-sdk-reference.md:130         | not taken | —                                            | Gabriel Ing |
| H32 | `%AI.Policy.Authorization` `%CanExecute(tool, call, metadata) As %Status`; `tool` is the tool spec JSON, not a name; on 154 the first argument is `toolref`, the bare registered name                                   | hackathon:ai-hub-policies:references/policies-reference.md:18                          | reworded  | `aihub_139_policies`                         | Gabriel Ing |
| H33 | `%AI.Policy.Audit` `%LogExecution` has untyped arguments; on 139 all five are typed                                                                                                                                     | hackathon:ai-hub-policies:references/policies-reference.md:74                          | false     | `aihub_139_class_inventory`                  | Gabriel Ing |
| H34 | `%AI.Policy.Discovery` exists                                                                                                                                                                                           | hackathon:ai-hub-policies:references/policies-reference.md:9                           | holds     | `aihub_139_class_inventory`                  | Gabriel Ing |
| H35 | `%AI.Policy.ConsoleAudit` exists                                                                                                                                                                                        | hackathon:ai-hub-policies:references/policies-reference.md:118                         | holds     | `aihub_139_class_inventory`                  | Gabriel Ing |
| H36 | The call object has `.name`; `.arguments` not measured                                                                                                                                                                  | hackathon:ai-hub-policies:references/policies-reference.md:42                          | reworded  | `aihub_139_policies`                         | Gabriel Ing |
| H37 | Changing `call.arguments` in `%CanExecute` changes what the tool gets                                                                                                                                                   | hackathon:ai-hub-policies:references/policies-reference.md:61                          | not taken | —                                            | Gabriel Ing |
| H38 | `%AI.ToolMgr` `SetAuthPolicy(obj)` and `SetAuditPolicy(obj)` attach global policies                                                                                                                                     | hackathon:ai-hub-policies:references/policies-reference.md:103                         | holds     | `aihub_139_policies`                         | Gabriel Ing |
| H39 | `<Policies><Authorization Class=..>` child elements fill the policy's properties; on 139 a list with one item loads empty                                                                                               | hackathon:ai-hub-policies:references/policies-reference.md:112                         | reworded  | `aihub_139_policies`                         | Gabriel Ing |
| H40 | An XML-configured policy extends `%XML.Adaptor` with `XMLNAME` and `XMLPROJECTION`; that recipe works (not tested as a must)                                                                                            | hackathon:ai-hub-policies:references/policies-reference.md:124                         | reworded  | `aihub_139_policies`                         | Gabriel Ing |
| H41 | Global authorization runs, then ToolSet authorization, and both must allow                                                                                                                                              | hackathon:ai-hub-policies:references/policies-reference.md:137                         | not taken | —                                            | Gabriel Ing |
| H42 | `%AI.RAG.Embedding.FastEmbed` `Create()` takes no args; local, 384 dims, AllMiniLML6V2                                                                                                                                  | hackathon:ai-hub-rag:references/rag-reference.md:17                                    | holds     | `aihub_139_rag_fastembed`                    | Gabriel Ing |
| H43 | `%AI.RAG.Embedding.OpenAI` `Create(provider)`, 1536 dims                                                                                                                                                                | hackathon:ai-hub-rag:references/rag-reference.md:18                                    | not taken | —                                            | Gabriel Ing |
| H44 | `%AI.RAG.VectorStore.IRIS` has `TableName`, `Dimensions`, `ModelName`; `Build(promotedFields)` returns %Status                                                                                                          | hackathon:ai-hub-rag:references/rag-reference.md:27                                    | holds     | `aihub_139_rag_fastembed`                    | Gabriel Ing |
| H45 | Promoted field types are varchar(N), integer, float, boolean                                                                                                                                                            | hackathon:ai-hub-rag:references/rag-reference.md:66                                    | not taken | —                                            | Gabriel Ing |
| H46 | `Build()` makes the table and `<Table>_Config`; a rebuild with another model is refused                                                                                                                                 | hackathon:ai-hub-rag:references/rag-reference.md:134                                   | holds     | `aihub_139_rag_fastembed`                    | Gabriel Ing |
| H47 | `%AI.RAG.KnowledgeBase` has `Name`, `Description`, `TopK`; `Build(embedding, vectorStore)` returns %Status                                                                                                              | hackathon:ai-hub-rag:references/rag-reference.md:33                                    | holds     | `aihub_139_rag_fastembed`                    | Gabriel Ing |
| H48 | `AddDocument(text, metadata)` returns %Status; `AddDocuments([[text,meta],...])` returns a chunk count                                                                                                                  | hackathon:ai-hub-rag:references/rag-reference.md:45                                    | holds     | `aihub_139_rag_fastembed`                    | Gabriel Ing |
| H49 | `ReindexDocument(source, text, metadata)` returns a chunk count                                                                                                                                                         | hackathon:ai-hub-rag:references/rag-reference.md:99                                    | holds     | `aihub_139_rag_fastembed`                    | Gabriel Ing |
| H50 | A second `AddDocument` with the same source duplicates chunks; on 139 it replaces them                                                                                                                                  | hackathon:ai-hub-rag:references/rag-reference.md:59                                    | false     | `aihub_139_rag_fastembed`                    | Gabriel Ing |
| H51 | `kb.AddToAgent(agent)` registers a tool named `kb.Name` (params `query`, `top_k`)                                                                                                                                       | hackathon:ai-hub-rag:references/rag-reference.md:117                                   | holds     | `aihub_139_rag_fastembed`                    | Gabriel Ing |
| H52 | An MCP service extends `%AI.MCP.Service` with `Parameter SPECIFICATION = "<ToolSet>"`                                                                                                                                   | hackathon:ai-hub-mcp-server:references/mcp-server-reference.md:20                      | holds     | `aihub_139_mcp_bridge`                       | Gabriel Ing |
| H53 | A web app uses the `%AI.MCP.Service` subclass as dispatch class; on 139 it needs Type 18 (CSP + MCP)                                                                                                                    | hackathon:ai-hub-mcp-server:references/mcp-server-reference.md:11                      | reworded  | `aihub_139_mcp_bridge`                       | Gabriel Ing |
| H54 | The bridge reaches IRIS on the superserver port 1972, not HTTP                                                                                                                                                          | hackathon:ai-hub-mcp-server:references/mcp-server-reference.md:98                      | holds     | `aihub_139_mcp_bridge`                       | Gabriel Ing |
| H55 | `[[iris]]` takes `server{host,port,username,password}` and `endpoints[{path,username,password}]`; `pool` not measured                                                                                                   | hackathon:ai-hub-mcp-server:references/mcp-server-reference.md:44                      | reworded  | `aihub_139_mcp_bridge`                       | Gabriel Ing |
| H56 | Server creds and endpoint creds are separate; bad endpoint creds give 403                                                                                                                                               | hackathon:ai-hub-mcp-server:references/mcp-server-reference.md:104                     | not taken | —                                            | Gabriel Ing |
| H57 | Bridge placeholders are `@{env:VAR}` and `@{vault:path#field}`                                                                                                                                                          | hackathon:ai-hub-mcp-server:references/mcp-server-reference.md:120                     | not taken | —                                            | Gabriel Ing |
| H58 | ToolSet `<MCP><Remote Token="@{env.X}">` uses a dot                                                                                                                                                                     | hackathon:ai-hub-toolsets:references/toolsets-reference.md:174                         | not taken | —                                            | Gabriel Ing |
| H59 | Bridged tool names get a service prefix: `mcp_<path segments>_<tool>`; discovery without endpoints not measured                                                                                                         | hackathon:ai-hub-mcp-server:references/mcp-server-reference.md:111                     | reworded  | `aihub_139_mcp_bridge`                       | Gabriel Ing |
| H60 | With stdio transport, logging must go to a file                                                                                                                                                                         | hackathon:ai-hub-mcp-server:references/mcp-server-reference.md:56                      | not taken | —                                            | Gabriel Ing |
| H61 | HTTPS uses `[mcp.tls]`; the IRIS link uses `tls={ca_cert}`                                                                                                                                                              | hackathon:ai-hub-mcp-server:references/mcp-server-reference.md:84                      | not taken | —                                            | Gabriel Ing |
| H62 | OAuth passthrough is HTTP/HTTPS only                                                                                                                                                                                    | hackathon:ai-hub-mcp-server:SKILL.md:37                                                | not taken | —                                            | Gabriel Ing |
| H63 | The bridge has an `iris_status` tool; on 139 it is gone once an endpoint serves tools                                                                                                                                   | hackathon:ai-hub-mcp-server:SKILL.md:39                                                | reworded  | `aihub_139_mcp_bridge`                       | Gabriel Ing |
| H64 | `[WebMethod]` methods become tools and `Parameter DESCRIPTION` describes them; on 139 a plain class method is a tool, its doc comment is the description, and `%AI.Tool` has no DESCRIPTION                             | hackathon:ai-hub-toolsets:references/toolsets-reference.md:21                          | false     | `aihub_139_tool_and_query_tools`             | Gabriel Ing |
| H65 | `%AI.ToolSet` reads `XData Definition` with root `<ToolSet Name=..>` and children such as Description, Policies, Include, Query                                                                                         | hackathon:ai-hub-toolsets:references/toolsets-reference.md:41                          | holds     | `aihub_139_tool_and_query_tools`             | Gabriel Ing |
| H66 | A ToolSet that includes another class needs `DependsOn`                                                                                                                                                                 | hackathon:ai-hub-toolsets:references/toolsets-reference.md:39                          | not taken | —                                            | Gabriel Ing |
| H67 | `<Tool Name= Method=>` binds an instance method on the ToolSet                                                                                                                                                          | hackathon:ai-hub-toolsets:references/toolsets-reference.md:64                          | not taken | —                                            | Gabriel Ing |
| H68 | `<Query Name Arguments="a As %Integer, b As %String = ''" MaxRows>` with `:named` params                                                                                                                                | hackathon:ai-hub-toolsets:references/toolsets-reference.md:88                          | holds     | `aihub_139_tool_and_query_tools`             | Gabriel Ing |
| H69 | Query arg `%Integer` maps to JSON `number`; on 139 it is `integer`                                                                                                                                                      | hackathon:ai-hub-toolsets:references/toolsets-reference.md:112                         | false     | `aihub_139_tool_and_query_tools`             | Gabriel Ing |
| H70 | Query args without a default are required                                                                                                                                                                               | hackathon:ai-hub-toolsets:references/toolsets-reference.md:116                         | holds     | `aihub_139_tool_and_query_tools`             | Gabriel Ing |
| H71 | Compile fails for `?` placeholders and for `:param` missing from Arguments                                                                                                                                              | hackathon:ai-hub-toolsets:references/toolsets-reference.md:122                         | holds     | `aihub_139_query_tool_compile_errors`        | Gabriel Ing |
| H72 | Filters `<Include Class>` and `<Exclude Tool>` work; `Exclude Match` and `Requirement` not measured                                                                                                                     | hackathon:ai-hub-toolsets:references/toolsets-reference.md:160                         | reworded  | `aihub_139_tool_and_query_tools`             | Gabriel Ing |
| H73 | `<MCP><Remote URL AuthType Token>` embeds remote MCP tools                                                                                                                                                              | hackathon:ai-hub-toolsets:references/toolsets-reference.md:171                         | not taken | —                                            | Gabriel Ing |
| H74 | The query result envelope is `rows`, `row_count`, `truncated`, `elapsed_ms`; 139 adds `columns`                                                                                                                         | hackathon:ai-hub-toolsets:references/toolsets-reference.md:192                         | reworded  | `aihub_139_tool_and_query_tools`             | Gabriel Ing |
| H75 | The row cap is `MaxRows`, then `Parameter QUERYMAXROWS` (100)                                                                                                                                                           | hackathon:ai-hub-toolsets:references/toolsets-reference.md:193                         | holds     | `aihub_139_tool_and_query_tools`             | Gabriel Ing |
| H76 | `%AI.ToolMgr` `AddTool(obj)` takes an instance                                                                                                                                                                          | hackathon:ai-hub-toolsets:references/toolsets-reference.md:194                         | holds     | `aihub_139_tool_and_query_tools`             | Gabriel Ing |
| H77 | `%AI.SubAgent.Create(parent, prompt, x)`; on 139 it is `%AI.Agent.SubAgent` `Create(parentAgent, systemPrompt, config)`                                                                                                 | hackathon:ai-hub-subagents-and-skills:references/subagents-and-skills-reference.md:15  | false     | `aihub_139_class_inventory`                  | Gabriel Ing |
| H78 | The sub-agent has `Run`, `Chat`, `CreateSession`; on 139 `Create` returns a `%AI.Agent`, which has them                                                                                                                 | hackathon:ai-hub-subagents-and-skills:references/subagents-and-skills-reference.md:22  | reworded  | `aihub_139_class_inventory`                  | Gabriel Ing |
| H79 | `%AI.Skill` declares tools with `Parameter TOOLS`; on 139 the class is `%AI.Agent.Skill`                                                                                                                                | hackathon:ai-hub-subagents-and-skills:references/subagents-and-skills-reference.md:59  | reworded  | `aihub_139_class_inventory`                  | Gabriel Ing |
| H80 | A skill has `XData SUMMARY` (YAML) and `XData INSTRUCTIONS`                                                                                                                                                             | hackathon:ai-hub-subagents-and-skills:references/subagents-and-skills-reference.md:61  | not taken | —                                            | Gabriel Ing |
| H81 | `%AI.Skill` has `ParentAgent`; on 139 `ParentAgent` is on `%AI.Agent`, not `%AI.Agent.Skill`                                                                                                                            | hackathon:ai-hub-subagents-and-skills:references/subagents-and-skills-reference.md:94  | false     | `aihub_139_class_inventory`                  | Gabriel Ing |
| H82 | `%AI.Agent.Skill` `ExportSkill(target)` returns a `%String` path; the files it writes not measured                                                                                                                      | hackathon:ai-hub-subagents-and-skills:references/subagents-and-skills-reference.md:108 | reworded  | `aihub_139_class_inventory`                  | Gabriel Ing |
| H83 | `GetSkillFromURI(uri[, skillName])`; on 139 it is `%AI.Agent.Skill` `GetSkillFromURI(uri, subpath, cacheDir, authProvider)`                                                                                             | hackathon:ai-hub-subagents-and-skills:references/subagents-and-skills-reference.md:124 | false     | `aihub_139_class_inventory`                  | Gabriel Ing |
| M1  | `%ConfigStore.Configuration` `Get` takes four args and returns the object                                                                                                                                               | upstream:Config_Store_Guide.md:154                                                     | false     | `aihub_139_agent_providerconfig`             | ai-hub-eap  |
| M2  | `%ConfigStore.Configuration` `Delete` also takes four args                                                                                                                                                              | upstream:Config_Store_Guide.md:175                                                     | false     | `aihub_139_agent_providerconfig`             | ai-hub-eap  |
| M3  | `PROVIDERCONFIG` takes a bare config name or the `@{prefix.key}` dot form; 139 refuses both, only `@{config:Name}` and `@{config:AI.LLM.Name}` work                                                                     | upstream:ObjectScript_SDK_Guide.md:250                                                 | false     | `aihub_139_agent_providerconfig`             | ai-hub-eap  |
| M4  | `%New()` alone is enough; on 139 `Provider` stays empty until `%Init()`                                                                                                                                                 | upstream:ObjectScript_SDK_Guide.md:713                                                 | false     | `aihub_139_agent_providerconfig`             | ai-hub-eap  |
| M5  | `%AI.Policy.ConsoleAudit` in a ToolSet breaks MCP `tools/call`; on 139 a ConsoleAudit subclass serves over the bridge                                                                                                   | upstream:MCP_Server_Guide.md:959                                                       | false     | `aihub_139_mcp_bridge`                       | ai-hub-eap  |
| M6  | The `%OnInit` guard `If ..Provider = "" && ..#MODELCONFIGNAME '= ""` keeps a caller's provider; unparenthesised it is always true and replaces it                                                                       | upstream:skills/aihub-eap/SKILL.md:148                                                 | false     | `aihub_139_agent_providerconfig`             | ai-hub-eap  |
| M7  | The guide says to use the service as a web app's dispatch class but gives no app Type; 139 refuses Type 16, and a Type 2 app serves no tools                                                                            | upstream:MCP_Server_Guide.md:136                                                       | reworded  | `aihub_139_mcp_bridge`                       | ai-hub-eap  |
| M8  | `<Authorization Class>` child elements configure the policy; a list with one item loads empty on 139                                                                                                                    | upstream:ObjectScript_SDK_Advanced.md:364                                              | reworded  | `aihub_139_policies`                         | ai-hub-eap  |
| O1  | The installed build is 2026.3.0AI Build 139 and USER sees at least 60 `%AI` classes                                                                                                                                     | own                                                                                    | holds     | `aihub_139_class_inventory`                  | —           |
| O2  | `%AI.Agent` `%Init`, `Run`, `UseToolSet`, `UseSkill`, `CreateSubAgent` signatures; `%AI.Agent.Session` `GetStats()` returns a `%DynamicObject`                                                                          | own                                                                                    | holds     | `aihub_139_class_inventory`                  | —           |
| O3  | `%AI.ToolMgr` `ExecuteTool(name, args)` returns `{timing, value}`; `RegisterToolSet`, `SetDiscoveryPolicy` exist; no `GetToolSpecs`                                                                                     | own                                                                                    | holds     | `aihub_139_tool_and_query_tools`             | —           |
| O4  | `%AI.Tool` `%Discover()` returns `{tools:[...]}`; `%AI.ToolMgr` `%Discover()` returns a bare array                                                                                                                      | own                                                                                    | holds     | `aihub_139_rag_fastembed`                    | —           |
| O5  | `%AI.Utils.SettingStore` exists and `Expand("@{config:Name}")` reads a ConfigStore entry                                                                                                                                | own                                                                                    | holds     | `aihub_139_agent_providerconfig`             | —           |
| O6  | `%AI.RAG.Embedding` is the embedding base class `Build` takes                                                                                                                                                           | own                                                                                    | holds     | `aihub_139_class_inventory`                  | —           |
| O7  | `%AI.Shell.StreamRenderer` exists                                                                                                                                                                                       | own                                                                                    | holds     | `aihub_139_class_inventory`                  | —           |
| O8  | `%AI.LLM.Response` has `Content`, `ToolCalls`, `Usage`                                                                                                                                                                  | own                                                                                    | holds     | `aihub_139_class_inventory`                  | —           |
| O9  | A real turn with a wallet-backed `%ConfigStore.Configuration` entry calls the agent's tool; the key never appears in output                                                                                             | own                                                                                    | holds     | `aihub_139_real_turn`                        | —           |
| O10 | With no web gateway, `docker_only` `iris_execute` reads `%Dictionary.CompiledMethod` for `%AI.Agent` `Chat`                                                                                                             | own                                                                                    | holds     | `aihub_139_docker_only_reads_the_dictionary` | —           |
| O11 | The bridge's `initialize` instructions name a `test_Add` example that is not on the instance; the tool result is JSON text                                                                                              | own                                                                                    | holds     | `aihub_139_mcp_bridge`                       | —           |
| O12 | `%AI.Agent.SubAgent` `Create(parentAgent, systemPrompt, config)` is a class method returning `%AI.Agent`                                                                                                                | own                                                                                    | holds     | `aihub_139_class_inventory`                  | —           |
| O13 | `%AI.Agent` `%OnInit` with each comparison parenthesised keeps a caller's provider                                                                                                                                      | own                                                                                    | holds     | `aihub_139_agent_providerconfig`             | —           |
| O14 | `%AI.Policy.Audit` `%LogExecution(call, metadata, result, duration, status)` with typed args, returning %Status                                                                                                         | own                                                                                    | holds     | `aihub_139_class_inventory`                  | —           |
| O15 | A fresh 139 or 154 instance has an empty descriptor registry, so `AI.LLM` Create fails with #26414 until `%ConfigStore.DescriptorManager` `RebuildRegistry()` runs; then an `openai` entry without `api_key` is refused | own                                                                                    | holds     | `aihub_139_agent_providerconfig`             | —           |
| O16 | On 154 `%ConfigStore.Configuration` `Create` defaults `readResource` and `editResource` to `$$$AdminConfigStoreResourceName` (empty on 139)                                                                             | own                                                                                    | holds     | `aihub_139_class_inventory`                  | —           |
