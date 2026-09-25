# Defects found while building the corpus — drafts, not filed

Ten problems I hit using the tool surface: nine while building 62 graded tasks, and one the graded run
turned up on its own. Nothing here is filed. This file is the draft; filing is a separate decision.

They are worth keeping together because of where they came from: building the corpus meant using
iad the way a new IRIS developer would, on a task list I could not shortcut, and that is a harder
exercise of the surface than any of its own tests. Every one of these is a thing I could not do or
a message I could not read, found by needing it.

Verification is marked per defect. "Confirmed in source" means I read the code path. "Confirmed at
the CLI" means I ran it. "Observed while building the corpus" means it happened once, during
corpus work, and I have not re-run it — the graded ladder is using the container and a repeat of a
namespace-creating call while 123 sessions grade against it is not a trade worth making.

## 1. There is no way to create a database

`iris_database_list` and `iris_database_stats` exist. Nothing creates one. A task that needs its
own database has no path through the tool surface at all, so the corpus reaches for `docker exec`
and the session stops being a measurement of iad.

Confirmed at the CLI: `tool --list | grep database` gives `iris_database_list` and
`iris_database_stats`, and that is the whole of it.

The awkward part is that this is not obviously a missing tool. Creating a database is a
`%SYS`-scoped, disk-allocating operation, and an agent that can do it unattended can fill a volume.
But `iris_namespace_create` already exists and already requires one, which means the surface
currently advertises step two of a two-step operation and leaves step one to the shell.

## 2. `iris_namespace_create` reports `created: true` for a namespace that does not exist

Two halves:

- It requires a pre-existing database, which defect 1 says cannot be made through the surface.
- When the database is missing, it still returns `created: true`, and `iris_namespace_list` then
  does not list the namespace.

The second half is the real bug. A false success is worse than a refusal: the caller writes into a
namespace it believes it has, and the failure surfaces somewhere else entirely, as a missing class
or an empty query.

Observed while building the corpus. The `created` field should be read back from
`iris_namespace_list` — or from the same `%SYS` call that would have raised — before it is
returned.

## 3. There is no `iris_namespace_delete`

Create without delete means test material accumulates. `rollout_namespace.py` needs teardown for
every graded run, so it does the teardown through `iris_execute` against `%SYS`, which is exactly
the arbitrary-execution path the gates exist to discourage.

Confirmed at the CLI: the namespace tools are `iris_namespace_create`, `iris_namespace_list`,
`compare_namespace`.

## 4. `doc put -` writes a class named `-.cls`

`doc put --help` says `-` reads content from stdin. It does — and then names the document `-`:

```
crates/iris-agentic-dev-bin/src/cmd/doc.rs:81
    let doc_name = ensure_cls_extension(&name);   // "-" -> "-.cls"
    let content = if name == "-" { ...stdin... }
```

`name` serves as both the document name and the stdin marker, so the one invocation that reads
stdin is the one invocation that cannot say what to call the result.

Confirmed in source, and confirmed at the CLI that there is no second positional to carry the name:

```
$ echo 'Class X {}' | iris-agentic-dev doc put - MyApp.X.cls
error: unexpected argument 'MyApp.X.cls' found
```

Fix: take the name as the positional and move the stdin marker to `--file -`, which is the
convention every other tool that reads stdin already uses and which `exec` already accepts.

## 5. A live test has been passing without exercising the command it names

`test_doc_get_library_object` (`crates/iris-agentic-dev-core/tests/integration/test_cmd_live.rs:247`)
writes its fixture with `doc put - CmdLiveTestGet.cls` — the four-argument form defect 4 shows clap
rejects. The test then does:

```rust
if put_output.map(|o| !o.status.success()).unwrap_or(true) {
    return;
}
```

So `put` fails on argument parsing, the test returns, `doc get` is never called, and the run
reports ok. Constitution XI, and a clean instance of the class: a skip-on-setup-failure guard whose
setup can fail for a reason that has nothing to do with the environment it was meant to skip for.

Confirmed at the CLI. The fix is defect 4's fix plus turning that `return` into a failure when the
binary and the environment are both present — the guard should skip on a missing container, not on
a broken command line.

