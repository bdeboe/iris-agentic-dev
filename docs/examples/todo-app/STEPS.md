# Table plus todo app, driven from prompts

**4 minutes 53 seconds, one prompt, 25 tool calls.** The prompt was "[the PM] just asked, and I want to
test this out!!" with a screenshot of the question attached. No follow-ups and no corrections. Of
those 4:53, 6.1 seconds was time spent in tool calls; the slowest thing IRIS did was 0.6 s, and
writing plus compiling a class took 0.9 s. Everything else was the model reading output and
deciding what to do next.

Twelve of the 25 calls were iad tools, and they are the twelve that touched IRIS: the class, the
compile, the rows, the web application, the verification query. Of Claude Code's eleven, four are
`ToolSearch` loading iad's own schemas and six are shell — a `docker ps`, the `curl` checks against
the finished app, and a file export. `transcript.md` has the whole table, call by call, with what
each one did.

The full record is in `transcript.md` — every prompt, every tool call with its arguments, and
every response, in order, with timestamps.

What this is: the five prompts that built a working todo app on IRIS, and what each one did.
Everything below ran on 2026-09-22 against `iris-dev-iris` (community 2026.2, web port 52780).
Nothing here is pseudocode — the app ran at `http://localhost:52780/todo/`.

The five prompts below are the work as it would be asked for deliberately. In the actual run the
agent chose those steps itself from the one sentence above, which is the part worth showing.

Before starting, the session needs the iad tools. `check_config` should come back
`connected: true` with the port and container you expect. If it does not, or if the tools are
missing entirely, say "set up iris-agentic-dev against a local IRIS container" and let the setup
skill do it.

## 1. The table

> Create a persistent class `Demo.Todo` in USER with Title, Done, Priority and Created, plus
> class methods to add an item, toggle one, and count what is outstanding. Compile it.

The agent writes the class and pushes it with `iris_doc(mode="put", compile=true)` — one call
that stores the source in IRIS and compiles it. The compile output comes back inline, so a syntax
error surfaces in the same turn rather than after a round trip through the portal.

`Demo.Todo` is both a class and a SQL table. The last dot is the schema separator, so the table is
`Demo.Todo`, not `Demo_Todo`.

## 2. Sample rows

> Insert five sample todos with a mix of priorities, then show me the table ordered by Done.

`iris_query(mode="write")` for the INSERT, `iris_query` for the SELECT. One gotcha worth showing
a customer, because it is the kind of thing that costs an afternoon: `$ZDATETIME($HOROLOG,3)` is
ObjectScript, not SQL, and an INSERT using it fails with `SQLCODE: -12`. `CURRENT_TIMESTAMP` is
the SQL spelling. The agent hit that, read the error, and corrected itself in one step.

## 3. The web layer

> Add `Demo.TodoREST` extending %CSP.REST with routes for the page, the list fragment, add,
> toggle and delete. Return HTML fragments for HTMX, not JSON, and escape the titles.

Fragments rather than JSON means the page carries no JavaScript of its own — one `<script>` tag
for HTMX and nothing else. Every mutating route ends by calling the same `Rows()` renderer, so
the initial page and every swap after it come from one place.

Escaping is `$ZCONVERT(x, "O", "HTML")`. Verified with a title of `<b>PM</b> & "quotes"`, which
comes back as `&lt;b&gt;PM&lt;/b&gt; &amp; &quot;quotes&quot;` — ampersand first, or you
double-escape the entities you just wrote.

## 4. The web application

> Map /todo to Demo.TodoREST in USER.

This is where the safety gate showed up, and it is the part worth demoing deliberately.
`iris_admin(create_webapp)` refused:

```text
iris_admin is a destructive tool and the destructive tier is disabled
(source: inferred_default)
```

Creating a web application is a security change, so it sits behind the destructive gate, which is
off by default. The `source` field says what decided it — no guessing which config file won. Two
ways forward: set `destructive_tools_enabled = true` in `.iris-agentic-dev.toml` for that
workspace, or do it explicitly, which is what happened here:

```objectscript
Kill p
Set p("NameSpace") = "USER", p("DispatchClass") = "Demo.TodoREST"
Set p("AutheEnabled") = 32, p("Enabled") = 1, p("Type") = 2
Set tSC = ##class(Security.Applications).Create("/todo", .p)
```

`AutheEnabled = 32` is password authentication, so the browser prompts once for `_SYSTEM` / `SYS`.
`Type = 2` is a REST application. Both numbers were read off `/api/atelier` rather than guessed:

> What AutheEnabled and Type does /api/atelier use?

`Type` did not need setting. Create the same application with only `NameSpace`, `DispatchClass`,
`AutheEnabled` and `Enabled`, read it straight back, and IRIS reports `Type=2` anyway — a dispatch
class is what makes it REST. Measured after the fact, on a throwaway path that was deleted again.
Setting it does no harm; knowing it is derived saves guessing the number.

## 5. Prove it works

> Exercise the app over HTTP: the page, the fragment, add, toggle, delete.

```bash
curl -s -u _SYSTEM:SYS http://localhost:52780/todo/rows
curl -s -u _SYSTEM:SYS -X POST http://localhost:52780/todo/add \
  -d 'title=Demo for the PM&priority=high'
curl -s -u _SYSTEM:SYS -X POST http://localhost:52780/todo/toggle/6
curl -s -u _SYSTEM:SYS -X DELETE http://localhost:52780/todo/del/6
```

The outstanding count in the fragment header moves with each call, which is the cheap end-to-end
check: the header count comes from a `COUNT(*)` against the table, so if it moves, the write
landed in IRIS and not in a cache.

Then open `http://localhost:52780/todo/` in a browser and use it.

## What to point at while presenting

- The class is written, stored and compiled in one call. There is no "now export it and import it
  in the portal" step.
- SQL errors come back with the SQLCODE and the parser's position, so the next prompt is a fix
  rather than an investigation.
- The gate refusal is a feature, and it names its own source. A tool that can create a web
  application can also create a user, so it is off until someone says otherwise.
- The whole thing is inspectable afterwards with the same tools: `iris_query` for the rows,
  `iris_doc(mode="get")` for the source that is actually on the server, which is not always the
  source in your editor.

## Files

`Demo.Todo.cls` and `Demo.TodoREST.cls` here are copies of what is compiled in `iris-dev-iris`.
To put them on another instance, `iris_doc(mode="put", compile=true)` each one, then create the
web application as in step 4.

## Teardown

```objectscript
Do ##class(Demo.Todo).%KillExtent()
Do ##class(Security.Applications).Delete("/todo")  // in %SYS
```

Then delete both classes with `iris_doc(mode="delete")`.
