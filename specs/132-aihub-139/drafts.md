# Drafts: ai-hub-eap docs against build 139

Each `D` entry is a place where the ai-hub-eap docs at `72749d6` say one thing and IRISHealth 2026.3.0AI.139.0 does another. The named live test in `crates/iris-agentic-dev-core/tests/integration/test_aihub_139_live.rs` shows what 139 does. The `B` entries are iad bugs found along the way.

Nothing here is filed. Tom files, or does not.

M5 (`MCP_Server_Guide.md:959`, ConsoleAudit over MCP) is not here: the test did not reproduce it. See research.md R5.

## D1: ConfigStore `Get` takes the full name, not four parts

- Doc: `Config_Store_Guide.md:154`
- Doc says: `Get("AI", "LLM", "", "openai")` returns the configuration object.
- 139 does: `Get` takes the full name and an output argument, `Get("AI.LLM.openai", .config)`, and returns a `%Status`. The four-argument call raises `<PARAMETER>`.
- Test: `aihub_139_agent_providerconfig`
- Status: drafted

Draft upstream text:

> Config_Store_Guide.md, "Retrieving Configurations" (line 154) and Example 3 (line 298) call `Get` with four arguments and use the return value as the object. On 2026.3.0AI.139.0 that call raises `<PARAMETER>`. The signature there is `Get(name, .config) As %Status`, where `name` is the full dotted name:
>
> ```objectscript
> Set sc = ##class(%ConfigStore.Configuration).Get("AI.LLM.openai", .config)
> $$$ThrowOnError(sc)
> ```
>
> Example 3's `If llmConfig = ""` check needs the same change: test the status, not the object.

## D2: ConfigStore `Delete` has no four-argument form

- Doc: `Config_Store_Guide.md:175`
- Doc says: `Delete("AI", "LLM", "", "openai")` works as well as `Delete("AI.LLM.openai")`.
- 139 does: the four-argument call raises `<PARAMETER>` and the entry stays. `Delete("AI.LLM.openai")` removes it.
- Test: `aihub_139_agent_providerconfig`
- Status: drafted

Draft upstream text:

> Config_Store_Guide.md, "Deleting Configurations", offers a "full parameter syntax" for `Delete` (line 175). On 2026.3.0AI.139.0 that call raises `<PARAMETER>` and the configuration is still there afterwards. Only the one-argument form, `Delete("AI.LLM.openai")`, works. I would drop the second block.

## D3: `PROVIDERCONFIG` needs `@{config:Name}`

- Doc: `ObjectScript_SDK_Guide.md:250`
- Doc says: `Parameter PROVIDERCONFIG = "MyConfigName";` names the config. The parameter table (line 670) gives the placeholder syntax as `@{prefix.key}`.
- 139 does: a bare name fails `%Init()` with `ProviderConfigError: PROVIDERCONFIG is invalid`, and so does `@{config.MyConfigName}` read literally from the table. `@{config:MyConfigName}` and `@{config:AI.LLM.MyConfigName}` both work.
- Test: `aihub_139_agent_providerconfig`
- Status: drafted

Draft upstream text:

> ObjectScript_SDK_Guide.md line 250 sets `Parameter PROVIDERCONFIG = "MyConfigName";`. On 2026.3.0AI.139.0, `%Init()` on that class returns `ProviderConfigError: PROVIDERCONFIG is invalid`. What works is `"@{config:MyConfigName}"`, the form the table at line 670 uses in its example column.
>
> The same table describes the syntax as `@{prefix.key}`. Read literally, that gives `@{config.MyConfigName}`, which fails the same way. `@{prefix:key}` would match the examples.

## D4: `%New()` alone leaves `Provider` empty

- Doc: `ObjectScript_SDK_Guide.md:713`
- Doc says: because the class already sets the provider parameter, `%New()` is enough, with no `%Init()` in that step.
- 139 does: after `%New()`, `Provider` is empty. `%Init()` builds it from `PROVIDERCONFIG`. Line 657 in the same guide does call `%Init()`.
- Test: `aihub_139_agent_providerconfig`
- Status: drafted

Draft upstream text:

> ObjectScript_SDK_Guide.md step 2 (line 713) says that since the agent class names its provider, `%New()` is all you need. On 2026.3.0AI.139.0, `agent.Provider` is empty after `%New()` and the first call fails. The provider is built in `%Init()`, which the earlier example at line 657 does call. Step 2 needs `$$$ThrowOnError(agent.%Init())` after `%New()`.

## D5: the `%OnInit` guard in the skill needs parentheses

- Doc: `skills/aihub-eap/SKILL.md:148`
- Doc says: `If ..Provider = "" && ..#MODELCONFIGNAME '= "" {` builds a provider only when the caller did not pass one.
- 139 does: ObjectScript evaluates strictly left to right, so the test is `((..Provider = "") && ..#MODELCONFIGNAME) '= ""`, which is always true. A provider passed to `%New()` is replaced. `If (..Provider = "") && (..#MODELCONFIGNAME '= "")` keeps it.
- Test: `aihub_139_agent_providerconfig`
- Status: drafted

