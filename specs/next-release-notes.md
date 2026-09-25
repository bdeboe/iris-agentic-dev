# Next release notes (staging)

Baseline: v1.4.2, whose notes are final in `docs/release-notes/v1.4.2.md`. What follows is
staged for the release after it.

I add an entry here as each user-facing change lands, so release notes are not
reconstructed from `git log` at tag time. At release time this drains into
`docs/release-notes/vX.Y.Z.md`, which is what `docs/release-checklist.md` step 4 gates on
and what becomes the GitHub release body via `gh release edit <tag> --notes`. There is no
`CHANGELOG.md` in this repo, so that release body is the changelog.

Rules for anything written here:

- Keep the three sections below, in this order, and end the drained file with a
  `vX.Y.Z...vA.B.C` compare link.
- Internal-only work (refactors, test infrastructure, CI) stays out unless a caller can
  observe the difference.
- Name the tool, flag, or file and give the number. "Improved performance" is not an entry;
  "suite went from 254 s to 61 s" is.
- Run `/no-ai-slop` detect on the drained file and fix every finding before publishing.
- First person singular. This is a one-person project.

## What's new

### Errors say where the fix is when iad knows it

Two errors from the todo-app demo now carry a `hint` field. `<CLASS DOES NOT EXIST>` for a class in
`Security.*`, `Config.*` or `SYS.*` says the class lives only in `%SYS` and to pass
`namespace: "%SYS"`. SQLCODE -12 on a `$ZDATETIME` inside an `INSERT` points at `CURRENT_TIMESTAMP`.
`iris_query`'s four `SQL_ERROR` sites and `iris_execute`'s three `IRIS_RUNTIME_ERROR` sites add the
hint when a row in `tools/error_hints.rs` matches and leave it out otherwise. Each hint cites a skill
section, and a test fails if that heading goes missing.

### A setup skill an agent can follow from a bare machine

The plugin ships `iris-agentic-dev-setup`: find or install the binary, find an IRIS before starting
one, clear the expired default password, read the web port off the container, register the server,
verify. I wrote it against a throwaway container, not the docs. It installs the right release asset
for all five platforms a tag builds, and `tests/e2e/test_setup_skill.py` checks every subcommand,
tool name and `--args` payload it names against the real CLI.

### `docs/examples/todo-app/`

The demo that exposed the fixes below, as two classes, `STEPS.md` and a transcript. A live test
puts and compiles both classes, creates the web application, adds, toggles and deletes rows, and
tears it all down.

### The skills are measured at nothing, and the README says so

The front page advertised **+27%** for `objectscript-review`. That number was true when it was
measured, under a harness that used a model to judge whether a task passed, on a 22-task repair
corpus. Both are gone. I built a graded corpus: 62 tasks, every one scored by an ObjectScript check
that prints `PASS` or `FAIL`, with no model anywhere in the scoring path. Then I ran the skills
against it on a 41-pair holdout.

Adding the skills on top of the tools moved the pass rate **+0.098, interval [-0.034, +0.229]**. Six
tasks won, two lost, p=0.1445. That is indistinguishable from no effect, and it is not an underpowered
run hiding a win: 41 pairs clears the floor of 37, so the interval is a real answer rather than a
shrug. The README leads with that now.

The tools are the other half of the same run: **+0.829, interval [+0.714, +0.944]**, from the same 41
pairs and the same check. So what iad is for has not changed. Which part of it has evidence has.

If you installed the skills expecting the +27%, that figure never covered what the graded corpus
measures. `objectscript-loop-patterns` still measures **−19%** on the older model-judged repair suite,
which is the one skill I would not install.

### `specs/121-benchmark-program/quickstart.md`

Every number above is checkable from a fresh clone. The quickstart walks it: what runs for free (the
split check, the harness suite, a dry-run cost ladder), what costs money and how much, how to resume a
run that dies halfway, and how to read `b`, `c`, the Wilson interval and the floor. It says which
commands need Docker and which need a model credential, because those are different failures.

`tests/e2e/test_published_figures.py` ties both figures to
`tests/e2e/results/ladder-121-tools-holdout.json`. If a future run moves them and the documents do
not follow, that test fails.

