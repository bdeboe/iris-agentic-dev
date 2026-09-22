# Research: fix what the todo-app demo exposed

All reproductions ran on `iris-dev-iris` (`IRIS for UNIX (Ubuntu Server LTS for ARM64 Containers)
2026.2.0L (Build 208U)`), 2026-09-22, against `master` at `5f38c46`.

## R1. `$ZDATETIME` inside an SQL INSERT

Scratch class `Scratch123.T` in USER, loaded and deleted in the same session.

```text
INSERT INTO Scratch123.T (Title, Created) VALUES ('a', $ZDATETIME($HOROLOG,3))
  → SQLCODE -12, "A term expected, beginning with either of: identifier, constant, aggregate,
    $$, (, :, +, -, %ALPHAUP, ... ^ INSERT INTO Scratch123 . T ( Title , Created ) VALUES ( ? , $"
INSERT INTO Scratch123.T (Title, Created) VALUES ('b', CURRENT_TIMESTAMP)
  → SQLCODE 0
```

The demo hit the identical message through `iris_query(mode="write")`, wrapped as
`ERROR #5540: SQLCODE: -12`.

**Decision**: the third example in `objectscript-sql-patterns` §7 quotes SQLCODE -12 and the
parser's `^ ... $` position marker, with `CURRENT_TIMESTAMP` as the fix.

## R2. `InitialExpression` and SQL INSERT

Same class, with `Created As %TimeStamp [ InitialExpression = {$ZDateTime($Horolog, 3)} ]` and
`Done As %Boolean [ InitialExpression = 0 ]`.

```text
INSERT INTO Scratch123.T (Title) VALUES ('c')   → SQLCODE 0
%New() + %Save() with only Title set            → 1
SELECT Title, Created, Done
  b |2026-09-22 20:56:30| done=|0|
  c |2026-09-22 20:56:30| done=|0|     ← SQL INSERT, column omitted: both defaults applied
  d |2026-09-22 20:56:30| done=|0|     ← %Save()
```

The demo's `STEPS.md` said the opposite: "a property's `InitialExpression` fires on `%Save()`, not
on a SQL INSERT. If you insert through SQL, populate the column yourself." Nothing in the
transcript tested that. The agent wrote it from belief.

**Decision**: spec US2 scenario 4 applies, so the spec is corrected, not the finding. `iris-sql`
gets the true statement, because an agent that believes the false one writes redundant columns
into every INSERT. `STEPS.md` loses the claim before it is published (FR-016).

## R3. Web application numbers in `STEPS.md` step 4

```text
Security.Applications.Get("/api/atelier") → AutheEnabled=32 Type=2 DispatchClass=%Api.Atelier
Security.Applications.Get("/todo")        → AutheEnabled=32 Type=2 DispatchClass=Demo.TodoREST
```

The claim stands as written.

## R4. How the round-trip test reaches the gate

The gate is enforced in `ServerHandler::call_tool`, so only a real MCP session exercises it
(`tests/integration/test_gate_enforcement_live.rs` header). `testing::McpSession::start(env)`
spawns `iris-agentic-dev mcp` through `clean_mcp_command` and adds back only the listed env, which
satisfies XII. `testing::live_env()` panics when `IRIS_HOST` is unset, which satisfies XI.

`iris_admin(create_webapp)` has a second gate inside the handler: `admin_write_allowed()` reads
`IRIS_ADMIN_TOOLS`. The test sets `IRIS_WRITE_TOOLS_ENABLED=1`,
`IRIS_DESTRUCTIVE_TOOLS_ENABLED=1` and `IRIS_ADMIN_TOOLS=1` in its own session env. The tiers
therefore cannot be the reason it does not run, and the "destructive tier off" skip in the first
draft of US3.5 disappears. Only an unreachable IRIS remains, and that panics.

`admin_create_webapp_impl` sets `AutheEnabled=32` and a `DispatchClass`, not `Type`. Whether a
REST dispatch works without `Type=2` is established by the test itself. If it does not, the test
creates the application through `iris_execute` as the demo did, and that becomes a finding for
`followups.md`.

**Alternatives rejected**:

- Calling handler impls directly. That skips `call_tool`, so the test would not prove the example
  works through the surface an agent uses.
- Skipping when the tier is off. The test can set the tier itself, so a skip would be a choice to
  run less.

## R5. Keeping the live `/todo` demo untouched

