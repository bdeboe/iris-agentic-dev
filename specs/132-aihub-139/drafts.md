# Drafts: ai-hub-eap docs against build 139

Each `D` entry is a place where the ai-hub-eap docs at `72749d6` say one thing and IRISHealth 2026.3.0AI.139.0 does another. The named live test in `crates/iris-agentic-dev-core/tests/integration/test_aihub_139_live.rs` shows what 139 does. The `B` entries are iad bugs found along the way; B1 to B3 are fixed here, not drafted.

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

## B1: each iad process leaked two or three CSP sessions on /api/atelier

- Doc: none. iad code: `crates/iris-agentic-dev-core/src/tools/mod.rs` built `client` and `exec_client` with `IrisConnection::http_client()`, and the startup probe built a third client with `probe_client()`.
- Doc says: n/a
- 139 did: each client had its own cookie jar, so each one opened its own CSP session, and none logged out when the process exited. The sessions lived out the web app's 3600 s timeout. Ten `iad exec` calls took `^%cspSession` on 139 from 15 to 35, and two ladder tasks ran the 128-LU key into `<LICENSE LIMIT EXCEEDED>` (HTTP 503). After that, `exec` fell back to docker exec, which refuses `{}` blocks.
- Test: `test_csp_session_132` (unit) and `test_csp_logout_132` (live, bin crate). Before the fix, 5 `exec` calls left 10 sessions, a failed `exec` left 2, and an MCP server stopped by SIGTERM left 3. After the fix, all three leave none.
- Status: fixed in iad, 132. Every client takes one process-wide cookie store (`iris::csp_session`). The store records each `CSPSESSIONID-*` cookie's path, and `main` and `crate::exit` send `?IRISLogout=end` to each path before the process exits. IRIS ends the session and answers 401. The cookie alone is enough, so no credentials are sent.

## B2: `iris_execute_method` handed back an error %Status as raw bytes

- Doc: none. iad code: `handle_iris_execute_method` in `crates/iris-agentic-dev-core/src/tools/doc.rs` wrote the method's return value as it was and took the first line.
- Doc says: n/a
- 139 did: an error %Status is `"0 "` followed by a `$List`, so `Security.Applications.Create` failing came back as `{"return_value":"0 \u0000+\u0004","success":true}`. In the holdout ladder, SKILL-24 tools repeat 0 made 17 such calls (calls 6-10, 12, 19-26). It never saw the error text and ended without the web app.
- Test: `test_tool_fixes_132` (unit) and `test_tool_fixes_132_live` (live). `%Library.Integer:IsValid("abc")` returned the raw status before the fix. After it, the call answers `success: false`, `METHOD_RETURNED_ERROR`, with `ERROR #7207`.
- Status: fixed in iad, 132. The generator code checks for `"0 "` followed by a valid `$List` and writes `$System.Status.GetErrorText` behind a marker. A plain value that starts with `"0 "` is still a value.

## B3: `iris_ws_exec` sent multi-line code as one terminal input

- Doc: none. iad code: `WsSessionPool::exec` in `crates/iris-agentic-dev-core/src/iris/ws_session.rs` sent `code` in one `prompt` frame.
- Doc says: n/a
- 139 did: the terminal read the first newline as part of line 1, so each multi-line call answered `<SYNTAX>` `Expected end of line` on its first line. SKILL-24 tools+iris-ai-hub repeat 0 spent calls 51-68 on this. It rewrote the same `Set tApp=...` block 18 ways, none of which could work.
- Test: `test_tool_fixes_132` (unit) and `test_tool_fixes_132_live` (live). `Set tA=1\nSet tB=2\nWrite tA+tB` answered `<SYNTAX>` before the fix and `3` after it.
- Status: fixed in iad, 132. Each non-blank line goes to the terminal as its own input, as a pasted block would.

Both ladder runs in `research.md` used the binary from before B2 and B3 were fixed. A re-run would show whether SKILL-24 changes.
