# Getting started

Fifteen minutes from nothing to an agent that can read and write ObjectScript on your IRIS
instance. Six steps, each one ending in output you can compare against what is printed here.

The order is deliberate. Three of the four common ways to fail happen before your editor is
involved at all, so this checks the binary before the connection, and the connection before
the editor. If you skip to step 6 and it does not work, you will not know which of the three
went wrong.

Every command below was run against `iris-community:2026.2` on the way to writing this, and
`tests/e2e/test_getting_started.py` checks that each subcommand, tool and argument named here
still exists.

## What you need

- IRIS with the Atelier REST API reachable over HTTP. A community Docker image has it; so does
  native IRIS on IIS or Apache. Enterprise IRIS without a Web Gateway does not — see
  [connecting.md](connecting.md).
- Credentials for a user that can read the namespace you care about.
- An editor with MCP support, for step 6 only. Steps 1–5 need nothing but a terminal.

## Step 1 — Install, and confirm what you installed

```bash
brew tap intersystems-community/iris-agentic-dev
brew install iris-agentic-dev
iris-agentic-dev --version
```

```text
iris-agentic-dev 1.4.2
```

Linux, direct download and Windows are in the README's [Install](../README.md#install)
section. One binary, no runtime, no Python or Node.

## Step 2 — Prove the binary works, with no IRIS at all

```bash
iris-agentic-dev tool --list
```

```text
agent_history                  Return recent tool call history for this session.
agent_stats                    Return learning agent status: skill count, pattern count, KB size.
capability_matrix              Show the roles assigned to a user on an IRIS instance.
check_config                   Return the active IRIS connection state without making any IRIS network calls.
...
```

Eighty-one lines. This reads the tool router and opens no connection, so it works with IRIS
down, with the wrong port, with no config file. That is the point of doing it second: if this
prints 81 tools, the binary is installed correctly and everything that fails from here is a
connection problem, not an install problem.

To see what one tool takes:

```bash
iris-agentic-dev tool iris_query --schema
```

That prints the description and the full JSON Schema — every parameter, its type, its default.
Also free, also no connection.

## Step 3 — Point it at IRIS, and check what it aimed at

The fastest way is environment variables:

```bash
export IRIS_HOST=localhost
export IRIS_WEB_PORT=52773      # 52780 for the iris-community:2026.2 private web server
export IRIS_USERNAME=_SYSTEM
export IRIS_PASSWORD=SYS
export IRIS_NAMESPACE=USER
```

Then ask what it thinks it is connected to, before you run anything that writes:

```bash
iris-agentic-dev tool check_config
```

```json
{
  "connected": true,
  "connection_source": "env_vars",
  "host": "localhost",
  "port": 52780,
  "namespace": "USER",
  "iris_version": "IRIS for UNIX ... 2026.2.0L (Build 208U) ...",
  "write_tools_enabled": true,
  "destructive_tools_enabled": false
}
```

Read `connection_source` first. `env_vars` means it used what you just exported. Anything else
means it did not.

**The trap worth ten seconds.** With no config file and no environment variables, the binary
falls back to discovery: Docker container names, then VS Code Server Manager, then a port scan.
That is convenient and it is also how you end up writing to the wrong instance. On the machine
this guide was written on, a bare `check_config` reported:

```json
{
  "connection_source": "auto_discovered",
  "container": "dxlab-r39-iris",
  "port": 45083,
  "fallback_warning": "No .iris-agentic-dev.toml config file found. Connection established via fallback discovery (Docker/Server Manager/port scan). Set OBJECTSCRIPT_WORKSPACE or create a .iris-agentic-dev.toml in your project root to pin the target instance."
}
```

Three IRIS containers were running and it picked one. It said so, in `connection_source`,
`container` and `fallback_warning` — but only because something asked. Nothing else in the
tool surface prints that.

For anything past a first experiment, pin the target in a file instead:

```bash
iris-agentic-dev init        # writes ./.iris-agentic-dev.toml
```

Set `container` or `host`/`web_port` in it and commit it. Credentials stay in
`IRIS_USERNAME`/`IRIS_PASSWORD`, not in the file. The full precedence order — config file, then
environment, then Server Manager, then discovery — is in [connecting.md](connecting.md).

## Step 4 — Prove IRIS answers

```bash
iris-agentic-dev tool iris_test_server \
  --args '{"host":"localhost","web_port":52780,"username":"_SYSTEM","password":"SYS"}'
```

```json
{
  "reachable": true,
  "auth": true,
  "atelier_version": "8",
  "latency_ms": 7,
  "iris_version": "IRIS for UNIX ... 2026.2.0L (Build 208U) ...",
  "error": null
}
```

`reachable` and `auth` are separate answers on purpose. Reachable with `auth: false` is a
password problem; unreachable is a host, port or prefix problem. They get fixed in different
places.

Then a real query:

```bash
iris-agentic-dev tool iris_query \
  --args '{"query":"SELECT TOP 3 Name FROM %Dictionary.ClassDefinition WHERE Name %STARTSWITH '\''%SYSTEM.OBJ'\''"}'
```

```json
{
  "count": 2,
  "namespace": "USER",
  "rows": [{ "Name": "%SYSTEM.OBJ" }, { "Name": "%SYSTEM.OBJ.FM2Class" }],
  "success": true
}
```