The demo app is compiled as `Demo.Todo`/`Demo.TodoREST` and mapped at `/todo`, and it has to
survive until the PM presents. A test that put, compiled and deleted `Demo.Todo` would destroy it.

**Decision**: the test reads the published `.cls` files and rewrites the package `Demo.` to
`IADEx123.` before the put. That covers the class names, the `##class(Demo.Todo)` calls, the
`FROM Demo.Todo` SQL and the `^Demo.TodoD` storage globals, since all of them share the prefix. The
web path is `/iadex123-todo`. Before starting, the test asserts that the rewritten source contains
no `Demo.` substring, so a missed reference fails rather than silently touching the live classes.

Teardown lives in a `Drop` guard, so it runs on panic: `delete_webapp`, `%KillExtent`, then
`iris_doc(mode="delete")` for both classes. A pre-clean runs the same steps first and ignores
not-found (spec edge case: aborted earlier run).

## R6. Parsing tier claims out of descriptions

Every write/destructive phrase in the 81 descriptions, as they read on `master`:

| Tool                     | Phrase                                                                             |
| ------------------------ | ---------------------------------------------------------------------------------- |
| `global_kill`            | `WRITE-GATED.`                                                                     |
| `iris_namespace_create`  | `WRITE-GATED.`                                                                     |
| `iris_admin`             | `Write actions (require IRIS_WRITE_TOOLS_ENABLED=1): create_user, ...`             |
| `iris_admin`             | `Destructive actions (require IRIS_DESTRUCTIVE_TOOLS_ENABLED=1): mirror_failover.` |
| `iris_credential_manage` | `Write-gated: suppressed on Live instances unless IRIS_ALLOW_PROD=1.`              |
| `iris_lookup_manage`     | `get/list_keys/list_tables always available; set/delete write-gated.`              |
| `iris_lookup_transfer`   | `export always available; import write-gated.`                                     |

**Grammar the test enforces**:

- A _claim_ is `\b(write|destructive)[ -](gated|tier|actions?)\b`, case-insensitive. The
  `[ -]` separator matters: it keeps `IRIS_WRITE_TOOLS_ENABLED`, `destructive_tools_source` and
  `destructive SQL` from counting as claims (spec edge case). `Execute-gated` and `PHI-gated`
  never match.
- A claim's _clause_ is the text between the nearest `.` or `;` on either side.
- The actions a claim covers are the tool's known actions that appear in the clause as whole
  identifiers, meaning they are not flanked by `[A-Za-z0-9_]`, so `delete` does not match inside
  `delete_user`. A claim that covers no action is a claim about the whole tool.
- A tool's known actions are the explicit keys in its `CLASSIFICATION` entry plus
  `testing::handler_match_arms(tool, "action" | "mode")`. The test asserts the set is non-empty
  for every `mixed()` tool whose default is destructive (XI: no loop over a possibly empty set).

**Checks** (each failure is a `(tool, action)` unit; `-` marks the whole tool):

1. An action claimed at tier T must resolve to T under `write_gate::classify`.
2. A whole-tool claim at tier T must equal every non-read-only tier the tool resolves to.
3. Every `(tool, action)` that resolves to destructive must be covered by a destructive claim.
   For a `de()` tool, a whole-tool destructive claim is enough.
4. A tool absent from `CLASSIFICATION` has no claims.

Checks 1 and 3 overlap on the fourteen wrong claims. Failures are collected into a set, so each
unit counts once. The expected count on `master` is 18: 7 `iris_admin`, 1 `global_kill`,
1 `iris_namespace_create`, 3 `iris_credential_manage`, 2 `iris_lookup_manage`, plus the four
silent ones `iris_global:kill`, `skill:forget`, `iris_remove_server:-` and `skill_forget:-`. The
test runs once before any description changes, and its failure output is saved to show FR-003.

**Alternative rejected**: generating descriptions from the gate table. That is out of scope, and
it would move the text away from the prose that agents read.

## R7. Where the denylist lives

`/.iad-local/denylist.txt`, one name per line, with `#` comments allowed. `/.iad-local/` is added
to `.gitignore`. It lives outside `docs/`, so a careless `git add docs/` cannot pick it up. The
scrub test resolves it from `workspace_root()`, not the CWD (XI).

## R8. Payload budget (SC-006)

The measure is the byte length of the `tools/list` result from the built binary, before and after,
using spec 114's method. The number is recorded in `quickstart.md` after implementation.
