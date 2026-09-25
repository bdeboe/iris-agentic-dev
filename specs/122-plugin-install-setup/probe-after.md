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

## The install channel, measured on a host with no Homebrew (closing Phase 4)

T018 got the binary by copying the Homebrew install, so the download channel the skill actually
tells a bare machine to use was never exercised. Docker gives a host where the formula is
genuinely absent, so that half is now measured without a model session and without network luck.

Facts checked against the source of truth rather than against local state:

- `intersystems-community/homebrew-tap` exists on `master` with `Formula/iris-agentic-dev.rb` at
  version 1.4.2. So `brew tap intersystems-community/tap && brew install iris-agentic-dev` is a
  real pair of commands, independent of this machine already having the formula.
- `gh release view v1.4.2` publishes five binaries: `linux-x86_64`, `linux-aarch64`,
  `macos-arm64`, `macos-x86_64`, `windows-x86_64.exe`.

Run in `debian:stable-slim`, `command -v brew` empty:

| Platform           | Asset selected                   | Result                   |
| ------------------ | -------------------------------- | ------------------------ |
| `linux/amd64`      | `iris-agentic-dev-linux-x86_64`  | `iris-agentic-dev 1.4.2` |
| `linux/arm64`      | `iris-agentic-dev-linux-aarch64` | `iris-agentic-dev 1.4.2` |
| this Mac (`arm64`) | `iris-agentic-dev-macos-arm64`   | `iris-agentic-dev 1.4.2` |

`tool --list` and `skill list` both answer on the downloaded binary with no IRIS and no config,
so the install leaves a usable CLI, not just a file that runs `--version`.

Two things that changed the skill:

1. **Step 2 named two of the five assets.** An ARM Linux reader was sent to the x86_64 binary,
   which on a real ARM host stops at `cannot execute binary file`, and an Intel Mac reader to the
   arm64 one, which stops at `Bad CPU type in executable`. Step 2 now reads `uname` and selects.
   Two new tests read `.github/workflows/release.yml` and require that the skill name every asset
   a tag publishes and no asset it does not, so adding a platform to the release cannot ship
   without the install instructions following it.
2. **A wrong asset name fails at the download, not later.** `curl -fsSL` on a name that does not
   exist exits 56 with `error: 404` and writes no file, so the `&&` stops before `chmod`. The
   skill said the error would surface at `chmod` or first run; it now says what actually happens.

One check came back inconclusive and is not evidence either way: running the x86_64 binary inside
the `linux/arm64` container succeeded. That is Docker Desktop's binfmt handler on the shared VM
kernel, not portability — a real ARM Linux host has no such handler. Which is why the fix is the
`uname` selector rather than a note saying it does not matter.

What is still not measured: whether an agent reading this skill on a machine with no formula
names the Homebrew channel from the skill rather than from `brew info`. T019 could not answer that
here and this does not either — the commands are now known good, but the model's source for them
is not. Answering it needs Claude Code running on a foreign host, which means credentials on that
host, so it stays open rather than getting a workaround.