## Notable fixes

### The Claude Code plugin could not be installed, and then arrived nearly empty

The repo had no `.claude-plugin/marketplace.json`, so `plugin marketplace add` failed. With that
fixed, the plugin launched `iris-dev`, a binary no release has installed; on a machine with an old
`~/.local/bin/iris-dev` it started 0.9.10 silently. It launches `iris-agentic-dev` now, and a test
checks the command against both the Cargo binary name and the name the Homebrew formula installs.
The `env` block that set six connection variables to empty strings is gone, so the server resolves
its connection from `.iris-agentic-dev.toml` like every other client.

An install also delivered 3 skills instead of 38: the loader reads `skills/<name>/SKILL.md` and the
bundled ones sit one level deeper. `plugin.json` declares that directory now, plus the nested
`nopws-setup` skill two tools point at when a NoPWS build refuses a connection.

### Tool descriptions name the tier the gate enforces

Eighteen tool/action descriptions disagreed with the gate table. `iris_admin` listed seven
destructive actions as write, `global_kill` and `iris_namespace_create` said WRITE-GATED, and four
destructive actions said nothing. A unit test reads every description against the table. No gate
behaviour changed. `iris_admin` also says which actions need `IRIS_ADMIN_TOOLS=1`.

### Adding a server no longer tells the agent to restart

`iris_add_server`, `iris_remove_server` and `iris_import_servers` said to restart iad. An agent in
another repo took that at face value and stopped using iad. They point at `iris_reload_pool` now,
which rebuilds the pool in the running server.

### The CLI handed out WebSocket tokens nothing could use

`iris-agentic-dev tool iris_ws_open` opened a session, printed a token, and exited. The token was a
handle into a pool of live sockets held in that process's memory, so the next command answered
`SESSION_STALE: Session token references an unknown server or expired session` — a timeout that had
not happened, against a server that was fine. Nothing in README or `docs/` said otherwise, and
nothing said what to do instead.

`tool` refuses `iris_ws_open`, `iris_ws_exec` and `iris_ws_close` now, before it resolves a
connection, and the refusal carries the `batch` script that works:

```bash
echo '[{"tool":"iris_ws_open","args":{}},
       {"tool":"iris_ws_exec","args":{"session":"{{0.session}}","code":"Set x=1"}},
       {"tool":"iris_ws_exec","args":{"session":"{{0.session}}","code":"Write x"}},
       {"tool":"iris_ws_close","args":{"session":"{{0.session}}"}}]' | iris-agentic-dev batch
```

`batch` has been there since 1.3.0 and appeared in no documentation at all — `grep batch README.md
docs/*.md` found nothing. It is in the README command list, the troubleshooting subcommand table,
and a troubleshooting section of its own now, and `docs/tools.md` explains the process boundary
where the session tools are documented. `iris_get_log` and `iris_doc`'s checkout prompt keep state
the same per-process way and need `batch` for the same reason.

`SESSION_STALE` itself is written for whoever is reading it: the CLI text names the process
boundary and the fix, the MCP text names a closed session or a restarted server, since an MCP client
has one process for the whole conversation and no CLI to run. Both call sites read one function, so
the two cannot drift.

`docs/tools.md` also promised that closing an already-closed session returns `already_closed: true`.
The handler has never returned that — it returns `SESSION_STALE`, because by then there is no
session to look up. The doc says so now.

### `iris_servers` reports the URL it actually calls

Every entry now carries `base_url`, prefix included. `docs/tools.md` has said "every entry carries
`base_url`, the URL iad actually calls" since 1.4.2 and step 5 of the 116 plan called for it, but the
listing never emitted the key — two instances behind one gateway still came back as the same host and
port with nothing to tell them apart. It is the same shape as the two CLI examples 1.4.2 fixed:
documented behaviour that no test asked for.

## Breaking changes

`iris-agentic-dev tool iris_ws_open` exits 1 instead of printing a session token. Any script that
read the token out of it was already broken — the very next call it made returned `SESSION_STALE`.
Under MCP the three tools are unchanged.
