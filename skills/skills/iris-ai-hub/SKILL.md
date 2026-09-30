---
name: iris-ai-hub
author: tdyar
version: 0.2.0
managed_by: iris-agentic-dev
description: "IRIS AI Hub (%AI.* classes, EAP builds): where the upstream docs are and which file covers what, how to check them against the installed build, and the %AI.Agent / %AI.Tool / %AI.ToolSet / ConfigStore / Wallet / MCP server facts measured on 2026.3.0AI build 139. Load when building or debugging AI Hub agents, tools, providers or MCP servers."
source: >-
  ai-hub-eap master 72749d6dbf0b856a60775378fa88d346bb79d4e4;
  ready-hackathon-dev-template 391c3d5 ai-hub-* skills by Gabriel Ing
---

# iris-ai-hub

AI Hub (`%AI.*`) ships only in Early Access builds, and each build changes names and signatures. Read the docs for concepts; read the installed classes for names. This skill says where each is.

## Where the docs are

- Repo: `https://github.com/intersystems-community/ai-hub-eap`, branch `master`.
- Read a file raw: `https://raw.githubusercontent.com/intersystems-community/ai-hub-eap/master/<path>`.
- The repo moves. Check its current state (latest commit, whether the file you want still exists) before relying on a file; the map below was recorded at `72749d6` (2026-09-09), when the docs described build 162.
- If GitHub is unreachable, skip the docs and work from the installed `%AI` classes alone (workflow step 2). Say that you did.

## Topic map

| Topic       | File                           |
| ----------- | ------------------------------ |
| ConfigStore | `Config_Store_Guide.md`        |
| MCP         | `MCP_Server_Guide.md`          |
| MCP         | `MCP_Server_Examples.md`       |
| SDK         | `ObjectScript_SDK_Guide.md`    |
| SDK         | `ObjectScript_SDK_Advanced.md` |
| SDK         | `ObjectScript_SDK_Examples.md` |
| LangChain   | `langchain_SDK.md`             |
| Samples     | `objectscript/cls/`            |

The SDK guide is over 3,000 lines. Fetch it once and search it for the class you need; do not read it top to bottom.

## Workflow

1. Read the build: `iris_info` with `what: "metadata"` (the `version` field), or `Write $ZVERSION` through `iris_execute`. Note the build number (for example `2026.3.0AI (Build 139U)`).
2. Read the installed `%AI` classes for the part you are about to use: `iris_symbols` or `docs_introspect` on the class, or `iris_query` on `%Dictionary.CompiledClass` / `%Dictionary.CompiledMethod` for names and signatures.
3. Fetch the doc file for the topic from the map above and read it for the concept and the calling pattern.
4. Where the doc and the installed class disagree, the installed classes win. Write the code against the installed signature, and tell the user which doc line disagrees with which build.
5. Compile with `iris_doc` (`mode: "put"`, `compile: true`) and run it before calling it done.

## No web gateway

Some AI builds ship without a web server (no private web server, and on Enterprise AI builds no gateway either). Then iad runs `docker_only = true` against the container, and only `iris_execute` and `iris_compile` work: `iris_doc`, `iris_symbols` and `docs_introspect` need Atelier REST and return `NOPWS_ATELIER_REQUIRED`.

Read class metadata through `iris_execute` instead, with SQL over `%Dictionary.CompiledClass` and `%Dictionary.CompiledMethod`:

```objectscript
Set rs = ##class(%SQL.Statement).%ExecDirect(, "SELECT Name, FormalSpec FROM %Dictionary.CompiledMethod WHERE parent = ?", "%AI.Agent")
While rs.%Next() { Write rs.Name, "(", rs.FormalSpec, ")", ! }
```

Do not name `%Dictionary.ClassDefinition` or `%Dictionary.MethodDefinition` in `iris_execute` code: iad blocks every `%Dictionary.*Definition` reference there, reads included (`CODE_EDIT_BLOCKED`).

## What holds on 2026.3

## Corrections

## Upstream's own skill

ai-hub-eap carries its own agent skill. Read it raw: `https://raw.githubusercontent.com/intersystems-community/ai-hub-eap/master/skills/aihub-eap/SKILL.md`. It describes build 162; check what it says against the installed classes as in the workflow above.

`skill_community` cannot install it: iad subscribes to a repo through an `iris-agentic-dev.toml` at the repo root, and ai-hub-eap has none.