## 6. Three CLI commands go quiet when a gate refuses

`code_edit_gate.rs:499` returns its refusal as `{success: false, error_code, code_edit_blocked,
matched, message, remediation}`. There is no `output` key and no `error` key.

`exec` prints `output`, or failing that `error`, then exits 1:

```
crates/iris-agentic-dev-bin/src/cmd/exec.rs:104-114
```

Neither key is there, so a blocked `exec` prints nothing at all and exits 1. The message naming
what matched and the remediation naming the tool to use instead are both in the body, unread.

Same shape next door:

- `query.rs:42` — `body["error"].as_str().unwrap_or("query failed")`. Prints `error: query failed`.
- `compile.rs:128` — prints `error: [CODE_EDIT_BLOCKED]: ` with an empty tail.

`doc.rs` is the only one of the four that reads `message`.

Confirmed in source for all four. This is the class, not the instance: any body whose failure
lives in `message` is invisible to three of the four commands, and the gate bodies are the ones a
user most needs to read, because they are the ones with a remediation attached. The fix is one
shared "print the failure a body describes" helper, used by all four, with the key precedence in
one place.

## 7. `doc get --namespace` is not a thing, and the error does not say why

```
$ iris-agentic-dev doc get Foo.Bar -n USER
error: unexpected argument '-n' found
  tip: to pass '-n' as a value, use '-- -n'
```

`-n` is a `doc`-level option, so `doc -n USER get Foo.Bar` works. The tip actively points the wrong
way — it suggests the flag is a value, when it is a flag in the wrong position. Every connection
option has this shape, and a user's first guess at where a flag goes is after the subcommand.

Confirmed at the CLI. Fix: flatten `ConnectionArgs` into the subcommands too, or set clap's
`args_conflicts_with_subcommands`/`global = true` on the connection args so either position parses.

## 8. `&sql` does not work through `iris_execute`

Embedded SQL in code passed to `iris_execute` fails. The executor compiles the code as a routine
fragment at runtime, and `&sql` needs a compile pass that path does not do.

Observed while building the corpus. It matters for the corpus specifically: `&sql` is how a lot of
real ObjectScript talks to tables, so a task written the way a developer would write it does not
run, and the task has to be rewritten around `%SQL.Statement` to be gradable. That is the harness
shaping the corpus, which is the thing the corpus is supposed to be free of.

Either make it work or say so in the tool description. Right now the failure reads as the user's
mistake.

## 9. `TSTART` is `<UNIMPLEMENTED>` through `iris_execute`

Same path, same cause, worse message: `<UNIMPLEMENTED>` tells the caller nothing about which layer
refused. A transaction cannot be opened, so no task can test rollback behaviour.

Observed while building the corpus.

Defects 8 and 9 are the same defect if the cause is the runtime-compile path, and the answer for
both is the same: the tool description should name what the execution path cannot do, since the
list appears to be short and knowable.

## 10. Three generation tools are advertised and inert without two undocumented env vars

The graded run's attribution table has `iris_generate_test` reached twice and `iris_generate_class`
once, three calls, all three failed, all with the same message:

```
MCP error -32600: LLM_UNAVAILABLE: Set IRIS_GENERATE_CLASS_MODEL and OPENAI_API_KEY
```

Confirmed from the run's own tool-call log: `tests/e2e/results/ladder-121-tools-holdout.json`, and
summarised in `lift-results.md`.

The message is a good one — it names both variables. The defect is upstream of it: nothing in
`tools/list` says these three tools need a second model behind them. An agent reads the surface, sees
a tool that generates a test class, calls it, and spends a turn finding out it was never going to
work. In a 300-second session that is a measurable cost, and it is the one cost the agent could not
have avoided by reading more carefully.

Two fixes, either acceptable. Say it in the description, so the agent can decide not to call it. Or
leave the tools out of `tools/list` when the variables are unset, so the surface describes what is
actually available. The second is better for an agent and worse for a human debugging why a tool
vanished, so it wants an `iris_info`-style line saying which tools are withheld and why.

`iris_generate` was never reached at all, so nothing is known about whether it has the same problem.