Draft upstream text:

> skills/aihub-eap/SKILL.md line 148: `If ..Provider = "" && ..#MODELCONFIGNAME '= "" {`. ObjectScript has no operator precedence, so this reads as `((..Provider = "") && ..#MODELCONFIGNAME) '= ""` and is always true. On 2026.3.0AI.139.0, an agent created with `%New(provider)` gets its provider replaced by the one from `MODELCONFIGNAME`. With parentheses it behaves as intended:
>
> ```objectscript
> If (..Provider = "") && (..#MODELCONFIGNAME '= "") {
> ```

## D6: an MCP server created in code needs web app Type 18

- Doc: `MCP_Server_Guide.md:136`
- Doc says: create the MCP server in the Management Portal under Security > Applications > MCP Servers. The guide gives no scripted route.
- 139 does: a `Security.Applications` entry with the `%AI.MCP.Service` subclass as dispatch class must have Type 18 (CSP + MCP). Type 16 is refused with a message about the CSP bit. Type 2 is accepted, but `iris-mcp-server` gets no tools from it and logs "failed identity checking".
- Test: `aihub_139_mcp_bridge`
- Status: drafted

Draft upstream text:

> MCP_Server_Guide.md step 2 (line 136) creates the MCP server through the Management Portal only. Anyone setting it up in a script or a container build will reach for `Security.Applications`. On 2026.3.0AI.139.0 that works with `Type = 18`. Type 16 is refused because the CSP bit is missing. Type 2 saves fine, but `iris-mcp-server` then reports "failed identity checking" and lists no tools. One line in step 2 would save people the search: when you create the application in code, set `Type` to 18.

## D7: a policy list with one XML child loads empty

- Doc: `ObjectScript_SDK_Advanced.md:364`
- Doc says: child elements of `<Authorization Class="...">` set the policy's properties, with a repeated element filling a list (`<AllowedPath>` twice).
- 139 does: two children give a list of two. A single child gives an empty list, so a policy with one `<Blocked>` tool blocks nothing. `%XML.Reader` reads the same one-child XML as a list of one, so the ToolSet loader drops it.
- Test: `aihub_139_policies`
- Status: drafted

Draft upstream text:

> ObjectScript_SDK_Advanced.md line 364 shows list properties set from repeated child elements. On 2026.3.0AI.139.0 that works with two or more children. With exactly one, for example a deny policy with a single `<Blocked>Reverse</Blocked>`, the list is empty after the ToolSet loads, and the tool runs. `%XML.Reader` correlating the same XML to the same class gives `Count() = 1`, so this looks like the ToolSet policy loader, not the class. Worth a fix, or a note in the guide until then.

## D8: add an `iris-agentic-dev.toml` so `skill_community` can install the skill (FR-008)

- Doc: `README.md`
- Doc says: the repo ships `skills/aihub-eap/SKILL.md` for agents to use.
- 139 does: not a 139 question. iris-agentic-dev's `skill_community install` only copies skills it loaded at startup through `mcp --subscribe`, and `--subscribe` reads the repo's `iris-agentic-dev.toml`. ai-hub-eap has none, so iad users cannot install the skill with it and have to fetch the raw file.
- Test: `aihub_139_upstream_files`
- Status: drafted

Draft upstream text:

> Would you take a small `iris-agentic-dev.toml` at the repo root? With it, people using iris-agentic-dev can subscribe to this repo and install `aihub-eap` with `skill_community`, and pick up changes when you push them. Today they have to copy the raw SKILL.md by hand. iad reads it from `HEAD` and fetches each listed directory's `SKILL.md`. The whole file is:
>
> ```toml
> [provides]
> skills = ["skills/aihub-eap"]
> ```
>
> I can open the PR if that helps.

## B1: each iad process leaks three CSP sessions on /api/atelier

- Doc: none, iad code: `crates/iris-agentic-dev-core/src/tools/mod.rs` builds `client` and `exec_client` with `IrisConnection::http_client()`, and the startup probe builds a third with `probe_client()`.
- Doc says: n/a
- 139 does: each client has its own cookie jar, so each one opens its own CSP session. None logs out when the process exits. The sessions live out the web app's 3600 s timeout, and each holds a license unit. On 139's 128-LU key, one run of the live suite costs about 30 LU. Two or three runs in an hour exhaust the key, and every later request gets a license error until `docker restart`.
- Test: none yet. Measured by hand with `$System.License.LUConsumed()` before and after a run (quickstart.md, "License units").
- Status: drafted

Draft upstream text:

> iad opens three CSP sessions per process on `/api/atelier` (probe, `client`, `exec_client`, each with its own cookie jar) and never ends them. On a licensed instance each session holds a license unit for the web app's session timeout. Fix: share one `reqwest` cookie jar across the three clients, and on shutdown send one request with `CacheLogout=1` so IRIS ends the session. Test: a binary test that spawns iad against a live instance, reads `LUConsumed()` before and after, and asserts it goes back to where it was.
