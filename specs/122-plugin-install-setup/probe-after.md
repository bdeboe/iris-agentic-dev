# Probe: the plugin path, measured (T018, T019)

Run 2026-09-22, after Phases 1 to 3 landed. One `claude -p` session, one prompt, no follow-ups.

## Environment

```text
cwd:  a fresh temp directory
PATH: $PROBE/bin:~/.local/bin:~/.local/share/vcs-guard/bin:/usr/bin:/bin:/usr/sbin:/sbin
      (no /opt/homebrew/bin, so no iris-agentic-dev and no brew)
MCP:  --strict-mcp-config --mcp-config '{"mcpServers":{}}'  →  zero MCP tools
      Verified separately: this leaves plugin skills loaded, including
      iris-dev:iris-agentic-dev-setup. The three iris-agentic-dev servers in
      ~/.claude.json name /opt/homebrew/bin by absolute path, so they would have
      worked regardless of PATH and had to be excluded or the probe proves nothing.
permissions: bypassPermissions, with containment rules in the prompt: install into
      $IAD_PROBE_BIN, name any container iad-probe, touch no other container.
```

## Prompt

> set up iris-agentic-dev against a local IRIS container, and finish by running a query that
> returns rows.

Plus the three containment rules above, which are an artefact of measuring on a working machine
rather than part of the scenario.

## Result: SC-001 met, with one caveat about the install step

The session ended with a query returning rows from a container it started itself. What it built:

| Piece     | Value                                                                              |
| --------- | ---------------------------------------------------------------------------------- |
| Binary    | `$IAD_PROBE_BIN/iris-agentic-dev`, v1.4.2                                          |
| Container | `iad-probe`, `intersystemsdc/iris-community:latest`, ports 61972→1972, 61773→52773 |
| Config    | `./.iris-agentic-dev.toml` pinning `container` and `web_port`                      |
| MCP       | `./.mcp.json`, project scope; handshake and `iris_query` verified over JSON-RPC    |

It cleared the password expiry, confirmed Atelier 200, and then proved the rows belonged to
`iad-probe` rather than to one of the sixteen other IRIS containers on this host by reading a
marker table three independent ways: through the binary, through raw Atelier REST on 61773, and
through `iris sql` inside the container. That last step was its own idea and is a better check
than the one the skill asks for.

**The caveat:** it obtained the binary by copying the existing Homebrew install rather than
downloading a release, because `/opt/homebrew/bin` was off PATH but the Cellar was still on disk.
So the steps after the install are measured and the install channel itself is not. A clean read
needs a host where the formula is genuinely absent.

## SC-002: the channel guess is gone, but the reading is contaminated

A separate read-only session, same PATH treatment, asked for the install commands. It answered
`brew install intersystems-community/tap/iris-agentic-dev` and said "known, not guessing", against
the 2026-09-22 baseline of _"I don't know the publish channel for this binary."_

It got there by running `brew info` and finding the formula already installed, which stripping
PATH does not hide. So the guess is gone and the cause is not established. Both this and the
baseline also ran with Tom's machine-wide `iris-agentic-dev` skill visible, which a newcomer would
not have. **SC-002 stays unproven until the probe runs somewhere the formula is absent**, which
means a CI runner or a container, not this laptop.

## What the probe found in the tool

All three reproduced by hand afterwards, so they are findings rather than transcript claims.

1. **A pin is advisory.** `check_config --container iris-nope --web-port 59999` returns
   `connected: true` against an unrelated container on a live port. `--container` is documented as
   "overrides auto-discovery" and does override it while the named target answers; when it does
   not, discovery carries on and substitutes. The same is true of `IRIS_CONTAINER` and
   `IRIS_WEB_PORT`. Since `tool` dispatches writes and the default config has
   `destructive_tools_enabled = true`, a write meant for one instance can land on another. This is
   the #111 pattern with teeth: the flag is wired, but its failure mode is silent substitution
   rather than an error.
2. **`connected: true` carries no connectivity signal** on a machine with other IRIS instances,
   which follows from 1. The `port` and `container` fields are honest about where it landed. The
   skill now says to read those and treat a successful query as the only proof.
3. **`check_config` provenance disagrees with its own behaviour.** The probe reported
   `connection_source: auto_discovered`, `config_file: null` and a `fallback_warning` that no TOML
   was found, while a valid TOML in the working directory was present and being obeyed. It
   demonstrated obedience by mis-porting the TOML and watching the reported port follow. Not
   re-verified here, so this one is the probe's account rather than mine.

None of these are filed. They belong next to the defects already drafted in
`specs/121-benchmark-program/tool-defects.md`.

## Cleanup

`iad-probe` removed, the temp directory and its binary removed. No other container was started,
stopped or read. One leftover the probe could not clear itself: an empty `.git` it created while
testing a hypothesis about the config loader needing a repo root (it does not), removal blocked by
a guard hook; it went with the temp directory.
