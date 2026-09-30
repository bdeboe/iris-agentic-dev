# Research: 132 AI Hub on EAP build 139

Measured 2026-09-30 on `iad-aihub-iris` unless marked otherwise. Anything not measured is labelled that way.

## R1: How iad reaches 139

**Decision**: `docker_only = true`. Tests load fixtures with `docker cp` + `$system.OBJ.Load` and read claims through iad `iris_execute` on the docker path. The ladder waits on a license key.

**Measured**:

- `WebServer=0`, no `/usr/irissys/httpd`, and host 52781 (mapped to 52773) does not answer.
- messages.log at startup:
  - `LMF Error: No valid license key. No valid local file found and LicenseID not defined.`
  - `Not licensed for Interoperability, auto-start skipped.`
- `$SYSTEM.License.LUAvailable()=0` and `LUConsumed()=1` with one `iris session` open. So the instance has one license unit.
- A Web Gateway sidecar (`containers.intersystems.com/intersystems/webgateway:2026.2`, arm64) was pointed at the IRIS container's bridge IP, port 1972, as CSPSystem/SYS, with host port 52782. `/csp/sys/UtilHome.csp` returned 200, so the gateway reached IRIS. `/api/atelier/` and `/api/mgmnt/` with `_SYSTEM:SYS` returned 503 `Service Unavailable` on every try. The gateway itself logged no error. My reading is that the authenticated login needs a license unit and none is free. That is inferred from the unit counts, not proven by an IRIS log line.
- IRIS logged `Web Gateway version 2602.1863 has connected … You should upgrade the Web Gateway`, a warning only.
- `docker network create` failed (`all predefined address pools have been fully subnetted`), so the sidecar used the default bridge by IP. A compose file with its own network would need a pool freed first.

**Alternatives**:

- Gateway sidecar now. Rejected: it returns 503.
- Run 139 on the ladder under `docker_only`. Rejected: `apply_documents`, `list_classes` and `reset_documents` in `graded_task.py` all call `iris_doc`, and the agent would have no way to write a class. Every task would fail on the plumbing, which measures nothing about AI Hub.
- Use another project's 2026.3 container (irispython-dx runs build 154). Rejected: the containers are project-exclusive, and it has no web server either.

**Unblock recipe (for when a key arrives)**: mount `iris.key` into `/usr/irissys/mgr/`, restart, check `LUAvailable()>1`, then run the sidecar from `quickstart.md` on 52781 (recreate IRIS with only 11976 mapped), and set the registry `web_port: 52781`. The gateway config I used is in quickstart.md.

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

- The docs describe build 162. Nothing mentions 139 or 2026.3.
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
- **Not measured yet**:
  - a TCP login on 11976
  - whether ConfigStore writes work from USER or need %SYS
  - whether an unlicensed instance makes an outbound provider call
  - the `%AI.MCP.Service` UrlMap

Each of these becomes a live test.

## R5: Mismatch candidates (to prove or drop by live test)

| #   | Doc                                                      | Doc says                                                            | 139 inventory says                                                             | Test                           |
| --- | -------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ------------------------------ |
| M1  | `Config_Store_Guide.md` (4-arg `Get`)                    | `Get` takes four args and returns an object                         | `Get(fqn, *config)`, two args, with an output parameter                        | `configstore_get_signature`    |
| M2  | `Config_Store_Guide.md:167` vs `:174`                    | `Delete` with one arg in one place, four in another                 | `Delete(fqn)`                                                                  | `configstore_delete_signature` |
| M3  | `ObjectScript_SDK_Guide.md:250`, `:2571`, `:670`         | `PROVIDERCONFIG` as a bare name, as `@{config:...}`, and "dot" form | to measure                                                                     | `providerconfig_forms`         |
| M4  | `ObjectScript_SDK_Guide.md:713` vs `:657`                | `%New()` alone is enough / `%Init()` is required                    | `%Init` runs `%CreateProvider` … `%OnInit`, so `%New` alone leaves no provider | `agent_new_without_init`       |
| M5  | `MCP_Server_Guide.md:959` vs hackathon `ai-hub-policies` | `ConsoleAudit` breaks MCP `tools/call` / the policies skill uses it | to measure                                                                     | `console_audit_with_mcp`       |

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

## Claim table

Filled during implementation. Columns: id, claim, source, verdict (holds / false / reworded / not taken), test, credit. The unit test parses this table.

| id  | claim | source | verdict | test | credit |
| --- | ----- | ------ | ------- | ---- | ------ |