That is the whole loop: your terminal, HTTP, Atelier, IRIS, back. No MCP server, no editor.

## Step 5 — Three things worth doing from the terminal

Read a class out of IRIS:

```bash
iris-agentic-dev tool iris_doc --args '{"mode":"get","name":"%SYSTEM.OBJ.cls"}'
```

Run ObjectScript:

```bash
iris-agentic-dev tool iris_execute --args '{"code":"Write $ZVERSION"}'
```

```json
{
  "output": "IRIS for UNIX ... 2026.2.0L (Build 208U) ...",
  "namespace": "USER",
  "execution_path": "atelier",
  "auth_user": "_SYSTEM",
  "success": true
}
```

See what namespaces exist:

```bash
iris-agentic-dev tool iris_namespace_list
```

```json
{ "count": 3, "namespaces": ["%SYS", "BENCHMARK", "USER"], "success": true }
```

All 81 tools work this way, and [tools.md](tools.md) is the catalogue. A note on state: a
session token from `iris_ws_open`, and `iris_doc`'s checkout prompt, live in the process that
created them, so they do not survive between two `tool` invocations. Use `batch` for those.

## Step 6 — Hand it to your editor

**Claude Code** — add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "iris-agentic-dev": {
      "command": "iris-agentic-dev",
      "args": ["mcp"],
      "env": {
        "IRIS_HOST": "localhost",
        "IRIS_WEB_PORT": "52773",
        "IRIS_USERNAME": "_SYSTEM",
        "IRIS_PASSWORD": "SYS",
        "IRIS_NAMESPACE": "USER"
      }
    }
  }
}
```

OpenCode, Cursor and VS Code + Copilot each want a different shape. They are in the README's
three Quick start sections, and Cursor has its own walkthrough in
[cursor-quickstart.md](cursor-quickstart.md).

Before restarting your editor, confirm the server answers. This is the same handshake the
editor performs:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | iris-agentic-dev mcp | head -2
```

Two JSON-RPC responses: `serverInfo` naming the version, then 81 tools. If that works and your
editor still shows no tools, the problem is the editor's config file, not this binary — and it
is almost always a path. An editor GUI does not inherit your shell `PATH`, so use the absolute
path from `which iris-agentic-dev`.

**Skills are separate.** Installing the binary installs no skills, and installing skills needs
no binary at runtime:

```bash
iris-agentic-dev skill install
iris-agentic-dev skill list
```

```text
SKILL                        CLAUDE CODE      OPENCODE     COPILOT
objectscript-review          installed        installed    n/a
objectscript-guardrails      installed        installed    n/a
...
```

What the skills are measured to be worth — currently nothing, on a graded holdout — is in the
README's [Skills](../README.md#skills--improve-ai-output-for-objectscript) section. Read it
before deciding to install them.

## When it does not work

The errors you are most likely to hit first, verbatim.

**Wrong field name.** The message lists the fields that exist, which is faster than the docs:

```text
error: bad params for iris_query: unknown field `sql`, expected one of `query`, `parameters`,
`namespace`, `force`, `confirm`, `mode`, `table`, `max_rows_affected`, `server`
```

**Wrong tool name.** Same idea — it prints the catalogue rather than guessing:

```text
error: unknown tool 'iris_quer'
available tools:
  agent_history
  ...
```

**Wrong password.** Reachable, rejected:

```json
{
  "error": "HTTP 401 Unauthorized",
  "error_code": "IRIS_UNREACHABLE",
  "hint": "Check IRIS_HOST and IRIS_WEB_PORT (and IRIS_WEB_PREFIX if using a non-root gateway)",
  "attempted_url": "http://localhost:52780/api/atelier/v1/USER/action/query"
}
```

Trust the `error` line and ignore the `hint` here: 401 is your credentials, and the host and
port in `attempted_url` were both fine. The code and hint are wrong for this case and are being
fixed.

**Wrong port, or IRIS down.** This one is ugly, and the shape is the tell rather than the text:

```text
error: ErrorData { code: ErrorCode(-32603), message: "HTTP error: error sending request for
url (http://localhost:59999/api/atelier/v1/USER/action/query)", data: None }
```

Nothing is listening at that URL. Check the port in the message against `docker ps` or your
Web Gateway. A raw struct like this instead of a JSON error means the failure happened below
the layer that formats errors properly.

**No tools in the editor.** Run the step 6 handshake. If it prints 81 tools, the binary is
fine and the editor's config has the wrong command path.

The symptom table in [troubleshooting.md](troubleshooting.md) covers the rest, including
`SESSION_STALE`, Web Gateway prefixes, and Windows Server Manager credentials.

## Where to go next

| You want to                                  | Read                                                    |
| -------------------------------------------- | ------------------------------------------------------- |
| Connect to something other than local Docker | [connecting.md](connecting.md)                          |
| Know what a tool does before calling it      | [tools.md](tools.md), or `tool <name> --schema`         |
| Understand the skill system                  | [skills.md](skills.md)                                  |
| Work out who did what to an instance         | [agent-attribution.md](agent-attribution.md)            |
| See whether any of this is measured to help  | [results.md](../specs/121-benchmark-program/results.md) |
